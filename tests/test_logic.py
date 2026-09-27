"""Reine Logik (Blueprint-Portierung) und echter schedule-Helfer mit Blockdaten."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest

from custom_components.pm_heizung.logic import (
    FAR_AWAY_M,
    RANK_BETWEEN,
    RANK_COMFORT,
    RANK_FAR,
    RANK_HOLD,
    away_temperature,
    ceil_half,
    compute_away_rank,
    distance_to_m,
    radii_for,
    round_half,
)

from .conftest import BACKEND, advance, backend_state, set_home_states

BAL = radii_for("balance", 3, 8, 20)


def test_radii() -> None:
    """Stufen-Radien wie im Blueprint, benutzerdefiniert monoton."""
    assert radii_for("eco", 0, 0, 0) == (1500, 4000, 15000)
    assert radii_for("aus", 0, 0, 0) == (0, 0, 25000)
    assert radii_for("unbekannt", 0, 0, 0) == BAL
    assert radii_for("eigene", 5, 2, 1) == (5000, 5000, 5000)


def test_distance_units() -> None:
    """Einheiten werden in Meter umgerechnet; ungültig = sehr weit."""
    assert distance_to_m("2", "km") == 2000
    assert distance_to_m("1", "mi") == pytest.approx(1609.344)
    assert distance_to_m("unknown", "m") == FAR_AWAY_M
    assert distance_to_m(None, None) == FAR_AWAY_M


def test_rounding() -> None:
    """0,5-Raster."""
    assert round_half(17.74) == 17.5
    assert round_half(17.75) == 18.0
    assert ceil_half(19.25) == 19.5
    assert ceil_half(19.5) == 19.5


@pytest.mark.parametrize(
    ("dist", "direction", "approach", "last", "expected"),
    [
        (3000, "towards", True, -1, RANK_COMFORT),
        (3000, "stationary", True, -1, RANK_HOLD),
        (3000, "stationary", True, RANK_COMFORT, RANK_COMFORT),  # Hysterese
        (3000, "away_from", True, RANK_COMFORT, RANK_HOLD),
        (8000, "towards", True, -1, RANK_BETWEEN),
        (8000, "stationary", False, -1, RANK_BETWEEN),
        (20000, "towards", True, -1, RANK_HOLD),
        (30000, "towards", True, -1, RANK_FAR),
        (8000, "stationary", True, RANK_COMFORT, RANK_BETWEEN),  # Hysterese max. Abstandsstufe
    ],
)
def test_rank_single(dist, direction, approach, last, expected) -> None:
    """Stufenberechnung eine Person."""
    assert compute_away_rank([dist], [direction], BAL, approach, last).rank == expected


def test_rank_pairs_and_aggregation() -> None:
    """Paarweise Auswertung; ungleiche Anzahl -> aggregiert; ohne Richtung -> nur Abstand."""
    # Person 1 nah aber stationary, Person 2 mittel und towards -> zwischen
    r = compute_away_rank([3000, 8000], ["stationary", "towards"], BAL, True, -1)
    assert r.rank == RANK_BETWEEN
    # aggregiert: kleinster Abstand + irgendwer towards
    r = compute_away_rank([3000, 8000], ["towards"], BAL, True, -1)
    assert r.rank == RANK_COMFORT
    r = compute_away_rank([3000, 8000], [], BAL, True, -1)
    assert r.rank == RANK_COMFORT


def test_away_temperatures() -> None:
    """Temperaturen relativ zur Komforttemperatur, nie über Zeitplan, nie unter Mindesttemperatur."""
    args = {"reference": 21.0, "setback": 3.0, "min_away": 16.0, "far_setback": 2.0}
    assert away_temperature("halten", base=21.0, **args) == 18.0
    assert away_temperature("fern", base=21.0, **args) == 16.0
    assert away_temperature("zwischen", base=21.0, **args) == 19.5
    assert away_temperature("komfort", base=22.0, **args) == 22.0
    assert away_temperature("halten", base=17.0, **args) == 17.0  # Eco-Zeit
    args["far_setback"] = 5
    assert away_temperature("fern", base=21.0, **args) == 16.0  # Mindesttemperatur


async def test_real_schedule_helper_block_data(
    hass: HomeAssistant, setup_integration, freezer
) -> None:
    """Der echte schedule-Helfer liefert Blockdaten als Attribut (HA ≥ 2025.x)."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    # Freitag, 25.09.2026, 07:30 Ortszeit
    freezer.move_to(datetime(2026, 9, 25, 7, 30, tzinfo=dt_util.get_default_time_zone()))
    day = {"from": "06:00", "to": "09:00", "data": {"temperatur": 22.5}}
    evening = {"from": "17:00", "to": "22:00"}
    assert await async_setup_component(
        hass,
        "schedule",
        {
            "schedule": {
                "heizung_wohnzimmer": {
                    "name": "Heizung Wohnzimmer",
                    **{
                        d: [day, evening]
                        for d in (
                            "monday",
                            "tuesday",
                            "wednesday",
                            "thursday",
                            "friday",
                            "saturday",
                            "sunday",
                        )
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    st = hass.states.get("schedule.heizung_wohnzimmer")
    assert st.state == "on"
    assert st.attributes["temperatur"] == 22.5
    set_home_states(hass)
    await setup_integration()
    await advance(hass, freezer, 11)
    assert backend_state(hass) == ("heat", 22.5)
    cl = hass.states.get("climate.pm_wohnzimmer")
    assert cl.attributes["naechster_wechsel"].startswith("2026-09-25T07:00:00")  # 09:00 Ortszeit

    # 09:00 -> Block zu Ende -> Eco
    freezer.move_to(datetime(2026, 9, 25, 9, 0, 1, tzinfo=dt_util.get_default_time_zone()))
    await advance(hass, freezer, 0)
    await advance(hass, freezer, 11)
    assert hass.states.get("schedule.heizung_wohnzimmer").state == "off"
    assert backend_state(hass) == ("heat", 18.0)

    # 17:00 -> Block ohne Daten -> Komfort
    freezer.move_to(datetime(2026, 9, 25, 17, 0, 1, tzinfo=dt_util.get_default_time_zone()))
    await advance(hass, freezer, 0)
    await advance(hass, freezer, 11)
    assert backend_state(hass) == ("heat", 21.0)
    assert hass.states.get(BACKEND) is not None
