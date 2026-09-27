"""Basis-Entitäten."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .central import Central
from .const import DOMAIN, NAME
from .room import RoomController

if TYPE_CHECKING:
    from .luft import AirRoom

MANUFACTURER = "PM Networks"
_LOGGER = logging.getLogger(__name__)


def supports_via_device_id(device_info_cls: Any, get_or_create: Any) -> bool:
    """Kennt diese HA-Version „via_device_id“ in DeviceInfo UND in async_get_or_create?

    Ab HA 2026.8 (geprüft am Quellcode 2026.9.3): DeviceInfo.via_device_id (Geräte-ID),
    „via_device“ ist veraltet (Entfernung 2027.8). Bis 2026.7 nur das Tupel „via_device“.
    Bewusst ohne Auswerten der Annotationen (Python 3.14 wertet sie verzögert aus):
    TypedDict-Schlüssel und Parameternamen aus dem Code-Objekt.
    """
    try:
        keys = set(device_info_cls.__required_keys__) | set(device_info_cls.__optional_keys__)
        func = getattr(get_or_create, "__wrapped__", get_or_create)
        code = func.__code__
        params = code.co_varnames[: code.co_argcount + code.co_kwonlyargcount]
    except (AttributeError, TypeError):
        return False
    return "via_device_id" in keys and "via_device_id" in params


HAS_VIA_DEVICE_ID = supports_via_device_id(dr.DeviceInfo, dr.DeviceRegistry.async_get_or_create)


def central_device(entry_id: str) -> DeviceInfo:
    """Gerät der Zentrale."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=NAME,
        manufacturer=MANUFACTURER,
        model="Zentrale",
        entry_type=DeviceEntryType.SERVICE,
    )


def child_device(central: Central, identifier: str, name: str, model: str) -> DeviceInfo:
    """Gerät unterhalb der Zentrale (via_device_id bzw. via_device je nach HA-Version)."""
    info: dict[str, Any] = {
        "identifiers": {(DOMAIN, identifier)},
        "name": name,
        "manufacturer": MANUFACTURER,
        "model": model,
        "entry_type": DeviceEntryType.SERVICE,
    }
    if HAS_VIA_DEVICE_ID:
        if central.device_id:
            info["via_device_id"] = central.device_id
    else:
        info["via_device"] = (DOMAIN, central.entry_id)
    return cast(DeviceInfo, info)


class RoomEntity(Entity):
    """Entität eines Raums (Heizung)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, room: RoomController, key: str) -> None:
        """Initialisieren."""
        self.room = room
        self._attr_unique_id = f"{room.subentry_id}_{key}"
        self._attr_device_info = child_device(
            room.central, room.subentry_id, f"{room.name} Heizung", "Raum"
        )

    async def async_added_to_hass(self) -> None:
        """Auf Raum-Updates hören."""
        await super().async_added_to_hass()
        self.async_on_remove(self.room.add_listener(self.async_write_ha_state))


class CentralEntity(Entity):
    """Entität der Zentrale."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, central: Central, key: str) -> None:
        """Initialisieren."""
        self.central = central
        self._attr_unique_id = f"{central.entry_id}_{key}"
        self._attr_device_info = central_device(central.entry_id)

    async def async_added_to_hass(self) -> None:
        """Auf Zentralen-Updates hören."""
        await super().async_added_to_hass()
        self.async_on_remove(self.central.add_listener(self.async_write_ha_state))


def safe_writer(entity: Entity) -> Callable[[], None]:
    """Zustand schreiben, Fehler nur protokollieren (Luft/Beratung sind isoliert)."""

    @callback
    def _write() -> None:
        try:
            entity.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Fehler beim Aktualisieren von %s", entity.entity_id)

    return _write


class AirEntity(Entity):
    """Entität des Luftmoduls eines Raums (eigenes Gerät „<Raum> Luft“)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, air: AirRoom, key: str) -> None:
        """Initialisieren."""
        self.air = air
        self._attr_unique_id = f"{air.room.subentry_id}_{key}"
        self._attr_device_info = child_device(
            air.room.central, f"{air.room.subentry_id}_luft", f"{air.room.name} Luft", "Luft"
        )

    async def async_added_to_hass(self) -> None:
        """Auf Luft-Updates hören."""
        await super().async_added_to_hass()
        unsub: CALLBACK_TYPE = self.air.add_listener(safe_writer(self))
        self.async_on_remove(unsub)
