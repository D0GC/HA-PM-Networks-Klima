"""Auszug aus homeassistant/helpers/device_registry.py (HA 2026.9.3, Apache-2.0).

Nur DeviceInfo und die Signatur von DeviceRegistry.async_get_or_create (Rumpf entfernt),
automatisch erzeugt, um die via_device_id-Erkennung gegen den echten Stand zu testen.
"""

from __future__ import annotations

from typing import Any, TypedDict

UNDEFINED: Any = object()  # Platzhalter (in HA: homeassistant.helpers.typing.UNDEFINED)


class DeviceInfo(TypedDict, total=False):
    """Entity device information for device registry."""

    configuration_url: str | URL | None
    connections: set[tuple[str, str]]
    entry_type: DeviceEntryType | None
    identifiers: set[tuple[str, str]]
    manufacturer: str | None
    model: str | None
    model_id: str | None
    name: str | None
    serial_number: str | None
    suggested_area: str | None
    sw_version: str | None
    hw_version: str | None
    translation_key: str | None
    translation_placeholders: Mapping[str, str] | None
    via_device_id: str


class DeviceRegistry:
    """Nur die Signatur."""

    def async_get_or_create(
        self,
        *,
        config_entry_id: str,
        config_subentry_id: str | UndefinedType | None = UNDEFINED,
        configuration_url: str | URL | UndefinedType | None = UNDEFINED,
        connections: set[tuple[str, str]] | UndefinedType | None = UNDEFINED,
        disabled_by: DeviceEntryDisabler | UndefinedType | None = UNDEFINED,
        entry_type: DeviceEntryType | UndefinedType | None = UNDEFINED,
        hw_version: str | UndefinedType | None = UNDEFINED,
        identifiers: set[tuple[str, str]] | UndefinedType | None = UNDEFINED,
        manufacturer: str | UndefinedType | None = UNDEFINED,
        model: str | UndefinedType | None = UNDEFINED,
        model_id: str | UndefinedType | None = UNDEFINED,
        name: str | UndefinedType | None = UNDEFINED,
        serial_number: str | UndefinedType | None = UNDEFINED,
        suggested_area: str | UndefinedType | None = UNDEFINED,
        sw_version: str | UndefinedType | None = UNDEFINED,
        translation_key: str | None = None,
        translation_placeholders: Mapping[str, str] | None = None,
        via_device_id: str | UndefinedType | None = UNDEFINED,
        **kwargs: Any,
    ) -> DeviceEntry: ...
