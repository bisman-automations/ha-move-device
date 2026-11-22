# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-11-22

### Fixed

- **"Area moves too" only when it does.** In the preview, an entity of a device that's already in the area you picked no longer says its area moves too. Nothing moved in that case; the label was wrong.

### Changed

- **Less work when you check and carry out a move.** Moving no longer looks up which automations and scripts target the area, which only the preview shows, and looking for old entity IDs in automations, scripts, scenes and helpers skips the ones that can't contain them.

## [0.2.1] - 2026-11-21

### Changed

- **Ruff 0.17.6.** Linting uses the current Ruff release. Nothing changes for you.

## [0.2.0] - 2026-11-17

### Removed

- **Move Device no longer edits automations, scripts and scenes.** The **Update** box, which rewrote `automations.yaml`, `scripts.yaml` and `scenes.yaml` to the new entity IDs, saved `.move_device.bak` copies and reloaded them, is gone. Changing those files behind the editor's back isn't something an integration should do. Raised in the review for the default HACS list. Files it already changed stay as they are, and any `.move_device.bak` copies can be deleted.

### Changed

- **A clear list of what to update.** Before and after a move, automations, scripts and scenes made in the editor are listed under **Needs updating in the editor**, each with its old and new entity IDs and an **Open in the editor** link. Helpers and YAML you wrote yourself are listed under **Change by hand**.
- Ruff 0.17.5 for the lint checks.

## [0.1.0] - 2026-11-13

### Added

- **Move devices to another area from the sidebar.** Pick devices, pick the area they're moving to, check every change, then move them. The page is for administrators only.
- **Linked devices move too.** Devices Home Assistant shows under **Linked devices** move and are renamed with the device you picked, unless you leave them out.
- **Names follow the room.** The old area's name and aliases are swapped for the new area's in device names, entity names and entity IDs, as whole words. Add your own **Find** and **Replace with** words, turn any kind of renaming off, or edit every suggestion before moving.
- **See what uses the old entity IDs.** Automations, scripts and scenes (including templates), helpers, and automations that target the old or new area are listed with links before the move and again after it.
- **Update automations, scripts and scenes for you.** Ones made in the Home Assistant editor can be updated to the new entity IDs and reloaded, with a copy of each changed file saved first.

[0.2.2]: https://github.com/bisman-automations/ha-move-device/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/bisman-automations/ha-move-device/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/bisman-automations/ha-move-device/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bisman-automations/ha-move-device/releases/tag/v0.1.0
