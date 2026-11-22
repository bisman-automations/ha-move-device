"""Preview and move, inside Home Assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.move_device.const import DOMAIN, EVENT_MOVED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

MAC = "02:00:00:00:00:01"

AUTOMATIONS = """\
# Made in the UI
- id: "1001"
  alias: Kitchen lamp at sunset
  triggers:
    - trigger: event
      event_type: test_sunset
  actions:
    - action: light.turn_on
      target:
        entity_id: light.kitchen_lamp
    - action: system_log.write
      data:
        message: "{{ states('sensor.kitchen_temperature') }}"
- id: "1002"
  alias: Unrelated
  triggers:
    - trigger: event
      event_type: test_other
  actions:
    - action: light.turn_on
      target:
        entity_id: light.kitchen_lamp_2
"""


@pytest.fixture
async def home(hass: HomeAssistant, tmp_path: Path) -> dict[str, Any]:
    """Kitchen and Office, a lamp in the kitchen, and a linked device."""
    hass.config.config_dir = str(tmp_path)
    areas = ar.async_get(hass)
    kitchen = areas.async_create("Kitchen", aliases={"Cookhouse"})
    office = areas.async_create("Office")
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    source = MockConfigEntry(domain="test")
    source.add_to_hass(hass)
    other = MockConfigEntry(domain="test2")
    other.add_to_hass(hass)

    lamp = devices.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={("test", "lamp")},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC)},
        name="Kitchen Lamp",
    )
    devices.async_update_device(lamp.id, area_id=kitchen.id)
    linked = devices.async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("test2", "lamp")},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC)},
        name="Kitchen Lamp Plug",
    )
    devices.async_update_device(linked.id, area_id=kitchen.id)
    bystander = devices.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={("test", "other")},
        name="Hall Lamp",
    )

    light = entities.async_get_or_create(
        "light",
        "test",
        "lamp",
        device_id=lamp.id,
        suggested_object_id="kitchen_lamp",
        has_entity_name=True,
        original_name=None,
    )
    temp = entities.async_get_or_create(
        "sensor",
        "test",
        "temp",
        device_id=lamp.id,
        suggested_object_id="kitchen_temperature",
        original_name="Kitchen Temperature",
    )
    entities.async_update_entity(temp.entity_id, area_id=kitchen.id)
    plug = entities.async_get_or_create(
        "switch",
        "test2",
        "plug",
        device_id=linked.id,
        suggested_object_id="kitchen_lamp_plug",
    )
    entities.async_update_entity(plug.entity_id, name="Cookhouse plug")
    hass.states.async_set(light.entity_id, "on")
    hass.states.async_set(temp.entity_id, "21")
    hass.states.async_set("light.office_lamp_taken", "off")

    (tmp_path / "automations.yaml").write_text(AUTOMATIONS)
    (tmp_path / "configuration.yaml").write_text(
        "automation: !include automations.yaml\n"
    )
    from homeassistant import config as conf_util

    config = await conf_util.async_hass_config_yaml(hass)
    assert await async_setup_component(hass, "automation", config)

    entry = MockConfigEntry(domain=DOMAIN, title="Move Device")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return {
        "kitchen": kitchen,
        "office": office,
        "lamp": lamp,
        "linked": linked,
        "bystander": bystander,
        "light": light.entity_id,
        "temp": temp.entity_id,
        "plug": plug.entity_id,
        "path": tmp_path,
    }


async def _ws(hass, hass_ws_client, message: dict[str, Any]) -> dict[str, Any]:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(message)
    return await client.receive_json()


async def test_preview(hass: HomeAssistant, hass_ws_client, home) -> None:
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/preview",
            "device_ids": [home["lamp"].id],
            "area_id": home["office"].id,
        },
    )
    assert reply["success"], reply
    preview = reply["result"]
    assert preview["area_name"] == "Office"
    rows = {row["device_id"]: row for row in preview["devices"]}
    assert set(rows) == {home["lamp"].id, home["linked"].id}
    lamp = rows[home["lamp"].id]
    assert lamp["new_name"] == "Office Lamp"
    assert lamp["linked_to"] is None
    assert rows[home["linked"].id]["linked_to"] == home["lamp"].id
    assert rows[home["linked"].id]["new_name"] == "Office Lamp Plug"
    ents = {e["entity_id"]: e for e in lamp["entities"]}
    assert ents[home["light"]]["new_entity_id"] == "light.office_lamp"
    # Uses the device's name: nothing of its own to rename.
    assert ents[home["light"]]["name"] is None
    assert ents[home["temp"]]["new_name"] == "Office Temperature"
    assert ents[home["temp"]]["area_moves"] is True
    plug = rows[home["linked"].id]["entities"][0]
    # The alias counts as the area's name.
    assert plug["new_name"] == "Office plug"

    refs = preview["references"]
    assert len(refs) == 1
    assert refs[0]["kind"] == "automation"
    assert refs[0]["in_editor"] is True
    assert "editable" not in refs[0]
    assert refs[0]["item_id"] == "1001"
    assert sorted(refs[0]["uses"]) == sorted([home["light"], home["temp"]])


async def test_preview_options_and_conflict(
    hass: HomeAssistant, hass_ws_client, home
) -> None:
    hass.states.async_set("light.office_lamp", "off")
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/preview",
            "device_ids": [home["lamp"].id],
            "area_id": home["office"].id,
            "options": {
                "include_linked": False,
                "rename_devices": False,
                "rename_entity_names": False,
            },
        },
    )
    rows = reply["result"]["devices"]
    assert len(rows) == 1
    assert rows[0]["new_name"] is None
    ents = {e["entity_id"]: e for e in rows[0]["entities"]}
    assert ents[home["light"]]["conflict"] == "exists"
    assert ents[home["temp"]]["new_name"] is None


async def test_preview_custom_find_replace(
    hass: HomeAssistant, hass_ws_client, home
) -> None:
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/preview",
            "device_ids": [home["bystander"].id],
            "area_id": home["office"].id,
            "options": {"find": "Hall", "replace": "Study"},
        },
    )
    assert reply["result"]["devices"][0]["new_name"] == "Study Lamp"


async def test_preview_area_moves_only_when_the_device_moves(
    hass: HomeAssistant, hass_ws_client, home
) -> None:
    """A device already in the area: its entities' areas don't move either."""
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/preview",
            "device_ids": [home["lamp"].id],
            "area_id": home["kitchen"].id,
            "options": {"include_linked": False},
        },
    )
    row = reply["result"]["devices"][0]
    assert row["already_there"] is True
    ents = {e["entity_id"]: e for e in row["entities"]}
    assert ents[home["temp"]]["area_moves"] is False


async def test_apply_skips_the_area_lookups(
    hass: HomeAssistant, hass_ws_client, home
) -> None:
    """Carrying out a move doesn't look up area targets it would throw away."""
    with patch(
        "custom_components.move_device.references._area_lookups", return_value=[]
    ) as lookups:
        reply = await _ws(
            hass,
            hass_ws_client,
            {
                "type": "move_device/apply",
                "area_id": home["office"].id,
                "devices": [{"device_id": home["lamp"].id}],
                "entities": [
                    {"entity_id": home["light"], "new_entity_id": "light.desk_lamp"}
                ],
            },
        )
    assert reply["success"], reply
    assert [ref["item_id"] for ref in reply["result"]["needs_updating"]] == ["1001"]
    lookups.assert_not_called()


