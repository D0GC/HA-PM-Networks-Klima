"""Sensoren: Grund je Raum, Abwesenheitsphase, Luft je Raum, Klima-Empfehlung."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import PmHeizungConfigEntry
from .beratung import Advisor
from .const import MOLD_LEVELS, PHASES, QUALITIES, REASONS
from .entity import AirEntity, CentralEntity, RoomEntity, safe_writer
from .luft import AirRoom
from .room import RoomController

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PmHeizungConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Sensoren anlegen."""
    data = entry.runtime_data
    async_add_entities([PhaseSensor(data.central)])
    for subentry_id, room in data.rooms.items():
        async_add_entities([ReasonSensor(room)], config_subentry_id=subentry_id)
    # Luft & Beratung (fehlerisoliert: Heizungs-Entitäten sind bereits angelegt)
    try:
        for subentry_id, air in data.air.items():
            async_add_entities(
                [AirQualitySensor(air), MoldSensor(air), VentDurationSensor(air)],
                config_subentry_id=subentry_id,
            )
        if data.advisor is not None:
            async_add_entities([AdviceSensor(data.central, data.advisor)])
    except Exception:
        _LOGGER.exception("PM Klima: Luft-/Beratungssensoren konnten nicht angelegt werden")


class ReasonSensor(RoomEntity, SensorEntity):
    """Warum hat der Raum gerade diese Solltemperatur?"""

    _attr_translation_key = "grund"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = REASONS

    def __init__(self, room: RoomController) -> None:
        """Initialisieren."""
        super().__init__(room, "grund")
        self.entity_id = f"sensor.pm_{slugify(room.name)}_grund"

    @property
    def native_value(self) -> str:
        return self.room.reason

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = self.room.attributes()
        attrs.pop("grund", None)
        return attrs


class PhaseSensor(CentralEntity, SensorEntity):
    """Abwesenheitsphase der Zentrale."""

    _attr_translation_key = "abwesenheitsphase"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = PHASES

    def __init__(self, central: Any) -> None:
        """Initialisieren."""
        super().__init__(central, "phase")
        self.entity_id = "sensor.pm_heizung_abwesenheitsphase"

    @property
    def native_value(self) -> str:
        return self.central.state.phase

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.central.state
        return {
            "jemand_zuhause": s.jemand_zuhause,
            "abwesend_seit": s.abwesend_seit.isoformat() if s.abwesend_seit else None,
            "absenkung_ab": s.absenkung_ab.isoformat() if s.absenkung_ab else None,
            "gesperrt": s.gesperrt,
            "sperre_grund": s.sperre_grund,
            "sperre_seit": s.sperre_seit.isoformat() if s.sperre_seit else None,
            "sperre_wechsel_wartet": s.sperre_wechsel_wartet,
            "sperre_wirkung": s.sperre_wirkung,
            "abwesenheit_wirksam": s.abwesenheit_wirksam,
            "abstaende_m": s.abstaende_m,
            "richtungen": s.richtungen,
            "beschreibung": s.grund,
            "aktiv": s.aktiv,
        }


class AirQualitySensor(AirEntity, SensorEntity):
    """Luftqualitätsindex gut/mittel/schlecht mit Begründung."""

    _attr_translation_key = "luftqualitaet"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = QUALITIES
    # Messwerte und Begründungen ändern sich laufend -> nicht in die Datenbank
    _unrecorded_attributes = frozenset(
        {
            "temperatur_innen",
            "feuchte_innen",
            "temperatur_aussen",
            "feuchte_aussen",
            "abs_feuchte_innen",
            "abs_feuchte_aussen",
            "taupunkt",
            "co2",
            "pm25",
            "regen",
            "gruende",
            "lueften_noetig",
            "lueften_sinnvoll",
            "zu_trocken",
            "feuchte_grenze",
        }
    )

    def __init__(self, air: AirRoom) -> None:
        """Initialisieren."""
        super().__init__(air, "luftqualitaet")
        self.entity_id = f"sensor.pm_{slugify(air.room.name)}_luftqualitaet"

    @property
    def native_value(self) -> str | None:
        return self.air.result.quality

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        res = self.air.result
        return {
            **self.air.base_attributes(),
            "gruende": res.quality_reasons,
            "lueften_noetig": res.needed,
            "lueften_sinnvoll": res.sensible,
            "zu_trocken": res.too_dry,
            "feuchte_grenze": self.air.humidity_limit,
        }


class MoldSensor(AirEntity, SensorEntity):
    """Relative Feuchte an der (kältesten) Wandoberfläche in % plus Stufe."""

    _attr_translation_key = "schimmelrisiko"
    _unrecorded_attributes = frozenset(
        {
            "wandtemperatur",
            "taupunkt",
            "frsi",
            "stufen",
            "temperatur_innen",
            "temperatur_aussen",
            "feuchte_innen",
        }
    )
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, air: AirRoom) -> None:
        """Initialisieren."""
        super().__init__(air, "schimmelrisiko")
        self.entity_id = f"sensor.pm_{slugify(air.room.name)}_schimmelrisiko"

    @property
    def native_value(self) -> float | None:
        return self.air.result.wall_rh

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        res = self.air.result
        return {
            "stufe": res.mold,
            "stufen": MOLD_LEVELS,
            "wandtemperatur": res.wall_temp,
            "taupunkt": res.dew_point,
            "frsi": self.air.inputs.frsi,
            "temperatur_innen": self.air.inputs.t_in,
            "temperatur_aussen": self.air.inputs.t_out,
            "feuchte_innen": self.air.inputs.rh_in,
        }


class VentDurationSensor(AirEntity, SensorEntity):
    """Empfohlene Stoßlüftdauer in Minuten."""

    _attr_translation_key = "lueftdauer"
    _unrecorded_attributes = frozenset(
        {"temperatur_aussen", "fenster_offen", "fenster_offen_seit", "fenster_schliessen"}
    )
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, air: AirRoom) -> None:
        """Initialisieren."""
        super().__init__(air, "lueftdauer")
        self.entity_id = f"sensor.pm_{slugify(air.room.name)}_lueftdauer"

    @property
    def native_value(self) -> int:
        return self.air.result.duration

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        inp = self.air.inputs
        since = self.air.window_open_since()
        return {
            "temperatur_aussen": inp.t_out,
            "fenster_offen": inp.window_open,
            # fester Zeitpunkt statt minütlich wechselnder Dauer
            "fenster_offen_seit": since.isoformat() if since else None,
            "fenster_schliessen": self.air.result.window_close_due,
        }


class AdviceSensor(CentralEntity, SensorEntity):
    """Wichtigste aktuelle Klima-Empfehlung, Attribut „liste“ mit allen."""

    _attr_translation_key = "klima_empfehlung"
    _unrecorded_attributes = frozenset({"liste", "anzahl", "letzte_meldung", "beratung_aktiv"})

    def __init__(self, central: Any, advisor: Advisor) -> None:
        """Initialisieren."""
        super().__init__(central, "klima_empfehlung")
        self.advisor = advisor
        self.entity_id = "sensor.pm_klima_empfehlung"

    async def async_added_to_hass(self) -> None:
        """Auf Beratung hören (statt auf die Zentrale)."""
        await SensorEntity.async_added_to_hass(self)
        self.async_on_remove(self.advisor.add_listener(safe_writer(self)))

    @property
    def native_value(self) -> str:
        return self.advisor.top_text()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self.advisor.as_list()
        return {
            "liste": items,
            "anzahl": len(items),
            "beratung_aktiv": self.advisor.aktiv,
            "letzte_meldung": self.advisor.last_message,
        }
