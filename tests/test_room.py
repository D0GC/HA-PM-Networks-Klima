"""Verhalten: Zeitplan, Overlay, Fenster, Abwesenheit, Vorheizen, Sperre, Restore, Backend."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    mock_restore_cache_with_extra_data,
)

from custom_components.pm_heizung.const import DOMAIN

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
GRUND = "sensor.pm_wohnzimmer_grund"
PHASE = "sensor.pm_heizung_abwesenheitsphase"


def attrs(hass: HomeAssistant) -> dict:
    return dict(hass.states.get(CLIMATE).attributes)


async def leave_home(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: int = 6) -> None:
    """Alle verlassen das Haus, Verzögerung (5 min) läuft ab."""
    hass.states.async_set("input_boolean.anna_ist_zuhause", "off")
    hass.states.async_set("input_boolean.ben_ist_zuhause", "off")
    hass.states.async_set("sensor.richtung_anna", "away_from")
    hass.states.async_set("sensor.richtung_ben", "away_from")
    for ent, dist in (("sensor.abstand_anna", "12000"), ("sensor.abstand_ben", "15000")):
        hass.states.async_set(ent, dist, {"unit_of_measurement": "m", "device_class": "distance"})
    await hass.async_block_till_done()
    await advance(hass, freezer, minutes * 60)
    await settle(hass, freezer)


# ---------------------------------------------------------------------------
async def test_auto_follows_schedule(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Auto-Modus: Blocktemperatur, Komfort ohne Blockdaten, Eco außerhalb."""
    set_schedule(hass, True, 22.5)
    await setup_integration()
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 22.5)
    assert hass.states.get(GRUND).state == "zeitplan"
    assert attrs(hass)["im_zeitblock"] is True

    set_schedule(hass, True, None)  # Block ohne Daten -> Komforttemperatur
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)

    set_schedule(hass, False)  # außerhalb -> Eco
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 18.0)
    assert attrs(hass)["naechster_wechsel"] is not None


async def test_debounce_and_only_send_on_difference(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Entprellung: schnelle Änderungen -> ein Sendevorgang; gleicher Wert -> kein Senden."""
    await setup_integration()
    await settle(hass, freezer)
    backend.calls.clear()
    for temp in (19.0, 19.5, 20.0):
        set_schedule(hass, True, temp)
        await hass.async_block_till_done()
        await advance(hass, freezer, 1)
    assert backend.calls == []
    await settle(hass, freezer)
    assert len(backend.calls) == 1
    assert backend_state(hass) == ("heat", 20.0)
    backend.calls.clear()
    set_schedule(hass, True, 20.0)
    await advance(hass, freezer, 30)
    assert backend.calls == []


async def test_manual_overlay_until_next_block(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Manuelle Änderung im Auto-Modus gilt bis zum nächsten Zeitplanwechsel."""
    set_schedule(hass, True, 21.0, next_in_min=30)
    await setup_integration()
    await settle(hass, freezer)

    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 23}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 23.0)
    st = hass.states.get(CLIMATE)
    assert st.state == "auto"
    assert st.attributes["grund"] == "manuell"
    overlay_until = dt_util.parse_datetime(st.attributes["overlay_bis"])
    assert overlay_until is not None
    assert abs((overlay_until - (dt_util.utcnow() + timedelta(minutes=30))).total_seconds()) < 60

    # Zeitplanwechsel: Block endet -> Overlay läuft ab -> Eco
    freezer.tick(timedelta(minutes=30))
    set_schedule(hass, False)
    await advance(hass, freezer, 1)
    await settle(hass, freezer)
    assert attrs(hass)["overlay_bis"] is None
    assert attrs(hass)["grund"] == "zeitplan"
    assert backend_state(hass) == ("heat", 18.0)


