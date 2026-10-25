"""Light platform for the Luke Roberts integration."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value
from pylukeroberts import Downlight, Uplight
from pylukeroberts.const import MAX_KELVIN, MIN_KELVIN, SCENE_OFF

from .const import DOMAIN
from .coordinator import LukeRobertsConfigEntry, LukeRobertsCoordinator
from .entity import LukeRobertsEntity

# One BLE lamp, one conversation at a time.
PARALLEL_UPDATES = 1

DEFAULT_UPLIGHT_HS = (30.0, 100.0)
DEFAULT_DOWNLIGHT_KELVIN = 3000


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Luke Roberts lights from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            LukeRobertsLight(coordinator),
            LukeRobertsUplight(coordinator),
            LukeRobertsDownlight(coordinator),
        ]
    )


def brightness_to_percent(brightness: int) -> int:
    """HA brightness 1..255 to 1..100 %, never rounding a lit lamp to 0 %."""
    return math.ceil(brightness_to_value((1, 100), brightness))


def saturation_to_byte(saturation: float) -> int:
    """HA saturation 0..100 to the lamp's 0..255."""
    return round(saturation * 255 / 100)


def clamp_kelvin(kelvin: int) -> int:
    return min(max(int(kelvin), MIN_KELVIN), MAX_KELVIN)


class LukeRobertsLight(LukeRobertsEntity, LightEntity):
    """The lamp as a whole.

    Brightness dims the entire scene, color temperature drives the downlight,
    HS color drives the uplight. The lamp does not report brightness or color
    back, so those attributes are optimistic and cleared on scene changes;
    on/off and the active scene are read from the lamp.
    """

    _attr_name = None
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(self, coordinator: LukeRobertsCoordinator) -> None:
        super().__init__(coordinator, None)
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_brightness = None
        self._attr_color_temp_kelvin = None
        self._attr_hs_color = None

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_on

    @property
    def effect(self) -> str | None:
        return self.coordinator.data.current_scene_name

    @property
    def effect_list(self) -> list[str]:
        return [
            scene.name
            for scene in self.coordinator.data.scenes
            if scene.id != SCENE_OFF
        ]

    @callback
    def _handle_scene_change(self) -> None:
        self._attr_brightness = None
        self._attr_color_temp_kelvin = None
        self._attr_hs_color = None
        self._attr_color_mode = ColorMode.COLOR_TEMP

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lamp on, optionally selecting a scene or adjusting it."""
        lamp = self.coordinator.lamp
        scene_id: int | None = None
        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            scene_id = next(
                (
                    scene.id
                    for scene in self.coordinator.data.scenes
                    if scene.name == effect and scene.id != SCENE_OFF
                ),
                None,
            )
            if scene_id is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_effect",
                    translation_placeholders={"effect": str(effect)},
                )
        kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        if kelvin is not None:
            kelvin = clamp_kelvin(kelvin)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        async def _apply() -> None:
            if scene_id is not None:
                await lamp.select_scene(scene_id)
            elif not lamp.is_on:
                await lamp.switch_on()
            if kelvin is not None:
                await lamp.set_color_temperature(kelvin)
            if hs_color is not None:
                # HS sets the uplight color at full uplight brightness; the
                # overall level is controlled by brightness below.
                await lamp.set_immediate_light(
                    uplight=Uplight(
                        hue=hs_color[0],
                        saturation=saturation_to_byte(hs_color[1]),
                        brightness=255,
                    )
                )
            if brightness is not None:
                await lamp.set_brightness(brightness_to_percent(brightness))

        await self._async_lamp_call(_apply())

        if kelvin is not None:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp_kelvin = kelvin
        if hs_color is not None:
            self._attr_color_mode = ColorMode.HS
            self._attr_hs_color = hs_color
        if brightness is not None:
            self._attr_brightness = brightness
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lamp off."""
        await self._async_lamp_call(self.coordinator.lamp.switch_off())


class LukeRobertsTransientLight(LukeRobertsEntity, LightEntity):
    """Base for the Immediate Light sub-packets.

    Changes are transient: the lamp reverts them on scene change or
    power-down and cannot report them back, so state is assumed and reset to
    unknown when the scene changes.
    """

    _attr_assumed_state = True

    def __init__(self, coordinator: LukeRobertsCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._attr_is_on = False if not coordinator.data.is_on else None
        self._attr_brightness = 255

    @callback
    def _handle_scene_change(self) -> None:
        self._attr_is_on = False if not self.coordinator.data.is_on else None


class LukeRobertsUplight(LukeRobertsTransientLight):
    """The indirect uplight, with its own brightness and HS color."""

    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

    def __init__(self, coordinator: LukeRobertsCoordinator) -> None:
        super().__init__(coordinator, "uplight")
        self._attr_hs_color = DEFAULT_UPLIGHT_HS

    def _packet(self, hs_color: tuple[float, float], brightness: int) -> Uplight:
        return Uplight(
            hue=hs_color[0],
            saturation=saturation_to_byte(hs_color[1]),
            brightness=brightness,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the uplight color and brightness."""
        hs_color = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness) or 255
        await self._async_lamp_call(
            self.coordinator.lamp.set_immediate_light(
                uplight=self._packet(hs_color, brightness)
            )
        )
        self._attr_is_on = True
        self._attr_hs_color = hs_color
        self._attr_brightness = brightness
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the uplight off by setting its brightness to zero."""
        assert self._attr_hs_color is not None
        await self._async_lamp_call(
            self.coordinator.lamp.set_immediate_light(
                uplight=self._packet(self._attr_hs_color, 0)
            )
        )
        self._attr_is_on = False
        self.async_write_ha_state()


class LukeRobertsDownlight(LukeRobertsTransientLight):
    """The direct downlight, with its own brightness and color temperature."""

    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(self, coordinator: LukeRobertsCoordinator) -> None:
        super().__init__(coordinator, "downlight")
        self._attr_color_temp_kelvin = DEFAULT_DOWNLIGHT_KELVIN

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the downlight color temperature and brightness."""
        kelvin = clamp_kelvin(
            kwargs.get(ATTR_COLOR_TEMP_KELVIN, self._attr_color_temp_kelvin)
        )
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness) or 255
        await self._async_lamp_call(
            self.coordinator.lamp.set_immediate_light(
                downlight=Downlight(kelvin=kelvin, brightness=brightness)
            )
        )
        self._attr_is_on = True
        self._attr_color_temp_kelvin = kelvin
        self._attr_brightness = brightness
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the downlight off by setting its brightness to zero."""
        assert self._attr_color_temp_kelvin is not None
        await self._async_lamp_call(
            self.coordinator.lamp.set_immediate_light(
                downlight=Downlight(kelvin=self._attr_color_temp_kelvin, brightness=0)
            )
        )
        self._attr_is_on = False
        self.async_write_ha_state()
