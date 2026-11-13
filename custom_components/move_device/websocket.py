"""The sidebar panel's API: ``move_device/preview`` and ``move_device/apply``.

Both are admin only: a move renames other integrations' devices and
entities, and can edit automations, scripts and scenes.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .planner import Options, async_apply, async_preview

_OPTIONS = vol.Schema(
    {
        vol.Optional("include_linked"): bool,
        vol.Optional("rename_devices"): bool,
        vol.Optional("rename_entity_names"): bool,
        vol.Optional("rename_entity_ids"): bool,
        vol.Optional("find"): str,
        vol.Optional("replace"): str,
    }
)


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_preview)
    websocket_api.async_register_command(hass, ws_apply)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "move_device/preview",
        vol.Required("device_ids"): [str],
        vol.Required("area_id"): str,
        vol.Optional("options"): _OPTIONS,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_preview(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    try:
        result = await async_preview(
            hass,
            msg["device_ids"],
            msg["area_id"],
            Options.from_dict(msg.get("options")),
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "move_device/apply",
        vol.Required("area_id"): str,
        vol.Required("devices"): [
            vol.Schema(
                {
                    vol.Required("device_id"): str,
                    vol.Optional("new_name"): vol.Any(str, None),
                }
            )
        ],
        vol.Optional("entities", default=[]): [
            vol.Schema(
                {
                    vol.Required("entity_id"): str,
                    vol.Optional("new_entity_id"): vol.Any(str, None),
                    vol.Optional("new_name"): vol.Any(str, None),
                }
            )
        ],
        vol.Optional("update_references", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_apply(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    try:
        result = await async_apply(
            hass,
            msg["area_id"],
            msg["devices"],
            msg["entities"],
            update_references=msg["update_references"],
            context=connection.context(msg),
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    connection.send_result(msg["id"], result)
