"""Match Home Assistant devices to the SHI catalog. Pure Python, no HA imports."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

SITE = "https://smarthomeindex.com"
BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# HA manufacturer strings that differ from SHI's.
MANUFACTURER_ALIASES = {
    "tplink": ["tplinkkasa", "tapo", "kasa"],
    "sonoff": ["sonoff", "itead"],
    "googleinc": ["google"],
    "ubiquitinetworks": ["ubiquiti", "unifi"],
}

# Entity signals that mean a category is already covered, whatever the device.
CATEGORY_SIGNALS = {
    "Lighting": [("light", None)],
    "Presence Detection": [("binary_sensor", "motion"), ("binary_sensor", "occupancy"), ("binary_sensor", "presence")],
    "Door, Window Sensor": [("binary_sensor", "door"), ("binary_sensor", "window"), ("binary_sensor", "opening")],
    "Environment Sensor": [("sensor", "temperature"), ("sensor", "humidity")],
    "Plug, Socket": [("switch", "outlet")],
    "Climate Control": [("climate", None)],
    "Lock, Access Control": [("lock", None)],
    "Window Cover": [("cover", None)],
    "Vacuum": [("vacuum", None)],
    "Cameras and CCTV": [("camera", None)],
    "Utility Monitoring": [("sensor", "energy")],
    "Button, Switch, Control": [("event", "button")],
}
SUGGEST_CATEGORIES = ["Presence Detection", "Door, Window Sensor", "Environment Sensor", "Plug, Socket",
                      "Climate Control", "Lock, Access Control", "Window Cover", "Utility Monitoring", "Lighting"]

# Integrations that imply the house speaks a protocol.
PROTOCOL_SIGNALS = {
    "zha": "Zigbee", "mqtt": "Zigbee", "zwave_js": "Z-Wave", "matter": "Thread", "thread": "Thread",
    "switchbot": "Bluetooth", "esphome": "Bluetooth", "bluetooth": "Bluetooth",
    "tplink": "Wi-Fi", "tasmota": "Wi-Fi", "shelly": "Wi-Fi", "tuya": "Wi-Fi",
}


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def hash_uuid(uuid: str) -> str:
    num, out = int(uuid.replace("-", ""), 16), ""
    while num:
        num, r = divmod(num, 62)
        out = BASE62[r] + out
    return out.rjust(22, "0")


def utm(surface: str) -> str:
    return f"utm_source=home-assistant&utm_medium=integration&utm_campaign={surface}"


def device_url(shi_id: str, surface: str) -> str:
    return f"{SITE}/?deviceId={shi_id}&{utm(surface)}"


def compare_url(ids: list[str], surface: str) -> str:
    return f"{SITE}/compare/{'...'.join(hash_uuid(i) for i in ids)}?{utm(surface)}"


def _mfr_ok(ha_mfr: str, shi_mfr: str) -> bool:
    a, b = norm(ha_mfr), norm(shi_mfr)
    if not a or not b:
        return False
    cands = [a] + MANUFACTURER_ALIASES.get(a, [])
    return any(c[:4] in b or b[:4] in c for c in cands)


# Words a product name tends to contain, by what the device exposes. Only used to rank near misses.
HINTS = {
    ("sensor", "temperature"): ["thermo", "temperature", "hygro", "climate", "meter"],
    ("sensor", "humidity"): ["hygro", "humidity", "thermo", "meter"],
    ("sensor", "co2"): ["co2", "air"],
    ("binary_sensor", "motion"): ["motion", "presence"],
    ("binary_sensor", "occupancy"): ["presence", "occupancy"],
    ("binary_sensor", "door"): ["door", "window", "contact"],
    ("binary_sensor", "moisture"): ["leak", "water"],
    ("light", None): ["bulb", "light", "strip", "lamp"],
    ("switch", "outlet"): ["plug", "socket"],
    ("lock", None): ["lock"],
    ("cover", None): ["blind", "curtain", "shutter", "roller"],
    ("camera", None): ["cam", "camera"],
}


def hints_from(signals) -> list[str]:
    sigs = {tuple(x) for x in signals or []}
    out = []
    for (d, c), words in HINTS.items():
        if (d, c) in sigs or (c is None and any(x[0] == d for x in sigs)):
            out += [w for w in words if w not in out]
    return out


def categories_from(signals) -> list[str]:
    """Guess SHI categories from the entities a device exposes, e.g. temperature + humidity -> Environment Sensor."""
    sigs = {tuple(x) for x in signals or []}
    return [cat for cat, wanted in CATEGORY_SIGNALS.items()
            if any((d, c) in sigs or (c is None and any(s[0] == d for s in sigs)) for d, c in wanted)]


def link_key(manufacturer, model_id, model) -> str:
    """Links are per model string, so linking one hygrometer links every copy of it."""
    return f"{norm(manufacturer)}|{norm(model_id or model)}"


def search(catalog: list[dict], query: str, manufacturer: str | None = None, limit: int = 8,
           categories: list[str] | None = None, hints: list[str] | None = None) -> list[dict]:
    """Find catalog records by name. With no query, return the same manufacturer's records (the near misses)."""
    words = [w for w in re.split(r"[^a-z0-9]+", (query or "").lower()) if w]
    out = []
    for d in catalog:
        same_mfr = bool(manufacturer) and _mfr_ok(manufacturer, d["manufacturer"])
        hay = (d["name"] + " " + d["manufacturer"]).lower()
        if words:
            if not all(w in hay for w in words):
                continue
        elif not same_mfr:
            continue
        in_cat = bool(categories) and bool(set(categories) & set(d["category"] or []))
        name = d["name"].lower()
        hit = sum(1 for h in hints or [] if h in name)
        out.append((same_mfr, in_cat, hit, d["spousalApprovalRating"] or 0, d))
    out.sort(key=lambda t: t[:4], reverse=True)
    return [{"id": d["id"], "name": d["name"], "manufacturer": d["manufacturer"], "rating": d["spousalApprovalRating"],
             "end_of_life": bool(d["endOfLife"]), "same_manufacturer": same, "same_category": cat}
            for same, cat, _, _, d in out[:limit]]


