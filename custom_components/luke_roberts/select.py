"""Scene select for the Luke Roberts integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LukeRobertsConfigEntry, LukeRobertsCoordinator
from .entity import LukeRobertsEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the scene select."""
    async_add_entities([LukeRobertsSceneSelect(entry.runtime_data)])


class LukeRobertsSceneSelect(LukeRobertsEntity, SelectEntity):
    """Select the active scene, including the Off scene."""

    _attr_translation_key = "scene"

    def __init__(self, coordinator: LukeRobertsCoordinator) -> None:
        super().__init__(coordinator, "scene")

    @property
    def options(self) -> list[str]:
        return [scene.name for scene in self.coordinator.data.scenes]

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.current_scene_name

    async def async_select_option(self, option: str) -> None:
        for scene in self.coordinator.data.scenes:
            if scene.name == option:
                await self._async_lamp_call(
                    self.coordinator.lamp.select_scene(scene.id)
                )
                return
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_effect",
            translation_placeholders={"effect": option},
        )
