# Smart Home Index for Home Assistant

Checks the devices in your Home Assistant against the [Smart Home Index](https://smarthomeindex.com) catalog. It tells you which of your devices are end of life and what replaced them, and which kinds of device your home doesn't have yet.

**Status: preview.** It runs, but it matches only part of a typical house and it isn't in the HACS store yet.

## What it does

- **Repairs.** One entry per end-of-life model you own, naming the devices and the successor. "Learn more" opens a side-by-side comparison on Smart Home Index.
- **A sidebar page** with four tabs: an overview, your matched devices with their SHI rating, ideas for categories your home lacks, and the devices it couldn't match.
- **Link and ignore.** If a device didn't match, search the catalog and link it. If it will never be in the catalog (a 3D printer plug, say), ignore it. Both choices are saved on your Home Assistant.
- **Four diagnostic sensors** on the integration's own page: matched, unmatched, ignored and end-of-life counts.

It doesn't add anything to your dashboards or create persistent notifications.

## Privacy

Matching runs inside Home Assistant. Your device list is not sent anywhere. The only network requests are to smarthomeindex.com for the catalog and for thumbnails in the sidebar page.

## Links

Every link goes to Smart Home Index, never to a shop. Smart Home Index earns from affiliate links on its own website. This integration carries none.

## Install

Not in the HACS store yet. Once the repository is public:

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/DataSolace/ha-smart-home-index` as an **Integration**.
3. Install, restart Home Assistant, then add **Smart Home Index** under Settings > Devices & services.

Needs Home Assistant 2026.10 or newer.

## Matching, and why some devices don't match

The same device reports different model names depending on how it's connected. A SwitchBot hygrometer reports `WoTHP`, which appears nowhere on the box. Matching uses the model number in the catalog name, plus a table of known model strings that people have checked by hand. When yours isn't in either, use **Link** on the "Not in SHI yet" tab. The diagnostics download on the integration page lists the links you made, so you can send them to Smart Home Index and help the next person.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

`custom_components/smart_home_index/matcher.py` holds the matching and ranking logic and imports nothing from Home Assistant, so the tests run without it.

Maintained by [DataSolace](https://github.com/DataSolace).
