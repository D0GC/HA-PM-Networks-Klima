"""Übersetzungen: de/en/strings haben identische Schlüssel, Dienste sind beschrieben."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

BASE = Path(__file__).parents[1] / "custom_components" / "pm_heizung"


def _keys(d: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for k, v in d.items():
        out.add(prefix + k)
        if isinstance(v, dict):
            out |= _keys(v, prefix + k + ".")
    return out


def test_translation_keys_match() -> None:
    """strings.json, en.json und de.json sind strukturgleich."""
    strings = json.loads((BASE / "strings.json").read_text(encoding="utf-8"))
    en = json.loads((BASE / "translations" / "en.json").read_text(encoding="utf-8"))
    de = json.loads((BASE / "translations" / "de.json").read_text(encoding="utf-8"))
    assert _keys(strings) == _keys(en) == _keys(de)


def test_services_translated() -> None:
    """Jeder Dienst und jedes Feld aus services.yaml ist übersetzt."""
    services = yaml.safe_load((BASE / "services.yaml").read_text(encoding="utf-8"))
    de = json.loads((BASE / "translations" / "de.json").read_text(encoding="utf-8"))
    for name, spec in services.items():
        assert name in de["services"]
        for field in (spec or {}).get("fields", {}):
            assert field in de["services"][name]["fields"]


def test_manifest() -> None:
    """Manifest-Pflichtfelder."""
    manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2.1.0"
    assert manifest["documentation"].startswith("https://github.com/D0GC/")
    assert manifest["name"] == "PM Klima"
    assert manifest["domain"] == "pm_heizung"
    assert manifest["iot_class"] == "calculated"
    assert manifest["config_flow"] is True
    assert manifest["dependencies"] == []
    assert manifest["codeowners"]


def test_no_icu_tags_in_translations() -> None:
    """„<…>“ gilt im Frontend als ICU-Tag (Anzeige „Translation error: UNCLOSED_TAG“)."""

    for path in (BASE / "translations").glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "<" not in text, path.name


def test_no_quoted_placeholders() -> None:
    """hassfest: Platzhalter nicht in einfache Anführungszeichen setzen."""
    import re

    for path in (BASE / "translations").glob("*.json"):
        assert not re.search(r"'\{[a-z_]+\}'", path.read_text(encoding="utf-8")), path.name
