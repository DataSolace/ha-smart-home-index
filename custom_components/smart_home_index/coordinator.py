"""Downloads the Smart Home Index catalog once a day and keeps the last good copy on disk."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import feed
from .const import DOMAIN, FEED_URL

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(hours=24)
TIMEOUT = aiohttp.ClientTimeout(total=60)


def make_fetch(hass: HomeAssistant) -> feed.Fetch:
    session = async_get_clientsession(hass)

    async def fetch(url: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
        async with session.get(url, headers=headers, timeout=TIMEOUT) as resp:
            return resp.status, dict(resp.headers), await resp.read()

    return fetch


class CatalogCoordinator(DataUpdateCoordinator[feed.Catalog]):
    """Holds the catalog. `data.devices` is what the matcher reads."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.url = FEED_URL
        self.store: Store = Store(hass, feed.STORAGE_VERSION, f"{DOMAIN}.catalog")
        self._cached: feed.Catalog | None = None
        self._fetch = make_fetch(hass)

    async def async_load_cache(self) -> None:
        self._cached = feed.Catalog.from_stored(await self.store.async_load())

    async def _async_update_data(self) -> feed.Catalog:
        previous = self.data or self._cached
        try:
            catalog = await feed.refresh(self._fetch, self.url, previous, dt_util.utcnow().isoformat(timespec="seconds"))
        except feed.FeedError as err:
            raise UpdateFailed(f"Could not download the Smart Home Index catalog: {err}") from err
        if catalog.source == "network":
            await self.store.async_save(catalog.as_stored())
            _LOGGER.debug("Catalog downloaded: %d devices", len(catalog.devices))
        elif catalog.source == "cache":
            _LOGGER.warning("Using the catalog downloaded %s: %s", catalog.fetched_at, catalog.note)
        return catalog

    async def async_remove_cache(self) -> None:
        await self.store.async_remove()
