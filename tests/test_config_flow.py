"""Tests for the Luke Roberts config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pylukeroberts import LukeRobertsConnectionError, LukeRobertsForbiddenError
import pytest

from custom_components.luke_roberts.const import DOMAIN

from .conftest import ADDRESS, make_service_info

FLOW_LAMP = "custom_components.luke_roberts.config_flow.LuvoLamp"
DISCOVERED = "custom_components.luke_roberts.config_flow.async_discovered_service_info"


@pytest.fixture
def flow_lamp():
    with patch(FLOW_LAMP) as cls:
        lamp = cls.return_value
        lamp.ping = AsyncMock(return_value=2)
        lamp.stop = AsyncMock()
        yield lamp


@pytest.fixture(autouse=True)
def no_setup():
    with patch(
        "custom_components.luke_roberts.async_setup_entry", return_value=True
    ) as setup:
        yield setup


async def test_bluetooth_discovery(hass: HomeAssistant, flow_lamp) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Luvo"
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS
    flow_lamp.ping.assert_awaited_once()
    flow_lamp.stop.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (LukeRobertsForbiddenError(0xFC), "security_code"),
        (LukeRobertsConnectionError("nope"), "cannot_connect"),
    ],
)
async def test_bluetooth_confirm_errors_and_recovery(
    hass: HomeAssistant, flow_lamp, error, key
) -> None:
    flow_lamp.ping.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}

    flow_lamp.ping.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_already_configured(
    hass: HomeAssistant, config_entry, flow_lamp
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow(hass: HomeAssistant, flow_lamp) -> None:
    other = make_service_info("11:22:33:44:55:66", service_uuids=[])
    with patch(DISCOVERED, return_value=[make_service_info(), other]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        schema = result["data_schema"].schema[CONF_ADDRESS]
        assert list(schema.container) == [ADDRESS]  # non-Luke-Roberts filtered

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_user_flow_cannot_connect(hass: HomeAssistant, flow_lamp) -> None:
    flow_lamp.ping.side_effect = LukeRobertsConnectionError("nope")
    with patch(DISCOVERED, return_value=[make_service_info()]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    with patch(DISCOVERED, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
