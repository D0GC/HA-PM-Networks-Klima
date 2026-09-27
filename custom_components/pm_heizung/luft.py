"""Modul „Luft“ je Raum: Feuchte, Schimmelrisiko, Lüftempfehlung, Luftreiniger-Automatik.

Fehlerisolation: Das Modul liest die Heizung nur (Fenster, Ist-Werte, Anwesenheit) und
hängt sich ausschließlich über abgesicherte Callbacks an. Jede Ausnahme wird hier
abgefangen und protokolliert – die Heizungssteuerung läuft unbeeinflusst weiter.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from datetime import datetime, time, timedelta
import functools
import logging
from typing import Any

from homeassistant.components.climate import ATTR_HVAC_ACTION, HVACAction
from homeassistant.components.fan import FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AIR_OUTDOOR_HUM,
    CONF_AIR_OUTDOOR_TEMP,
    CONF_CO2_SENSOR,
    CONF_FRSI,
    CONF_HUMIDITY_LIMIT,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_OUTDOOR,
    CONF_PM25_SENSOR,
    CONF_PURIFIER,
    CONF_PURIFIER_FILTERS,
    CONF_PURIFIER_HOLD,
    CONF_PURIFIER_PAUSE,
    CONF_WEATHER,
    CONF_WET_ROOM,
    DEFAULT_FRSI,
    DEFAULT_HUMIDITY_LIMIT,
    DEFAULT_HUMIDITY_LIMIT_WET,
    DEFAULT_NIGHT_END,
    DEFAULT_NIGHT_START,
    DEFAULT_PURIFIER_HOLD,
    DEFAULT_PURIFIER_PAUSE,
    DOMAIN,
    FILTER_HOURS_MIN,
    FILTER_PERCENT_MIN,
    FROST_INDOOR,
    PM25_HIGH,
    PM25_HIGH_OFF,
    PM25_MID,
    PM25_MID_OFF,
    PURIFIER_AUTO,
    PURIFIER_FAST,
    PURIFIER_MIN_GAP,
    PURIFIER_OFF,
    PURIFIER_PERCENT,
    PURIFIER_PRESET_OPTIONS,
    PURIFIER_SLEEP,
    PURIFIER_TURBO,
    RAIN_STATES,
    SHOWER_RISE,
    SHOWER_WINDOW_MIN,
    STORAGE_VERSION,
    TOPIC_DRY,
    TOPIC_FILTER,
    TOPIC_FROST,
    TOPIC_HEAT_WINDOW,
    TOPIC_MOLD,
    TOPIC_MOLD_WARN,
    TOPIC_PM25,
    TOPIC_VENT_CO2,
    TOPIC_VENT_HUMIDITY,
    TOPIC_WINDOW_CLOSE,
    TOPIC_WINDOW_RAIN,
    TOPICS,
    WARN_THROTTLE,
)
from .logic import fmt_number
from .luft_calc import (
    AirInputs,
    AirResult,
    Recommendation,
    evaluate_air,
    minutes_word,
)
from .room import RoomController
from .sprache import t

_LOGGER = logging.getLogger(__name__)
INVALID = (STATE_UNAVAILABLE, STATE_UNKNOWN, None)
HEAT_WINDOW_MIN = 3.0  # Minuten offenes Fenster, bevor „Heizen bei offenem Fenster“ zählt
RAIN_WINDOW_MIN = 2.0


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_time(value: Any, default: str) -> time:
    text = str(value or default)
    parsed = dt_util.parse_time(text)
    return parsed or dt_util.parse_time(default) or time(0, 0)


def in_window(now_local: datetime, start: time, end: time) -> bool:
    """Liegt die Uhrzeit im (ggf. über Mitternacht reichenden) Zeitfenster?"""
    current = now_local.time()
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def priority(topic: str) -> int:
    """1 = höchste Priorität."""
    return TOPICS.index(topic) + 1


class _ErrorGate:
    """Fehler protokollieren, aber gedrosselt (erste Meldung mit Traceback)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.last: datetime | None = None
        self.count = 0

    def report(self, what: str) -> None:
        self.count += 1
        now = dt_util.utcnow()
        if self.last is None or (now - self.last).total_seconds() >= WARN_THROTTLE:
            self.last = now
            _LOGGER.exception(
                "%s: Fehler in %s (Heizung läuft unbeeinflusst weiter, %s. Fehler)",
                self.name,
                what,
                self.count,
            )
        else:
            _LOGGER.debug("%s: erneuter Fehler in %s", self.name, what, exc_info=True)


