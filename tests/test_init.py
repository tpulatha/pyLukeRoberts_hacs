"""Tests for setup, unload, polling and diagnostics."""

from __future__ import annotations

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pylukeroberts import LukeRobertsConnectionError, LukeRobertsForbiddenError
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.luke_roberts.const import SCENE_REFRESH_INTERVAL, UPDATE_INTERVAL

from .conftest import ADDRESS


async def test_setup_and_unload(hass: HomeAssistant, setup_integration, lamp) -> None:
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    lamp.update_scenes.assert_awaited_once()
    lamp.update.assert_awaited_once_with(refresh_scenes=False, disconnect_after=True)
    assert hass.states.get("light.luvo").state == STATE_ON

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    lamp.stop.assert_awaited()


async def test_setup_device_not_found(hass: HomeAssistant, config_entry, lamp) -> None:
    with patch(
        "custom_components.luke_roberts.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_connection_error_retries(
    hass: HomeAssistant, config_entry, lamp
) -> None:
    lamp.update_scenes.side_effect = LukeRobertsConnectionError("timeout")
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_security_code_is_permanent(
    hass: HomeAssistant, config_entry, lamp
) -> None:
    lamp.update_scenes.side_effect = LukeRobertsForbiddenError(0xFC)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_poll_failure_marks_unavailable(
    hass: HomeAssistant, setup_integration, lamp, freezer: FrozenDateTimeFactory
) -> None:
    lamp.update.side_effect = LukeRobertsConnectionError("gone")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("light.luvo").state == STATE_UNAVAILABLE


async def test_scene_list_is_refreshed_periodically(
    hass: HomeAssistant, setup_integration, lamp
) -> None:
    coordinator = setup_integration.runtime_data
    coordinator._scenes_read_at -= SCENE_REFRESH_INTERVAL.total_seconds() + 1
    await coordinator.async_refresh()
    lamp.update.assert_awaited_with(refresh_scenes=True, disconnect_after=True)


async def test_diagnostics(hass: HomeAssistant, hass_client, setup_integration) -> None:
    diag = await get_diagnostics_for_config_entry(hass, hass_client, setup_integration)
    assert diag["entry"]["data"]["address"] == "**REDACTED**"
    assert diag["lamp"]["current_scene_name"] == "Lesen"
    assert len(diag["lamp"]["scenes"]) == 3
    assert ADDRESS not in str(diag)
