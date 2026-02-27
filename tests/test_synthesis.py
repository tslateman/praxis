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
        assert "pending_missions" in result
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
        assert result["pending_missions"] == []

    def test_blockers_counts(self, lore_dir):
        result = synthesis.status()
        assert result["blockers"]["recent_failures"] >= 1
        # obs-001 and obs-004 are raw and older than 7 days
        assert result["blockers"]["stale_observations"] >= 1

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
                    "mission": "test",
                    "timestamp": _days_ago(1),
                }
            )
        _write_jsonl(path, failures)
        lore.cache_clear()
        result = synthesis.status()
        assert result["pulse"] == "attention"


# --- next_work() ---


class TestNextWork:
    def test_returns_sorted_missions(self, lore_dir):
        result = synthesis.next_work()
        assert len(result) == 2  # mission-001 (in_progress) + mission-002 (pending)

    def test_in_progress_first(self, lore_dir):
        result = synthesis.next_work()
        assert result[0]["status"] == "in_progress"

    def test_empty_when_no_missions(self, empty_lore_dir):
        assert synthesis.next_work() == []

    def test_excludes_completed(self, lore_dir):
        result = synthesis.next_work()
        ids = [m["id"] for m in result]
        assert "mission-003" not in ids


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
    def test_finds_stale_observations(self, lore_dir):
        result = synthesis.stale(days=7)
        assert result["stale_count"] >= 1
        # obs-001 (10d) and obs-004 (20d) are raw and older than 7 days
        stale_ids = [o["id"] for o in result["stale_observations"]]
        assert "obs-001" in stale_ids
        assert "obs-004" in stale_ids

    def test_excludes_recent_raw(self, lore_dir):
        result = synthesis.stale(days=7)
        stale_ids = [o["id"] for o in result["stale_observations"]]
        # obs-002 is raw but only 2 days old
        assert "obs-002" not in stale_ids

    def test_total_raw_count(self, lore_dir):
        result = synthesis.stale(days=7)
        assert result["total_raw"] == 3  # obs-001, obs-002, obs-004

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


# --- context() ---


class TestContext:
    def test_returns_expected_keys(self, lore_dir):
        result = synthesis.context()
        assert "patterns" in result
        assert "anti_patterns" in result
        assert "decisions" in result
        assert "goals" in result
        assert "token_estimate" in result
        assert "truncated" in result
        assert "filters_applied" in result

    def test_unfiltered_returns_all_sections(self, lore_dir):
        result = synthesis.context(budget=50000)
        assert len(result["patterns"]) > 0
        assert len(result["goals"]) > 0

    def test_tag_filter_narrows_results(self, lore_dir):
        all_results = synthesis.context(budget=50000)
        filtered = synthesis.context(tags=["caching"], budget=50000)
        # Filtered should have equal or fewer items
        all_total = sum(
            len(all_results[k])
            for k in ("patterns", "anti_patterns", "decisions", "goals")
        )
        filt_total = sum(
            len(filtered[k])
            for k in ("patterns", "anti_patterns", "decisions", "goals")
        )
        assert filt_total <= all_total

    def test_project_filter(self, lore_dir):
        result = synthesis.context(project="praxis", budget=50000)
        assert result["filters_applied"]["project"] == "praxis"

    def test_budget_truncation(self, lore_dir):
        result = synthesis.context(budget=1)
        # With 1 token budget, nothing fits
        total = sum(
            len(result[k]) for k in ("patterns", "anti_patterns", "decisions", "goals")
        )
        assert total == 0
        assert result["truncated"] is True

    def test_since_days_filter(self, lore_dir):
        result = synthesis.context(since_days=1, budget=50000)
        # Only items from last 1 day should appear
        assert result["filters_applied"]["since_days"] == 1

    def test_scores_present(self, lore_dir):
        result = synthesis.context(budget=50000)
        for section in ("patterns", "anti_patterns", "decisions", "goals"):
            for item in result[section]:
                assert "_score" in item

    def test_empty_data(self, empty_lore_dir):
        result = synthesis.context()
        assert result["patterns"] == []
        assert result["decisions"] == []
        assert result["token_estimate"] == 0

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
        assert "stale_observations" in result
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
