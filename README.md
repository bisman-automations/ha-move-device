<p align="center">
  <img src="custom_components/move_device/brand/icon.png" alt="Move Device" width="128">
</p>

# Move Device

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-blue.svg)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/bisman-automations/ha-move-device)](https://github.com/bisman-automations/ha-move-device/releases)
[![Test](https://github.com/bisman-automations/ha-move-device/actions/workflows/test.yml/badge.svg)](https://github.com/bisman-automations/ha-move-device/actions/workflows/test.yml)
[![Validate](https://github.com/bisman-automations/ha-move-device/actions/workflows/validate.yml/badge.svg)](https://github.com/bisman-automations/ha-move-device/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/bisman-automations/ha-move-device)](LICENSE)

Move devices to another area (room) without hunting down every name that still says the old one. Move Device moves the devices you pick, and the devices linked to them, renames the devices and their entities for the new area, and shows you every automation, script, scene and helper that uses the old entity IDs, with the option to update them for you.

Nothing changes until you've seen the full list and pressed **Move**.

## Requirements

- Home Assistant 2026.8 or newer.
- An administrator account. The sidebar page only shows for administrators.

## Installation

### Marketplace (Home Assistant 2026.11 and newer, recommended)

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=bisman-automations&repository=ha-move-device&category=integration)

1. Open the Marketplace and search for **Move Device**, or select the button above to open this repository in the Marketplace.
2. Download **Move Device** and restart Home Assistant.

New versions show up under **Settings > Updates**. Already installed Move Device with
HACS? There's nothing to do: Home Assistant moves it into the Marketplace the
first time it starts on 2026.11.

### HACS (Home Assistant 2026.10 and older)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bisman-automations&repository=ha-move-device&category=integration)

1. Open HACS and search for **Move Device**, or select the button above to open this repository in HACS.
2. Download **Move Device** and restart Home Assistant.

### Custom repository

If **Move Device** does not appear in search:

1. In HACS open the menu, choose **Custom repositories**, and add `https://github.com/bisman-automations/ha-move-device` as an **Integration**.
2. Download **Move Device** and restart Home Assistant.

### Manual

1. Download `move_device.zip` from the [latest release](https://github.com/bisman-automations/ha-move-device/releases/latest).
2. Unzip it into `config/custom_components/move_device/` and restart Home Assistant.

## Setup

[![Open your Home Assistant instance and start setting up Move Device.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=move_device)

Select the button above, or go to **Settings > Devices & services > Add
integration** and search for **Move Device**. There's nothing to fill in.
**Move Device** then shows in the sidebar for administrators.

## Moving devices

1. Open **Move Device** in the sidebar.
2. **Devices to move**: pick one or more devices. Narrow the list with **From area** or **Search**.
3. **Moving to**: pick the new area, and what to rename:
   - **Move linked devices too**: devices Home Assistant shows under **Linked devices** on a device's page, such as the same lamp from its smart plug's integration. They move and are renamed with it.
   - **Rename devices**, **Rename entities** and **Change entity IDs**: each can be turned off.
   - **Find** and **Replace with**: the old area's name and its aliases are always replaced by the new area's name. Add other words in **Find** (a nickname for the room, say), or type a different **Replace with**. Leave **Replace with** blank to use the new area's name.
4. Select **Preview**. Every device is listed with its new name, and every entity with its new name and entity ID:
   - Change any name or entity ID, or put back the old one to keep it.
   - Clear a device's box to leave it where it is.
   - An entity ID that's already used, or isn't valid, is marked; **Move** stays off until it's fixed.
5. Check **What uses the old entity IDs** (below), then select **Move**.

### How names change

Words are matched whole, ignoring case. Moving from Kitchen to Office:

| Before | After |
| --- | --- |
| Kitchen Lamp | Office Lamp |
| `light.kitchen_lamp` | `light.office_lamp` |
| Kitchenette Lamp | unchanged |
| Desk Lamp | unchanged |

Entities that show their device's name (most do) have no name of their own, so only their entity ID changes; the new device name shows on them.

## What uses the old entity IDs

Changing an entity ID breaks anything that still uses the old one. Before the move, Move Device lists:

- **Automations, scripts and scenes** that use an entity ID that's changing, including IDs inside templates. Each links to its editor.
  - **Can be updated**: made in the Home Assistant editor (stored in `automations.yaml`, `scripts.yaml` or `scenes.yaml`). Tick **Update** and Move Device swaps the old entity IDs for the new ones and reloads them. A copy of each file it changes is saved next to it first, ending in `.move_device.bak`.
  - **Change by hand**: written in other YAML files or packages. Move Device never edits those.
- **Helpers** (groups, template helpers and other integrations' settings) that mention an old entity ID, to change by hand.
- **Area targets**: automations and scripts that target the old or the new area. They don't break, but a device that moves out of an area is no longer included when they run, and one that moves in is.

After the move, anything still using the old IDs is listed again with links.

Dashboards aren't checked. Look over any cards that show the moved devices.

## Things to know

- Device names are set as your own name for the device, as if you'd renamed it on its page. The integration's own name is kept underneath.
- Entities you had placed in the device's old area yourself move with it. Entities placed in some other area stay there.
- Unique IDs never change, so history, statistics and the Energy dashboard follow the entity to its new ID.
- Each move fires a `move_device_moved` event with the area, the moved devices and the entity IDs that changed.

## Troubleshooting

- **A new entity ID is marked as already used.** Another entity has it. Pick a different ID for this one, or put back its old ID.
- **An automation wasn't updated.** Only automations, scripts and scenes made in the Home Assistant editor can be updated. The rest are listed after the move with a link; change them by hand.
- **I want the old file back.** The copy saved before the change sits next to it, for example `automations.yaml.20261113164500.move_device.bak`. Rename it back and reload automations.
- **Debug logs:** on the integration's page choose **Enable debug logging**,
  reproduce the problem, then **Disable debug logging** to download the log.
- Report problems at [Issues](https://github.com/bisman-automations/ha-move-device/issues).

## Development

```
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

CI also tests the oldest supported Home Assistant (`requirements_test_min.txt`)
and runs hassfest and the HACS checks. Releases are drafted automatically from
`CHANGELOG.md` on every push to `main` and published by hand. See
[CLAUDE.md](CLAUDE.md) and [CONTRIBUTING](https://github.com/bisman-automations/.github/blob/main/CONTRIBUTING.md).

## License

[MIT](LICENSE)
