# FAQ & Fehlersuche

[← Zurück zur Übersicht](../README.md)

### Das Thermostat übernimmt die Temperatur nicht.

1. `climate.pm_<raum>` → Attribut `ziel_backend` zeigt, was gesendet werden soll.
2. Protokoll prüfen (Einstellungen → System → Protokolle, Filter `pm_heizung`): Meldungen wie
   „Senden an … fehlgeschlagen“ nennen die Ursache; PM Klima wiederholt mit Wartezeit.
3. Rundet das Gerät auf eigene Stufen (z. B. ganze Grad), akzeptiert PM Klima den gerundeten
   Wert nach der Rückmeldung – kein Endlos-Senden.
4. Diagnosedaten des Raumgeräts herunterladen: `backends` zeigt je Thermostat Heizmodus,
   „kann aus“, zuletzt gesendeten Wert und Typ.

### Das Thermostat springt immer wieder auf „aus“.

Etwas anderes schaltet parallel – meist Geofencing, ein Zeitplan oder die Fenstererkennung der
Hersteller-App. Nach drei Rückstellungen in 30 Minuten hält PM Klima inne (5 → 60 min) und meldet
unter Reparaturen „Thermostat in <Raum> wird wiederholt ausgeschaltet“. Die Hersteller-Logik
abschalten oder – bei tado ohne Fenstersensor – „Externes Aus als Fensteröffnung werten“ aktivieren.

### Warum heizt ein Raum nicht, obwohl der Zeitplan läuft?

`sensor.pm_<raum>_grund` nennt die wirksame Stufe: `fenster`, `sperre` (Außentemperatur oder
Sommerschalter), `abwesenheit`, `aus`, `pausiert` (Hauptschalter aus) … Die Reihenfolge steht in
[Funktionsweise](funktionsweise.md#wie-wird-die-solltemperatur-bestimmt-priorität-von-oben-nach-unten).

### Kann ich die tado-Integration löschen?

Nur, wenn die Thermostate anders angebunden sind (HomeKit Device oder Matter). PM Klima selbst
braucht die tado-Cloud nicht. Vorgehen: [Umstieg tado → lokal](umstieg-tado-lokal.md).

### Mein Thermostat hat keinen Modus „aus“.

Kein Problem: Statt „aus“ sendet PM Klima die niedrigste Solltemperatur des Geräts.

### Die Texte sind auf Englisch (oder Deutsch), ich möchte die andere Sprache.

Zentrale → Konfigurieren → Schritt 1 → *Sprache der Texte*. Die Oberfläche selbst folgt der
Profilsprache in Home Assistant.

### Die Beratung meldet sich nicht.

* Schalter `switch.pm_klima_beratung` ist standardmäßig **aus**.
* Push geht nur an Personen, die zuhause sind und in der Zuordnung stehen.
* Sprachansage und Wanddisplay brauchen ein eingetragenes Skript bzw. einen Dienst.
* Ruhezeit, Stummschalter, 5 min Mindestdauer und 120 min Abstand je Thema beachten.
* Test: `pm_heizung.beratung_testen` mit `kanal: push`.

### Kann PM Klima kühlen?

Nein. PM Klima ist eine Heizungssteuerung; Klimageräte im Kühlbetrieb werden nicht unterstützt.

### Die Integration zeigt kein Symbol, nur einen Platzhalter.

PM Klima bringt sein Symbol selbst mit (`custom_components/pm_heizung/brand/`). Home Assistant
zeigt diese lokalen Bilder ab Version 2026.3; ältere Versionen zeigen einen Platzhalter. Auf die
Funktion hat das keinen Einfluss.

### Wie melde ich einen Fehler?

Über [GitHub Issues](https://github.com/D0GC/HA-PM-Networks-Klima/issues/new/choose) – bitte mit
Home-Assistant-Version, Thermostat-Integration, Diagnosedaten des Raumgeräts und einem
Protokollauszug.
