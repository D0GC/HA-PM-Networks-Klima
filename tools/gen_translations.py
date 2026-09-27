"""Erzeugt strings.json, translations/de.json und translations/en.json."""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "custom_components" / "pm_heizung"
TOPIC_NAMES = {
    "frostgefahr": ("Frostgefahr", "Frost risk"),
    "heizen_fenster": ("Heizen bei offenem Fenster", "Heating with open window"),
    "schimmel": ("Schimmelrisiko", "Mould risk"),
    "fenster_schliessen": ("Fenster schließen", "Close window"),
    "fenster_regen": ("Fenster offen bei Regen", "Window open while raining"),
    "lueften_co2": ("Lüften (CO₂)", "Ventilate (CO₂)"),
    "lueften_feuchte": ("Lüften (Feuchte)", "Ventilate (humidity)"),
    "feinstaub": ("Feinstaub", "Particulate matter"),
    "zu_trocken": ("Zu trocken", "Too dry"),
    "filter": ("Filterwartung", "Filter maintenance"),
}

# key: (de, en)
T = {
    # Zentrale
    "personen": ("Personen", "Persons"),
    "anwesenheit_entitaeten": ("Anwesenheits-Entitäten (optional)", "Presence entities (optional)"),
    "abstand_sensoren": ("Proximity – Abstandssensoren", "Proximity distance sensors"),
    "richtung_sensoren": ("Proximity – Richtungssensoren", "Proximity direction sensors"),
    "absenkung": ("Absenkung bei Abwesenheit", "Setback when away"),
    "mindesttemperatur": ("Mindesttemperatur bei Abwesenheit", "Minimum temperature when away"),
    "fern_absenkung": ("Zusätzliche Fern-Absenkung", "Additional far setback"),
    "vorheizstufe": ("Vorheizstufe", "Preheat level"),
    "eigener_nahradius": ("Eigener Nahradius", "Custom near radius"),
    "eigener_mittelradius": ("Eigener Mittelradius", "Custom middle radius"),
    "eigener_fernradius": ("Eigener Fernradius", "Custom far radius"),
    "annaeherung_erforderlich": ("Annäherung erforderlich", "Approach required"),
    "verlassen_verzoegerung": ("Verlassen-Verzögerung", "Leave delay"),
    "aussentemperatur_sensor": (
        "Außentemperatur-Sensor (optional)",
        "Outdoor temperature sensor (optional)",
    ),
    "aussentemperatur_grenze": ("Außentemperatur-Grenze", "Outdoor temperature limit"),
    "freigabe_entitaet": (
        "Freigabe / Sommerschalter (optional)",
        "Release / summer switch (optional)",
    ),
    "sperre_wirkung": ("Wirkung der Sperre", "Lock effect"),
    "sperre_mindesthaltezeit": ("Mindesthaltezeit der Sperre", "Minimum lock hold time"),
    "sprache": ("Sprache der Texte", "Language of generated texts"),
    # Raum
    "name": ("Raumname", "Room name"),
    "klimageraete": ("Thermostate (climate-Entitäten)", "Thermostats (climate entities)"),
    "temperatursensor": (
        "Externer Temperatursensor (optional)",
        "External temperature sensor (optional)",
    ),
    "feuchtesensor": ("Externer Feuchtesensor (optional)", "External humidity sensor (optional)"),
    "fenstersensoren": ("Fenster-/Türsensoren (optional)", "Window/door sensors (optional)"),
    "zeitplan": ("Zeitplan (schedule-Helfer, optional)", "Schedule helper (optional)"),
    "zeitplan_attribut": (
        "Temperatur-Schlüssel in den Blockdaten",
        "Temperature key in block data",
    ),
    "komforttemperatur": ("Komforttemperatur (im Zeitblock)", "Comfort temperature (inside block)"),
    "ecotemperatur": ("Eco-Temperatur (außerhalb der Blöcke)", "Eco temperature (outside blocks)"),
    "frostschutztemperatur": ("Frostschutztemperatur", "Frost protection temperature"),
    "min_temperatur": ("Minimale Solltemperatur", "Minimum setpoint"),
    "max_temperatur": ("Maximale Solltemperatur (auch Boost)", "Maximum setpoint (also boost)"),
    "overlay_modus": ("Manuelle Änderung im Auto-Modus gilt", "Manual change in auto mode lasts"),
    "overlay_minuten": ("Dauer bei „für X Minuten“", "Duration for 'for X minutes'"),
    "boost_minuten": ("Boost-Dauer", "Boost duration"),
    "fenster_verzoegerung_offen": ("Fenster: Verzögerung beim Öffnen", "Window: delay on open"),
    "fenster_verzoegerung_zu": ("Fenster: Verzögerung beim Schließen", "Window: delay on close"),
    "fenster_aktion": ("Bei offenem Fenster", "When window is open"),
    "aus_mit_frostschutz": ("Modus „Aus“ hält Frostschutz", "Mode 'off' keeps frost protection"),
    "externe_aenderung_uebernehmen": (
        "Änderungen direkt am Thermostat übernehmen",
        "Adopt changes made directly on the thermostat",
    ),
    "extern_aus_als_fenster": (
        "Externes Aus als Fensteröffnung werten",
        "Treat external off as window opening",
    ),
    # Luft (Zentrale)
    "luft_aussentemperatur": (
        "Außentemperatur für Luft (optional)",
        "Outdoor temperature for air (optional)",
    ),
    "luft_aussenfeuchte": ("Außenluftfeuchte (optional)", "Outdoor humidity (optional)"),
    "wetter_entitaet": (
        "Wetter-Entität für Regen (optional)",
        "Weather entity for rain (optional)",
    ),
    # Beratung (Zentrale)
    "beratung_push": ("Push an anwesende Personen", "Push to persons at home"),
    "beratung_alexa": ("Sprachansage (z. B. Alexa)", "Voice announcement (e.g. Alexa)"),
    "beratung_panel": ("Wanddisplay (z. B. NSPanel)", "Wall display (e.g. NSPanel)"),
    "beratung_push_zuordnung": ("Zuordnung Person → Push-Dienst", "Mapping person → push service"),
    "beratung_alexa_skript": ("Skript für Sprachansagen", "Script for voice announcements"),
    "beratung_panel_dienst": ("Dienst für das Wanddisplay", "Service for the wall display"),
    "beratung_stumm": (
        "Stummschalter (sperren Sprachansagen)",
        "Mute switches (block voice announcements)",
    ),
    "beratung_ruhe_beginn": ("Ruhezeit ab", "Quiet time from"),
    "beratung_ruhe_ende": ("Ruhezeit bis", "Quiet time until"),
    "beratung_abstand": ("Mindestabstand je Thema und Raum", "Minimum interval per topic and room"),
    # Luft (Raum)
    "co2_sensor": ("CO₂-Sensor (optional)", "CO₂ sensor (optional)"),
    "pm25_sensor": ("PM2,5-Sensor (optional)", "PM2.5 sensor (optional)"),
    "nassraum": ("Nassraum (Bad, Duschen-Erkennung)", "Wet room (bathroom, shower detection)"),
    "feuchte_grenze": (
        "Feuchte-Grenze für „Lüften nötig“",
        "Humidity limit for 'ventilation needed'",
    ),
    "frsi": ("Temperaturfaktor fRsi der Außenwand", "Temperature factor fRsi of the outer wall"),
    "luftreiniger": ("Luftreiniger (optional)", "Air purifier (optional)"),
    "luftreiniger_filter": ("Filter-Sensoren (% oder Stunden)", "Filter sensors (% or hours)"),
    "nacht_beginn": ("Nacht ab (Luftreiniger Sleep)", "Night from (purifier sleep)"),
    "nacht_ende": ("Nacht bis", "Night until"),
    "luftreiniger_pause": ("Pause nach manueller Bedienung", "Pause after manual operation"),
    "luftreiniger_haltezeit": ("Mindesthaltezeit einer Stufe", "Minimum hold time per level"),
    "luftreiniger_preset_auto": ("Preset für Stufe „Auto“", "Preset for level 'Auto'"),
    "luftreiniger_preset_sleep": ("Preset für Stufe „Sleep“", "Preset for level 'Sleep'"),
    "luftreiniger_preset_fast": ("Preset für Stufe „Fast“", "Preset for level 'Fast'"),
    "luftreiniger_preset_turbo": ("Preset für Stufe „Turbo“", "Preset for level 'Turbo'"),
}

