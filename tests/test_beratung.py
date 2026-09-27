"""Modul Beratung – Kanäle, Drosselung, Ruhezeit, Stummschalter, Anwesenheit, Texte."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.pm_heizung.beratung import parse_push_map, sample_values
from custom_components.pm_heizung.beratung_texte import TEXTS, TITLES, render
from custom_components.pm_heizung.const import DOMAIN, NOTIFY_TOPICS

from .conftest import advance, backend_state, base_options, room_data, settle

SWITCH = "switch.pm_klima_beratung"
ADVICE = "sensor.pm_klima_empfehlung"
WINDOW = "binary_sensor.fenster_1_wohnzimmer"
PUSH_MAP = (
    "person.anna: notify.mobile_app_annas_telefon\nperson.ben = notify.mobile_app_bens_telefon"
)


class Channels:
    """Aufgezeichnete Aufrufe aller Kanäle."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.anna = async_mock_service(hass, "notify", "mobile_app_annas_telefon")
        self.ben = async_mock_service(hass, "notify", "mobile_app_bens_telefon")
        self.alexa = async_mock_service(hass, "script", "notify_alexa")
        self.panel = async_mock_service(hass, "esphome", "panel_tt_notification_show")

    def counts(self) -> tuple[int, int, int, int]:
        return len(self.anna), len(self.ben), len(self.alexa), len(self.panel)

    def total(self) -> int:
        return sum(self.counts())


def options(**kw: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "luft_aussenfeuchte": "sensor.aussenluftfeuchte",
        "beratung_push_zuordnung": PUSH_MAP,
        # Alexa und Panel sind ohne Skript/Dienst aus – hier ausdrücklich eingerichtet
        "beratung_alexa": True,
        "beratung_alexa_skript": "script.notify_alexa",
        "beratung_panel": True,
        "beratung_panel_dienst": "esphome.panel_tt_notification_show",
        "beratung_stumm": [
            "input_boolean.alles_stumm",
            "input_boolean.besuch_da",
            "input_boolean.ben_lernt",
        ],
    }
    values.update(kw)
    return base_options(**values)


def room(**kw: Any) -> dict[str, Any]:
    return room_data(
        temperatursensor="sensor.wz_temp", feuchtesensor="sensor.wz_feuchte", frsi=0.9, **kw
    )


