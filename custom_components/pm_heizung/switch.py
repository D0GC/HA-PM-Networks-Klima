"""Schalter: Hauptschalter Heizung, Beratung, Luftreiniger-Automatik je Raum."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from . import PmHeizungConfigEntry
from .beratung import Advisor
from .entity import AirEntity, CentralEntity, safe_writer
from .luft import AirRoom

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PmHeizungConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Schalter anlegen."""
    data = entry.runtime_data
    async_add_entities([MainSwitch(data.central)])
    try:
        if data.advisor is not None:
            async_add_entities([AdviceSwitch(data.central, data.advisor)])
        for subentry_id, air in data.air.items():
            if air.purifier.entity_id:
                async_add_entities([PurifierSwitch(air)], config_subentry_id=subentry_id)
    except Exception:
        _LOGGER.exception("PM Klima: Luft-/Beratungsschalter konnten nicht angelegt werden")


class MainSwitch(CentralEntity, SwitchEntity):
    """Aus = Heizungssteuerung pausiert und sendet nichts an die Thermostate."""

    _attr_translation_key = "aktiv"

    def __init__(self, central: Any) -> None:
        """Initialisieren."""
        super().__init__(central, "aktiv")
        self.entity_id = "switch.pm_heizung_aktiv"

    @property
    def is_on(self) -> bool:
        return self.central.state.aktiv

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Einschalten (Zustand wird in der Zentrale gespeichert)."""
        self.central.set_active(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Ausschalten."""
        self.central.set_active(False)


class AdviceSwitch(CentralEntity, SwitchEntity):
    """Globaler Schalter der Beratung (Benachrichtigungen). Standard: aus."""

    _attr_translation_key = "beratung"

    def __init__(self, central: Any, advisor: Advisor) -> None:
        """Initialisieren."""
        super().__init__(central, "beratung")
        self.advisor = advisor
        self.entity_id = "switch.pm_klima_beratung"

    async def async_added_to_hass(self) -> None:
        """Auf Beratung hören."""
        await SwitchEntity.async_added_to_hass(self)
        self.async_on_remove(self.advisor.add_listener(safe_writer(self)))

    @property
    def is_on(self) -> bool:
        return self.advisor.aktiv

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Beratung einschalten (gespeichert)."""
        self.advisor.set_active(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Beratung ausschalten."""
        self.advisor.set_active(False)


class PurifierSwitch(AirEntity, SwitchEntity, RestoreEntity):
    """Luftreiniger-Automatik eines Raums (Standard aus, Zustand neustartsicher)."""

    _attr_translation_key = "luftreiniger_automatik"
    _unrecorded_attributes = frozenset({"ziel", "begruendung", "pausiert_bis", "letzter_befehl"})

    def __init__(self, air: AirRoom) -> None:
        """Initialisieren."""
        super().__init__(air, "luftreiniger_automatik")
        self.entity_id = f"switch.pm_{slugify(air.room.name)}_luftreiniger_automatik"

    async def async_added_to_hass(self) -> None:
        """Zustand wiederherstellen (ohne sofort zu senden)."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.air.purifier.enabled = last.state == STATE_ON

    @property
    def is_on(self) -> bool:
        return self.air.purifier.enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.air.purifier.attributes()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Automatik ein."""
        self.air.purifier.set_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Automatik aus (Gerät bleibt im aktuellen Zustand)."""
        self.air.purifier.set_enabled(False)
        self.async_write_ha_state()
