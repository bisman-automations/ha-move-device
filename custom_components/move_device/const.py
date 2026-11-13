"""Constants for Move Device."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "move_device"

# Fired after a move: {area_id, device_ids, renamed: {old entity id: new}}.
EVENT_MOVED: Final = f"{DOMAIN}_moved"

# Copies kept of a UI-made file before a move changes it:
# automations.yaml.<YYYYmmddHHMMSS>.move_device.bak
BACKUP_SUFFIX: Final = f".{DOMAIN}.bak"

PANEL_PATH: Final = "move-device"
PANEL_COMPONENT: Final = "move-device-panel"
STATIC_URL: Final = f"/{DOMAIN}_static"
