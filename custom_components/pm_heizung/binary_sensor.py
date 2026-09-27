"""Binärsensoren je Raum: „Fenster offen“ (aggregiert) und „Lüften empfohlen“."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import PmHeizungConfigEntry
from .entity import AirEntity, RoomEntity
from .luft import AirRoom
from .room import RoomController

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PmHeizungConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Fenster-Binärsensoren anlegen (nur Räume mit Fenstersensoren)."""
    for subentry_id, room in entry.runtime_data.rooms.items():
        if room.windows:
            async_add_entities([WindowSensor(room)], config_subentry_id=subentry_id)
    try:
        for subentry_id, air in entry.runtime_data.air.items():
            async_add_entities([VentSensor(air)], config_subentry_id=subentry_id)
    except Exception:
        _LOGGER.exception("PM Klima: Lüften-Sensoren konnten nicht angelegt werden")


class WindowSensor(RoomEntity, BinarySensorEntity):
    """Mindestens ein Fenster des Raums ist offen."""

    _attr_translation_key = "fenster_offen"
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, room: RoomController) -> None:
        """Initialisieren."""
        super().__init__(room, "fenster")
        self.entity_id = f"binary_sensor.pm_{slugify(room.name)}_fenster_offen"

    @property
    def is_on(self) -> bool:
        return self.room.window.raw_open

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "wirksam": self.room.window.effective_open,
            "offene_sensoren": self.room.window.open_sensors,
        }


class VentSensor(AirEntity, BinarySensorEntity):
    """Lüften empfohlen (nötig und sinnvoll, Fenster zu)."""

    _attr_translation_key = "lueften_empfohlen"
    _unrecorded_attributes = frozenset(
        {
            "noetig",
            "sinnvoll",
            "gruende",
            "dauer_min",
            "abs_feuchte_innen",
            "abs_feuchte_aussen",
            "regen",
        }
    )

    def __init__(self, air: AirRoom) -> None:
        """Initialisieren."""
        super().__init__(air, "lueften_empfohlen")
        self.entity_id = f"binary_sensor.pm_{slugify(air.room.name)}_lueften_empfohlen"

    @property
    def is_on(self) -> bool:
        return self.air.result.recommended

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        res = self.air.result
        return {
            "noetig": res.needed,
            "sinnvoll": res.sensible,
            "gruende": res.need_reasons,
            "dauer_min": res.duration,
            "abs_feuchte_innen": res.abs_in,
            "abs_feuchte_aussen": res.abs_out,
            "regen": self.air.inputs.raining,
        }
