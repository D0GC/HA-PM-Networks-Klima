"""PM Klima (Domain pm_heizung) – Heizungssteuerung für beliebige Thermostate plus Luft und Beratung.

Architektur:
* Heizung (central.py, room.py): unverändert eigenständig, kennt Luft/Beratung nicht.
* Luft (luft.py, luft_calc.py): liest Heizung und Sensoren nur, eigene Entitäten.
* Beratung (beratung.py, beratung_texte.py): sammelt Empfehlungen, meldet gedrosselt.
Fehler in Luft/Beratung werden abgefangen (auch schon beim Einrichten) – die Heizung
startet und läuft in jedem Fall.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .beratung import Advisor
from .central import Central
from .const import (
    CONF_ADV_ALEXA,
    CONF_ADV_PANEL,
    CONF_ADV_PUSH,
    CONF_ADV_PUSH_MAP,
    CONF_EXT_OFF_AS_WINDOW,
    CONF_LANGUAGE,
    CONF_WINDOWS,
    CONFIG_MINOR_VERSION,
    CONFIG_VERSION,
    DOMAIN,
    LANGUAGE_DE,
    NAME,
    PLATFORMS,
    SUBENTRY_ROOM,
)
from .entity import central_device
from .luft import AirRoom
from .room import RoomController
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class PmHeizungData:
    """Laufzeitdaten eines Config-Entrys."""

    central: Central
    rooms: dict[str, RoomController] = field(default_factory=dict)
    air: dict[str, AirRoom] = field(default_factory=dict)
    advisor: Advisor | None = None


type PmHeizungConfigEntry = ConfigEntry[PmHeizungData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Dienste einmalig registrieren."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Schema 1.1 (v1.0.x) -> 1.2 (v2.0.0) -> 1.3 (v2.0.1) -> 1.4 (v2.1.0).

    Nur additive Änderungen, Entitäten und gespeicherte Daten bleiben unverändert:
    1.2: Kanäle der Beratung (Push an, Alexa/Panel aus, keine Zuordnung), Titel „PM Klima“.
    1.3: je Raum „Externes Aus als Fensteröffnung werten“ = an, wenn kein Fenstersensor.
    1.4: Sprache der Texte bleibt Deutsch (bestehende Installationen); je Raum wird der
         bisher implizite Wert „Externes Aus als Fensteröffnung“ festgeschrieben, damit der
         neue geräteabhängige Standard nichts verändert.
    """
    if entry.version > CONFIG_VERSION:
        return False  # Downgrade von einer unbekannten Hauptversion
    if entry.version == 1 and entry.minor_version < 2:
        options: dict[str, Any] = dict(entry.options)
        options.setdefault(CONF_ADV_PUSH, True)
        options.setdefault(CONF_ADV_ALEXA, False)
        options.setdefault(CONF_ADV_PANEL, False)
        options.setdefault(CONF_ADV_PUSH_MAP, "")
        title = NAME if entry.title == "PM Heizung" else entry.title
        hass.config_entries.async_update_entry(entry, options=options, title=title, minor_version=2)
    if entry.version == 1 and entry.minor_version < 3:
        for subentry in list(entry.subentries.values()):
            if subentry.subentry_type != SUBENTRY_ROOM:
                continue
            if CONF_EXT_OFF_AS_WINDOW in subentry.data:
                continue
            data = {**subentry.data, CONF_EXT_OFF_AS_WINDOW: not subentry.data.get(CONF_WINDOWS)}
            hass.config_entries.async_update_subentry(entry, subentry, data=data)
        hass.config_entries.async_update_entry(entry, minor_version=3)
    if entry.version == 1 and entry.minor_version < 4:
        for subentry in list(entry.subentries.values()):
            if subentry.subentry_type != SUBENTRY_ROOM or CONF_EXT_OFF_AS_WINDOW in subentry.data:
                continue
            data = {**subentry.data, CONF_EXT_OFF_AS_WINDOW: not subentry.data.get(CONF_WINDOWS)}
            hass.config_entries.async_update_subentry(entry, subentry, data=data)
        options = dict(entry.options)
        options.setdefault(CONF_LANGUAGE, LANGUAGE_DE)
        hass.config_entries.async_update_entry(entry, options=options, minor_version=4)
        _LOGGER.info("PM Klima: Konfiguration auf Schema 1.%s migriert", CONFIG_MINOR_VERSION)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PmHeizungConfigEntry) -> bool:
    """Zentrale, Räume, Luft und Beratung einrichten."""
    central = Central(hass, entry.entry_id, entry.options)
    await central.async_start()
    data = PmHeizungData(central=central)
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_ROOM:
            continue
        data.rooms[subentry_id] = RoomController(
            hass, entry, central, subentry_id, {**subentry.data, "name": subentry.title}
        )
    entry.runtime_data = data
    entry.async_on_unload(central.async_stop)
    for room in data.rooms.values():
        entry.async_on_unload(room.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    # Zentralgerät vorab anlegen (Räume verweisen per via_device_id darauf)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **central_device(entry.entry_id)
    )
    central.device_id = device.id

    # Luft & Beratung: fehlerisoliert – ein Fehler hier verhindert nie die Heizung
    try:
        for subentry_id, room in data.rooms.items():
            sub = entry.subentries[subentry_id]
            air = AirRoom(hass, entry, room, sub.data)
            await air.async_load()
            data.air[subentry_id] = air
        data.advisor = Advisor(hass, entry, central, data.air)
    except Exception:
        _LOGGER.exception("PM Klima: Luft/Beratung konnten nicht eingerichtet werden")
        data.air.clear()
        data.advisor = None

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Aufräumen immer VOR dem Start registrieren, damit auch ein Teilstart sauber endet
    for air in data.air.values():
        entry.async_on_unload(air.async_stop)
        air.async_start()
    if data.advisor is not None:
        entry.async_on_unload(data.advisor.async_stop)
        try:
            await data.advisor.async_start()
        except Exception:
            _LOGGER.exception("PM Klima: Beratung konnte nicht gestartet werden")
            data.advisor.async_stop()
    return True


async def _async_update_listener(hass: HomeAssistant, entry: PmHeizungConfigEntry) -> None:
    """Optionen/Räume geändert -> neu laden."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PmHeizungConfigEntry) -> bool:
    """Entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
