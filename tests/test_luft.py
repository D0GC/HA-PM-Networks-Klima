"""Modul Luft – Entitäten und Luftreiniger-Automatik."""

from __future__ import annotations

from typing import Any

from homeassistant.core import Context, HomeAssistant, ServiceCall

from .conftest import advance, base_options, room_data, settle

FAN = "fan.luftreiniger"
PM = "sensor.pm25_wz"
SWITCH = "switch.pm_wohnzimmer_luftreiniger_automatik"
WINDOW = "binary_sensor.fenster_1_wohnzimmer"


def air_options(**kw: Any) -> dict[str, Any]:
    return base_options(
        luft_aussenfeuchte="sensor.aussenluftfeuchte", wetter_entitaet="weather.dwd", **kw
    )


def air_room(**kw: Any) -> dict[str, Any]:
    return room_data(
        temperatursensor="sensor.wz_temp",
        feuchtesensor="sensor.wz_feuchte",
        co2_sensor="sensor.co2_wz",
        pm25_sensor=PM,
        luftreiniger=FAN,
        luftreiniger_filter=["sensor.filter_prozent", "sensor.filter_stunden"],
        **kw,
    )


def set_air(  # noqa: PLR0917
    hass: HomeAssistant,
    t_in: float = 21.0,
    rh_in: float = 50.0,
    co2: float = 600,
    pm: float = 4,
    t_out: float = 5.0,
    rh_out: float = 80.0,
    weather: str = "cloudy",
) -> None:
    hass.states.async_set("sensor.wz_temp", str(t_in))
    hass.states.async_set("sensor.wz_feuchte", str(rh_in))
    hass.states.async_set("sensor.co2_wz", str(co2))
    hass.states.async_set(PM, str(pm))
    hass.states.async_set("sensor.aussentemperatur", str(t_out), {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.aussenluftfeuchte", str(rh_out))
    hass.states.async_set("weather.dwd", weather)
    hass.states.async_set("sensor.filter_prozent", "85", {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.filter_stunden", "4000", {"unit_of_measurement": "h"})


def set_fan(hass: HomeAssistant, state: str, preset: str | None, context: Context | None = None):
    hass.states.async_set(
        FAN,
        state,
        {"preset_modes": ["Auto", "Sleep", "Medium", "Fast", "Turbo"], "preset_mode": preset},
        context=context,
    )


def fan_mocks(hass: HomeAssistant) -> list[ServiceCall]:
    """fan-Dienste simulieren, Aufrufe in zeitlicher Reihenfolge aufzeichnen."""
    calls: list[ServiceCall] = []

    async def _record(call: ServiceCall) -> None:
        calls.append(call)

    for svc in ("turn_on", "turn_off", "set_preset_mode"):
        hass.services.async_register("fan", svc, _record)
    return calls


def all_calls(mocks: list[ServiceCall]) -> list[tuple[str, dict]]:
    return [(c.service, dict(c.data)) for c in mocks]


def last_ctx(mocks: list[ServiceCall]) -> Context:
    return mocks[-1].context


async def test_air_entities(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Luftqualität, Schimmelrisiko, Lüften empfohlen und Lüftdauer je Raum."""
    freezer.move_to("2026-01-15 10:00:00+01:00")
    set_air(hass, t_in=21.0, rh_in=50.0, t_out=5.0)
    set_fan(hass, "on", "Auto")
    await setup_integration(options=air_options(), data=air_room())
    await settle(hass, freezer)
    q = hass.states.get("sensor.pm_wohnzimmer_luftqualitaet")
    assert q.state == "gut"
    assert q.attributes["abs_feuchte_innen"] == 9.14
    assert q.attributes["friendly_name"].startswith("Wohnzimmer Luft ")
    mold = hass.states.get("sensor.pm_wohnzimmer_schimmelrisiko")
    assert float(mold.state) == 64.2  # fRsi 0,75
    assert mold.attributes["stufe"] == "gering"
    assert mold.attributes["wandtemperatur"] == 17.0
    assert hass.states.get("binary_sensor.pm_wohnzimmer_lueften_empfohlen").state == "off"
    assert hass.states.get("sensor.pm_wohnzimmer_lueftdauer").state == "10"

    # feucht -> Lüften empfohlen, Qualität schlecht (Wand > 80 %)
    set_air(hass, t_in=21.0, rh_in=68.0, t_out=-2.0, rh_out=80.0)
    await hass.async_block_till_done()
    vent = hass.states.get("binary_sensor.pm_wohnzimmer_lueften_empfohlen")
    assert vent.state == "on"
    assert "Luftfeuchte 68 %" in vent.attributes["gruende"]
    assert hass.states.get("sensor.pm_wohnzimmer_lueftdauer").state == "5"
    assert hass.states.get("sensor.pm_wohnzimmer_luftqualitaet").state == "schlecht"
    assert hass.states.get("sensor.pm_wohnzimmer_schimmelrisiko").attributes["stufe"] == "risiko"

    # Regen: Feuchte-Lüften nicht sinnvoll
    set_air(hass, t_in=21.0, rh_in=68.0, t_out=-2.0, weather="rainy")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.pm_wohnzimmer_lueften_empfohlen").state == "off"

    # CO2 hoch: auch bei Regen empfohlen; Fenster offen -> nicht mehr
    set_air(hass, co2=1500, weather="rainy")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.pm_wohnzimmer_lueften_empfohlen").state == "on"
    hass.states.async_set(WINDOW, "on")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.pm_wohnzimmer_lueften_empfohlen").state == "off"


async def test_air_without_sensors_is_unknown(hass: HomeAssistant, setup_integration, freezer):
    """Ohne Außenwerte bleibt das Schimmelrisiko unbekannt; Feuchte kommt vom Thermostat."""
    opts = base_options()
    opts.pop("aussentemperatur_sensor")
    await setup_integration(options=opts)
    await settle(hass, freezer)
    assert hass.states.get("sensor.pm_wohnzimmer_schimmelrisiko").state == "unknown"
    q = hass.states.get("sensor.pm_wohnzimmer_luftqualitaet")
    assert q.state == "gut"  # 55 % vom Thermostat
    assert q.attributes["feuchte_innen"] == 55.0
    assert hass.states.get(SWITCH) is None  # kein Luftreiniger konfiguriert


async def test_purifier_automation(hass: HomeAssistant, setup_integration, freezer) -> None:
    """Standard aus; Regeln, Hysterese, Mindesthaltezeit, eigenes Echo, Fenster."""
    freezer.move_to("2026-01-15 10:00:00+01:00")
    mocks = fan_mocks(hass)
    set_air(hass, pm=4)
    set_fan(hass, "on", "Sleep")
    await setup_integration(options=air_options(), data=air_room())
    await settle(hass, freezer)
    assert hass.states.get(SWITCH).state == "off"
    assert all_calls(mocks) == []  # Automatik standardmäßig aus

    await hass.services.async_call("switch", "turn_on", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()
    calls = all_calls(mocks)
    assert calls == [("set_preset_mode", {"entity_id": FAN, "preset_mode": "Auto"})]
    # Echo des eigenen Befehls (gleicher Kontext) pausiert nicht
    set_fan(hass, "on", "Auto", context=last_ctx(mocks))
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).attributes["pausiert_bis"] is None

    # Feinstaub hoch -> Turbo, aber erst nach Mindesthaltezeit (10 min)
    hass.states.async_set(PM, "40")
    await advance(hass, freezer, 60)
    assert len(all_calls(mocks)) == 1
    await advance(hass, freezer, 9 * 60 + 5)
    assert all_calls(mocks)[-1] == ("set_preset_mode", {"entity_id": FAN, "preset_mode": "Turbo"})
    set_fan(hass, "on", "Turbo", context=last_ctx(mocks))

    # Hysterese: 32 bleibt Turbo, 28 -> Auto (nach Haltezeit)
    hass.states.async_set(PM, "32")
    await advance(hass, freezer, 11 * 60)
    assert len(all_calls(mocks)) == 2
    hass.states.async_set(PM, "28")
    await advance(hass, freezer, 11 * 60)
    assert all_calls(mocks)[-1][1]["preset_mode"] == "Auto"
    set_fan(hass, "on", "Auto", context=last_ctx(mocks))

    # Fenster offen -> sofort aus (nur 30 s Mindestabstand)
    count = len(all_calls(mocks))
    hass.states.async_set(WINDOW, "on")
    await advance(hass, freezer, 31)
    assert all_calls(mocks)[count:] == [("turn_off", {"entity_id": FAN})]
    set_fan(hass, "off", None, context=last_ctx(mocks))
    hass.states.async_set(WINDOW, "off")
    await advance(hass, freezer, 11 * 60)
    assert all_calls(mocks)[-1] == ("turn_on", {"entity_id": FAN, "preset_mode": "Auto"})


async def test_purifier_manual_pause_and_night(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Manuelle Bedienung pausiert 60 min; nachts Sleep; Abwesenheit Auto."""
    freezer.move_to("2026-01-15 21:00:00+01:00")
    mocks = fan_mocks(hass)
    set_air(hass, pm=4)
    set_fan(hass, "on", "Auto")
    await setup_integration(options=air_options(), data=air_room(luftreiniger_pause=60))
    await hass.services.async_call("switch", "turn_on", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()
    assert all_calls(mocks) == []  # schon Auto

    # jemand stellt am Gerät auf Medium (fremder Kontext)
    set_fan(hass, "on", "Medium")
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).attributes["pausiert_bis"] is not None
    # 22:00 -> Nacht, aber Pause läuft (bis 22:00 + x): nichts senden
    await advance(hass, freezer, 59 * 60)
    assert all_calls(mocks) == []
    await advance(hass, freezer, 2 * 60)
    assert all_calls(mocks) == [("set_preset_mode", {"entity_id": FAN, "preset_mode": "Sleep"})]
    assert hass.states.get(SWITCH).attributes["begruendung"] == "Nacht"
    set_fan(hass, "on", "Sleep", context=last_ctx(mocks))

    # nachts Feinstaub hoch -> Fast statt Turbo
    hass.states.async_set(PM, "50")
    await advance(hass, freezer, 11 * 60)
    assert all_calls(mocks)[-1][1]["preset_mode"] == "Fast"

    # Automatik aus -> keine Befehle mehr
    await hass.services.async_call("switch", "turn_off", {"entity_id": SWITCH}, blocking=True)
    count = len(all_calls(mocks))
    hass.states.async_set(PM, "3")
    await advance(hass, freezer, 20 * 60)
    assert len(all_calls(mocks)) == count


async def test_purifier_switch_restored(hass: HomeAssistant, setup_integration, freezer):
    """Automatik-Schalter ist neustartsicher (RestoreEntity)."""
    from homeassistant.core import State
    from pytest_homeassistant_custom_component.common import mock_restore_cache

    mock_restore_cache(hass, [State(SWITCH, "on")])
    freezer.move_to("2026-01-15 10:00:00+01:00")
    mocks = fan_mocks(hass)
    set_air(hass, pm=4)
    set_fan(hass, "on", "Sleep")
    await setup_integration(options=air_options(), data=air_room())
    await settle(hass, freezer)
    assert hass.states.get(SWITCH).state == "on"
    assert all_calls(mocks)[-1][1]["preset_mode"] == "Auto"
