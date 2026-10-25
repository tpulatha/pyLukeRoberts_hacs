"""Base entity for the Luke Roberts integration."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pylukeroberts import LukeRobertsError, LukeRobertsForbiddenError

from .const import DOMAIN
from .coordinator import LukeRobertsCoordinator


class LukeRobertsEntity(CoordinatorEntity[LukeRobertsCoordinator]):
    """Common device info, availability and command handling."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LukeRobertsCoordinator, key: str | None) -> None:
        super().__init__(coordinator)
        lamp = coordinator.lamp
        mac = dr.format_mac(lamp.address)
        self._attr_unique_id = mac if key is None else f"{mac}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(dr.CONNECTION_BLUETOOTH, lamp.address)},
            name=lamp.name,
            manufacturer="Luke Roberts",
            model="Luvo",
        )
        self._last_scene_id = coordinator.data.current_scene_id

    @property
    def available(self) -> bool:
        return super().available and bluetooth.async_address_present(
            self.hass, self.coordinator.lamp.address, connectable=True
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        scene_id = self.coordinator.data.current_scene_id
        if scene_id != self._last_scene_id:
            self._last_scene_id = scene_id
            self._handle_scene_change()
        super()._handle_coordinator_update()

    @callback
    def _handle_scene_change(self) -> None:
        """Reset transient state; the lamp reverts it on a scene change."""

    async def _async_lamp_call(self, call: Awaitable[None]) -> None:
        """Run a lamp command, translate errors and publish the new state."""
        try:
            await call
        except LukeRobertsForbiddenError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="security_code"
            ) from err
        except LukeRobertsError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.coordinator.async_publish_lamp_state()