async def test_overlay_timer_and_permanent(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Overlay-Modus „für X Minuten“ und Dienst mit dauer=0 (dauerhaft)."""
    await setup_integration(data=room_data(overlay_modus="timer", overlay_minuten=45))
    await settle(hass, freezer)
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 19}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 19.0)
    await advance(hass, freezer, 45 * 60)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)

    await hass.services.async_call(
        DOMAIN, "set_overlay", {"entity_id": CLIMATE, "temperatur": 22, "dauer": 0}, blocking=True
    )
    await settle(hass, freezer)
    assert attrs(hass)["overlay_bis"] == "dauerhaft"
    await advance(hass, freezer, 24 * 3600)
    assert backend_state(hass) == ("heat", 22.0)
    await hass.services.async_call(DOMAIN, "clear_overlay", {"entity_id": CLIMATE}, blocking=True)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)


async def test_heat_and_off_modes(hass: HomeAssistant, setup_integration, freezer) -> None:
    """heat = dauerhaft manuell; off = Backend aus; Presets."""
    await setup_integration()
    await settle(hass, freezer)
    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": CLIMATE, "hvac_mode": "heat"}, blocking=True
    )
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 19.5}, blocking=True
    )
    await settle(hass, freezer)
    assert hass.states.get(CLIMATE).state == "heat"
    assert backend_state(hass) == ("heat", 19.5)
    set_schedule(hass, False)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 19.5)  # Zeitplan wirkt nicht

    await hass.services.async_call(
        "climate", "set_preset_mode", {"entity_id": CLIMATE, "preset_mode": "eco"}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 18.0)
    assert hass.states.get(CLIMATE).attributes["preset_mode"] == "eco"

    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": CLIMATE, "hvac_mode": "off"}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass)[0] == "off"
    assert hass.states.get(GRUND).state == "aus"


async def test_boost(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Boost = Maximaltemperatur für X Minuten, danach zurück."""
    await setup_integration()
    await settle(hass, freezer)
    await hass.services.async_call(
        DOMAIN, "boost", {"entity_id": CLIMATE, "dauer": 15}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 25.0)
    assert hass.states.get(CLIMATE).attributes["preset_mode"] == "boost"
    assert hass.states.get(GRUND).state == "boost"
    await advance(hass, freezer, 15 * 60)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)
    # v2: nach dem Boost läuft der Zeitplan -> Preset „zeitplan“ (v1: „none“)
    assert hass.states.get(CLIMATE).attributes["preset_mode"] == "zeitplan"


async def test_window_frost_and_back(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Fenster offen -> nach Verzögerung Frostschutz, geschlossen -> zurück."""
    await setup_integration()
    await settle(hass, freezer)
    hass.states.async_set("binary_sensor.fenster_1_wohnzimmer", "on")
    await advance(hass, freezer, 10)
    assert hass.states.get("binary_sensor.pm_wohnzimmer_fenster_offen").state == "on"
    assert backend_state(hass) == ("heat", 21.0)  # Verzögerung (30 s) läuft
    await advance(hass, freezer, 25)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 7.0)
    assert hass.states.get(GRUND).state == "fenster"

    hass.states.async_set("binary_sensor.fenster_1_wohnzimmer", "off")
    await advance(hass, freezer, 11)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)
    assert hass.states.get(GRUND).state == "zeitplan"


async def test_window_off_action_and_heat_mode(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Fensteraktion „aus“ wirkt auch im heat-Modus."""
    await setup_integration(data=room_data(fenster_aktion="aus", fenster_verzoegerung_offen=0))
    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": CLIMATE, "hvac_mode": "heat"}, blocking=True
    )
    await settle(hass, freezer)
    hass.states.async_set("binary_sensor.fenster_1_wohnzimmer", "on")
    await settle(hass, freezer)
    assert backend_state(hass)[0] == "off"


