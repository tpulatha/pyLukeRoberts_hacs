"""DataUpdateCoordinator for the Luke Roberts integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from bleak.exc import BleakError
from pylukeroberts import LuvoLamp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

type LukeRobertsConfigEntry = ConfigEntry[LukeRobertsCoordinator]


class LukeRobertsCoordinator(DataUpdateCoordinator[None]):
    """Polls the lamp for its scene list and current scene."""

    config_entry: LukeRobertsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LukeRobertsConfigEntry,
        lamp: LuvoLamp,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {lamp.address}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.lamp = lamp

    async def _async_update_data(self) -> None:
        try:
            await self.lamp.update()
        except (BleakError, TimeoutError, OSError) as err:
            raise UpdateFailed(f"Unable to reach lamp {self.lamp.address}: {err}") from err
