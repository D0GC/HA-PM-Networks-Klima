"""Climate-Entität je Raum."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoredExtraData, RestoreEntity
from homeassistant.util import slugify

from . import PmHeizungConfigEntry
from .const import PRESETS
from .entity import RoomEntity
from .room import RoomController

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PmHeizungConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Climate-Entitäten je Raum-Subentry anlegen."""
    for subentry_id, room in entry.runtime_data.rooms.items():
        async_add_entities([PmHeizungClimate(room)], config_subentry_id=subentry_id)


class PmHeizungClimate(RoomEntity, ClimateEntity, RestoreEntity):
    """Raumthermostat „<Raum> Heizung“."""

    _attr_name = None
    _attr_translation_key = "raum"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]  # noqa: RUF012
    _attr_preset_modes = list(PRESETS)  # noqa: RUF012
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, room: RoomController) -> None:
        """Initialisieren."""
        super().__init__(room, "climate")
        self.entity_id = f"climate.pm_{slugify(room.name)}"
        self._attr_min_temp = min(room.min_temp, room.frost)
        self._attr_max_temp = room.max_temp

    async def async_added_to_hass(self) -> None:
        """Zustand wiederherstellen und Raum starten."""
        await super().async_added_to_hass()
        restored: dict[str, Any] | None = None
        if (extra := await self.async_get_last_extra_data()) is not None:
            restored = extra.as_dict()
        elif (last := await self.async_get_last_state()) is not None and last.state in (
            HVACMode.AUTO,
            HVACMode.HEAT,
            HVACMode.OFF,
        ):
            restored = {"hvac_mode": last.state}
        self.room.async_start(restored, self._persist_changed)
        self.async_on_remove(self.room.async_stop)

    @callback
    def _persist_changed(self) -> None:
        """Hook für Persistenz (Restore-Daten werden beim Schreiben erfasst)."""

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Neustartsichere Daten."""
        return RestoredExtraData(self.room.persist.as_dict())

    # --- Zustand ---------------------------------------------------------
    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode(self.room.persist.hvac_mode)

    @property
    def hvac_action(self) -> HVACAction:
        return self.room.hvac_action()

    @property
    def target_temperature(self) -> float | None:
        d = self.room.desired
        return d.target if d else None

    @property
    def current_temperature(self) -> float | None:
        return self.room.current_temperature()

    @property
    def current_humidity(self) -> float | None:
        return self.room.current_humidity()

    @property
    def preset_mode(self) -> str:
        return self.room.preset_mode()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.room.attributes()

    # --- Befehle ---------------------------------------------------------
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Solltemperatur setzen (im Auto-Modus = Overlay)."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        mode = kwargs.get(ATTR_HVAC_MODE)
        if temperature is None:
            if mode is not None:
                self.room.set_hvac_mode(mode)
            return
        self.room.set_temperature(float(temperature), mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Betriebsart setzen."""
        self.room.set_hvac_mode(hvac_mode)

    async def async_turn_on(self) -> None:
        """Einschalten = Auto."""
        self.room.set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Ausschalten."""
        self.room.set_hvac_mode(HVACMode.OFF)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Preset setzen."""
        self.room.set_preset(preset_mode)

    # --- Dienste ---------------------------------------------------------
    async def async_service_boost(self, dauer: float | None = None) -> None:
        """pm_heizung.boost."""
        self.room.boost(dauer)

    async def async_service_set_overlay(
        self, temperatur: float, dauer: float | None = None
    ) -> None:
        """pm_heizung.set_overlay."""
        if self.room.persist.hvac_mode != HVACMode.AUTO:
            self.room.set_temperature(temperatur)
            return
        self.room.set_overlay(temperatur, dauer)

    async def async_service_clear_overlay(self) -> None:
        """pm_heizung.clear_overlay."""
        self.room.clear_overlay()
