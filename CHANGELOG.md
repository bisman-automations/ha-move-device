# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-13

### Added

- **Move devices to another area from the sidebar.** Pick devices, pick the area they're moving to, check every change, then move them. The page is for administrators only.
- **Linked devices move too.** Devices Home Assistant shows under **Linked devices** move and are renamed with the device you picked, unless you leave them out.
- **Names follow the room.** The old area's name and aliases are swapped for the new area's in device names, entity names and entity IDs, as whole words. Add your own **Find** and **Replace with** words, turn any kind of renaming off, or edit every suggestion before moving.
- **See what uses the old entity IDs.** Automations, scripts and scenes (including templates), helpers, and automations that target the old or new area are listed with links before the move and again after it.
- **Update automations, scripts and scenes for you.** Ones made in the Home Assistant editor can be updated to the new entity IDs and reloaded, with a copy of each changed file saved first.

[0.1.0]: https://github.com/bisman-automations/ha-move-device/releases/tag/v0.1.0