D = {  # data_description
    "luft_aussentemperatur": (
        "Leer = Sensor der Sperre (Schritt 3).",
        "Empty = lock sensor (step 3).",
    ),
    "luft_aussenfeuchte": (
        "Für absolute Feuchte außen („Lüften sinnvoll“).",
        "Used for absolute outdoor humidity ('ventilation sensible').",
    ),
    "wetter_entitaet": (
        "Regen, Gewitter, Hagel und Schneeregen verhindern die Feuchte-Lüftempfehlung und lösen „Fenster offen bei Regen“ aus.",
        "Rain, thunderstorm, hail and sleet block humidity ventilation advice and trigger 'window open while raining'.",
    ),
    "beratung_push_zuordnung": (
        "Eine Zeile je Person, z. B. „person.anna: notify.mobile_app_annas_iphone“. Push geht nur an anwesende Personen (bei Abwesenheit aller nur Frost/Fenster an alle). Leer = kein Push.",
        "One line per person, e.g. 'person.anna: notify.mobile_app_annas_iphone'. Push goes to persons at home only (when everyone is away: frost/window to all). Empty = no push.",
    ),
    "beratung_alexa_skript": (
        "Skript für Sprachansagen, aufgerufen mit message, type=tts und title (z. B. ein Skript um notify.alexa_media). Leer = keine Ansage. Zusätzlich gelten die Stummschalter.",
        "Script for voice announcements, called with message, type=tts and title (e.g. a script around notify.alexa_media). Empty = no announcement. The mute switches apply in addition.",
    ),
    "beratung_panel_dienst": (
        "Dienst mit den Feldern label und message, z. B. eine ESPHome-Aktion für ein Wanddisplay (esphome.GERÄT_notification_show). Leer = keine Anzeige.",
        "Service with fields label and message, e.g. an ESPHome action for a wall display (esphome.DEVICE_notification_show). Empty = no display.",
    ),
    "sprache": (
        "Gilt für Anzeigetexte, Empfehlungen und Meldungen der Beratung. Automatisch = Sprache von Home Assistant (Deutsch bei de, sonst Englisch).",
        "Applies to display texts, recommendations and advice messages. Automatic = Home Assistant language (German for de, otherwise English).",
    ),
    "luftreiniger_preset_auto": (
        "Preset-Name des Geräts für diese Stufe (Groß-/Kleinschreibung egal). Leer = „Auto“. Geräte ohne Presets werden über die Drehzahl gesteuert (Sleep 25 %, Auto 50 %, Fast 75 %, Turbo 100 %).",
        "Device preset name for this level (case-insensitive). Empty = 'Auto'. Devices without presets are driven by speed (sleep 25 %, auto 50 %, fast 75 %, turbo 100 %).",
    ),
    "beratung_stumm": (
        "Ist einer davon an, gibt es keine Sprachansage (Beratung ist keine Sicherheitsmeldung).",
        "If any is on, no voice announcement is made (advice is not a safety message).",
    ),
    "beratung_ruhe_beginn": (
        "In der Ruhezeit kein Push und keine Sprachansage – außer Frostgefahr. Das Wanddisplay zeigt weiter an.",
        "No push and no voice announcement during quiet time – except frost risk. The wall display still shows messages.",
    ),
    "beratung_abstand": (
        "Dieselbe Meldung für denselben Raum frühestens nach dieser Zeit erneut. Zwischen zwei beliebigen Meldungen liegen mindestens 10 Minuten.",
        "The same message for the same room is repeated at most after this time. Any two messages are at least 10 minutes apart.",
    ),
    "nassraum": (
        "Feuchte-Grenze standardmäßig 70 % statt 65 %, schneller Anstieg (+10 Punkte in 20 min) wird als Duschen erkannt.",
        "Humidity limit 70 % instead of 65 % by default, a quick rise is detected as a shower.",
    ),
    "feuchte_grenze": (
        "Leer = 65 % (Nassraum 70 %).",
        "Empty = 65 % (wet room 70 %).",
    ),
    "frsi": (
        "Schätzt die kälteste Wandstelle: θsi = θi − (θi − θe)·(1 − fRsi). 0,70 = Mindestwert nach DIN 4108-2 (Altbau eher 0,6–0,7, Neubau 0,8+).",
        "Estimates the coldest wall spot. 0.70 = DIN 4108-2 minimum.",
    ),
    "luftreiniger": (
        "Gesteuert wird über Presets (Namen je Stufe unten einstellbar) oder – bei Geräten ohne Presets – über die Drehzahl. Die Automatik wird über den Schalter „Luftreiniger-Automatik“ aktiviert (Standard aus).",
        "Controlled via presets (names per level configurable below) or, for devices without presets, via speed. Enable via the 'Purifier automation' switch (default off).",
    ),
    "luftreiniger_filter": (
        "Hinweis unter 10 % bzw. unter 7 Tagen (168 h).",
        "Hint below 10 % or 7 days (168 h).",
    ),
    "luftreiniger_pause": (
        "Wird der Luftreiniger am Gerät oder in der App bedient, pausiert die Automatik so lange.",
        "When the purifier is operated manually, the automation pauses this long.",
    ),
    "anwesenheit_entitaeten": (
        "Wenn gesetzt, gilt „jemand zuhause“ = mindestens eine Entität ist „an“ (empfohlen bei entprellten Helfern). Sonst zählt der Personen-Zustand „home“.",
        "If set, 'someone home' = at least one entity is on (recommended for debounced helpers). Otherwise the person state 'home' is used.",
    ),
    "abstand_sensoren": (
        "Je Person der Abstandssensor der Proximity-Integration (Einheit wird automatisch umgerechnet). Ohne Sensoren wird bei Abwesenheit nur abgesenkt (Phase halten).",
        "One proximity distance sensor per person. Without sensors only the setback (phase hold) is used.",
    ),
    "richtung_sensoren": (
        "In derselben Reihenfolge wie die Abstandssensoren wählen (paarweise Auswertung). Bei ungleicher Anzahl wird aggregiert.",
        "Select in the same order as the distance sensors (evaluated pairwise). Different counts are aggregated.",
    ),
    "absenkung": (
        "Haltetemperatur = Komforttemperatur des Raums − Absenkung (nie über der aktuellen Zeitplantemperatur).",
        "Hold temperature = room comfort − setback (never above the current schedule temperature).",
    ),
    "fern_absenkung": (
        "Zusätzlich, wenn alle außerhalb des Fernradius sind. 0 = aus.",
        "Extra setback when everyone is beyond the far radius. 0 = off.",
    ),
    "vorheizstufe": (
        "Nah/Mittel/Fern: Eco 1,5/4/15 km · Balance 4/10/25 km · Komfort 10/25/50 km · Aus: kein Vorheizen (Fern 25 km).",
        "Near/middle/far: Eco 1.5/4/15 km · Balance 4/10/25 km · Comfort 10/25/50 km · Off: no preheating (far 25 km).",
    ),
    "annaeherung_erforderlich": (
        "Vorheizen nur bei Richtung „towards“. Eine erreichte Stufe bleibt, solange niemand „away_from“ meldet und die Person im Radius bleibt.",
        "Preheat only when heading 'towards'. A reached level is kept unless someone reports 'away_from' or leaves the radius.",
    ),
    "verlassen_verzoegerung": (
        "So lange muss niemand zuhause sein, bevor abgesenkt wird.",
        "Nobody must be home this long before the setback starts.",
    ),
    "aussentemperatur_sensor": (
        "Ab der Grenze (keine Hysterese) wird gesperrt. Ein unbekannter Wert sperrt nicht.",
        "At or above the limit (no hysteresis) the lock is active. Unknown values never lock.",
    ),
    "freigabe_entitaet": (
        "Nur wenn diese Entität „an“ ist, darf die Abwesenheitslogik arbeiten. Leer = immer.",
        "Absence logic only works while this entity is on. Empty = always.",
    ),
    "sperre_mindesthaltezeit": (
        "Ein Wechsel gesperrt ↔ frei durch die Außentemperatur wird erst übernommen, wenn der bisherige Zustand so lange bestand (verhindert ständiges Umschalten um die Grenze). Die Grenze selbst bleibt exakt. Die Freigabe-Entität wirkt sofort.",
        "A lock change caused by the outdoor temperature is only applied after the previous state lasted this long (prevents toggling around the limit). The limit itself stays exact. The release entity acts immediately.",
    ),
    "sperre_wirkung": (
        "Zeitplan: Abwesenheit/Vorheizen pausieren, Räume folgen ihrem Zeitplan (Blueprint-Verhalten). Heizung aus: Räume im Auto-Modus werden abgeschaltet (Sommerbetrieb).",
        "Schedule: pause absence/preheat, rooms follow their schedule. Heating off: rooms in auto mode are switched off (summer).",
    ),
    "klimageraete": (
        "Beliebige climate-Entitäten (z. B. Zigbee, Homematic, HomeKit Device, Matter, tado). Gesteuert wird nur über die Heiz-Betriebsart (heat, sonst heat_cool bzw. auto), „off“ und die Solltemperatur. Geräte ohne „off“ erhalten ihre niedrigste Solltemperatur.",
        "Any climate entities (e.g. Zigbee, Homematic, HomeKit Device, Matter, tado). Only the heating mode (heat, else heat_cool or auto), off and the setpoint are used. Devices without off get their lowest setpoint.",
    ),
    "zeitplan": (
        "Im Block gilt die Blocktemperatur (Blockdaten, z. B. temperatur: 21) oder die Komforttemperatur, außerhalb die Eco-Temperatur. Ohne Zeitplan gilt immer die Komforttemperatur.",
        "Inside a block the block temperature (block data, e.g. temperatur: 21) or comfort applies, outside eco. Without schedule comfort always applies.",
    ),
    "zeitplan_attribut": (
        "Schlüssel in den „Zusätzlichen Daten“ des Zeitblocks.",
        "Key in the block's additional data.",
    ),
    "extern_aus_als_fenster": (
        "Für Thermostate mit eigener Fenstererkennung, die dabei auf „aus“ schalten (z. B. tado). An: ein externes „aus“ gilt als offenes Fenster – 30 min Frostschutz, danach geht es normal weiter; solange das Thermostat „aus“ meldet, wird nichts gesendet. Aus: ein externes „aus“ wird zurückgestellt. Vorschlag: an bei tado-Thermostaten ohne Fenstersensor.",
        "For thermostats with their own window detection that switch to off (e.g. tado). On: an external off counts as an open window – 30 min frost protection, then normal operation; nothing is sent while the thermostat reports off. Off: an external off is reverted. Suggested: on for tado thermostats without window sensor.",
    ),
    "externe_aenderung_uebernehmen": (
        "Ein am Thermostat gedrehter Wert wird wie eine manuelle Änderung behandelt. Aus: der Wert wird zurückgesetzt.",
        "A value changed on the device is handled like a manual change. Off: it is reverted.",
    ),
}

