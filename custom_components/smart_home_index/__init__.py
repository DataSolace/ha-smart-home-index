"""Smart Home Index preview: matches this house's devices against the SHI catalog."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import CONF_PANEL, DOMAIN, PANEL_URL, STATIC_URL
from .matcher import build_report, link_key, search

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]
HERE = Path(__file__).parent
SIGNAL = f"{DOMAIN}_updated"


def _load(name: str):
    return json.loads((HERE / "data" / name).read_text())


def _signals(hass: HomeAssistant, entreg, device_id: str) -> list[tuple[str, str | None]]:
    out = []
    for e in er.async_entries_for_device(entreg, device_id):
        st = hass.states.get(e.entity_id)
        out.append((e.domain, (st.attributes.get("device_class") if st else None) or e.original_device_class))
    return out


def _inventory(hass: HomeAssistant):
    devreg, entreg = dr.async_get(hass), er.async_get(hass)
    devices = []
    for d in list(devreg.devices):
        d = devreg.devices[d] if isinstance(d, str) else d
        if d.entry_type is dr.DeviceEntryType.SERVICE or d.disabled_by:
            continue
        entry = hass.config_entries.async_get_entry(d.config_entry_id)
        if entry is None or entry.domain == DOMAIN:
            continue
        devices.append({"id": d.id, "name": d.name_by_user or d.name, "manufacturer": d.manufacturer, "model": d.model,
                        "model_id": d.model_id, "sw_version": d.sw_version, "domain": entry.domain,
                        "connections": [list(c) for c in d.connections],
                        "identifiers": [list(i) for i in d.identifiers],
                        "signals": _signals(hass, entreg, d.id)})
    entities = [(s.domain, s.attributes.get("device_class")) for s in hass.states.async_all()]
    domains = {e.domain for e in hass.config_entries.async_entries() if e.state is ConfigEntryState.LOADED}
    return devices, entities, domains


def _recompute(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = entry.runtime_data
    devices, entities, domains = _inventory(hass)
    user = data["user"]
    report = build_report(data["catalog"], data["aliases"], devices, entities, domains,
                          links=user["links"], ignored=set(user["ignored"])).as_dict()
    report["region"] = entry.options.get("region", "en")
    report["catalog_size"] = len(data["catalog"])
    data["report"] = report
    _sync_issues(hass, report)
    async_dispatcher_send(hass, SIGNAL)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    catalog = (await hass.async_add_executor_job(_load, "catalog_snapshot.json"))["devices"]
    aliases = await hass.async_add_executor_job(_load, "ha_model_ids.json")
    store = Store(hass, 1, f"{DOMAIN}.user_matches")
    user = await store.async_load() or {}
    user.setdefault("links", {})
    user.setdefault("ignored", [])
    entry.runtime_data = {"catalog": catalog, "aliases": aliases, "store": store, "user": user, "report": {}}
    _recompute(hass, entry)

    _remove_stray_devices(hass, entry)
    await _register_frontend(hass, entry)
    for cmd in (ws_report, ws_search, ws_link, ws_unlink, ws_ignore, ws_unignore):
        websocket_api.async_register_command(hass, cmd)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


def _remove_stray_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """HA 2026.10 gives each device one config entry, so only the catalog service device is ours."""
    devreg = dr.async_get(hass)
    for d in dr.async_entries_for_config_entry(devreg, entry.entry_id):
        if (DOMAIN, "catalog") not in d.identifiers:
            devreg.async_remove_device(d.id)


async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device) -> bool:
    return (DOMAIN, "catalog") not in device.identifiers


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _sync_issues(hass: HomeAssistant, report: dict) -> None:
    wanted = set()
    for g in report["end_of_life"]:
        issue_id = f"eol_{g['shi_id']}"
        wanted.add(issue_id)
        rep = g["replacements"][0] if g["replacements"] else None
        ir.async_create_issue(
            hass, DOMAIN, issue_id, is_fixable=False, is_persistent=False, severity=ir.IssueSeverity.WARNING,
            translation_key="eol_with_replacement" if rep else "eol_no_replacement",
            translation_placeholders={
                "model": g["shi_name"], "count": str(g["count"]), "devices": ", ".join(g["devices"]),
                "replacement": rep["name"] if rep else "", "compare_url": g["compare_url"] or g["url"],
                "replacement_url": rep["url"] if rep else "", "url": g["url"],
            },
            learn_more_url=g["compare_url"] or g["url"],
        )
    for (domain, issue_id) in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id not in wanted:
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def _register_frontend(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if not hass.data.get(f"{DOMAIN}_static"):
        await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, str(HERE / "frontend"), False)])
        hass.data[f"{DOMAIN}_static"] = True
    if entry.options.get(CONF_PANEL, True) and PANEL_URL not in hass.data.get(frontend.DATA_PANELS, {}):
        await panel_custom.async_register_panel(
            hass, webcomponent_name="shi-panel", frontend_url_path=PANEL_URL, sidebar_title="Smart Home Index",
            sidebar_icon="mdi:home-search-outline", module_url=f"{STATIC_URL}/shi-panel.js?v=8", require_admin=True,
            config={})


def _entry(hass: HomeAssistant, connection, msg):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_loaded", "Smart Home Index is not set up")
        return None
    return entries[0]


@websocket_api.websocket_command({vol.Required("type"): "smart_home_index/report"})
@websocket_api.require_admin
@callback
def ws_report(hass: HomeAssistant, connection, msg) -> None:
    if (entry := _entry(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], entry.runtime_data["report"])


@websocket_api.websocket_command({vol.Required("type"): "smart_home_index/search", vol.Required("query"): str,
                                  vol.Optional("manufacturer"): vol.Any(str, None),
                                  vol.Optional("categories"): [str], vol.Optional("hints"): [str]})
@websocket_api.require_admin
@callback
def ws_search(hass: HomeAssistant, connection, msg) -> None:
    if (entry := _entry(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], search(entry.runtime_data["catalog"], msg["query"], msg.get("manufacturer"), categories=msg.get("categories"), hints=msg.get("hints")))


async def _save(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = entry.runtime_data
    await data["store"].async_save(data["user"])
    _recompute(hass, entry)


def _find(entry: ConfigEntry, device_id: str) -> dict | None:
    r = entry.runtime_data["report"]
    return next((u for u in r["unmatched"] + r["ignored"] if u["device_id"] == device_id), None)


@websocket_api.websocket_command({vol.Required("type"): "smart_home_index/link", vol.Required("device_id"): str,
                                  vol.Required("shi_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_link(hass: HomeAssistant, connection, msg) -> None:
    if (entry := _entry(hass, connection, msg)) is None:
        return
    dev = _find(entry, msg["device_id"])
    if dev is None or not any(d["id"] == msg["shi_id"] for d in entry.runtime_data["catalog"]):
        connection.send_error(msg["id"], "not_found", "Unknown device or catalog entry")
        return
    entry.runtime_data["user"]["links"][link_key(dev["manufacturer"], dev["model_id"], dev["model"])] = msg["shi_id"]
    await _save(hass, entry)
    connection.send_result(msg["id"], entry.runtime_data["report"])


@websocket_api.websocket_command({vol.Required("type"): "smart_home_index/unlink", vol.Required("link_key"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_unlink(hass: HomeAssistant, connection, msg) -> None:
    if (entry := _entry(hass, connection, msg)) is None:
        return
    entry.runtime_data["user"]["links"].pop(msg["link_key"], None)
    await _save(hass, entry)
    connection.send_result(msg["id"], entry.runtime_data["report"])


@websocket_api.websocket_command({vol.Required("type"): "smart_home_index/ignore", vol.Required("device_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_ignore(hass: HomeAssistant, connection, msg) -> None:
    if (entry := _entry(hass, connection, msg)) is None:
        return
    ignored = entry.runtime_data["user"]["ignored"]
    if msg["device_id"] not in ignored:
        ignored.append(msg["device_id"])
    await _save(hass, entry)
    connection.send_result(msg["id"], entry.runtime_data["report"])


@websocket_api.websocket_command({vol.Required("type"): "smart_home_index/unignore", vol.Required("device_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_unignore(hass: HomeAssistant, connection, msg) -> None:
    if (entry := _entry(hass, connection, msg)) is None:
        return
    ignored = entry.runtime_data["user"]["ignored"]
    if msg["device_id"] in ignored:
        ignored.remove(msg["device_id"])
    await _save(hass, entry)
    connection.send_result(msg["id"], entry.runtime_data["report"])


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    frontend.async_remove_panel(hass, PANEL_URL)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    for (domain, issue_id) in list(ir.async_get(hass).issues):
        if domain == DOMAIN:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
    await Store(hass, 1, f"{DOMAIN}.user_matches").async_remove()
