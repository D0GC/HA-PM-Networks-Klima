"""v2.0.0 – Heizung: UX-Korrekturen A1–A9."""

from __future__ import annotations

import logging

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import pytest

from custom_components.pm_heizung.const import DOMAIN
from custom_components.pm_heizung.entity import HAS_VIA_DEVICE_ID

from .conftest import (
    FakeThermostat,
    advance,
    backend_state,
    base_options,
    room_data,
    set_schedule,
    settle,
)

CLIMATE = "climate.pm_wohnzimmer"
WINDOW = "binary_sensor.fenster_1_wohnzimmer"


def attrs(hass: HomeAssistant) -> dict:
    return dict(hass.states.get(CLIMATE).attributes)


async def call(hass: HomeAssistant, service: str, **data) -> None:
    domain = "climate"
    if service in ("boost", "set_overlay", "clear_overlay"):
        domain = DOMAIN
    await hass.services.async_call(domain, service, {"entity_id": CLIMATE, **data}, blocking=True)


async def open_window(hass: HomeAssistant, freezer) -> None:
    hass.states.async_set(WINDOW, "on")
    await advance(hass, freezer, 31)
    await settle(hass, freezer)


# --- A1: Presets „zeitplan“ und „manuell“ --------------------------------------
async def test_a1_presets_schedule_and_manual(hass: HomeAssistant, setup_integration, freezer):
    """Auto ohne Overlay = zeitplan, mit Overlay = manuell; „zeitplan“ wählen = clear_overlay."""
    await setup_integration()
    await settle(hass, freezer)
    st = hass.states.get(CLIMATE)
    assert "zeitplan" in st.attributes["preset_modes"]
    assert "manuell" in st.attributes["preset_modes"]
    assert st.attributes["preset_mode"] == "zeitplan"

    await call(hass, "set_temperature", temperature=23)
    assert attrs(hass)["preset_mode"] == "manuell"
    await call(hass, "set_preset_mode", preset_mode="zeitplan")
    await settle(hass, freezer)
    a = attrs(hass)
    assert a["preset_mode"] == "zeitplan"
    assert a["overlay_bis"] is None
    assert backend_state(hass) == ("heat", 21.0)

    # Preset eco im Auto-Modus = Overlay mit eigenem Namen
    await call(hass, "set_preset_mode", preset_mode="eco")
    assert attrs(hass)["preset_mode"] == "eco"
    assert attrs(hass)["anzeige"].startswith("Eco · 18 °C bis ")
    # „manuell“ ohne Overlay hält den aktuellen Zeitplanwert fest
    await call(hass, "set_preset_mode", preset_mode="zeitplan")
    await call(hass, "set_preset_mode", preset_mode="manuell")
    a = attrs(hass)
    assert a["preset_mode"] == "manuell"
    assert a["temperature"] == 21.0
    assert a["overlay_bis"] is not None


async def test_a1_preset_schedule_from_heat_returns_to_auto(
    hass: HomeAssistant, setup_integration, freezer
):
    """„zeitplan“ im heat-Modus schaltet auf auto zurück; heat zeigt „manuell“."""
    await setup_integration()
    await call(hass, "set_hvac_mode", hvac_mode="heat")
    assert attrs(hass)["preset_mode"] == "manuell"
    await call(hass, "set_preset_mode", preset_mode="zeitplan")
    assert hass.states.get(CLIMATE).state == "auto"
    assert attrs(hass)["preset_mode"] == "zeitplan"
    await call(hass, "set_hvac_mode", hvac_mode="off")
    assert attrs(hass)["preset_mode"] == "none"


# --- A2: target_temperature / eingestellt ---------------------------------------
async def test_a2_target_is_effective_input_shown_immediately(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
):
    """Eingabe sofort sichtbar (vor dem Senden); Fenster übersteuert sichtbar."""
    await setup_integration()
    await settle(hass, freezer)
    backend.calls.clear()
    await call(hass, "set_temperature", temperature=23)
    # noch nichts gesendet (Entprellung), Anzeige zeigt aber bereits 23
    assert backend.calls == []
    a = attrs(hass)
    assert a["temperature"] == 23.0
    assert a["eingestellt"] == 23.0
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 23.0)

    await open_window(hass, freezer)
    a = attrs(hass)
    assert a["temperature"] == 7.0  # wirksamer Sollwert
    assert a["eingestellt"] == 23.0  # Eingabe bleibt erhalten
    assert a["grund"] == "fenster"
    assert a["anzeige"] == "Fenster offen · Frostschutz (danach 23 °C)"
    # Eingabe bei offenem Fenster: gespeichert, sichtbar in „eingestellt“
    await call(hass, "set_temperature", temperature=22)
    assert attrs(hass)["eingestellt"] == 22.0
    assert attrs(hass)["temperature"] == 7.0
    hass.states.async_set(WINDOW, "off")
    await advance(hass, freezer, 11)
    await settle(hass, freezer)
    assert attrs(hass)["temperature"] == 22.0


