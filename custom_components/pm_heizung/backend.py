"""Thermostat-Backends: Fähigkeiten, Gerätetyp und Cloud-Abhängigkeiten.

PM Klima spricht Thermostate nur über die Standarddienste der climate-Domain an. Welche
Betriebsart dabei „heizen“ bzw. „aus“ bedeutet, hängt vom Gerät ab und wird aus dessen
Attribut ``hvac_modes`` abgeleitet:

* Heizen: ``heat``, sonst ``heat_cool``, sonst ``auto`` (Geräte ohne eigenen Heizmodus).
* Aus: ``off``, falls vorhanden. Geräte ohne ``off`` (z. B. manche Zigbee-Thermostate)
  erhalten stattdessen ihre niedrigste Solltemperatur im Heizmodus.

Der Gerätetyp (tado über die Cloud, tado lokal über HomeKit/Matter, sonstige) steuert nur
Vorgaben – etwa, ob ein externes „aus“ standardmäßig als Fenstererkennung gilt.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.climate import ATTR_HVAC_MODES, HVACMode
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.loader import IntegrationNotFound, async_get_integration

from .const import BACKEND_GENERIC, BACKEND_TADO_CLOUD, BACKEND_TADO_LOCAL

TADO_CLOUD_PLATFORMS = frozenset({"tado"})
LOCAL_PLATFORMS = frozenset({"homekit_controller", "matter"})
HEAT_MODE_ORDER = (HVACMode.HEAT, HVACMode.HEAT_COOL, HVACMode.AUTO)


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Was ein Thermostat kann."""

    heat_mode: str  # Betriebsart, in der ein Sollwert gesendet wird
    can_off: bool  # kennt „off“


def capabilities(state: State | None) -> Capabilities:
    """Fähigkeiten aus dem Zustand ableiten (ohne Angabe: heat/off wie bisher)."""
    modes = [str(m) for m in (state.attributes.get(ATTR_HVAC_MODES) or [])] if state else []
    if not modes:
        return Capabilities(HVACMode.HEAT, True)
    heat = next((m for m in HEAT_MODE_ORDER if m in modes), HVACMode.HEAT)
    return Capabilities(str(heat), HVACMode.OFF in modes)


def backend_kind(hass: HomeAssistant, entity_id: str) -> str:
    """tado über die Cloud, tado lokal (HomeKit/Matter) oder generisch."""
    reg = er.async_get(hass).async_get(entity_id)
    if reg is None:
        return BACKEND_GENERIC
    if reg.platform in TADO_CLOUD_PLATFORMS:
        return BACKEND_TADO_CLOUD
    if reg.platform in LOCAL_PLATFORMS and reg.device_id:
        device = dr.async_get(hass).async_get(reg.device_id)
        if device and "tado" in (device.manufacturer or "").casefold():
            return BACKEND_TADO_LOCAL
    return BACKEND_GENERIC


def is_tado(kind: str) -> bool:
    """Ein tado-Gerät (Cloud oder lokal)?"""
    return kind in (BACKEND_TADO_CLOUD, BACKEND_TADO_LOCAL)


def entity_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Zustand oder Registereintrag vorhanden (auch wenn gerade nicht verfügbar)."""
    return (
        hass.states.get(entity_id) is not None
        or er.async_get(hass).async_get(entity_id) is not None
    )


async def async_describe_entities(
    hass: HomeAssistant, entity_ids: Iterable[str]
) -> dict[str, dict[str, Any]]:
    """Herkunft je Entität: Integration, IoT-Klasse und ob sie die Cloud braucht."""
    registry = er.async_get(hass)
    result: dict[str, dict[str, Any]] = {}
    for entity_id in dict.fromkeys(entity_ids):
        reg = registry.async_get(entity_id)
        platform = reg.platform if reg else None
        iot_class: str | None = None
        if platform:
            try:
                iot_class = (await async_get_integration(hass, platform)).iot_class
            except IntegrationNotFound:
                iot_class = None
        result[entity_id] = {
            "domain": split_entity_id(entity_id)[0],
            "integration": platform,
            "iot_class": iot_class,
            "cloud": bool(iot_class and iot_class.startswith("cloud")),
            "vorhanden": entity_exists(hass, entity_id),
            "typ": backend_kind(hass, entity_id) if entity_id.startswith("climate.") else None,
        }
    return result
