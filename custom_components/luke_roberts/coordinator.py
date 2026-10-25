"""DataUpdateCoordinator for the Luke Roberts integration."""

from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pylukeroberts import (
    LampState,
    LukeRobertsError,
    LukeRobertsForbiddenError,
    LuvoLamp,
)

from .const import DOMAIN, SCENE_REFRESH_INTERVAL, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type LukeRobertsConfigEntry = ConfigEntry[LukeRobertsCoordinator]


class LukeRobertsCoordinator(DataUpdateCoordinator[LampState]):
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
            update_interval=UPDATE_INTERVAL,
        )
        self.lamp = lamp
        self._scenes_read_at = 0.0

    async def _async_setup(self) -> None:
        """Read the scene list once before the first poll."""
        try:
            await self.lamp.update_scenes()
        except LukeRobertsForbiddenError as err:
            # Permanent until the user removes the code in the app.
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="security_code"
            ) from err
        except LukeRobertsError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self._scenes_read_at = time.monotonic()

    async def _async_update_data(self) -> LampState:
        refresh_scenes = (
            time.monotonic() - self._scenes_read_at
            > SCENE_REFRESH_INTERVAL.total_seconds()
        )
        try:
            # Release the connection right after polling so the lamp stays
            # available to the Luke Roberts app.
            state = await self.lamp.update(
                refresh_scenes=refresh_scenes, disconnect_after=True
            )
        except LukeRobertsForbiddenError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="security_code"
            ) from err
        except LukeRobertsError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        if refresh_scenes:
            self._scenes_read_at = time.monotonic()
        return state

    def async_publish_lamp_state(self) -> None:
        """Push the library's state to all entities after a command."""
        self.async_set_updated_data(self.lamp.state)