def guarded[**P](what: str) -> Callable[[Callable[P, None]], Callable[P, None]]:
    """Methode eines Objekts mit `_errors` gegen Ausnahmen absichern."""

    def deco(func: Callable[P, None]) -> Callable[P, None]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            try:
                func(*args, **kwargs)
            except Exception:
                args[0]._errors.report(what)  # type: ignore[attr-defined]

        return wrapper

    return deco


UNKNOWN_PRESET = "?"  # an, aber ohne (bekanntes) Preset – nie gleich „Auto“
PERCENT_TOLERANCE = 12.0  # Prozentpunkte: Geräte runden Drehzahlen auf eigene Stufen
ECHO_WINDOW = 120.0  # s nach einem eigenen Befehl: jede Änderung gilt als Rückmeldung
LATE_ECHO_WINDOW = 300.0  # s: Wechsel genau auf das eigene Ziel gilt noch als Rückmeldung


def _key(value: str | None) -> str:
    """Preset/Zustand normalisieren (Groß-/Kleinschreibung egal)."""
    return (value or "").strip().casefold()


class PurifierAutomation:
    """Automatik für einen Luftreiniger (Presets oder Lüfterdrehzahl).

    Regeln (Priorität von oben): Fenster offen -> aus; PM2,5 > 35 -> Turbo (nachts Fast);
    PM2,5 > 12 -> Auto; Nachtfenster -> Sleep; niemand zuhause -> Auto; sonst Auto.
    Die Stufen heißen standardmäßig wie bei Philips Air+ (Auto/Sleep/Fast/Turbo); je Raum
    lässt sich der Preset-Name jeder Stufe einstellen. Geräte ohne Presets werden über die
    Drehzahl gesteuert (Sleep 25 %, Auto 50 %, Fast 75 %, Turbo 100 %).
    Hysterese (35/30 bzw. 12/10 µg/m³), Mindesthaltezeit, 30 s Mindestabstand.
    Presets werden ohne Rücksicht auf Groß-/Kleinschreibung verglichen, ein fehlendes Preset
    gilt nicht als „Auto“. Eigene Befehle werden über den Kontext und ein Erwartungsfenster
    erkannt (auch verspätete Rückmeldungen per Polling); manuelle Bedienung pausiert die
    Automatik, die Pause ist neustartsicher gespeichert.
    """

    def __init__(self, air: AirRoom) -> None:
        """Initialisieren."""
        self.air = air
        self.hass = air.hass
        self.enabled = False
        self.paused_until: datetime | None = None
        self.last_cmd_at: datetime | None = None
        self.last_target: str | None = None
        self.high = False
        self.mid = False
        self.reason = t(air.room.central.language, "pur_off")
        self.target: str | None = None
        self._contexts: deque[str] = deque(maxlen=20)
        self._retry: CALLBACK_TYPE | None = None
        self._store: Store[dict[str, Any]] = Store(
            air.hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{air.entry.entry_id}.luftreiniger_{air.room.subentry_id}",
        )

    @property
    def entity_id(self) -> str | None:
        return self.air.data.get(CONF_PURIFIER) or None

    @property
    def hold(self) -> float:
        return float(self.air.get(CONF_PURIFIER_HOLD, DEFAULT_PURIFIER_HOLD)) * 60

    @property
    def pause(self) -> float:
        return float(self.air.get(CONF_PURIFIER_PAUSE, DEFAULT_PURIFIER_PAUSE)) * 60

    # --- Speicher --------------------------------------------------------
    async def async_load(self) -> None:
        """Pause und letzten Befehl laden (neustartsicher)."""
        if not self.entity_id:
            return
        data = await self._store.async_load() or {}
        now = dt_util.utcnow()
        paused = _parse_utc(data.get("pausiert_bis"))
        self.paused_until = paused if paused and paused > now else None
        self.last_cmd_at = _parse_utc(data.get("letzter_befehl"))
        self.last_target = data.get("letztes_ziel")

    def _save(self) -> None:
        self._store.async_delay_save(
            lambda: {
                "pausiert_bis": self.paused_until.isoformat() if self.paused_until else None,
                "letzter_befehl": self.last_cmd_at.isoformat() if self.last_cmd_at else None,
                "letztes_ziel": self.last_target,
            },
            1,
        )

    def stop(self) -> None:
        if self._retry is not None:
            self._retry()
            self._retry = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.paused_until = None
        self.last_cmd_at = None  # beim Einschalten sofort wirken
        self._save()
        self.air.recompute()

    # --- Zustand ---------------------------------------------------------
    @staticmethod
    def _state_key(state: State | None) -> str | None:
        """„aus“, Preset (normalisiert), Drehzahl („50%“ bei Geräten ohne Presets),
        „?“ (an ohne Preset) oder None (unbekannt)."""
        if state is None or state.state in INVALID:
            return None
        if state.state == STATE_OFF:
            return PURIFIER_OFF
        if preset := _key(state.attributes.get("preset_mode")):
            return preset
        percentage = _float(state.attributes.get("percentage"))
        if percentage is not None and not state.attributes.get("preset_modes"):
            return f"{round(percentage)}%"
        return UNKNOWN_PRESET

    @staticmethod
    def _matches(current: str | None, target: str | None) -> bool:
        """Entspricht der Gerätezustand dem Ziel? Drehzahlen mit Toleranz (Geräte runden)."""
        if current is None or target is None:
            return False
        cur, tgt = _key(current), _key(target)
        if cur.endswith("%") and tgt.endswith("%"):
            try:
                return abs(float(cur[:-1]) - float(tgt[:-1])) <= PERCENT_TOLERANCE
            except ValueError:
                return False
        return cur == tgt

    def preset_name(self, level: str) -> str:
        """Preset-Name des Geräts für eine Stufe (Raumeinstellung, sonst Standardname)."""
        key = PURIFIER_PRESET_OPTIONS.get(level)
        return str(self.air.get(key, level)) if key else level

    def current(self) -> str | None:
        if not self.entity_id:
            return None
        return self._state_key(self.hass.states.get(self.entity_id))

    def desired(self, now: datetime) -> tuple[str, str]:
        """(Ziel, Begründung)."""
        pm = self.air.pm25()
        if pm is not None:
            self.high = pm > PM25_HIGH or (self.high and pm >= PM25_HIGH_OFF)
            self.mid = pm > PM25_MID or (self.mid and pm >= PM25_MID_OFF)
        else:
            self.high = self.mid = False
        night = self.air.is_night(now)
        lang = self.air.room.central.language
        if self.air.room.window.raw_open:
            return PURIFIER_OFF, t(lang, "pur_window")
        if self.high:
            if night:
                return PURIFIER_FAST, t(lang, "pur_pm_high_night")
            return PURIFIER_TURBO, t(lang, "pur_pm_high")
        if self.mid:
            return PURIFIER_AUTO, t(lang, "pur_pm_mid")
        if night:
            return PURIFIER_SLEEP, t(lang, "pur_night")
        if not self.air.room.central.state.jemand_zuhause:
            return PURIFIER_AUTO, t(lang, "pur_away")
        return PURIFIER_AUTO, t(lang, "pur_normal")

    def _device_state(self) -> State | None:
        return self.hass.states.get(self.entity_id) if self.entity_id else None

    def _device_modes(self) -> list[str]:
        st = self._device_state()
        return [str(m) for m in (st.attributes.get("preset_modes") or [])] if st else []

    def _speed_only(self) -> bool:
        """Gerät ohne Presets, aber mit Drehzahl (z. B. IKEA, viele Zigbee-Lüfter)."""
        st = self._device_state()
        if st is None or self._device_modes():
            return False
        features = int(st.attributes.get(ATTR_SUPPORTED_FEATURES) or 0)
        return bool(features & FanEntityFeature.SET_SPEED) or "percentage" in st.attributes

    def _supported(self, target: str) -> str:
        """Stufe auf das Gerät abbilden.

        Presets: konfigurierter Name der Stufe in der Schreibweise des Geräts, mit Rückfall
        Turbo -> Fast -> Auto. Ohne Presets: Drehzahl in Prozent („75%“).
        """
        if target == PURIFIER_OFF:
            return target
        modes = self._device_modes()
        if not modes:
            if self._speed_only():
                return f"{PURIFIER_PERCENT.get(target, PURIFIER_PERCENT[PURIFIER_AUTO])}%"
            return self.preset_name(target)
        by_key = {_key(m): m for m in modes}
        levels = [target]
        if target == PURIFIER_TURBO:
            levels.append(PURIFIER_FAST)
        levels.append(PURIFIER_AUTO)
        for level in levels:
            for cand in (self.preset_name(level), level):
                if _key(cand) in by_key:
                    return by_key[_key(cand)]
        return modes[0]

    def evaluate(self, force: bool = False) -> None:
        now = dt_util.utcnow()
        target, reason = self.desired(now)
        target = self._supported(target)
        self.target, self.reason = target, reason
        if not self.enabled or not self.entity_id:
            return
        if self.paused_until is not None:
            if now < self.paused_until:
                self.reason = t(self.air.room.central.language, "pur_paused")
                self._schedule((self.paused_until - now).total_seconds())
                return
            self.paused_until = None
            self._save()
        current = self.current()
        if current is None or self._matches(current, target):
            return
        urgent = target == PURIFIER_OFF  # Fenster offen: sofort aus
        wait = 0.0
        if self.last_cmd_at is not None and not force:
            since = (now - self.last_cmd_at).total_seconds()
            wait = max(0.0, (PURIFIER_MIN_GAP if urgent else self.hold) - since)
        if wait > 0:
            self._schedule(wait)
            return
        self._send(target, current)

    def _schedule(self, seconds: float) -> None:
        self.stop()

        @callback
        def _fire(_now: datetime) -> None:
            self._retry = None
            self.air.recompute()

        self._retry = async_call_later(self.hass, seconds + 0.5, _fire)

    def _send(self, target: str, current: str) -> None:
        assert self.entity_id is not None
        ctx = Context()
        self._contexts.append(ctx.id)
        self.last_cmd_at = dt_util.utcnow()
        self.last_target = target
        data: dict[str, Any]
        if target == PURIFIER_OFF:
            service, data = "turn_off", {}
        elif target.endswith("%"):
            percentage = int(target[:-1])
            if current == PURIFIER_OFF:
                service, data = "turn_on", {"percentage": percentage}
            else:
                service, data = "set_percentage", {"percentage": percentage}
        elif current == PURIFIER_OFF:
            service, data = "turn_on", {"preset_mode": target}
        else:
            service, data = "set_preset_mode", {"preset_mode": target}
        _LOGGER.info("%s: Luftreiniger -> %s (%s)", self.air.room.name, target, self.reason)
        self._save()
        self.air.entry.async_create_background_task(
            self.hass,
            self._async_call(service, {ATTR_ENTITY_ID: self.entity_id, **data}, ctx),
            f"pm_heizung luftreiniger {self.entity_id}",
        )

    async def _async_call(self, service: str, data: dict[str, Any], ctx: Context) -> None:
        try:
            await self.hass.services.async_call("fan", service, data, blocking=True, context=ctx)
        except Exception as err:  # Gerät nicht erreichbar o. Ä.
            _LOGGER.warning("%s: Luftreiniger-Befehl fehlgeschlagen: %s", self.air.room.name, err)

    def is_own_echo(self, new: State, after: str | None, now: datetime) -> bool:
        """Rückmeldung eines eigenen Befehls (Kontext oder Erwartungsfenster)?"""
        ctx = new.context
        if ctx.id in self._contexts or (ctx.parent_id and ctx.parent_id in self._contexts):
            return True
        if self.last_cmd_at is None:
            return False
        since = (now - self.last_cmd_at).total_seconds()
        if since < ECHO_WINDOW:
            return True  # Zwischenzustände/Polling direkt nach dem eigenen Befehl
        return since < LATE_ECHO_WINDOW and self._matches(after, self.last_target)

    def on_fan_change(self, event: Event[EventStateChangedData]) -> None:
        """Manuelle Bedienung erkennen -> Automatik pausieren."""
        new, old = event.data["new_state"], event.data["old_state"]
        if not self.enabled or new is None or old is None:
            return
        before, after = self._state_key(old), self._state_key(new)
        if before is None or after is None or before == after:
            return
        now = dt_util.utcnow()
        if self.is_own_echo(new, after, now):
            return
        self.paused_until = now + timedelta(seconds=self.pause)
        self._save()
        _LOGGER.info(
            "%s: Luftreiniger manuell bedient (%s -> %s) – Automatik pausiert bis %s",
            self.air.room.name,
            before,
            after,
            dt_util.as_local(self.paused_until).strftime("%H:%M"),
        )
        self._schedule(self.pause)

    def attributes(self) -> dict[str, Any]:
        return {
            "luftreiniger": self.entity_id,
            "ziel": self.target,
            "begruendung": self.reason,
            "pausiert_bis": self.paused_until.isoformat() if self.paused_until else None,
            "letzter_befehl": self.last_cmd_at.isoformat() if self.last_cmd_at else None,
        }


