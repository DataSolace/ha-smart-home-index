from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SIGNAL = f"{DOMAIN}_updated"

COUNTS = {
    "matched": ("Matched devices", "mdi:link-variant",
                lambda r: len(r["matched"]),
                lambda r: {"considered": r["considered"], "catalog_size": r["catalog_size"],
                           "catalog_fetched_at": r["catalog"]["fetched_at"], "catalog_checked_at": r["catalog"]["checked_at"]}),
    "unmatched": ("Unmatched devices", "mdi:help-circle-outline",
                  lambda r: len(r["unmatched"]), lambda r: {"devices": [f"{u['manufacturer']} {u['model_id'] or u['model']}" for u in r["unmatched"]]}),
    "ignored": ("Ignored devices", "mdi:eye-off-outline", lambda r: len(r["ignored"]), lambda r: {}),
    "end_of_life": ("End-of-life devices", "mdi:skull-outline",
                    lambda r: sum(g["count"] for g in r["end_of_life"]), lambda r: {"models": [g["shi_name"] for g in r["end_of_life"]]}),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    hub = DeviceInfo(identifiers={(DOMAIN, "catalog")}, name="Smart Home Index", manufacturer="DataSolace",
                     model="Device catalog", entry_type=DeviceEntryType.SERVICE,
                     configuration_url="https://smarthomeindex.com/?utm_source=home-assistant&utm_medium=integration&utm_campaign=service-device")
    add([Count(entry, hub, key) for key in COUNTS])


class Count(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, hub, key):
        self._entry, self._key = entry, key
        name, icon, _, _ = COUNTS[key]
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name, self._attr_icon, self._attr_device_info = name, icon, hub

    @property
    def native_value(self):
        return COUNTS[self._key][2](self._entry.runtime_data.report)

    @property
    def extra_state_attributes(self):
        return COUNTS[self._key][3](self._entry.runtime_data.report)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL, self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()
