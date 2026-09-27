"""v2.0.1 – Auflagen aus dem unabhängigen Review (Punkte 1–8)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.core import Context, HomeAssistant, ServiceCall, State
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import mock_restore_cache_with_extra_data

from custom_components.pm_heizung.const import DOMAIN

from .conftest import FakeThermostat, advance, backend_state, room_data, settle

CLIMATE = "climate.pm_wohnzimmer"
WINDOW = "binary_sensor.fenster_1_wohnzimmer"


def attrs(hass: HomeAssistant) -> dict:
    return dict(hass.states.get(CLIMATE).attributes)


def issue(hass: HomeAssistant, entry) -> ir.IssueEntry | None:
    sub_id = next(iter(entry.subentries))
    return ir.async_get(hass).async_get_issue(DOMAIN, f"extern_aus_{sub_id}")


def sends(backend: FakeThermostat) -> int:
    return len(backend.calls)


# --- 1: Pingpong-Schutz bei externem „aus“ ---------------------------------------
async def test_1_pingpong_backoff_issue_and_quiet(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Ab 3 Ablehnungen in 30 min: 5/10 min zurückhalten, Hinweis, Ruhe -> Hinweis weg."""
    entry = await setup_integration()  # Raum MIT Fenstersensor -> Ablehnen
    await advance(hass, freezer, 120)
    base = sends(backend)

    # Ablehnung 1 und 2: sofortiges Zurückstellen, noch kein Hinweis
    for n in (1, 2):
        backend.external_change(HVACMode.OFF)
        await settle(hass, freezer)
        assert backend_state(hass) == ("heat", 21.0)
        assert sends(backend) == base + n
        await advance(hass, freezer, 60)
    assert issue(hass, entry) is None

    # Ablehnung 3: 5 min zurückhalten, Reparaturhinweis
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    assert backend_state(hass)[0] == "off"
    assert sends(backend) == base + 2
    found = issue(hass, entry)
    assert found is not None
    assert found.translation_key == "extern_aus"
    assert found.translation_placeholders["raum"] == "Wohnzimmer"
    assert found.translation_placeholders["pause"] == "5"
    assert attrs(hass)["extern_aus_pause"] is True
    await advance(hass, freezer, 4 * 60)
    assert sends(backend) == base + 2
    await advance(hass, freezer, 70)
    assert sends(backend) == base + 3
    assert backend_state(hass) == ("heat", 21.0)

    # Ablehnung 4: 10 min
    await advance(hass, freezer, 90)
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    await advance(hass, freezer, 9 * 60)
    assert sends(backend) == base + 3
    await advance(hass, freezer, 70)
    assert sends(backend) == base + 4

    # 60 min Ruhe -> Hinweis entfernt, Schutz zurückgesetzt
    await advance(hass, freezer, 61 * 60)
    assert issue(hass, entry) is None
    assert attrs(hass)["extern_aus_pause"] is False
    assert attrs(hass)["extern_aus_abgelehnt"] == 4


async def test_1_own_change_releases_hold(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """„aussetzen bis zur nächsten eigenen Änderung“: eigene Änderung sendet sofort."""
    await setup_integration()
    await advance(hass, freezer, 120)
    base = sends(backend)
    # tado schaltet jeweils sofort nach dem Zurückstellen wieder aus (schnelles Pingpong)
    for _ in range(3):
        backend.external_change(HVACMode.OFF)
        await settle(hass, freezer)
        await advance(hass, freezer, 30)
    assert backend_state(hass)[0] == "off"  # zurückgehalten
    assert sends(backend) == base + 2
    # schnelle Wiederholungen zählen für den Schutz, nicht als „abgelehnt“ (evtl. Poll)
    assert attrs(hass)["extern_aus_pause"] is True
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 22}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 22.0)


