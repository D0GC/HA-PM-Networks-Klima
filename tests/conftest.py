"""Gemeinsame Fixtures für PM Heizung."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from datetime import timedelta
import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    setup_test_component_platform,
)

from custom_components.pm_heizung.const import DOMAIN, SUBENTRY_ROOM

BACKEND = "climate.tado_wohnzimmer"


class FakeThermostat(ClimateEntity):
    """Simuliert ein Thermostat (HomeKit/tado): heat/off/auto + Solltemperatur."""

    _attr_should_poll = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]  # noqa: RUF012
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 5
    _attr_max_temp = 25
    _attr_target_temperature_step = 0.5

    def __init__(self, unique_id: str, name: str) -> None:
        """Initialisieren."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_hvac_mode = HVACMode.AUTO
        self._attr_target_temperature = 20.0
        self._attr_current_temperature = 20.5
        self._attr_current_humidity = 55.0
        self.calls: list[tuple[str, Any]] = []
        self.fail = False  # Dienstaufruf wirft Fehler
        self.ignore = False  # Befehl wird stillschweigend ignoriert
        self.round_down_to_int = False  # Gerät rundet intern auf ganze Grad

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Soll setzen."""
        self.calls.append(("set_temperature", dict(kwargs)))
        if self.fail:
            raise HomeAssistantError("Thermostat nicht erreichbar")
        if self.ignore:
            return
        if (mode := kwargs.get("hvac_mode")) is not None:
            self._attr_hvac_mode = HVACMode(mode)
        temp = kwargs["temperature"]
        self._attr_target_temperature = float(int(temp)) if self.round_down_to_int else temp
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Modus setzen."""
        self.calls.append(("set_hvac_mode", hvac_mode))
        if self.fail:
            raise HomeAssistantError("Thermostat nicht erreichbar")
        if self.ignore:
            return
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    def set_available(self, available: bool) -> None:
        """Verfügbarkeit simulieren."""
        self._attr_available = available
        self.async_write_ha_state()

    def external_change(self, mode: HVACMode, temperature: float | None = None) -> None:
        """Jemand dreht direkt am Thermostat (neuer Kontext)."""
        self._context = None
        self._attr_hvac_mode = mode
        if temperature is not None:
            self._attr_target_temperature = temperature
        self.async_write_ha_state()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Custom Integrations erlauben."""


@pytest.fixture(autouse=True)
def no_integration_errors(
    request: pytest.FixtureRequest, caplog: pytest.LogCaptureFixture
) -> Generator[None]:
    """Kein Test darf unerwartet ERROR-Meldungen der Integration erzeugen."""
    yield
    if request.node.get_closest_marker("allow_errors"):
        return
    errors = [
        r
        for r in caplog.get_records("call")
        if r.levelno >= logging.ERROR and r.name.startswith("custom_components.pm_heizung")
    ]
    assert not errors, [r.getMessage() for r in errors]


@pytest.fixture
async def backend(hass: HomeAssistant) -> FakeThermostat:
    """Fake-Thermostat als climate-Entität bereitstellen."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.language = "de"  # Texte werden auf Deutsch geprüft (Option „auto“)
    entity = FakeThermostat("fake_wz", "tado Wohnzimmer")
    setup_test_component_platform(hass, "climate", [entity])
    assert await async_setup_component(hass, "climate", {"climate": {"platform": "test"}})
    await hass.async_block_till_done()
    assert hass.states.get(BACKEND) is not None
    return entity


def base_options(**overrides: Any) -> dict[str, Any]:
    """Standard-Optionen der Zentrale."""
    opts: dict[str, Any] = {
        "personen": ["person.anna", "person.ben"],
        "anwesenheit_entitaeten": [
            "input_boolean.anna_ist_zuhause",
            "input_boolean.ben_ist_zuhause",
        ],
        "abstand_sensoren": ["sensor.abstand_anna", "sensor.abstand_ben"],
        "richtung_sensoren": ["sensor.richtung_anna", "sensor.richtung_ben"],
        "absenkung": 3.0,
        "mindesttemperatur": 16.0,
        "fern_absenkung": 2.0,
        "vorheizstufe": "balance",
        "annaeherung_erforderlich": True,
        "verlassen_verzoegerung": 5,
        "aussentemperatur_sensor": "sensor.aussentemperatur",
        "aussentemperatur_grenze": 17.0,
        "sperre_wirkung": "zeitplan",
    }
    opts.update(overrides)
    return opts


