"""Fixtures for Luke Roberts integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from habluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from pylukeroberts import LampState, Scene
from pylukeroberts.const import SERVICE_UUID
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luke_roberts.const import DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"

SCENES = (Scene(0, "Off"), Scene(1, "Lesen"), Scene(2, "Entspannen"))


def make_service_info(
    address: str = ADDRESS, service_uuids: list[str] | None = None
) -> BluetoothServiceInfoBleak:
    uuids = [SERVICE_UUID] if service_uuids is None else service_uuids
    return BluetoothServiceInfoBleak(
        name="Luvo",
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids,
        source="local",
        device=BLEDevice(address, "Luvo", None),
        advertisement=AdvertisementData(
            local_name="Luvo",
            manufacturer_data={},
            service_data={},
            service_uuids=uuids,
            tx_power=None,
            rssi=-60,
            platform_data=(),
        ),
        connectable=True,
        time=0,
        tx_power=None,
    )


class FakeLamp:
    """Stand-in for pylukeroberts.LuvoLamp with real state handling."""

    def __init__(self, *args, **kwargs) -> None:
        self.address = ADDRESS
        self.name = "Luvo"
        self.is_connected = False
        self.current_scene_id = 1
        self.scenes = list(SCENES)
        self.ping = AsyncMock(return_value=2)
        self.stop = AsyncMock()
        self.update_scenes = AsyncMock()
        self.update = AsyncMock(side_effect=self._update)
        self.select_scene = AsyncMock(side_effect=self._select_scene)
        self.switch_on = AsyncMock(side_effect=self._switch_on)
        self.switch_off = AsyncMock(side_effect=self._switch_off)
        self.set_brightness = AsyncMock()
        self.set_color_temperature = AsyncMock()
        self.set_immediate_light = AsyncMock()
        self.set_ble_device_and_advertisement_data = MagicMock()

    @property
    def is_on(self) -> bool:
        return self.current_scene_id != 0

    @property
    def state(self) -> LampState:
        name = next(
            (s.name for s in self.scenes if s.id == self.current_scene_id), None
        )
        return LampState(
            is_on=self.is_on,
            current_scene_id=self.current_scene_id,
            current_scene_name=name,
            scenes=tuple(self.scenes),
        )

    async def _update(self, **kwargs) -> LampState:
        return self.state

    async def _select_scene(self, scene_id: int) -> None:
        self.current_scene_id = scene_id

    async def _switch_on(self) -> None:
        self.current_scene_id = 1  # the lamp's default scene

    async def _switch_off(self) -> None:
        self.current_scene_id = 0


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom_components in every test."""
    return


@pytest.fixture(autouse=True)
def auto_enable_bluetooth(enable_bluetooth):
    """Set up the mocked Bluetooth stack in every test."""
    return


@pytest.fixture
def lamp() -> Generator[FakeLamp]:
    fake = FakeLamp()
    with (
        patch("custom_components.luke_roberts.LuvoLamp", return_value=fake),
        patch(
            "custom_components.luke_roberts.bluetooth.async_ble_device_from_address",
            return_value=BLEDevice(ADDRESS, "Luvo", None),
        ),
        patch(
            "custom_components.luke_roberts.entity.bluetooth.async_address_present",
            return_value=True,
        ),
    ):
        yield fake


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}, title="Luvo"
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, lamp: FakeLamp
) -> MockConfigEntry:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
