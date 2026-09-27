"""v2.1.0: beliebige Thermostate, Sprache, neutrale Vorgaben, Umstiegsdienste, Luftreiniger."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pm_heizung import backend as backend_mod
from custom_components.pm_heizung.backend import backend_kind, capabilities
from custom_components.pm_heizung.const import (
    BACKEND_GENERIC,
    BACKEND_TADO_CLOUD,
    BACKEND_TADO_LOCAL,
    DOMAIN,
    SUBENTRY_ROOM,
)
from custom_components.pm_heizung.logic import fmt_temp, fmt_time

from .conftest import (
    BACKEND,
    FakeThermostat,
    advance,
    backend_state,
    base_options,
    room_data,
    set_home_states,
    set_schedule,
    settle,
)

CLIMATE = "climate.pm_wohnzimmer"


async def setup_v4(
    hass: HomeAssistant,
    options: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Eintrag im aktuellen Schema (ohne Migration, also mit den neuen Standards)."""
    set_home_states(hass)
    set_schedule(hass, True, 21.0)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PM Klima",
        unique_id=DOMAIN,
        version=1,
        minor_version=4,
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


def attrs(hass: HomeAssistant) -> dict[str, Any]:
    st = hass.states.get(CLIMATE)
    assert st is not None
    return dict(st.attributes)


def sends(backend: FakeThermostat) -> list[tuple[str, Any]]:
    return list(backend.calls)


# --- Fähigkeiten und Gerätetyp ------------------------------------------------------
def test_capabilities_from_hvac_modes() -> None:
    """Heizmodus: heat, sonst heat_cool, sonst auto; „off“ nur wenn angeboten."""
    assert capabilities(State("climate.a", "heat", {"hvac_modes": ["off", "auto", "heat"]})) == (
        backend_mod.Capabilities("heat", True)
    )
    caps = capabilities(State("climate.b", "heat_cool", {"hvac_modes": ["off", "heat_cool"]}))
    assert (caps.heat_mode, caps.can_off) == ("heat_cool", True)
    caps = capabilities(State("climate.c", "auto", {"hvac_modes": ["auto"]}))
    assert (caps.heat_mode, caps.can_off) == ("auto", False)
    caps = capabilities(State("climate.d", "heat", {"hvac_modes": ["heat"]}))
    assert (caps.heat_mode, caps.can_off) == ("heat", False)
    # ohne Angabe wie bisher heat/off
    assert capabilities(State("climate.e", "heat", {})) == backend_mod.Capabilities("heat", True)
    assert capabilities(None) == backend_mod.Capabilities("heat", True)