# --- 2: externes „aus“ als Fensteröffnung (Räume ohne Fenstersensor) --------------
async def test_2_ext_off_as_window_without_sensor(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Ohne Fenstersensor: 30 min Frostschutz (ohne Senden), danach zurück."""
    await setup_integration(data=room_data(fenstersensoren=None))
    await advance(hass, freezer, 120)
    base = sends(backend)
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    a = attrs(hass)
    assert a["grund"] == "fenster_extern"
    assert hass.states.get("sensor.pm_wohnzimmer_grund").state == "fenster_extern"
    assert a["temperature"] == 7.0
    assert a["anzeige"].startswith("Fenster (Thermostat) · Frostschutz bis ")
    assert a["extern_aus_abgelehnt"] == 0
    assert a["naechster_wechsel_grund"] == "fenster_extern_ende"
    # während der 30 min: nichts senden (tado „aus“ genügt), erneutes „aus“ egal
    await advance(hass, freezer, 10 * 60)
    backend.external_change(HVACMode.OFF)
    await advance(hass, freezer, 15 * 60)
    assert sends(backend) == base
    assert backend_state(hass)[0] == "off"
    await advance(hass, freezer, 6 * 60)
    await settle(hass, freezer)
    assert attrs(hass)["grund"] == "zeitplan"
    assert backend_state(hass) == ("heat", 21.0)
    assert sends(backend) == base + 1


async def test_2_ext_window_ends_when_tado_turns_on(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """tado schaltet selbst wieder ein -> Fenster (tado) vorbei, kein Overlay übernommen."""
    await setup_integration(data=room_data(fenstersensoren=None))
    await advance(hass, freezer, 120)
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    backend.external_change(HVACMode.HEAT, 19.0)
    await settle(hass, freezer)
    a = attrs(hass)
    assert a["grund"] == "zeitplan"
    assert a["fenster_extern_bis"] is None
    assert backend_state(hass) == ("heat", 21.0)


async def test_2_user_action_ends_ext_window_and_option_off(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Eigene Bedienung beendet es; Option aus -> ablehnen wie mit Fenstersensor."""
    entry = await setup_integration(data=room_data(fenstersensoren=None))
    await advance(hass, freezer, 120)
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 22}, blocking=True
    )
    await settle(hass, freezer)
    assert attrs(hass)["grund"] == "manuell"
    assert backend_state(hass) == ("heat", 22.0)
    room = next(iter(entry.runtime_data.rooms.values()))
    assert room.ext_off_as_window is True
    room.data["extern_aus_als_fenster"] = False
    assert room.ext_off_as_window is False
    await advance(hass, freezer, 120)
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    assert attrs(hass)["extern_aus_abgelehnt"] == 1
    assert backend_state(hass) == ("heat", 22.0)


