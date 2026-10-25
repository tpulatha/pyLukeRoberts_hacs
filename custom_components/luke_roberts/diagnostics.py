"""Diagnostics support for the Luke Roberts integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .coordinator import LukeRobertsConfigEntry

TO_REDACT = {CONF_ADDRESS, "title", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LukeRobertsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    lamp = coordinator.lamp
    state = coordinator.data
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
            },
            TO_REDACT,
        ),
        "lamp": {
            "is_on": state.is_on,
            "is_connected": lamp.is_connected,
            "current_scene_id": state.current_scene_id,
            "current_scene_name": state.current_scene_name,
            "scenes": [{"id": scene.id, "name": scene.name} for scene in state.scenes],
        },
        "bluetooth": {
            "address_present": bluetooth.async_address_present(
                hass, lamp.address, connectable=True
            ),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception).replace(
                lamp.address, "**REDACTED**"
            ),
        },
    }