@dataclass
class Report:
    matched: list = field(default_factory=list)
    unmatched: list = field(default_factory=list)
    ignored: list = field(default_factory=list)
    end_of_life: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    protocols: list = field(default_factory=list)
    considered: int = 0

    def as_dict(self) -> dict:
        return {"considered": self.considered, "matched": self.matched, "unmatched": self.unmatched, "ignored": self.ignored,
                "end_of_life": self.end_of_life, "gaps": self.gaps, "protocols": self.protocols}


def build_report(catalog: list[dict], aliases: dict, devices: list[dict], entities: list[tuple[str, str | None]],
                 domains: set[str], links: dict[str, str] | None = None, ignored: set[str] | None = None) -> Report:
    """devices: dicts with id, name, manufacturer, model, model_id, sw_version, domain, connections."""
    by_id = {d["id"]: d for d in catalog}
    by_token = defaultdict(list)
    for d in catalog:
        for t in d.get("modelTokens") or []:
            by_token[norm(t)].append(d)
    ignore = aliases.get("ignore", {})

    def resolve_alias(dev):
        for r in aliases.get("rules", []):
            if norm(r["manufacturer"]) == norm(dev["manufacturer"]) and norm(r["model_id"]) in (norm(dev["model_id"]), norm(dev["model"])):
                sid = r["shi_id"]
                if sid.startswith("@token:"):
                    hits = by_token.get(norm(sid[7:]))
                    return hits[0] if hits else None
                return by_id.get(sid)
        return None

    links, ignored = links or {}, ignored or set()
    rep = Report()
    seen = set()
    for dev in devices:
        if dev["id"] in ignored:
            rep.ignored.append({"device_id": dev["id"], "name": dev["name"], "integration": dev["domain"],
                                "manufacturer": dev["manufacturer"], "model": dev["model"], "model_id": dev["model_id"]})
            continue
        if dev["domain"] in ignore.get("integrations", []) or dev["model"] in ignore.get("models", []):
            continue
        # The same thing often appears twice (e.g. tplink and unifi). Dedupe on MAC, then on make/model/firmware.
        macs = {c[1].lower() for c in dev.get("connections") or [] if c[0] == "mac"}
        key = frozenset(macs) or (norm(dev["manufacturer"]), norm(dev["model"]), dev["sw_version"], norm(dev["name"]))
        if dev["domain"] == "unifi" and norm(dev["manufacturer"]) != "ubiquitinetworks":
            continue  # unifi lists network clients as devices; the owning integration reports them properly
        if key in seen:
            continue
        seen.add(key)
        rep.considered += 1

        lk = link_key(dev["manufacturer"], dev["model_id"], dev["model"])
        hit, how = by_id.get(links.get(lk)), "your link"
        if not hit:
            hit, how = resolve_alias(dev), "alias table"
        if not hit:
            how = "model number"
            for k in (dev["model_id"], dev["model"]):
                cands = [c for c in by_token.get(norm(k), []) if _mfr_ok(dev["manufacturer"], c["manufacturer"])]
                if cands:
                    hit = cands[0]
                    break
        if not hit:
            rep.unmatched.append({"device_id": dev["id"], "name": dev["name"], "integration": dev["domain"],
                                  "categories": categories_from(dev.get("signals")), "hints": hints_from(dev.get("signals")), "manufacturer": dev["manufacturer"], "model": dev["model"], "model_id": dev["model_id"]})
            continue
        m = {"device_id": dev["id"], "name": dev["name"], "integration": dev["domain"], "sw_version": dev["sw_version"],
             "matched_by": how, "link_key": lk, "shi_id": hit["id"], "shi_name": hit["name"], "category": hit["category"],
             "rating": hit["spousalApprovalRating"], "end_of_life": bool(hit["endOfLife"]),
             "replacements": hit.get("eolReplacements") or [], "notes_url": hit.get("selfhostingRepoUrl"),
             "url": device_url(hit["id"], "device")}
        rep.matched.append(m)

    # Group EoL by catalog record: eight SNZB-02s are one problem, not eight.
    groups = defaultdict(list)
    for m in rep.matched:
        if m["end_of_life"]:
            groups[m["shi_id"]].append(m)
    for sid, ms in groups.items():
        reps = ms[0]["replacements"]
        tokens = (by_id.get(sid) or {}).get("modelTokens") or []
        rep.end_of_life.append({
            "shi_id": sid, "shi_name": ms[0]["shi_name"], "short_name": tokens[0] if tokens else ms[0]["shi_name"],
            "count": len(ms), "devices": [m["name"] for m in ms],
            "rating": ms[0]["rating"],
            "replacements": [{"id": r["id"], "name": r["name"], "url": device_url(r["id"], "repairs"),
                              "rating": (by_id.get(r["id"]) or {}).get("spousalApprovalRating")} for r in reps],
            "compare_url": compare_url([sid] + [r["id"] for r in reps], "repairs") if reps else None,
            "url": device_url(sid, "repairs"),
        })
    rep.end_of_life.sort(key=lambda g: -g["count"])

    # Protocol fit and category gaps.
    protos = Counter(PROTOCOL_SIGNALS[d] for d in domains if d in PROTOCOL_SIGNALS)
    for m in rep.matched:
        protos.update((by_id[m["shi_id"]].get("connectivity") or []))
    rep.protocols = [p for p, _ in protos.most_common()]
    covered = {cat for cat, sigs in CATEGORY_SIGNALS.items() if any(s in entities or (s[1] is None and any(e[0] == s[0] for e in entities)) for s in sigs)}
    covered |= {c for m in rep.matched for c in m["category"]}
    z2m = "mqtt" in domains
    for cat in SUGGEST_CATEGORIES:
        if cat in covered:
            continue
        pool = [d for d in catalog if cat in d["category"] and not d["endOfLife"]
                and set(d["connectivity"] or []) & set(rep.protocols[:3])
                and not (d.get("requiredDevices"))]
        def score(d):
            fit = len(set(d["connectivity"]) & set(rep.protocols[:2]))
            return (d["spousalApprovalRating"] or 0, fit, z2m and "Zigbee2MQTT" in (d["ecosystem"] or []))
        pool.sort(key=score, reverse=True)
        rep.gaps.append({"category": cat, "suggestions": [{
            "id": d["id"], "name": d["name"], "rating": d["spousalApprovalRating"], "connectivity": d["connectivity"],
            "why": [p for p in d["connectivity"] if p in rep.protocols[:3]]
                   + (["works with Zigbee2MQTT"] if z2m and "Zigbee2MQTT" in (d["ecosystem"] or []) else [])
                   + (["Home Assistant certified"] if "Home Assistant (Certified)" in (d["ecosystem"] or []) else []),
            "url": device_url(d["id"], "gaps")} for d in pool[:3]]})
    return rep