SEL = {
    "vorheizstufe": {
        "aus": ("Aus – erst bei Ankunft heizen", "Off – heat on arrival"),
        "eco": ("Eco – spät vorheizen", "Eco – preheat late"),
        "balance": ("Balance – Kompromiss", "Balance"),
        "komfort": ("Komfort – früh vorheizen", "Comfort – preheat early"),
        "eigene": ("Benutzerdefiniert", "Custom"),
    },
    "sperre_wirkung": {
        "zeitplan": (
            "Nur Abwesenheit/Vorheizen aussetzen (Zeitplan läuft)",
            "Pause absence/preheat only (schedule runs)",
        ),
        "aus": ("Heizung im Auto-Modus aus (Sommer)", "Heating off in auto mode (summer)"),
    },
    "overlay_modus": {
        "naechster_block": ("Bis zum nächsten Zeitplanwechsel", "Until next schedule change"),
        "timer": ("Für X Minuten", "For X minutes"),
        "dauerhaft": ("Dauerhaft (bis „Auto“)", "Permanently (until auto)"),
    },
    "fenster_aktion": {
        "frostschutz": ("Frostschutztemperatur", "Frost protection"),
        "aus": ("Thermostat aus", "Thermostat off"),
    },
    "kanal": {
        "push": ("Push", "Push"),
        "alexa": ("Sprachansage", "Voice announcement"),
        "panel": ("Wanddisplay", "Wall display"),
    },
    "thema": TOPIC_NAMES,
    "sprache": {
        "auto": ("Automatisch (Sprache von Home Assistant)", "Automatic (Home Assistant language)"),
        "de": ("Deutsch", "German"),
        "en": ("Englisch", "English"),
    },
}

