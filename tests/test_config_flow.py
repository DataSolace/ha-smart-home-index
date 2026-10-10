"""The config flow against a real Home Assistant core. Skipped when pytest-homeassistant-custom-component is absent."""

import json
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402

from custom_components.smart_home_index.const import DOMAIN, FEED_URL  # noqa: E402

CATALOG = json.dumps({"version": 1, "count": 1, "devices": [{"id": "a", "name": "Widget (W-1000)"}]})


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations):
    yield


async def test_setup_downloads_the_catalog_and_creates_the_entry(hass, aioclient_mock):
    aioclient_mock.get(FEED_URL, text=CATALOG, headers={"ETag": '"abc"', "Content-Type": "application/json"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {}

    with patch("custom_components.smart_home_index.async_setup_entry", return_value=True) as setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"show_panel": False})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Smart Home Index" and result["options"] == {"show_panel": False}
    assert aioclient_mock.call_count == 1 and setup.call_count == 1


async def test_setup_without_network_shows_an_error_and_no_entry(hass, aioclient_mock):
    aioclient_mock.get(FEED_URL, exc=OSError("offline"))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"show_panel": True})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_only_one_entry_is_allowed(hass, aioclient_mock):
    aioclient_mock.get(FEED_URL, text=CATALOG)
    with patch("custom_components.smart_home_index.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        await hass.config_entries.flow.async_configure(result["flow_id"], {"show_panel": True})
        await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "single_instance_allowed"
