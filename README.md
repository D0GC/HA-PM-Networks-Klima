<p align="center">
  <img src="docs/bilder/banner.png" alt="PM Klima – Heizung, Luft &amp; Beratung für Home Assistant" width="100%">
</p>

<p align="center">
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Integration-41BDF5.svg" alt="HACS Integration"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.2%2B-18BCF2.svg" alt="Home Assistant 2026.2+">
  <img src="https://img.shields.io/badge/Version-2.1.0-784295.svg" alt="Version 2.1.0">
  <a href="https://github.com/D0GC/HA-PM-Networks-Klima/actions/workflows/ci.yml"><img src="https://github.com/D0GC/HA-PM-Networks-Klima/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Sprache-Deutsch%20%7C%20English-443171.svg" alt="Deutsch | English">
  <a href="LICENSE"><img src="https://img.shields.io/badge/Lizenz-MIT-191537.svg" alt="Lizenz: MIT"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=D0GC&amp;repository=HA-PM-Networks-Klima&amp;category=integration"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store."></a>
</p>

# PM Klima

**Eine komplette Heizungssteuerung für Home Assistant – lokal, ohne Cloud und für jedes
Thermostat.** Zeitpläne mit Blocktemperaturen, manuelle Overlays, Abwesenheit und Vorheizen per
Geofencing, Fenstererkennung, Boost und Sommerbetrieb. Dazu ein Luftmodul mit Schimmelrisiko und
Lüftempfehlung sowie eine Beratung, die sich zurückhaltend per Push, Sprachansage oder Wanddisplay
meldet.

![Beispiel-Dashboard](docs/bilder/dashboard.png)

## Warum PM Klima?

| | |
|---|---|
| **Ein Raum, ein Thermostat-Objekt** | `climate.pm_<raum>` mit Modi *auto / heat / off* und Presets *zeitplan, manuell, komfort, eco, abwesend, frostschutz, boost*. |
| **Zeitpläne wie in der Hersteller-App** | Helfer *Zeitplan* mit eigener Temperatur je Block; manuelle Änderungen gelten bis zum nächsten Wechsel, für X Minuten oder dauerhaft. |
| **Geofencing & Vorheizen** | Absenkung, wenn niemand zuhause ist; Vorheizen in Stufen, wenn sich jemand nähert (Proximity). |
| **Fenster, Boost, Sommer** | Frostschutz bei offenem Fenster, Boost auf Knopfdruck, Sperre ab Außentemperatur oder per Sommerschalter. |
| **Erklärt sich selbst** | Attribut `anzeige` im Klartext: „Zeitplan · 21,5 °C bis 23:00“, „Fenster offen · Frostschutz (danach 21 °C)“. |
| **Luft** | Absolute Feuchte, Taupunkt, Schimmelrisiko an der kältesten Wandstelle, Lüftempfehlung und -dauer, Luftreiniger-Automatik. |
| **Beratung** | Gedrosselte Empfehlungen mit Ruhezeit und Stummschaltern; zehn Textvarianten je Thema, Deutsch und Englisch. |
| **Jedes Thermostat** | Zigbee, Homematic, FRITZ!DECT, Netatmo, HomeKit, Matter, tado, `generic_thermostat` – PM Klima nutzt nur Standarddienste. |
| **Lokal** | Keine Cloud, keine Abhängigkeiten. Umstieg von einer Cloud-Anbindung (z. B. tado) ohne Neueinrichtung. |

## Schnellstart

1. **Installieren** – am einfachsten über den Button *Open in HACS* oben: *PM Klima*
   herunterladen → Home Assistant neu starten. Alternativ HACS → ⋮ → Benutzerdefinierte
   Repositories → `https://github.com/D0GC/HA-PM-Networks-Klima` (Integration).
   ([Details](docs/installation.md))
2. **Zentrale einrichten** – Einstellungen → Geräte & Dienste → Integration hinzufügen →
   *PM Klima*: Personen, Abwesenheit, Sperre, Luft, Beratung. ([Details](docs/einrichtung.md#teil-1-zentrale))
3. **Räume anlegen** – *Raum hinzufügen*: Thermostat(e), Sensoren, Fenster, Zeitplan,
   Temperaturen. ([Details](docs/einrichtung.md#teil-2-räume))
4. **Hersteller-Logik abschalten** – Zeitpläne und Geofencing in der Hersteller-App aus.
5. **Dashboard** – [Beispiel](docs/dashboard.md) übernehmen und mit einem Raum beginnen.

<table>
  <tr>
    <td width="50%"><img src="docs/bilder/integration.png" alt="Integrationsseite"><br><sub>Zentrale und Räume als Untereinträge</sub></td>
    <td width="50%"><img src="docs/bilder/thermostat_dialog.png" alt="Raumthermostat"><br><sub>Raumthermostat mit Presets</sub></td>
  </tr>
  <tr>
    <td><img src="docs/bilder/raum_1_geraete.png" alt="Raum einrichten"><br><sub>Raum einrichten – Geräte</sub></td>
    <td><img src="docs/bilder/zentrale_2_abwesenheit.png" alt="Abwesenheit und Vorheizen"><br><sub>Abwesenheit & Vorheizen</sub></td>
  </tr>
</table>

## Dokumentation

| Seite | Inhalt |
|---|---|
| [Installation](docs/installation.md) | HACS, manuell, Update, Deinstallation |
| [Einrichtung](docs/einrichtung.md) | Zentrale und Räume Schritt für Schritt – mit Screenshots jedes Dialogs |
| [Funktionsweise](docs/funktionsweise.md) | Prioritäten, Overlays, Presets, Abwesenheitsphasen, externes „aus“, Grenzen |
| [Thermostate & Anbindung](docs/thermostate.md) | Welche Geräte, wie sie angesprochen werden, Thermostat wechseln |
| [Umstieg tado → lokal](docs/umstieg-tado-lokal.md) | tado ohne Web-API über HomeKit oder Matter |
| [Luft & Beratung](docs/luft-und-beratung.md) | Formeln, Lüftempfehlung, Luftreiniger, Kanäle und Regeln der Beratung |
| [Entitäten & Dienste](docs/entitaeten-und-dienste.md) | Alle Entitäten und Attribute, Dienste, Automationsbeispiele |
| [Dashboard](docs/dashboard.md) | Beispiel-Dashboard mit Standardkarten |
| [FAQ & Fehlersuche](docs/faq.md) | Häufige Fragen und Lösungen |
| [Changelog](CHANGELOG.md) · [Mitwirken](CONTRIBUTING.md) | Versionen, Entwicklung, Tests |

## In English

PM Klima is a complete, **local** heating controller for Home Assistant that works with **any
thermostat** exposed as a `climate` entity: schedules with per-block temperatures, manual
overlays, away/preheat via proximity, window detection, boost and a summer lock – plus an air
module (absolute humidity, dew point, mould risk, ventilation advice, purifier automation) and an
advice module (push, voice announcements, wall display). The user interface is available in
German and English; runtime texts (display text, recommendations, messages) follow the option
*Language of generated texts* (automatic = Home Assistant language).

![Dashboard with English runtime texts](docs/bilder/dashboard_en.png)

Install via HACS as a custom repository (category *Integration*), restart Home Assistant and add
*PM Klima* under Settings → Devices & services. The detailed documentation is written in German;
the screenshots and YAML examples are language-independent.

---

<sub>PM Klima ist ein Projekt von PM Networks und steht in keiner Verbindung zu tado GmbH oder zu
anderen Herstellern. Alle Screenshots stammen aus einer Demo-Instanz mit Beispieldaten.</sub>
