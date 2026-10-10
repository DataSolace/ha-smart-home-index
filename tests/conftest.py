"""Load matcher.py and feed.py by path. They import nothing from Home Assistant, so their tests run without it."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "smart_home_index"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"shi_{name}", ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"shi_{name}"] = mod  # dataclasses looks the module up by name
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def matcher():
    return _load("matcher")


@pytest.fixture(scope="session")
def feed():
    return _load("feed")


@pytest.fixture(scope="session")
def aliases():
    return json.loads((ROOT / "data" / "ha_model_ids.json").read_text())


def rec(id_, name, manufacturer, category, connectivity=("Zigbee",), eol=False, replacements=(), rating=4,
        tokens=(), ecosystem=(), required=()):
    return {"id": id_, "name": name, "manufacturer": manufacturer, "category": list(category),
            "connectivity": list(connectivity), "ecosystem": list(ecosystem), "endOfLife": eol,
            "eolReplacements": [{"id": i, "name": n} for i, n in replacements], "requiredDevices": list(required),
            "spousalApprovalRating": rating, "hasSelfHostingNotes": False, "selfhostingRepoUrl": None,
            "modelTokens": list(tokens)}


@pytest.fixture
def catalog():
    return [
        rec("11111111-0000-0000-0000-000000000001", "SONOFF Zigbee Temperature Humidity Sensor (SNZB-02)", "Sonoff",
            ["Environment Sensor"], eol=True, replacements=[("11111111-0000-0000-0000-000000000002", "SONOFF SNZB-02P")],
            rating=3, tokens=["SNZB-02"]),
        rec("11111111-0000-0000-0000-000000000002", "SONOFF SNZB-02P", "Sonoff", ["Environment Sensor"], tokens=["SNZB-02P"]),
        rec("22222222-0000-0000-0000-000000000001", "SwitchBot Indoor/Outdoor Thermo-Hygrometer", "SwitchBot",
            ["Environment Sensor"], connectivity=["Bluetooth"]),
        rec("22222222-0000-0000-0000-000000000002", "SwitchBot Relay Switch 1", "SwitchBot", ["Plug, Socket"],
            connectivity=["Bluetooth"], rating=5),
        rec("33333333-0000-0000-0000-000000000001", "Aqara FP2 (PS-S02D)", "Aqara", ["Presence Detection"],
            connectivity=["Wi-Fi"], rating=5, ecosystem=["Home Assistant (Certified)"]),
    ]


def device(id_, name, manufacturer, model, model_id=None, domain="mqtt", signals=(), connections=(), sw=None):
    return {"id": id_, "name": name, "manufacturer": manufacturer, "model": model, "model_id": model_id,
            "sw_version": sw, "domain": domain, "connections": [list(c) for c in connections], "identifiers": [],
            "signals": [list(s) for s in signals]}
