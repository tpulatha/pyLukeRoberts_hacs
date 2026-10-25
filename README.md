# Luke Roberts for Home Assistant

[![GitHub release](https://img.shields.io/github/v/release/tpulatha/pyLukeRoberts_hacs)](https://github.com/tpulatha/pyLukeRoberts_hacs/releases)
[![Validate](https://github.com/tpulatha/pyLukeRoberts_hacs/actions/workflows/validate.yml/badge.svg)](https://github.com/tpulatha/pyLukeRoberts_hacs/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for [Luke Roberts](https://www.luke-roberts.com/) smart lamps (Luvo / Model F), controlled locally over Bluetooth Low Energy via [pyLukeRoberts](https://github.com/tpulatha/pyLukeRoberts).

## Features

- **Automatic discovery** — lamps in Bluetooth range are discovered and offered for setup automatically. Works with local Bluetooth adapters and [ESPHome Bluetooth proxies](https://esphome.io/components/bluetooth_proxy.html).
- **A main light entity per lamp** with:
  - On/off
  - Brightness (dims the whole scene)
  - Color temperature (2700–4000 K, drives the downlight)
  - Color (hue/saturation, drives the uplight)
  - The lamp's built-in scenes as light *effects*
- **A "Scene" select entity** listing all scenes of the lamp, including *Off*
- **Separate "Uplight" and "Downlight" entities** on the same device, each with
  its own independent brightness — the uplight with HS color, the downlight
  with color temperature. These use the lamp's *Immediate Light* command, so
  changes are transient: the lamp reverts them when the scene changes or power
  cycles, and their state in Home Assistant is assumed (the lamp cannot report
  it back).

## Installation

### HACS (recommended)

1. In HACS, open **⋮ → Custom repositories**.
2. Add `https://github.com/tpulatha/pyLukeRoberts_hacs` as an **Integration**.
3. Install **Luke Roberts** and restart Home Assistant.

### Manual

Copy `custom_components/luke_roberts` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

If a lamp is in range it is discovered automatically — accept the discovery notification in **Settings → Devices & Services**. Otherwise add the integration manually via **Add Integration → Luke Roberts** and pick the lamp from the list.

## Example automation

```yaml
# Warm, dim reading light in the evening
automation:
  - alias: "Evening reading light"
    triggers:
      - trigger: sun
        event: sunset
    actions:
      - action: light.turn_on
        target:
          entity_id: light.luvo
        data:
          effect: "Reading"        # one of the lamp's scenes
      - action: light.turn_on
        target:
          entity_id: light.luvo_downlight
        data:
          color_temp_kelvin: 2700
          brightness_pct: 40
```

## Troubleshooting

- **Lamp is not discovered / commands fail:** the lamp accepts one BLE
  connection at a time. Close the Luke Roberts phone app (or move it to the
  background) — it holds connections to all lamps in range while open.
- **Commands rejected:** if a Bluetooth *security code* is set in the Luke
  Roberts app, the lamp rejects all API commands. Setup detects this and
  shows an error. Remove the code to use this integration.
- **New scenes missing:** the scene list is re-read every 30 minutes; reload
  the integration to pick up changes immediately.
- **Uplight/Downlight show wrong state:** their changes are transient by
  design; the lamp reverts them on scene change or power-cycle without any way
  to report that back. The main light entity always reflects the polled scene
  state.

### Debug logging

Enable via **Settings → Devices & Services → Luke Roberts → ⋮ → Enable debug
logging**. Reproduce the issue, then disable debug logging — Home Assistant
downloads a log filtered to this integration, including the BLE commands sent
by the `pylukeroberts` library. Attach that file to a
[GitHub issue](https://github.com/tpulatha/pyLukeRoberts_hacs/issues).

## Notes

- On/off is scene-based: turning the lamp on selects the lamp's default scene, turning it off selects the "Off" scene.
- Brightness and color changes modify the currently active scene and are not persisted by the lamp across power cycles (this mirrors the lamp's BLE API).
- The lamp does not report brightness/color back, so those attributes are optimistic and are cleared when the scene changes; the active scene and on/off state are polled from the lamp every 60 s. The connection is released right after each poll so the Luke Roberts app can still reach the lamp.
- Requires Home Assistant 2026.4 or newer.

## Development

```bash
python3.14 -m venv venv && . venv/bin/activate
pip install -r requirements_test.txt
pytest
```
