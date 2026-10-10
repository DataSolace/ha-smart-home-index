from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from . import feed
from .const import CONF_PANEL, DOMAIN, FEED_URL
from .coordinator import make_fetch


def _schema(d: dict) -> vol.Schema:
    return vol.Schema({vol.Required(CONF_PANEL, default=d.get(CONF_PANEL, True)): bool})


class ShiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # The first run needs the network: there is no catalog on disk yet.
            try:
                await feed.refresh(make_fetch(self.hass), FEED_URL, None, "")
            except feed.FeedError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Smart Home Index", data={}, options=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ShiOptionsFlow()


class ShiOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=_schema(dict(self.config_entry.options)))