async def test_backend_kind(hass: HomeAssistant) -> None:
    """tado-Cloud über die Plattform, tado lokal über Hersteller + HomeKit/Matter."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    cloud = ent_reg.async_get_or_create("climate", "tado", "zone5", suggested_object_id="wz")
    hk_entry = MockConfigEntry(domain="homekit_controller")
    hk_entry.add_to_hass(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=hk_entry.entry_id,
        identifiers={("homekit_controller", "tado-va02")},
        manufacturer="tado GmbH",
    )
    local = ent_reg.async_get_or_create(
        "climate",
        "homekit_controller",
        "hk1",
        suggested_object_id="wz_homekit",
        device_id=device.id,
        config_entry=hk_entry,
    )
    other = ent_reg.async_get_or_create("climate", "zha", "trv1", suggested_object_id="trv")
    assert backend_kind(hass, cloud.entity_id) == BACKEND_TADO_CLOUD
    assert backend_kind(hass, local.entity_id) == BACKEND_TADO_LOCAL
    assert backend_kind(hass, other.entity_id) == BACKEND_GENERIC
    assert backend_kind(hass, "climate.unbekannt") == BACKEND_GENERIC


async def test_device_without_off_gets_lowest_setpoint(
    hass: HomeAssistant, backend: FakeThermostat, freezer
) -> None:
    """Gerät ohne „off“: statt Ausschalten die niedrigste Solltemperatur im Heizmodus."""
    backend._attr_hvac_modes = [HVACMode.HEAT]
    backend._attr_min_temp = 4.5
    backend.async_write_ha_state()
    await setup_v4(hass)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)
    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": CLIMATE, "hvac_mode": "off"}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 4.5)
    assert not [c for c in backend.calls if c[0] == "set_hvac_mode"]
    assert attrs(hass)["ziel_backend"] == "aus"
    # stabil: kein erneutes Senden
    count = len(backend.calls)
    await advance(hass, freezer, 120)
    assert len(backend.calls) == count


async def test_heat_cool_device(hass: HomeAssistant, backend: FakeThermostat, freezer) -> None:
    """Gerät ohne „heat“: Sollwert im Modus heat_cool, wird als „heizt“ erkannt."""
    backend._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    backend._attr_hvac_mode = HVACMode.OFF
    backend.async_write_ha_state()
    await setup_v4(hass)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat_cool", 21.0)
    name, call = backend.calls[-1]
    assert (name, call["temperature"], call["hvac_mode"]) == ("set_temperature", 21.0, "heat_cool")
    count = len(backend.calls)
    await advance(hass, freezer, 120)
    assert len(backend.calls) == count  # kein Endlos-Nachsenden
    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": CLIMATE, "hvac_mode": "off"}, blocking=True
    )
    await settle(hass, freezer)
    assert backend_state(hass)[0] == "off"


async def test_device_ignoring_hvac_mode_kwarg(
    hass: HomeAssistant, backend: FakeThermostat, freezer, monkeypatch
) -> None:
    """Gerät wertet hvac_mode in set_temperature nicht aus (wie generic_thermostat):
    PM Klima schickt die Betriebsart nach."""
    original = FakeThermostat.async_set_temperature

    async def ignore_mode(self: FakeThermostat, **kwargs: Any) -> None:
        kwargs.pop("hvac_mode", None)
        await original(self, **kwargs)

    monkeypatch.setattr(FakeThermostat, "async_set_temperature", ignore_mode)
    backend._attr_hvac_mode = HVACMode.OFF
    backend.async_write_ha_state()
    await setup_v4(hass)
    await settle(hass, freezer)
    assert backend_state(hass) == ("heat", 21.0)
    assert [c[0] for c in backend.calls[:2]] == ["set_temperature", "set_hvac_mode"]
    count = len(backend.calls)
    await advance(hass, freezer, 120)
    assert len(backend.calls) == count


async def test_tado_single_call(
    hass: HomeAssistant, backend: FakeThermostat, freezer, monkeypatch
) -> None:
    """tado: nie ein nachgeschobenes set_hvac_mode (Cloud meldet verzögert, Kontingent)."""
    monkeypatch.setattr(
        "custom_components.pm_heizung.room.backend_kind", lambda _h, _e: BACKEND_TADO_CLOUD
    )
    original = FakeThermostat.async_set_temperature

    async def delayed_mode(self: FakeThermostat, **kwargs: Any) -> None:
        kwargs.pop("hvac_mode", None)  # Rückmeldung des Modus kommt erst später
        await original(self, **kwargs)

    monkeypatch.setattr(FakeThermostat, "async_set_temperature", delayed_mode)
    backend._attr_hvac_mode = HVACMode.OFF
    backend.async_write_ha_state()
    await setup_v4(hass)
    await settle(hass, freezer)
    assert backend.calls[0][0] == "set_temperature"
    assert "set_hvac_mode" not in [c[0] for c in backend.calls]


# --- externes „aus“: Standard nach Gerätetyp ----------------------------------------
async def test_ext_off_default_generic_is_rejected(
    hass: HomeAssistant, backend: FakeThermostat, freezer
) -> None:
    """Generisches Thermostat ohne Fenstersensor: „aus“ am Gerät gilt nicht als Fenster."""
    await setup_v4(hass, data=room_data(fenstersensoren=None))
    await advance(hass, freezer, 120)
    assert attrs(hass)["thermostat_typ"] == BACKEND_GENERIC
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    assert attrs(hass)["grund"] != "fenster_extern"
    assert attrs(hass)["extern_aus_abgelehnt"] == 1
    assert backend_state(hass) == ("heat", 21.0)


async def test_ext_off_default_tado_is_window(
    hass: HomeAssistant, backend: FakeThermostat, freezer, monkeypatch
) -> None:
    """tado ohne Fenstersensor: „aus“ (Fenstererkennung) = 30 min Frostschutz."""
    monkeypatch.setattr(
        "custom_components.pm_heizung.room.backend_kind", lambda _h, _e: BACKEND_TADO_CLOUD
    )
    await setup_v4(hass, data=room_data(fenstersensoren=None))
    await advance(hass, freezer, 120)
    assert attrs(hass)["thermostat_typ"] == BACKEND_TADO_CLOUD
    backend.external_change(HVACMode.OFF)
    await settle(hass, freezer)
    assert attrs(hass)["grund"] == "fenster_extern"
    assert attrs(hass)["anzeige"].startswith("Fenster (Thermostat) · Frostschutz bis ")


# --- Sprache -------------------------------------------------------------------------
def test_format_by_language(hass: HomeAssistant) -> None:
    """Dezimaltrennzeichen und Wochentage je Sprache."""
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    assert fmt_temp(19.5) == "19,5 °C"
    assert fmt_temp(19.5, "en") == "19.5 °C"
    now = dt_util.utcnow()
    assert fmt_time(now + timedelta(days=2), now, "en")[:3] in {
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    }


async def test_language_english(hass: HomeAssistant, backend: FakeThermostat, freezer) -> None:
    """Option „en“: Anzeige, Empfehlung und Zentrale auf Englisch."""
    await setup_v4(hass, options=base_options(sprache="en"))
    await settle(hass, freezer)
    assert attrs(hass)["anzeige"].startswith("Schedule · 21 °C until ")
    # Wand 70 % (Innenfeuchte des Thermostats, 5 °C außen): nur Anzeige, auf Englisch
    assert hass.states.get("sensor.pm_klima_empfehlung").state == (
        "Wohnzimmer: wall humidity elevated (70 %)"
    )
    phase = hass.states.get("sensor.pm_heizung_abwesenheitsphase")
    assert phase.attributes.get("beschreibung") == "Someone at home"


async def test_language_auto_follows_home_assistant(
    hass: HomeAssistant, backend: FakeThermostat, freezer
) -> None:
    """Option „auto“: Deutsch bei de, sonst Englisch."""
    hass.config.language = "en"
    await setup_v4(hass, options=base_options(sprache="auto"))
    await settle(hass, freezer)
    assert attrs(hass)["anzeige"].startswith("Schedule · ")


# --- Beratung ohne installationsspezifische Vorgaben -----------------------------------
async def test_advice_channels_need_targets(
    hass: HomeAssistant, backend: FakeThermostat, freezer
) -> None:
    """Ohne Skript/Dienst keine Alexa- bzw. Panel-Ziele, auch nicht im Test."""
    await setup_v4(hass)
    await settle(hass, freezer)
    result = await hass.services.async_call(
        DOMAIN, "beratung_testen", {"kanal": "alexa"}, blocking=True, return_response=True
    )
    assert result["ziele"] == []
    result = await hass.services.async_call(
        DOMAIN, "beratung_testen", {"kanal": "panel"}, blocking=True, return_response=True
    )
    assert result["ziele"] == []
    advisor = hass.config_entries.async_entries(DOMAIN)[0].runtime_data.advisor
    assert advisor.push_map == {}
    assert advisor.mute_entities == []
    from homeassistant.util import dt as dt_util

    assert advisor.plan("lueften_feuchte", dt_util.utcnow()) == {}


# --- Umstiegsdienste -----------------------------------------------------------------
async def test_dependencies_service(hass: HomeAssistant, backend: FakeThermostat, freezer) -> None:
    """abhaengigkeiten: Cloud- und tado-Entitäten werden benannt."""
    ent_reg = er.async_get(hass)
    humidity = ent_reg.async_get_or_create(
        "sensor", "tado", "hum5", suggested_object_id="wohnzimmer_luftfeuchtigkeit"
    )
    hass.states.async_set(humidity.entity_id, "55")
    await setup_v4(hass, data=room_data(feuchtesensor=humidity.entity_id))
    await settle(hass, freezer)
    result = await hass.services.async_call(
        DOMAIN, "abhaengigkeiten", {}, blocking=True, return_response=True
    )
    room = result["raeume"]["Wohnzimmer"]
    assert room[BACKEND]["integration"] == "test"
    assert room[humidity.entity_id]["integration"] == "tado"
    assert room[humidity.entity_id]["cloud"] is True
    assert result["tado_cloud"] == [humidity.entity_id]
    assert result["tado_integration_entbehrlich"] is False


async def test_replace_entity_service(
    hass: HomeAssistant, backend: FakeThermostat, freezer
) -> None:
    """entitaet_ersetzen: Thermostat in allen Räumen tauschen, Einstellungen bleiben."""
    entry = await setup_v4(hass)
    await settle(hass, freezer)
    hass.states.async_set("climate.wohnzimmer_homekit", "off", {"hvac_modes": ["off", "heat"]})
    hass.states.async_set("sensor.x", "1")

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "entitaet_ersetzen", {"alt": BACKEND, "neu": "sensor.x"}, blocking=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "entitaet_ersetzen",
            {"alt": BACKEND, "neu": "climate.gibt_es_nicht"},
            blocking=True,
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "entitaet_ersetzen",
            {"alt": "climate.nicht_verwendet", "neu": "climate.wohnzimmer_homekit"},
            blocking=True,
        )

    result = await hass.services.async_call(
        DOMAIN,
        "entitaet_ersetzen",
        {"alt": BACKEND, "neu": "climate.wohnzimmer_homekit"},
        blocking=True,
        return_response=True,
    )
    assert result["geaendert"] == ["Wohnzimmer: klimageraete"]
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    assert sub.data["klimageraete"] == ["climate.wohnzimmer_homekit"]
    assert sub.data["komforttemperatur"] == 21.0
    assert entry.state is ConfigEntryState.LOADED


async def test_missing_thermostat_issue(
    hass: HomeAssistant, backend: FakeThermostat, freezer
) -> None:
    """Fehlt ein Thermostat (z. B. Integration gelöscht), erscheint ein Reparaturhinweis."""
    entry = await setup_v4(hass, data=room_data(klimageraete=["climate.geloescht"]))
    await settle(hass, freezer)
    sub_id = next(iter(entry.subentries))
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"thermostat_fehlt_{sub_id}")
    assert issue is not None
    assert issue.translation_placeholders["entitaeten"] == "climate.geloescht"


# --- Luftreiniger: Preset-Namen und Drehzahl ------------------------------------------
FAN = "fan.reiniger"


def _fan_mocks(hass: HomeAssistant) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    async def _record(call: ServiceCall) -> None:
        calls.append(call)

    for svc in ("turn_on", "turn_off", "set_preset_mode", "set_percentage"):
        hass.services.async_register("fan", svc, _record)
    return calls


def _air_room(**kw: Any) -> dict[str, Any]:
    return room_data(pm25_sensor="sensor.pm25", luftreiniger=FAN, **kw)


async def _enable_purifier(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.pm_wohnzimmer_luftreiniger_automatik"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_purifier_custom_preset_names(
    hass: HomeAssistant, backend: FakeThermostat, freezer
) -> None:
    """Eigene Preset-Namen je Stufe (z. B. Xiaomi „silent“ für Sleep)."""
    freezer.move_to("2026-01-15 23:30:00+01:00")  # Nacht -> Sleep
    calls = _fan_mocks(hass)
    hass.states.async_set("sensor.pm25", "3")
    hass.states.async_set(
        FAN, "on", {"preset_modes": ["auto", "silent", "favorite"], "preset_mode": "auto"}
    )
    await setup_v4(hass, data=_air_room(luftreiniger_preset_sleep="Silent"))
    await settle(hass, freezer)
    await _enable_purifier(hass)
    assert [(c.service, dict(c.data)) for c in calls] == [
        ("set_preset_mode", {"entity_id": FAN, "preset_mode": "silent"})
    ]


async def test_purifier_speed_only(hass: HomeAssistant, backend: FakeThermostat, freezer) -> None:
    """Gerät ohne Presets: Stufen als Drehzahl, gerundete Rückmeldung gilt als erreicht."""
    freezer.move_to("2026-01-15 10:00:00+01:00")
    calls = _fan_mocks(hass)
    hass.states.async_set("sensor.pm25", "20")  # erhöht -> Auto (50 %)
    hass.states.async_set(FAN, "on", {"percentage": 20, "supported_features": 1})
    await setup_v4(hass, data=_air_room())
    await settle(hass, freezer)
    await _enable_purifier(hass)
    assert [(c.service, dict(c.data)) for c in calls] == [
        ("set_percentage", {"entity_id": FAN, "percentage": 50})
    ]
    hass.states.async_set(
        FAN, "on", {"percentage": 55, "supported_features": 1}, context=calls[-1].context
    )
    await advance(hass, freezer, 15 * 60)
    assert len(calls) == 1  # 55 % ≈ 50 %: kein erneutes Senden
    hass.states.async_set("sensor.pm25", "60")  # hoch -> Turbo (100 %)
    await advance(hass, freezer, 11 * 60)
    assert (calls[-1].service, calls[-1].data["percentage"]) == ("set_percentage", 100)


# --- Migration der Live-Konfiguration 1.3 -> 1.4 ---------------------------------------
LIVE_V201_OPTIONS: dict[str, Any] = {
    "absenkung": 3,
    "annaeherung_erforderlich": True,
    "aussentemperatur_grenze": 17,
    "aussentemperatur_sensor": "sensor.aussentemperatur",
    "beratung_abstand": 120,
    "beratung_alexa": True,
    "beratung_alexa_skript": "script.notify_alexa",
    "beratung_panel": True,
    "beratung_panel_dienst": "esphome.panel_tt_notification_show",
    "beratung_push": True,
    "beratung_push_zuordnung": "person.anna: notify.mobile_app_annas_telefon",
    "beratung_ruhe_beginn": "22:00:00",
    "beratung_ruhe_ende": "07:00:00",
    "beratung_stumm": ["input_boolean.alles_stumm"],
    "mindesttemperatur": 16,
    "personen": ["person.anna", "person.ben"],
    "sperre_wirkung": "aus",
    "vorheizstufe": "balance",
}


async def test_migration_v201_keeps_live_settings(
    hass: HomeAssistant, backend: FakeThermostat, freezer
) -> None:
    """1.3 -> 1.4: alle Werte bleiben, nur „sprache = de“ kommt hinzu."""
    set_home_states(hass)
    set_schedule(hass, True, 21.0)
    data = room_data(fenstersensoren=None, extern_aus_als_fenster=True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PM Klima",
        unique_id=DOMAIN,
        version=1,
        minor_version=3,
        options=dict(LIVE_V201_OPTIONS),
        subentries_data=[
            {
                "data": data,
                "subentry_type": SUBENTRY_ROOM,
                "title": "Wohnzimmer",
                "unique_id": "wohnzimmer",
            }
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (entry.version, entry.minor_version) == (1, 4)
    assert dict(entry.options) == {**LIVE_V201_OPTIONS, "sprache": "de"}
    assert dict(next(iter(entry.subentries.values())).data) == data
    advisor = entry.runtime_data.advisor
    assert advisor.alexa_script == "script.notify_alexa"
    assert advisor.panel_service == "esphome.panel_tt_notification_show"
