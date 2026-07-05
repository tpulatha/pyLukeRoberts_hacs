# Luke Roberts for Home Assistant

A Home Assistant custom integration for [Luke Roberts](https://www.luke-roberts.com/) smart lamps (Luvo / Model F), controlled locally over Bluetooth Low Energy via [pyLukeRoberts](https://github.com/tpulatha/pyLukeRoberts).

## Features

- **Automatic discovery** — lamps in Bluetooth range are discovered and offered for setup automatically. Works with local Bluetooth adapters and [ESPHome Bluetooth proxies](https://esphome.io/components/bluetooth_proxy.html).
- **One light entity per lamp** with:
  - On/off
  - Brightness
  - Color temperature (2700–4000 K, drives the downlight)
  - Color (hue/saturation, drives the uplight)
  - The lamp's built-in scenes as light *effects*

## Installation

### HACS (recommended)

1. In HACS, open **⋮ → Custom repositories**.
2. Add `https://github.com/tpulatha/pyLukeRoberts_hacs` as an **Integration**.
3. Install **Luke Roberts** and restart Home Assistant.

### Manual

Copy `custom_components/luke_roberts` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

If a lamp is in range it is discovered automatically — accept the discovery notification in **Settings → Devices & Services**. Otherwise add the integration manually via **Add Integration → Luke Roberts** and pick the lamp from the list.

## Notes

- On/off is scene-based: turning the lamp on selects the lamp's default scene, turning it off selects the "Off" scene.
- Brightness and color changes modify the currently active scene and are not persisted by the lamp across power cycles (this mirrors the lamp's BLE API).
- The lamp does not report brightness/color back, so those attributes are optimistic; the active scene and on/off state are polled from the lamp.
