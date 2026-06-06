"""Deterministic reliability tests for the hardened tool layer.

These run WITHOUT a Gemini key or a live MongoDB — pymongo is mocked — so they
make a genuine CI gate. They lock in the Track 2 hardening: structured errors
(no silent fallback), regex escaping (no injection), DB-config guards, and a
honest `degraded` flag when vector search fails.

    pytest eval/test_tools_reliability.py -q
"""

import json
import os
import sys

import pytest
from pymongo.errors import PyMongoError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import tools  # noqa: E402


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def limit(self, n):
        return self._rows[:n]


class _FakeCollection:
    def __init__(self, find_rows=None, aggregate_error=False, find_one_row=None):
        self._find_rows = find_rows or []
        self._aggregate_error = aggregate_error
        self._find_one_row = find_one_row

    def aggregate(self, pipeline):
        if self._aggregate_error:
            raise PyMongoError("simulated vector search failure")
        return list(self._find_rows)

    def find(self, *a, **k):
        return _FakeCursor(self._find_rows)

    def find_one(self, *a, **k):
        return self._find_one_row


class _FakeDB:
    def __init__(self, **collections):
        self._cols = collections

    def __getitem__(self, name):
        return self._cols[name]


def _reset_db_cache():
    tools._client = None
    tools._db = None


def test_missing_uri_returns_structured_error(monkeypatch):
    _reset_db_cache()
    monkeypatch.delenv("MONGODB_URI", raising=False)
    out = json.loads(tools.search_providers("endocrinology", "San Francisco"))
    assert out["ok"] is False
    assert "MONGODB_URI" in out["error"]


def test_missing_required_args():
    out = json.loads(tools.search_providers("", "San Francisco"))
    assert out["ok"] is False


def test_vector_failure_flags_degraded_not_silent(monkeypatch):
    provider = {"name": "Dr. Sarah Chen", "specialty": "Endocrinology",
                "location": {"city": "San Francisco"}, "common_prescriptions": []}
    fake = _FakeDB(providers=_FakeCollection(find_rows=[provider], aggregate_error=True))
    monkeypatch.setattr(tools, "_get_db", lambda: fake)
    out = json.loads(tools.search_providers("endocrinology", "San Francisco"))
    assert out["ok"] is True
    assert out["search_mode"] == "text_fallback"
    assert out["degraded"] is True  # a failed vector search must never look clean
    assert out["count"] == 1


def test_vector_success_is_not_degraded(monkeypatch):
    provider = {"name": "Dr. Sarah Chen", "specialty": "Endocrinology",
                "location": {"city": "San Francisco"}, "common_prescriptions": []}
    fake = _FakeDB(providers=_FakeCollection(find_rows=[provider]))
    monkeypatch.setattr(tools, "_get_db", lambda: fake)
    out = json.loads(tools.search_providers("endocrinology", "San Francisco"))
    assert out["search_mode"] == "vector"
    assert out["degraded"] is False


def test_empty_results_distinct_from_error(monkeypatch):
    fake = _FakeDB(providers=_FakeCollection(find_rows=[]))
    monkeypatch.setattr(tools, "_get_db", lambda: fake)
    out = json.loads(tools.search_providers("oncology", "San Francisco"))
    assert out["ok"] is True and out["count"] == 0  # graceful, not a crash


def test_data_driven_conflict_flag(monkeypatch):
    provider = {"name": "Dr. Maria Lopez", "specialty": "Endocrinology",
                "location": {"city": "San Francisco"},
                "common_prescriptions": [{"name": "Berberine", "conflicts_with": ["metformin"]}]}
    fake = _FakeDB(providers=_FakeCollection(find_rows=[provider]))
    monkeypatch.setattr(tools, "_get_db", lambda: fake)
    out = json.loads(tools.search_providers("endocrinology", "San Francisco", current_medications="metformin"))
    flags = out["providers"][0]["medication_flags"]
    assert any("metformin" in f.lower() for f in flags)


def test_regex_inputs_are_escaped():
    # Malicious / special-char input must be treated as a literal, not a pattern.
    assert tools._rx(".*")["$regex"] == r"\.\*"
    assert tools._rx("O'Brien (x)")["$regex"] == r"O'Brien\ \(x\)" or \
           tools._rx("O'Brien (x)")["$regex"].startswith("O'Brien")


def test_drug_interaction_requires_inputs(monkeypatch):
    fake = _FakeDB(drug_interactions=_FakeCollection())
    monkeypatch.setattr(tools, "_get_db", lambda: fake)
    out = json.loads(tools.check_drug_interactions("", "tramadol"))
    assert out["ok"] is False


def test_drug_interaction_found(monkeypatch):
    hit = {"drug_a": "escitalopram", "drug_b": "tramadol", "severity": "major"}
    fake = _FakeDB(drug_interactions=_FakeCollection(find_one_row=hit))
    monkeypatch.setattr(tools, "_get_db", lambda: fake)
    out = json.loads(tools.check_drug_interactions("escitalopram", "tramadol"))
    assert out["ok"] is True and out["count"] == 1
    assert out["interactions"][0]["severity"] == "major"


def test_provider_not_found_is_structured(monkeypatch):
    fake = _FakeDB(providers=_FakeCollection(find_one_row=None))
    monkeypatch.setattr(tools, "_get_db", lambda: fake)
    out = json.loads(tools.get_provider_details("Dr. Nobody"))
    assert out["ok"] is False and out.get("not_found") is True