def humid(hass: HomeAssistant, t_in: float = 21.0, rh: float = 68.0) -> None:
    hass.states.async_set("sensor.wz_temp", str(t_in))
    hass.states.async_set("sensor.wz_feuchte", str(rh))
    hass.states.async_set("sensor.aussentemperatur", "8", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.aussenluftfeuchte", "80")


async def enable(hass: HomeAssistant) -> None:
    await hass.services.async_call("switch", "turn_on", {"entity_id": SWITCH}, blocking=True)


async def start(hass, setup_integration, freezer, when: str, **kw) -> Channels:
    freezer.move_to(when)
    ch = Channels(hass)
    humid(hass)
    await setup_integration(options=options(**kw.pop("opts", {})), data=room(**kw))
    await settle(hass, freezer)
    return ch


# ---------------------------------------------------------------------------
async def test_channels_throttle_and_list(hass: HomeAssistant, setup_integration, freezer):
    """Schalter Standard aus; dann alle Kanäle einmal; Drosselung 2 h; Liste im Sensor."""
    ch = await start(hass, setup_integration, freezer, "2026-01-15 10:00:00+01:00")
    assert hass.states.get(SWITCH).state == "off"
    await advance(hass, freezer, 6 * 60)
    assert ch.total() == 0  # Beratung aus -> keine Meldung, Dashboard trotzdem
    st = hass.states.get(ADVICE)
    assert st.state == "Wohnzimmer: 10 min stoßlüften (Feuchte 68 %)"
    liste = st.attributes["liste"]
    assert [i["thema"] for i in liste] == ["lueften_feuchte", "schimmel_warnung"]
    assert liste[0]["raum"] == "Wohnzimmer" and liste[0]["prioritaet"] < liste[1]["prioritaet"]
    assert liste[0]["seit"]

    await enable(hass)
    await advance(hass, freezer, 61)
    assert ch.counts() == (1, 1, 1, 1)
    msg = ch.alexa[0].data["message"]
    assert "68 Prozent" in msg and "!" not in msg
    assert ch.alexa[0].data["type"] == "tts"
    assert ch.anna[0].data["title"] == "🌬️ Lüften empfohlen"
    assert ch.panel[0].data == {"label": "Lüften empfohlen", "message": msg}
    assert hass.states.get(ADVICE).attributes["letzte_meldung"]["kanaele"] == [
        "alexa",
        "panel",
        "push",
    ]
    # Drosselung: gleiche Meldung frühestens nach 2 h
    await advance(hass, freezer, 60 * 60)
    await advance(hass, freezer, 50 * 60)
    assert ch.counts() == (1, 1, 1, 1)
    await advance(hass, freezer, 11 * 60)
    assert ch.counts() == (2, 2, 2, 2)


async def test_min_active_time(hass: HomeAssistant, setup_integration, freezer):
    """Eine Empfehlung muss 5 min bestehen, bevor gemeldet wird (keine Sendestürme)."""
    ch = await start(hass, setup_integration, freezer, "2026-01-15 10:00:00+01:00")
    await enable(hass)
    humid(hass, rh=50)
    await advance(hass, freezer, 61)
    humid(hass, rh=68)
    await advance(hass, freezer, 61)
    assert ch.total() == 0  # „seit“ beginnt beim erneuten Auftreten
    for _ in range(4):
        await advance(hass, freezer, 61)
    assert ch.total() == 0
    await advance(hass, freezer, 61)
    assert ch.counts() == (1, 1, 1, 1)


async def test_quiet_time_and_frost(hass: HomeAssistant, setup_integration, freezer):
    """Ruhezeit: nur Panel; Frostgefahr darf auch nachts per Push/Alexa."""
    ch = await start(hass, setup_integration, freezer, "2026-01-15 23:00:00+01:00")
    await enable(hass)
    await advance(hass, freezer, 6 * 60)
    assert ch.counts() == (0, 0, 0, 1)

    humid(hass, t_in=10.5, rh=50)
    await advance(hass, freezer, 61)
    await advance(hass, freezer, 6 * 60)
    assert ch.counts() == (1, 1, 1, 1 + 1)
    assert "10,5 Grad" in ch.alexa[0].data["message"]
    assert ch.anna[0].data["title"] == "🥶 Frostgefahr"


async def test_mute_switches_block_alexa_only(hass: HomeAssistant, setup_integration, freezer):
    """Alles stumm / Besuch ist da / Ben lernt -> keine Alexa, Push und Panel schon."""
    hass.states.async_set("input_boolean.ben_lernt", "on")
    ch = await start(hass, setup_integration, freezer, "2026-01-15 10:00:00+01:00")
    await enable(hass)
    await advance(hass, freezer, 6 * 60)
    assert ch.counts() == (1, 1, 0, 1)
    # eigene Stumm-Liste: nur alles_stumm zählt
    hass.states.async_set("input_boolean.ben_lernt", "off")
    hass.states.async_set("input_boolean.alles_stumm", "on")
    await advance(hass, freezer, 2 * 60 * 60 + 60)
    assert ch.counts() == (2, 2, 0, 2)
    hass.states.async_set("input_boolean.alles_stumm", "off")
    hass.states.async_set("input_boolean.besuch_da", "on")
    await advance(hass, freezer, 2 * 60 * 60 + 60)
    assert ch.counts()[2] == 0


async def test_push_only_to_present_persons(hass: HomeAssistant, setup_integration, freezer):
    """Push nur an anwesende Personen."""
    ch = await start(hass, setup_integration, freezer, "2026-01-15 10:00:00+01:00")
    hass.states.async_set("person.ben", "not_home")
    await enable(hass)
    await advance(hass, freezer, 6 * 60)
    assert ch.counts() == (1, 0, 1, 1)


async def test_nobody_home(hass: HomeAssistant, setup_integration, freezer):
    """Niemand zuhause: keine Lüftmeldung; Fenster offen -> Push an alle (kein Alexa/Panel)."""
    freezer.move_to("2026-01-15 10:00:00+01:00")
    ch = Channels(hass)
    humid(hass)
    await setup_integration(options=options(), data=room(), home=False)
    await enable(hass)
    await advance(hass, freezer, 6 * 60)
    assert ch.total() == 0
    hass.states.async_set(WINDOW, "on")
    await advance(hass, freezer, 16 * 60)
    await advance(hass, freezer, 6 * 60)
    assert ch.counts() == (1, 1, 0, 0)
    assert ch.anna[0].data["title"] == "🪟 Fenster schließen"


async def test_global_gap_one_message_per_round(hass: HomeAssistant, setup_integration, freezer):
    """Zwei Themen: die wichtigere zuerst, die zweite frühestens 10 min später."""
    hass.states.async_set("sensor.filter", "5", {"unit_of_measurement": "%"})
    ch = await start(
        hass,
        setup_integration,
        freezer,
        "2026-01-15 10:00:00+01:00",
        luftreiniger="fan.lr",
        luftreiniger_filter=["sensor.filter"],
    )
    hass.states.async_set("fan.lr", "on", {"preset_mode": "Auto"})
    await enable(hass)
    await advance(hass, freezer, 6 * 60)
    assert len(ch.alexa) == 1
    assert "68 Prozent" in ch.alexa[0].data["message"]
    await advance(hass, freezer, 5 * 60)
    assert len(ch.alexa) == 1
    await advance(hass, freezer, 6 * 60)
    assert len(ch.alexa) == 2
    assert "5 Prozent" in ch.alexa[1].data["message"]
    assert ch.anna[1].data["title"] == "🧰 Filterwartung"


async def test_throttle_survives_restart(hass: HomeAssistant, setup_integration, freezer):
    """Drosselzustand und Schalter sind neustartsicher (Store)."""
    ch = await start(hass, setup_integration, freezer, "2026-01-15 10:00:00+01:00")
    await enable(hass)
    await advance(hass, freezer, 6 * 60)
    assert len(ch.alexa) == 1
    await advance(hass, freezer, 5)  # Store schreiben
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "on"
    await advance(hass, freezer, 30 * 60)
    assert len(ch.alexa) == 1


async def test_test_service(hass: HomeAssistant, setup_integration, freezer):
    """pm_heizung.beratung_testen sendet an genau einen Kanal (ohne Drosselung)."""
    ch = await start(hass, setup_integration, freezer, "2026-01-15 23:30:00+01:00")
    resp = await hass.services.async_call(
        DOMAIN, "beratung_testen", {"kanal": "alexa"}, blocking=True, return_response=True
    )
    assert ch.counts() == (0, 0, 1, 0)
    assert resp["text"] == ch.alexa[0].data["message"]
    await hass.services.async_call(
        DOMAIN, "beratung_testen", {"kanal": "push", "thema": "schimmel"}, blocking=True
    )
    assert ch.counts() == (1, 1, 1, 0)
    assert ch.ben[0].data["title"] == "🍄 Schimmelrisiko"
    await hass.services.async_call(DOMAIN, "beratung_testen", {"kanal": "panel"}, blocking=True)
    assert ch.counts() == (1, 1, 1, 1)


async def test_disabled_channels(hass: HomeAssistant, setup_integration, freezer):
    """Abgeschaltete Kanäle werden nicht benutzt."""
    ch = await start(
        hass,
        setup_integration,
        freezer,
        "2026-01-15 10:00:00+01:00",
        opts={"beratung_alexa": False, "beratung_panel": False},
    )
    await enable(hass)
    await advance(hass, freezer, 6 * 60)
    assert ch.counts() == (1, 1, 0, 0)


@pytest.mark.allow_errors
async def test_advisor_failure_isolated(
    hass: HomeAssistant, setup_integration, freezer, monkeypatch
):
    """Fehler in den Empfehlungen stören weder Heizung noch Sensor-Anlage."""
    from custom_components.pm_heizung import luft

    def boom(self):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(luft.AirRoom, "recommendations", boom)
    ch = await start(hass, setup_integration, freezer, "2026-01-15 10:00:00+01:00")
    await enable(hass)
    await advance(hass, freezer, 6 * 60)
    assert ch.total() == 0
    assert hass.states.get(ADVICE).state == "Keine Empfehlung"
    assert backend_state(hass) == ("heat", 21.0)


# --- Texte ------------------------------------------------------------------------
EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ten_variants_per_type_and_style(lang: str) -> None:
    """Je Meldungsart und Sprache zehn verschiedene Varianten im Jarvis-Register."""
    texts = TEXTS[lang]
    assert set(texts) == set(TEXTS["de"])
    assert set(TITLES[lang]) == set(TITLES["de"])
    for topic in NOTIFY_TOPICS:
        assert topic in texts, topic
        assert topic in TITLES[lang], topic
    for key, variants in texts.items():
        assert len(variants) == 10, key
        assert len(set(variants)) == 10, key
        for text in variants:
            assert "!" not in text, text
            assert not EMOJI.search(text), text
            low = f" {text.lower()} "
            if lang == "de":
                assert not re.search(r"\b(du|dein|deine|dich|dir)\b", low), text
            rendered = render(key, sample_values(lang), lang=lang)
            assert "{" not in rendered and "}" not in rendered
            assert rendered[0].isupper()
            assert len(rendered) < 250


def test_render_uses_random_variant() -> None:
    """Varianten werden zufällig gewählt, Platzhalter gefüllt, Satzanfang groß."""
    import random

    rng = random.Random(3)
    seen = {
        render("lueften_feuchte", {"im_raum": "im Bad", "wert": "74", "dauer": "zehn Minuten"}, rng)
        for _ in range(60)
    }
    assert len(seen) >= 8
    assert all("74 Prozent" in t or "74" in t for t in seen)
    assert "Im Bad" in " ".join(seen)


def test_parse_push_map() -> None:
    """Zuordnung Person -> notify-Dienst aus Text."""
    assert parse_push_map(PUSH_MAP) == {
        "person.anna": "notify.mobile_app_annas_telefon",
        "person.ben": "notify.mobile_app_bens_telefon",
    }
    assert parse_push_map("person.a -> mobile_app_a") == {"person.a": "notify.mobile_app_a"}
    assert parse_push_map("") == {}
    assert parse_push_map(None) == {}  # keine installationsspezifische Vorgabe


def _unused(call: ServiceCall) -> None:  # pragma: no cover - Typ-Hilfe
    pass