async def test_preview_unknown_area(hass: HomeAssistant, hass_ws_client, home) -> None:
    reply = await _ws(
        hass,
        hass_ws_client,
        {"type": "move_device/preview", "device_ids": [], "area_id": "nope"},
    )
    assert not reply["success"]


async def test_apply_moves_renames_and_lists_what_needs_updating(
    hass: HomeAssistant, hass_ws_client, home
) -> None:
    """The registries change; automations are listed with old -> new IDs, not edited."""
    events = []
    hass.bus.async_listen(EVENT_MOVED, events.append)
    # Stand in for the reload services so any call to them is recorded.
    reload_calls = {
        kind: async_mock_service(hass, kind, "reload")
        for kind in ("automation", "script", "scene")
    }
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/apply",
            "area_id": home["office"].id,
            "devices": [
                {"device_id": home["lamp"].id, "new_name": "Desk Lamp"},
                {"device_id": home["linked"].id, "new_name": "Office Lamp Plug"},
            ],
            "entities": [
                {"entity_id": home["light"], "new_entity_id": "light.desk_lamp"},
                {
                    "entity_id": home["temp"],
                    "new_entity_id": "sensor.office_temperature",
                    "new_name": "Office Temperature",
                },
            ],
        },
    )
    assert reply["success"], reply
    result = reply["result"]
    await hass.async_block_till_done()

    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    lamp = devices.async_get(home["lamp"].id)
    assert lamp.area_id == home["office"].id
    assert lamp.name_by_user == "Desk Lamp"
    assert devices.async_get(home["linked"].id).area_id == home["office"].id
    assert entities.async_get("light.desk_lamp") is not None
    temp = entities.async_get("sensor.office_temperature")
    assert temp.name == "Office Temperature"
    assert temp.area_id == home["office"].id
    # A device not in the move stays.
    assert devices.async_get(home["bystander"].id).area_id is None

    # The automation is listed for the editor, with the new ID for each old one.
    assert [ref["item_id"] for ref in result["needs_updating"]] == ["1001"]
    ref = result["needs_updating"][0]
    assert ref["in_editor"] is True
    assert ref["kind"] == "automation"
    assert ref["renames"] == {
        home["light"]: "light.desk_lamp",
        home["temp"]: "sensor.office_temperature",
    }
    assert "updated" not in result
    assert "left_to_update" not in result

    # ...and nothing was edited, copied or reloaded for the person.
    assert (home["path"] / "automations.yaml").read_text() == AUTOMATIONS
    assert not list(home["path"].glob("*.bak"))
    assert not any(reload_calls.values())
    assert events and events[0].data["renamed"][home["light"]] == "light.desk_lamp"


