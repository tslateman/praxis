"""Tests for praxis.lore — Lore data readers and TTL cache."""

import json

import yaml

from praxis import lore

# --- Failures ---


class TestFailures:
    def test_reads_all_failures(self, lore_dir):
        result = lore.failures()
        assert len(result) == 5
        assert all("error_type" in f for f in result)

    def test_missing_file_returns_empty(self, empty_lore_dir):
        assert lore.failures() == []

    def test_failure_fields(self, lore_dir):
        result = lore.failures()
        first = result[0]
        assert first["id"] == "fail-001"
        assert first["error_type"] == "Timeout"


# --- Evidence ---


class TestEvidence:
    def test_reads_all_evidence(self, lore_dir):
        result = lore.evidence()
        assert len(result) == 4
        assert all("confidence" in e for e in result)

    def test_missing_file_returns_empty(self, empty_lore_dir):
        assert lore.evidence() == []

    def test_preliminary_evidence(self, lore_dir):
        result = lore.preliminary_evidence()
        assert len(result) == 1
        assert result[0]["id"] == "evi-002"

    def test_confirmed_evidence(self, lore_dir):
        result = lore.confirmed_evidence()
        assert len(result) == 2
        ids = [e["id"] for e in result]
        assert "evi-001" in ids
        assert "evi-003" in ids

    def test_evidence_fields(self, lore_dir):
        result = lore.evidence()
        first = next(e for e in result if e["id"] == "evi-001")
        assert first["source"] == "praxis"
        assert first["confidence"] == "confirmed"
        assert first["provenance"] == "Benchmarked in test suite"


# --- Signals ---


class TestSignals:
    def test_reads_all_signals(self, lore_dir):
        result = lore.signals()
        assert len(result) == 4

    def test_missing_file_returns_empty(self, empty_lore_dir):
        assert lore.signals() == []

    def test_raw_signals_filters_by_status(self, lore_dir):
        raw = lore.raw_signals()
        assert len(raw) == 3
        assert all(s["status"] == "raw" for s in raw)

    def test_raw_signals_excludes_processed(self, lore_dir):
        raw = lore.raw_signals()
        ids = [s["id"] for s in raw]
        assert "sig-003" not in ids  # processed


# --- Backward Compatibility Aliases ---


class TestBackwardCompat:
    def test_observations_alias(self, lore_dir):
        assert lore.observations() == lore.signals()

    def test_raw_observations_alias(self, lore_dir):
        assert lore.raw_observations() == lore.raw_signals()


# --- Decisions ---


class TestDecisions:
    def test_reads_all_decisions(self, lore_dir):
        result = lore.decisions()
        assert len(result) == 5

    def test_missing_file_returns_empty(self, empty_lore_dir):
        assert lore.decisions() == []

    def test_decision_fields(self, lore_dir):
        result = lore.decisions()
        dec = next(d for d in result if d["id"] == "dec-001")
        assert dec["outcome"] == "accepted"
        assert "storage" in dec["tags"]


# --- Goals ---


class TestGoals:
    def test_reads_all_goals(self, lore_dir):
        result = lore.goals()
        assert len(result) == 3

    def test_missing_dir_returns_empty(self, empty_lore_dir):
        assert lore.goals() == []

    def test_active_goals_filters(self, lore_dir):
        active = lore.active_goals()
        assert len(active) == 2
        assert all(g["status"] == "active" for g in active)

    def test_active_goals_excludes_archived(self, lore_dir):
        active = lore.active_goals()
        ids = [g["id"] for g in active]
        assert "goal-003" not in ids


# --- Registry ---


class TestRegistry:
    def test_reads_registry(self, lore_dir):
        reg = lore.registry()
        assert "dependencies" in reg
        assert "lore" in reg["dependencies"]

    def test_missing_file_returns_empty_dict(self, empty_lore_dir):
        assert lore.registry() == {}

    def test_projects_from_registry(self, lore_dir):
        proj = lore.projects()
        assert proj == ["bach", "council", "lore", "praxis"]

    def test_projects_empty_when_no_registry(self, empty_lore_dir):
        assert lore.projects() == []


# --- Patterns ---


class TestPatterns:
    def test_reads_patterns(self, lore_dir):
        pats = lore.patterns()
        assert len(pats) == 2
        assert pats[0]["id"] == "pat-001"

    def test_missing_file_returns_empty(self, empty_lore_dir):
        assert lore.patterns() == []

    def test_anti_patterns(self, lore_dir):
        anti = lore.anti_patterns()
        assert len(anti) == 2
        assert anti[0]["id"] == "anti-001"

    def test_anti_patterns_missing_returns_empty(self, empty_lore_dir):
        assert lore.anti_patterns() == []


# --- JSONL edge cases ---


class TestJsonlEdgeCases:
    def test_empty_lines_ignored(self, lore_dir):
        """Blank lines in JSONL should be skipped."""
        path = lore_dir / "failures" / "data" / "failures.jsonl"
        content = path.read_text()
        path.write_text("\n\n" + content + "\n\n")
        lore.cache_clear()
        result = lore.failures()
        assert len(result) == 5

    def test_malformed_jsonl_raises(self, lore_dir):
        """A line that isn't valid JSON should raise."""
        path = lore_dir / "failures" / "data" / "failures.jsonl"
        path.write_text('{"valid": true}\nnot json\n')
        lore.cache_clear()
        with __import__("pytest").raises(json.JSONDecodeError):
            lore.failures()


# --- YAML edge cases ---


class TestYamlEdgeCases:
    def test_empty_yaml_returns_none(self, lore_dir):
        """An empty YAML file returns None from _read_yaml."""
        path = lore_dir / "registry" / "data" / "relationships.yaml"
        path.write_text("")
        lore.cache_clear()
        # registry() wraps None -> {}
        assert lore.registry() == {}

    def test_patterns_yaml_missing_keys(self, lore_dir):
        """patterns.yaml without 'patterns' key returns empty list."""
        path = lore_dir / "patterns" / "data" / "patterns.yaml"
        path.write_text(yaml.dump({"something_else": []}))
        lore.cache_clear()
        assert lore.patterns() == []
        assert lore.anti_patterns() == []


# --- TTL Cache ---


class TestCache:
    def test_cache_returns_same_object(self, lore_dir):
        """Consecutive calls within TTL return cached result."""
        a = lore.failures()
        b = lore.failures()
        assert a is b

    def test_cache_clear_forces_reread(self, lore_dir):
        a = lore.failures()
        lore.cache_clear()
        b = lore.failures()
        # After clear, should still equal but be a new list object
        assert a == b
        assert a is not b

    def test_cache_expires_after_ttl(self, lore_dir, monkeypatch):
        """After TTL expires, cache returns fresh data."""
        import praxis.lore as lore_mod

        # Use a very short TTL for testing
        original_store = lore_mod._cache_store

        lore.cache_clear()
        a = lore.failures()

        # Manually expire the cache entries by backdating timestamps
        with lore_mod._cache_lock:
            for key in list(original_store.keys()):
                ts, val = original_store[key]
                # Set timestamp to 60 seconds in the past (well beyond 30s TTL)
                original_store[key] = (ts - 60, val)

        b = lore.failures()
        assert a == b
        assert a is not b  # Fresh read after expiry