# --- A3: Temperatur setzen bei off -----------------------------------------------
async def test_a3_set_temperature_when_off_switches_to_heat(
    hass: HomeAssistant, setup_integration, freezer
):
    """Wie tado: aus + Temperatur -> heat mit diesem Wert."""
    await setup_integration()
    await call(hass, "set_hvac_mode", hvac_mode="off")
    await settle(hass, freezer)
    assert backend_state(hass)[0] == "off"
    await call(hass, "set_temperature", temperature=22.5)
    assert hass.states.get(CLIMATE).state == "heat"
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 22.5)
    assert attrs(hass)["grund"] == "manuell"


# --- A4: auto -> heat übernimmt nie Frost/Fenster/Boost --------------------------
async def test_a4_heat_from_window_uses_schedule(hass: HomeAssistant, setup_integration, freezer):
    """Fenster offen (7 °C) -> heat: Zeitplanwert, nicht Frostschutz."""
    set_schedule(hass, True, 21.5)
    await setup_integration()
    await open_window(hass, freezer)
    assert attrs(hass)["temperature"] == 7.0
    await call(hass, "set_hvac_mode", hvac_mode="heat")
    assert attrs(hass)["eingestellt"] == 21.5


async def test_a4_heat_from_boost_uses_last_manual(hass: HomeAssistant, setup_integration, freezer):
    """Boost (25 °C) -> heat: letzter Handwert statt Boost."""
    await setup_integration()
    await call(hass, "set_temperature", temperature=22)
    await call(hass, "boost", dauer=30)
    assert attrs(hass)["temperature"] == 25.0
    await call(hass, "set_hvac_mode", hvac_mode="heat")
    a = attrs(hass)
    assert a["temperature"] == 22.0
    assert a["boost_bis"] is None  # heat beendet Boost


async def test_a4_frost_preset_never_hand_value(hass: HomeAssistant, setup_integration, freezer):
    """Preset Frostschutz als Overlay -> heat nimmt Zeitplan bzw. Komfort."""
    await setup_integration()
    await call(hass, "set_preset_mode", preset_mode="frostschutz")
    assert attrs(hass)["temperature"] == 7.0
    await call(hass, "set_hvac_mode", hvac_mode="heat")
    assert attrs(hass)["temperature"] == 21.0


async def test_a4_heat_uses_active_overlay(hass: HomeAssistant, setup_integration, freezer):
    """Aktives manuelles Overlay wird in heat übernommen."""
    await setup_integration()
    await call(hass, "set_temperature", temperature=23.5)
    await call(hass, "set_hvac_mode", hvac_mode="heat")
    assert attrs(hass)["temperature"] == 23.5


# --- A5: heat/off löschen Overlays, overlay_bis nur in auto ---------------------
async def test_a5_mode_change_clears_overlay(hass: HomeAssistant, setup_integration, freezer):
    """heat/off löschen Overlay und Boost; naechster_wechsel_grund gesetzt."""
    await setup_integration()
    await call(hass, "set_temperature", temperature=23)
    assert attrs(hass)["overlay_bis"] is not None
    await call(hass, "set_hvac_mode", hvac_mode="heat")
    a = attrs(hass)
    assert a["overlay_bis"] is None
    assert a["naechster_wechsel"] is None
    assert a["naechster_wechsel_grund"] == "manuell_dauerhaft"
    # Boost in heat: nächster Wechsel = Boost-Ende
    await call(hass, "boost", dauer=15)
    a = attrs(hass)
    assert a["naechster_wechsel"] == a["boost_bis"]
    assert a["naechster_wechsel_grund"] == "boost_ende"
    await call(hass, "set_hvac_mode", hvac_mode="off")
    a = attrs(hass)
    assert a["boost_bis"] is None
    assert a["naechster_wechsel_grund"] == "aus"
    # zurück nach auto: kein altes Overlay taucht wieder auf
    await call(hass, "set_hvac_mode", hvac_mode="auto")
    await settle(hass, freezer)
    assert attrs(hass)["grund"] == "zeitplan"
    assert attrs(hass)["naechster_wechsel_grund"] == "zeitplan"


