"""Automations, scripts, scenes and helpers that use entity IDs a move renames.

Found two ways, together:

- Home Assistant's own lookups (``automations_with_entity`` and friends),
  which cover every automation, script and scene however it was made, but
  only entity IDs in targets and fields, not inside templates.
- The UI-made files (``automations.yaml``, ``scripts.yaml``,
  ``scenes.yaml``), read item by item (in the executor), which also catches
  IDs inside templates.

This module only **finds** and **lists**. It never writes a file, never
reloads anything, and never changes another integration's config entry.
Each :class:`Reference` says whether it was made in the Home Assistant
editor (``in_editor``), so the panel can link straight to the editor where
the person updates it. Anything defined elsewhere (packages, other YAML
files) and helpers are listed to change by hand. Rewriting the YAML for the
person was removed in 0.2.0 after the HACS review (hacs/default#14121):
editing those files behind the editor's back is not something an integration
should do.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .names import uses_entity_ids

_LOGGER = logging.getLogger(__name__)

# kind -> the file in the config folder the Home Assistant editor saves it to.
# Read only, to find entity IDs inside templates; never written.
UI_FILES: dict[str, str] = {
    "automation": "automations.yaml",
    "script": "scripts.yaml",
    "scene": "scenes.yaml",
}


@dataclass
class Reference:
    """One automation, script, scene or helper that uses a renamed ID.

    ``in_editor`` is True for an automation, script or scene made in the
    Home Assistant editor: ``item_id`` then opens it there
    (``/config/<kind>/edit/<item_id>``) and the person updates it to the new
    entity IDs. False means it lives in YAML Move Device doesn't know the
    editor can open (a package, an ``!include``), or it is a helper; the
    person changes those by hand.
    """

    kind: str
    name: str
    uses: list[str]
    in_editor: bool
    entity_id: str | None = None
    item_id: str | None = None
    entry_id: str | None = None
    domain: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AreaTarget:
    """An automation or script that targets the device's old or new area."""

    kind: str
    entity_id: str
    name: str
    area_id: str
    leaving: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _UiItem:
    kind: str
    item_id: str
    text: str
    alias: str | None = None


@dataclass
class Found:
    references: list[Reference] = field(default_factory=list)
    area_targets: list[AreaTarget] = field(default_factory=list)


def _read_ui_items(config_dir: str) -> list[_UiItem]:
    """Every item in the UI-made files, as text. Runs in the executor."""
    from homeassistant.util.yaml import Secrets, load_yaml  # noqa: PLC0415

    secrets = Secrets(Path(config_dir))
    items: list[_UiItem] = []
    for kind, filename in UI_FILES.items():
        path = Path(config_dir) / filename
        if not path.is_file():
            continue
        try:
            data = load_yaml(str(path), secrets)
        except Exception:  # noqa: BLE001 - a broken file is reported by its owner
            _LOGGER.debug("Could not read %s", path, exc_info=True)
            continue
        if kind == "script" and isinstance(data, dict):
            pairs = [(str(key), value) for key, value in data.items()]
        elif isinstance(data, list):
            pairs = [
                (str(item.get("id")), item)
                for item in data
                if isinstance(item, dict) and item.get("id") is not None
            ]
        else:
            continue
        for item_id, value in pairs:
            alias = value.get("alias") if isinstance(value, dict) else None
            text = json.dumps(value, default=str, ensure_ascii=False)
            items.append(_UiItem(kind, item_id, text, alias or None))
    return items


def _entity_for_item(hass: HomeAssistant, kind: str, item_id: str) -> str | None:
    """The automation, script or scene entity a UI-made item creates."""
    platform = "homeassistant" if kind == "scene" else kind
    return er.async_get(hass).async_get_entity_id(kind, platform, item_id)


def _item_for_entity(hass: HomeAssistant, entity_id: str) -> str | None:
    entry = er.async_get(hass).async_get(entity_id)
    return entry.unique_id if entry else None


def _name(hass: HomeAssistant, entity_id: str | None, fallback: str) -> str:
    if entity_id and (state := hass.states.get(entity_id)):
        return str(state.attributes.get("friendly_name") or fallback)
    return fallback


