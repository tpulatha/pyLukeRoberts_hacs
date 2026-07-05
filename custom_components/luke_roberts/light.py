"""Light platform for the Luke Roberts integration."""

from __future__ import annotations

from typing import Any

from pylukeroberts.const import MAX_KELVIN, MIN_KELVIN, SCENE_OFF

from homeassistant.components import bluetooth
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LukeRobertsConfigEntry, LukeRobertsCoordinator

DEFAULT_UPLIGHT_HS = (30.0, 100.0)
DEFAULT_DOWNLIGHT_KELVIN = 3000


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LukeRobertsConfigEntry,
    async_add_entities: AddEntitiesCallback,
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


class LukeRobertsBaseLight(CoordinatorEntity[LukeRobertsCoordinator], LightEntity):
    """Common device info and availability for all lamp entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LukeRobertsCoordinator) -> None:
        super().__init__(coordinator)
        lamp = coordinator.lamp
        self._mac = dr.format_mac(lamp.address)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            connections={(dr.CONNECTION_BLUETOOTH, lamp.address)},
            name=lamp.name,
            manufacturer="Luke Roberts",
            model="Luvo",
        )

    @property
    def available(self) -> bool:
        return super().available and bluetooth.async_address_present(
            self.hass, self.coordinator.lamp.address, connectable=True
        )


class LukeRobertsLight(LukeRobertsBaseLight):
    """The lamp as a whole.

    Brightness dims the entire scene, color temperature drives the downlight,
    HS color drives the uplight. The lamp does not report brightness or color
    back, so those attributes are optimistic; on/off and the active scene are
    read from the lamp.
    """

    _attr_name = None
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(self, coordinator: LukeRobertsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = self._mac
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_brightness = None
        self._attr_color_temp_kelvin = None
        self._attr_hs_color = None

    @property
    def is_on(self) -> bool:
        return self.coordinator.lamp.is_on

    @property
    def effect(self) -> str | None:
        return self.coordinator.lamp.current_scene_name

    @property
    def effect_list(self) -> list[str]:
        return [
            scene.name
            for scene in self.coordinator.lamp.scenes
            if scene.id != SCENE_OFF
        ]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lamp on, optionally selecting a scene or adjusting it."""
        lamp = self.coordinator.lamp

        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            for scene in lamp.scenes:
                if scene.name == effect and scene.id != SCENE_OFF:
                    await lamp.select_scene(scene.id)
                    break
        elif not lamp.is_on:
            await lamp.switch_on()

        if (kelvin := kwargs.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
            kelvin = min(max(int(kelvin), MIN_KELVIN), MAX_KELVIN)
            await lamp.set_color_temperature(kelvin)
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp_kelvin = kelvin

        if (hs_color := kwargs.get(ATTR_HS_COLOR)) is not None:
            hue, saturation = hs_color
            brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)
            brightness_pct = (
                round(brightness / 255 * 100) if brightness is not None else 100
            )
            await lamp.set_hue(round(hue), round(saturation), brightness_pct)
            self._attr_color_mode = ColorMode.HS
            self._attr_hs_color = (hue, saturation)
            self._attr_brightness = kwargs.get(ATTR_BRIGHTNESS, brightness)
        elif (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            await lamp.set_brightness(round(brightness / 255 * 100))
            self._attr_brightness = brightness

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lamp off."""
        await self.coordinator.lamp.switch_off()
        self.async_write_ha_state()


class LukeRobertsUplight(LukeRobertsBaseLight):
    """The indirect uplight, with its own brightness and HS color.

    Drives the uplight sub-packet of the Immediate Light command. Changes are
    transient: the lamp reverts them on scene change or power-down, and
    nothing is readable back, so all state is assumed.
    """

    _attr_name = "Uplight"
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS
    _attr_assumed_state = True

    def __init__(self, coordinator: LukeRobertsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._mac}-uplight"
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_hs_color = DEFAULT_UPLIGHT_HS

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the uplight color and brightness."""
        hue, saturation = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness) or 255
        await self.coordinator.lamp.set_hue(
            round(hue), round(saturation), round(brightness / 255 * 100)
        )
        self._attr_is_on = True
        self._attr_hs_color = (hue, saturation)
        self._attr_brightness = brightness
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the uplight off by setting its brightness to zero."""
        hue, saturation = self._attr_hs_color
        await self.coordinator.lamp.set_hue(round(hue), round(saturation), 0)
        self._attr_is_on = False
        self.async_write_ha_state()


class LukeRobertsDownlight(LukeRobertsBaseLight):
    """The direct downlight, with its own brightness and color temperature.

    Drives the downlight sub-packet of the Immediate Light command. Changes
    are transient: the lamp reverts them on scene change or power-down, and
    nothing is readable back, so all state is assumed.
    """

    _attr_name = "Downlight"
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN
    _attr_assumed_state = True

    def __init__(self, coordinator: LukeRobertsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._mac}-downlight"
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_color_temp_kelvin = DEFAULT_DOWNLIGHT_KELVIN

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the downlight color temperature and brightness."""
        kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN, self._attr_color_temp_kelvin)
        kelvin = min(max(int(kelvin), MIN_KELVIN), MAX_KELVIN)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness) or 255
        await self.coordinator.lamp.set_downlight(
            kelvin, round(brightness / 255 * 100)
        )
        self._attr_is_on = True
        self._attr_color_temp_kelvin = kelvin
        self._attr_brightness = brightness
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the downlight off by setting its brightness to zero."""
        await self.coordinator.lamp.set_downlight(self._attr_color_temp_kelvin, 0)
        self._attr_is_on = False
        self.async_write_ha_state()
