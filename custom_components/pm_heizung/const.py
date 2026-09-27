"""Konstanten für PM Klima (Domain pm_heizung)."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "pm_heizung"
PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]

SUBENTRY_ROOM: Final = "raum"
STORAGE_VERSION: Final = 1
NAME: Final = "PM Klima"
CONFIG_VERSION: Final = 1
CONFIG_MINOR_VERSION: Final = 4  # 1.1 = v1.0.x, 1.2 = v2.0.0, 1.3 = v2.0.1, 1.4 = v2.1.0

# --- Zentrale (Options) --------------------------------------------------
CONF_PERSONS: Final = "personen"
CONF_PRESENCE: Final = "anwesenheit_entitaeten"
CONF_DISTANCE: Final = "abstand_sensoren"
CONF_DIRECTION: Final = "richtung_sensoren"
CONF_SETBACK: Final = "absenkung"
CONF_MIN_TEMP_AWAY: Final = "mindesttemperatur"
CONF_FAR_SETBACK: Final = "fern_absenkung"
CONF_PREHEAT: Final = "vorheizstufe"
CONF_RADIUS_NEAR: Final = "eigener_nahradius"
CONF_RADIUS_MID: Final = "eigener_mittelradius"
CONF_RADIUS_FAR: Final = "eigener_fernradius"
CONF_APPROACH: Final = "annaeherung_erforderlich"
CONF_LEAVE_DELAY: Final = "verlassen_verzoegerung"
CONF_OUTDOOR: Final = "aussentemperatur_sensor"
CONF_OUTDOOR_LIMIT: Final = "aussentemperatur_grenze"
CONF_RELEASE: Final = "freigabe_entitaet"
CONF_LOCK_EFFECT: Final = "sperre_wirkung"
CONF_LOCK_HOLD: Final = "sperre_mindesthaltezeit"
CONF_LANGUAGE: Final = "sprache"

LANGUAGE_AUTO: Final = "auto"
LANGUAGE_DE: Final = "de"
LANGUAGE_EN: Final = "en"
LANGUAGES: Final = [LANGUAGE_AUTO, LANGUAGE_DE, LANGUAGE_EN]
DEFAULT_LANGUAGE: Final = LANGUAGE_AUTO

PREHEAT_OFF: Final = "aus"
PREHEAT_ECO: Final = "eco"
PREHEAT_BALANCE: Final = "balance"
PREHEAT_COMFORT: Final = "komfort"
PREHEAT_CUSTOM: Final = "eigene"
PREHEAT_LEVELS: Final = [
    PREHEAT_OFF,
    PREHEAT_ECO,
    PREHEAT_BALANCE,
    PREHEAT_COMFORT,
    PREHEAT_CUSTOM,
]
# Radien [nah, mittel, fern] in Metern (wie Blueprint)
PREHEAT_RADII: Final[dict[str, tuple[float, float, float]]] = {
    PREHEAT_ECO: (1500.0, 4000.0, 15000.0),
    PREHEAT_BALANCE: (4000.0, 10000.0, 25000.0),
    PREHEAT_COMFORT: (10000.0, 25000.0, 50000.0),
    PREHEAT_OFF: (0.0, 0.0, 25000.0),
}

LOCK_EFFECT_SCHEDULE: Final = "zeitplan"
LOCK_EFFECT_OFF: Final = "aus"
LOCK_EFFECTS: Final = [LOCK_EFFECT_SCHEDULE, LOCK_EFFECT_OFF]

DEFAULT_SETBACK: Final = 3.0
DEFAULT_MIN_TEMP_AWAY: Final = 16.0
DEFAULT_FAR_SETBACK: Final = 2.0
DEFAULT_PREHEAT: Final = PREHEAT_BALANCE
DEFAULT_RADIUS_NEAR: Final = 3.0
DEFAULT_RADIUS_MID: Final = 8.0
DEFAULT_RADIUS_FAR: Final = 20.0
DEFAULT_APPROACH: Final = True
DEFAULT_LEAVE_DELAY: Final = 5
DEFAULT_OUTDOOR_LIMIT: Final = 17.0
DEFAULT_LOCK_EFFECT: Final = LOCK_EFFECT_SCHEDULE
DEFAULT_LOCK_HOLD: Final = 15

# --- Raum (Subentry-Daten) -----------------------------------------------
CONF_NAME: Final = "name"
CONF_CLIMATES: Final = "klimageraete"
CONF_TEMP_SENSOR: Final = "temperatursensor"
CONF_HUMIDITY_SENSOR: Final = "feuchtesensor"
CONF_WINDOWS: Final = "fenstersensoren"
CONF_WINDOW_OPEN_DELAY: Final = "fenster_verzoegerung_offen"
CONF_WINDOW_CLOSE_DELAY: Final = "fenster_verzoegerung_zu"
CONF_WINDOW_ACTION: Final = "fenster_aktion"
CONF_SCHEDULE: Final = "zeitplan"
CONF_SCHEDULE_ATTR: Final = "zeitplan_attribut"
CONF_COMFORT: Final = "komforttemperatur"
CONF_ECO: Final = "ecotemperatur"
CONF_FROST: Final = "frostschutztemperatur"
CONF_MIN: Final = "min_temperatur"
CONF_MAX: Final = "max_temperatur"
CONF_OVERLAY_MODE: Final = "overlay_modus"
CONF_OVERLAY_MINUTES: Final = "overlay_minuten"
CONF_BOOST_MINUTES: Final = "boost_minuten"
CONF_OFF_FROST: Final = "aus_mit_frostschutz"
CONF_ADOPT_EXTERNAL: Final = "externe_aenderung_uebernehmen"
CONF_EXT_OFF_AS_WINDOW: Final = "extern_aus_als_fenster"

WINDOW_ACTION_FROST: Final = "frostschutz"
WINDOW_ACTION_OFF: Final = "aus"
WINDOW_ACTIONS: Final = [WINDOW_ACTION_FROST, WINDOW_ACTION_OFF]

OVERLAY_NEXT_BLOCK: Final = "naechster_block"
OVERLAY_TIMER: Final = "timer"
OVERLAY_PERMANENT: Final = "dauerhaft"
OVERLAY_MODES: Final = [OVERLAY_NEXT_BLOCK, OVERLAY_TIMER, OVERLAY_PERMANENT]

DEFAULT_SCHEDULE_ATTR: Final = "temperatur"
DEFAULT_COMFORT: Final = 21.0
DEFAULT_ECO: Final = 18.0
DEFAULT_FROST: Final = 7.0
DEFAULT_MIN: Final = 5.0
DEFAULT_MAX: Final = 25.0
DEFAULT_WINDOW_OPEN_DELAY: Final = 30
DEFAULT_WINDOW_CLOSE_DELAY: Final = 10
DEFAULT_OVERLAY_MODE: Final = OVERLAY_NEXT_BLOCK
DEFAULT_OVERLAY_MINUTES: Final = 60
DEFAULT_BOOST_MINUTES: Final = 30

# --- Phasen / Gründe -----------------------------------------------------
PHASE_HOME: Final = "zuhause"
PHASE_COMFORT: Final = "komfort"
PHASE_BETWEEN: Final = "zwischen"
PHASE_HOLD: Final = "halten"
PHASE_FAR: Final = "fern"
PHASES: Final = [PHASE_FAR, PHASE_HOLD, PHASE_BETWEEN, PHASE_COMFORT, PHASE_HOME]

REASON_SCHEDULE: Final = "zeitplan"
REASON_AWAY: Final = "abwesenheit"
REASON_PREHEAT: Final = "vorheizen"
REASON_WINDOW: Final = "fenster"
REASON_LOCK: Final = "sperre"
REASON_MANUAL: Final = "manuell"
REASON_BOOST: Final = "boost"
REASON_OFF: Final = "aus"
REASON_PAUSED: Final = "pausiert"
REASON_WINDOW_EXT: Final = "fenster_extern"
REASONS: Final = [
    REASON_SCHEDULE,
    REASON_AWAY,
    REASON_PREHEAT,
    REASON_WINDOW,
    REASON_WINDOW_EXT,
    REASON_LOCK,
    REASON_MANUAL,
    REASON_BOOST,
    REASON_OFF,
    REASON_PAUSED,
]

LOCK_REASON_RELEASE: Final = "freigabe_aus"
LOCK_REASON_OUTDOOR: Final = "aussentemperatur"

# --- Presets -------------------------------------------------------------
PRESET_COMFORT: Final = "komfort"
PRESET_ECO: Final = "eco"
PRESET_AWAY: Final = "abwesend"
PRESET_FROST: Final = "frostschutz"
PRESET_BOOST: Final = "boost"
PRESET_NONE: Final = "none"
PRESET_SCHEDULE: Final = "zeitplan"
PRESET_MANUAL: Final = "manuell"
PRESETS: Final = [
    PRESET_NONE,
    PRESET_SCHEDULE,
    PRESET_MANUAL,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_AWAY,
    PRESET_FROST,
    PRESET_BOOST,
]
# Presets, deren Temperatur nie als „letzter Handwert“ gilt
NON_MANUAL_PRESETS: Final = (PRESET_FROST, PRESET_BOOST)

# --- Backend-Ansteuerung -------------------------------------------------
DEBOUNCE_SECONDS: Final = 5.0
MIN_SEND_INTERVAL: Final = 10.0
ECHO_GRACE_SECONDS: Final = 60.0
DEFAULT_TEMP_STEP: Final = 0.5
MAX_SEND_ATTEMPTS: Final = 3
VERIFY_SECONDS: Final = 30.0
BACKOFF_START: Final = 60.0
BACKOFF_MAX: Final = 15 * 60.0
WARN_THROTTLE: Final = 15 * 60.0
OVERLAY_FALLBACK_MINUTES: Final = 60
TEMP_TOLERANCE: Final = 0.05
# Externes „aus“: Fensteröffnung (Fenstererkennung des Thermostats) bzw. Pingpong-Schutz
EXT_WINDOW_MINUTES: Final = 30
OFF_REJECT_WINDOW: Final = 30 * 60.0  # Betrachtungszeitraum
OFF_REJECT_LIMIT: Final = 3  # ab so vielen Ablehnungen im Zeitraum zurückhalten
OFF_HOLD_START: Final = 5 * 60.0  # 5, 10, 20, 40, 60 min
OFF_HOLD_MAX: Final = 60 * 60.0
OFF_QUIET_SECONDS: Final = 60 * 60.0  # so lange Ruhe -> Reparaturhinweis weg
ISSUE_EXT_OFF: Final = "extern_aus"
ISSUE_BACKEND_MISSING: Final = "thermostat_fehlt"
ACTION_HOLD_SECONDS: Final = 120.0  # optimistische hvac_action bis Backend bestätigt
ACTION_MARGIN: Final = 0.2

# --- Dienste -------------------------------------------------------------
SERVICE_BOOST: Final = "boost"
SERVICE_SET_OVERLAY: Final = "set_overlay"
SERVICE_CLEAR_OVERLAY: Final = "clear_overlay"
SERVICE_REEVALUATE: Final = "reevaluate"
ATTR_DURATION: Final = "dauer"
ATTR_TEMPERATURE: Final = "temperatur"

SERVICE_DEPENDENCIES: Final = "abhaengigkeiten"
SERVICE_REPLACE_ENTITY: Final = "entitaet_ersetzen"
ATTR_OLD: Final = "alt"
ATTR_NEW: Final = "neu"

SERVICE_ADVICE_TEST: Final = "beratung_testen"
ATTR_CHANNEL: Final = "kanal"
ATTR_TOPIC: Final = "thema"

SIGNAL_CENTRAL_UPDATED: Final = f"{DOMAIN}_central_updated_{{}}"

# =========================================================================
# Modul „Luft“
# =========================================================================
# Zentrale (Options)
CONF_AIR_OUTDOOR_TEMP: Final = "luft_aussentemperatur"
CONF_AIR_OUTDOOR_HUM: Final = "luft_aussenfeuchte"
CONF_WEATHER: Final = "wetter_entitaet"

# Raum (Subentry)
CONF_CO2_SENSOR: Final = "co2_sensor"
CONF_PM25_SENSOR: Final = "pm25_sensor"
CONF_HUMIDITY_LIMIT: Final = "feuchte_grenze"
CONF_WET_ROOM: Final = "nassraum"
CONF_FRSI: Final = "frsi"
CONF_PURIFIER: Final = "luftreiniger"
CONF_PURIFIER_FILTERS: Final = "luftreiniger_filter"
CONF_NIGHT_START: Final = "nacht_beginn"
CONF_NIGHT_END: Final = "nacht_ende"
CONF_PURIFIER_PAUSE: Final = "luftreiniger_pause"
CONF_PURIFIER_HOLD: Final = "luftreiniger_haltezeit"

DEFAULT_HUMIDITY_LIMIT: Final = 65.0
DEFAULT_HUMIDITY_LIMIT_WET: Final = 70.0
DEFAULT_FRSI: Final = 0.75
DEFAULT_NIGHT_START: Final = "22:00:00"
DEFAULT_NIGHT_END: Final = "07:00:00"
DEFAULT_PURIFIER_PAUSE: Final = 60
DEFAULT_PURIFIER_HOLD: Final = 10

HUMIDITY_DRY: Final = 35.0
HUMIDITY_VERY_DRY: Final = 30.0
HUMIDITY_BAD: Final = 70.0
CO2_WARN: Final = 1000.0
CO2_BAD: Final = 1400.0
PM25_MID: Final = 12.0
PM25_HIGH: Final = 35.0
PM25_MID_OFF: Final = 10.0  # Hysterese
PM25_HIGH_OFF: Final = 30.0
MOLD_WARN: Final = 70.0
MOLD_RISK: Final = 80.0
ABS_HUMIDITY_MARGIN: Final = 1.0  # g/m³ – „deutlich“ trockener draußen
FROST_INDOOR: Final = 12.0
FILTER_PERCENT_MIN: Final = 10.0
FILTER_HOURS_MIN: Final = 7 * 24.0
WINDOW_REMIND_GRACE_MIN: Final = 5.0
SHOWER_RISE: Final = 10.0  # Prozentpunkte Anstieg …
SHOWER_WINDOW_MIN: Final = 20.0  # … innerhalb dieser Minuten = Duschen erkannt
PURIFIER_MIN_GAP: Final = 30.0  # s zwischen zwei Befehlen an den Luftreiniger
RAIN_STATES: Final = ("rainy", "pouring", "lightning-rainy", "snowy-rainy", "hail")

QUALITY_GOOD: Final = "gut"
QUALITY_MID: Final = "mittel"
QUALITY_BAD: Final = "schlecht"
QUALITIES: Final = [QUALITY_GOOD, QUALITY_MID, QUALITY_BAD]

MOLD_LOW: Final = "gering"
MOLD_LEVEL_WARN: Final = "warnung"
MOLD_LEVEL_RISK: Final = "risiko"
MOLD_LEVELS: Final = [MOLD_LOW, MOLD_LEVEL_WARN, MOLD_LEVEL_RISK]

# Stufen der Luftreiniger-Automatik (Standardnamen = Presets von Philips Air+)
PURIFIER_OFF: Final = "aus"
PURIFIER_AUTO: Final = "Auto"
PURIFIER_SLEEP: Final = "Sleep"
PURIFIER_FAST: Final = "Fast"
PURIFIER_TURBO: Final = "Turbo"
CONF_PURIFIER_PRESET_AUTO: Final = "luftreiniger_preset_auto"
CONF_PURIFIER_PRESET_SLEEP: Final = "luftreiniger_preset_sleep"
CONF_PURIFIER_PRESET_FAST: Final = "luftreiniger_preset_fast"
CONF_PURIFIER_PRESET_TURBO: Final = "luftreiniger_preset_turbo"
PURIFIER_PRESET_OPTIONS: Final[dict[str, str]] = {
    PURIFIER_AUTO: CONF_PURIFIER_PRESET_AUTO,
    PURIFIER_SLEEP: CONF_PURIFIER_PRESET_SLEEP,
    PURIFIER_FAST: CONF_PURIFIER_PRESET_FAST,
    PURIFIER_TURBO: CONF_PURIFIER_PRESET_TURBO,
}
# Geräte ohne Presets: Stufe -> Lüfterdrehzahl in Prozent
PURIFIER_PERCENT: Final[dict[str, int]] = {
    PURIFIER_SLEEP: 25,
    PURIFIER_AUTO: 50,
    PURIFIER_FAST: 75,
    PURIFIER_TURBO: 100,
}

# =========================================================================
# Modul „Beratung“
# =========================================================================
CONF_ADV_PUSH: Final = "beratung_push"
CONF_ADV_ALEXA: Final = "beratung_alexa"
CONF_ADV_PANEL: Final = "beratung_panel"
CONF_ADV_PUSH_MAP: Final = "beratung_push_zuordnung"
CONF_ADV_ALEXA_SCRIPT: Final = "beratung_alexa_skript"
CONF_ADV_PANEL_SERVICE: Final = "beratung_panel_dienst"
CONF_ADV_MUTE: Final = "beratung_stumm"
CONF_ADV_QUIET_START: Final = "beratung_ruhe_beginn"
CONF_ADV_QUIET_END: Final = "beratung_ruhe_ende"
CONF_ADV_INTERVAL: Final = "beratung_abstand"

# Keine installationsspezifischen Vorgaben: Kanäle wirken erst, wenn ein Ziel gesetzt ist
DEFAULT_PUSH_MAP: Final[dict[str, str]] = {}
DEFAULT_ALEXA_SCRIPT: Final = ""
DEFAULT_PANEL_SERVICE: Final = ""
DEFAULT_MUTE: Final[list[str]] = []
DEFAULT_ADV_PUSH: Final = True
DEFAULT_ADV_ALEXA: Final = False
DEFAULT_ADV_PANEL: Final = False
DEFAULT_QUIET_START: Final = "22:00:00"
DEFAULT_QUIET_END: Final = "07:00:00"
DEFAULT_ADV_INTERVAL: Final = 120

ADV_MIN_ACTIVE_SECONDS: Final = 5 * 60.0  # Empfehlung muss so lange bestehen
ADV_GLOBAL_GAP_SECONDS: Final = 10 * 60.0  # Mindestabstand zweier Meldungen insgesamt
ADV_TICK_SECONDS: Final = 60.0
ADV_DEBOUNCE_SECONDS: Final = 10.0

CHANNEL_PUSH: Final = "push"
CHANNEL_ALEXA: Final = "alexa"
CHANNEL_PANEL: Final = "panel"
CHANNELS: Final = [CHANNEL_PUSH, CHANNEL_ALEXA, CHANNEL_PANEL]

# Themen (Reihenfolge = Priorität, 1 = höchste)
TOPIC_FROST: Final = "frostgefahr"
TOPIC_HEAT_WINDOW: Final = "heizen_fenster"
TOPIC_MOLD: Final = "schimmel"
TOPIC_WINDOW_CLOSE: Final = "fenster_schliessen"
TOPIC_WINDOW_RAIN: Final = "fenster_regen"
TOPIC_VENT_CO2: Final = "lueften_co2"
TOPIC_VENT_HUMIDITY: Final = "lueften_feuchte"
TOPIC_PM25: Final = "feinstaub"
TOPIC_DRY: Final = "zu_trocken"
TOPIC_FILTER: Final = "filter"
TOPIC_MOLD_WARN: Final = "schimmel_warnung"  # nur Dashboard, keine Meldung
TOPICS: Final = [
    TOPIC_FROST,
    TOPIC_HEAT_WINDOW,
    TOPIC_MOLD,
    TOPIC_WINDOW_CLOSE,
    TOPIC_WINDOW_RAIN,
    TOPIC_VENT_CO2,
    TOPIC_VENT_HUMIDITY,
    TOPIC_PM25,
    TOPIC_DRY,
    TOPIC_FILTER,
    TOPIC_MOLD_WARN,
]
NOTIFY_TOPICS: Final = [t for t in TOPICS if t != TOPIC_MOLD_WARN]
# Themen, die auch bei Abwesenheit (per Push) gemeldet werden
AWAY_TOPICS: Final = (TOPIC_FROST, TOPIC_WINDOW_CLOSE, TOPIC_WINDOW_RAIN, TOPIC_HEAT_WINDOW)
# Themen, die auch in der Ruhezeit per Push/Alexa gemeldet werden
QUIET_EXEMPT_TOPICS: Final = (TOPIC_FROST,)

# =========================================================================
# Thermostat-Typen (Backend)
# =========================================================================
BACKEND_TADO_CLOUD: Final = "tado_cloud"  # tado-Integration (Web-API)
BACKEND_TADO_LOCAL: Final = "tado_lokal"  # tado über HomeKit Device bzw. Matter
BACKEND_GENERIC: Final = "generisch"