REASONS = {
    "zeitplan": ("Zeitplan", "Schedule"),
    "abwesenheit": ("Abwesenheit", "Away"),
    "vorheizen": ("Vorheizen", "Preheating"),
    "fenster": ("Fenster offen", "Window open"),
    "fenster_extern": ("Fenster (Thermostat)", "Window (thermostat)"),
    "sperre": ("Sperre", "Locked"),
    "manuell": ("Manuell", "Manual"),
    "boost": ("Boost", "Boost"),
    "aus": ("Aus", "Off"),
    "pausiert": ("Pausiert", "Paused"),
}
PHASES = {
    "zuhause": ("Zuhause", "Home"),
    "komfort": ("Komfort (Vorheizen)", "Comfort (preheat)"),
    "zwischen": ("Zwischenstufe", "Between"),
    "halten": ("Halten", "Hold"),
    "fern": ("Fern", "Far"),
}
PRESETS = {
    "none": ("Kein", "None"),
    "zeitplan": ("Zeitplan", "Schedule"),
    "manuell": ("Manuell", "Manual"),
    "komfort": ("Komfort", "Comfort"),
    "eco": ("Eco", "Eco"),
    "abwesend": ("Abwesend", "Away"),
    "frostschutz": ("Frostschutz", "Frost protection"),
    "boost": ("Boost", "Boost"),
}

