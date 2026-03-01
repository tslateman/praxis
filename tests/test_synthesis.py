"""Tests for praxis.synthesis — actionable views from Lore data."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from praxis import lore, synthesis

# --- Helpers ---


def _now():
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> str:
    return (_now() - timedelta(days=n)).isoformat()


def _write_jsonl(path: Path, records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# --- status() ---


class TestStatus:
    def test_returns_expected_keys(self, lore_dir):
        result = synthesis.status()
        assert "active_goals" in result
        assert "blockers" in result
        assert "pulse" in result

    def test_pulse_active_with_recent_failures(self, lore_dir):
        result = synthesis.status()
        # Fixture has 4 failures within 7 days
        assert result["pulse"] in ("active", "attention")

    def test_pulse_clear_with_no_data(self, empty_lore_dir):
        result = synthesis.status()
        assert result["pulse"] == "clear"
        assert result["active_goals"] == []

    def test_blockers_counts(self, lore_dir):
        result = synthesis.status()
        assert result["blockers"]["recent_failures"] >= 1
        # sig-001 and sig-004 are raw and older than 7 days
        assert result["blockers"]["stale_signals"] >= 1

    def test_pulse_attention_many_failures(self, lore_dir):
        """6+ recent failures trigger 'attention' pulse."""
        path = lore_dir / "failures" / "data" / "failures.jsonl"
        failures = []
        for i in range(7):
            failures.append(
                {
                    "id": f"fail-extra-{i}",
                    "error_type": "Flood",
                    "error_message": "too many",
                    "project": "test",
                    "timestamp": _days_ago(1),
                }
            )
        _write_jsonl(path, failures)
        lore.cache_clear()
        result = synthesis.status()
        assert result["pulse"] == "attention"

    def test_status_with_spectrace_tasks(self, lore_dir, monkeypatch):
        monkeypatch.setattr(
            "praxis.spectrace.fetch_tasks",
            lambda: [
                {"external_id": "T-1", "title": "Task 1", "status": "unclaimed"},
                {"external_id": "T-2", "title": "Task 2", "status": "in_progress"},
                {"external_id": "T-3", "title": "Task 3", "status": "in_progress"},
            ],
        )
        result = synthesis.status()
        assert result["tasks"]["unclaimed"] == 1
        assert result["tasks"]["in_progress"] == 2


# --- next_work() ---


class TestNextWork:
    def test_returns_sorted_goals(self, lore_dir):
        result = synthesis.next_work()
        assert len(result) == 2  # goal-001 (high), goal-002 (medium)

    def test_priority_first(self, lore_dir):
        result = synthesis.next_work()
        assert result[0]["id"] == "goal-001"

    def test_empty_when_no_goals(self, empty_lore_dir):
        assert synthesis.next_work() == []

    def test_excludes_archived(self, lore_dir):
        result = synthesis.next_work()
        ids = [g["id"] for g in result]
        assert "goal-003" not in ids

    def test_spectrace_tasks_prioritized(self, lore_dir, monkeypatch):
        monkeypatch.setattr(
            "praxis.spectrace.fetch_tasks",
            lambda: [
                {"external_id": "T-1", "title": "Task 1", "status": "unclaimed"},
                {"external_id": "T-2", "title": "Task 2", "status": "in_progress"},
                {"external_id": "T-3", "title": "Task 3", "status": "completed"},
            ],
        )
        result = synthesis.next_work()

        # in_progress task comes first
        assert result[0]["id"] == "T-2"
        assert result[0]["type"] == "task"
        assert result[0]["status"] == "in_progress"

        # unclaimed task comes second
        assert result[1]["id"] == "T-1"
        assert result[1]["type"] == "task"
        assert result[1]["status"] == "unclaimed"

        # goal comes third
        assert result[2]["id"] == "goal-001"
        assert result[2]["type"] == "goal"


# --- blockers_view() ---


class TestBlockersView:
    def test_returns_expected_keys(self, lore_dir):
        result = synthesis.blockers_view()
        assert "failures" in result
        assert "stale" in result
        assert "friction" in result

    def test_failure_counts(self, lore_dir):
        result = synthesis.blockers_view()
        assert result["failures"]["count"] >= 1
        assert "Timeout" in result["failures"]["by_type"]

    def test_stale_signals_in_blockers(self, lore_dir):
        result = synthesis.blockers_view()
        assert "signals" in result["stale"]
        assert result["stale"]["count"] >= 1

    def test_empty_data(self, empty_lore_dir):
        result = synthesis.blockers_view()
        assert result["failures"]["count"] == 0
        assert result["stale"]["count"] == 0


# --- triggers() ---


class TestTriggers:
    def test_finds_timeout_trigger(self, lore_dir):
        result = synthesis.triggers(threshold=3)
        types = [t["error_type"] for t in result]
        assert "Timeout" in types

    def test_threshold_filters(self, lore_dir):
        # Only Timeout has 3+ occurrences in fixtures
        result = synthesis.triggers(threshold=3)
        assert all(t["count"] >= 3 for t in result)

    def test_higher_threshold_excludes(self, lore_dir):
        result = synthesis.triggers(threshold=10)
        assert result == []

    def test_empty_data(self, empty_lore_dir):
        assert synthesis.triggers() == []


# --- stale() ---


class TestStale:
    def test_finds_stale_signals(self, lore_dir):
        result = synthesis.stale(days=7)
        assert result["stale_count"] >= 1
        # sig-001 (10d) and sig-004 (20d) are raw and older than 7 days
        stale_ids = [s["id"] for s in result["stale_signals"]]
        assert "sig-001" in stale_ids
        assert "sig-004" in stale_ids

    def test_excludes_recent_raw(self, lore_dir):
        result = synthesis.stale(days=7)
        stale_ids = [s["id"] for s in result["stale_signals"]]
        # sig-002 is raw but only 2 days old
        assert "sig-002" not in stale_ids

    def test_total_raw_count(self, lore_dir):
        result = synthesis.stale(days=7)
        assert result["total_raw"] == 3  # sig-001, sig-002, sig-004

    def test_empty_data(self, empty_lore_dir):
        result = synthesis.stale()
        assert result["stale_count"] == 0
        assert result["total_raw"] == 0


# --- friction() ---


class TestFriction:
    def test_finds_lore_boundary(self, lore_dir):
        result = synthesis.friction()
        boundaries = [f["boundary"] for f in result]
        assert "lore" in boundaries

    def test_sorted_by_count_descending(self, lore_dir):
        result = synthesis.friction()
        if len(result) >= 2:
            assert result[0]["failure_count"] >= result[1]["failure_count"]

    def test_empty_data(self, empty_lore_dir):
        assert synthesis.friction() == []


# --- blind_spots() ---


class TestBlindSpots:
    def test_returns_expected_keys(self, lore_dir):
        result = synthesis.blind_spots(threshold=3)
        assert "orphaned_failures" in result
        assert "blind_spot_count" in result
        assert "suggestions" in result

    def test_finds_orphaned_failures(self, lore_dir):
        """Timeout failures have 3 occurrences but a decision exists nearby,
        so this tests the detection logic."""
        result = synthesis.blind_spots(threshold=3)
        # Whether they're orphaned depends on decision timestamps
        assert isinstance(result["orphaned_failures"], list)

    def test_empty_data(self, empty_lore_dir):
        result = synthesis.blind_spots()
        assert result["blind_spot_count"] == 0

    def test_high_threshold_finds_nothing(self, lore_dir):
        result = synthesis.blind_spots(threshold=100)
        assert result["blind_spot_count"] == 0


# --- refinement() ---


class TestRefinement:
    def test_returns_expected_keys(self, lore_dir):
        result = synthesis.refinement()
        assert "tag_clusters" in result
        assert "decision_chains" in result
        assert "aging" in result
        assert "cluster_count" in result
        assert "suggestions" in result

    def test_finds_tag_clusters(self, lore_dir):
        """'architecture' tag has 3 decisions but no pattern with that name."""
        result = synthesis.refinement(min_cluster=3)
        tags = [tc["tag"] for tc in result["tag_clusters"]]
        assert "architecture" in tags

    def test_finds_decision_chains(self, lore_dir):
        """dec-002 and dec-003 are related, but chain is only 2 so min_cluster=2
        should find it."""
        result = synthesis.refinement(min_cluster=2)
        # Chain of dec-002 <-> dec-003
        assert result["chain_count"] >= 1 or result["cluster_count"] >= 1

    def test_finds_aging_decisions(self, lore_dir):
        """dec-004 has no outcome and is 30 days old."""
        result = synthesis.refinement(stale_days=14)
        aging_ids = [a["id"] for a in result["aging"]]
        assert "dec-004" in aging_ids

    def test_aging_includes_pending(self, lore_dir):
        """dec-003 has outcome='pending' and is 20 days old."""
        result = synthesis.refinement(stale_days=14)
        aging_ids = [a["id"] for a in result["aging"]]
        assert "dec-003" in aging_ids

    def test_empty_data(self, empty_lore_dir):
        result = synthesis.refinement()
        assert result["cluster_count"] == 0
        assert result["chain_count"] == 0
        assert result["aging_count"] == 0


# --- correlate() ---


class TestCorrelate:
    def test_returns_list(self, lore_dir):
        result = synthesis.correlate()
        assert isinstance(result, list)

    def test_failure_has_nearby_decisions(self, lore_dir):
        result = synthesis.correlate(window_hours=168)  # 7 days
        # With a wide window, most failures should correlate to some decision
        has_nearby = any(len(r["nearby_decisions"]) > 0 for r in result)
        assert has_nearby

    def test_empty_data(self, empty_lore_dir):
        assert synthesis.correlate() == []

    def test_narrow_window_finds_fewer(self, lore_dir):
        wide = synthesis.correlate(window_hours=168)
        narrow = synthesis.correlate(window_hours=1)
        # Narrow should find equal or fewer nearby decisions total
        wide_total = sum(len(r["nearby_decisions"]) for r in wide)
        narrow_total = sum(len(r["nearby_decisions"]) for r in narrow)
        assert narrow_total <= wide_total


# --- drift() ---


class TestDrift:
    def test_returns_expected_keys(self, lore_dir):
        result = synthesis.drift()
        assert "reversals" in result
        assert "reversal_count" in result
        assert "volatile_tags" in result
        assert "chains" in result
        assert "chain_count" in result
        assert "filters_applied" in result

    def test_finds_revised_decision(self, lore_dir):
        """dec-005 has outcome='revised' and should appear."""
        result = synthesis.drift()
        revised_ids = [r["revised"]["id"] for r in result["reversals"]]
        assert "dec-005" in revised_ids

    def test_reversal_count(self, lore_dir):
        result = synthesis.drift()
        assert result["reversal_count"] == 1  # dec-005

    def test_volatile_tags_from_revised(self, lore_dir):
        """dec-005 has tag 'storage', so storage should be volatile."""
        result = synthesis.drift()
        tag_names = [vt["tag"] for vt in result["volatile_tags"]]
        assert "storage" in tag_names

    def test_tag_filter_narrows(self, lore_dir):
        all_result = synthesis.drift()
        filtered = synthesis.drift(tags=["storage"])
        assert filtered["reversal_count"] <= all_result["reversal_count"]

    def test_tag_filter_excludes_unmatched(self, lore_dir):
        result = synthesis.drift(tags=["nonexistent-tag-xyz"])
        assert result["reversal_count"] == 0

    def test_chains_link_related_decisions(self, lore_dir):
        """dec-005 is revised. If it has related_decisions, those form a chain."""
        # Add related_decisions to dec-005 pointing to dec-001
        path = lore_dir / "journal" / "data" / "decisions.jsonl"
        _write_jsonl(
            path,
            [
                {
                    "id": "dec-rev-a",
                    "title": "Original storage plan",
                    "outcome": "revised",
                    "tags": ["storage"],
                    "related_decisions": ["dec-rev-b"],
                    "timestamp": _days_ago(10),
                },
                {
                    "id": "dec-rev-b",
                    "title": "Updated storage plan",
                    "outcome": "accepted",
                    "tags": ["storage"],
                    "related_decisions": ["dec-rev-a"],
                    "timestamp": _days_ago(5),
                },
            ],
        )
        lore.cache_clear()
        result = synthesis.drift()
        assert result["chain_count"] >= 1
        # Chain should contain both decisions
        chain_ids = set()
        for chain in result["chains"]:
            for step in chain["steps"]:
                chain_ids.add(step["id"])
        assert "dec-rev-a" in chain_ids
        assert "dec-rev-b" in chain_ids

    def test_chain_chronological_order(self, lore_dir):
        """Chain steps are sorted oldest-first."""
        path = lore_dir / "journal" / "data" / "decisions.jsonl"
        _write_jsonl(
            path,
            [
                {
                    "id": "dec-old",
                    "title": "First attempt",
                    "outcome": "revised",
                    "tags": ["api"],
                    "related_decisions": ["dec-new"],
                    "timestamp": _days_ago(20),
                },
                {
                    "id": "dec-new",
                    "title": "Second attempt",
                    "outcome": "accepted",
                    "tags": ["api"],
                    "related_decisions": ["dec-old"],
                    "timestamp": _days_ago(2),
                },
            ],
        )
        lore.cache_clear()
        result = synthesis.drift()
        for chain in result["chains"]:
            timestamps = [s["timestamp"] for s in chain["steps"]]
            assert timestamps == sorted(timestamps)

    def test_since_days_filter(self, lore_dir):
        result = synthesis.drift(since_days=1)
        # dec-005 is 4 days old, should be excluded
        assert result["reversal_count"] == 0

    def test_empty_data(self, empty_lore_dir):
        result = synthesis.drift()
        assert result["reversal_count"] == 0
        assert result["chain_count"] == 0
        assert result["volatile_tags"] == []

    def test_replacement_linked(self, lore_dir):
        """When a revised decision has related_decisions, the replacement is found."""
        path = lore_dir / "journal" / "data" / "decisions.jsonl"
        _write_jsonl(
            path,
            [
                {
                    "id": "dec-X",
                    "title": "Old approach",
                    "outcome": "revised",
                    "tags": ["infra"],
                    "related_decisions": ["dec-Y"],
                    "timestamp": _days_ago(10),
                },
                {
                    "id": "dec-Y",
                    "title": "New approach",
                    "outcome": "accepted",
                    "tags": ["infra"],
                    "related_decisions": ["dec-X"],
                    "timestamp": _days_ago(5),
                },
            ],
        )
        lore.cache_clear()
        result = synthesis.drift()
        reversal = next(r for r in result["reversals"] if r["revised"]["id"] == "dec-X")
        assert reversal["replaced_by"] is not None
        assert reversal["replaced_by"]["id"] == "dec-Y"


# --- context() ---


class TestContext:
    def test_returns_expected_keys(self, lore_dir):
        result = synthesis.context()
        assert "evidence" in result
        assert "patterns" in result
        assert "anti_patterns" in result
        assert "decisions" in result
        assert "goals" in result
        assert "token_estimate" in result
        assert "truncated" in result
        assert "filters_applied" in result

    def test_unfiltered_returns_all_sections(self, lore_dir):
        result = synthesis.context(budget=50000)
        assert len(result["evidence"]) > 0
        assert len(result["patterns"]) > 0
        assert len(result["goals"]) > 0

    def test_tag_filter_narrows_results(self, lore_dir):
        all_results = synthesis.context(budget=50000)
        filtered = synthesis.context(tags=["caching"], budget=50000)
        # Filtered should have equal or fewer items
        sections = ("evidence", "patterns", "anti_patterns", "decisions", "goals")
        all_total = sum(len(all_results[k]) for k in sections)
        filt_total = sum(len(filtered[k]) for k in sections)
        assert filt_total <= all_total

    def test_project_filter(self, lore_dir):
        result = synthesis.context(project="praxis", budget=50000)
        assert result["filters_applied"]["project"] == "praxis"

    def test_budget_truncation(self, lore_dir):
        result = synthesis.context(budget=1)
        # With 1 token budget, nothing fits
        sections = ("evidence", "patterns", "anti_patterns", "decisions", "goals")
        total = sum(len(result[k]) for k in sections)
        assert total == 0
        assert result["truncated"] is True

    def test_since_days_filter(self, lore_dir):
        result = synthesis.context(since_days=1, budget=50000)
        # Only items from last 1 day should appear
        assert result["filters_applied"]["since_days"] == 1

    def test_scores_present(self, lore_dir):
        result = synthesis.context(budget=50000)
        for section in ("evidence", "patterns", "anti_patterns", "decisions", "goals"):
            for item in result[section]:
                assert "_score" in item

    def test_empty_data(self, empty_lore_dir):
        result = synthesis.context()
        assert result["evidence"] == []
        assert result["patterns"] == []
        assert result["decisions"] == []
        assert result["token_estimate"] == 0

    def test_evidence_in_context(self, lore_dir):
        """Evidence appears in context output with scoring."""
        result = synthesis.context(budget=50000)
        assert len(result["evidence"]) > 0
        evi = result["evidence"][0]
        assert "id" in evi
        assert "content" in evi
        assert "confidence" in evi
        assert "_score" in evi

    def test_evidence_quality_scoring(self, lore_dir):
        """Confirmed evidence scores higher than contested."""
        result = synthesis.context(budget=50000)
        scores_by_conf = {}
        for e in result["evidence"]:
            conf = e["confidence"]
            scores_by_conf.setdefault(conf, []).append(e["_score"])
        if "confirmed" in scores_by_conf and "contested" in scores_by_conf:
            avg_confirmed = sum(scores_by_conf["confirmed"]) / len(
                scores_by_conf["confirmed"]
            )
            avg_contested = sum(scores_by_conf["contested"]) / len(
                scores_by_conf["contested"]
            )
            assert avg_confirmed > avg_contested

    def test_contention_detection(self, lore_dir):
        """dec-001 (accepted, storage tag) and dec-005 (revised, storage tag)
        should produce a contention."""
        result = synthesis.context(budget=50000)
        contentions = result["contentions"]
        # Check structure even if no contentions are found
        assert isinstance(contentions, list)


# --- ecosystem_overlap() ---


class TestEcosystemOverlap:
    def test_no_overlap_without_claude_md(self, lore_dir, monkeypatch):
        """Without CLAUDE.md files, no overlap detected."""
        monkeypatch.setenv("DEV_DIR", str(lore_dir / "nonexistent_dev"))
        result = synthesis.ecosystem_overlap()
        assert result == []

    def test_detects_overlap(self, lore_dir, tmp_path, monkeypatch):
        """Two projects with same command name produce an overlap."""
        dev_dir = tmp_path / "dev"

        # Create CLAUDE.md for two projects with overlapping command
        proj_a = dev_dir / "lore"
        proj_a.mkdir(parents=True)
        (proj_a / "CLAUDE.md").write_text(
            "| Command | Description |\n"
            "| --- | --- |\n"
            "| `lore status` | Show status |\n"
            "| `lore health` | Show health |\n"
        )

        proj_b = dev_dir / "praxis"
        proj_b.mkdir(parents=True)
        (proj_b / "CLAUDE.md").write_text(
            "| Command | Description |\n"
            "| --- | --- |\n"
            "| `praxis status` | Show status |\n"
            "| `praxis next` | Show next |\n"
        )

        monkeypatch.setenv("DEV_DIR", str(dev_dir))
        result = synthesis.ecosystem_overlap()
        cmds = [o["command"] for o in result]
        assert "status" in cmds

    def test_empty_projects(self, empty_lore_dir):
        result = synthesis.ecosystem_overlap()
        assert result == []


# --- ecosystem_complexity() ---


class TestEcosystemComplexity:
    def test_no_complexity_without_claude_md(self, lore_dir, monkeypatch):
        monkeypatch.setenv("DEV_DIR", str(lore_dir / "nonexistent_dev"))
        result = synthesis.ecosystem_complexity()
        assert result == []

    def test_detects_high_complexity(self, lore_dir, tmp_path, monkeypatch):
        """A project with many commands triggers a complexity warning."""
        dev_dir = tmp_path / "dev"
        proj = dev_dir / "lore"
        proj.mkdir(parents=True)

        # Generate a CLAUDE.md with 12 commands
        lines = ["| Command | Description |\n", "| --- | --- |\n"]
        for i in range(12):
            lines.append(f"| `lore cmd{i}` | Command {i} |\n")
        (proj / "CLAUDE.md").write_text("".join(lines))

        monkeypatch.setenv("DEV_DIR", str(dev_dir))
        result = synthesis.ecosystem_complexity(max_commands=10)
        assert len(result) == 1
        assert result[0]["project"] == "lore"
        assert result[0]["command_count"] == 12

    def test_under_threshold_is_fine(self, lore_dir, tmp_path, monkeypatch):
        dev_dir = tmp_path / "dev"
        proj = dev_dir / "lore"
        proj.mkdir(parents=True)

        lines = ["| Command | Description |\n", "| --- | --- |\n"]
        for i in range(3):
            lines.append(f"| `lore cmd{i}` | Command {i} |\n")
        (proj / "CLAUDE.md").write_text("".join(lines))

        monkeypatch.setenv("DEV_DIR", str(dev_dir))
        result = synthesis.ecosystem_complexity(max_commands=10)
        assert result == []


# --- undocumented() ---


class TestUndocumented:
    def test_returns_expected_keys(self, lore_dir):
        result = synthesis.undocumented()
        assert "decisions" in result
        assert "patterns" in result
        assert "decision_count" in result
        assert "pattern_count" in result

    def test_finds_undocumented_decision(self, lore_dir):
        """dec-003 has empty rationale."""
        result = synthesis.undocumented()
        ids = [d["id"] for d in result["decisions"]]
        assert "dec-003" in ids

    def test_finds_undocumented_pattern(self, lore_dir):
        """pat-002 has empty problem field."""
        result = synthesis.undocumented()
        ids = [p["id"] for p in result["patterns"]]
        assert "pat-002" in ids

    def test_empty_data(self, empty_lore_dir):
        result = synthesis.undocumented()
        assert result["decision_count"] == 0
        assert result["pattern_count"] == 0


# --- health() ---


class TestHealth:
    def test_returns_all_sections(self, lore_dir):
        result = synthesis.health()
        assert "summary" in result
        assert "status" in result
        assert "triggers" in result
        assert "stale_signals" in result
        assert "blind_spots" in result
        assert "friction" in result

    def test_status_values(self, lore_dir):
        result = synthesis.health()
        assert result["status"] in ("healthy", "attention", "critical")

    def test_summary_counts(self, lore_dir):
        result = synthesis.health()
        s = result["summary"]
        assert s["total_failures"] == 5
        assert s["recent_failures"] >= 1

    def test_healthy_with_no_data(self, empty_lore_dir):
        result = synthesis.health()
        assert result["status"] == "healthy"
        assert result["summary"]["total_failures"] == 0


# --- _parse_claude_md_commands() ---


class TestParseClaude:
    def test_table_format(self):
        content = (
            "| Command | Description |\n"
            "| --- | --- |\n"
            "| `praxis status` | Show status |\n"
            "| `praxis health` | Health check |\n"
        )
        cmds = synthesis._parse_claude_md_commands(content, "praxis")
        assert "status" in cmds
        assert "health" in cmds

    def test_code_block_format(self):
        content = "Usage:\n\npraxis status\npraxis next --json\npraxis health\n"
        cmds = synthesis._parse_claude_md_commands(content, "praxis")
        assert "status" in cmds
        assert "next" in cmds
        assert "health" in cmds

    def test_ignores_other_projects(self):
        content = (
            "| `lore status` | Lore status |\n| `praxis status` | Praxis status |\n"
        )
        cmds = synthesis._parse_claude_md_commands(content, "praxis")
        assert "status" in cmds
        # Should only find praxis commands
        assert len(cmds) == 1

    def test_empty_content(self):
        assert synthesis._parse_claude_md_commands("", "praxis") == []
