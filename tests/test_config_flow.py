"""Config-Flow (Zentrale), Options-Flow und Raum-Subentry-Flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.pm_heizung.const import DOMAIN, SUBENTRY_ROOM

from .conftest import BACKEND, room_data


async def _create_central(hass: HomeAssistant) -> config_entries.ConfigEntry:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "personen": ["person.anna", "person.ben"],
            "anwesenheit_entitaeten": ["input_boolean.anna_ist_zuhause"],
            "abstand_sensoren": ["sensor.abstand_anna"],
            "richtung_sensoren": ["sensor.richtung_anna"],
        },
    )
    assert result["step_id"] == "abwesenheit"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "absenkung": 3,
            "mindesttemperatur": 16,
            "fern_absenkung": 2,
            "vorheizstufe": "balance",
            "eigener_nahradius": 3,
            "eigener_mittelradius": 8,
            "eigener_fernradius": 20,
            "annaeherung_erforderlich": True,
            "verlassen_verzoegerung": 5,
        },
    )
    assert result["step_id"] == "sperre"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "aussentemperatur_sensor": "sensor.aussentemperatur",
            "aussentemperatur_grenze": 17,
            "sperre_wirkung": "zeitplan",
        },
    )
    assert result["step_id"] == "luft"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"luft_aussenfeuchte": "sensor.aussenluftfeuchte", "wetter_entitaet": "weather.dwd"},
    )
    assert result["step_id"] == "beratung"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "beratung_push": True,
            "beratung_alexa": True,
            "beratung_panel": False,
            "beratung_push_zuordnung": "person.anna: notify.mobile_app_annas_telefon",
            "beratung_stumm": ["input_boolean.alles_stumm"],
            "beratung_ruhe_beginn": "22:00:00",
            "beratung_ruhe_ende": "07:00:00",
            "beratung_abstand": 120,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def test_central_flow_and_single_instance(hass: HomeAssistant, backend) -> None:
    """Zentrale anlegen; zweite Einrichtung wird abgewiesen."""
    entry = await _create_central(hass)
    assert entry.title == "PM Klima"
    assert entry.minor_version == 4
    assert entry.options["beratung_panel"] is False
    assert entry.options["luft_aussenfeuchte"] == "sensor.aussenluftfeuchte"
    assert entry.options["personen"] == ["person.anna", "person.ben"]
    assert entry.options["aussentemperatur_grenze"] == 17
    assert "freigabe_entitaet" not in entry.options
    assert hass.states.get("switch.pm_heizung_aktiv").state == "on"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_central_flow_direction_without_distance(hass: HomeAssistant) -> None:
    """Richtungssensoren ohne Abstandssensoren -> Fehler."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"personen": ["person.anna"], "richtung_sensoren": ["sensor.richtung_anna"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"richtung_sensoren": "richtung_ohne_abstand"}


async def test_options_flow(hass: HomeAssistant, backend) -> None:
    """Optionen ändern und optionales Feld leeren."""
    entry = await _create_central(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "user"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"personen": ["person.anna"]}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "absenkung": 4,
            "mindesttemperatur": 15,
            "fern_absenkung": 0,
            "vorheizstufe": "eigene",
            "eigener_nahradius": 2,
            "eigener_mittelradius": 5,
            "eigener_fernradius": 10,
            "annaeherung_erforderlich": False,
            "verlassen_verzoegerung": 10,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"aussentemperatur_grenze": 18, "sperre_wirkung": "aus"},
    )
    assert result["step_id"] == "luft"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["step_id"] == "beratung"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "beratung_push": False,
            "beratung_alexa": True,
            "beratung_panel": True,
            "beratung_ruhe_beginn": "21:30:00",
            "beratung_ruhe_ende": "07:00:00",
            "beratung_abstand": 60,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["personen"] == ["person.anna"]
    assert "abstand_sensoren" not in entry.options
    assert "aussentemperatur_sensor" not in entry.options
    assert entry.options["absenkung"] == 4
    assert entry.options["sperre_wirkung"] == "aus"
    assert "luft_aussenfeuchte" not in entry.options
    # bewusst geleerte Felder bleiben leer (nicht Standard)
    assert entry.options["beratung_push_zuordnung"] == ""
    assert entry.options["beratung_stumm"] == []
    assert entry.options["beratung_ruhe_beginn"] == "21:30:00"


