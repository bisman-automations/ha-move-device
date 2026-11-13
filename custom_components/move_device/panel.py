"""The Move Device sidebar panel (admins only).

The static path is registered once in ``async_setup``; the panel itself is
added while the config entry is loaded. Only when the frontend is running
(not in tests).
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration

from .const import DOMAIN, PANEL_COMPONENT, PANEL_PATH, STATIC_URL

FRONTEND_DIR = Path(__file__).parent / "frontend"
DATA_STATIC = f"{DOMAIN}_static"
DATA_PANEL = f"{DOMAIN}_panel"


def _frontend_ready(hass: HomeAssistant) -> bool:
    return "frontend" in hass.config.components and hass.http is not None


async def async_register_static(hass: HomeAssistant) -> None:
    if hass.data.get(DATA_STATIC) or not _frontend_ready(hass):
        return
    from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
    )
    hass.data[DATA_STATIC] = True


async def async_register_panel(hass: HomeAssistant) -> None:
    if hass.data.get(DATA_PANEL) or not _frontend_ready(hass):
        return
    await async_register_static(hass)
    from homeassistant.components import panel_custom  # noqa: PLC0415

    version = (await async_get_integration(hass, DOMAIN)).version
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title="Move Device",
        sidebar_icon="mdi:home-switch-outline",
        # The version in the URL makes browsers load the new script after an update.
        module_url=f"{STATIC_URL}/{PANEL_COMPONENT}.js?v={version}",
        require_admin=True,
    )
    hass.data[DATA_PANEL] = True


@callback
def async_remove_panel(hass: HomeAssistant) -> None:
    if not hass.data.pop(DATA_PANEL, False):
        return
    from homeassistant.components import frontend  # noqa: PLC0415

    frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