CENTRAL_STEPS = {
    "user": (
        ("Personen & Proximity", "Persons & proximity"),
        (
            "Wer wird für Abwesenheit und Vorheizen ausgewertet?",
            "Who is evaluated for away and preheat?",
        ),
        ["personen", "anwesenheit_entitaeten", "abstand_sensoren", "richtung_sensoren", "sprache"],
    ),
    "abwesenheit": (
        ("Abwesenheit & Vorheizen", "Away & preheat"),
        (
            "Geofencing: Absenkung bei Abwesenheit, Vorheizen bei Annäherung.",
            "Geofencing: setback when away, preheat when approaching.",
        ),
        [
            "absenkung",
            "mindesttemperatur",
            "fern_absenkung",
            "vorheizstufe",
            "eigener_nahradius",
            "eigener_mittelradius",
            "eigener_fernradius",
            "annaeherung_erforderlich",
            "verlassen_verzoegerung",
        ],
    ),
    "sperre": (
        ("Sperre (Außentemperatur / Freigabe)", "Lock (outdoor temperature / release)"),
        (
            "Die Rückkehr bei Ankunft läuft immer, auch während der Sperre.",
            "Returning on arrival always works, even while locked.",
        ),
        [
            "aussentemperatur_sensor",
            "aussentemperatur_grenze",
            "freigabe_entitaet",
            "sperre_wirkung",
            "sperre_mindesthaltezeit",
        ],
    ),
    "luft": (
        ("Luft: Außenwerte", "Air: outdoor values"),
        (
            "Für absolute Feuchte, Schimmelrisiko und Lüftempfehlungen. Alles optional.",
            "Used for absolute humidity, mould risk and ventilation advice. All optional.",
        ),
        ["luft_aussentemperatur", "luft_aussenfeuchte", "wetter_entitaet"],
    ),
    "beratung": (
        ("Beratung: Benachrichtigungen", "Advice: notifications"),
        (
            "Eingeschaltet wird die Beratung über den Schalter „PM Klima Beratung“ (Standard aus).",
            "Advice is enabled with the switch 'PM Klima advice' (default off).",
        ),
        [
            "beratung_push",
            "beratung_alexa",
            "beratung_panel",
            "beratung_push_zuordnung",
            "beratung_alexa_skript",
            "beratung_panel_dienst",
            "beratung_stumm",
            "beratung_ruhe_beginn",
            "beratung_ruhe_ende",
            "beratung_abstand",
        ],
    ),
}
ROOM_STEPS = {
    "user": (
        ("Raum: Geräte", "Room: devices"),
        (
            "Welche Thermostate und Sensoren gehören zum Raum?",
            "Which thermostats and sensors belong to the room?",
        ),
        [
            "name",
            "klimageraete",
            "temperatursensor",
            "feuchtesensor",
            "fenstersensoren",
            "zeitplan",
            "zeitplan_attribut",
        ],
    ),
    "temperaturen": (
        ("Raum: Temperaturen", "Room: temperatures"),
        ("", ""),
        [
            "komforttemperatur",
            "ecotemperatur",
            "frostschutztemperatur",
            "min_temperatur",
            "max_temperatur",
        ],
    ),
    "verhalten": (
        ("Raum: Verhalten", "Room: behaviour"),
        ("", ""),
        [
            "overlay_modus",
            "overlay_minuten",
            "boost_minuten",
            "fenster_verzoegerung_offen",
            "fenster_verzoegerung_zu",
            "fenster_aktion",
            "aus_mit_frostschutz",
            "externe_aenderung_uebernehmen",
            "extern_aus_als_fenster",
        ],
    ),
    "luft": (
        ("Raum: Luft (optional)", "Room: air (optional)"),
        (
            "Die Luftfeuchte kommt aus dem Feuchtesensor (Schritt 1) oder dem Thermostat.",
            "Humidity comes from the humidity sensor (step 1) or the thermostat.",
        ),
        [
            "co2_sensor",
            "pm25_sensor",
            "nassraum",
            "feuchte_grenze",
            "frsi",
            "luftreiniger",
            "luftreiniger_filter",
            "nacht_beginn",
            "nacht_ende",
            "luftreiniger_pause",
            "luftreiniger_haltezeit",
            "luftreiniger_preset_auto",
            "luftreiniger_preset_sleep",
            "luftreiniger_preset_fast",
            "luftreiniger_preset_turbo",
        ],
    ),
}

