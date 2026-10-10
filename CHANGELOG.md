# Changelog

## 0.1.0 (2026-10-10)

First release candidate, for install as a HACS custom repository.

- Downloads the catalog from `smarthomeindex.com/api/catalog-lite` once a day, revalidating with the ETag. The last good copy stays in Home Assistant's storage, so the integration keeps working offline after the first setup.
- One Repairs issue per end-of-life model, with a short title that fits the Settings card and the full name, the devices and the successor in the description. Both links go to Smart Home Index.
- A sidebar page with four tabs: overview, your devices, ideas for categories your home lacks, and the devices it couldn't match, with Link and Ignore.
- Four diagnostic sensors on the integration's own page: matched, unmatched, ignored and end-of-life counts.
- A diagnostics download listing unmatched model strings and the links you made.
- Brand icon and logo, with light variants for dark themes.
- Removed from the prototype: the bundled catalog snapshot, the region option (links do not take one) and the telemetry checkbox (nothing was built behind it).
