"""Build a move's preview and carry it out.

The preview (``async_preview``) lists every device that moves (the ones
picked plus the devices Home Assistant shows as linked to them), the new
names and entity IDs the renaming rules propose, any that clash, and what
uses the old IDs. Nothing changes until ``async_apply``, which takes the
preview back with the person's edits and checks every row again.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .const import EVENT_MOVED
from .names import swap_name, swap_object_id, valid_entity_id
from .references import Reference, async_find


@dataclass
class Options:
    """What to rename. Every switch is on by default."""

    include_linked: bool = True
    rename_devices: bool = True
    rename_entity_names: bool = True
    rename_entity_ids: bool = True
    find: str = ""
    replace: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Options:
        data = data or {}
        return cls(
            include_linked=bool(data.get("include_linked", True)),
            rename_devices=bool(data.get("rename_devices", True)),
            rename_entity_names=bool(data.get("rename_entity_names", True)),
            rename_entity_ids=bool(data.get("rename_entity_ids", True)),
            find=str(data.get("find") or ""),
            replace=str(data.get("replace") or ""),
        )


@dataclass
class _Rules:
    finds: list[str] = field(default_factory=list)
    replace: str = ""


def all_devices(registry: dr.DeviceRegistry) -> list[dr.DeviceEntry]:
    """Every device: ``registry.devices`` is a mapping on 2026.8, iterable later."""
    devices = registry.devices
    return [devices[item] if isinstance(item, str) else item for item in devices]


def _keys(device: dr.DeviceEntry) -> set[tuple[str, ...]]:
    keys: set[tuple[str, ...]] = set()
    for kind, values in (("i", device.identifiers), ("c", device.connections)):
        for value in values:
            keys.add((kind, *(str(part) for part in value)))
    return keys


def linked_devices(
    registry: dr.DeviceRegistry, device_ids: Iterable[str]
) -> dict[str, str]:
    """Devices that share an identifier or connection with a picked one.

    These are the devices Home Assistant shows under **Linked devices**.
    Returns linked device id -> the picked device it's linked to.
    """
    picked = [d for d in (registry.async_get(i) for i in device_ids) if d]
    picked_ids = {d.id for d in picked}
    keys = {key: d.id for d in picked for key in _keys(d)}
    linked: dict[str, str] = {}
    for device in all_devices(registry):
        if device.id in picked_ids:
            continue
        for key in _keys(device):
            if key in keys:
                linked[device.id] = keys[key]
                break
    return linked


def _rules(
    area: ar.AreaEntry | None, new_area: ar.AreaEntry, options: Options
) -> _Rules:
    finds = [options.find] if options.find.strip() else []
    if area is not None:
        finds += [area.name, *sorted(area.aliases or ())]
    replace = options.replace if options.replace.strip() else new_area.name
    return _Rules(finds, replace)


def _device_name(device: dr.DeviceEntry) -> str:
    return device.name_by_user or device.name or device.id


async def async_preview(
    hass: HomeAssistant,
    device_ids: list[str],
    area_id: str,
    options: Options,
) -> dict[str, Any]:
    """Everything a move would change. Changes nothing."""
    areas = ar.async_get(hass)
    new_area = areas.async_get_area(area_id)
    if new_area is None:
        raise HomeAssistantError(f"Unknown area {area_id}")
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    order = [i for i in dict.fromkeys(device_ids) if devices.async_get(i)]
    linked = linked_devices(devices, order) if options.include_linked else {}

    taken: set[str] = set()
    rows: list[dict[str, Any]] = []
    from_areas: set[str] = set()
    old_ids: list[str] = []
    for device_id in [*order, *linked]:
        device = devices.async_get(device_id)
        if device is None:
            continue
        area = areas.async_get_area(device.area_id) if device.area_id else None
        if area is not None and area.id != area_id:
            from_areas.add(area.id)
        rules = _rules(area, new_area, options)
        name = _device_name(device)
        new_name = (
            swap_name(name, rules.finds, rules.replace)
            if options.rename_devices
            else None
        )
        entity_rows = []
        for entity in er.async_entries_for_device(
            entities, device.id, include_disabled_entities=True
        ):
            new_entity_id = (
                swap_object_id(entity.entity_id, rules.finds, rules.replace)
                if options.rename_entity_ids
                else None
            )
            own_name = entity.name or (
                None if entity.has_entity_name else entity.original_name
            )
            new_entity_name = (
                swap_name(own_name, rules.finds, rules.replace)
                if options.rename_entity_names
                else None
            )
            conflict = None
            if new_entity_id:
                if new_entity_id in taken or (
                    entities.async_get(new_entity_id) is not None
                    or hass.states.get(new_entity_id) is not None
                ):
                    conflict = "exists"
                taken.add(new_entity_id)
                old_ids.append(entity.entity_id)
            entity_rows.append(
                {
                    "entity_id": entity.entity_id,
                    "new_entity_id": new_entity_id,
                    "name": own_name,
                    "shown_name": _shown_name(hass, entity),
                    "new_name": new_entity_name,
                    "own_area": entity.area_id,
                    # Only when the device really changes area, as async_apply does.
                    "area_moves": bool(
                        entity.area_id
                        and device.area_id
                        and device.area_id != area_id
                        and entity.area_id == device.area_id
                    ),
                    "disabled": entity.disabled_by is not None,
                    "conflict": conflict,
                }
            )
        rows.append(
            {
                "device_id": device.id,
                "name": name,
                "new_name": new_name,
                "area_id": device.area_id,
                "area_name": area.name if area else None,
                "linked_to": linked.get(device.id),
                "already_there": device.area_id == area_id,
                "entities": entity_rows,
            }
        )

    found = await async_find(hass, old_ids, from_areas=from_areas, to_area=area_id)
    return {
        "area_id": area_id,
        "area_name": new_area.name,
        "devices": rows,
        "references": [ref.as_dict() for ref in found.references],
        "area_targets": [target.as_dict() for target in found.area_targets],
    }


def _shown_name(hass: HomeAssistant, entity: er.RegistryEntry) -> str:
    if state := hass.states.get(entity.entity_id):
        return str(state.attributes.get("friendly_name") or entity.entity_id)
    return entity.name or entity.original_name or entity.entity_id


async def async_apply(
    hass: HomeAssistant,
    area_id: str,
    devices_in: list[Mapping[str, Any]],
    entities_in: list[Mapping[str, Any]],
    *,
    context: Any = None,
) -> dict[str, Any]:
    """Move and rename what the preview (with the person's edits) lists.

    ``devices_in``: {device_id, new_name?}. ``entities_in``: {entity_id,
    new_entity_id?, new_name?}. A blank or unchanged value leaves that part
    alone. Every new entity ID is checked again; one that is invalid, in
    another domain or already used fails the whole move before anything
    changes.

    Only the device and entity registries change. Automations, scripts,
    scenes and helpers that use a renamed entity ID are returned in
    ``needs_updating`` (found before the IDs change), each with the
    old -> new IDs it uses, for the person to update in the editor.
    """
    areas = ar.async_get(hass)
    if areas.async_get_area(area_id) is None:
        raise HomeAssistantError(f"Unknown area {area_id}")
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    moving = [d for d in devices_in if devices.async_get(str(d.get("device_id")))]
    moving_ids = {str(d["device_id"]) for d in moving}

    renames: dict[str, str] = {}
    name_changes: dict[str, str | None] = {}
    for item in entities_in:
        entity_id = str(item.get("entity_id") or "")
        entry = entities.async_get(entity_id)
        if entry is None or entry.device_id not in moving_ids:
            continue
        new_entity_id = str(item.get("new_entity_id") or "").strip()
        if new_entity_id and new_entity_id != entity_id:
            if (
                not valid_entity_id(new_entity_id)
                or new_entity_id.split(".", 1)[0] != entity_id.split(".", 1)[0]
            ):
                raise HomeAssistantError(f"{new_entity_id} is not a valid entity ID")
            if (
                new_entity_id in renames.values()
                or entities.async_get(new_entity_id) is not None
                or hass.states.get(new_entity_id) is not None
            ):
                raise HomeAssistantError(f"{new_entity_id} is already used")
            renames[entity_id] = new_entity_id
        if "new_name" in item and item["new_name"] is not None:
            new_name = str(item["new_name"]).strip()
            current = entry.name or (
                None if entry.has_entity_name else entry.original_name
            )
            if new_name != (current or ""):
                name_changes[entity_id] = new_name or None

    # Find what uses the old IDs before they change.
    references: list[Reference] = []
    if renames:
        found = await async_find(hass, list(renames), from_areas=set(), to_area=None)
        references = found.references

    renamed_entities = []
    for entity_id in {*renames, *name_changes}:
        changes: dict[str, Any] = {}
        if entity_id in renames:
            changes["new_entity_id"] = renames[entity_id]
        if entity_id in name_changes:
            changes["name"] = name_changes[entity_id]
        entities.async_update_entity(entity_id, **changes)
        renamed_entities.append(
            {"entity_id": entity_id, "new_entity_id": renames.get(entity_id, entity_id)}
        )

    moved = []
    for item in moving:
        device = devices.async_get(str(item["device_id"]))
        if device is None:
            continue
        old_area = device.area_id
        changes = {"area_id": area_id}
        new_name = str(item.get("new_name") or "").strip()
        if new_name and new_name != _device_name(device):
            changes["name_by_user"] = new_name
        devices.async_update_device(device.id, **changes)
        # Entities placed in the device's old area by hand follow it.
        if old_area and old_area != area_id:
            for entity in er.async_entries_for_device(
                entities, device.id, include_disabled_entities=True
            ):
                if entity.area_id == old_area:
                    entities.async_update_entity(entity.entity_id, area_id=area_id)
        moved.append(device.id)

    # Nothing is edited for the person: list what still uses the old IDs,
    # with the new ID for each, so the panel can link to the editor.
    needs_updating = [
        {**ref.as_dict(), "renames": {old: renames[old] for old in ref.uses}}
        for ref in references
    ]
    result = {
        "area_id": area_id,
        "moved": moved,
        "renamed_entities": renamed_entities,
        "needs_updating": needs_updating,
    }
    hass.bus.async_fire(
        EVENT_MOVED,
        {"area_id": area_id, "device_ids": moved, "renamed": renames},
        context=context,
    )
    return result
