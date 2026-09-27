"""Reine Rechenlogik (nur dt_util aus Home Assistant für Zeitzonen).

Portierung der Abwesenheits-/Vorheizlogik aus dem Blueprint
"Abwesenheit & Vorheizen (Proximity, tado-Stil)".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import math

from homeassistant.util import dt as dt_util

from .const import (
    PHASES,
    PREHEAT_BALANCE,
    PREHEAT_CUSTOM,
    PREHEAT_RADII,
)

FAR_AWAY_M = 1_000_000_000.0
UNIT_FACTORS: dict[str, float] = {
    "m": 1.0,
    "km": 1000.0,
    "mi": 1609.344,
    "ft": 0.3048,
    "yd": 0.9144,
}
RANK_FAR = 0
RANK_HOLD = 1
RANK_BETWEEN = 2
RANK_COMFORT = 3
RANK_HOME = 4


def round_half(value: float) -> float:
    """Auf 0,5 runden (kaufmännisch)."""
    return math.floor(value * 2 + 0.5) / 2


def ceil_half(value: float) -> float:
    """Auf 0,5 aufrunden."""
    return math.ceil(value * 2 - 1e-9) / 2


def round_step(value: float, step: float) -> float:
    """Auf das Raster des Thermostats runden (kaufmännisch)."""
    if step <= 0:
        return value
    return round(math.floor(value / step + 0.5) * step, 2)


def clamp(value: float, low: float, high: float) -> float:
    """Wert auf [low, high] begrenzen (low gewinnt bei low > high)."""
    return max(low, min(high, value))


def radii_for(
    level: str, near_km: float, mid_km: float, far_km: float
) -> tuple[float, float, float]:
    """Radien [nah, mittel, fern] in Metern, monoton erzwungen."""
    if level == PREHEAT_CUSTOM:
        near = float(near_km) * 1000
        mid = max(near, float(mid_km) * 1000)
        far = max(mid, float(far_km) * 1000)
        return (near, mid, far)
    return PREHEAT_RADII.get(level, PREHEAT_RADII[PREHEAT_BALANCE])


def distance_to_m(state: str | None, unit: str | None) -> float:
    """Abstand in Meter; unbekannt = sehr weit weg."""
    try:
        value = float(state)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return FAR_AWAY_M
    if math.isnan(value):
        return FAR_AWAY_M
    return value * UNIT_FACTORS.get((unit or "m").lower(), 1.0)


def _rank_for_distance(dist: float, radii: tuple[float, float, float]) -> int:
    near, mid, far = radii
    if near > 0 and dist <= near:
        return RANK_COMFORT
    if mid > 0 and dist <= mid:
        return RANK_BETWEEN
    if dist <= far:
        return RANK_HOLD
    return RANK_FAR


@dataclass(frozen=True, slots=True)
class RankResult:
    """Ergebnis der Stufenberechnung (ohne Anwesenheit)."""

    direction_rank: int
    distance_rank: int
    away_from: bool
    rank: int


def compute_away_rank(
    distances_m: Sequence[float],
    directions: Sequence[str],
    radii: tuple[float, float, float],
    approach_required: bool,
    last_rank: int,
) -> RankResult:
    """Stufe berechnen, wenn niemand zuhause ist (Blueprint-Logik inkl. Hysterese).

    last_rank: zuletzt angewandte Stufe (-1 = keine).
    """
    has_direction = len(directions) > 0
    paired = has_direction and len(directions) == len(distances_m)
    pairs: list[tuple[float, str]]
    if paired:
        pairs = list(zip(distances_m, directions, strict=True))
    elif has_direction:
        pairs = [
            (
                min(distances_m) if distances_m else FAR_AWAY_M,
                "towards" if "towards" in directions else "sonst",
            )
        ]
    else:
        pairs = [(d, "towards") for d in distances_m]

    dir_rank = RANK_FAR
    dist_rank = RANK_FAR
    for dist, direction in pairs:
        by_distance = _rank_for_distance(dist, radii)
        if not approach_required or not has_direction or direction in ("towards", "arrived"):
            by_direction = by_distance
        else:
            by_direction = min(by_distance, RANK_HOLD)
        dir_rank = max(dir_rank, by_direction)
        dist_rank = max(dist_rank, by_distance)

    away_from = "away_from" in directions
    rank = dir_rank
    if approach_required and has_direction and not away_from:
        # Stufe halten, solange niemand away_from meldet und die Person
        # noch im Radius dieser Stufe ist (Stau/Ampel kühlt nicht ab).
        rank = max(rank, min(last_rank, dist_rank))
    return RankResult(dir_rank, dist_rank, away_from, rank)


def phase_name(rank: int) -> str:
    """Rang -> Phasenname."""
    return PHASES[max(0, min(RANK_HOME, rank))]


def away_temperature(  # noqa: PLR0917
    phase: str,
    base: float,
    reference: float,
    setback: float,
    min_away: float,
    far_setback: float,
) -> float:
    """Zieltemperatur einer Abwesenheitsphase.

    base:      aktuell gültige Zeitplantemperatur des Raums
    reference: Komforttemperatur des Raums (Bezug wie im Blueprint)
    Ergebnis liegt nie über der Zeitplantemperatur.
    """
    hold = clamp(round_half(reference - setback), min_away, reference)
    far = clamp(round_half(reference - setback - far_setback), min_away, reference)
    between = clamp(ceil_half((hold + reference) / 2), min_away, reference)
    value = {
        "fern": far,
        "halten": hold,
        "zwischen": between,
        "komfort": base,
        "zuhause": base,
    }.get(phase, base)
    return min(value, base)


_WEEKDAYS = {
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}


def fmt_number(value: float, decimals: int = 1, lang: str = "de") -> str:
    """Zahl formatieren (de: 21 / 19,5 – en: 21 / 19.5), ohne überflüssige Nachkommastelle."""
    rounded = round(float(value), decimals)
    if rounded == int(rounded):
        return str(int(rounded))
    text = f"{rounded:.{decimals}f}".rstrip("0")
    return text if lang == "en" else text.replace(".", ",")


def fmt_temp(value: float | None, lang: str = "de") -> str:
    """Temperatur als „21 °C“ bzw. „19,5 °C“ (en: „19.5 °C“)."""
    if value is None:
        return "–"
    return f"{fmt_number(value, lang=lang)} °C"


def fmt_time(when: datetime, now: datetime, lang: str = "de") -> str:
    """Uhrzeit (lokal) „22:30“, an anderen Tagen „Mo 06:00“ bzw. „27.09. 06:00“."""
    local = dt_util.as_local(when)
    today = dt_util.as_local(now).date()
    clock = local.strftime("%H:%M")
    days = (local.date() - today).days
    if days == 0:
        return clock
    weekdays = _WEEKDAYS.get(lang, _WEEKDAYS["de"])
    if 0 < days < 7:
        return f"{weekdays[local.weekday()]} {clock}"
    if lang == "en":
        return f"{local.strftime('%d/%m')} {clock}"
    return f"{local.strftime('%d.%m.')} {clock}"
