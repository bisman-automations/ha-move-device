"""Constants for Move Device."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "move_device"

# Fired after a move: {area_id, device_ids, renamed: {old entity id: new}}.
EVENT_MOVED: Final = f"{DOMAIN}_moved"

PANEL_PATH: Final = "move-device"
PANEL_COMPONENT: Final = "move-device-panel"
STATIC_URL: Final = f"/{DOMAIN}_static"
