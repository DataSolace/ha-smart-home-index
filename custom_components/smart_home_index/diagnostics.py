from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    d = entry.runtime_data
    r = d["report"]
    return {
        "what_this_is": "Devices Smart Home Index could not match. Attach this file to an issue so SHI can learn their model strings.",
        "catalog_size": r["catalog_size"],
        "considered": r["considered"],
        "matched": len(r["matched"]),
        "unmatched": [{k: u[k] for k in ("integration", "manufacturer", "model", "model_id")} for u in r["unmatched"]],
        "your_links": d["user"]["links"],
        "ignored_count": len(d["user"]["ignored"]),
        "matched_by": [{"integration": m["integration"], "shi_name": m["shi_name"], "matched_by": m["matched_by"]} for m in r["matched"]],
    }