def room_data(**overrides: Any) -> dict[str, Any]:
    """Standard-Daten eines Raums."""
    data: dict[str, Any] = {
        "klimageraete": [BACKEND],
        "fenstersensoren": ["binary_sensor.fenster_1_wohnzimmer"],
        "zeitplan": "schedule.heizung_wohnzimmer",
        "zeitplan_attribut": "temperatur",
        "komforttemperatur": 21.0,
        "ecotemperatur": 18.0,
        "frostschutztemperatur": 7.0,
        "min_temperatur": 5.0,
        "max_temperatur": 25.0,
        "overlay_modus": "naechster_block",
        "overlay_minuten": 60,
        "boost_minuten": 30,
        "fenster_verzoegerung_offen": 30,
        "fenster_verzoegerung_zu": 10,
        "fenster_aktion": "frostschutz",
        "aus_mit_frostschutz": False,
        "externe_aenderung_uebernehmen": True,
    }
    data.update(overrides)
    return data


def set_home_states(hass: HomeAssistant, home: bool = True) -> None:
    """Umgebungszustände setzen."""
    st = "on" if home else "off"
    hass.states.async_set("person.anna", "home" if home else "not_home")
    hass.states.async_set("person.ben", "home" if home else "not_home")
    hass.states.async_set("input_boolean.anna_ist_zuhause", st)
    hass.states.async_set("input_boolean.ben_ist_zuhause", st)
    hass.states.async_set(
        "sensor.abstand_anna", "0", {"unit_of_measurement": "m", "device_class": "distance"}
    )
    hass.states.async_set(
        "sensor.abstand_ben", "0", {"unit_of_measurement": "m", "device_class": "distance"}
    )
    hass.states.async_set("sensor.richtung_anna", "arrived")
    hass.states.async_set("sensor.richtung_ben", "arrived")
    hass.states.async_set("sensor.aussentemperatur", "5.0", {"unit_of_measurement": "°C"})
    hass.states.async_set("binary_sensor.fenster_1_wohnzimmer", "off")


def set_schedule(
    hass: HomeAssistant, on: bool, temp: float | None = None, next_in_min: int = 60
) -> None:
    """Zeitplan-Entität simulieren (wie schedule-Helfer mit Blockdaten)."""
    from homeassistant.util import dt as dt_util

    attrs: dict[str, Any] = {
        "next_event": dt_util.now() + timedelta(minutes=next_in_min),
        "editable": True,
    }
    if on and temp is not None:
        attrs["temperatur"] = temp
    hass.states.async_set("schedule.heizung_wohnzimmer", "on" if on else "off", attrs)


@pytest.fixture
def setup_integration(
    hass: HomeAssistant, backend: FakeThermostat
) -> Callable[..., Awaitable[MockConfigEntry]]:
    """Integration mit einem Raum einrichten."""

    async def _setup(
        options: dict[str, Any] | None = None, data: dict[str, Any] | None = None, home: bool = True
    ) -> MockConfigEntry:
        set_home_states(hass, home)
        if not hass.states.get("schedule.heizung_wohnzimmer"):
            set_schedule(hass, True, 21.0)
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="PM Heizung",
            unique_id=DOMAIN,
            data={},
            options=options or base_options(),
            subentries_data=[
                {
                    "data": data or room_data(),
                    "subentry_type": SUBENTRY_ROOM,
                    "title": "Wohnzimmer",
                    "unique_id": "wohnzimmer",
                }
            ],
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup


async def advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float) -> None:
    """Zeit vorspulen und Timer auslösen."""
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # zweiter Durchlauf für Folge-Timer
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def backend_state(hass: HomeAssistant) -> tuple[str, float | None]:
    """(Modus, Soll) des Fake-Thermostats."""
    st = hass.states.get(BACKEND)
    assert st is not None
    return st.state, st.attributes.get("temperature")


async def settle(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Entprellung (5 s) und Mindestsendeabstand (10 s) abwarten."""
    await advance(hass, freezer, 11)
