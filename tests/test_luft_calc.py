"""Modul Luft – Rechenlogik mit Referenzwerten (Magnus, Taupunkt, Schimmel, Lüften)."""

from __future__ import annotations

import pytest

from custom_components.pm_heizung.luft_calc import (
    AirInputs,
    absolute_humidity,
    dew_point,
    evaluate_air,
    minutes_word,
    mold_level,
    room_phrase,
    saturation_vapor_pressure,
    vent_duration,
    wall_humidity,
    wall_temperature,
)


@pytest.mark.parametrize(
    ("temp", "expected"),
    [(0.0, 6.112), (10.0, 12.27), (20.0, 23.37), (30.0, 42.43)],
)
def test_saturation_vapor_pressure(temp: float, expected: float) -> None:
    """Magnus (DWD-Koeffizienten) – Tabellenwerte über Wasser, ±0,1 hPa."""
    assert saturation_vapor_pressure(temp) == pytest.approx(expected, abs=0.1)


@pytest.mark.parametrize(
    ("temp", "rel", "expected"),
    [
        (20.0, 50.0, 8.64),  # Klassiker: 20 °C / 50 % ≈ 8,6 g/m³
        (20.0, 100.0, 17.28),
        (0.0, 80.0, 3.88),
        (5.0, 80.0, 5.44),
        (22.0, 60.0, 11.64),
    ],
)
def test_absolute_humidity(temp: float, rel: float, expected: float) -> None:
    """Absolute Feuchte in g/m³, ±0,05."""
    assert absolute_humidity(temp, rel) == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize(
    ("temp", "rel", "expected"),
    [(20.0, 50.0, 9.3), (20.0, 65.0, 13.2), (22.0, 60.0, 13.9), (10.0, 100.0, 10.0)],
)
def test_dew_point(temp: float, rel: float, expected: float) -> None:
    """Taupunkt, ±0,1 K."""
    assert dew_point(temp, rel) == pytest.approx(expected, abs=0.1)


def test_wall_temperature_and_humidity() -> None:
    """θsi = θi − (θi − θe)·(1 − fRsi); Feuchte an der Wand bei gleichem Dampfdruck."""
    assert wall_temperature(20.0, 0.0, 0.7) == pytest.approx(14.0)
    assert wall_temperature(20.0, -10.0, 0.7) == pytest.approx(11.0)
    assert wall_temperature(20.0, 10.0, 0.7) == pytest.approx(17.0)
    # 20 °C / 50 % innen, Wand 14 °C -> ≈ 73 % (Warnung)
    assert wall_humidity(20.0, 50.0, 14.0) == pytest.approx(73.1, abs=0.3)
    assert mold_level(wall_humidity(20.0, 50.0, 14.0)) == "warnung"
    # 20 °C / 60 % bei 0 °C außen -> ≈ 88 % (Risiko)
    assert wall_humidity(20.0, 60.0, 14.0) == pytest.approx(87.7, abs=0.3)
    assert mold_level(87.7) == "risiko"
    # milde Außentemperatur -> gering
    assert mold_level(wall_humidity(20.0, 50.0, 17.0)) == "gering"
    # an der Taupunkttemperatur 100 %
    assert wall_humidity(20.0, 50.0, dew_point(20.0, 50.0)) == pytest.approx(100.0, abs=0.2)
    assert wall_humidity(20.0, 80.0, 5.0) == 100.0  # gedeckelt
    assert mold_level(None) is None
    assert mold_level(80.0) == "warnung"
    assert mold_level(70.0) == "gering"


@pytest.mark.parametrize(
    ("outdoor", "minutes"),
    [
        (-5.0, 5),
        (-0.1, 5),
        (0.0, 10),
        (9.9, 10),
        (10.0, 15),
        (14.9, 15),
        (15.0, 25),
        (28, 25),
        (None, 10),
    ],
)
def test_vent_duration(outdoor: float | None, minutes: int) -> None:
    """<0 °C 5 min, 0–10 °C 10 min, 10–15 °C 15 min, >15 °C 20–30 min (25)."""
    assert vent_duration(outdoor) == minutes


