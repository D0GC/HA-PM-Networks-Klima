# Mitwirken

Beiträge sind willkommen – Fehlerberichte, Erfahrungen mit weiteren Thermostaten, Übersetzungen
und Code.

## Fehler melden

Bitte die [Issue-Vorlage](https://github.com/D0GC/HA-PM-Networks-Klima/issues/new/choose) nutzen
und angeben: Home-Assistant-Version, PM-Klima-Version, Thermostat-Integration, Diagnosedaten des
betroffenen Raumgeräts (Gerät → „Diagnosedaten herunterladen“) und einen Protokollauszug
(`logger: logs: custom_components.pm_heizung: debug`).

## Entwicklung

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
ruff check . && ruff format --check .
python -m pytest -q
```

* **Tests:** jede Verhaltensänderung mit Test (`tests/`); die Suite läuft gegen eine echte
  Home-Assistant-Instanz (`pytest-homeassistant-custom-component`).
* **Übersetzungen:** nicht `strings.json`/`translations/*.json` von Hand bearbeiten, sondern
  `tools/gen_translations.py` anpassen und ausführen. Kein `<` in Texten (ICU-Tags).
* **Laufzeittexte** (Anzeige, Empfehlungen): `sprache.py`; Meldungstexte der Beratung:
  `beratung_texte.py` – je Thema und Sprache zehn Varianten.
* **Konfiguration:** neue Optionen additiv, bei geändertem Verhalten Migration in `__init__.py`
  (Schema-Nebenversion erhöhen) und Test in `tests/test_migration.py`.
* **Stil:** ruff (Konfiguration in `pyproject.toml`), Kommentare und Docstrings auf Deutsch.

## Pull Requests

Kleine, fokussierte PRs mit Beschreibung *was* und *warum*. Die CI prüft Lint, Tests, aktuelle
Übersetzungen, `hassfest` und die HACS-Validierung.
