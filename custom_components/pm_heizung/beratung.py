"""Modul „Beratung“: regelbasierte Klima-Empfehlungen und Benachrichtigungen.

Fehlerisolation: Alle Einstiegspunkte sind abgesichert; Fehler beim Senden oder Rechnen
werden protokolliert und beeinflussen weder die Heizung noch das Luftmodul.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import random
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_ON
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .beratung_texte import TITLES_DE, render, title
from .central import Central
from .const import (
    ADV_DEBOUNCE_SECONDS,
    ADV_GLOBAL_GAP_SECONDS,
    ADV_MIN_ACTIVE_SECONDS,
    ADV_TICK_SECONDS,
    AWAY_TOPICS,
    CHANNEL_ALEXA,
    CHANNEL_PANEL,
    CHANNEL_PUSH,
    CONF_ADV_ALEXA,
    CONF_ADV_ALEXA_SCRIPT,
    CONF_ADV_INTERVAL,
    CONF_ADV_MUTE,
    CONF_ADV_PANEL,
    CONF_ADV_PANEL_SERVICE,
    CONF_ADV_PUSH,
    CONF_ADV_PUSH_MAP,
    CONF_ADV_QUIET_END,
    CONF_ADV_QUIET_START,
    DEFAULT_ADV_ALEXA,
    DEFAULT_ADV_INTERVAL,
    DEFAULT_ADV_PANEL,
    DEFAULT_ADV_PUSH,
    DEFAULT_ALEXA_SCRIPT,
    DEFAULT_MUTE,
    DEFAULT_PANEL_SERVICE,
    DEFAULT_PUSH_MAP,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DOMAIN,
    NOTIFY_TOPICS,
    QUIET_EXEMPT_TOPICS,
    STORAGE_VERSION,
    TOPIC_FROST,
)
from .luft import AirRoom, _ErrorGate, _parse_time, guarded, in_window
from .luft_calc import Recommendation, minutes_word, room_phrase
from .sprache import t

_LOGGER = logging.getLogger(__name__)
NO_RECOMMENDATION = "Keine Empfehlung"  # Deutsch; sonst sprache.t(…, "no_recommendation")
SAMPLE_ROOM: dict[str, str] = {"de": "Wohnzimmer", "en": "Living room"}


def sample_values(lang: str) -> dict[str, str]:
    """Beispielwerte für Testmeldungen."""
    room = SAMPLE_ROOM.get(lang, SAMPLE_ROOM["de"])
    return {
        "wert": "74",
        "dauer": minutes_word(10, lang),
        "ppm": "1200",
        "empfohlen": minutes_word(10, lang),
        "aussen": "8",
        "wand": "13",
        "name": "Filter" if lang == "en" else "Filterwechsel",
        "rest": t(lang, "filter_days", value=5),
        "raum": room,
        "im_raum": room_phrase(room, lang),
    }


def parse_push_map(value: Any) -> dict[str, str]:
    """„person.x: notify.y“ je Zeile (Trenner „:“, „=“ oder „->“) in ein Dict wandeln."""
    if value is None:
        return dict(DEFAULT_PUSH_MAP)
    if isinstance(value, Mapping):
        return {str(k): str(v) for k, v in value.items()}
    result: dict[str, str] = {}
    for raw in str(value).replace(",", "\n").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for sep in ("->", "=", ":"):
            if sep in line:
                person, service = (p.strip() for p in line.split(sep, 1))
                if person and service:
                    if not service.startswith("notify."):
                        service = f"notify.{service}"
                    result[person] = service
                break
    return result


def format_push_map(mapping: Mapping[str, str]) -> str:
    """Dict als mehrzeiligen Text („person.x: notify.y“)."""
    return "\n".join(f"{k}: {v}" for k, v in mapping.items())


@dataclass(slots=True)
class ActiveRecommendation:
    """Aktive Empfehlung mit Beginn."""

    rec: Recommendation
    since: datetime


class Advisor:
    """Sammelt Empfehlungen aller Räume, führt Liste und verschickt gedrosselt."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        central: Central,
        airs: Mapping[str, AirRoom],
        rng: random.Random | None = None,
    ) -> None:
        """Initialisieren."""
        self.hass = hass
        self.entry = entry
        self.central = central
        self.airs = dict(airs)
        self.rng = rng or random.Random()
        self.aktiv = False
        self.active: dict[str, ActiveRecommendation] = {}
        self.last_message: dict[str, Any] | None = None
        self._sent: dict[str, datetime] = {}
        self._last_any: datetime | None = None
        self._stored_since: dict[str, datetime] = {}
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._debounce: CALLBACK_TYPE | None = None
        self._errors = _ErrorGate("Beratung")
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.beratung"
        )

    # --- Konfiguration ---------------------------------------------------
    def opt(self, key: str, default: Any) -> Any:
        value = self.central.options.get(key)
        return default if value is None or value == "" else value

    @property
    def language(self) -> str:
        return self.central.language

    @property
    def alexa_script(self) -> str:
        return str(self.opt(CONF_ADV_ALEXA_SCRIPT, DEFAULT_ALEXA_SCRIPT))

    @property
    def panel_service(self) -> str:
        return str(self.opt(CONF_ADV_PANEL_SERVICE, DEFAULT_PANEL_SERVICE))

    @property
    def interval(self) -> timedelta:
        return timedelta(minutes=float(self.opt(CONF_ADV_INTERVAL, DEFAULT_ADV_INTERVAL)))

    @property
    def push_map(self) -> dict[str, str]:
        return parse_push_map(self.central.options.get(CONF_ADV_PUSH_MAP))

    @property
    def mute_entities(self) -> list[str]:
        value = self.central.options.get(CONF_ADV_MUTE)
        if value is None:
            return list(DEFAULT_MUTE)
        return [value] if isinstance(value, str) else list(value)

    # --- Lebenszyklus ----------------------------------------------------
    async def async_start(self) -> None:
        """Gespeicherte Drosselzustände laden, Listener anhängen."""
        try:
            stored = await self._store.async_load() or {}
        except Exception:
            self._errors.report("Laden des Speichers")
            stored = {}
        self.aktiv = bool(stored.get("aktiv", False))
        self._sent = _parse_map(stored.get("gesendet"))
        self._stored_since = _parse_map(stored.get("seit"))
        self._last_any = _parse(stored.get("zuletzt"))
        if isinstance(last := stored.get("letzte_meldung"), dict):
            self.last_message = last
        for air in self.airs.values():
            self._unsubs.append(air.add_listener(self._async_air_changed))
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_tick, timedelta(seconds=ADV_TICK_SECONDS)
            )
        )
        self.refresh()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._debounce is not None:
            self._debounce()
            self._debounce = None

    @callback
    def add_listener(self, cb: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(cb)

        @callback
        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                self._errors.report("Listener")

    def _save(self) -> None:
        self._store.async_delay_save(self._data_to_store, 1)

    def _data_to_store(self) -> dict[str, Any]:
        return {
            "aktiv": self.aktiv,
            "gesendet": {k: v.isoformat() for k, v in self._sent.items()},
            "seit": {k: a.since.isoformat() for k, a in self.active.items()},
            "zuletzt": self._last_any.isoformat() if self._last_any else None,
            "letzte_meldung": self.last_message,
        }

    @callback
    def set_active(self, active: bool) -> None:
        """Globaler Schalter „Beratung“."""
        self.aktiv = active
        self._save()
        self._notify()

    # --- Auswertung ------------------------------------------------------
    @callback
    def _async_air_changed(self) -> None:
        if self._debounce is not None:
            return

        @callback
        def _fire(_now: datetime) -> None:
            self._debounce = None
            self.run()

        self._debounce = async_call_later(self.hass, ADV_DEBOUNCE_SECONDS, _fire)

    @callback
    def _async_tick(self, _now: datetime) -> None:
        # zeitabhängige Bedingungen (Fensterdauer, Nachtfenster) neu bewerten
        for air in self.airs.values():
            air.recompute()
        self.run()

    @guarded("Auswertung")
    def run(self) -> None:
        self.refresh()
        self.maybe_notify(dt_util.utcnow())

    @guarded("Empfehlungsliste")
    def refresh(self) -> None:
        now = dt_util.utcnow()
        current: dict[str, Recommendation] = {}
        for air in self.airs.values():
            try:
                for rec in air.recommendations():
                    current[rec.key] = rec
            except Exception:
                self._errors.report(f"Empfehlungen {air.room.name}")
        changed = set(current) != set(self.active)
        new_active: dict[str, ActiveRecommendation] = {}
        for key, rec in current.items():
            since = (
                self.active[key].since if key in self.active else self._stored_since.pop(key, now)
            )
            new_active[key] = ActiveRecommendation(rec, since)
            if key in self.active and self.active[key].rec.short != rec.short:
                changed = True
        self.active = new_active
        if changed:
            self._save()
        self._notify()

    def sorted_active(self) -> list[ActiveRecommendation]:
        return sorted(self.active.values(), key=lambda a: (a.rec.priority, a.since))

    def top_text(self) -> str:
        items = self.sorted_active()
        return items[0].rec.short[:255] if items else t(self.language, "no_recommendation")

    def as_list(self) -> list[dict[str, Any]]:
        return [
            {
                "raum": a.rec.room,
                "thema": a.rec.topic,
                "prioritaet": a.rec.priority,
                "text": a.rec.short,
                "seit": a.since.isoformat(),
            }
            for a in self.sorted_active()
        ]

    # --- Kanäle ----------------------------------------------------------
    def quiet(self, now: datetime) -> bool:
        start = _parse_time(
            self.opt(CONF_ADV_QUIET_START, DEFAULT_QUIET_START), DEFAULT_QUIET_START
        )
        end = _parse_time(self.opt(CONF_ADV_QUIET_END, DEFAULT_QUIET_END), DEFAULT_QUIET_END)
        return in_window(dt_util.as_local(now), start, end)

    def muted(self) -> bool:
        return any(self.hass.states.is_state(e, STATE_ON) for e in self.mute_entities)

    def present_push_targets(self) -> list[str]:
        return [
            svc
            for person, svc in self.push_map.items()
            if self.hass.states.is_state(person, STATE_HOME)
        ]

    def plan(self, topic: str, now: datetime) -> dict[str, list[str]]:
        """Kanäle (und Push-Empfänger) für ein Thema unter den aktuellen Bedingungen."""
        plan: dict[str, list[str]] = {}
        home = self.central.state.jemand_zuhause
        quiet = self.quiet(now) and topic not in QUIET_EXEMPT_TOPICS
        push_on = bool(self.opt(CONF_ADV_PUSH, DEFAULT_ADV_PUSH))
        if not home:
            if topic in AWAY_TOPICS and push_on and not quiet:
                targets = list(dict.fromkeys(self.push_map.values()))
                if targets:
                    plan[CHANNEL_PUSH] = targets
            return plan
        if push_on and not quiet and (targets := self.present_push_targets()):
            plan[CHANNEL_PUSH] = targets
        # Alexa und Panel nur mit hinterlegtem Skript bzw. Dienst
        alexa_on = bool(self.opt(CONF_ADV_ALEXA, DEFAULT_ADV_ALEXA)) and self.alexa_script
        if alexa_on and not quiet and not self.muted():
            plan[CHANNEL_ALEXA] = [self.alexa_script]
        if bool(self.opt(CONF_ADV_PANEL, DEFAULT_ADV_PANEL)) and self.panel_service:
            plan[CHANNEL_PANEL] = [self.panel_service]
        return plan

    def maybe_notify(self, now: datetime) -> None:
        """Höchstens eine Meldung je Durchlauf – die wichtigste berechtigte."""
        if not self.aktiv:
            return
        for item in self.sorted_active():
            rec = item.rec
            if rec.topic not in NOTIFY_TOPICS:
                continue
            if (now - item.since).total_seconds() < ADV_MIN_ACTIVE_SECONDS:
                continue
            last = self._sent.get(rec.key)
            if last is not None and now - last < self.interval:
                continue
            if (
                rec.topic != TOPIC_FROST
                and self._last_any is not None
                and (now - self._last_any).total_seconds() < ADV_GLOBAL_GAP_SECONDS
            ):
                return  # globaler Mindestabstand: später erneut versuchen
            plan = self.plan(rec.topic, now)
            if not plan:
                continue
            lang = self.language
            values = {
                **rec.values,
                "raum": rec.room,
                "im_raum": room_phrase(rec.room, lang),
            }
            text = render(rec.variant or rec.topic, values, self.rng, lang)
            self._sent[rec.key] = now
            self._last_any = now
            self._dispatch(rec.topic, text, plan, rec.room)
            self._save()
            return

    def _dispatch(self, topic: str, text: str, plan: Mapping[str, list[str]], room: str) -> None:
        self.last_message = {
            "zeit": dt_util.utcnow().isoformat(),
            "thema": topic,
            "raum": room,
            "text": text,
            "kanaele": sorted(plan),
        }
        _LOGGER.info("Beratung (%s, %s) über %s: %s", topic, room, ", ".join(sorted(plan)), text)
        self.entry.async_create_background_task(
            self.hass, self._async_send(topic, text, plan), f"pm_heizung beratung {topic}"
        )
        self._notify()

    async def _async_send(self, topic: str, text: str, plan: Mapping[str, list[str]]) -> None:
        push_title = title(topic, self.language)
        plain = title(topic, self.language, plain=True)
        for channel, targets in plan.items():
            for target in targets:
                try:
                    if channel == CHANNEL_PUSH:
                        domain, service = target.split(".", 1)
                        data: dict[str, Any] = {"title": push_title, "message": text}
                    elif channel == CHANNEL_ALEXA:
                        domain, service = "script", target.split(".", 1)[-1]
                        data = {"message": text, "type": "tts", "title": plain}
                    else:
                        domain, service = target.split(".", 1)
                        data = {"label": plain, "message": text}
                    if not domain or not service:
                        continue
                    if not self.hass.services.has_service(domain, service):
                        _LOGGER.warning("Beratung: Dienst %s.%s nicht vorhanden", domain, service)
                        continue
                    await self.hass.services.async_call(
                        domain, service, data, blocking=channel != CHANNEL_ALEXA
                    )
                except Exception as err:
                    _LOGGER.warning(
                        "Beratung: Senden über %s (%s) fehlgeschlagen: %s", channel, target, err
                    )

    async def async_test(self, channel: str, topic: str | None = None) -> dict[str, Any]:
        """Testmeldung an einen Kanal (ohne Drosselung, Ruhezeit, Stumm- und Anwesenheitsprüfung)."""
        key = topic or "test"
        text = render(key, sample_values(self.language), self.rng, self.language)
        if channel == CHANNEL_PUSH:
            targets = list(dict.fromkeys(self.push_map.values()))
        elif channel == CHANNEL_ALEXA:
            targets = [self.alexa_script] if self.alexa_script else []
        else:
            targets = [self.panel_service] if self.panel_service else []
        if targets:
            await self._async_send(key if key in TITLES_DE else "test", text, {channel: targets})
        return {"kanal": channel, "ziele": targets, "text": text}

    def diagnostics(self) -> dict[str, Any]:
        return {
            "aktiv": self.aktiv,
            "liste": self.as_list(),
            "gesendet": {k: v.isoformat() for k, v in self._sent.items()},
            "letzte_meldung": self.last_message,
            "push_zuordnung": self.push_map,
            "fehler": self._errors.count,
        }


def _parse(value: Any) -> datetime | None:
    if isinstance(value, str) and (parsed := dt_util.parse_datetime(value)):
        return dt_util.as_utc(parsed)
    return None


def _parse_map(value: Any) -> dict[str, datetime]:
    if not isinstance(value, dict):
        return {}
    return {str(k): d for k, v in value.items() if (d := _parse(v)) is not None}
