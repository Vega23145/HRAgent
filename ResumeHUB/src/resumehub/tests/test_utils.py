import pytest

from resumehub.app.core.utils import build_set, clean_keys, deep_merge


def test_deep_merge_replaces_lists_merges_dicts():
    base = {"resume": {"name": "A", "skills": [1, 2]}, "x": 1}
    out = deep_merge(base, {"resume": {"skills": [3]}})
    assert out == {"resume": {"name": "A", "skills": [3]}, "x": 1}
    assert base["resume"]["skills"] == [1, 2]  # input untouched


def test_build_set_uses_dotted_paths_only_under_dict_parents():
    existing = {"contact": None, "resume": {"name": "A"}}
    patch = {"contact": {"emails": ["a@b.c"]}, "resume": {"name": "B"}}
    assert build_set(existing, patch) == {"contact": {"emails": ["a@b.c"]}, "resume.name": "B"}


def test_clean_keys_rejects_operators_and_dots():
    clean_keys({"a": {"b": [{"c": 1}]}})
    for bad in ({"$set": 1}, {"a.b": 1}, {"a": [{"$gt": 1}]}):
        with pytest.raises(ValueError):
            clean_keys(bad)