async def test_room_subentry_flow_and_reconfigure(hass: HomeAssistant, backend) -> None:
    """Raum als Subentry anlegen, Entitäten entstehen, Raum ändern."""
    entry = await _create_central(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # eigene Entität als Backend ist verboten
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Küche",
            "klimageraete": ["climate.pm_wohnzimmer"],
            "zeitplan_attribut": "temperatur",
        },
    )
    assert result["errors"] == {"klimageraete": "eigene_entitaet"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Küche",
            "klimageraete": [BACKEND],
            "fenstersensoren": ["binary_sensor.fenster_kueche"],
            "zeitplan": "schedule.heizung_kueche",
            "zeitplan_attribut": "temperatur",
        },
    )
    assert result["step_id"] == "temperaturen"
    # min >= max -> Fehler
    bad = {
        k: room_data()[k] for k in ("komforttemperatur", "ecotemperatur", "frostschutztemperatur")
    }
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**bad, "min_temperatur": 25, "max_temperatur": 20}
    )
    assert result["errors"] == {"max_temperatur": "min_max"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**bad, "min_temperatur": 5, "max_temperatur": 25}
    )
    assert result["step_id"] == "verhalten"
    beh = {
        k: room_data()[k]
        for k in (
            "overlay_modus",
            "overlay_minuten",
            "boost_minuten",
            "fenster_verzoegerung_offen",
            "fenster_verzoegerung_zu",
            "fenster_aktion",
            "aus_mit_frostschutz",
            "externe_aenderung_uebernehmen",
        )
    }
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], beh)
    assert result["step_id"] == "luft"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "co2_sensor": "sensor.co2_kueche",
            "nassraum": False,
            "frsi": 0.7,
            "nacht_beginn": "22:00:00",
            "nacht_ende": "07:00:00",
            "luftreiniger_pause": 60,
            "luftreiniger_haltezeit": 10,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subs = list(entry.subentries.values())
    assert len(subs) == 1
    assert subs[0].title == "Küche"
    assert subs[0].unique_id == "kuche"
    assert subs[0].data["komforttemperatur"] == 21.0
    assert "name" not in subs[0].data
    # Entry wurde neu geladen -> Raum-Entitäten existieren
    assert hass.states.get("climate.pm_kuche") is not None
    assert hass.states.get("climate.pm_kuche").attributes["friendly_name"] == "Küche Heizung"
    assert hass.states.get("sensor.pm_kuche_grund") is not None
    assert hass.states.get("binary_sensor.pm_kuche_fenster_offen") is not None
    assert subs[0].data["co2_sensor"] == "sensor.co2_kueche"
    assert hass.states.get("sensor.pm_kuche_luftqualitaet") is not None
    assert hass.states.get("binary_sensor.pm_kuche_lueften_empfohlen") is not None
    assert hass.states.get("switch.pm_kuche_luftreiniger_automatik") is None  # kein Gerät

    # Doppelter Name wird abgewiesen
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Küche", "klimageraete": [BACKEND], "zeitplan_attribut": "temperatur"},
    )
    assert result["errors"] == {"name": "name_vorhanden", "klimageraete": "thermostat_vergeben"}

    # Reconfigure
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": subs[0].subentry_id},
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Küche", "klimageraete": [BACKEND], "zeitplan_attribut": "temperatur"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**bad, "komforttemperatur": 22, "min_temperatur": 5, "max_temperatur": 25},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], beh)
    assert result["step_id"] == "luft"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "nassraum": True,
            "frsi": 0.65,
            "nacht_beginn": "22:00:00",
            "nacht_ende": "07:00:00",
            "luftreiniger_pause": 60,
            "luftreiniger_haltezeit": 10,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    sub = entry.subentries[subs[0].subentry_id]
    assert sub.data["komforttemperatur"] == 22
    assert "fenstersensoren" not in sub.data
    assert "zeitplan" not in sub.data
    assert sub.data["nassraum"] is True
    assert "co2_sensor" not in sub.data
