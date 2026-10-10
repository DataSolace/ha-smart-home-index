from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_PANEL, CONF_REGION, CONF_TELEMETRY, DOMAIN, REGIONS


def _schema(d: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_REGION, default=d.get(CONF_REGION, "en")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value=k, label=v) for k, v in REGIONS.items()],
                                          mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_PANEL, default=d.get(CONF_PANEL, True)): bool,
        vol.Required(CONF_TELEMETRY, default=d.get(CONF_TELEMETRY, False)): bool,
    })


def _catalog_size() -> int:
    import json
    from pathlib import Path
    return len(json.loads((Path(__file__).parent / "data" / "catalog_snapshot.json").read_text())["devices"])


class ShiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Smart Home Index", data={}, options=user_input)
        count = await self.hass.async_add_executor_job(_catalog_size)
        return self.async_show_form(step_id="user", data_schema=_schema({}), description_placeholders={"count": str(count)})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ShiOptionsFlow()


class ShiOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=_schema(dict(self.config_entry.options)))