# --- A6: hvac_action optimistisch ------------------------------------------------
async def test_a6_hvac_action_optimistic(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
):
    """Abgeleitet bis das Backend bestätigt; kein Flackern; off sofort."""
    backend._attr_hvac_action = HVACAction.IDLE
    await setup_integration()
    await settle(hass, freezer)
    await advance(hass, freezer, 130)
    assert attrs(hass)["hvac_action"] == "idle"  # 21 soll, 20,5 ist -> gemeldet idle

    await call(hass, "set_temperature", temperature=23)
    assert attrs(hass)["hvac_action"] == "heating"  # sofort, Backend noch 21
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 23.0)
    # Backend bestätigt Sollwert, meldet aber (Polling) noch idle -> kein Flackern
    assert attrs(hass)["hvac_action"] == "heating"
    await advance(hass, freezer, 60)
    assert attrs(hass)["hvac_action"] == "heating"
    backend._attr_hvac_action = HVACAction.HEATING
    backend.async_write_ha_state()
    await hass.async_block_till_done()
    assert attrs(hass)["hvac_action"] == "heating"

    # aus -> sofort off, auch wenn das Backend noch heizt
    await call(hass, "set_hvac_mode", hvac_mode="off")
    assert attrs(hass)["hvac_action"] == "off"


async def test_a6_after_hold_backend_wins(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
):
    """Nach Bestätigung und Haltezeit gilt die gemeldete Aktivität."""
    backend._attr_hvac_action = HVACAction.IDLE
    await setup_integration()
    await call(hass, "set_temperature", temperature=23)
    await settle(hass, freezer)
    await advance(hass, freezer, 125)
    backend.async_write_ha_state()
    await hass.async_block_till_done()
    assert attrs(hass)["hvac_action"] == "idle"


# --- A7: anzeige ------------------------------------------------------------------
async def test_a7_display_texts(hass: HomeAssistant, setup_integration, freezer):
    """Deutsche Kurztexte für alle Zustände."""
    await setup_integration(options=base_options(sperre_mindesthaltezeit=0))
    await settle(hass, freezer)
    assert attrs(hass)["anzeige"].startswith("Zeitplan · 21 °C bis ")
    await call(hass, "set_temperature", temperature=22)
    assert attrs(hass)["anzeige"].startswith("Manuell · 22 °C bis ")
    await call(hass, "boost", dauer=30)
    assert attrs(hass)["anzeige"].startswith("Boost bis ")
    await call(hass, "clear_overlay")
    await call(hass, "set_overlay", temperatur=19.5, dauer=0)
    assert attrs(hass)["anzeige"] == "Manuell · 19,5 °C dauerhaft"
    await call(hass, "set_hvac_mode", hvac_mode="heat")
    assert attrs(hass)["anzeige"] == "Manuell · 19,5 °C dauerhaft"
    await call(hass, "set_hvac_mode", hvac_mode="off")
    assert attrs(hass)["anzeige"] == "Aus"
    await call(hass, "set_hvac_mode", hvac_mode="auto")
    await open_window(hass, freezer)
    assert attrs(hass)["anzeige"] == "Fenster offen · Frostschutz (danach 21 °C)"


async def test_a7_display_lock_away_preheat(hass: HomeAssistant, setup_integration, freezer):
    """Sperre mit Außentemperatur, Abwesend, Vorheizen."""
    await setup_integration(options=base_options(sperre_wirkung="aus", sperre_mindesthaltezeit=0))
    hass.states.async_set("sensor.aussentemperatur", "17.4")
    await settle(hass, freezer)
    assert attrs(hass)["anzeige"] == "Sperre · außen 17,4 °C"
    hass.states.async_set("sensor.aussentemperatur", "5")
    await settle(hass, freezer)
    hass.states.async_set("input_boolean.anna_ist_zuhause", "off")
    hass.states.async_set("input_boolean.ben_ist_zuhause", "off")
    for ent in ("sensor.richtung_anna", "sensor.richtung_ben"):
        hass.states.async_set(ent, "away_from")
    for ent in ("sensor.abstand_anna", "sensor.abstand_ben"):
        hass.states.async_set(ent, "12000", {"unit_of_measurement": "m"})
    await advance(hass, freezer, 6 * 60)
    assert attrs(hass)["anzeige"] == "Abwesend · 18 °C"
    hass.states.async_set("sensor.richtung_anna", "towards")
    hass.states.async_set("sensor.abstand_anna", "8000", {"unit_of_measurement": "m"})
    await settle(hass, freezer)
    assert attrs(hass)["anzeige"] == "Vorheizen · 19,5 °C"


