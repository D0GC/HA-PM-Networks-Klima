"""Sprache der erzeugten Texte (Anzeige, Empfehlungen, Begründungen).

Die Oberfläche (Config-Flow, Entitätsnamen, Zustände) übersetzt Home Assistant selbst über
``translations/*.json``. Texte, die PM Klima zur Laufzeit erzeugt – Attribut ``anzeige``,
Empfehlungen, Begründungen, Meldungen der Beratung –, folgen der Option „Sprache“:
``auto`` = Sprache von Home Assistant (Deutsch bei ``de*``, sonst Englisch).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import LANGUAGE_AUTO, LANGUAGE_DE, LANGUAGE_EN

if TYPE_CHECKING:  # reine Textfunktionen bleiben ohne Home-Assistant-Abhängigkeit nutzbar
    from homeassistant.core import HomeAssistant


def resolve_language(hass: HomeAssistant, option: Any) -> str:
    """„de“ oder „en“ aus der Option (auto = Sprache von Home Assistant)."""
    value = str(option or LANGUAGE_AUTO)
    if value in (LANGUAGE_DE, LANGUAGE_EN):
        return value
    language = (hass.config.language or "").casefold()
    return LANGUAGE_DE if language.startswith("de") else LANGUAGE_EN


TEXT: dict[str, dict[str, str]] = {
    "de": {
        # Anzeige (Attribut „anzeige“)
        "starting": "Startet",
        "paused": "Pausiert",
        "window_open": "Fenster offen",
        "frost": "Frostschutz",
        "off": "aus",
        "Off": "Aus",
        "then": "danach {value}",
        "until": "bis {time}",
        "permanent": "dauerhaft",
        "window_ext": "Fenster (Thermostat)",
        "boost_until": "Boost bis {time}",
        "lock": "Sperre",
        "lock_outdoor": "außen {value}",
        "lock_outdoor_unknown": "Außentemperatur",
        "lock_release": "Freigabe aus",
        "manual": "Manuell",
        "away": "Abwesend",
        "preheat": "Vorheizen",
        "schedule": "Zeitplan",
        "comfort": "Komfort",
        "eco": "Eco",
        # Zentrale (Attribut „grund“ der Abwesenheitsphase)
        "central_home": "Jemand zuhause",
        "central_leaving": "Verlassen-Verzögerung läuft",
        "central_away": "Niemand zuhause – Phase {phase}",
        "central_locked_release": " (gesperrt: Freigabe aus)",
        "central_locked_outdoor": " (gesperrt: Außentemperatur ≥ Grenze)",
        # Luft: Gründe
        "need_humidity": "Luftfeuchte {value} %",
        "need_wall": "Wandfeuchte {value} %",
        "need_co2": "CO₂ {value} ppm",
        "q_co2_high": "CO₂ hoch ({value} ppm)",
        "q_co2_mid": "CO₂ erhöht ({value} ppm)",
        "q_rh_high": "Luftfeuchte hoch ({value} %)",
        "q_rh_mid": "Luftfeuchte erhöht ({value} %)",
        "q_rh_very_dry": "Luft sehr trocken ({value} %)",
        "q_rh_dry": "Luft trocken ({value} %)",
        "q_pm_high": "Feinstaub hoch ({value} µg/m³)",
        "q_pm_mid": "Feinstaub erhöht ({value} µg/m³)",
        "q_mold_risk": "Schimmelrisiko (Wand {value} %)",
        "q_mold_warn": "Schimmelwarnung (Wand {value} %)",
        "q_ok": "alle Werte im Rahmen",
        # Luft: Kurztexte (Dashboard)
        "rec_frost": "{room}: nur {value} °C",
        "rec_heat_window": "{room}: Heizung läuft bei offenem Fenster",
        "rec_mold": "{room}: Schimmelrisiko (Wand {value} %)",
        "rec_mold_warn": "{room}: Wandfeuchte erhöht ({value} %)",
        "rec_rain": "{room}: Fenster offen, es regnet",
        "rec_window_close": "{room}: Fenster seit {minutes} min offen",
        "rec_vent_co2": "{room}: {minutes} min stoßlüften (CO₂ {value} ppm)",
        "rec_vent_humidity": "{room}: {minutes} min stoßlüften (Feuchte {value} %)",
        "rec_pm25": "{room}: Feinstaub {value} µg/m³",
        "rec_dry": "{room}: Luft trocken ({value} %)",
        "rec_filter": "{room}: Filter prüfen ({label}: {rest})",
        "filter_percent": "noch {value} Prozent",
        "filter_less_day": "weniger als einen Tag",
        "filter_one_day": "noch einen Tag",
        "filter_days": "noch {value} Tage",
        "unknown": "unbekannt",
        "no_recommendation": "Keine Empfehlung",
        # Luftreiniger: Begründung
        "pur_off": "aus",
        "pur_window": "Fenster offen",
        "pur_pm_high_night": "Feinstaub hoch (nachts)",
        "pur_pm_high": "Feinstaub hoch",
        "pur_pm_mid": "Feinstaub erhöht",
        "pur_night": "Nacht",
        "pur_away": "niemand zuhause",
        "pur_normal": "Normalbetrieb",
        "pur_paused": "pausiert (manuelle Bedienung)",
    },
    "en": {
        "starting": "Starting",
        "paused": "Paused",
        "window_open": "Window open",
        "frost": "Frost protection",
        "off": "off",
        "Off": "Off",
        "then": "then {value}",
        "until": "until {time}",
        "permanent": "permanent",
        "window_ext": "Window (thermostat)",
        "boost_until": "Boost until {time}",
        "lock": "Locked",
        "lock_outdoor": "outdoor {value}",
        "lock_outdoor_unknown": "outdoor temperature",
        "lock_release": "release off",
        "manual": "Manual",
        "away": "Away",
        "preheat": "Preheating",
        "schedule": "Schedule",
        "comfort": "Comfort",
        "eco": "Eco",
        "central_home": "Someone at home",
        "central_leaving": "Leave delay running",
        "central_away": "Nobody at home – phase {phase}",
        "central_locked_release": " (locked: release off)",
        "central_locked_outdoor": " (locked: outdoor temperature ≥ limit)",
        "need_humidity": "Humidity {value} %",
        "need_wall": "Wall humidity {value} %",
        "need_co2": "CO₂ {value} ppm",
        "q_co2_high": "CO₂ high ({value} ppm)",
        "q_co2_mid": "CO₂ elevated ({value} ppm)",
        "q_rh_high": "Humidity high ({value} %)",
        "q_rh_mid": "Humidity elevated ({value} %)",
        "q_rh_very_dry": "Air very dry ({value} %)",
        "q_rh_dry": "Air dry ({value} %)",
        "q_pm_high": "Particulate matter high ({value} µg/m³)",
        "q_pm_mid": "Particulate matter elevated ({value} µg/m³)",
        "q_mold_risk": "Mould risk (wall {value} %)",
        "q_mold_warn": "Mould warning (wall {value} %)",
        "q_ok": "all values within range",
        "rec_frost": "{room}: only {value} °C",
        "rec_heat_window": "{room}: heating with window open",
        "rec_mold": "{room}: mould risk (wall {value} %)",
        "rec_mold_warn": "{room}: wall humidity elevated ({value} %)",
        "rec_rain": "{room}: window open, raining",
        "rec_window_close": "{room}: window open for {minutes} min",
        "rec_vent_co2": "{room}: ventilate {minutes} min (CO₂ {value} ppm)",
        "rec_vent_humidity": "{room}: ventilate {minutes} min (humidity {value} %)",
        "rec_pm25": "{room}: particulate matter {value} µg/m³",
        "rec_dry": "{room}: air dry ({value} %)",
        "rec_filter": "{room}: check filter ({label}: {rest})",
        "filter_percent": "{value} percent left",
        "filter_less_day": "less than a day",
        "filter_one_day": "one day left",
        "filter_days": "{value} days left",
        "unknown": "unknown",
        "no_recommendation": "No recommendation",
        "pur_off": "off",
        "pur_window": "window open",
        "pur_pm_high_night": "particulate matter high (night)",
        "pur_pm_high": "particulate matter high",
        "pur_pm_mid": "particulate matter elevated",
        "pur_night": "night",
        "pur_away": "nobody at home",
        "pur_normal": "normal operation",
        "pur_paused": "paused (manual operation)",
    },
}


def t(lang: str, key: str, **values: Any) -> str:
    """Text in der gewählten Sprache (Rückfall Deutsch), Platzhalter befüllt."""
    table = TEXT.get(lang, TEXT[LANGUAGE_DE])
    template = table.get(key, TEXT[LANGUAGE_DE].get(key, key))
    return template.format(**values) if values else template
