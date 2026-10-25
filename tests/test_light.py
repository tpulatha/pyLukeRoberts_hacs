"""Tests for the light and select entities."""

from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pylukeroberts import (
    Downlight,
    LukeRobertsConnectionError,
    LukeRobertsForbiddenError,
    Uplight,
)
import pytest

MAIN = "light.luvo"
UP = "light.luvo_uplight"
DOWN = "light.luvo_downlight"
SCENE = "select.luvo_scene"


async def turn_on(hass: HomeAssistant, entity_id: str, **data) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )


async def turn_off(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


async def test_main_light_state(hass: HomeAssistant, setup_integration) -> None:
    state = hass.states.get(MAIN)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "Lesen"
    assert state.attributes[ATTR_EFFECT_LIST] == ["Lesen", "Entspannen"]


async def test_turn_off_and_on(hass: HomeAssistant, setup_integration, lamp) -> None:
    await turn_off(hass, MAIN)
    lamp.switch_off.assert_awaited_once()
    assert hass.states.get(MAIN).state == STATE_OFF

    await turn_on(hass, MAIN)
    lamp.switch_on.assert_awaited_once()
    state = hass.states.get(MAIN)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "Lesen"  # pushed immediately


async def test_effect_selects_scene(
    hass: HomeAssistant, setup_integration, lamp
) -> None:
    await turn_on(hass, MAIN, **{ATTR_EFFECT: "Entspannen"})
    lamp.select_scene.assert_awaited_once_with(2)
    assert hass.states.get(MAIN).attributes[ATTR_EFFECT] == "Entspannen"
    assert hass.states.get(SCENE).state == "Entspannen"


async def test_unknown_effect_raises(
    hass: HomeAssistant, setup_integration, lamp
) -> None:
    with pytest.raises(ServiceValidationError):
        await turn_on(hass, MAIN, **{ATTR_EFFECT: "Disco"})
    lamp.select_scene.assert_not_awaited()


@pytest.mark.parametrize(("brightness", "percent"), [(1, 1), (128, 51), (255, 100)])
async def test_brightness_never_rounds_to_zero(
    hass: HomeAssistant, setup_integration, lamp, brightness, percent
) -> None:
    await turn_on(hass, MAIN, **{ATTR_BRIGHTNESS: brightness})
    lamp.set_brightness.assert_awaited_once_with(percent)
    assert hass.states.get(MAIN).attributes[ATTR_BRIGHTNESS] == brightness


async def test_hs_color_drives_uplight_and_brightness_dims_scene(
    hass: HomeAssistant, setup_integration, lamp
) -> None:
    await turn_on(hass, MAIN, **{ATTR_HS_COLOR: (120, 50), ATTR_BRIGHTNESS: 128})
    lamp.set_immediate_light.assert_awaited_once_with(
        uplight=Uplight(hue=120, saturation=128, brightness=255)
    )
    lamp.set_brightness.assert_awaited_once_with(51)


async def test_color_temp(hass: HomeAssistant, setup_integration, lamp) -> None:
    await turn_on(hass, MAIN, **{ATTR_COLOR_TEMP_KELVIN: 3500})
    lamp.set_color_temperature.assert_awaited_once_with(3500)
    assert hass.states.get(MAIN).attributes[ATTR_COLOR_TEMP_KELVIN] == 3500


async def test_scene_change_clears_optimistic_state(
    hass: HomeAssistant, setup_integration, lamp
) -> None:
    await turn_on(hass, MAIN, **{ATTR_COLOR_TEMP_KELVIN: 3500})
    await turn_on(hass, DOWN, **{ATTR_BRIGHTNESS: 100})
    assert hass.states.get(DOWN).state == STATE_ON

    await turn_on(hass, MAIN, **{ATTR_EFFECT: "Entspannen"})
    assert hass.states.get(MAIN).attributes.get(ATTR_COLOR_TEMP_KELVIN) is None
    assert hass.states.get(DOWN).state == STATE_UNKNOWN

    await turn_off(hass, MAIN)
    assert hass.states.get(DOWN).state == STATE_OFF


async def test_uplight_uses_raw_brightness(
    hass: HomeAssistant, setup_integration, lamp
) -> None:
    await turn_on(hass, UP, **{ATTR_HS_COLOR: (200, 100), ATTR_BRIGHTNESS: 3})
    lamp.set_immediate_light.assert_awaited_with(
        uplight=Uplight(hue=200, saturation=255, brightness=3)
    )
    assert hass.states.get(UP).state == STATE_ON

    await turn_off(hass, UP)
    lamp.set_immediate_light.assert_awaited_with(
        uplight=Uplight(hue=200, saturation=255, brightness=0)
    )
    assert hass.states.get(UP).state == STATE_OFF


async def test_downlight(hass: HomeAssistant, setup_integration, lamp) -> None:
    await turn_on(hass, DOWN, **{ATTR_COLOR_TEMP_KELVIN: 2800, ATTR_BRIGHTNESS: 10})
    lamp.set_immediate_light.assert_awaited_with(
        downlight=Downlight(kelvin=2800, brightness=10)
    )
    await turn_off(hass, DOWN)
    lamp.set_immediate_light.assert_awaited_with(
        downlight=Downlight(kelvin=2800, brightness=0)
    )


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (LukeRobertsForbiddenError(0xFC), "security_code"),
        (LukeRobertsConnectionError("gone"), "command_failed"),
    ],
)
async def test_command_errors_are_translated(
    hass: HomeAssistant, setup_integration, lamp, error, key
) -> None:
    lamp.switch_off.side_effect = error
    with pytest.raises(HomeAssistantError) as exc:
        await turn_off(hass, MAIN)
    assert exc.value.translation_key == key


async def test_scene_select(hass: HomeAssistant, setup_integration, lamp) -> None:
    state = hass.states.get(SCENE)
    assert state.state == "Lesen"
    assert state.attributes[ATTR_OPTIONS] == ["Off", "Lesen", "Entspannen"]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SCENE, ATTR_OPTION: "Off"},
        blocking=True,
    )
    lamp.select_scene.assert_awaited_once_with(0)
    assert hass.states.get(MAIN).state == STATE_OFF
