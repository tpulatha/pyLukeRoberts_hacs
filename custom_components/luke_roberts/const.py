"""Constants for the Luke Roberts integration."""

from datetime import timedelta

from pylukeroberts.const import SERVICE_UUID

DOMAIN = "luke_roberts"

__all__ = ["DOMAIN", "SCENE_REFRESH_INTERVAL", "SERVICE_UUID", "UPDATE_INTERVAL"]

UPDATE_INTERVAL = timedelta(seconds=60)

# Scenes added or renamed in the Luke Roberts app show up after this long.
SCENE_REFRESH_INTERVAL = timedelta(minutes=30)