async def test_apply_without_renaming_ids_lists_nothing(
    hass: HomeAssistant, hass_ws_client, home
) -> None:
    """Moving without changing entity IDs leaves nothing to update."""
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/apply",
            "area_id": home["office"].id,
            "devices": [{"device_id": home["lamp"].id}],
        },
    )
    assert reply["success"], reply
    assert reply["result"]["needs_updating"] == []
    assert reply["result"]["renamed_entities"] == []
    assert (home["path"] / "automations.yaml").read_text() == AUTOMATIONS


async def test_apply_lists_helpers_to_change_by_hand(
    hass: HomeAssistant, hass_ws_client, home
) -> None:
    """A helper (another config entry) that uses an old ID is listed, not edited."""
    helper = MockConfigEntry(
        domain="template",
        title="Lamp watcher",
        options={"state": "{{ is_state('light.kitchen_lamp', 'on') }}"},
    )
    helper.add_to_hass(hass)
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/apply",
            "area_id": home["office"].id,
            "devices": [{"device_id": home["lamp"].id}],
            "entities": [
                {"entity_id": home["light"], "new_entity_id": "light.office_lamp"}
            ],
        },
    )
    assert reply["success"], reply
    by_kind = {ref["kind"]: ref for ref in reply["result"]["needs_updating"]}
    assert set(by_kind) == {"automation", "helper"}
    assert by_kind["helper"]["in_editor"] is False
    assert by_kind["helper"]["entry_id"] == helper.entry_id
    assert by_kind["helper"]["renames"] == {home["light"]: "light.office_lamp"}
    # The helper's options are untouched.
    entry = hass.config_entries.async_get_entry(helper.entry_id)
    assert "light.kitchen_lamp" in entry.options["state"]


async def test_apply_no_longer_takes_update_references(
    hass: HomeAssistant, hass_ws_client, home
) -> None:
    """The option to rewrite automations.yaml for the person is gone."""
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/apply",
            "area_id": home["office"].id,
            "devices": [{"device_id": home["lamp"].id}],
            "entities": [
                {"entity_id": home["light"], "new_entity_id": "light.office_lamp"}
            ],
            "update_references": True,
        },
    )
    assert not reply["success"]
    assert reply["error"]["code"] == "invalid_format"
    # Rejected before anything changed.
    assert dr.async_get(hass).async_get(home["lamp"].id).area_id == home["kitchen"].id
    assert (home["path"] / "automations.yaml").read_text() == AUTOMATIONS


@pytest.mark.parametrize(
    "new_entity_id", ["light.office_lamp_taken", "switch.office_lamp", "light.Bad"]
)
async def test_apply_refuses_bad_ids(
    hass: HomeAssistant, hass_ws_client, home, new_entity_id: str
) -> None:
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/apply",
            "area_id": home["office"].id,
            "devices": [{"device_id": home["lamp"].id}],
            "entities": [{"entity_id": home["light"], "new_entity_id": new_entity_id}],
        },
    )
    assert not reply["success"]
    # Nothing changed.
    assert dr.async_get(hass).async_get(home["lamp"].id).area_id == home["kitchen"].id
    assert er.async_get(hass).async_get(home["light"]) is not None


async def test_admin_only(
    hass: HomeAssistant, hass_ws_client, hass_admin_user, home
) -> None:
    hass_admin_user.groups = []
    reply = await _ws(
        hass,
        hass_ws_client,
        {
            "type": "move_device/preview",
            "device_ids": [home["lamp"].id],
            "area_id": home["office"].id,
        },
    )
    assert not reply["success"]
    assert reply["error"]["code"] == "unauthorized"


async def test_config_flow_once(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
