# Smart Home Index for Home Assistant

Checks the devices in your Home Assistant against the [Smart Home Index](https://smarthomeindex.com) catalog. It tells you which of your devices are end of life and what replaced them, and which kinds of device your home doesn't have yet.

**Status: 0.1.1, an early release.** It works, but it matches only part of a typical house and it isn't in the HACS store yet.

## What it does

- **Repairs.** One entry per end-of-life model you own, naming the devices and the successor. "Learn more" opens a side-by-side comparison on Smart Home Index.
- **A sidebar page** with four tabs: an overview, your matched devices with their SHI rating, ideas for categories your home lacks, and the devices it couldn't match.
- **Link and ignore.** If a device didn't match, search the catalog and link it. If it will never be in the catalog (a 3D printer plug, say), ignore it. Both choices are saved on your Home Assistant.
- **Four diagnostic sensors** on the integration's own page: matched, unmatched, ignored and end-of-life counts.

It doesn't add anything to your dashboards or create persistent notifications.

## Privacy

Matching runs inside Home Assistant. Your device list is not sent anywhere. The only network requests are to smarthomeindex.com for the catalog and for thumbnails in the sidebar page.

## The catalog

The integration downloads the catalog from `https://smarthomeindex.com/api/catalog-lite` when you set it up and once a day after that. The first setup needs an internet connection; after that it keeps the last good copy in Home Assistant's storage and carries on from it if the site is unreachable. The feed carries names, model numbers, categories, protocols, ratings and end-of-life data. It carries no prices or purchase links.

## Links

Every link goes to Smart Home Index, never to a shop. Smart Home Index earns from affiliate links on its own website. This integration carries none.

## Install

Not in the HACS store yet. Once the repository is public:

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/DataSolace/ha-smart-home-index` as an **Integration**.
3. Install, restart Home Assistant, then add **Smart Home Index** under Settings > Devices & services.

Needs Home Assistant 2026.10 or newer. The one option is whether to show the sidebar page; you can change it later from the integration's **Configure** button.

## Matching, and why some devices don't match

The same device reports different model names depending on how it's connected. A SwitchBot hygrometer reports `WoTHP`, which appears nowhere on the box. Matching uses the model number in the catalog name, plus a table of known model strings that people have checked by hand. When yours isn't in either, use **Link** on the "Not in SHI yet" tab. The diagnostics download on the integration page lists the links you made, so you can send them to Smart Home Index and help the next person.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

`matcher.py` (matching and ranking) and `feed.py` (downloading the catalog with ETag revalidation and an offline fallback) import nothing from Home Assistant, so their tests run with plain pytest. The config flow test uses `pytest-homeassistant-custom-component`, which needs Python 3.14, and is skipped when that package is absent.

`scripts/deploy.sh` copies the integration into a Home Assistant docker container over SSH. Its `--feed-url` option points the deployed copy at a local build of the Smart Home Index app.

## Licence

Apache License 2.0, see [LICENSE](LICENSE). The licence covers this code. The Smart Home Index catalog data and name are not part of it.

Maintained by [DataSolace](https://github.com/DataSolace).
