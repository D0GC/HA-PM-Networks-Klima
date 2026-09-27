# Umstieg: tado-Cloud-Integration → lokale Anbindung

[← Zurück zur Übersicht](../README.md) · [Thermostate & Anbindung](thermostate.md)

Diese Anleitung beschreibt, wie tado-Thermostate ohne die tado-Web-API an PM Klima angebunden
werden, sodass die tado-Integration von Home Assistant entfallen kann.

## Warum?

Die Home-Assistant-Integration **tado** spricht die Cloud-API von tado an. Jede Abfrage und jeder
Befehl zählt gegen ein tägliches Anfragekontingent, und ohne Internet ist keine Steuerung
möglich. PM Klima selbst hat **keine** tado-Schnittstelle: Es sendet nur
`climate.set_temperature`/`set_hvac_mode` an die konfigurierten `climate`-Entitäten. Ersetzt man
diese Entitäten durch lokale, entfällt die Cloud-Abhängigkeit – Zeitpläne, Einstellungen und
Zustände von PM Klima bleiben erhalten.

| Hardware | Lokaler Weg in Home Assistant |
|---|---|
| tado V3+ (Internet-Bridge `IB01`, Heizkörperthermostate, Smart Thermostat) | **HomeKit Device** (`homekit_controller`) über die Bridge |
| tado X (Bridge X, Thread) | **Matter** |
| ältere Generationen ohne HomeKit | kein lokaler Weg – Cloud-Integration beibehalten |

PM Klima erkennt beide lokalen Wege als Gerätetyp `tado_lokal` (Attribut `thermostat_typ`).

## Schritte (tado V3+ über HomeKit)

### 1. HomeKit Device koppeln – tado-Integration bleibt vorerst

1. Einstellungen → Geräte & Dienste. Die Bridge erscheint meist unter *Entdeckt* als
   *HomeKit Device*; sonst Integration hinzufügen → **HomeKit Device**.
2. HomeKit-Code eingeben (Aufkleber auf der Bridge; wird auch in der tado-App angezeigt).
3. Ein HomeKit-Zubehör kann nur mit **einer** Steuerzentrale gekoppelt sein. Ist die Bridge in
   Apple Home eingebunden, dort zuerst entfernen. Apple Home kann die Geräte später über die
   *HomeKit Bridge* von Home Assistant wieder erhalten.

### 2. Neue Entitäten prüfen

Je Raum entsteht eine neue `climate`-Entität. Bitte kontrollieren:

* `hvac_modes` – PM Klima verwendet `heat` und `off`; der tado-Zeitplan (`auto` bzw.
  `heat_cool`) wird wie bisher überschrieben.
* Luftfeuchte – kommt sie über HomeKit nicht mit, im Raum einen anderen Feuchtesensor eintragen.
* Ein Probe-Sollwert direkt an der HomeKit-Entität kommt am Thermostat an.

### 3. Abhängigkeiten prüfen

```yaml
action: pm_heizung.abhaengigkeiten
```

Unter `tado_cloud` stehen alle Entitäten aus der tado-Integration, die PM Klima noch verwendet –
typischerweise die Thermostate und die Feuchtesensoren der Räume. Außerhalb von PM Klima hilft
Einstellungen → Entitäten → Entität öffnen → **Verwendet in**, um Automationen, Skripte, Helfer
und Dashboards zu finden.

### 4. Umstellen

**Empfohlen – Entitäts-IDs übernehmen** (Automationen und Dashboards bleiben unverändert):

1. `switch.pm_heizung_aktiv` ausschalten – PM Klima sendet nichts.
2. tado-Integration löschen (Einstellungen → Geräte & Dienste → tado → ⋮ → Löschen).
3. Die HomeKit-Entitäten auf die bisherigen IDs umbenennen (z. B. `climate.wohnzimmer`,
   `sensor.wohnzimmer_luftfeuchtigkeit`).
4. `pm_heizung.reevaluate` aufrufen, `switch.pm_heizung_aktiv` einschalten.

**Alternative – PM Klima umstellen, IDs der HomeKit-Entitäten behalten:**

```yaml
action: pm_heizung.entitaet_ersetzen
data:
  alt: climate.wohnzimmer
  neu: climate.wohnzimmer_2
```

Automationen und Dashboards außerhalb von PM Klima müssen dann von Hand angepasst werden.

### 5. Kontrolle

* `climate.pm_<raum>` → Attribut `thermostat_typ` = `tado_lokal`
* `pm_heizung.abhaengigkeiten` → `tado_integration_entbehrlich: true`
* Einstellungen → Reparaturen: kein Hinweis „Thermostat für <Raum> nicht gefunden“

## Was ohne die tado-Integration entfällt

Soweit HomeKit sie nicht selbst liefert: Batteriestand und Verbindungszustand der Thermostate,
Heizleistung in Prozent, „Früher Start“, Overlay-Anzeige, tado-Modus- und Geofencing-Sensoren,
Kindersicherungs-Schalter, tado-Außentemperatur und -Wetter, Temperatur-Offset. Die tado-App
funktioniert weiter; Kindersicherung und Offset werden dann dort eingestellt.

## Empfohlene Einstellungen in der tado-App

* Geofencing / Auto-Assist-Abwesenheit: **aus** (PM Klima übernimmt Abwesenheit und Vorheizen).
* Manuelle Steuerung: **„Bis du es aufhebst“** – sonst springt tado auf den eigenen Zeitplan zurück.
* Fenster-offen-Erkennung: darf an bleiben. In Räumen ohne Fenstersensor wertet PM Klima das
  „aus“ als Fensteröffnung (Option „Externes Aus als Fensteröffnung werten“).
