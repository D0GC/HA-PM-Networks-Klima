"""Tests zu den Review-Befunden (Version 1.0.1)."""

from __future__ import annotations

from datetime import timedelta
import logging
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.pm_heizung.const import SUBENTRY_ROOM

from .conftest import (
    BACKEND,
    FakeThermostat,
    advance,
    backend_state,
    base_options,
    room_data,
    set_schedule,
    settle,
)

CLIMATE = "climate.pm_wohnzimmer"
PHASE = "sensor.pm_heizung_abwesenheitsphase"


def _far_away(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.richtung_anna", "away_from")
    hass.states.async_set("sensor.richtung_ben", "away_from")
    for ent in ("sensor.abstand_anna", "sensor.abstand_ben"):
        hass.states.async_set(ent, "12000", {"unit_of_measurement": "m"})


# --- 1: Verlassen-Verzögerung ------------------------------------------------
async def test_leave_delay_not_reset_by_unknown_or_restart(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """unknown einer Präsenz-Entität und ein Neustart setzen die Verzögerung nicht zurück."""
    entry = await setup_integration()
    await settle(hass, freezer)
    _far_away(hass)
    hass.states.async_set("input_boolean.anna_ist_zuhause", "off")
    hass.states.async_set("input_boolean.ben_ist_zuhause", "off")
    await advance(hass, freezer, 3 * 60)
    # kurzes unknown und wieder off: kein neuer Übergang, Verzögerung läuft weiter
    hass.states.async_set("input_boolean.ben_ist_zuhause", "unknown")
    await advance(hass, freezer, 30)
    hass.states.async_set("input_boolean.ben_ist_zuhause", "off")
    await advance(hass, freezer, 2 * 60)
    assert hass.states.get(PHASE).state == "halten"  # 5 min nach dem echten Verlassen
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 18.0)

    # Neustart (Reload) während der Abwesenheit: sofort wieder halten, kein Hochheizen
    await advance(hass, freezer, 2)  # Store schreiben
    backend.calls.clear()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(PHASE).state == "halten"
    await advance(hass, freezer, 60)
    assert backend.calls == []
    assert backend_state(hass) == ("heat", 18.0)


async def test_leave_delay_holds_last_phase_and_zone_change(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Personen-Modus: Zonenwechsel (not_home -> Arbeit) löst keinen neuen Übergang aus."""
    opts = base_options()
    opts.pop("anwesenheit_entitaeten")
    await setup_integration(options=opts)
    _far_away(hass)
    hass.states.async_set("person.anna", "not_home")
    hass.states.async_set("person.ben", "not_home")
    await advance(hass, freezer, 60)
    assert hass.states.get(PHASE).state == "zuhause"  # gehalten während Verzögerung
    assert hass.states.get(PHASE).attributes["beschreibung"] == "Verlassen-Verzögerung läuft"
    hass.states.async_set("person.anna", "Arbeit")
    await advance(hass, freezer, 4 * 60 + 5)
    assert hass.states.get(PHASE).state == "halten"
    hass.states.async_set("person.anna", "unavailable")
    await advance(hass, freezer, 5)
    assert hass.states.get(PHASE).state == "halten"


# --- 2: externes OFF (v2: wird nie übernommen, siehe test_v2_heizung) -------------
async def test_external_off_without_schedule_is_reverted(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Externes „aus“ bei nicht verfügbarem Zeitplan: kein Overlay, Sollwert zurück."""
    hass.states.async_set("schedule.heizung_wohnzimmer", "unavailable")
    await setup_integration()
    await advance(hass, freezer, 120)
    assert backend_state(hass) == ("heat", 21.0)
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    st = hass.states.get(CLIMATE)
    assert st.attributes["grund"] == "zeitplan"
    assert st.attributes["overlay_bis"] is None
    assert st.attributes["extern_aus_abgelehnt"] == 1
    assert backend_state(hass) == ("heat", 21.0)


async def test_external_off_permanent_mode_not_adopted(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Auch bei Overlay-Modus „dauerhaft“ entsteht aus externem „aus“ kein Overlay."""
    await setup_integration(data=room_data(overlay_modus="dauerhaft"))
    await advance(hass, freezer, 120)
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    assert hass.states.get(CLIMATE).attributes["overlay_bis"] is None
    assert hass.states.get(CLIMATE).attributes["preset_mode"] == "zeitplan"


async def test_next_block_overlay_fallback_without_schedule(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Overlay „bis nächster Block“ ohne Zeitplan -> 60 min statt dauerhaft."""
    await setup_integration(data=room_data(zeitplan=None))
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 23}, blocking=True
    )
    until = dt_util.parse_datetime(hass.states.get(CLIMATE).attributes["overlay_bis"])
    assert until is not None
    assert abs((until - dt_util.utcnow()).total_seconds() - 3600) < 5


# --- 3: Rundung / kein Endlos-Senden -------------------------------------------
async def test_rounding_to_backend_step(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Soll wird auf target_temp_step des Backends gerundet."""
    backend._attr_target_temperature_step = 1.0
    backend.async_write_ha_state()
    set_schedule(hass, True, 21.5)
    await setup_integration()
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 22.0)


async def test_no_endless_resend_when_backend_rounds(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Backend rundet selbst (21,5 -> 21): einmal senden, nicht als manuell übernehmen."""
    backend.round_down_to_int = True
    set_schedule(hass, True, 21.5)
    await setup_integration()
    for _ in range(10):
        await settle(hass, freezer)
    assert len(backend.calls) == 1
    assert backend_state(hass) == ("heat", 21.0)
    assert hass.states.get(CLIMATE).attributes["grund"] == "zeitplan"


async def test_resend_limited_when_backend_ignores(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Backend reagiert gar nicht: höchstens 3 Versuche für denselben Sollwert."""
    backend.ignore = True
    await setup_integration()
    for _ in range(10):
        await settle(hass, freezer)

    def temps() -> int:
        return sum(1 for c in backend.calls if c[0] == "set_temperature")

    assert temps() == 3
    # neuer Sollwert -> wieder senden
    set_schedule(hass, True, 22.0)
    await settle(hass, freezer)
    assert temps() == 4


# --- 4: Thermostat nur in einem Raum ------------------------------------------
async def test_thermostat_only_in_one_room(hass: HomeAssistant, setup_integration) -> None:
    """Zweiter Raum mit demselben Thermostat wird abgewiesen (auch Reconfigure erlaubt eigenes)."""
    entry = await setup_integration()
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Küche", "klimageraete": [BACKEND], "zeitplan_attribut": "temperatur"},
    )
    assert result["errors"] == {"klimageraete": "thermostat_vergeben"}
    assert result["description_placeholders"]["raum"] == "Wohnzimmer"

    sub_id = next(iter(entry.subentries))
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": sub_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Wohnzimmer", "klimageraete": [BACKEND], "zeitplan_attribut": "temperatur"},
    )
    assert result["step_id"] == "temperaturen"


# --- 5: Mindesthaltezeit der Sperre ---------------------------------------------
async def test_lock_min_hold_time(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Grenze exakt 17 °C, aber Sperrwechsel frühestens nach 15 min; Freigabe sofort."""
    hass.states.async_set("input_boolean.heizperiode", "on")
    await setup_integration(options=base_options(freigabe_entitaet="input_boolean.heizperiode"))
    await advance(hass, freezer, 20 * 60)
    hass.states.async_set("sensor.aussentemperatur", "17.0")
    await advance(hass, freezer, 1)
    ph = hass.states.get(PHASE)
    assert ph.attributes["gesperrt"] is True  # frei seit > 15 min -> sofort
    hass.states.async_set("sensor.aussentemperatur", "16.9")
    await advance(hass, freezer, 60)
    ph = hass.states.get(PHASE)
    assert ph.attributes["gesperrt"] is True  # Haltezeit läuft
    assert ph.attributes["sperre_wechsel_wartet"] == "frei"
    await advance(hass, freezer, 14 * 60 + 5)
    assert hass.states.get(PHASE).attributes["gesperrt"] is False
    # Freigabe-Schalter wirkt sofort, unabhängig von der Haltezeit
    hass.states.async_set("input_boolean.heizperiode", "off")
    await advance(hass, freezer, 1)
    assert hass.states.get(PHASE).attributes["sperre_grund"] == "freigabe_aus"


# --- 6: Hintergrund-Task am Entry ------------------------------------------------
async def test_send_uses_entry_background_task(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Senden läuft als Background-Task des Config-Entrys."""
    original = ConfigEntry.async_create_background_task
    names: list[str] = []

    def _spy(self, hass_, target, name, eager_start=True):
        names.append(name)
        return original(self, hass_, target, name, eager_start)

    with patch.object(ConfigEntry, "async_create_background_task", _spy):
        await setup_integration()
        await settle(hass, freezer)
    assert f"pm_heizung send {BACKEND}" in names
    assert backend_state(hass) == ("heat", 21.0)


# --- 7: erst senden, wenn HA läuft -----------------------------------------------
async def test_no_send_before_running(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Während des Starts wird nur berechnet, gesendet erst nach EVENT_HOMEASSISTANT_STARTED."""
    hass.set_state(CoreState.starting)
    await setup_integration()
    await settle(hass, freezer)
    assert backend.calls == []
    assert hass.states.get(CLIMATE).attributes["temperature"] == 21.0
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)


# --- 8: Backoff bei Fehlern -----------------------------------------------------
async def test_backoff_and_throttled_warning(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer, caplog
) -> None:
    """Fehler -> 60 s, 120 s, 240 s …; Warnung nur beim ersten Fehler."""
    backend.fail = True
    caplog.set_level(logging.WARNING, logger="custom_components.pm_heizung")
    await setup_integration()
    await settle(hass, freezer)
    assert len(backend.calls) == 1
    await advance(hass, freezer, 55)
    assert len(backend.calls) == 1
    await advance(hass, freezer, 10)  # 60 s nach Fehler 1
    assert len(backend.calls) == 2
    await advance(hass, freezer, 100)
    assert len(backend.calls) == 2  # 120 s Pause
    await advance(hass, freezer, 25)
    assert len(backend.calls) == 3
    warnings = [r for r in caplog.records if "fehlgeschlagen" in r.getMessage()]
    assert len(warnings) == 1
    # Erholung
    backend.fail = False
    await advance(hass, freezer, 240 + 5)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)
    room = next(
        iter(hass.config_entries.async_entries("pm_heizung")[0].runtime_data.rooms.values())
    )
    assert room._tracks[BACKEND].fail_count == 0


async def test_backoff_capped_at_15_minutes(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Backoff wächst bis max. 15 min."""
    backend.fail = True
    entry = await setup_integration()
    await settle(hass, freezer)
    for _ in range(12):
        await advance(hass, freezer, 15 * 60 + 5)
    room = next(iter(entry.runtime_data.rooms.values()))
    track = room._tracks[BACKEND]
    assert track.retry_at is not None
    assert (track.retry_at - dt_util.utcnow()) <= timedelta(minutes=15)
    assert track.fail_count >= 6