async def test_away_setback_after_delay(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Niemand zuhause -> erst nach Verlassen-Verzögerung absenken (Komfort − 3 = 18)."""
    await setup_integration()
    await settle(hass, freezer)
    hass.states.async_set("input_boolean.anna_ist_zuhause", "off")
    hass.states.async_set("input_boolean.ben_ist_zuhause", "off")
    hass.states.async_set("sensor.richtung_anna", "away_from")
    hass.states.async_set("sensor.richtung_ben", "away_from")
    hass.states.async_set("sensor.abstand_anna", "12000", {"unit_of_measurement": "m"})
    await advance(hass, freezer, 60)
    assert hass.states.get(PHASE).state == "zuhause"  # Verzögerung läuft
    assert backend_state(hass) == ("heat", 21.0)

    await advance(hass, freezer, 4 * 60 + 10)
    await settle(hass, freezer)
    assert hass.states.get(PHASE).state == "halten"
    assert backend_state(hass) == ("heat", 18.0)
    assert hass.states.get(GRUND).state == "abwesenheit"

    # weiter weg als Fernradius (25 km Balance) -> fern: 21 − 3 − 2 = 16
    hass.states.async_set("sensor.abstand_anna", "30", {"unit_of_measurement": "km"})
    hass.states.async_set("sensor.abstand_ben", "40000", {"unit_of_measurement": "m"})
    await settle(hass, freezer)
    assert hass.states.get(PHASE).state == "fern"
    assert backend_state(hass) == ("heat", 16.0)


async def test_away_never_above_schedule(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Abwesenheit hebt nie über die Zeitplantemperatur (Eco 17 < Halten 18)."""
    set_schedule(hass, False)
    await setup_integration(data=room_data(ecotemperatur=17.0))
    await leave_home(hass, freezer)
    assert hass.states.get(PHASE).state == "halten"
    assert backend_state(hass) == ("heat", 17.0)


async def test_preheat_towards_within_radius(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Annäherung: Mittelradius -> Zwischenstufe, Nahradius -> Komfort; Stau hält die Stufe."""
    await setup_integration()
    await leave_home(hass, freezer)
    assert backend_state(hass) == ("heat", 18.0)

    # innerhalb Mittelradius (10 km), aber nicht towards -> bleibt halten
    hass.states.async_set("sensor.abstand_anna", "8000", {"unit_of_measurement": "m"})
    hass.states.async_set("sensor.richtung_anna", "stationary")
    await settle(hass, freezer)
    assert hass.states.get(PHASE).state == "halten"

    hass.states.async_set("sensor.richtung_ben", "stationary")
    hass.states.async_set("sensor.richtung_anna", "towards")
    await settle(hass, freezer)
    assert hass.states.get(PHASE).state == "zwischen"
    assert backend_state(hass) == ("heat", 19.5)  # ceil((18+21)/2)
    assert hass.states.get(GRUND).state == "vorheizen"

    hass.states.async_set("sensor.abstand_anna", "3000", {"unit_of_measurement": "m"})
    await settle(hass, freezer)
    assert hass.states.get(PHASE).state == "komfort"
    assert backend_state(hass) == ("heat", 21.0)

    # Stau: stationary -> Stufe bleibt (Hysterese)
    hass.states.async_set("sensor.richtung_anna", "stationary")
    await settle(hass, freezer)
    assert hass.states.get(PHASE).state == "komfort"
    # away_from -> zurück auf halten
    hass.states.async_set("sensor.richtung_anna", "away_from")
    hass.states.async_set("sensor.abstand_anna", "12000", {"unit_of_measurement": "m"})
    await settle(hass, freezer)
    assert hass.states.get(PHASE).state == "halten"


async def test_lock_releases_instead_of_freezing(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Außentemperatur ≥ Grenze: abgesenkte Räume gehen an den Zeitplan zurück."""
    await setup_integration(options=base_options(sperre_mindesthaltezeit=0))
    await leave_home(hass, freezer)
    assert backend_state(hass) == ("heat", 18.0)

    hass.states.async_set("sensor.aussentemperatur", "17.0")  # genau Grenze -> sperrt
    await settle(hass, freezer)
    ph = hass.states.get(PHASE)
    assert ph.attributes["gesperrt"] is True
    assert ph.attributes["sperre_grund"] == "aussentemperatur"
    assert backend_state(hass) == ("heat", 21.0)  # nicht eingefroren
    assert hass.states.get(GRUND).state == "zeitplan"

    # Zeitplan läuft weiter
    set_schedule(hass, False)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 18.0)
    set_schedule(hass, True, 21.0)

    # unbekannter Wert sperrt nicht, 16.9 sperrt nicht (keine Hysterese)
    hass.states.async_set("sensor.aussentemperatur", "unknown")
    await settle(hass, freezer)
    assert hass.states.get(PHASE).attributes["gesperrt"] is False
    assert backend_state(hass) == ("heat", 18.0)
    hass.states.async_set("sensor.aussentemperatur", "16.9")
    await settle(hass, freezer)
    assert hass.states.get(PHASE).attributes["gesperrt"] is False


async def test_arrival_under_lock(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Rückkehr bei Ankunft läuft immer, auch bei Sperre (Freigabe aus)."""
    hass.states.async_set("input_boolean.heizperiode", "on")
    await setup_integration(options=base_options(freigabe_entitaet="input_boolean.heizperiode"))
    await leave_home(hass, freezer)
    assert backend_state(hass) == ("heat", 18.0)

    hass.states.async_set("input_boolean.heizperiode", "off")
    hass.states.async_set("input_boolean.anna_ist_zuhause", "on")
    await settle(hass, freezer)
    ph = hass.states.get(PHASE)
    assert ph.state == "zuhause"
    assert ph.attributes["sperre_grund"] == "freigabe_aus"
    assert backend_state(hass) == ("heat", 21.0)
    assert hass.states.get(GRUND).state == "zeitplan"


async def test_lock_effect_off_summer(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Sperre-Wirkung „aus“: Auto-Räume werden abgeschaltet (Sommer), auch zuhause."""
    await setup_integration(options=base_options(sperre_wirkung="aus", sperre_mindesthaltezeit=0))
    await settle(hass, freezer)
    hass.states.async_set("sensor.aussentemperatur", "20.5")
    await settle(hass, freezer)
    assert backend_state(hass)[0] == "off"
    assert hass.states.get(GRUND).state == "sperre"
    hass.states.async_set("sensor.aussentemperatur", "10")
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)


async def test_main_switch_pauses(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Hauptschalter aus -> nichts senden; wieder an -> nachziehen."""
    await setup_integration()
    await settle(hass, freezer)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.pm_heizung_aktiv"}, blocking=True
    )
    backend.calls.clear()
    set_schedule(hass, False)
    await advance(hass, freezer, 30)
    assert backend.calls == []
    assert hass.states.get(GRUND).state == "pausiert"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.pm_heizung_aktiv"}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 18.0)


async def test_backend_unavailable_catch_up(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Backend nicht erreichbar -> merken, beim Wiederkommen nachziehen."""
    await setup_integration()
    await settle(hass, freezer)
    backend.set_available(False)
    await hass.async_block_till_done()
    backend.calls.clear()
    set_schedule(hass, True, 23.0)
    await advance(hass, freezer, 30)
    assert backend.calls == []
    assert hass.states.get(BACKEND).state == "unavailable"

    backend.set_available(True)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 23.0)
    # wiederkommender Wert wurde nicht als manuelle Änderung übernommen
    assert attrs(hass)["grund"] == "zeitplan"


async def test_min_send_interval(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Mindestabstand zwischen zwei Sendungen an dasselbe Backend."""
    await setup_integration()
    await settle(hass, freezer)
    backend.calls.clear()
    set_schedule(hass, True, 22.0)
    await settle(hass, freezer)
    set_schedule(hass, True, 23.0)
    await advance(hass, freezer, 5.5)
    assert len(backend.calls) == 1  # 10 s Mindestabstand
    await advance(hass, freezer, 5)
    assert len(backend.calls) == 2
    assert backend_state(hass) == ("heat", 23.0)


async def test_external_change_adopted_as_overlay(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Am Thermostat gedreht -> manuelles Overlay; ohne Option -> zurückgesetzt."""
    await setup_integration()
    await advance(hass, freezer, 120)
    backend.external_change(HVACMode.HEAT, 24.0)
    await settle(hass, freezer)
    st = hass.states.get(CLIMATE)
    assert st.attributes["grund"] == "manuell"
    assert st.attributes["temperature"] == 24.0
    assert backend_state(hass) == ("heat", 24.0)


async def test_external_change_reverted_when_disabled(
    hass: HomeAssistant, setup_integration, backend: FakeThermostat, freezer
) -> None:
    """Option aus: Änderung am Thermostat wird überschrieben."""
    await setup_integration(data=room_data(externe_aenderung_uebernehmen=False))
    await advance(hass, freezer, 120)
    backend.external_change(HVACMode.HEAT, 24.0)
    await settle(hass, freezer)
    assert attrs(hass)["grund"] == "zeitplan"
    assert backend_state(hass) == ("heat", 21.0)


async def test_restore_after_restart(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Modus, manueller Wert und Overlay überleben einen Neustart."""
    until = dt_util.utcnow() + timedelta(minutes=20)
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(CLIMATE, "auto"),
                {
                    "hvac_mode": "auto",
                    "manual_temp": 19.0,
                    "preset": None,
                    "overlay_active": True,
                    "overlay_temp": 22.5,
                    "overlay_until": until.isoformat(),
                    "boost_until": None,
                },
            )
        ],
    )
    await setup_integration()
    await settle(hass, freezer)
    st = hass.states.get(CLIMATE)
    assert st.state == "auto"
    assert st.attributes["grund"] == "manuell"
    assert backend_state(hass) == ("heat", 22.5)
    # Ablauf ist zeitbasiert und überlebt den Neustart
    await advance(hass, freezer, 20 * 60 + 1)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)


async def test_restore_heat_mode_and_expired_overlay(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """heat-Modus wird wiederhergestellt; abgelaufenes Overlay verworfen."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(CLIMATE, "heat"),
                {
                    "hvac_mode": "heat",
                    "manual_temp": 19.5,
                    "overlay_active": True,
                    "overlay_temp": 24,
                    "overlay_until": (dt_util.utcnow() - timedelta(minutes=1)).isoformat(),
                },
            )
        ],
    )
    await setup_integration()
    await settle(hass, freezer)
    assert hass.states.get(CLIMATE).state == "heat"
    assert backend_state(hass) == ("heat", 19.5)
    assert attrs(hass)["overlay_bis"] is None


async def test_restore_roundtrip_via_extra_data(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """extra_restore_state_data liefert die aktuellen Raumdaten."""
    entry = await setup_integration()
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": CLIMATE, "temperature": 23}, blocking=True
    )
    room = next(iter(entry.runtime_data.rooms.values()))
    data = room.persist.as_dict()
    assert data["overlay_active"] is True
    assert data["overlay_temp"] == 23
    assert data["overlay_until"] is not None


async def test_reevaluate_service_and_diagnostics(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """reevaluate und Diagnose."""
    from custom_components.pm_heizung.diagnostics import async_get_config_entry_diagnostics

    entry = await setup_integration()
    await hass.services.async_call(DOMAIN, "reevaluate", {}, blocking=True)
    await settle(hass, freezer)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["central"]["state"]["phase"] == "zuhause"
    room = next(iter(diag["rooms"].values()))
    assert room["backends"][BACKEND]["last_sent"] == ("heat", 21.0)


async def test_unload(hass: HomeAssistant, setup_integration) -> None:
    """Entladen löst alle Listener."""
    entry = await setup_integration()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
