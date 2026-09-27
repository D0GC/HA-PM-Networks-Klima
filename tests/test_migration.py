"""Migration v1.0.1 (Schema 1.1) -> v2.0.0 (Schema 1.2) mit Live-ähnlichen Daten."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    setup_test_component_platform,
)

from custom_components.pm_heizung.const import DOMAIN, SUBENTRY_ROOM

from .conftest import FakeThermostat, set_home_states, settle

# Optionen und Räume wie im Live-System (Stand v1.0.1)
LIVE_OPTIONS: dict[str, Any] = {
    "personen": ["person.anna", "person.ben"],
    "anwesenheit_entitaeten": [
        "input_boolean.anna_ist_zuhause",
        "input_boolean.ben_ist_zuhause",
    ],
    "abstand_sensoren": ["sensor.abstand_anna", "sensor.abstand_ben"],
    "richtung_sensoren": ["sensor.richtung_anna", "sensor.richtung_ben"],
    "absenkung": 3,
    "mindesttemperatur": 16,
    "fern_absenkung": 2,
    "vorheizstufe": "balance",
    "eigener_nahradius": 3,
    "eigener_mittelradius": 8,
    "eigener_fernradius": 20,
    "annaeherung_erforderlich": True,
    "verlassen_verzoegerung": 5,
    "aussentemperatur_sensor": "sensor.aussentemperatur",
    "aussentemperatur_grenze": 17,
    "sperre_wirkung": "aus",
    "sperre_mindesthaltezeit": 15,
}


def _room(backend: str, comfort: float, **extra: Any) -> dict[str, Any]:
    return {
        "klimageraete": [backend],
        "zeitplan": f"schedule.heizplan_{backend.split('.')[1]}",
        "zeitplan_attribut": "temperatur",
        "komforttemperatur": comfort,
        "ecotemperatur": 18,
        "frostschutztemperatur": 7,
        "min_temperatur": 5,
        "max_temperatur": 25,
        "overlay_modus": "naechster_block",
        "overlay_minuten": 60,
        "boost_minuten": 30,
        "fenster_verzoegerung_offen": 30,
        "fenster_verzoegerung_zu": 10,
        "fenster_aktion": "frostschutz",
        "aus_mit_frostschutz": False,
        "externe_aenderung_uebernehmen": True,
        **extra,
    }


ROOMS = {
    "01WZ": (
        "Wohnzimmer",
        "wohnzimmer",
        _room(
            "climate.wohnzimmer",
            21,
            temperatursensor="sensor.wohnzimmertemperatur",
            fenstersensoren=["binary_sensor.fenster_1_wohnzimmer"],
        ),
    ),
    "01KU": (
        "Küche",
        "kuche",
        _room("climate.kuche", 21, fenstersensoren=["binary_sensor.fenster_kuche"]),
    ),
    "01SZ": ("Schlafzimmer", "schlafzimmer", _room("climate.schlafzimmer", 20)),
    "01BZ": ("Badezimmer", "badezimmer", _room("climate.badezimmer", 22)),
}


async def _backends(hass: HomeAssistant) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    ents = [FakeThermostat(f"fake_{slug}", slug.capitalize()) for _, slug, _ in ROOMS.values()]
    setup_test_component_platform(hass, "climate", ents)
    assert await async_setup_component(hass, "climate", {"climate": {"platform": "test"}})
    await hass.async_block_till_done()


def _v1_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="PM Heizung",
        unique_id=DOMAIN,
        version=1,
        minor_version=1,
        data={},
        options=dict(LIVE_OPTIONS),
        subentries_data=[
            {
                "subentry_id": sid,
                "data": data,
                "subentry_type": SUBENTRY_ROOM,
                "title": title,
                "unique_id": slug,
            }
            for sid, (title, slug, data) in ROOMS.items()
        ],
    )


async def test_migration_v1_to_v2_keeps_everything(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer
) -> None:
    """Bestehende Einträge laden ohne Datenverlust, Entitäts-IDs bleiben gleich."""
    await _backends(hass)
    set_home_states(hass, True)
    hass.states.async_set("person.ben", "home")
    for _, slug, _ in ROOMS.values():
        hass.states.async_set(f"schedule.heizplan_{slug}", "on", {"temperatur": 21})
    entry = _v1_entry()
    entry.add_to_hass(hass)

    # Entitätsregister wie von v1.0.1 angelegt
    reg = er.async_get(hass)
    v1_ids: dict[str, str] = {}
    for sid, (_title, slug, data) in ROOMS.items():
        v1_ids[f"{sid}_climate"] = reg.async_get_or_create(
            "climate",
            DOMAIN,
            f"{sid}_climate",
            suggested_object_id=f"pm_{slug}",
            config_entry=entry,
            config_subentry_id=sid,
        ).entity_id
        v1_ids[f"{sid}_grund"] = reg.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{sid}_grund",
            suggested_object_id=f"pm_{slug}_grund",
            config_entry=entry,
            config_subentry_id=sid,
        ).entity_id
        if data.get("fenstersensoren"):
            v1_ids[f"{sid}_fenster"] = reg.async_get_or_create(
                "binary_sensor",
                DOMAIN,
                f"{sid}_fenster",
                suggested_object_id=f"pm_{slug}_fenster_offen",
                config_entry=entry,
                config_subentry_id=sid,
            ).entity_id
    v1_ids["phase"] = reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_phase",
        suggested_object_id="pm_heizung_abwesenheitsphase",
        config_entry=entry,
    ).entity_id
    v1_ids["aktiv"] = reg.async_get_or_create(
        "switch",
        DOMAIN,
        f"{entry.entry_id}_aktiv",
        suggested_object_id="pm_heizung_aktiv",
        config_entry=entry,
    ).entity_id

    # gespeicherte Daten von v1: Zentrale pausiert, Wohnzimmer mit laufendem Overlay
    hass_storage[f"{DOMAIN}.{entry.entry_id}.zentrale"] = {
        "version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}.zentrale",
        "data": {"aktiv": False, "last_rank": -1, "phase": "zuhause", "presence_known": {}},
    }
    until = dt_util.utcnow() + timedelta(minutes=40)
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("climate.pm_wohnzimmer", "auto"),
                {
                    "hvac_mode": "auto",
                    "manual_temp": None,
                    "preset": None,
                    "overlay_active": True,
                    "overlay_temp": 22.5,
                    "overlay_until": until.isoformat(),
                    "boost_until": None,
                },
            ),
            (State("climate.pm_badezimmer", "off"), {"hvac_mode": "off"}),
        ],
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await settle(hass, freezer)
    assert entry.state is ConfigEntryState.LOADED

    # Schema und Titel migriert, alte Optionen unverändert, neue ergänzt
    assert (entry.version, entry.minor_version) == (1, 4)
    assert entry.title == "PM Klima"
    for key, value in LIVE_OPTIONS.items():
        assert entry.options[key] == value
    # Kanäle ohne installationsspezifische Vorgaben: Push an (ohne Zuordnung = kein Push),
    # Alexa und Panel aus, bis ein Skript bzw. Dienst eingetragen ist
    assert entry.options["beratung_push"] is True
    assert entry.options["beratung_alexa"] is False
    assert entry.options["beratung_panel"] is False
    assert entry.options["beratung_push_zuordnung"] == ""
    assert entry.options["sprache"] == "de"  # bestehende Installation bleibt deutsch
    # Räume: bisherige Daten unverändert, nur die neue Option ergänzt
    # (externes Aus als Fensteröffnung = an, wenn kein Fenstersensor)
    assert {sid: dict(s.data) for sid, s in entry.subentries.items()} == {
        sid: {**data, "extern_aus_als_fenster": not data.get("fenstersensoren")}
        for sid, (_t, _s, data) in ROOMS.items()
    }
    assert entry.subentries["01SZ"].data["extern_aus_als_fenster"] is True
    assert entry.subentries["01WZ"].data["extern_aus_als_fenster"] is False

    # Alle bisherigen Entitäts-IDs bestehen unverändert und haben einen Zustand
    expected = {
        "climate.pm_wohnzimmer",
        "climate.pm_kuche",
        "climate.pm_schlafzimmer",
        "climate.pm_badezimmer",
        "sensor.pm_wohnzimmer_grund",
        "sensor.pm_kuche_grund",
        "sensor.pm_schlafzimmer_grund",
        "sensor.pm_badezimmer_grund",
        "binary_sensor.pm_wohnzimmer_fenster_offen",
        "binary_sensor.pm_kuche_fenster_offen",
        "sensor.pm_heizung_abwesenheitsphase",
        "switch.pm_heizung_aktiv",
    }
    assert set(v1_ids.values()) == expected
    for entity_id in v1_ids.values():
        assert reg.async_get(entity_id).config_entry_id == entry.entry_id
        assert hass.states.get(entity_id) is not None, entity_id
    assert reg.async_get("climate.pm_wohnzimmer").unique_id == "01WZ_climate"
    assert not [e for e in hass.states.async_entity_ids() if e.endswith("_2")]

    # gespeicherte Daten wirken weiter
    assert hass.states.get("switch.pm_heizung_aktiv").state == "off"
    wz = hass.states.get("climate.pm_wohnzimmer")
    assert wz.attributes["grund"] == "pausiert"
    assert wz.attributes["eingestellt"] == 22.5
    assert wz.attributes["preset_mode"] == "manuell"
    assert hass.states.get("climate.pm_badezimmer").state == "off"

    # neue Entitäten (v2) sind hinzugekommen
    for slug in ("wohnzimmer", "kuche", "schlafzimmer", "badezimmer"):
        assert hass.states.get(f"sensor.pm_{slug}_luftqualitaet") is not None
        assert hass.states.get(f"sensor.pm_{slug}_schimmelrisiko") is not None
        assert hass.states.get(f"binary_sensor.pm_{slug}_lueften_empfohlen") is not None
        assert hass.states.get(f"sensor.pm_{slug}_lueftdauer") is not None
    assert hass.states.get("sensor.pm_klima_empfehlung") is not None
    assert hass.states.get("switch.pm_klima_beratung").state == "off"


async def test_migration_unknown_major_version_refused(hass: HomeAssistant) -> None:
    """Eine unbekannte Hauptversion wird nicht geladen (kein Datenverlust)."""
    entry = MockConfigEntry(domain=DOMAIN, version=3, minor_version=1, options={})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migration_respects_existing_values(hass: HomeAssistant, freezer) -> None:
    """Vorhandene Werte und eigene Titel werden bei der Migration nicht überschrieben."""
    await _backends(hass)
    set_home_states(hass, True)
    opts = {**LIVE_OPTIONS, "beratung_push_zuordnung": "", "beratung_alexa": False}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meine Heizung",
        unique_id=DOMAIN,
        version=1,
        minor_version=1,
        options=opts,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.title == "Meine Heizung"
    assert entry.options["beratung_push_zuordnung"] == ""
    assert entry.options["beratung_alexa"] is False
