"""Scope proposals come in whatever shape the agent wrote; readers always get one shape."""

from hub.db.scope import exclusion_lines, scope_items


def test_keeps_canonical_items_as_they_are():
    items = [{"asset": "app.example.com", "type": "domain", "notes": "tier 1"}, "api.example.com"]
    assert scope_items(items) == [{"asset": "app.example.com", "type": "domain", "notes": "tier 1"}, {"asset": "api.example.com"}]


def test_folds_extra_fields_into_notes_without_losing_them():
    [item] = scope_items([{"asset": "api.example.com", "type": "url", "pays": "USD 100-10,000", "conditions": "own accounts only"}])
    assert item == {"asset": "api.example.com", "type": "url", "notes": "pays: USD 100-10,000; conditions: own accounts only"}


def test_reads_nested_lists_and_other_asset_keys():
    [item] = scope_items([{"host": "*.example.com OOS", "items": ["status", "ir"], "note": "each is <name>.example.com"}])
    assert item["asset"] == "*.example.com OOS"
    assert item["notes"] == "items: status, ir; note: each is <name>.example.com"


def test_flattens_grouped_scope():
    assert scope_items({"web": ["a.example.com"], "api": [{"asset": "api.example.com"}]}) == [
        {"asset": "a.example.com", "notes": "web"},
        {"asset": "api.example.com"},
    ]


def test_turns_grouped_exclusions_into_labelled_lines():
    grouped = {"conduct": ["No DoS", "Own accounts only"], "out_of_band": "No social engineering"}
    assert exclusion_lines(grouped) == ["conduct: No DoS", "conduct: Own accounts only", "out of band: No social engineering"]
    assert exclusion_lines(["No DoS", {"rule": "No brute force"}]) == ["No DoS", "rule: No brute force"]


def test_tolerates_empty_and_scalar_values():
    assert scope_items(None) == [] and scope_items([]) == [] and exclusion_lines(None) == []
    assert exclusion_lines("No DoS") == ["No DoS"]
    assert scope_items([{}, "", None]) == []
