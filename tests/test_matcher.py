from conftest import device

SNZB = "11111111-0000-0000-0000-000000000001"
HYGRO = "22222222-0000-0000-0000-000000000001"


def report(matcher, catalog, aliases, devices, **kw):
    return matcher.build_report(catalog, aliases, devices, kw.pop("entities", []), kw.pop("domains", {"mqtt"}), **kw).as_dict()


def test_matches_by_model_number_in_the_name(matcher, catalog, aliases):
    d = device("a", "living room", "SONOFF", "Temperature and humidity sensor", "SNZB-02")
    r = report(matcher, catalog, aliases, [d])
    assert r["matched"][0]["shi_id"] == SNZB
    assert r["matched"][0]["matched_by"] == "model number"


def test_model_number_needs_the_right_manufacturer(matcher, catalog, aliases):
    d = device("a", "x", "Acme", "Temperature sensor", "SNZB-02")
    assert report(matcher, catalog, aliases, [d])["unmatched"][0]["device_id"] == "a"


def test_eight_sensors_are_one_end_of_life_issue(matcher, catalog, aliases):
    devs = [device(str(i), f"s{i}", "SONOFF", "x", "SNZB-02") for i in range(8)]
    eol = report(matcher, catalog, aliases, devs)["end_of_life"]
    assert len(eol) == 1 and eol[0]["count"] == 8
    assert eol[0]["replacements"][0]["name"] == "SONOFF SNZB-02P"


def test_links_go_to_shi_only(matcher, catalog, aliases):
    eol = report(matcher, catalog, aliases, [device("a", "s", "SONOFF", "x", "SNZB-02")])["end_of_life"][0]
    urls = [eol["url"], eol["compare_url"]] + [r["url"] for r in eol["replacements"]]
    assert all(u.startswith("https://smarthomeindex.com/") for u in urls)
    assert all("utm_source=home-assistant" in u for u in urls)


def test_link_is_per_model_string(matcher, catalog, aliases):
    devs = [device("a", "Outdoor", "switchbot", "WoTHP", domain="switchbot"),
            device("b", "Garage", "switchbot", "WoTHP", domain="switchbot")]
    assert len(report(matcher, catalog, aliases, devs)["unmatched"]) == 2
    key = matcher.link_key("switchbot", None, "WoTHP")
    r = report(matcher, catalog, aliases, devs, links={key: HYGRO})
    assert [m["matched_by"] for m in r["matched"]] == ["your link", "your link"]
    assert r["unmatched"] == []


def test_a_link_to_a_removed_record_falls_back_to_unmatched(matcher, catalog, aliases):
    d = device("a", "x", "switchbot", "WoTHP", domain="switchbot")
    key = matcher.link_key("switchbot", None, "WoTHP")
    assert len(report(matcher, catalog, aliases, [d], links={key: "gone"})["unmatched"]) == 1


def test_ignored_devices_count_nowhere(matcher, catalog, aliases):
    devs = [device("a", "printer plug", "Tasmota", "FLSUN"), device("b", "s", "SONOFF", "x", "SNZB-02")]
    r = report(matcher, catalog, aliases, devs, ignored={"a"})
    assert r["considered"] == 1 and r["unmatched"] == [] and [i["device_id"] for i in r["ignored"]] == ["a"]


def test_skips_integrations_that_are_not_devices(matcher, catalog, aliases):
    d = device("a", "phone", "Apple", "iPhone14,4", domain="mobile_app")
    assert report(matcher, catalog, aliases, [d])["considered"] == 0


def test_unifi_client_copies_are_skipped(matcher, catalog, aliases):
    d = device("a", "bulb", "TP-Link", "LB130", domain="unifi")
    assert report(matcher, catalog, aliases, [d])["considered"] == 0


def test_the_same_mac_counts_once(matcher, catalog, aliases):
    mac = [("mac", "aa:bb")]
    devs = [device("a", "lamp", "X", "Y", domain="tplink", connections=mac),
            device("b", "lamp", "X", "Y", domain="esphome", connections=mac)]
    assert report(matcher, catalog, aliases, devs)["considered"] == 1


def test_gap_analysis_skips_categories_the_house_has(matcher, catalog, aliases):
    d = device("a", "s", "SONOFF", "x", "SNZB-02")
    r = report(matcher, catalog, aliases, [d], entities=[("sensor", "temperature")])
    assert "Environment Sensor" not in [g["category"] for g in r["gaps"]]


def test_gap_suggestions_fit_the_protocols_in_the_house(matcher, catalog, aliases):
    d = device("a", "s", "SONOFF", "x", "SNZB-02")
    r = report(matcher, catalog, aliases, [d], entities=[("sensor", "temperature")], domains={"mqtt"})
    names = [s["name"] for g in r["gaps"] for s in g["suggestions"]]
    assert "Aqara FP2 (PS-S02D)" not in names  # Wi-Fi only, and the house is Zigbee


def test_search_puts_the_same_manufacturer_and_kind_of_device_first(matcher, catalog):
    sig = [("sensor", "temperature"), ("sensor", "humidity")]
    out = matcher.search(catalog, "", "switchbot", categories=matcher.categories_from(sig), hints=matcher.hints_from(sig))
    assert out[0]["name"].startswith("SwitchBot Indoor/Outdoor")
    assert all(o["same_manufacturer"] for o in out)


def test_search_by_words_ignores_case_and_order(matcher, catalog):
    assert [o["id"] for o in matcher.search(catalog, "HYGRO thermo")] == [HYGRO]


def test_search_with_no_query_and_no_manufacturer_returns_nothing(matcher, catalog):
    assert matcher.search(catalog, "", None) == []


def test_hash_uuid_matches_the_site(matcher):
    # Known pair from smarthomeindex.com: the SNZB-02 and its successor in a compare URL.
    assert matcher.hash_uuid("e19e414b-8046-4a58-bf22-e97e8b76c0ab") == "6rjayJVueis4EQ0lof6P5n"
    assert matcher.hash_uuid("00000000-0000-0000-0000-000000000000") == "0" * 22


def test_alias_table_rules_point_at_shapes_the_matcher_can_read(aliases):
    for r in aliases["rules"]:
        assert {"manufacturer", "model_id", "shi_id"} <= r.keys()