async def test_2_ext_window_survives_restart(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Die Fensteröffnung (tado) ist Teil der Restore-Daten."""
    until = dt_util.utcnow() + timedelta(minutes=20)
    mock_restore_cache_with_extra_data(
        hass,
        [(State(CLIMATE, "auto"), {"hvac_mode": "auto", "ext_window_until": until.isoformat()})],
    )
    backend._attr_hvac_mode = HVACMode.OFF
    backend.async_write_ha_state()
    await setup_integration(data=room_data(fenstersensoren=None))
    await settle(hass, freezer)
    assert attrs(hass)["grund"] == "fenster_extern"
    assert backend_state(hass)[0] == "off"
    await advance(hass, freezer, 21 * 60)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)


# --- 4: set_temperature mit hvac_mode off --------------------------------------------
async def test_4_set_temperature_with_mode_off_stays_off(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """climate.set_temperature(hvac_mode=off) bleibt aus und merkt den Wert."""
    await setup_integration()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": CLIMATE, "temperature": 22.5, "hvac_mode": "off"},
        blocking=True,
    )
    await settle(hass, freezer)
    st = hass.states.get(CLIMATE)
    assert st.state == "off"
    assert st.attributes["eingestellt"] == 22.5
    assert backend_state(hass)[0] == "off"
    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": CLIMATE, "hvac_mode": "heat"}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 22.5)


# --- 5: Luftreiniger --------------------------------------------------------------
FAN = "fan.lr"
PM = "sensor.pm25"
SWITCH = "switch.pm_wohnzimmer_luftreiniger_automatik"


def fan_calls(hass: HomeAssistant) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    async def _record(call: ServiceCall) -> None:
        calls.append(call)

    for svc in ("turn_on", "turn_off", "set_preset_mode"):
        hass.services.async_register("fan", svc, _record)
    return calls


def set_fan(hass: HomeAssistant, state: str, preset: str | None, ctx: Context | None = None):
    hass.states.async_set(
        FAN,
        state,
        {"preset_modes": ["auto", "sleep", "medium", "fast", "turbo"], "preset_mode": preset},
        context=ctx,
    )


async def purifier_setup(hass, setup_integration, freezer, preset: str | None):
    freezer.move_to("2026-01-15 10:00:00+01:00")
    calls = fan_calls(hass)
    hass.states.async_set(PM, "4")
    set_fan(hass, "on", preset)
    entry = await setup_integration(
        data=room_data(pm25_sensor=PM, luftreiniger=FAN, luftreiniger_pause=60)
    )
    await hass.services.async_call("switch", "turn_on", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()
    return entry, calls


async def test_5_case_insensitive_presets(hass: HomeAssistant, setup_integration, freezer):
    """Gerät mit kleingeschriebenen Presets: „auto“ == Auto, Befehle in Geräteschreibweise."""
    _, calls = await purifier_setup(hass, setup_integration, freezer, "auto")
    assert calls == []
    hass.states.async_set(PM, "50")
    await advance(hass, freezer, 11 * 60)
    assert calls[-1].data == {"entity_id": FAN, "preset_mode": "turbo"}


async def test_5_missing_preset_is_not_auto(hass: HomeAssistant, setup_integration, freezer):
    """An ohne preset_mode gilt nicht als Auto -> Automatik stellt Auto ein."""
    _, calls = await purifier_setup(hass, setup_integration, freezer, None)
    assert [(c.service, c.data["preset_mode"]) for c in calls] == [("set_preset_mode", "auto")]


async def test_5_late_echo_not_manual(hass: HomeAssistant, setup_integration, freezer):
    """Zwischenzustände/Polling nach eigenem Befehl (fremder Kontext) pausieren nicht."""
    _, calls = await purifier_setup(hass, setup_integration, freezer, "sleep")
    assert calls[-1].data["preset_mode"] == "auto"
    set_fan(hass, "on", "medium")  # Zwischenzustand, fremder Kontext, < 120 s
    await advance(hass, freezer, 60)
    set_fan(hass, "on", "sleep")
    await advance(hass, freezer, 60)
    set_fan(hass, "on", "auto")  # verspätetes Echo nach 200 s (Polling), fremder Kontext
    await advance(hass, freezer, 5)
    assert hass.states.get(SWITCH).attributes["pausiert_bis"] is None
    # echte Bedienung nach > 5 min
    await advance(hass, freezer, 6 * 60)
    set_fan(hass, "on", "fast")
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).attributes["pausiert_bis"] is not None


async def test_5_pause_survives_restart(hass: HomeAssistant, setup_integration, freezer):
    """Pause nach manueller Bedienung ist neustartsicher (Store)."""
    entry, calls = await purifier_setup(hass, setup_integration, freezer, "auto")
    await advance(hass, freezer, 10 * 60)
    set_fan(hass, "on", "medium")
    await hass.async_block_till_done()
    until = hass.states.get(SWITCH).attributes["pausiert_bis"]
    assert until is not None
    await advance(hass, freezer, 5)  # Store schreiben
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "on"
    assert hass.states.get(SWITCH).attributes["pausiert_bis"] == until
    count = len(calls)
    await advance(hass, freezer, 30 * 60)
    assert len(calls) == count  # weiterhin pausiert
    await advance(hass, freezer, 31 * 60)
    assert calls[-1].data["preset_mode"] == "auto"


# --- 6: Teilstart der Beratung räumt auf ----------------------------------------------
@pytest.mark.allow_errors
async def test_6_advisor_partial_start_cleans_up(
    hass: HomeAssistant, setup_integration, freezer, monkeypatch
) -> None:
    """Scheitert async_start nach dem Anmelden von Listenern, wird alles gelöst."""
    from custom_components.pm_heizung import beratung

    original = beratung.Advisor.async_start
    ticks: list[int] = []

    async def failing(self):
        await original(self)
        raise RuntimeError("Teilstart")

    monkeypatch.setattr(beratung.Advisor, "async_start", failing)
    monkeypatch.setattr(beratung.Advisor, "run", lambda self: ticks.append(1))
    entry = await setup_integration()
    advisor = entry.runtime_data.advisor
    assert advisor is not None
    assert advisor._unsubs == []
    await advance(hass, freezer, 5 * 60)
    assert ticks == []
    assert backend_state(hass) == ("heat", 21.0)
    assert await hass.config_entries.async_unload(entry.entry_id)


# --- 7: Recorder --------------------------------------------------------------------
def test_7_unrecorded_attributes() -> None:
    """Laufend wechselnde Detailwerte und Listen werden nicht aufgezeichnet."""
    from custom_components.pm_heizung.binary_sensor import VentSensor
    from custom_components.pm_heizung.sensor import (
        AdviceSensor,
        AirQualitySensor,
        MoldSensor,
        VentDurationSensor,
    )
    from custom_components.pm_heizung.switch import PurifierSwitch

    assert {"liste", "letzte_meldung"} <= AdviceSensor._unrecorded_attributes
    assert {
        "co2",
        "pm25",
        "gruende",
        "abs_feuchte_innen",
    } <= AirQualitySensor._unrecorded_attributes
    assert {"wandtemperatur", "taupunkt"} <= MoldSensor._unrecorded_attributes
    assert {"fenster_offen_seit"} <= VentDurationSensor._unrecorded_attributes
    assert {"gruende", "abs_feuchte_aussen"} <= VentSensor._unrecorded_attributes
    assert {"pausiert_bis", "begruendung"} <= PurifierSwitch._unrecorded_attributes


async def test_7_no_minutely_state_writes(hass: HomeAssistant, setup_integration, freezer):
    """Offenes Fenster: Lüftdauer-Sensor ändert sich nicht jede Minute."""
    await setup_integration()
    hass.states.async_set(WINDOW, "on")
    await advance(hass, freezer, 5)
    events: list[Any] = []
    hass.bus.async_listen(
        "state_changed",
        lambda e: (
            events.append(e) if e.data["entity_id"] == "sensor.pm_wohnzimmer_lueftdauer" else None
        ),
    )
    for _ in range(5):
        await advance(hass, freezer, 61)
    assert events == []
    st = hass.states.get("sensor.pm_wohnzimmer_lueftdauer")
    assert st.attributes["fenster_offen_seit"] is not None
    assert "fenster_offen_min" not in st.attributes


# --- 8: via_device_id auf HA 2026.9 ----------------------------------------------
def test_8_detection_against_ha_2026_9_3_source() -> None:
    """Erkennung gegen den echten Auszug aus HA 2026.9.3 (DeviceInfo + Signatur)."""
    from custom_components.pm_heizung.entity import supports_via_device_id

    from .fixtures import ha_2026_9_3_device_registry as ha2609

    assert supports_via_device_id(ha2609.DeviceInfo, ha2609.DeviceRegistry.async_get_or_create)
    # installierte Testversion (2026.2.3) kennt den Parameter noch nicht
    assert not supports_via_device_id(dr.DeviceInfo, dr.DeviceRegistry.async_get_or_create)
    # nur TypedDict-Schlüssel ohne Parameter reicht nicht
    assert not supports_via_device_id(ha2609.DeviceInfo, dr.DeviceRegistry.async_get_or_create)


async def test_8_new_parameter_used_on_2026_9_path(
    hass: HomeAssistant, setup_integration, monkeypatch
) -> None:
    """2026.9-Pfad simuliert: nur via_device_id wird übergeben, nie das veraltete via_device."""
    from custom_components.pm_heizung import entity

    original = dr.DeviceRegistry.async_get_or_create
    seen: list[dict[str, Any]] = []

    def get_or_create_2026_9(self, *, via_device_id=UNDEFINED, **kwargs):
        if "via_device" in kwargs and via_device_id is not UNDEFINED:
            raise AssertionError("via_device und via_device_id gleichzeitig (2026.9 lehnt ab)")
        seen.append({"via_device_id": via_device_id, "via_device": kwargs.get("via_device")})
        if via_device_id is not UNDEFINED:
            parent = self.async_get(via_device_id)
            assert parent is not None, "via_device_id muss eine registrierte Geräte-ID sein"
            kwargs["via_device"] = next(iter(parent.identifiers))
        return original(self, **kwargs)

    monkeypatch.setattr(entity, "HAS_VIA_DEVICE_ID", True)
    monkeypatch.setattr(dr.DeviceRegistry, "async_get_or_create", get_or_create_2026_9)
    entry = await setup_integration()
    central_id = entry.runtime_data.central.device_id
    child_calls = [c for c in seen if c["via_device_id"] is not UNDEFINED]
    assert child_calls, "Raum-/Luftgeräte müssen via_device_id nutzen"
    assert all(c["via_device_id"] == central_id for c in child_calls)
    assert all(c["via_device"] is None for c in seen)
    reg = dr.async_get(hass)
    sub_id = next(iter(entry.subentries))
    assert reg.async_get_device(identifiers={(DOMAIN, sub_id)}).via_device_id == central_id