def test_ventilation_needed_and_sensible() -> None:
    """Feuchte über Grenze + draußen deutlich trockener -> empfohlen."""
    base = {"t_in": 21.0, "t_out": 5.0, "rh_out": 80.0, "humidity_limit": 65.0}
    res = evaluate_air(AirInputs(rh_in=50.0, **base))
    assert res.sensible is True  # 9,1 g/m³ innen vs 5,4 außen
    assert res.mold == "gering"  # Wand 16,2 °C -> 67 %
    assert res.needed is False
    assert res.recommended is False
    res = evaluate_air(AirInputs(rh_in=70.0, **base))
    assert res.needed and res.humidity_reason
    assert res.recommended is True
    assert res.duration == 10
    # Regen: Feuchte-Lüften nicht sinnvoll
    res = evaluate_air(AirInputs(rh_in=70.0, raining=True, **base))
    assert res.sensible is False
    assert res.recommended is False
    # CO2 ist auch bei Regen ein Grund
    res = evaluate_air(AirInputs(rh_in=50.0, co2=1200, raining=True, **base))
    assert res.co2_reason and res.recommended
    # Fenster bereits offen -> keine Empfehlung
    res = evaluate_air(AirInputs(rh_in=70.0, window_open=True, **base))
    assert res.recommended is False
    # draußen feucht-warm (Sommer): Lüften bringt nichts
    res = evaluate_air(
        AirInputs(t_in=22.0, rh_in=70.0, t_out=26.0, rh_out=80.0, humidity_limit=65.0)
    )
    assert res.sensible is False and res.recommended is False
    # ohne Außenfeuchte: Feuchte-Empfehlung unbestimmt -> nicht empfohlen
    res = evaluate_air(AirInputs(t_in=21.0, rh_in=70.0, t_out=5.0))
    assert res.sensible is None and res.recommended is False


def test_mold_warning_is_display_only() -> None:
    """Review 2.0.1: 20 °C/50 %/−5 °C außen (fRsi 0,75) -> Wand ≈ 74 % = Warnung, kein Lüften."""
    res = evaluate_air(
        AirInputs(t_in=20.0, rh_in=50.0, t_out=-5.0, rh_out=80.0, humidity_limit=65.0)
    )
    assert res.wall_temp == 13.8
    assert res.wall_rh == pytest.approx(74.3, abs=0.2)
    assert res.mold == "warnung"
    assert res.humidity_reason is False
    assert res.needed is False and res.recommended is False
    assert res.quality == "mittel"  # nur Anzeige


def test_mold_risk_is_ventilation_reason() -> None:
    """Wandfeuchte > 80 % (Risiko) macht Lüften nötig, auch unter der Raumgrenze."""
    res = evaluate_air(
        AirInputs(t_in=20.0, rh_in=55.0, t_out=-5.0, rh_out=80.0, humidity_limit=65.0)
    )
    assert res.wall_rh is not None and res.wall_rh > 80
    assert res.mold == "risiko"
    assert res.humidity_reason and res.recommended
    assert res.duration == 5


def test_default_frsi() -> None:
    """Standard-fRsi ist 0,75."""
    from custom_components.pm_heizung.const import DEFAULT_FRSI

    assert DEFAULT_FRSI == 0.75
    assert AirInputs().frsi == 0.75


def test_too_dry_and_quality_index() -> None:
    """Qualitätsindex gut/mittel/schlecht mit Begründungen."""
    good = evaluate_air(AirInputs(t_in=21.0, rh_in=45.0, t_out=12.0, co2=600, pm25=4))
    assert good.quality == "gut"
    mid = evaluate_air(AirInputs(t_in=21.0, rh_in=45.0, co2=1100, pm25=4))
    assert mid.quality == "mittel"
    assert any("CO₂" in r for r in mid.quality_reasons)
    bad = evaluate_air(AirInputs(t_in=21.0, rh_in=45.0, co2=600, pm25=40))
    assert bad.quality == "schlecht"
    assert bad.quality_reasons[0].startswith("Feinstaub hoch")
    dry = evaluate_air(AirInputs(t_in=22.0, rh_in=32.0))
    assert dry.too_dry and dry.quality == "mittel"
    very_dry = evaluate_air(AirInputs(t_in=22.0, rh_in=28.0))
    assert very_dry.quality == "schlecht"
    assert evaluate_air(AirInputs(t_in=21.0)).quality is None


def test_window_close_due() -> None:
    """Erinnerung nach empfohlener Dauer + 5 min Karenz, nur in der Heizperiode."""
    kw = {"t_in": 21.0, "rh_in": 50.0, "window_open": True, "t_out": 5.0}
    assert evaluate_air(AirInputs(window_open_minutes=14.0, **kw)).window_close_due is False
    assert evaluate_air(AirInputs(window_open_minutes=16.0, **kw)).window_close_due is True
    kw["t_out"] = 18.0
    assert evaluate_air(AirInputs(window_open_minutes=60.0, **kw)).window_close_due is False


def test_words() -> None:
    """Gesprochene Minuten und Raumbezug."""
    assert minutes_word(10) == "zehn Minuten"
    assert minutes_word(1) == "eine Minute"
    assert minutes_word(37) == "37 Minuten"
    assert room_phrase("Küche") == "in der Küche"
    assert room_phrase("Badezimmer") == "im Badezimmer"
