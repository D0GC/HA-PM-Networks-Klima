"""Raumsteuerung: Soll-Berechnung, Overlays, Fenster und Backend-Ansteuerung."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util, slugify

from .backend import backend_kind, capabilities, entity_exists, is_tado
from .central import Central
from .const import (
    ACTION_HOLD_SECONDS,
    ACTION_MARGIN,
    BACKOFF_MAX,
    BACKOFF_START,
    CONF_ADOPT_EXTERNAL,
    CONF_BOOST_MINUTES,
    CONF_CLIMATES,
    CONF_COMFORT,
    CONF_ECO,
    CONF_EXT_OFF_AS_WINDOW,
    CONF_FROST,
    CONF_HUMIDITY_SENSOR,
    CONF_MAX,
    CONF_MIN,
    CONF_NAME,
    CONF_OFF_FROST,
    CONF_OVERLAY_MINUTES,
    CONF_OVERLAY_MODE,
    CONF_SCHEDULE,
    CONF_SCHEDULE_ATTR,
    CONF_TEMP_SENSOR,
    CONF_WINDOW_ACTION,
    CONF_WINDOW_CLOSE_DELAY,
    CONF_WINDOW_OPEN_DELAY,
    CONF_WINDOWS,
    DEBOUNCE_SECONDS,
    DEFAULT_BOOST_MINUTES,
    DEFAULT_COMFORT,
    DEFAULT_ECO,
    DEFAULT_FROST,
    DEFAULT_MAX,
    DEFAULT_MIN,
    DEFAULT_OVERLAY_MINUTES,
    DEFAULT_OVERLAY_MODE,
    DEFAULT_SCHEDULE_ATTR,
    DEFAULT_TEMP_STEP,
    DEFAULT_WINDOW_CLOSE_DELAY,
    DEFAULT_WINDOW_OPEN_DELAY,
    DOMAIN,
    ECHO_GRACE_SECONDS,
    EXT_WINDOW_MINUTES,
    ISSUE_BACKEND_MISSING,
    ISSUE_EXT_OFF,
    LOCK_EFFECT_OFF,
    LOCK_REASON_OUTDOOR,
    MAX_SEND_ATTEMPTS,
    MIN_SEND_INTERVAL,
    NON_MANUAL_PRESETS,
    OFF_HOLD_MAX,
    OFF_HOLD_START,
    OFF_QUIET_SECONDS,
    OFF_REJECT_LIMIT,
    OFF_REJECT_WINDOW,
    OVERLAY_FALLBACK_MINUTES,
    OVERLAY_NEXT_BLOCK,
    OVERLAY_TIMER,
    PHASE_BETWEEN,
    PHASE_COMFORT,
    PHASE_HOLD,
    PHASE_HOME,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_FROST,
    PRESET_MANUAL,
    PRESET_NONE,
    PRESET_SCHEDULE,
    REASON_AWAY,
    REASON_BOOST,
    REASON_LOCK,
    REASON_MANUAL,
    REASON_OFF,
    REASON_PAUSED,
    REASON_PREHEAT,
    REASON_SCHEDULE,
    REASON_WINDOW,
    REASON_WINDOW_EXT,
    TEMP_TOLERANCE,
    VERIFY_SECONDS,
    WARN_THROTTLE,
    WINDOW_ACTION_FROST,
)
from .logic import away_temperature, clamp, fmt_temp, fmt_time, round_step
from .sprache import t

_LOGGER = logging.getLogger(__name__)

INVALID_STATES = (STATE_UNAVAILABLE, STATE_UNKNOWN)
PRESET_LABELS: dict[str, str] = {  # Preset -> Textschlüssel (sprache.py)
    PRESET_COMFORT: "comfort",
    PRESET_ECO: "eco",
    PRESET_AWAY: "away",
    PRESET_FROST: "frost",
}


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return dt_util.as_utc(value)
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        return dt_util.as_utc(parsed) if parsed else None
    return None


@dataclass(slots=True)
class Desired:
    """Gewünschter Backend-Zustand und Begründung."""

    target: float | None  # None = Backend aus (wirksamer Sollwert)
    reason: str
    phase: str
    base: float
    in_block: bool | None
    next_change: datetime | None
    planned: float | None = None  # Sollwert ohne Übersteuerung (Fenster/Boost)
    planned_reason: str = REASON_SCHEDULE


@dataclass(slots=True)
class BackendTrack:
    """Sendeprotokoll je Backend-Entität."""

    last_sent: tuple[str, float | None] | None = None
    last_sent_at: datetime | None = None
    before_send: tuple[str, float | None] | None = None
    pending: bool = False
    attempts: int = 0  # Sendeversuche für denselben Sollwert ohne Reaktion
    settled_note: bool = False  # Rundung des Backends bereits protokolliert
    fail_count: int = 0  # aufeinanderfolgende Fehler (Backoff)
    retry_at: datetime | None = None
    last_warn: datetime | None = None
    off_hold: bool = False  # retry_at stammt aus dem Pingpong-Schutz (externes „aus“)


@dataclass(slots=True)
class RoomPersist:
    """Neustartsichere Raumdaten (über RestoreEntity gesichert)."""

    hvac_mode: str = HVACMode.AUTO
    manual_temp: float | None = None
    preset: str | None = None
    overlay_active: bool = False
    overlay_temp: float | None = None  # None bei aktivem Overlay = aus
    overlay_until: datetime | None = None
    boost_until: datetime | None = None
    extern_off_rejected: int = 0  # abgelehnte „aus“-Befehle vom Backend
    ext_window_until: datetime | None = None  # externes „aus“ als Fensteröffnung

    def as_dict(self) -> dict[str, Any]:
        """Serialisieren."""
        return {
            "hvac_mode": str(self.hvac_mode),
            "manual_temp": self.manual_temp,
            "preset": self.preset,
            "overlay_active": self.overlay_active,
            "overlay_temp": self.overlay_temp,
            "overlay_until": self.overlay_until.isoformat() if self.overlay_until else None,
            "boost_until": self.boost_until.isoformat() if self.boost_until else None,
            "extern_off_rejected": self.extern_off_rejected,
            "ext_window_until": (
                self.ext_window_until.isoformat() if self.ext_window_until else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RoomPersist:
        """Deserialisieren."""
        mode = data.get("hvac_mode", HVACMode.AUTO)
        if mode not in (HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF):
            mode = HVACMode.AUTO
        return cls(
            hvac_mode=mode,
            manual_temp=_float(data.get("manual_temp")),
            preset=data.get("preset"),
            overlay_active=bool(data.get("overlay_active", False)),
            overlay_temp=_float(data.get("overlay_temp")),
            overlay_until=_parse_dt(data.get("overlay_until")),
            boost_until=_parse_dt(data.get("boost_until")),
            extern_off_rejected=int(_float(data.get("extern_off_rejected")) or 0),
            ext_window_until=_parse_dt(data.get("ext_window_until")),
        )


@dataclass(slots=True)
class WindowState:
    """Fensterzustand (roh und wirksam)."""

    raw_open: bool = False
    effective_open: bool = False
    open_sensors: list[str] = field(default_factory=list)


class RoomController:
    """Steuert einen Raum, unabhängig vom konkreten Thermostat-Backend."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        central: Central,
        subentry_id: str,
        data: Mapping[str, Any],
    ) -> None:
        """Initialisieren."""
        self.hass = hass
        self.entry = entry
        self.central = central
        self.subentry_id = subentry_id
        self.data = dict(data)
        self.persist = RoomPersist()
        self.window = WindowState()
        self.desired: Desired | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._tracks: dict[str, BackendTrack] = {}
        self._contexts: deque[str] = deque(maxlen=50)
        self._started = False
        self._on_persist_change: Callable[[], None] | None = None
        self._action_changed_at: datetime | None = None
        self._extern_off_warned_at: datetime | None = None
        self._off_rejects: deque[datetime] = deque(maxlen=20)
        self._off_hold_level = 0
        self._issue_active = False

    # --- Konfiguration ---------------------------------------------------
    def _get(self, key: str, default: Any) -> Any:
        value = self.data.get(key)
        return default if value is None or value == "" else value

    @property
    def name(self) -> str:
        return str(self.data.get(CONF_NAME, "Raum"))

    @property
    def backends(self) -> list[str]:
        return _as_list(self.data.get(CONF_CLIMATES))

    @property
    def windows(self) -> list[str]:
        return _as_list(self.data.get(CONF_WINDOWS))

    @property
    def schedule(self) -> str | None:
        return self.data.get(CONF_SCHEDULE) or None

    @property
    def comfort(self) -> float:
        return float(self._get(CONF_COMFORT, DEFAULT_COMFORT))

    @property
    def eco(self) -> float:
        return float(self._get(CONF_ECO, DEFAULT_ECO))

    @property
    def frost(self) -> float:
        return float(self._get(CONF_FROST, DEFAULT_FROST))

    @property
    def min_temp(self) -> float:
        return float(self._get(CONF_MIN, DEFAULT_MIN))

    @property
    def max_temp(self) -> float:
        return float(self._get(CONF_MAX, DEFAULT_MAX))

    @property
    def adopt_external(self) -> bool:
        return bool(self._get(CONF_ADOPT_EXTERNAL, True))

    def backend_kinds(self) -> dict[str, str]:
        """Gerätetyp je Thermostat (tado_cloud, tado_lokal, generisch)."""
        return {e: backend_kind(self.hass, e) for e in self.backends}

    @property
    def ext_off_as_window(self) -> bool:
        """Externes „aus“ als Fensteröffnung werten.

        Standard: nur bei tado-Thermostaten (deren Fenstererkennung schaltet aus) und nur
        ohne eigenen Fenstersensor. Andere Geräte melden „aus“ nur, wenn jemand ausschaltet.
        """
        value = self.data.get(CONF_EXT_OFF_AS_WINDOW)
        if value is not None:
            return bool(value)
        return not self.windows and any(is_tado(k) for k in self.backend_kinds().values())

    def ext_window_active(self, now: datetime | None = None) -> bool:
        until = self.persist.ext_window_until
        return until is not None and until > (now or dt_util.utcnow())

    def away_preset_temp(self) -> float:
        """Temperatur des Presets „abwesend“ (Haltetemperatur)."""
        return away_temperature(
            PHASE_HOLD,
            self.comfort,
            self.comfort,
            self.central.setback,
            self.central.min_away,
            self.central.far_setback,
        )

    def preset_temp(self, preset: str) -> float:
        """Temperatur eines Presets."""
        return {
            PRESET_COMFORT: self.comfort,
            PRESET_ECO: self.eco,
            PRESET_AWAY: self.away_preset_temp(),
            PRESET_FROST: self.frost,
            PRESET_BOOST: self.max_temp,
        }.get(preset, self.comfort)

    # --- Lebenszyklus ----------------------------------------------------
    @callback
    def async_start(
        self,
        restored: Mapping[str, Any] | None,
        on_persist_change: Callable[[], None] | None = None,
    ) -> None:
        """Zustand wiederherstellen und Listener anhängen."""
        if restored:
            self.persist = RoomPersist.from_dict(restored)
        self._on_persist_change = on_persist_change
        now = dt_util.utcnow()
        p = self.persist
        if p.overlay_active and p.overlay_until and p.overlay_until <= now:
            self._clear_overlay()
        if p.boost_until and p.boost_until <= now:
            p.boost_until = None
            if p.preset == PRESET_BOOST:
                p.preset = None
        if p.ext_window_until and p.ext_window_until <= now:
            p.ext_window_until = None
        self._arm_timers()

        # Fenster beim Start ohne Verzögerung übernehmen
        self._update_window_raw()
        self.window.effective_open = self.window.raw_open

        tracked = list(
            dict.fromkeys(
                [
                    *self.backends,
                    *self.windows,
                    *[
                        e
                        for e in (
                            self.schedule,
                            self.data.get(CONF_TEMP_SENSOR),
                            self.data.get(CONF_HUMIDITY_SENSOR),
                        )
                        if e
                    ],
                ]
            )
        )
        if tracked:
            self._unsubs.append(
                async_track_state_change_event(self.hass, tracked, self._async_on_state)
            )
        self._unsubs.append(self.central.add_listener(self._async_on_central))
        self._started = True
        # Erst senden, wenn Home Assistant vollständig gestartet ist (Zeitplan,
        # Anwesenheit usw. sind dann geladen) – bis dahin nur berechnen.
        self._unsubs.append(async_at_started(self.hass, self._async_hass_started))
        self.evaluate()

    @callback
    def _async_hass_started(self, _hass: HomeAssistant) -> None:
        self._check_backends_exist()
        self.evaluate()

    def _check_backends_exist(self) -> None:
        """Reparaturhinweis, wenn ein Thermostat nicht mehr existiert (z. B. Integration entfernt)."""
        missing = [e for e in self.backends if not entity_exists(self.hass, e)]
        issue_id = f"{ISSUE_BACKEND_MISSING}_{self.subentry_id}"
        if not missing:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        _LOGGER.warning("%s: Thermostat nicht vorhanden: %s", self.name, ", ".join(missing))
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_BACKEND_MISSING,
            translation_placeholders={"raum": self.name, "entitaeten": ", ".join(missing)},
        )

    @callback
    def async_stop(self) -> None:
        """Alle Listener/Timer lösen."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for timer in self._timers.values():
            timer()
        self._timers.clear()
        self._started = False

    @callback
    def add_listener(self, cb: Callable[[], None]) -> CALLBACK_TYPE:
        """Listener für Anzeige-Updates."""
        self._listeners.append(cb)

        @callback
        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    # --- Timer-Hilfen ----------------------------------------------------
    def _cancel(self, name: str) -> None:
        if (timer := self._timers.pop(name, None)) is not None:
            timer()

    def _at(self, name: str, when: datetime, action: Callable[[], None]) -> None:
        self._cancel(name)

        @callback
        def _fire(_now: datetime) -> None:
            self._timers.pop(name, None)
            action()

        self._timers[name] = async_track_point_in_time(self.hass, _fire, when)

    def _later(self, name: str, seconds: float, action: Callable[[], None]) -> None:
        self._cancel(name)

        @callback
        def _fire(_now: datetime) -> None:
            self._timers.pop(name, None)
            action()

        self._timers[name] = async_call_later(self.hass, seconds, _fire)

    def _arm_timers(self) -> None:
        p = self.persist
        if p.overlay_active and p.overlay_until:
            self._at("overlay", p.overlay_until, self._overlay_expired)
        else:
            self._cancel("overlay")
        if p.boost_until:
            self._at("boost", p.boost_until, self._boost_expired)
        else:
            self._cancel("boost")
        if p.ext_window_until:
            self._at("extwin", p.ext_window_until, self._ext_window_expired)
        else:
            self._cancel("extwin")

    @callback
    def _ext_window_expired(self) -> None:
        _LOGGER.info("%s: Fenster (Thermostat) abgelaufen – zurück zum normalen Betrieb", self.name)
        self.persist.ext_window_until = None
        self._persist_changed()
        self.evaluate()

    def _clear_ext_window(self) -> None:
        """Eigene Bedienung beendet die als Fenster gewertete Abschaltung."""
        if self.persist.ext_window_until is not None:
            self.persist.ext_window_until = None
            self._cancel("extwin")

    @callback
    def _overlay_expired(self) -> None:
        _LOGGER.debug("%s: Overlay abgelaufen", self.name)
        self._clear_overlay()
        self._persist_changed()
        self.evaluate()

    @callback
    def _boost_expired(self) -> None:
        _LOGGER.debug("%s: Boost abgelaufen", self.name)
        self.persist.boost_until = None
        if self.persist.preset == PRESET_BOOST:
            self.persist.preset = None
        self._persist_changed()
        self.evaluate()

    def _clear_overlay(self) -> None:
        p = self.persist
        p.overlay_active = False
        p.overlay_temp = None
        p.overlay_until = None
        if p.hvac_mode == HVACMode.AUTO and p.preset != PRESET_BOOST:
            p.preset = None
        self._cancel("overlay")

    def _persist_changed(self) -> None:
        if self._on_persist_change:
            self._on_persist_change()

    # --- Eingänge --------------------------------------------------------
    @callback
    def _async_on_central(self) -> None:
        self.evaluate()

    @callback
    def _async_on_state(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        if entity_id in self.backends:
            self._handle_backend_change(event)
        if entity_id in self.windows:
            self._handle_window_change()
        self.evaluate()

    def _update_window_raw(self) -> None:
        open_sensors = [e for e in self.windows if self.hass.states.is_state(e, STATE_ON)]
        self.window.open_sensors = open_sensors
        self.window.raw_open = bool(open_sensors)

    def _handle_window_change(self) -> None:
        was_raw = self.window.raw_open
        self._update_window_raw()
        if self.window.raw_open == was_raw:
            return
        self._cancel("window")
        target = self.window.raw_open
        if target == self.window.effective_open:
            return
        delay = float(
            self._get(CONF_WINDOW_OPEN_DELAY, DEFAULT_WINDOW_OPEN_DELAY)
            if target
            else self._get(CONF_WINDOW_CLOSE_DELAY, DEFAULT_WINDOW_CLOSE_DELAY)
        )

        @callback
        def _apply() -> None:
            self.window.effective_open = target
            _LOGGER.debug("%s: Fenster wirksam %s", self.name, target)
            self.evaluate()

        if delay <= 0:
            self.window.effective_open = target
        else:
            self._later("window", delay, _apply)

    # --- Befehle (vom climate-Entity / Diensten) -------------------------
    def _overlay_until(self, minutes: float | None = None) -> datetime | None:
        now = dt_util.utcnow()
        if minutes is not None:
            return None if minutes <= 0 else now + timedelta(minutes=minutes)
        mode = self._get(CONF_OVERLAY_MODE, DEFAULT_OVERLAY_MODE)
        if mode == OVERLAY_TIMER:
            return now + timedelta(
                minutes=float(self._get(CONF_OVERLAY_MINUTES, DEFAULT_OVERLAY_MINUTES))
            )
        if mode == OVERLAY_NEXT_BLOCK:
            _base, _in_block, next_change = self._schedule_info()
            if next_change is None:
                # Kein (verfügbarer) Zeitplan: nie unbemerkt dauerhaft
                return now + timedelta(minutes=OVERLAY_FALLBACK_MINUTES)
            return next_change
        return None  # dauerhaft

    @callback
    def set_overlay(
        self,
        temperature: float | None,
        minutes: float | None = None,
        preset: str | None = None,
        max_minutes: float | None = None,
    ) -> None:
        """Manuelles Overlay im Auto-Modus (temperature None = aus).

        max_minutes begrenzt die Dauer.
        """
        self._clear_ext_window()
        p = self.persist
        p.overlay_active = True
        p.overlay_temp = (
            None
            if temperature is None
            else clamp(temperature, min(self.min_temp, self.frost), self.max_temp)
        )
        if p.overlay_temp is not None and preset not in NON_MANUAL_PRESETS:
            p.manual_temp = p.overlay_temp  # letzter Handwert (für auto -> heat)
        until = self._overlay_until(minutes)
        if max_minutes is not None:
            cap = dt_util.utcnow() + timedelta(minutes=max_minutes)
            until = cap if until is None else min(until, cap)
        p.overlay_until = until
        p.preset = preset
        self._arm_timers()
        self._persist_changed()
        self.evaluate()

    @callback
    def clear_overlay(self) -> None:
        """Overlay und Boost beenden."""
        self._clear_ext_window()
        self._clear_overlay()
        self.persist.boost_until = None
        if self.persist.preset == PRESET_BOOST:
            self.persist.preset = None
        self._arm_timers()
        self._persist_changed()
        self.evaluate()

    @callback
    def set_temperature(self, temperature: float, hvac_mode: str | None = None) -> None:
        """Solltemperatur (manuell) setzen.

        auto -> Overlay, heat -> dauerhafter Handwert, off -> Wechsel auf heat mit diesem
        Wert.
        """
        self._clear_ext_window()
        temperature = clamp(temperature, self.min_temp, self.max_temp)
        p = self.persist
        if hvac_mode == HVACMode.OFF:
            # ausdrücklich „aus“ mit Temperatur: aus bleiben, Wert für später merken
            self.set_hvac_mode(HVACMode.OFF, evaluate=False)
            p.manual_temp = temperature
            p.preset = None
            self._persist_changed()
            self.evaluate()
            return
        if hvac_mode is not None:
            self.set_hvac_mode(hvac_mode, evaluate=False)
        if p.hvac_mode == HVACMode.OFF:
            self.set_hvac_mode(HVACMode.HEAT, evaluate=False)
        if p.hvac_mode == HVACMode.AUTO:
            self.set_overlay(temperature)
            return
        p.manual_temp = temperature
        p.preset = None
        self._persist_changed()
        self.evaluate()

    def hand_value(self) -> float:
        """Wert für den Wechsel auf heat: nie Frostschutz/Fenster/Boost.

        Reihenfolge: aktives manuelles Overlay, letzter Handwert, aktueller Zeitplanwert,
        Komfort.
        """
        p = self.persist
        candidates: list[float | None] = []
        if p.hvac_mode == HVACMode.AUTO and p.overlay_active and p.preset not in NON_MANUAL_PRESETS:
            candidates.append(p.overlay_temp)
        candidates.append(p.manual_temp)
        candidates.append(self._schedule_info()[0])
        for value in candidates:
            if value is not None and value > self.frost + TEMP_TOLERANCE:
                return clamp(value, self.min_temp, self.max_temp)
        return clamp(self.comfort, self.min_temp, self.max_temp)

    @callback
    def set_hvac_mode(self, hvac_mode: str, evaluate: bool = True) -> None:
        """Betriebsart setzen.

        heat übernimmt den letzten Handwert; heat und off beenden Overlay und Boost.
        """
        self._clear_ext_window()
        p = self.persist
        old = p.hvac_mode
        if hvac_mode == HVACMode.HEAT and old != HVACMode.HEAT:
            p.manual_temp = self.hand_value()
        if hvac_mode in (HVACMode.HEAT, HVACMode.OFF) and old != hvac_mode:
            self._clear_overlay()
            p.boost_until = None
        if hvac_mode == HVACMode.AUTO:
            self._clear_overlay()
        if hvac_mode != old or (p.preset == PRESET_BOOST and p.boost_until is None):
            p.preset = None
        p.hvac_mode = HVACMode(hvac_mode)
        self._arm_timers()
        self._persist_changed()
        if evaluate:
            self.evaluate()

    @callback
    def set_preset(self, preset: str) -> None:
        """Preset setzen („zeitplan“ = zurück zum Zeitplan, „manuell“ = Wert halten)."""
        self._clear_ext_window()
        p = self.persist
        if preset == PRESET_BOOST:
            self.boost(None)
            return
        if preset == PRESET_SCHEDULE and p.hvac_mode != HVACMode.AUTO:
            self.set_hvac_mode(HVACMode.AUTO)
            return
        if preset in (PRESET_NONE, PRESET_SCHEDULE):
            self.clear_overlay()
            return
        if preset == PRESET_MANUAL:
            if p.hvac_mode == HVACMode.OFF:
                self.set_hvac_mode(HVACMode.HEAT)
            elif p.hvac_mode == HVACMode.AUTO and not p.overlay_active:
                # aktuellen (geplanten) Wert als manuelles Overlay festhalten
                planned = self.desired.planned if self.desired else None
                self.set_overlay(planned if planned is not None else self.hand_value())
            elif p.preset is not None:
                p.preset = None
                self._persist_changed()
                self.evaluate()
            return
        temp = self.preset_temp(preset)
        if p.hvac_mode == HVACMode.AUTO:
            self.set_overlay(temp, preset=preset)
            return
        p.hvac_mode = HVACMode.HEAT
        p.manual_temp = temp
        p.preset = preset
        self._persist_changed()
        self.evaluate()

    @callback
    def boost(self, minutes: float | None) -> None:
        """Boost: Höchsttemperatur für X Minuten."""
        self._clear_ext_window()
        mins = (
            float(minutes)
            if minutes
            else float(self._get(CONF_BOOST_MINUTES, DEFAULT_BOOST_MINUTES))
        )
        self.persist.boost_until = dt_util.utcnow() + timedelta(minutes=mins)
        self.persist.preset = PRESET_BOOST
        self._arm_timers()
        self._persist_changed()
        self.evaluate()

    # --- Berechnung ------------------------------------------------------
    def _schedule_info(self) -> tuple[float, bool | None, datetime | None]:
        """(Zeitplantemperatur, im Block?, nächster Wechsel)."""
        if not self.schedule:
            return self.comfort, None, None
        st = self.hass.states.get(self.schedule)
        if st is None or st.state in INVALID_STATES:
            return self.comfort, None, None
        next_change = _parse_dt(st.attributes.get("next_event"))
        if st.state == STATE_ON:
            attr = str(self._get(CONF_SCHEDULE_ATTR, DEFAULT_SCHEDULE_ATTR))
            block = _float(st.attributes.get(attr))
            temp = block if block is not None else self.comfort
            return clamp(temp, self.min_temp, self.max_temp), True, next_change
        return clamp(self.eco, self.min_temp, self.max_temp), False, next_change

    def compute(self) -> Desired:
        """Gewünschten Zustand berechnen (ohne Seiteneffekte)."""
        now = dt_util.utcnow()
        p = self.persist
        cs = self.central.state
        base, in_block, next_change = self._schedule_info()
        phase = cs.phase
        frost_or_off = self.frost if self._get(CONF_OFF_FROST, False) else None
        boost_active = p.boost_until is not None and p.boost_until > now

        # 1) geplanter Sollwert (ohne Übersteuerung durch Fenster/Boost)
        planned: float | None
        if p.hvac_mode == HVACMode.OFF:
            planned, planned_reason = frost_or_off, REASON_OFF
        elif p.hvac_mode == HVACMode.HEAT:
            planned = p.manual_temp if p.manual_temp is not None else self.comfort
            planned_reason = REASON_MANUAL
        elif p.overlay_active:
            planned, planned_reason = p.overlay_temp, REASON_MANUAL
        elif cs.gesperrt and cs.sperre_wirkung == LOCK_EFFECT_OFF:
            planned, planned_reason = frost_or_off, REASON_LOCK
        elif cs.abwesenheit_wirksam:
            planned = away_temperature(
                phase,
                base,
                self.comfort,
                self.central.setback,
                self.central.min_away,
                self.central.far_setback,
            )
            planned_reason = (
                REASON_PREHEAT if phase in (PHASE_COMFORT, PHASE_BETWEEN) else REASON_AWAY
            )
        else:
            planned, planned_reason = base, REASON_SCHEDULE

        low = min(self.min_temp, self.frost)
        if planned is not None:
            planned = clamp(planned, low, self.max_temp)

        # 2) Übersteuerungen: aus (ohne Boost) > Fenster > Boost > geplant
        target: float | None
        if p.hvac_mode == HVACMode.OFF and not boost_active:
            target, reason = planned, planned_reason
        elif self.window.effective_open:
            action = self._get(CONF_WINDOW_ACTION, WINDOW_ACTION_FROST)
            target = self.frost if action == WINDOW_ACTION_FROST else None
            reason = REASON_WINDOW
        elif self.ext_window_active(now):
            target, reason = self.frost, REASON_WINDOW_EXT
        elif boost_active:
            target, reason = self.max_temp, REASON_BOOST
        else:
            target, reason = planned, planned_reason

        if target is not None:
            target = clamp(target, low, self.max_temp)

        candidates = [
            t
            for t in (
                next_change if p.hvac_mode == HVACMode.AUTO else None,
                p.overlay_until if p.overlay_active else None,
                p.boost_until if boost_active else None,
                p.ext_window_until,
            )
            if t is not None and t > now
        ]
        return Desired(
            target=target,
            reason=reason,
            phase=phase if not cs.gesperrt else f"{phase} (gesperrt)",
            base=base,
            in_block=in_block,
            next_change=min(candidates) if candidates else None,
            planned=planned,
            planned_reason=planned_reason,
        )

    @callback
    def evaluate(self) -> None:
        """Neu berechnen, Anzeige aktualisieren, ggf. Synchronisation planen."""
        if not self._started:
            return
        new = self.compute()
        changed = self.desired is None or (
            new.target != self.desired.target or new.reason != self.desired.reason
        )
        self.desired = new
        if changed:
            self._release_off_holds()
            self._action_changed_at = dt_util.utcnow()
            # nach Ablauf der Haltezeit die (dann gemeldete) Heizaktivität anzeigen
            self._later("action", ACTION_HOLD_SECONDS + 1, self._notify_listeners)
            _LOGGER.debug("%s: Soll %s (%s)", self.name, new.target, new.reason)
        if (
            self.central.state.aktiv
            and self.hass.state is CoreState.running
            and self._needs_sync()
            and ("sync" not in self._timers or changed)
        ):
            self._later("sync", DEBOUNCE_SECONDS, self._sync_now)
        self._notify_listeners()

    @callback
    def _notify_listeners(self) -> None:
        for cb in list(self._listeners):
            cb()

    @property
    def reason(self) -> str:
        """Aktueller Grund (inkl. Pause)."""
        if not self.central.state.aktiv:
            return REASON_PAUSED
        return self.desired.reason if self.desired else REASON_SCHEDULE

    # --- Backend ---------------------------------------------------------
    def _backend_desired(self, st: State) -> tuple[str, float | None]:
        """Gewünschter Zustand eines Thermostats, normiert auf (heat|off, Soll).

        „heat“ steht für die Heiz-Betriebsart des Geräts (heat, heat_cool oder auto). Kennt
        das Gerät kein „off“, erhält es stattdessen seine niedrigste Solltemperatur.
        """
        assert self.desired is not None
        target = self.desired.target
        lo = _float(st.attributes.get(ATTR_MIN_TEMP))
        hi = _float(st.attributes.get(ATTR_MAX_TEMP))
        if target is None:
            if capabilities(st).can_off:
                return (HVACMode.OFF, None)
            target = lo if lo is not None else min(self.min_temp, self.frost)
        step = _float(st.attributes.get(ATTR_TARGET_TEMP_STEP)) or DEFAULT_TEMP_STEP
        target = round_step(target, step)
        if lo is not None:
            target = max(lo, target)
        if hi is not None:
            target = min(hi, target)
        return (HVACMode.HEAT, target)

    @staticmethod
    def _step(st: State) -> float:
        return _float(st.attributes.get(ATTR_TARGET_TEMP_STEP)) or DEFAULT_TEMP_STEP

    def _settled(
        self,
        track: BackendTrack,
        want: tuple[str, float | None],
        have: tuple[str, float | None],
        step: float,
    ) -> bool:
        """Kein erneutes Senden nötig, obwohl Soll und Ist abweichen?

        * Das Backend hat auf genau diesen Sollwert reagiert, aber anders gerundet
          (Ist hat sich seit dem Senden geändert) -> akzeptieren.
        * Das Backend hat mehrfach gar nicht reagiert -> nicht endlos wiederholen.
        """
        if have[0] == HVACMode.OFF and want[0] == HVACMode.HEAT and self.ext_window_active():
            return True  # Fenstererkennung des Thermostats: „aus“ genügt, nichts senden
        if track.last_sent is None or not self._same(track.last_sent, want):
            return False
        rounded = (
            have[0] == want[0] == HVACMode.HEAT
            and have[1] is not None
            and want[1] is not None
            and abs(have[1] - want[1]) <= step + TEMP_TOLERANCE
        )
        if rounded and track.before_send is not None and not self._same(have, track.before_send):
            return True
        return track.attempts >= MAX_SEND_ATTEMPTS

    @staticmethod
    def _backend_actual(st: State) -> tuple[str, float | None]:
        """Ist-Zustand, normiert: die Heiz-Betriebsart des Geräts gilt als „heat“."""
        if st.state == capabilities(st).heat_mode:
            return (HVACMode.HEAT, _float(st.attributes.get(ATTR_TEMPERATURE)))
        return (st.state, None)

    @staticmethod
    def _same(a: tuple[str, float | None], b: tuple[str, float | None]) -> bool:
        if a[0] != b[0]:
            return False
        if a[0] != HVACMode.HEAT:
            return True
        if a[1] is None or b[1] is None:
            return a[1] is None and b[1] is None
        return abs(a[1] - b[1]) <= TEMP_TOLERANCE

    def _needs_sync(self) -> bool:
        if self.desired is None:
            return False
        for ent in self.backends:
            st = self.hass.states.get(ent)
            if st is None or st.state in INVALID_STATES:
                self._tracks.setdefault(ent, BackendTrack()).pending = True
                continue
            want = self._backend_desired(st)
            have = self._backend_actual(st)
            track = self._tracks.setdefault(ent, BackendTrack())
            if not self._same(have, want) and not self._settled(track, want, have, self._step(st)):
                return True
        return False

    @callback
    def _sync_now(self) -> None:
        """Abweichende Backends ansteuern (Mindestabstand beachten)."""
        if not self._started or self.desired is None or not self.central.state.aktiv:
            return
        now = dt_util.utcnow()
        retry: float | None = None
        for ent in self.backends:
            track = self._tracks.setdefault(ent, BackendTrack())
            st = self.hass.states.get(ent)
            if st is None or st.state in INVALID_STATES:
                track.pending = True  # beim Wiederkommen nachziehen
                continue
            want = self._backend_desired(st)
            have = self._backend_actual(st)
            if self._same(have, want):
                track.pending = False
                track.attempts = 0
                track.settled_note = False
                continue
            if self._settled(track, want, have, self._step(st)):
                if not track.settled_note:
                    track.settled_note = True
                    _LOGGER.debug(
                        "%s: %s meldet %s statt %s – kein erneutes Senden",
                        self.name,
                        ent,
                        have,
                        want,
                    )
                continue
            wait = 0.0
            if track.last_sent_at is not None:
                wait = MIN_SEND_INTERVAL - (now - track.last_sent_at).total_seconds()
            if track.retry_at is not None:
                wait = max(wait, (track.retry_at - now).total_seconds())
            if wait > 0:
                retry = wait if retry is None else min(retry, wait)
                continue
            if track.last_sent is not None and self._same(track.last_sent, want):
                track.attempts += 1
            else:
                track.attempts = 1
                track.settled_note = False
            track.before_send = have
            track.last_sent = want
            track.last_sent_at = now
            track.pending = False
            self.entry.async_create_background_task(
                self.hass, self._async_send(ent, want), f"pm_heizung send {ent}"
            )
            # Kontrolle: hat das Backend reagiert? Sonst (begrenzt) erneut senden
            self._later(f"verify_{ent}", VERIFY_SECONDS, self._sync_now)
        if retry is not None:
            self._later("sync", retry + 0.1, self._sync_now)

    async def _async_send(self, entity_id: str, want: tuple[str, float | None]) -> None:
        ctx = Context()
        self._contexts.append(ctx.id)
        try:
            if want[0] == HVACMode.OFF:
                await self.hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_SET_HVAC_MODE,
                    {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
                    blocking=True,
                    context=ctx,
                )
            else:
                heat_mode = capabilities(self.hass.states.get(entity_id)).heat_mode
                await self.hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_SET_TEMPERATURE,
                    {
                        ATTR_ENTITY_ID: entity_id,
                        ATTR_TEMPERATURE: want[1],
                        ATTR_HVAC_MODE: heat_mode,
                    },
                    blocking=True,
                    context=ctx,
                )
                # hvac_mode in set_temperature reicht Home Assistant nur an das Gerät weiter;
                # nicht jede Integration wertet es aus (z. B. generic_thermostat). Steht das
                # Gerät danach nicht im Heizmodus, die Betriebsart nachschicken. Bei tado
                # nicht (verzögerte Cloud-Rückmeldung, jede Anfrage zählt gegen das Kontingent).
                after = self.hass.states.get(entity_id)
                if (
                    after is not None
                    and after.state not in INVALID_STATES
                    and after.state != heat_mode
                    and not is_tado(backend_kind(self.hass, entity_id))
                ):
                    await self.hass.services.async_call(
                        CLIMATE_DOMAIN,
                        SERVICE_SET_HVAC_MODE,
                        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: heat_mode},
                        blocking=True,
                        context=ctx,
                    )
            _LOGGER.debug("%s: %s -> %s", self.name, entity_id, want)
        except Exception as err:
            self._send_failed(entity_id, err)
            return
        track = self._tracks.setdefault(entity_id, BackendTrack())
        if track.fail_count:
            _LOGGER.info(
                "%s: Senden an %s wieder erfolgreich (nach %s Fehlern)",
                self.name,
                entity_id,
                track.fail_count,
            )
        track.fail_count = 0
        track.retry_at = None

    def _send_failed(self, entity_id: str, err: Exception) -> None:
        """Fehler: exponentieller Backoff (60 s … 15 min), gedrosselte Warnung."""
        now = dt_util.utcnow()
        track = self._tracks.setdefault(entity_id, BackendTrack())
        track.fail_count += 1
        delay = min(BACKOFF_START * 2 ** (track.fail_count - 1), BACKOFF_MAX)
        track.retry_at = now + timedelta(seconds=delay)
        track.off_hold = False
        track.pending = True
        track.last_sent = None  # Fehlversuch zählt nicht als gesendet
        track.attempts = 0
        if (
            track.fail_count == 1
            or track.last_warn is None
            or (now - track.last_warn).total_seconds() >= WARN_THROTTLE
        ):
            track.last_warn = now
            _LOGGER.warning(
                "%s: Senden an %s fehlgeschlagen (%s. Versuch, nächster in %.0f s): %s",
                self.name,
                entity_id,
                track.fail_count,
                delay,
                err,
            )
        else:
            _LOGGER.debug(
                "%s: Senden an %s erneut fehlgeschlagen (%s): %s",
                self.name,
                entity_id,
                track.fail_count,
                err,
            )
        self._later(f"retry_{entity_id}", delay + 0.1, self._sync_now)

    def _handle_backend_change(self, event: Event[EventStateChangedData]) -> None:
        """Rückkehr aus unavailable nachziehen; externe Änderungen erkennen."""
        entity_id = event.data["entity_id"]
        new = event.data["new_state"]
        old = event.data["old_state"]
        track = self._tracks.setdefault(entity_id, BackendTrack())
        if new is None or new.state in INVALID_STATES:
            track.pending = True
            return
        if old is None or old.state in INVALID_STATES:
            _LOGGER.debug("%s: %s wieder verfügbar – nachziehen", self.name, entity_id)
            track.pending = True
            track.attempts = 0
            return
        ctx = new.context
        if ctx.id in self._contexts or (ctx.parent_id and ctx.parent_id in self._contexts):
            return  # eigenes Echo
        before = self._backend_actual(old)
        after = self._backend_actual(new)
        if self._same(before, after):
            return  # nur Attribut-/Ist-Wert-Änderung
        track.attempts = 0  # Backend hat sich bewegt -> wieder senden dürfen
        if track.last_sent is not None and self._same(after, track.last_sent):
            return  # verspätetes Echo
        if (
            track.last_sent_at is not None
            and track.before_send is not None
            and (dt_util.utcnow() - track.last_sent_at).total_seconds() < ECHO_GRACE_SECONDS
            and (
                self._same(after, track.before_send)
                or (
                    track.last_sent is not None
                    and after[0] == track.last_sent[0] == HVACMode.HEAT
                    and after[1] is not None
                    and track.last_sent[1] is not None
                    and abs(after[1] - track.last_sent[1]) <= self._step(new) + TEMP_TOLERANCE
                )
            )
        ):
            if (
                after[0] == HVACMode.OFF
                and self.central.state.aktiv
                and not self.ext_window_active()
                and self._backend_desired(new)[0] == HVACMode.HEAT
            ):
                # „aus“ direkt nach dem eigenen Senden: veralteter Poll-Wert ODER das
                # Gerät/die Hersteller-Cloud schaltet sofort wieder aus -> zählt für den
                # Pingpong-Schutz mit
                self._reject_external_off(entity_id, track, bounce=True)
            return  # veralteter Poll-Wert bzw. vom Backend gerundetes Echo
        if self.desired is not None and self._same(after, self._backend_desired(new)):
            return
        if not self.central.state.aktiv:
            return  # pausiert: nichts übernehmen, nichts senden
        if after[0] == HVACMode.OFF:
            if self.ext_window_active():
                return  # passt zur laufenden Fensteröffnung
            if self.ext_off_as_window and self.persist.hvac_mode != HVACMode.OFF:
                self._start_ext_window(entity_id)
                return
            # „aus“ wird sonst nie übernommen: zurückstellen, melden, zählen
            self._reject_external_off(entity_id, track)
            return
        if self.ext_window_active():
            # Thermostat heizt wieder -> Fenstererkennung beendet: normal weiter
            _LOGGER.info("%s: %s wieder an – Fenster (Thermostat) beendet", self.name, entity_id)
            self._clear_ext_window()
            self._persist_changed()
            return
        if not self.adopt_external:
            return  # wird beim nächsten Sync überschrieben
        if after[0] != HVACMode.HEAT:
            return  # z. B. auto (Zeitplan des Geräts) – nicht übernehmen, überschreiben
        _LOGGER.info(
            "%s: Änderung direkt am Thermostat %s erkannt (%s) – als manuell übernommen",
            self.name,
            entity_id,
            after,
        )
        # Wert als eigenen Sollwert übernehmen, damit kein Rücksenden erfolgt
        track.last_sent = after
        p = self.persist
        if p.hvac_mode == HVACMode.AUTO:
            self.set_overlay(after[1])
        else:
            p.hvac_mode = HVACMode.HEAT
            p.manual_temp = after[1]
            p.preset = None
            self._persist_changed()

    def _start_ext_window(self, entity_id: str) -> None:
        """Externes „aus“ als Fensteröffnung (Fenstererkennung des Thermostats) werten."""
        until = dt_util.utcnow() + timedelta(minutes=EXT_WINDOW_MINUTES)
        _LOGGER.info(
            "%s: %s extern ausgeschaltet – als Fensteröffnung gewertet (Frostschutz bis %s)",
            self.name,
            entity_id,
            dt_util.as_local(until).strftime("%H:%M"),
        )
        self.persist.ext_window_until = until
        self._arm_timers()
        self._persist_changed()

    def _reject_external_off(
        self, entity_id: str, track: BackendTrack, bounce: bool = False
    ) -> None:
        """„Aus“ vom Backend (Gerät, Hersteller-App/-Cloud) im Auto-/Heat-Modus nicht übernehmen.

        Der eigene Sollwert bleibt, der nächste Abgleich stellt das Thermostat zurück.
        Pingpong-Schutz: ab 3 Ablehnungen in 30 min wird das Zurückstellen exponentiell
        zurückgehalten (5, 10, 20, 40, max. 60 min) bzw. bis zur nächsten eigenen Änderung
        ausgesetzt, und ein Reparaturhinweis erscheint. Nach 60 min Ruhe verschwindet er.
        """
        p = self.persist
        now = dt_util.utcnow()
        self._off_rejects.append(now)
        while (
            self._off_rejects and (now - self._off_rejects[0]).total_seconds() > OFF_REJECT_WINDOW
        ):
            self._off_rejects.popleft()
        recent = len(self._off_rejects)
        hold = 0.0
        if recent >= OFF_REJECT_LIMIT:
            self._off_hold_level += 1
            hold = min(OFF_HOLD_MAX, OFF_HOLD_START * 2 ** (self._off_hold_level - 1))
            until = now + timedelta(seconds=hold)
            if track.retry_at is None or track.retry_at < until:
                track.retry_at = until
            track.off_hold = True
            self._raise_issue(recent, hold)
        self._later("offquiet", OFF_QUIET_SECONDS, self._off_quiet)
        if bounce:
            # möglicherweise nur ein veralteter Poll-Wert: kein Zähler, keine Warnung
            return
        p.extern_off_rejected += 1
        if (
            self._extern_off_warned_at is None
            or (now - self._extern_off_warned_at).total_seconds() >= WARN_THROTTLE
        ):
            self._extern_off_warned_at = now
            _LOGGER.warning(
                "%s: %s wurde extern ausgeschaltet – nicht übernommen%s (bisher %s-mal). "
                "Ausschalten bitte über %s",
                self.name,
                entity_id,
                f", Zurückstellen pausiert {hold / 60:.0f} min"
                if hold
                else ", Sollwert wird wiederhergestellt",
                p.extern_off_rejected,
                f"climate.pm_{slugify(self.name)}",
            )
        else:
            _LOGGER.debug("%s: externes „aus“ an %s erneut abgelehnt", self.name, entity_id)
        self._persist_changed()

    def _release_off_holds(self) -> None:
        """Eigene Änderung des Sollwerts: zurückgehaltenes Senden wieder erlauben."""
        for track in self._tracks.values():
            if track.off_hold:
                track.off_hold = False
                track.retry_at = None

    @callback
    def _off_quiet(self) -> None:
        """Ruhe: Pingpong-Schutz zurücksetzen, Reparaturhinweis entfernen."""
        self._off_rejects.clear()
        self._off_hold_level = 0
        if self._issue_active:
            self._issue_active = False
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            _LOGGER.info("%s: seit 60 min kein externes „aus“ mehr – Hinweis entfernt", self.name)
        self._notify_listeners()

    @property
    def issue_id(self) -> str:
        return f"{ISSUE_EXT_OFF}_{self.subentry_id}"

    def _raise_issue(self, count: int, hold: float) -> None:
        self._issue_active = True
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self.issue_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_EXT_OFF,
            translation_placeholders={
                "raum": self.name,
                "anzahl": str(count),
                "pause": f"{hold / 60:.0f}",
                "entitaet": f"climate.pm_{slugify(self.name)}",
            },
        )

    # --- Anzeige ---------------------------------------------------------
    def current_temperature(self) -> float | None:
        """Ist-Temperatur (externer Sensor oder Mittelwert der Backends)."""
        if sensor := self.data.get(CONF_TEMP_SENSOR):
            st = self.hass.states.get(sensor)
            if st and (value := _float(st.state)) is not None:
                return value
        values = [
            v
            for e in self.backends
            if (st := self.hass.states.get(e))
            and (v := _float(st.attributes.get(ATTR_CURRENT_TEMPERATURE))) is not None
        ]
        return round(sum(values) / len(values), 2) if values else None

    def current_humidity(self) -> float | None:
        """Luftfeuchte (externer Sensor oder Backend)."""
        if sensor := self.data.get(CONF_HUMIDITY_SENSOR):
            st = self.hass.states.get(sensor)
            if st and (value := _float(st.state)) is not None:
                return value
        for e in self.backends:
            if (st := self.hass.states.get(e)) and (
                v := _float(st.attributes.get(ATTR_CURRENT_HUMIDITY))
            ) is not None:
                return v
        return None

    def _derived_action(self) -> HVACAction:
        """Aus eigenem Sollwert abgeleitete Heizaktivität."""
        if self.desired is None or self.desired.target is None:
            return HVACAction.OFF
        current = self.current_temperature()
        if current is not None and self.desired.target > current + ACTION_MARGIN:
            return HVACAction.HEATING
        return HVACAction.IDLE

    def _backends_confirmed(self) -> bool:
        """Alle verfügbaren Backends zeigen den gewünschten Zustand."""
        if self.desired is None:
            return False
        seen = False
        for ent in self.backends:
            st = self.hass.states.get(ent)
            if st is None or st.state in INVALID_STATES:
                continue
            seen = True
            want = self._backend_desired(st)
            have = self._backend_actual(st)
            if not self._same(have, want):
                track = self._tracks.get(ent)
                if track is None or not self._settled(track, want, have, self._step(st)):
                    return False
        return seen

    def hvac_action(self) -> HVACAction:
        """Heizaktivität – optimistisch, bis das Backend bestätigt.

        * eigener Sollwert „aus“ -> off (sofort, unabhängig vom Backend)
        * solange das Backend den Sollwert noch nicht übernommen hat bzw. innerhalb von
          120 s nach einer Änderung noch etwas anderes meldet -> abgeleitet
          (Soll > Ist + 0,2 -> heating, sonst idle)
        * danach die vom Backend gemeldete Aktivität (ohne Meldung: abgeleitet)
        """
        derived = self._derived_action()
        if derived == HVACAction.OFF and self.central.state.aktiv:
            return HVACAction.OFF
        actions = [
            st.attributes.get(ATTR_HVAC_ACTION)
            for e in self.backends
            if (st := self.hass.states.get(e)) and st.state not in INVALID_STATES
        ]
        reported_list = [a for a in actions if a]
        if not reported_list:
            return derived
        if HVACAction.HEATING in reported_list:
            reported = HVACAction.HEATING
        elif all(a == HVACAction.OFF for a in reported_list):
            reported = HVACAction.OFF
        else:
            reported = HVACAction.IDLE
        if not self.central.state.aktiv:
            return reported
        if not self._backends_confirmed():
            return derived
        changed = self._action_changed_at
        if (
            reported != derived
            and changed is not None
            and (dt_util.utcnow() - changed).total_seconds() < ACTION_HOLD_SECONDS
        ):
            return derived
        return reported

    def preset_mode(self) -> str:
        """Aktives Preset.

        auto ohne Overlay -> „zeitplan“, auto mit Overlay -> gewähltes Preset bzw.
        „manuell“, heat -> Preset bzw. „manuell“, off -> „none“, Boost hat Vorrang.
        """
        p = self.persist
        if p.boost_until and p.boost_until > dt_util.utcnow():
            return PRESET_BOOST
        if p.hvac_mode == HVACMode.OFF:
            return PRESET_NONE
        if p.hvac_mode == HVACMode.AUTO and not p.overlay_active:
            return PRESET_SCHEDULE
        if p.preset and p.preset not in (PRESET_BOOST, PRESET_NONE):
            return p.preset
        return PRESET_MANUAL

    def display_text(self) -> str:
        """Kurztext für Dashboards (Attribut „anzeige“) in der gewählten Sprache."""
        d = self.desired
        p = self.persist
        cs = self.central.state
        lang = self.central.language

        def tx(key: str, **values: Any) -> str:
            return t(lang, key, **values)

        def temp(value: float | None) -> str:
            return fmt_temp(value, lang)

        def when(value: datetime) -> str:
            return fmt_time(value, now, lang)

        if d is None:
            return tx("starting")
        if not cs.aktiv:
            return tx("paused")
        now = dt_util.utcnow()
        if d.reason == REASON_WINDOW:
            text = f"{tx('window_open')} · " + (tx("frost") if d.target is not None else tx("off"))
            if d.planned is not None and p.hvac_mode != HVACMode.OFF:
                text += f" ({tx('then', value=temp(d.planned))})"
            return text
        if d.reason == REASON_WINDOW_EXT and p.ext_window_until:
            until = tx("until", time=when(p.ext_window_until))
            return f"{tx('window_ext')} · {tx('frost')} {until}"
        if d.reason == REASON_BOOST and p.boost_until:
            return tx("boost_until", time=when(p.boost_until))
        if d.reason == REASON_OFF:
            return tx("Off") + (f" · {tx('frost')} {temp(d.target)}" if d.target else "")
        if d.reason == REASON_LOCK:
            return f"{tx('lock')} · " + self._lock_text()
        if d.reason == REASON_MANUAL:
            label = tx(PRESET_LABELS.get(p.preset or "", "manual"))
            value = tx("off") if d.target is None else temp(d.target)
            if p.hvac_mode == HVACMode.HEAT or not p.overlay_until:
                return f"{label} · {value} {tx('permanent')}"
            return f"{label} · {value} {tx('until', time=when(p.overlay_until))}"
        if d.reason == REASON_AWAY:
            return f"{tx('away')} · {temp(d.target)}"
        if d.reason == REASON_PREHEAT:
            return f"{tx('preheat')} · {temp(d.target)}"
        text = f"{tx('schedule')} · {temp(d.target)}"
        if d.next_change:
            text += f" {tx('until', time=when(d.next_change))}"
        return text

    def _lock_text(self) -> str:
        cs = self.central.state
        lang = self.central.language
        if cs.sperre_grund == LOCK_REASON_OUTDOOR:
            value = self.central.outdoor_temperature()
            if value is None:
                return t(lang, "lock_outdoor_unknown")
            return t(lang, "lock_outdoor", value=fmt_temp(value, lang))
        return t(lang, "lock_release")

    def _next_change_reason(self) -> str:
        d = self.desired
        p = self.persist
        if d is None:
            return "unbekannt"
        if p.ext_window_until and d.next_change == p.ext_window_until:
            return "fenster_extern_ende"
        if p.boost_until and d.next_change == p.boost_until:
            return "boost_ende"
        if p.hvac_mode == HVACMode.HEAT:
            return "manuell_dauerhaft"
        if p.hvac_mode == HVACMode.OFF:
            return "aus"
        if p.overlay_active:
            return "overlay_ende" if p.overlay_until else "overlay_dauerhaft"
        return "zeitplan" if d.next_change else "kein_zeitplan"

    def attributes(self) -> dict[str, Any]:
        """Zusatzattribute."""
        d = self.desired
        p = self.persist
        auto = p.hvac_mode == HVACMode.AUTO
        return {
            "grund": self.reason,
            "anzeige": self.display_text(),
            # in „aus“ der gemerkte Wert für das nächste Einschalten
            "eingestellt": p.manual_temp
            if p.hvac_mode == HVACMode.OFF
            else (d.planned if d else None),
            "phase": d.phase if d else PHASE_HOME,
            "zeitplan_temperatur": d.base if d else None,
            "im_zeitblock": d.in_block if d else None,
            "naechster_wechsel": d.next_change.isoformat() if d and d.next_change else None,
            "naechster_wechsel_grund": self._next_change_reason(),
            "overlay_bis": (
                (p.overlay_until.isoformat() if p.overlay_until else "dauerhaft")
                if auto and p.overlay_active
                else None
            ),
            "boost_bis": p.boost_until.isoformat() if p.boost_until else None,
            "fenster_offen": self.window.effective_open,
            "ziel_backend": "aus" if d and d.target is None else (d.target if d else None),
            "extern_aus_abgelehnt": p.extern_off_rejected,
            "fenster_extern_bis": p.ext_window_until.isoformat() if p.ext_window_until else None,
            "extern_aus_pause": self._off_hold_level > 0,
            "thermostat_typ": self._kind_summary(),
        }

    def _kind_summary(self) -> str | None:
        """Gerätetyp der Thermostate (bei mehreren unterschiedlichen: „gemischt“)."""
        kinds = set(self.backend_kinds().values())
        if not kinds:
            return None
        return kinds.pop() if len(kinds) == 1 else "gemischt"

    def diagnostics(self) -> dict[str, Any]:
        """Diagnosedaten."""
        return {
            "name": self.name,
            "data": self.data,
            "persist": self.persist.as_dict(),
            "window": {
                "raw_open": self.window.raw_open,
                "effective_open": self.window.effective_open,
                "open_sensors": self.window.open_sensors,
            },
            "attributes": self.attributes(),
            "backends": {
                e: {
                    "state": (st.state if (st := self.hass.states.get(e)) else None),
                    "last_sent": (tr := self._tracks.get(e)) and tr.last_sent,
                    "last_sent_at": tr.last_sent_at.isoformat() if tr and tr.last_sent_at else None,
                    "pending": tr.pending if tr else None,
                    "typ": backend_kind(self.hass, e),
                    "heizmodus": (c := capabilities(self.hass.states.get(e))).heat_mode,
                    "kann_aus": c.can_off,
                }
                for e in self.backends
            },
        }