ERR_CENTRAL = {
    "richtung_ohne_abstand": (
        "Richtungssensoren benötigen Abstandssensoren.",
        "Direction sensors require distance sensors.",
    )
}
ERR_ROOM = {
    "name_ungueltig": ("Bitte einen gültigen Namen eingeben.", "Please enter a valid name."),
    "name_vorhanden": (
        "Ein Raum mit diesem Namen existiert bereits.",
        "A room with this name already exists.",
    ),
    "thermostat_vergeben": (
        "Das Thermostat {thermostat} ist bereits dem Raum „{raum}“ zugeordnet. Ein Thermostat darf nur in einem Raum vorkommen.",
        "The thermostat {thermostat} is already assigned to room {raum}. A thermostat may only belong to one room.",
    ),
    "eigene_entitaet": (
        "PM-Klima-Entitäten können nicht als Thermostat gewählt werden.",
        "PM Klima entities cannot be used as thermostat.",
    ),
    "min_max": (
        "Das Minimum muss kleiner als das Maximum sein.",
        "Minimum must be lower than maximum.",
    ),
    "ausser_bereich": (
        "Komfort- und Eco-Temperatur müssen zwischen Minimum und Maximum liegen.",
        "Comfort and eco must be between minimum and maximum.",
    ),
}

