# Changelog

Alle nennenswerten Änderungen an PM Klima.

## 2.1.0 – für beliebige Thermostate und Installationen

* Heiz- und Aus-Modus je Gerät aus `hvac_modes` (heat → heat_cool → auto; ohne `off` die
  niedrigste Solltemperatur), Gerätetyp-Erkennung (`tado_cloud`, `tado_lokal`, `generisch`),
  „Externes Aus als Fensteröffnung“ nur noch bei tado als Vorschlag.
* Neutrale Texte statt tado-spezifischer („Fenster (Thermostat)“, Reparaturhinweis).
* Sprache der Laufzeittexte wählbar (automatisch/Deutsch/Englisch), englische Meldungstexte
  (10 Varianten je Thema).
* Keine installationsspezifischen Vorgaben mehr (Personen, Push-Dienste, Alexa-Skript,
  NSPanel-Dienst, Stummschalter); Sprachansage und Wanddisplay erst mit eingetragenem Ziel.
* Luftreiniger: Preset-Name je Stufe einstellbar, Geräte ohne Presets über die Drehzahl.
* Neue Dienste `abhaengigkeiten` und `entitaet_ersetzen`, Reparaturhinweis bei fehlendem
  Thermostat – Umstieg von einer Cloud- auf eine lokale Anbindung ohne Neueinrichtung.
* Schema 1.4: bestehende Installationen behalten alle Werte, Sprache wird auf Deutsch gesetzt.
* Geräte, die die Betriebsart in `set_temperature` nicht auswerten (z. B. `generic_thermostat`),
  erhalten `set_hvac_mode` nachgeschoben – vorher blieben sie auf „aus“ (bei tado nicht, um das
  Kontingent zu schonen).
* Beschriftungen der Beratung allgemein („Sprachansage“, „Wanddisplay“); Übersetzungsfehler
  „UNCLOSED_TAG“ im Hilfetext behoben.
* Dokumentation mit Screenshots (Installation, Einrichtung, Funktionsweise, Thermostate, Luft &
  Beratung, Dashboard, FAQ), Beispiel-Dashboard, Issue-Vorlagen; Metadaten (Repository, HACS),
  CI (ruff, pytest, Übersetzungen, hassfest, HACS).
* Veröffentlichung über HACS: Lizenz (MIT), „Open in HACS“-Button, Symbol der Integration (ab
  Home Assistant 2026.3), Release-Workflow.

## 2.0.1

* Pingpong-Schutz bei externem „aus“: ab 3 Ablehnungen in 30 min exponentiell zurückhalten
  (5 … 60 min) bzw. bis zur nächsten eigenen Änderung; übersetzter Reparaturhinweis, der sich
  nach 60 min Ruhe selbst entfernt; auch sofortiges Wieder-Ausschalten zählt.
* Neue Raumoption „Externes Aus als Fensteröffnung werten“ (Standard: an ohne Fenstersensor):
  30 min Frostschutz (`fenster_extern`) ohne Senden, danach zurück; Migration auf Schema 1.3.
* Schimmel/Lüften: Standard-fRsi 0,75; Wandfeuchte-Warnung (70–80 %) ist kein Lüftungsgrund.
* `climate.set_temperature` mit `hvac_mode: off` bleibt aus und merkt den Wert.
* Luftreiniger: Presets unabhängig von Groß-/Kleinschreibung, fehlendes Preset ≠ Auto,
  verspätete Rückmeldungen nicht als manuell, Pause neustartsicher.
* Beratung/Luft: Aufräumen wird vor dem Start registriert (sauberer Teilstart).
* Recorder: minütlich wechselnde Attribute entfernt bzw. ausgenommen.
* `via_device_id`: Erkennung ohne Auswerten von Annotationen (Python 3.14), gegen den
  Quellcode von HA 2026.9.3 getestet.

## 2.0.0 – PM Klima

* Anzeigename „PM Klima“ (Domain, Entitäts-IDs, Dienste unverändert), Konfigurationsschema 1.2
  mit automatischer Migration.
* Heizung: Presets `zeitplan`/`manuell`; wirksamer Sollwert plus Attribut `eingestellt`,
  Eingaben sofort sichtbar; Attribut `anzeige`; Temperatur bei „aus“ schaltet auf heat;
  auto → heat nie mit Frostschutz-/Fenster-/Boostwert; heat/off beenden Overlay und Boost;
  `overlay_bis` nur in auto, `naechster_wechsel_grund`; `hvac_action` optimistisch ohne
  Flackern; externes „aus“ wird nie übernommen (Warnung gedrosselt, Zähler);
  `via_device_id` ab HA 2026.8.
* Neues Modul Luft (Feuchte, Taupunkt, Schimmelrisiko, Lüftempfehlung, Lüftdauer, Qualität,
  Luftreiniger-Automatik, Filterhinweise).
* Neues Modul Beratung (Push/Alexa/NSPanel/Dashboard, Drosselung, Ruhezeit, Stummschalter,
  Anwesenheit, 10 Textvarianten je Meldungsart, Dienst `beratung_testen`).
* Fehlerisolation: Luft/Beratung können die Heizung nicht beeinträchtigen.

## 1.0.1

* Verlassen-Verzögerung nur beim Übergang jemand → niemand, gespeichert (neustartsicher);
  `unknown`/`unavailable` lösen keinen Übergang aus.
* Übernommenes „aus“ im Auto-Modus nie dauerhaft, als Frostschutz; Overlay-Fallback 60 min
  ohne Zeitplan.
* Rundung auf den Temperaturschritt des Thermostats, kein Endlos-Nachsenden.
* Thermostat nur in einem Raum.
* Mindesthaltezeit für Sperrwechsel (Grenze bleibt exakt).
* Senden als Background-Task des Config-Entrys, erst wenn Home Assistant läuft; Backoff bei Fehlern.

## 1.0.0

* Erstveröffentlichung.
