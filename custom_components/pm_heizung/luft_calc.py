"""Modul „Luft“ – reine Berechnungen (ohne Home-Assistant-Abhängigkeiten).

Formeln:
* Sättigungsdampfdruck nach Magnus (über Wasser, DWD-Koeffizienten)
  E(T) = 6,112 hPa · exp(17,62 · T / (243,12 + T))
* absolute Feuchte  ρw = 216,7 · (φ · E(T)) / (273,15 + T)   [g/m³]
* Taupunkt          Td = 243,12 · α / (17,62 − α),  α = ln(φ) + 17,62 · T / (243,12 + T)
* Wandoberfläche    θsi = θi − (θi − θe) · (1 − fRsi)   (DIN 4108-2: fRsi 0,70 = Mindestwert; Standard hier 0,75)
* rel. Feuchte an der Wand  φsi = φi · E(θi) / E(θsi)   (Dampfdruck bleibt gleich)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from .const import (
    ABS_HUMIDITY_MARGIN,
    CO2_BAD,
    CO2_WARN,
    HUMIDITY_BAD,
    HUMIDITY_DRY,
    HUMIDITY_VERY_DRY,
    MOLD_LEVEL_RISK,
    MOLD_LEVEL_WARN,
    MOLD_LOW,
    MOLD_RISK,
    MOLD_WARN,
    PM25_HIGH,
    PM25_MID,
    QUALITY_BAD,
    QUALITY_GOOD,
    QUALITY_MID,
    WINDOW_REMIND_GRACE_MIN,
)
from .sprache import t

MAGNUS_A = 17.62
MAGNUS_B = 243.12  # °C
MAGNUS_E0 = 6.112  # hPa
HEATING_SEASON_OUTDOOR = 15.0  # °C – darüber keine Fenster-zu-Erinnerung (außer Regen)


def saturation_vapor_pressure(temp: float) -> float:
    """Sättigungsdampfdruck in hPa (Magnus, über Wasser)."""
    return MAGNUS_E0 * math.exp(MAGNUS_A * temp / (MAGNUS_B + temp))


def absolute_humidity(temp: float, rel: float) -> float:
    """Absolute Feuchte in g/m³."""
    vapor = rel / 100.0 * saturation_vapor_pressure(temp)
    return 216.7 * vapor / (273.15 + temp)


def dew_point(temp: float, rel: float) -> float:
    """Taupunkt in °C."""
    rel = max(rel, 0.1)
    alpha = math.log(rel / 100.0) + MAGNUS_A * temp / (MAGNUS_B + temp)
    return MAGNUS_B * alpha / (MAGNUS_A - alpha)


def wall_temperature(indoor: float, outdoor: float, frsi: float) -> float:
    """Geschätzte Temperatur der Wandoberfläche (Wärmebrücke) in °C."""
    return indoor - (indoor - outdoor) * (1.0 - frsi)


def wall_humidity(indoor: float, rel: float, wall_temp: float) -> float:
    """Relative Feuchte direkt an der Wandoberfläche in % (max. 100)."""
    return min(
        100.0, rel * saturation_vapor_pressure(indoor) / saturation_vapor_pressure(wall_temp)
    )


def mold_level(wall_rel: float | None) -> str | None:
    """Stufe des Schimmelrisikos (>80 % Risiko, >70 % Warnung)."""
    if wall_rel is None:
        return None
    if wall_rel > MOLD_RISK:
        return MOLD_LEVEL_RISK
    if wall_rel > MOLD_WARN:
        return MOLD_LEVEL_WARN
    return MOLD_LOW


def vent_duration(outdoor: float | None) -> int:
    """Empfohlene Stoßlüftdauer in Minuten nach Außentemperatur."""
    if outdoor is None:
        return 10
    if outdoor < 0:
        return 5
    if outdoor < 10:
        return 10
    if outdoor < 15:
        return 15
    return 25  # 20–30 Minuten


def _num(value: float, decimals: int = 0, lang: str = "de") -> str:
    text = f"{value:.{decimals}f}"
    return text if lang == "en" else text.replace(".", ",")


@dataclass(slots=True)
class AirInputs:
    """Messwerte eines Raums."""

    t_in: float | None = None
    rh_in: float | None = None
    t_out: float | None = None
    rh_out: float | None = None
    co2: float | None = None
    pm25: float | None = None
    raining: bool = False
    window_open: bool = False
    window_open_minutes: float = 0.0
    humidity_limit: float = 65.0
    frsi: float = 0.75
    shower: bool = False
    lang: str = "de"  # Sprache der Begründungstexte


@dataclass(slots=True)
class AirResult:
    """Ergebnis der Luftbewertung."""

    abs_in: float | None = None
    abs_out: float | None = None
    dew_point: float | None = None
    wall_temp: float | None = None
    wall_rh: float | None = None
    mold: str | None = None
    sensible: bool | None = None  # Lüften bringt trockenere Luft (und kein Regen)
    needed: bool = False
    need_reasons: list[str] = field(default_factory=list)
    humidity_reason: bool = False
    co2_reason: bool = False
    recommended: bool = False
    duration: int = 10
    too_dry: bool = False
    quality: str | None = None
    quality_reasons: list[str] = field(default_factory=list)
    window_close_due: bool = False


def evaluate_air(inp: AirInputs) -> AirResult:
    """Luft eines Raums bewerten."""
    res = AirResult(duration=vent_duration(inp.t_out))
    lang = inp.lang

    def txt(key: str, value: float) -> str:
        return t(lang, key, value=_num(value, lang=lang))

    if inp.t_in is not None and inp.rh_in is not None:
        res.abs_in = round(absolute_humidity(inp.t_in, inp.rh_in), 2)
        res.dew_point = round(dew_point(inp.t_in, inp.rh_in), 1)
        if inp.t_out is not None:
            wall = wall_temperature(inp.t_in, inp.t_out, inp.frsi)
            res.wall_temp = round(wall, 1)
            res.wall_rh = round(wall_humidity(inp.t_in, inp.rh_in, wall), 1)
            res.mold = mold_level(res.wall_rh)
    if inp.t_out is not None and inp.rh_out is not None:
        res.abs_out = round(absolute_humidity(inp.t_out, inp.rh_out), 2)
    if res.abs_in is not None and res.abs_out is not None:
        res.sensible = res.abs_out < res.abs_in - ABS_HUMIDITY_MARGIN and not inp.raining
    elif inp.raining:
        res.sensible = False

    # Lüften nötig?
    if inp.rh_in is not None and inp.rh_in > inp.humidity_limit:
        res.humidity_reason = True
        res.need_reasons.append(txt("need_humidity", inp.rh_in))
    # Wandfeuchte: nur „Risiko“ (> 80 %) ist ein Lüftungsgrund, „Warnung“ nur Anzeige
    if res.wall_rh is not None and res.wall_rh > MOLD_RISK:
        res.humidity_reason = True
        res.need_reasons.append(txt("need_wall", res.wall_rh))
    if inp.co2 is not None and inp.co2 >= CO2_WARN:
        res.co2_reason = True
        res.need_reasons.append(txt("need_co2", inp.co2))
    res.needed = res.humidity_reason or res.co2_reason
    # CO₂ ist immer ein Grund zu lüften, Feuchte nur, wenn es draußen trockener ist
    res.recommended = (
        not inp.window_open
        and res.needed
        and (res.co2_reason or (res.humidity_reason and res.sensible is True))
    )
    res.too_dry = inp.rh_in is not None and inp.rh_in < HUMIDITY_DRY

    # Fenster zu lange offen (nur in der Heizperiode relevant)
    res.window_close_due = (
        inp.window_open
        and (inp.t_out is None or inp.t_out < HEATING_SEASON_OUTDOOR)
        and inp.window_open_minutes > res.duration + WINDOW_REMIND_GRACE_MIN
    )

    # Luftqualitätsindex
    bad: list[str] = []
    mid: list[str] = []
    if inp.co2 is not None:
        if inp.co2 > CO2_BAD:
            bad.append(txt("q_co2_high", inp.co2))
        elif inp.co2 > CO2_WARN:
            mid.append(txt("q_co2_mid", inp.co2))
    if inp.rh_in is not None:
        if inp.rh_in > HUMIDITY_BAD:
            bad.append(txt("q_rh_high", inp.rh_in))
        elif inp.rh_in > inp.humidity_limit:
            mid.append(txt("q_rh_mid", inp.rh_in))
        elif inp.rh_in < HUMIDITY_VERY_DRY:
            bad.append(txt("q_rh_very_dry", inp.rh_in))
        elif inp.rh_in < HUMIDITY_DRY:
            mid.append(txt("q_rh_dry", inp.rh_in))
    if inp.pm25 is not None:
        if inp.pm25 > PM25_HIGH:
            bad.append(txt("q_pm_high", inp.pm25))
        elif inp.pm25 > PM25_MID:
            mid.append(txt("q_pm_mid", inp.pm25))
    if res.wall_rh is not None:
        if res.wall_rh > MOLD_RISK:
            bad.append(txt("q_mold_risk", res.wall_rh))
        elif res.wall_rh > MOLD_WARN:
            mid.append(txt("q_mold_warn", res.wall_rh))
    if inp.rh_in is None and inp.co2 is None and inp.pm25 is None:
        res.quality = None
    elif bad:
        res.quality, res.quality_reasons = QUALITY_BAD, bad + mid
    elif mid:
        res.quality, res.quality_reasons = QUALITY_MID, mid
    else:
        res.quality, res.quality_reasons = QUALITY_GOOD, [t(lang, "q_ok")]
    return res


@dataclass(slots=True)
class Recommendation:
    """Aktive Empfehlung eines Raums (Grundlage für Dashboard und Beratung)."""

    topic: str
    room: str
    priority: int
    short: str  # Kurztext fürs Dashboard
    values: dict[str, str] = field(default_factory=dict)  # Platzhalter der Meldungstexte
    variant: str | None = None  # abweichender Textsatz (z. B. „lueften_dusche“)

    @property
    def key(self) -> str:
        """Schlüssel für Drosselung („thema|raum“)."""
        return f"{self.topic}|{self.room}"


_EN_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    5: "five",
    10: "ten",
    15: "fifteen",
    20: "twenty",
    25: "twenty-five",
    30: "thirty",
    45: "forty-five",
    60: "sixty",
}


def minutes_word(minutes: float, lang: str = "de") -> str:
    """Minutenzahl für gesprochene Texte („zehn Minuten“, en: „ten minutes“)."""
    if lang == "en":
        value = round(minutes)
        word = _EN_WORDS.get(value, str(value))
        return f"{word} minute" if value == 1 else f"{word} minutes"
    words = {
        1: "eine",
        2: "zwei",
        3: "drei",
        5: "fünf",
        10: "zehn",
        15: "fünfzehn",
        20: "zwanzig",
        25: "fünfundzwanzig",
        30: "dreißig",
        45: "fünfundvierzig",
        60: "sechzig",
    }
    value = round(minutes)
    word = words.get(value, str(value))
    return f"{word} Minute" if value == 1 else f"{word} Minuten"


def room_phrase(name: str, lang: str = "de") -> str:
    """„im Wohnzimmer“, „in der Küche“ … (en: „in the Kitchen“)."""
    if lang == "en":
        return f"in the {name}"
    feminine = (
        "küche",
        "diele",
        "garage",
        "waschküche",
        "speisekammer",
        "toilette",
        "werkstatt",
        "kammer",
        "sauna",
        "loggia",
        "terrasse",
    )
    lower = name.lower()
    if lower.endswith(feminine):
        return f"in der {name}"
    return f"im {name}"
