"""Zentrale: Anwesenheit, Abwesenheitsphase, Vorheizen und Sperre."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.const import STATE_HOME, STATE_ON
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_APPROACH,
    CONF_DIRECTION,
    CONF_DISTANCE,
    CONF_FAR_SETBACK,
    CONF_LANGUAGE,
    CONF_LEAVE_DELAY,
    CONF_LOCK_EFFECT,
    CONF_LOCK_HOLD,
    CONF_MIN_TEMP_AWAY,
    CONF_OUTDOOR,
    CONF_OUTDOOR_LIMIT,
    CONF_PERSONS,
    CONF_PREHEAT,
    CONF_PRESENCE,
    CONF_RADIUS_FAR,
    CONF_RADIUS_MID,
    CONF_RADIUS_NEAR,
    CONF_RELEASE,
    CONF_SETBACK,
    DEFAULT_APPROACH,
    DEFAULT_FAR_SETBACK,
    DEFAULT_LEAVE_DELAY,
    DEFAULT_LOCK_EFFECT,
    DEFAULT_LOCK_HOLD,
    DEFAULT_MIN_TEMP_AWAY,
    DEFAULT_OUTDOOR_LIMIT,
    DEFAULT_PREHEAT,
    DEFAULT_RADIUS_FAR,
    DEFAULT_RADIUS_MID,
    DEFAULT_RADIUS_NEAR,
    DEFAULT_SETBACK,
    DOMAIN,
    LOCK_REASON_OUTDOOR,
    LOCK_REASON_RELEASE,
    PHASE_HOME,
    PHASES,
    STORAGE_VERSION,
)
from .logic import RANK_HOLD, RANK_HOME, compute_away_rank, distance_to_m, phase_name, radii_for
from .sprache import resolve_language, t

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CentralState:
    """Momentaufnahme der Zentrale."""

    aktiv: bool = True
    jemand_zuhause: bool = True
    phase: str = PHASE_HOME
    abwesend_seit: datetime | None = None
    absenkung_ab: datetime | None = None
    gesperrt: bool = False
    sperre_grund: str | None = None
    sperre_seit: datetime | None = None
    sperre_wechsel_wartet: str | None = None  # gemessener, noch gehaltener Sperrzustand
    sperre_wirkung: str = DEFAULT_LOCK_EFFECT
    abstaende_m: list[float] = field(default_factory=list)
    richtungen: list[str] = field(default_factory=list)
    grund: str = ""

    @property
    def abwesenheit_wirksam(self) -> bool:
        """Abwesenheits-/Vorheizlogik greift (niemand da, Verzögerung um, keine Sperre)."""
        return self.phase != PHASE_HOME and not self.gesperrt

    def as_dict(self) -> dict[str, Any]:
        """Für Diagnose/Attribute."""
        data = asdict(self)
        for key in ("abwesend_seit", "absenkung_ab", "sperre_seit"):
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data


def _parse(value: Any) -> datetime | None:
    if isinstance(value, str) and (parsed := dt_util.parse_datetime(value)):
        return dt_util.as_utc(parsed)
    return None


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


class Central:
    """Event-getriebene Zentrale (kein Polling)."""

    def __init__(self, hass: HomeAssistant, entry_id: str, options: Mapping[str, Any]) -> None:
        """Initialisieren."""
        self.hass = hass
        self.entry_id = entry_id
        self.options = dict(options)
        self.state = CentralState()
        self.device_id: str | None = None  # Geräte-ID der Zentrale (via_device_id)
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._timer: CALLBACK_TYPE | None = None
        self._lock_timer: CALLBACK_TYPE | None = None
        self._last_rank = -1
        # Neustartsicher gespeichert:
        self._empty_since: datetime | None = None  # nur beim Übergang jemand -> niemand gesetzt
        self._presence_known: dict[str, bool] = {}  # letzter gültiger Wert je Präsenz-Entität
        self._lock: str | None = None  # wirksamer Sperrgrund
        self._lock_changed_at: datetime | None = None
        self._lock_initialized = False
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.zentrale"
        )

    # --- Konfiguration ---------------------------------------------------
    @property
    def language(self) -> str:
        """Sprache der erzeugten Texte („de“ oder „en“)."""
        return resolve_language(self.hass, self.options.get(CONF_LANGUAGE))

    def opt(self, key: str, default: Any) -> Any:
        """Option mit Standardwert (leere Werte = Standard)."""
        value = self.options.get(key)
        return default if value is None or value == "" else value

    @property
    def persons(self) -> list[str]:
        return _as_list(self.options.get(CONF_PERSONS))

    @property
    def presence(self) -> list[str]:
        return _as_list(self.options.get(CONF_PRESENCE))

    @property
    def distances(self) -> list[str]:
        return _as_list(self.options.get(CONF_DISTANCE))

    @property
    def directions(self) -> list[str]:
        return _as_list(self.options.get(CONF_DIRECTION))

    @property
    def setback(self) -> float:
        return float(self.opt(CONF_SETBACK, DEFAULT_SETBACK))

    @property
    def min_away(self) -> float:
        return float(self.opt(CONF_MIN_TEMP_AWAY, DEFAULT_MIN_TEMP_AWAY))

    @property
    def far_setback(self) -> float:
        return float(self.opt(CONF_FAR_SETBACK, DEFAULT_FAR_SETBACK))

    def outdoor_temperature(self) -> float | None:
        """Aktuelle Außentemperatur des Sperre-Sensors (None = unbekannt)."""
        if not (outdoor := self.options.get(CONF_OUTDOOR)):
            return None
        st = self.hass.states.get(outdoor)
        try:
            return float(st.state) if st else None
        except (TypeError, ValueError):
            return None

    def tracked_entities(self) -> list[str]:
        """Alle Entitäten, auf deren Änderung reagiert wird."""
        ents = self.persons + self.presence + self.distances + self.directions
        for key in (CONF_OUTDOOR, CONF_RELEASE):
            if value := self.options.get(key):
                ents.append(value)
        return list(dict.fromkeys(ents))

    # --- Lebenszyklus ----------------------------------------------------
    async def async_start(self) -> None:
        """Gespeicherten Zustand laden und Listener anhängen."""
        stored = await self._store.async_load() or {}
        self.state.aktiv = bool(stored.get("aktiv", True))
        self._last_rank = int(stored.get("last_rank", -1))
        self._empty_since = _parse(stored.get("empty_since"))
        self._presence_known = {
            str(k): bool(v) for k, v in (stored.get("presence_known") or {}).items()
        }
        if (phase := stored.get("phase")) in PHASES:
            self.state.phase = phase
        if "lock" in stored:
            self._lock = stored.get("lock")
            self._lock_changed_at = _parse(stored.get("lock_changed_at"))
            self._lock_initialized = True
        if ents := self.tracked_entities():
            self._unsubs.append(
                async_track_state_change_event(self.hass, ents, self._async_on_change)
            )
        self._recompute(notify=False)

    @callback
    def async_stop(self) -> None:
        """Listener lösen."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_timer()
        if self._lock_timer is not None:
            self._lock_timer()
            self._lock_timer = None

    @callback
    def add_listener(self, cb: Callable[[], None]) -> CALLBACK_TYPE:
        """Listener für Zustandsänderungen registrieren."""
        self._listeners.append(cb)

        @callback
        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    @callback
    def set_active(self, active: bool) -> None:
        """Hauptschalter setzen."""
        if self.state.aktiv == active:
            return
        self.state.aktiv = active
        self._save()
        self._notify()

    @callback
    def async_reevaluate(self) -> None:
        """Neu berechnen und alle Räume informieren."""
        self._recompute(notify=False)
        self._notify()

    # --- intern ----------------------------------------------------------
    @callback
    def _async_on_change(self, event: Event[EventStateChangedData]) -> None:
        self._recompute()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer()
            self._timer = None

    @callback
    def _async_timer_fired(self, _now: datetime) -> None:
        self._timer = None
        self._recompute()

    def _save(self) -> None:
        self._store.async_delay_save(self._data_to_store, 1)

    def _data_to_store(self) -> dict[str, Any]:
        return {
            "aktiv": self.state.aktiv,
            "last_rank": self._last_rank,
            "empty_since": self._empty_since.isoformat() if self._empty_since else None,
            "presence_known": self._presence_known,
            "phase": self.state.phase,
            "lock": self._lock,
            "lock_changed_at": (
                self._lock_changed_at.isoformat() if self._lock_changed_at else None
            ),
        }

    @callback
    def _async_lock_timer_fired(self, _now: datetime) -> None:
        self._lock_timer = None
        self._recompute()

    def _effective_lock(self, now: datetime) -> str | None:
        """Sperre mit Mindesthaltezeit (keine Hysterese an der Grenze selbst).

        Wechsel, die nur die Außentemperatur betreffen, werden erst übernommen, wenn der
        bisherige Sperrzustand mindestens die Haltezeit bestand. Die Freigabe-Entität
        (manueller Schalter) wirkt sofort.
        """
        raw = self._lock_reason()
        self.state.sperre_wechsel_wartet = None
        if self._lock_timer is not None:
            self._lock_timer()
            self._lock_timer = None
        if not self._lock_initialized:
            self._lock_initialized = True
            self._lock, self._lock_changed_at = raw, now
            self._save()
            return raw
        if raw == self._lock:
            return raw
        hold = timedelta(minutes=float(self.opt(CONF_LOCK_HOLD, DEFAULT_LOCK_HOLD)))
        release_involved = LOCK_REASON_RELEASE in (raw, self._lock)
        since = self._lock_changed_at
        if release_involved or since is None or now - since >= hold:
            self._lock, self._lock_changed_at = raw, now
            self._save()
            return raw
        self.state.sperre_wechsel_wartet = raw or "frei"
        self._lock_timer = async_track_point_in_time(
            self.hass, self._async_lock_timer_fired, since + hold
        )
        return self._lock

    @callback
    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    def _lock_reason(self) -> str | None:
        release = self.options.get(CONF_RELEASE)
        if release and not self.hass.states.is_state(release, STATE_ON):
            return LOCK_REASON_RELEASE
        if outdoor := self.options.get(CONF_OUTDOOR):
            st = self.hass.states.get(outdoor)
            try:
                value = float(st.state) if st else None
            except (TypeError, ValueError):
                value = None  # unbekannter Wert sperrt nicht
            limit = float(self.opt(CONF_OUTDOOR_LIMIT, DEFAULT_OUTDOOR_LIMIT))
            if value is not None and value >= limit:  # keine Hysterese
                return LOCK_REASON_OUTDOOR
        return None

    @callback
    def _recompute(self, notify: bool = True) -> None:
        self._cancel_timer()
        hass = self.hass
        now = dt_util.utcnow()
        old = self.state.as_dict()

        uses_helpers = bool(self.presence)
        presence_list = self.presence if uses_helpers else self.persons
        home_state = STATE_ON if uses_helpers else STATE_HOME
        # unknown/unavailable ändert nichts: es gilt der letzte gültige Wert der Entität
        for ent in presence_list:
            st = hass.states.get(ent)
            if st is not None and st.state not in ("unknown", "unavailable"):
                self._presence_known[ent] = st.state == home_state
        known = [self._presence_known[e] for e in presence_list if e in self._presence_known]
        # Fail-safe: ist noch gar keine Anwesenheit bekannt, gilt „zuhause“
        someone_home = not known or any(known)
        delay = timedelta(minutes=float(self.opt(CONF_LEAVE_DELAY, DEFAULT_LEAVE_DELAY)))
        persist_before = self._data_to_store()

        distances: list[float] = []
        for ent in self.distances:
            st = hass.states.get(ent)
            distances.append(
                distance_to_m(
                    st.state if st else None,
                    st.attributes.get("unit_of_measurement") if st else None,
                )
            )
        directions = [
            (st.state if (st := hass.states.get(e)) else "unknown") for e in self.directions
        ]

        lock_reason = self._effective_lock(now)
        s = self.state
        s.jemand_zuhause = someone_home
        s.abstaende_m = distances
        s.richtungen = directions
        s.gesperrt = lock_reason is not None
        s.sperre_grund = lock_reason
        s.sperre_seit = self._lock_changed_at
        s.sperre_wirkung = str(self.opt(CONF_LOCK_EFFECT, DEFAULT_LOCK_EFFECT))

        if someone_home:
            self._empty_since = None
            s.abwesend_seit = None
            s.absenkung_ab = None
            s.phase = PHASE_HOME
            self._last_rank = -1
            s.grund = t(self.language, "central_home")
        else:
            if self._empty_since is None:
                # Übergang jemand -> niemand (nur hier wird „leer seit“ gesetzt)
                self._empty_since = now
            s.abwesend_seit = self._empty_since
            start = self._empty_since + delay
            s.absenkung_ab = start
            if now < start:
                # Während der Verzögerung gilt die zuletzt gültige Phase weiter
                s.grund = t(self.language, "central_leaving")
                self._timer = async_track_point_in_time(hass, self._async_timer_fired, start)
            else:
                radii = radii_for(
                    str(self.opt(CONF_PREHEAT, DEFAULT_PREHEAT)),
                    float(self.opt(CONF_RADIUS_NEAR, DEFAULT_RADIUS_NEAR)),
                    float(self.opt(CONF_RADIUS_MID, DEFAULT_RADIUS_MID)),
                    float(self.opt(CONF_RADIUS_FAR, DEFAULT_RADIUS_FAR)),
                )
                result = compute_away_rank(
                    distances,
                    directions,
                    radii,
                    bool(self.opt(CONF_APPROACH, DEFAULT_APPROACH)),
                    self._last_rank,
                )
                # Ohne Proximity-Sensoren: einfache Absenkung (Phase halten)
                rank = min(result.rank, RANK_HOME - 1) if distances else RANK_HOLD
                s.phase = phase_name(rank)
                self._last_rank = rank
                s.grund = t(self.language, "central_away", phase=s.phase)
        if s.gesperrt:
            s.grund += t(
                self.language,
                "central_locked_release"
                if lock_reason == LOCK_REASON_RELEASE
                else "central_locked_outdoor",
            )
        if self._data_to_store() != persist_before:
            self._save()
        if notify and s.as_dict() != old:
            _LOGGER.debug("Zentrale: %s", s.grund)
            self._notify()

    def diagnostics(self) -> dict[str, Any]:
        """Diagnosedaten."""
        return {"state": self.state.as_dict(), "last_rank": self._last_rank}
