"""Config-Flow: Zentrale (Config-Entry) und Räume (Config-Subentries)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector as sel
from homeassistant.util import slugify
import voluptuous as vol

from .backend import backend_kind, is_tado
from .const import (
    CONF_ADOPT_EXTERNAL,
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
    CONF_AIR_OUTDOOR_HUM,
    CONF_AIR_OUTDOOR_TEMP,
    CONF_APPROACH,
    CONF_BOOST_MINUTES,
    CONF_CLIMATES,
    CONF_CO2_SENSOR,
    CONF_COMFORT,
    CONF_DIRECTION,
    CONF_DISTANCE,
    CONF_ECO,
    CONF_EXT_OFF_AS_WINDOW,
    CONF_FAR_SETBACK,
    CONF_FROST,
    CONF_FRSI,
    CONF_HUMIDITY_LIMIT,
    CONF_HUMIDITY_SENSOR,
    CONF_LANGUAGE,
    CONF_LEAVE_DELAY,
    CONF_LOCK_EFFECT,
    CONF_LOCK_HOLD,
    CONF_MAX,
    CONF_MIN,
    CONF_MIN_TEMP_AWAY,
    CONF_NAME,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_OFF_FROST,
    CONF_OUTDOOR,
    CONF_OUTDOOR_LIMIT,
    CONF_OVERLAY_MINUTES,
    CONF_OVERLAY_MODE,
    CONF_PERSONS,
    CONF_PM25_SENSOR,
    CONF_PREHEAT,
    CONF_PRESENCE,
    CONF_PURIFIER,
    CONF_PURIFIER_FILTERS,
    CONF_PURIFIER_HOLD,
    CONF_PURIFIER_PAUSE,
    CONF_PURIFIER_PRESET_AUTO,
    CONF_PURIFIER_PRESET_FAST,
    CONF_PURIFIER_PRESET_SLEEP,
    CONF_PURIFIER_PRESET_TURBO,
    CONF_RADIUS_FAR,
    CONF_RADIUS_MID,
    CONF_RADIUS_NEAR,
    CONF_RELEASE,
    CONF_SCHEDULE,
    CONF_SCHEDULE_ATTR,
    CONF_SETBACK,
    CONF_TEMP_SENSOR,
    CONF_WEATHER,
    CONF_WET_ROOM,
    CONF_WINDOW_ACTION,
    CONF_WINDOW_CLOSE_DELAY,
    CONF_WINDOW_OPEN_DELAY,
    CONF_WINDOWS,
    CONFIG_MINOR_VERSION,
    CONFIG_VERSION,
    DEFAULT_ADV_ALEXA,
    DEFAULT_ADV_INTERVAL,
    DEFAULT_ADV_PANEL,
    DEFAULT_ADV_PUSH,
    DEFAULT_APPROACH,
    DEFAULT_BOOST_MINUTES,
    DEFAULT_COMFORT,
    DEFAULT_ECO,
    DEFAULT_FAR_SETBACK,
    DEFAULT_FROST,
    DEFAULT_FRSI,
    DEFAULT_LANGUAGE,
    DEFAULT_LEAVE_DELAY,
    DEFAULT_LOCK_EFFECT,
    DEFAULT_LOCK_HOLD,
    DEFAULT_MAX,
    DEFAULT_MIN,
    DEFAULT_MIN_TEMP_AWAY,
    DEFAULT_NIGHT_END,
    DEFAULT_NIGHT_START,
    DEFAULT_OUTDOOR_LIMIT,
    DEFAULT_OVERLAY_MINUTES,
    DEFAULT_OVERLAY_MODE,
    DEFAULT_PREHEAT,
    DEFAULT_PURIFIER_HOLD,
    DEFAULT_PURIFIER_PAUSE,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DEFAULT_RADIUS_FAR,
    DEFAULT_RADIUS_MID,
    DEFAULT_RADIUS_NEAR,
    DEFAULT_SCHEDULE_ATTR,
    DEFAULT_SETBACK,
    DEFAULT_WINDOW_CLOSE_DELAY,
    DEFAULT_WINDOW_OPEN_DELAY,
    DOMAIN,
    LANGUAGES,
    LOCK_EFFECTS,
    NAME,
    OVERLAY_MODES,
    PREHEAT_LEVELS,
    PURIFIER_AUTO,
    PURIFIER_FAST,
    PURIFIER_SLEEP,
    PURIFIER_TURBO,
    SUBENTRY_ROOM,
    WINDOW_ACTION_FROST,
    WINDOW_ACTIONS,
)


def _num(low: float, high: float, step: float, unit: str, mode: str = "box") -> sel.NumberSelector:
    return sel.NumberSelector(
        sel.NumberSelectorConfig(
            min=low,
            max=high,
            step=step,
            mode=sel.NumberSelectorMode(mode),
            **({"unit_of_measurement": unit} if unit else {}),
        )
    )


def _entities(multiple: bool = False, **filt: Any) -> sel.EntitySelector:
    return sel.EntitySelector(
        sel.EntitySelectorConfig(
            filter=sel.EntityFilterSelectorConfig(**filt),  # type: ignore[typeddict-item]
            multiple=multiple,
        )
    )


def _select(options: list[str], key: str) -> sel.SelectSelector:
    return sel.SelectSelector(
        sel.SelectSelectorConfig(
            options=options, translation_key=key, mode=sel.SelectSelectorMode.DROPDOWN
        )
    )


TEMP = _num(5, 30, 0.5, "°C", "slider")

# ---------------------------------------------------------------------------
# Zentrale
# ---------------------------------------------------------------------------
STEP_PERSONS = vol.Schema(
    {
        vol.Required(CONF_PERSONS): _entities(True, domain="person"),
        vol.Optional(CONF_PRESENCE): sel.EntitySelector(
            sel.EntitySelectorConfig(domain=["input_boolean", "binary_sensor"], multiple=True)
        ),
        vol.Optional(CONF_DISTANCE): _entities(
            True, domain="sensor", device_class=SensorDeviceClass.DISTANCE
        ),
        vol.Optional(CONF_DIRECTION): _entities(True, domain="sensor"),
        vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): _select(LANGUAGES, CONF_LANGUAGE),
    }
)

STEP_AWAY = vol.Schema(
    {
        vol.Required(CONF_SETBACK, default=DEFAULT_SETBACK): _num(0.5, 10, 0.5, "K", "slider"),
        vol.Required(CONF_MIN_TEMP_AWAY, default=DEFAULT_MIN_TEMP_AWAY): _num(
            5, 20, 0.5, "°C", "slider"
        ),
        vol.Required(CONF_FAR_SETBACK, default=DEFAULT_FAR_SETBACK): _num(
            0, 10, 0.5, "K", "slider"
        ),
        vol.Required(CONF_PREHEAT, default=DEFAULT_PREHEAT): _select(PREHEAT_LEVELS, CONF_PREHEAT),
        vol.Required(CONF_RADIUS_NEAR, default=DEFAULT_RADIUS_NEAR): _num(0.1, 100, 0.1, "km"),
        vol.Required(CONF_RADIUS_MID, default=DEFAULT_RADIUS_MID): _num(0.1, 100, 0.1, "km"),
        vol.Required(CONF_RADIUS_FAR, default=DEFAULT_RADIUS_FAR): _num(0.1, 100, 0.1, "km"),
        vol.Required(CONF_APPROACH, default=DEFAULT_APPROACH): sel.BooleanSelector(),
        vol.Required(CONF_LEAVE_DELAY, default=DEFAULT_LEAVE_DELAY): _num(
            0, 60, 1, "min", "slider"
        ),
    }
)

STEP_LOCK = vol.Schema(
    {
        vol.Optional(CONF_OUTDOOR): _entities(
            domain="sensor", device_class=SensorDeviceClass.TEMPERATURE
        ),
        vol.Required(CONF_OUTDOOR_LIMIT, default=DEFAULT_OUTDOOR_LIMIT): _num(
            0, 30, 0.5, "°C", "slider"
        ),
        vol.Optional(CONF_RELEASE): sel.EntitySelector(
            sel.EntitySelectorConfig(domain=["input_boolean", "binary_sensor", "schedule"])
        ),
        vol.Required(CONF_LOCK_EFFECT, default=DEFAULT_LOCK_EFFECT): _select(
            LOCK_EFFECTS, CONF_LOCK_EFFECT
        ),
        vol.Required(CONF_LOCK_HOLD, default=DEFAULT_LOCK_HOLD): _num(0, 180, 1, "min"),
    }
)

STEP_AIR = vol.Schema(
    {
        vol.Optional(CONF_AIR_OUTDOOR_TEMP): _entities(
            domain="sensor", device_class=SensorDeviceClass.TEMPERATURE
        ),
        vol.Optional(CONF_AIR_OUTDOOR_HUM): _entities(
            domain="sensor", device_class=SensorDeviceClass.HUMIDITY
        ),
        vol.Optional(CONF_WEATHER): _entities(domain="weather"),
    }
)

STEP_ADVICE = vol.Schema(
    {
        vol.Required(CONF_ADV_PUSH, default=DEFAULT_ADV_PUSH): sel.BooleanSelector(),
        vol.Required(CONF_ADV_ALEXA, default=DEFAULT_ADV_ALEXA): sel.BooleanSelector(),
        vol.Required(CONF_ADV_PANEL, default=DEFAULT_ADV_PANEL): sel.BooleanSelector(),
        vol.Optional(CONF_ADV_PUSH_MAP): sel.TextSelector(sel.TextSelectorConfig(multiline=True)),
        vol.Optional(CONF_ADV_ALEXA_SCRIPT): _entities(domain="script"),
        vol.Optional(CONF_ADV_PANEL_SERVICE): sel.TextSelector(),
        vol.Optional(CONF_ADV_MUTE): sel.EntitySelector(
            sel.EntitySelectorConfig(
                domain=["input_boolean", "switch", "binary_sensor"], multiple=True
            )
        ),
        vol.Required(CONF_ADV_QUIET_START, default=DEFAULT_QUIET_START): sel.TimeSelector(),
        vol.Required(CONF_ADV_QUIET_END, default=DEFAULT_QUIET_END): sel.TimeSelector(),
        vol.Required(CONF_ADV_INTERVAL, default=DEFAULT_ADV_INTERVAL): _num(15, 1440, 15, "min"),
    }
)

CENTRAL_STEPS: dict[str, vol.Schema] = {
    "user": STEP_PERSONS,
    "abwesenheit": STEP_AWAY,
    "sperre": STEP_LOCK,
    "luft": STEP_AIR,
    "beratung": STEP_ADVICE,
}
CENTRAL_ORDER = ["user", "abwesenheit", "sperre", "luft", "beratung"]
# Diese Felder dürfen bewusst leer sein (leer = „keine“, nicht „Standard“)
KEEP_EMPTY = {CONF_ADV_MUTE, CONF_ADV_PUSH_MAP}


def _keys(schema: vol.Schema) -> set[str]:
    return {str(k) for k in schema.schema}


def _merge_step(options: dict[str, Any], schema: vol.Schema, user_input: Mapping[str, Any]) -> None:
    """Werte eines Schritts übernehmen; leere optionale Felder werden entfernt."""
    for key in _keys(schema):
        options.pop(key, None)
    options.update(
        {k: v for k, v in user_input.items() if k in KEEP_EMPTY or v not in (None, "", [])}
    )
    for key in KEEP_EMPTY & _keys(schema):
        if key not in user_input:
            options[key] = [] if key == CONF_ADV_MUTE else ""


def _validate_central(user_input: Mapping[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    directions = user_input.get(CONF_DIRECTION) or []
    distances = user_input.get(CONF_DISTANCE) or []
    if directions and not distances:
        errors[CONF_DIRECTION] = "richtung_ohne_abstand"
    return errors


class _CentralSteps:
    """Gemeinsame Schrittlogik für Config- und Options-Flow."""

    _options: dict[str, Any]

    def _show(self, step_id: str, errors: dict[str, str] | None = None) -> Any:
        schema = CENTRAL_STEPS[step_id]
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, self._options),  # type: ignore[attr-defined]
            errors=errors or {},
        )

    async def _handle(self, step_id: str, user_input: dict[str, Any] | None) -> Any:
        if user_input is None:
            return self._show(step_id)
        if step_id == "user" and (errors := _validate_central(user_input)):
            return self._show(step_id, errors)
        _merge_step(self._options, CENTRAL_STEPS[step_id], user_input)
        idx = CENTRAL_ORDER.index(step_id)
        if idx + 1 < len(CENTRAL_ORDER):
            return self._show(CENTRAL_ORDER[idx + 1])
        return self._finish()

    def _finish(self) -> Any:
        raise NotImplementedError


class PmHeizungConfigFlow(_CentralSteps, ConfigFlow, domain=DOMAIN):
    """Einrichtung der Zentrale."""

    VERSION = CONFIG_VERSION
    MINOR_VERSION = CONFIG_MINOR_VERSION

    def __init__(self) -> None:
        """Initialisieren."""
        self._options = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options-Flow."""
        return PmHeizungOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Räume als Subentries."""
        return {SUBENTRY_ROOM: RoomSubentryFlow}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Schritt 1: Personen & Proximity."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self._handle("user", user_input)  # type: ignore[no-any-return]

    async def async_step_abwesenheit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schritt 2: Abwesenheit & Vorheizen."""
        return await self._handle("abwesenheit", user_input)  # type: ignore[no-any-return]

    async def async_step_sperre(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Schritt 3: Sperre."""
        return await self._handle("sperre", user_input)  # type: ignore[no-any-return]

    async def async_step_luft(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Schritt 4: Außenwerte fürs Luftmodul."""
        return await self._handle("luft", user_input)  # type: ignore[no-any-return]

    async def async_step_beratung(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schritt 5: Beratung."""
        return await self._handle("beratung", user_input)  # type: ignore[no-any-return]

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title=NAME, data={}, options=self._options)


class PmHeizungOptionsFlow(_CentralSteps, OptionsFlow):
    """Zentrale nachträglich ändern."""

    def __init__(self) -> None:
        """Initialisieren."""
        self._options = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Einstieg."""
        self._options = dict(self.config_entry.options)
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Schritt 1."""
        return await self._handle("user", user_input)  # type: ignore[no-any-return]

    async def async_step_abwesenheit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schritt 2."""
        return await self._handle("abwesenheit", user_input)  # type: ignore[no-any-return]

    async def async_step_sperre(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Schritt 3."""
        return await self._handle("sperre", user_input)  # type: ignore[no-any-return]

    async def async_step_luft(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Schritt 4."""
        return await self._handle("luft", user_input)  # type: ignore[no-any-return]

    async def async_step_beratung(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schritt 5."""
        return await self._handle("beratung", user_input)  # type: ignore[no-any-return]

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._options)


# ---------------------------------------------------------------------------
# Raum (Subentry)
# ---------------------------------------------------------------------------
ROOM_STEP_DEVICES = vol.Schema(
    {
        vol.Required(CONF_NAME): sel.TextSelector(),
        vol.Required(CONF_CLIMATES): _entities(True, domain="climate"),
        vol.Optional(CONF_TEMP_SENSOR): _entities(
            domain="sensor", device_class=SensorDeviceClass.TEMPERATURE
        ),
        vol.Optional(CONF_HUMIDITY_SENSOR): _entities(
            domain="sensor", device_class=SensorDeviceClass.HUMIDITY
        ),
        vol.Optional(CONF_WINDOWS): sel.EntitySelector(
            sel.EntitySelectorConfig(
                filter=[
                    sel.EntityFilterSelectorConfig(domain="binary_sensor", device_class=dc)
                    for dc in (
                        BinarySensorDeviceClass.WINDOW,
                        BinarySensorDeviceClass.DOOR,
                        BinarySensorDeviceClass.OPENING,
                    )
                ],
                multiple=True,
            )
        ),
        vol.Optional(CONF_SCHEDULE): _entities(domain="schedule"),
        vol.Required(CONF_SCHEDULE_ATTR, default=DEFAULT_SCHEDULE_ATTR): sel.TextSelector(),
    }
)

ROOM_STEP_TEMPS = vol.Schema(
    {
        vol.Required(CONF_COMFORT, default=DEFAULT_COMFORT): TEMP,
        vol.Required(CONF_ECO, default=DEFAULT_ECO): TEMP,
        vol.Required(CONF_FROST, default=DEFAULT_FROST): _num(5, 12, 0.5, "°C", "slider"),
        vol.Required(CONF_MIN, default=DEFAULT_MIN): TEMP,
        vol.Required(CONF_MAX, default=DEFAULT_MAX): TEMP,
    }
)

ROOM_STEP_BEHAVIOUR = vol.Schema(
    {
        vol.Required(CONF_OVERLAY_MODE, default=DEFAULT_OVERLAY_MODE): _select(
            OVERLAY_MODES, CONF_OVERLAY_MODE
        ),
        vol.Required(CONF_OVERLAY_MINUTES, default=DEFAULT_OVERLAY_MINUTES): _num(
            5, 1440, 5, "min"
        ),
        vol.Required(CONF_BOOST_MINUTES, default=DEFAULT_BOOST_MINUTES): _num(5, 240, 5, "min"),
        vol.Required(CONF_WINDOW_OPEN_DELAY, default=DEFAULT_WINDOW_OPEN_DELAY): _num(
            0, 1800, 5, "s"
        ),
        vol.Required(CONF_WINDOW_CLOSE_DELAY, default=DEFAULT_WINDOW_CLOSE_DELAY): _num(
            0, 1800, 5, "s"
        ),
        vol.Required(CONF_WINDOW_ACTION, default=WINDOW_ACTION_FROST): _select(
            WINDOW_ACTIONS, CONF_WINDOW_ACTION
        ),
        vol.Required(CONF_OFF_FROST, default=False): sel.BooleanSelector(),
        vol.Required(CONF_ADOPT_EXTERNAL, default=True): sel.BooleanSelector(),
        # Vorschlag je Raum: an, wenn kein Fenstersensor konfiguriert ist
        vol.Optional(CONF_EXT_OFF_AS_WINDOW): sel.BooleanSelector(),
    }
)

ROOM_STEP_AIR = vol.Schema(
    {
        vol.Optional(CONF_CO2_SENSOR): _entities(
            domain="sensor", device_class=SensorDeviceClass.CO2
        ),
        vol.Optional(CONF_PM25_SENSOR): _entities(
            domain="sensor", device_class=SensorDeviceClass.PM25
        ),
        vol.Required(CONF_WET_ROOM, default=False): sel.BooleanSelector(),
        vol.Optional(CONF_HUMIDITY_LIMIT): _num(40, 90, 1, "%", "slider"),
        vol.Required(CONF_FRSI, default=DEFAULT_FRSI): _num(0.5, 0.95, 0.01, "", "box"),
        vol.Optional(CONF_PURIFIER): _entities(domain="fan"),
        vol.Optional(CONF_PURIFIER_FILTERS): _entities(True, domain="sensor"),
        vol.Required(CONF_NIGHT_START, default=DEFAULT_NIGHT_START): sel.TimeSelector(),
        vol.Required(CONF_NIGHT_END, default=DEFAULT_NIGHT_END): sel.TimeSelector(),
        vol.Required(CONF_PURIFIER_PAUSE, default=DEFAULT_PURIFIER_PAUSE): _num(5, 480, 5, "min"),
        vol.Required(CONF_PURIFIER_HOLD, default=DEFAULT_PURIFIER_HOLD): _num(1, 120, 1, "min"),
        # Preset-Namen je Stufe (leer = Standardname; Geräte ohne Presets: Drehzahl)
        vol.Optional(CONF_PURIFIER_PRESET_AUTO): sel.TextSelector(),
        vol.Optional(CONF_PURIFIER_PRESET_SLEEP): sel.TextSelector(),
        vol.Optional(CONF_PURIFIER_PRESET_FAST): sel.TextSelector(),
        vol.Optional(CONF_PURIFIER_PRESET_TURBO): sel.TextSelector(),
    }
)
PURIFIER_PRESET_DEFAULTS = {
    CONF_PURIFIER_PRESET_AUTO: PURIFIER_AUTO,
    CONF_PURIFIER_PRESET_SLEEP: PURIFIER_SLEEP,
    CONF_PURIFIER_PRESET_FAST: PURIFIER_FAST,
    CONF_PURIFIER_PRESET_TURBO: PURIFIER_TURBO,
}

ROOM_STEPS: dict[str, vol.Schema] = {
    "user": ROOM_STEP_DEVICES,
    "temperaturen": ROOM_STEP_TEMPS,
    "verhalten": ROOM_STEP_BEHAVIOUR,
    "luft": ROOM_STEP_AIR,
}
ROOM_ORDER = ["user", "temperaturen", "verhalten", "luft"]


class RoomSubentryFlow(ConfigSubentryFlow):
    """Raum anlegen oder ändern."""

    def __init__(self) -> None:
        """Initialisieren."""
        self._data: dict[str, Any] = {}
        self._error_placeholders: dict[str, str] = {"thermostat": "", "raum": ""}

    @property
    def _is_new(self) -> bool:
        return self.source == "user"

    def _show(self, step_id: str, errors: dict[str, str] | None = None) -> SubentryFlowResult:
        if step_id == "verhalten" and CONF_EXT_OFF_AS_WINDOW not in self._data:
            # Vorschlag: nur bei tado-Thermostaten (Fenstererkennung schaltet aus) ohne Fenstersensor
            climates = self._data.get(CONF_CLIMATES) or []
            tado = any(is_tado(backend_kind(self.hass, e)) for e in climates)
            self._data[CONF_EXT_OFF_AS_WINDOW] = tado and not self._data.get(CONF_WINDOWS)
        if step_id == "luft":
            for key, default in PURIFIER_PRESET_DEFAULTS.items():
                self._data.setdefault(key, default)
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(ROOM_STEPS[step_id], self._data),
            errors=errors or {},
            description_placeholders=self._error_placeholders,
        )

    def _validate(self, step_id: str, user_input: Mapping[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        if step_id == "user":
            name = str(user_input.get(CONF_NAME, "")).strip()
            if not slugify(name):
                errors[CONF_NAME] = "name_ungueltig"
            else:
                entry = self._get_entry()
                own_id = None if self._is_new else self._reconfigure_subentry_id
                for sub in entry.subentries.values():
                    if sub.subentry_id != own_id and slugify(sub.title) == slugify(name):
                        errors[CONF_NAME] = "name_vorhanden"
            registry = er.async_get(self.hass)
            own_id = None if self._is_new else self._reconfigure_subentry_id
            used: dict[str, str] = {}
            for sub in self._get_entry().subentries.values():
                if sub.subentry_id == own_id:
                    continue
                for ent in sub.data.get(CONF_CLIMATES) or []:
                    used[ent] = sub.title
            for ent in user_input.get(CONF_CLIMATES) or []:
                reg = registry.async_get(ent)
                if (reg and reg.platform == DOMAIN) or ent.startswith("climate.pm_"):
                    errors[CONF_CLIMATES] = "eigene_entitaet"
                elif ent in used:
                    errors[CONF_CLIMATES] = "thermostat_vergeben"
                    self._error_placeholders = {"thermostat": ent, "raum": used[ent]}
        elif step_id == "temperaturen":
            low, high = user_input[CONF_MIN], user_input[CONF_MAX]
            if low >= high:
                errors[CONF_MAX] = "min_max"
            elif not (
                low <= user_input[CONF_ECO] <= high and low <= user_input[CONF_COMFORT] <= high
            ):
                errors[CONF_COMFORT] = "ausser_bereich"
        return errors

    async def _handle(self, step_id: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        if user_input is None:
            return self._show(step_id)
        if errors := self._validate(step_id, user_input):
            self._data.update(user_input)
            return self._show(step_id, errors)
        _merge_step(self._data, ROOM_STEPS[step_id], user_input)
        idx = ROOM_ORDER.index(step_id)
        if idx + 1 < len(ROOM_ORDER):
            return self._show(ROOM_ORDER[idx + 1])
        name = str(self._data.pop(CONF_NAME)).strip()
        if self._is_new:
            return self.async_create_entry(title=name, data=self._data, unique_id=slugify(name))
        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            title=name,
            data=self._data,
            unique_id=slugify(name),
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Neuer Raum: Geräte."""
        return await self._handle("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Raum ändern."""
        sub = self._get_reconfigure_subentry()
        self._data = {**sub.data, CONF_NAME: sub.title}
        return self._show("user")

    async def async_step_temperaturen(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Temperaturen."""
        return await self._handle("temperaturen", user_input)

    async def async_step_verhalten(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Verhalten."""
        return await self._handle("verhalten", user_input)

    async def async_step_luft(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Luft (optional)."""
        return await self._handle("luft", user_input)
