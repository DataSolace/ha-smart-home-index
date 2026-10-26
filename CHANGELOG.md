# Changelog

## 0.1.1 (2026-10-26)

Dependency and CI maintenance. The integration's code is the same as 0.1.0, and it still installs no Python packages of its own, so none of the advisories below reached a Home Assistant install through it.

- Test harness: `pytest-homeassistant-custom-component` 0.13.371 to 0.13.375 (Home Assistant 2026.10.0 to 2026.10.4) and `home-assistant-frontend` 20260930.2 to 20260930.5.
- The test environment gets `certifi` 2026.10.19 or newer, which drops the emSign root CAs whose intermediate keys were compromised (GHSA-6q48-6c7w-9gw2, critical). Moving to HA 2026.10.4 also brings `uv` 0.13.5, fixing the same CA problem in uv's own store (GHSA-hq85-5cpj-mr62, critical).
- CI: `actions/checkout` v5 to v7 and `actions/setup-python` v6 to v7.
- Not fixed yet: Home Assistant 2026.10.x pins Pillow 12.3.0, which has 37 open advisories (CVE-2026-96636 and others, fixed in Pillow 13.0.0). Our tests never open an image. HA's development branch already pins Pillow 13.0.0, so the test pin moves with HA 2026.11.

## 0.1.0 (2026-10-10)

First release candidate, for install as a HACS custom repository.

- Downloads the catalog from `smarthomeindex.com/api/catalog-lite` once a day, revalidating with the ETag. The last good copy stays in Home Assistant's storage, so the integration keeps working offline after the first setup.
- One Repairs issue per end-of-life model, with a short title that fits the Settings card and the full name, the devices and the successor in the description. Both links go to Smart Home Index.
- A sidebar page with four tabs: overview, your devices, ideas for categories your home lacks, and the devices it couldn't match, with Link and Ignore.
- Four diagnostic sensors on the integration's own page: matched, unmatched, ignored and end-of-life counts.
- A diagnostics download listing unmatched model strings and the links you made.
- Brand icon and logo, with light variants for dark themes.
- Removed from the prototype: the bundled catalog snapshot, the region option (links do not take one) and the telemetry checkbox (nothing was built behind it).