def _core_lookups(hass: HomeAssistant, entity_id: str) -> list[tuple[str, str]]:
    """(kind, automation/script/scene entity id) from Home Assistant's lookups."""
    found: list[tuple[str, str]] = []
    lookups: list[tuple[str, str, str]] = [
        (
            "automation",
            "homeassistant.components.automation",
            "automations_with_entity",
        ),
        ("script", "homeassistant.components.script", "scripts_with_entity"),
        ("scene", "homeassistant.components.homeassistant.scene", "scenes_with_entity"),
    ]
    for kind, module_name, func_name in lookups:
        if kind not in hass.config.components:
            continue
        try:
            module = __import__(module_name, fromlist=[func_name])
            found.extend(
                (kind, eid) for eid in getattr(module, func_name)(hass, entity_id)
            )
        except Exception:  # noqa: BLE001 - a lookup that fails only means fewer hints
            _LOGGER.debug("%s lookup failed", kind, exc_info=True)
    return found


def _area_lookups(hass: HomeAssistant, area_id: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for kind, module_name, func_name in (
        ("automation", "homeassistant.components.automation", "automations_with_area"),
        ("script", "homeassistant.components.script", "scripts_with_area"),
    ):
        if kind not in hass.config.components:
            continue
        try:
            module = __import__(module_name, fromlist=[func_name])
            found.extend(
                (kind, eid) for eid in getattr(module, func_name)(hass, area_id)
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("%s area lookup failed", kind, exc_info=True)
    return found


async def async_find(
    hass: HomeAssistant,
    old_ids: list[str],
    *,
    from_areas: set[str],
    to_area: str,
) -> Found:
    """Everything that uses ``old_ids``, and what targets the areas involved."""
    found = Found()
    if old_ids:
        items = await hass.async_add_executor_job(
            _read_ui_items, hass.config.config_dir
        )
        by_entity: dict[str, Reference] = {}
        ui_entities: set[str] = set()
        for item in items:
            entity_id = _entity_for_item(hass, item.kind, item.item_id)
            if entity_id:
                ui_entities.add(entity_id)
            uses = uses_entity_ids(item.text, old_ids)
            if not uses:
                continue
            ref = Reference(
                kind=item.kind,
                name=_name(hass, entity_id, item.alias or item.item_id),
                uses=uses,
                in_editor=True,
                entity_id=entity_id,
                item_id=item.item_id,
            )
            found.references.append(ref)
            by_entity[entity_id or f"{item.kind}:{item.item_id}"] = ref
        for old in old_ids:
            for kind, entity_id in _core_lookups(hass, old):
                if ref := by_entity.get(entity_id):
                    if old not in ref.uses:
                        ref.uses.append(old)
                    continue
                ref = Reference(
                    kind=kind,
                    name=_name(hass, entity_id, entity_id),
                    uses=[old],
                    in_editor=entity_id in ui_entities,
                    entity_id=entity_id,
                    item_id=_item_for_entity(hass, entity_id),
                )
                found.references.append(ref)
                by_entity[entity_id] = ref
        for entry in hass.config_entries.async_entries():
            if entry.domain == DOMAIN:
                continue
            text = json.dumps(
                {"data": dict(entry.data), "options": dict(entry.options)},
                default=str,
                ensure_ascii=False,
            )
            if uses := uses_entity_ids(text, old_ids):
                found.references.append(
                    Reference(
                        kind="helper",
                        name=entry.title,
                        uses=uses,
                        in_editor=False,
                        entry_id=entry.entry_id,
                        domain=entry.domain,
                    )
                )
    seen: set[tuple[str, bool]] = set()
    for area_id, leaving in [(a, True) for a in sorted(from_areas)] + [
        (to_area, False)
    ]:
        for kind, entity_id in _area_lookups(hass, area_id):
            if (entity_id, leaving) in seen:
                continue
            seen.add((entity_id, leaving))
            found.area_targets.append(
                AreaTarget(
                    kind, entity_id, _name(hass, entity_id, entity_id), area_id, leaving
                )
            )
    return found