SERVICES = {
    "boost": (
        ("Boost", "Boost"),
        (
            "Heizt den Raum für die angegebene Dauer mit der Höchsttemperatur, danach geht es normal weiter.",
            "Heats the room at maximum temperature for the given duration.",
        ),
        {
            "dauer": (
                ("Dauer", "Duration"),
                ("Minuten; leer = Raumeinstellung.", "Minutes; empty = room setting."),
            )
        },
    ),
    "set_overlay": (
        ("Manuelle Temperatur setzen", "Set overlay"),
        (
            "Setzt eine manuelle Solltemperatur (wie am Thermostat gedreht).",
            "Sets a manual setpoint (like turning the thermostat).",
        ),
        {
            "temperatur": (
                ("Temperatur", "Temperature"),
                ("Solltemperatur in °C.", "Setpoint in °C."),
            ),
            "dauer": (
                ("Dauer", "Duration"),
                (
                    "Minuten; leer = Raumeinstellung, 0 = dauerhaft.",
                    "Minutes; empty = room setting, 0 = permanent.",
                ),
            ),
        },
    ),
    "clear_overlay": (
        ("Zurück zum Zeitplan", "Clear overlay"),
        ("Beendet manuelle Temperatur und Boost.", "Ends manual overlay and boost."),
        {},
    ),
    "reevaluate": (
        ("Neu berechnen", "Re-evaluate"),
        (
            "Berechnet Zentrale und alle Räume neu und gleicht die Thermostate ab.",
            "Recomputes central logic and all rooms.",
        ),
        {},
    ),
    "abhaengigkeiten": (
        ("Abhängigkeiten prüfen", "Check dependencies"),
        (
            "Listet alle konfigurierten Entitäten mit Integration und zeigt, ob noch etwas von einer Cloud-Integration (z. B. tado) abhängt. Antwort: tado_integration_entbehrlich = true, sobald nichts mehr die tado-Integration benötigt.",
            "Lists all configured entities with their integration and shows whether anything still depends on a cloud integration (e.g. tado). Response: tado_integration_entbehrlich = true once nothing needs the tado integration any more.",
        ),
        {},
    ),
    "entitaet_ersetzen": (
        ("Entität ersetzen", "Replace entity"),
        (
            "Ersetzt eine Entität in der Zentrale und in allen Räumen, z. B. das tado-Cloud-Thermostat durch die lokale HomeKit-Entität. Zeitpläne, Einstellungen und Zustände bleiben erhalten; die Integration lädt danach neu.",
            "Replaces an entity in the central settings and all rooms, e.g. the tado cloud thermostat with the local HomeKit entity. Schedules, settings and state are kept; the integration reloads afterwards.",
        ),
        {
            "alt": (
                ("Bisherige Entität", "Old entity"),
                ("Darf bereits gelöscht sein.", "May already be deleted."),
            ),
            "neu": (
                ("Neue Entität", "New entity"),
                ("Muss dieselbe Domain haben.", "Must have the same domain."),
            ),
        },
    ),
    "beratung_testen": (
        ("Beratung testen", "Test advice"),
        (
            "Sendet eine Testmeldung an einen Kanal – ohne Drosselung, Ruhezeit, Stummschalter und Anwesenheitsprüfung.",
            "Sends a test message to one channel – without throttling, quiet time, mute switches and presence check.",
        ),
        {
            "kanal": (
                ("Kanal", "Channel"),
                (
                    "Push, Sprachansage oder Wanddisplay.",
                    "Push, voice announcement or wall display.",
                ),
            ),
            "thema": (
                ("Thema (optional)", "Topic (optional)"),
                (
                    "Mit Thema wird eine Beispielmeldung dieses Themas gesendet, sonst ein Testtext.",
                    "With a topic, a sample message of that topic is sent, otherwise a test text.",
                ),
            ),
        },
    ),
}


