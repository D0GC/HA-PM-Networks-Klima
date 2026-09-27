"""Diagnose für PM Klima."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import PmHeizungConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PmHeizungConfigEntry
) -> dict[str, Any]:
    """Diagnosedaten (keine Geheimnisse enthalten, nur Entitäts-IDs)."""
    data = entry.runtime_data
    return {
        "options": dict(entry.options),
        "subentries": {
            sid: {"title": sub.title, "type": sub.subentry_type, "data": dict(sub.data)}
            for sid, sub in entry.subentries.items()
        },
        "central": data.central.diagnostics(),
        "rooms": {sid: room.diagnostics() for sid, room in data.rooms.items()},
        "luft": {sid: air.diagnostics() for sid, air in data.air.items()},
        "beratung": data.advisor.diagnostics() if data.advisor else None,
    }
