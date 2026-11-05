"""Veröffentlichung über HACS: Lizenz, Symbole der Integration, hacs.json."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
import pytest

ROOT = Path(__file__).parents[1]
BRAND = ROOT / "custom_components" / "pm_heizung" / "brand"


def test_license() -> None:
    """LICENSE liegt im Repository-Root und ist die MIT-Lizenz."""
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text


@pytest.mark.parametrize(
    ("name", "size"),
    [
        ("icon.png", 256),
        ("icon@2x.png", 512),
        ("dark_icon.png", 256),
        ("dark_icon@2x.png", 512),
    ],
)
def test_brand_icons(name: str, size: int) -> None:
    """Symbole sind quadratische PNGs in der richtigen Größe mit Transparenz."""
    path = BRAND / name
    assert path.is_file()
    with Image.open(path) as img:
        assert img.format == "PNG"
        assert img.size == (size, size)
        assert img.mode == "RGBA"
        alpha_min, alpha_max = img.getchannel("A").getextrema()
        assert alpha_min == 0
        assert alpha_max == 255


def test_hacs_json() -> None:
    """hacs.json nennt Name und Mindestversion von Home Assistant."""
    data = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert data["name"] == "PM Klima"
    assert data["homeassistant"] == "2026.2.0"
    assert data["render_readme"] is True