# --- A8: externes „aus“ ------------------------------------------------------------
async def test_a8_external_off_rejected_in_heat_with_throttled_warning(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer, caplog
):
    """heat-Modus: externes aus wird zurückgestellt, Warnung gedrosselt, Zähler."""
    caplog.set_level(logging.WARNING, logger="custom_components.pm_heizung")
    await setup_integration()
    await call(hass, "set_hvac_mode", hvac_mode="heat")
    await call(hass, "set_temperature", temperature=22)
    await advance(hass, freezer, 120)
    assert backend_state(hass) == ("heat", 22.0)
    for _ in range(2):
        backend.external_change(HVACMode.OFF)
        await settle(hass, freezer)
        await advance(hass, freezer, 60)
        assert backend_state(hass) == ("heat", 22.0)
    st = hass.states.get(CLIMATE)
    assert st.state == "heat"
    assert st.attributes["extern_aus_abgelehnt"] == 2
    warnings = [r for r in caplog.records if "extern ausgeschaltet" in r.getMessage()]
    assert len(warnings) == 1


async def test_a8_external_off_rejected_even_without_adopt(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
):
    """Auch ohne „übernehmen“ wird gezählt und zurückgestellt; Temperatur wie konfiguriert."""
    await setup_integration(data=room_data(externe_aenderung_uebernehmen=False))
    await advance(hass, freezer, 120)
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)
    assert attrs(hass)["extern_aus_abgelehnt"] == 1


async def test_a8_counter_survives_restart(hass: HomeAssistant, setup_integration, freezer):
    """Zähler ist Teil der Restore-Daten."""
    entry = await setup_integration()
    room = next(iter(entry.runtime_data.rooms.values()))
    room.persist.extern_off_rejected = 3
    data = room.persist.as_dict()
    from custom_components.pm_heizung.room import RoomPersist

    assert RoomPersist.from_dict(data).extern_off_rejected == 3
    assert RoomPersist.from_dict({"hvac_mode": "auto"}).extern_off_rejected == 0


# --- A9: via_device_id ------------------------------------------------------------
async def test_a9_room_device_linked_to_central(hass: HomeAssistant, setup_integration):
    """Raumgeräte hängen an der Zentrale (via_device_id bzw. via_device)."""
    entry = await setup_integration()
    reg = dr.async_get(hass)
    central = reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    sub_id = next(iter(entry.subentries))
    room = reg.async_get_device(identifiers={(DOMAIN, sub_id)})
    air = reg.async_get_device(identifiers={(DOMAIN, f"{sub_id}_luft")})
    assert central is not None and room is not None and air is not None
    assert central.name == "PM Klima"
    assert room.via_device_id == central.id
    assert air.via_device_id == central.id
    assert entry.runtime_data.central.device_id == central.id


def test_a9_device_info_key_matches_ha_version() -> None:
    """Je nach HA-Version wird der passende Schlüssel benutzt."""
    from custom_components.pm_heizung.entity import child_device

    class _C:
        device_id = "abc"
        entry_id = "e1"

    info = child_device(_C(), "x", "X", "Raum")  # type: ignore[arg-type]
    if HAS_VIA_DEVICE_ID:
        assert info["via_device_id"] == "abc"  # type: ignore[typeddict-item]
        assert "via_device" not in info
    else:
        assert info["via_device"] == (DOMAIN, "e1")


# --- Fehlerisolation --------------------------------------------------------------
@pytest.mark.allow_errors
async def test_air_failure_never_affects_heating(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer, monkeypatch
):
    """Wirft das Luftmodul, läuft die Heizung unverändert weiter."""
    from custom_components.pm_heizung import luft

    def boom(self, now):
        raise RuntimeError("Sensor kaputt")

    monkeypatch.setattr(luft.AirRoom, "collect", boom)
    await setup_integration()
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)
    await call(hass, "set_temperature", temperature=23)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 23.0)
    hass.states.async_set(WINDOW, "on")
    await advance(hass, freezer, 31)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 7.0)


@pytest.mark.allow_errors
async def test_air_setup_failure_never_blocks_heating(
    hass: HomeAssistant, setup_integration, freezer, monkeypatch
):
    """Schlägt schon das Einrichten von Luft/Beratung fehl, startet die Heizung trotzdem."""
    from custom_components.pm_heizung import luft

    def boom(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(luft.AirRoom, "__init__", boom)
    entry = await setup_integration()
    await settle(hass, freezer)
    assert entry.runtime_data.air == {}
    assert hass.states.get(CLIMATE) is not None
    assert hass.states.get("sensor.pm_wohnzimmer_luftqualitaet") is None
    assert backend_state(hass) == ("heat", 21.0)