def _parse_utc(value: Any) -> datetime | None:
    if isinstance(value, str) and (parsed := dt_util.parse_datetime(value)):
        return dt_util.as_utc(parsed)
    return None


class AirRoom:
    """Luftbewertung eines Raums."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        room: RoomController,
        data: Mapping[str, Any],
    ) -> None:
        """Initialisieren."""
        self.hass = hass
        self.entry = entry
        self.room = room
        self.data = dict(data)
        self.inputs = AirInputs()
        self.result = AirResult()
        self.purifier = PurifierAutomation(self)
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._humidity_log: deque[tuple[datetime, float]] = deque(maxlen=120)
        self._shower_until: datetime | None = None
        self._errors = _ErrorGate(f"{room.name} (Luft)")
        self._started = False

    # --- Konfiguration ---------------------------------------------------
    def get(self, key: str, default: Any) -> Any:
        value = self.data.get(key)
        return default if value is None or value == "" else value

    @property
    def central_options(self) -> Mapping[str, Any]:
        return self.room.central.options

    @property
    def wet_room(self) -> bool:
        return bool(self.data.get(CONF_WET_ROOM, False))

    @property
    def humidity_limit(self) -> float:
        default = DEFAULT_HUMIDITY_LIMIT_WET if self.wet_room else DEFAULT_HUMIDITY_LIMIT
        return float(self.get(CONF_HUMIDITY_LIMIT, default))

    @property
    def filters(self) -> list[str]:
        value = self.data.get(CONF_PURIFIER_FILTERS) or []
        return [value] if isinstance(value, str) else list(value)

    def _outdoor_temp_entity(self) -> str | None:
        return self.central_options.get(CONF_AIR_OUTDOOR_TEMP) or self.central_options.get(
            CONF_OUTDOOR
        )

    def tracked(self) -> list[str]:
        ents = [
            self.data.get(CONF_CO2_SENSOR),
            self.data.get(CONF_PM25_SENSOR),
            self.data.get(CONF_PURIFIER),
            self._outdoor_temp_entity(),
            self.central_options.get(CONF_AIR_OUTDOOR_HUM),
            self.central_options.get(CONF_WEATHER),
            *self.filters,
            *self.room.windows,
        ]
        return list(dict.fromkeys(e for e in ents if e))

    # --- Lebenszyklus ----------------------------------------------------
    async def async_load(self) -> None:
        """Gespeicherte Daten laden (Fehler werden abgefangen)."""
        try:
            await self.purifier.async_load()
        except Exception:
            self._errors.report("Laden des Speichers")

    @guarded("Start")
    def async_start(self) -> None:
        if ents := self.tracked():
            self._unsubs.append(
                async_track_state_change_event(self.hass, ents, self._async_on_state)
            )
        self._unsubs.append(self.room.add_listener(self._async_on_room))
        self._started = True
        self.recompute()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # pragma: no cover - defensiv
                _LOGGER.debug("Abmelden fehlgeschlagen", exc_info=True)
        self._unsubs.clear()
        self.purifier.stop()
        self._started = False

    @callback
    def add_listener(self, cb: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(cb)

        @callback
        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    @callback
    @guarded("Raum-Aktualisierung")
    def _async_on_room(self) -> None:
        self.recompute()

    @callback
    @guarded("Zustandsänderung")
    def _async_on_state(self, event: Event[EventStateChangedData]) -> None:
        if event.data["entity_id"] == self.data.get(CONF_PURIFIER):
            self.purifier.on_fan_change(event)
        self.recompute()

    # --- Messwerte -------------------------------------------------------
    def _value(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return _float(st.state) if st is not None else None

    def pm25(self) -> float | None:
        return self._value(self.data.get(CONF_PM25_SENSOR))

    def is_night(self, now: datetime) -> bool:
        start = _parse_time(self.data.get(CONF_NIGHT_START), DEFAULT_NIGHT_START)
        end = _parse_time(self.data.get(CONF_NIGHT_END), DEFAULT_NIGHT_END)
        return in_window(dt_util.as_local(now), start, end)

    def _raining(self) -> bool:
        weather = self.central_options.get(CONF_WEATHER)
        if not weather or (st := self.hass.states.get(weather)) is None:
            return False
        if st.state in RAIN_STATES:
            return True
        precipitation = _float(st.attributes.get("precipitation"))
        return precipitation is not None and precipitation > 0

    def window_open_since(self) -> datetime | None:
        """Seit wann ist (mindestens) ein Fenster offen?"""
        opened = [
            st.last_changed
            for e in self.room.windows
            if (st := self.hass.states.get(e)) is not None and st.state == STATE_ON
        ]
        return min(opened) if opened else None

    def _window_open_minutes(self, now: datetime) -> float:
        since = self.window_open_since()
        return 0.0 if since is None else max(0.0, (now - since).total_seconds() / 60)

    def _detect_shower(self, now: datetime, rh: float | None) -> bool:
        if rh is None or not self.wet_room:
            return False
        if not self._humidity_log or self._humidity_log[-1][1] != rh:
            self._humidity_log.append((now, rh))
        horizon = now - timedelta(minutes=SHOWER_WINDOW_MIN)
        recent = [v for t, v in self._humidity_log if t >= horizon]
        if recent and rh - min(recent) >= SHOWER_RISE:
            self._shower_until = now + timedelta(minutes=60)
        if self._shower_until is not None and now >= self._shower_until:
            self._shower_until = None
        return self._shower_until is not None and rh > self.humidity_limit

    def collect(self, now: datetime) -> AirInputs:
        rh_in = self.room.current_humidity()
        return AirInputs(
            t_in=self.room.current_temperature(),
            rh_in=rh_in,
            t_out=self._value(self._outdoor_temp_entity()),
            rh_out=self._value(self.central_options.get(CONF_AIR_OUTDOOR_HUM)),
            co2=self._value(self.data.get(CONF_CO2_SENSOR)),
            pm25=self.pm25(),
            raining=self._raining(),
            window_open=self.room.window.raw_open,
            window_open_minutes=self._window_open_minutes(now),
            humidity_limit=self.humidity_limit,
            frsi=float(self.get(CONF_FRSI, DEFAULT_FRSI)),
            shower=self._detect_shower(now, rh_in),
            lang=self.room.central.language,
        )

    @guarded("Berechnung")
    def recompute(self) -> None:
        if not self._started:
            return
        now = dt_util.utcnow()
        self.inputs = self.collect(now)
        self.result = evaluate_air(self.inputs)
        try:
            self.purifier.evaluate()
        except Exception:
            self._errors.report("Luftreiniger-Automatik")
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                self._errors.report("Listener")

    # --- Empfehlungen ----------------------------------------------------
    def _backend_heating(self) -> bool:
        for e in self.room.backends:
            st = self.hass.states.get(e)
            if st is not None and st.attributes.get(ATTR_HVAC_ACTION) == HVACAction.HEATING:
                return True
        return False

    def _filter_recs(self, name: str) -> list[Recommendation]:
        recs: list[Recommendation] = []
        for ent in self.filters:
            st = self.hass.states.get(ent)
            if st is None or (value := _float(st.state)) is None:
                continue
            unit = str(st.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or "")
            label = str(st.attributes.get("friendly_name") or ent)
            lang = self.room.central.language
            if unit == "%" and value < FILTER_PERCENT_MIN:
                rest = t(lang, "filter_percent", value=fmt_number(value, 0, lang))
            elif unit in ("h", "Std.") and value < FILTER_HOURS_MIN:
                days = max(0, round(value / 24))
                rest = (
                    t(lang, "filter_less_day")
                    if days < 1
                    else (
                        t(lang, "filter_one_day")
                        if days == 1
                        else t(lang, "filter_days", value=days)
                    )
                )
            else:
                continue
            recs.append(
                Recommendation(
                    TOPIC_FILTER,
                    name,
                    priority(TOPIC_FILTER),
                    t(lang, "rec_filter", room=name, label=label, rest=rest),
                    {"name": label, "rest": rest},
                )
            )
        return recs[:1]  # ein Filterhinweis je Raum genügt

    def recommendations(self) -> list[Recommendation]:
        """Aktive Empfehlungen dieses Raums."""
        if not self._started:
            return []
        name = self.room.name
        inp, res = self.inputs, self.result
        recs: list[Recommendation] = []

        lang = self.room.central.language

        def add(topic: str, short: str, variant: str | None = None, **values: str) -> None:
            recs.append(Recommendation(topic, name, priority(topic), short, values, variant))

        def num(value: float, decimals: int = 1) -> str:
            return fmt_number(value, decimals, lang)

        def short(key: str, **values: Any) -> str:
            return t(lang, key, room=name, **values)

        duration = minutes_word(res.duration, lang)
        if inp.t_in is not None and inp.t_in < FROST_INDOOR:
            add(TOPIC_FROST, short("rec_frost", value=num(inp.t_in)), wert=num(inp.t_in))
        open_min = inp.window_open_minutes
        if inp.window_open and open_min >= HEAT_WINDOW_MIN and self._backend_heating():
            add(
                TOPIC_HEAT_WINDOW,
                short("rec_heat_window"),
                dauer=minutes_word(open_min, lang),
            )
        if res.wall_rh is not None and res.mold == "risiko":
            add(
                TOPIC_MOLD,
                short("rec_mold", value=num(res.wall_rh, 0)),
                wert=num(res.wall_rh, 0),
                wand=num(res.wall_temp or 0),
                dauer=duration,
            )
        elif res.wall_rh is not None and res.mold == "warnung":
            add(
                TOPIC_MOLD_WARN,
                short("rec_mold_warn", value=num(res.wall_rh, 0)),
                wert=num(res.wall_rh, 0),
            )
        if inp.window_open and inp.raining and open_min >= RAIN_WINDOW_MIN:
            add(TOPIC_WINDOW_RAIN, short("rec_rain"))
        elif res.window_close_due:
            add(
                TOPIC_WINDOW_CLOSE,
                short("rec_window_close", minutes=round(open_min)),
                dauer=minutes_word(open_min, lang),
                empfohlen=duration,
                aussen=num(inp.t_out) if inp.t_out is not None else t(lang, "unknown"),
            )
        if res.recommended and res.co2_reason and inp.co2 is not None:
            add(
                TOPIC_VENT_CO2,
                short("rec_vent_co2", minutes=res.duration, value=num(inp.co2, 0)),
                None,
                ppm=num(inp.co2, 0),
                dauer=duration,
            )
        elif res.recommended and res.humidity_reason and inp.rh_in is not None:
            add(
                TOPIC_VENT_HUMIDITY,
                short("rec_vent_humidity", minutes=res.duration, value=num(inp.rh_in, 0)),
                "lueften_dusche" if inp.shower else None,
                wert=num(inp.rh_in, 0),
                dauer=duration,
            )
        purifier_auto = self.purifier.enabled and self.purifier.entity_id
        if inp.pm25 is not None and inp.pm25 > PM25_HIGH and not purifier_auto:
            add(
                TOPIC_PM25,
                short("rec_pm25", value=num(inp.pm25, 0)),
                "feinstaub_ohne_geraet" if not self.purifier.entity_id else None,
                wert=num(inp.pm25, 0),
            )
        if res.too_dry and not inp.window_open and inp.rh_in is not None:
            add(
                TOPIC_DRY,
                short("rec_dry", value=num(inp.rh_in, 0)),
                wert=num(inp.rh_in, 0),
            )
        recs.extend(self._filter_recs(name))
        return recs

    # --- Anzeige ---------------------------------------------------------
    def base_attributes(self) -> dict[str, Any]:
        inp, res = self.inputs, self.result
        return {
            "temperatur_innen": inp.t_in,
            "feuchte_innen": inp.rh_in,
            "temperatur_aussen": inp.t_out,
            "feuchte_aussen": inp.rh_out,
            "abs_feuchte_innen": res.abs_in,
            "abs_feuchte_aussen": res.abs_out,
            "taupunkt": res.dew_point,
            "co2": inp.co2,
            "pm25": inp.pm25,
            "regen": inp.raining,
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "inputs": {k: getattr(self.inputs, k) for k in self.inputs.__slots__},
            "result": {k: getattr(self.result, k) for k in self.result.__slots__},
            "purifier": {"enabled": self.purifier.enabled, **self.purifier.attributes()},
            "fehler": self._errors.count,
        }
