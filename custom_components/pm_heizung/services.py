"""Dienste von PM Klima."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
import voluptuous as vol

from .backend import async_describe_entities, entity_exists
from .const import (
    ATTR_CHANNEL,
    ATTR_DURATION,
    ATTR_NEW,
    ATTR_OLD,
    ATTR_TEMPERATURE,
    ATTR_TOPIC,
    BACKEND_TADO_CLOUD,
    CHANNELS,
    CONF_ADV_PANEL_SERVICE,
    CONF_ADV_PUSH_MAP,
    CONF_CLIMATES,
    DOMAIN,
    NOTIFY_TOPICS,
    SERVICE_ADVICE_TEST,
    SERVICE_BOOST,
    SERVICE_CLEAR_OVERLAY,
    SERVICE_DEPENDENCIES,
    SERVICE_REEVALUATE,
    SERVICE_REPLACE_ENTITY,
    SERVICE_SET_OVERLAY,
    SUBENTRY_ROOM,
)

DURATION = vol.All(vol.Coerce(float), vol.Range(min=0, max=24 * 60))
ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
# Optionen, die Dienste statt Entitäten enthalten
NOT_ENTITIES = {CONF_ADV_PANEL_SERVICE, CONF_ADV_PUSH_MAP}


def _entity_values(data: Mapping[str, Any]) -> list[str]:
    """Alle Entitäts-IDs einer Konfiguration (Einzelwerte und Listen)."""
    found: list[str] = []
    for key, value in data.items():
        if key in NOT_ENTITIES:
            continue
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str) and ENTITY_ID_RE.match(item):
                found.append(item)
    return found


def _replace(data: Mapping[str, Any], old: str, new: str) -> tuple[dict[str, Any], list[str]]:
    """Entität in einer Konfiguration ersetzen -> (neue Daten, geänderte Schlüssel)."""
    result: dict[str, Any] = dict(data)
    keys: list[str] = []
    for key, value in data.items():
        if key in NOT_ENTITIES:
            continue
        if value == old:
            result[key] = new
            keys.append(key)
        elif isinstance(value, list) and old in value:
            result[key] = list(dict.fromkeys(new if v == old else v for v in value))
            keys.append(key)
    return result, keys


def _loaded_entry(hass: HomeAssistant) -> ConfigEntry:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nicht_geladen")


async def async_dependencies(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Herkunft aller konfigurierten Entitäten, besonders Cloud- und tado-Abhängigkeiten."""
    central = await async_describe_entities(hass, _entity_values(entry.options))
    rooms: dict[str, dict[str, Any]] = {}
    for sub in entry.subentries.values():
        if sub.subentry_type == SUBENTRY_ROOM:
            rooms[sub.title] = await async_describe_entities(hass, _entity_values(sub.data))
    everything: dict[str, dict[str, Any]] = {**central}
    for described in rooms.values():
        everything.update(described)
    tado_cloud = sorted(e for e, i in everything.items() if i["integration"] == "tado")
    return {
        "zentrale": central,
        "raeume": rooms,
        "cloud": sorted(e for e, i in everything.items() if i["cloud"]),
        "tado_cloud": tado_cloud,
        "tado_cloud_thermostate": sorted(
            e for e, i in everything.items() if i["typ"] == BACKEND_TADO_CLOUD
        ),
        "fehlend": sorted(e for e, i in everything.items() if not i["vorhanden"]),
        "tado_integration_entbehrlich": not tado_cloud,
    }


async def async_replace_entity(
    hass: HomeAssistant, entry: ConfigEntry, old: str, new: str
) -> dict[str, Any]:
    """Eine Entität in Zentrale und allen Räumen durch eine andere ersetzen."""
    if split_entity_id(old)[0] != split_entity_id(new)[0]:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="domain_verschieden",
            translation_placeholders={"alt": old, "neu": new},
        )
    if not entity_exists(hass, new):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entitaet_fehlt",
            translation_placeholders={"entitaet": new},
        )
    changes: list[str] = []
    rooms = [s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_ROOM]
    for sub in rooms:
        if old in (sub.data.get(CONF_CLIMATES) or []):
            continue
        if new in (sub.data.get(CONF_CLIMATES) or []):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="thermostat_vergeben",
                translation_placeholders={"entitaet": new, "raum": sub.title},
            )
    updates: list[tuple[Any, dict[str, Any]]] = []
    for sub in rooms:
        data, keys = _replace(sub.data, old, new)
        if keys:
            updates.append((sub, data))
            changes.extend(f"{sub.title}: {k}" for k in keys)
    options, keys = _replace(entry.options, old, new)
    changes.extend(f"Zentrale: {k}" for k in keys)
    if not changes:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="nicht_verwendet",
            translation_placeholders={"entitaet": old},
        )
    # Jede Änderung löst ein Neuladen aus; das geplante Neuladen fasst sie zusammen.
    for sub, data in updates:
        hass.config_entries.async_update_subentry(entry, sub, data=data)
    if keys:
        hass.config_entries.async_update_entry(entry, options=options)
    return {"alt": old, "neu": new, "geaendert": changes}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Dienste registrieren."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_BOOST,
        entity_domain=CLIMATE_DOMAIN,
        schema={vol.Optional(ATTR_DURATION): DURATION},
        func="async_service_boost",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_OVERLAY,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            vol.Required(ATTR_TEMPERATURE): vol.All(vol.Coerce(float), vol.Range(min=5, max=30)),
            vol.Optional(ATTR_DURATION): DURATION,
        },
        func="async_service_set_overlay",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_OVERLAY,
        entity_domain=CLIMATE_DOMAIN,
        schema={},
        func="async_service_clear_overlay",
    )

    async def _reevaluate(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            entry.runtime_data.central.async_reevaluate()
            for room in entry.runtime_data.rooms.values():
                room.evaluate()

    hass.services.async_register(DOMAIN, SERVICE_REEVALUATE, _reevaluate, schema=vol.Schema({}))

    async def _dependencies(call: ServiceCall) -> ServiceResponse:
        return await async_dependencies(hass, _loaded_entry(hass))

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEPENDENCIES,
        _dependencies,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )

    async def _replace_entity(call: ServiceCall) -> ServiceResponse:
        return await async_replace_entity(
            hass, _loaded_entry(hass), call.data[ATTR_OLD], call.data[ATTR_NEW]
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REPLACE_ENTITY,
        _replace_entity,
        schema=vol.Schema(
            {vol.Required(ATTR_OLD): cv.entity_id, vol.Required(ATTR_NEW): cv.entity_id}
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def _advice_test(call: ServiceCall) -> ServiceResponse:
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED and entry.runtime_data.advisor:
                return await entry.runtime_data.advisor.async_test(
                    call.data[ATTR_CHANNEL], call.data.get(ATTR_TOPIC)
                )
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="beratung_nicht_verfuegbar"
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADVICE_TEST,
        _advice_test,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHANNEL): vol.In(CHANNELS),
                vol.Optional(ATTR_TOPIC): vol.In(NOTIFY_TOPICS),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