def build(i: int) -> dict:
    def steps(defs):
        out = {}
        for sid, (title, desc, keys) in defs.items():
            step = {"title": title[i], "data": {k: T[k][i] for k in keys}}
            if desc[i]:
                step["description"] = desc[i]
            dd = {k: D[k][i] for k in keys if k in D}
            if dd:
                step["data_description"] = dd
            out[sid] = step
        return out

    central = {
        "step": steps(CENTRAL_STEPS),
        "error": {k: v[i] for k, v in ERR_CENTRAL.items()},
    }
    config = {
        **central,
        "abort": {
            "already_configured": (
                "PM Klima ist bereits eingerichtet. Räume werden über „Raum hinzufügen“ angelegt.",
                "PM Klima is already set up. Add rooms via 'Add room'.",
            )[i]
        },
    }
    return {
        "config": config,
        "options": central,
        "config_subentries": {
            "raum": {
                "entry_type": ("Raum", "Room")[i],
                "initiate_flow": {
                    "user": ("Raum hinzufügen", "Add room")[i],
                    "reconfigure": ("Raum bearbeiten", "Edit room")[i],
                },
                "step": steps(ROOM_STEPS),
                "error": {k: v[i] for k, v in ERR_ROOM.items()},
                "abort": {
                    "reconfigure_successful": ("Raum wurde aktualisiert.", "Room updated.")[i]
                },
            }
        },
        "selector": {
            key: {"options": {o: v[i] for o, v in opts.items()}} for key, opts in SEL.items()
        },
        "entity": {
            "climate": {
                "raum": {
                    "state_attributes": {
                        "preset_mode": {"state": {k: v[i] for k, v in PRESETS.items()}}
                    }
                }
            },
            "sensor": {
                "grund": {
                    "name": ("Grund", "Reason")[i],
                    "state": {k: v[i] for k, v in REASONS.items()},
                },
                "abwesenheitsphase": {
                    "name": ("Abwesenheitsphase", "Away phase")[i],
                    "state": {k: v[i] for k, v in PHASES.items()},
                },
                "luftqualitaet": {
                    "name": ("Qualität", "Quality")[i],
                    "state": {
                        "gut": ("Gut", "Good")[i],
                        "mittel": ("Mittel", "Medium")[i],
                        "schlecht": ("Schlecht", "Poor")[i],
                    },
                },
                "schimmelrisiko": {"name": ("Schimmelrisiko", "Mould risk")[i]},
                "lueftdauer": {"name": ("Lüftdauer", "Ventilation time")[i]},
                "klima_empfehlung": {"name": ("Empfehlung", "Recommendation")[i]},
            },
            "binary_sensor": {
                "fenster_offen": {"name": ("Fenster offen", "Window open")[i]},
                "lueften_empfohlen": {"name": ("Lüften empfohlen", "Ventilation advised")[i]},
            },
            "switch": {
                "aktiv": {"name": ("Heizung aktiv", "Heating active")[i]},
                "beratung": {"name": ("Beratung", "Advice")[i]},
                "luftreiniger_automatik": {
                    "name": ("Luftreiniger-Automatik", "Purifier automation")[i]
                },
            },
        },
        "issues": {
            "extern_aus": {
                "title": (
                    "Thermostat in {raum} wird wiederholt ausgeschaltet",
                    "Thermostat in {raum} is repeatedly switched off",
                )[i],
                "description": (
                    "Das Thermostat im Raum {raum} wurde in 30 Minuten {anzahl}-mal von außen ausgeschaltet (am Gerät, in der Hersteller-App oder durch die Hersteller-Cloud). PM Klima stellt es nicht mehr sofort zurück, sondern wartet {pause} Minuten bzw. bis zur nächsten eigenen Änderung – das schont Batterie und ggf. das Kontingent der Hersteller-API.\n\nBitte in der Hersteller-App prüfen, ob Geofencing/Abwesenheit, ein eigener Zeitplan oder die Fenster-offen-Erkennung parallel eingreifen (bei tado: tado-App). Soll ein externes Aus in diesem Raum als Fensteröffnung gelten, im Raum „Externes Aus als Fensteröffnung werten“ einschalten. Ausschalten bitte über {entitaet}.\n\nDieser Hinweis verschwindet von selbst nach 60 Minuten ohne externes Aus.",
                    "The thermostat in {raum} was switched off externally {anzahl} times within 30 minutes (on the device, in the vendor app or by the vendor cloud). PM Klima now waits {pause} minutes (or until its next own change) before reverting, to spare battery and any vendor API quota.\n\nPlease check the vendor app for geofencing/away, an own schedule or open-window detection interfering (tado: tado app). To treat an external off as a window opening in this room, enable 'Treat external off as window opening'. Switch off via {entitaet}.\n\nThis notice disappears after 60 minutes without an external off.",
                )[i],
            },
            "thermostat_fehlt": {
                "title": (
                    "Thermostat für {raum} nicht gefunden",
                    "Thermostat for {raum} not found",
                )[i],
                "description": (
                    "Im Raum {raum} ist ein Thermostat konfiguriert, das es nicht mehr gibt: {entitaeten}. Wurde z. B. die tado-Integration entfernt, bitte die neue (lokale) Entität eintragen – im Raum „Raum bearbeiten“ oder mit dem Dienst pm_heizung.entitaet_ersetzen. Der Hinweis verschwindet nach dem nächsten Start ohne fehlendes Thermostat.",
                    "Room {raum} uses a thermostat that no longer exists: {entitaeten}. If e.g. the tado integration was removed, please enter the new (local) entity – via 'Edit room' or the service pm_heizung.entitaet_ersetzen. The notice disappears after the next start without missing thermostat.",
                )[i],
            },
        },
        "exceptions": {
            "beratung_nicht_verfuegbar": {
                "message": (
                    "Die Beratung ist nicht verfügbar (Integration nicht geladen).",
                    "Advice is not available (integration not loaded).",
                )[i]
            },
            "nicht_geladen": {
                "message": (
                    "PM Klima ist nicht geladen.",
                    "PM Klima is not loaded.",
                )[i]
            },
            "domain_verschieden": {
                "message": (
                    "{alt} und {neu} haben unterschiedliche Domains.",
                    "{alt} and {neu} have different domains.",
                )[i]
            },
            "entitaet_fehlt": {
                "message": (
                    "Die Entität {entitaet} existiert nicht.",
                    "The entity {entitaet} does not exist.",
                )[i]
            },
            "nicht_verwendet": {
                "message": (
                    "{entitaet} wird in PM Klima nicht verwendet.",
                    "{entitaet} is not used by PM Klima.",
                )[i]
            },
            "thermostat_vergeben": {
                "message": (
                    "{entitaet} ist bereits dem Raum „{raum}“ zugeordnet.",
                    "{entitaet} is already assigned to room {raum}.",
                )[i]
            },
        },
        "services": {
            name: {
                "name": title[i],
                "description": desc[i],
                **(
                    {
                        "fields": {
                            f: {"name": fn[i], "description": fd[i]}
                            for f, (fn, fd) in fields.items()
                        }
                    }
                    if fields
                    else {}
                ),
            }
            for name, (title, desc, fields) in SERVICES.items()
        },
    }


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


dump(BASE / "strings.json", build(1))
dump(BASE / "translations" / "en.json", build(1))
dump(BASE / "translations" / "de.json", build(0))
print("ok")
