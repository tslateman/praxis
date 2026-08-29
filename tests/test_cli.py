"""Tests for praxis.cli — CLI presentation layer over synthesis."""

import argparse
import json
import sys

import pytest

from praxis import cli

# --- Helper ---


def _ns(**kwargs):
    defaults = {"json": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# --- cmd_status ---


class TestCmdStatus:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_status(_ns())
        out = capsys.readouterr().out
        assert "Pulse:" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_status(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "pulse" in data
        assert "active_goals" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_status(_ns())
        out = capsys.readouterr().out
        assert "Pulse:" in out
        assert "No active goals" in out


# --- cmd_next ---


class TestCmdNext:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_next(_ns())
        out = capsys.readouterr().out
        assert "Work Queue:" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_next(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_next(_ns())
        out = capsys.readouterr().out
        assert "Nothing in the queue" in out


# --- cmd_blockers ---


class TestCmdBlockers:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_blockers(_ns())
        out = capsys.readouterr().out
        assert "Failures" in out or "No recent failures" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_blockers(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "failures" in data
        assert "stale" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_blockers(_ns())
        out = capsys.readouterr().out
        assert "No recent failures" in out


# --- cmd_health ---


class TestCmdHealth:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_health(_ns())
        out = capsys.readouterr().out
        assert "Ecosystem Health:" in out
        assert "Summary:" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_health(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "status" in data
        assert "summary" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_health(_ns())
        out = capsys.readouterr().out
        assert "Ecosystem Health:" in out


# --- cmd_verify ---


class TestCmdVerify:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_verify(_ns())
        out = capsys.readouterr().out
        assert "Verification:" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_verify(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "status" in data

    def test_unavailable_message(self, lore_dir, capsys):
        cli.cmd_verify(_ns())
        out = capsys.readouterr().out
        assert "UNAVAILABLE" in out


# --- cmd_stale ---


class TestCmdStale:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_stale(_ns(days=7))
        out = capsys.readouterr().out
        assert "Stale signals" in out or "No stale signals" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_stale(_ns(json=True, days=7))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "stale_signals" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_stale(_ns(days=7))
        out = capsys.readouterr().out
        assert "No stale signals" in out


# --- cmd_friction ---


class TestCmdFriction:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_friction(_ns())
        out = capsys.readouterr().out
        assert "boundary" in out or "No failures mapped" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_friction(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_friction(_ns())
        out = capsys.readouterr().out
        assert "No failures mapped" in out


# --- cmd_blind_spots ---


class TestCmdBlindSpots:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_blind_spots(_ns(threshold=3))
        out = capsys.readouterr().out
        assert "blind spot" in out.lower() or "No blind spots" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_blind_spots(_ns(json=True, threshold=3))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "orphaned_failures" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_blind_spots(_ns(threshold=3))
        out = capsys.readouterr().out
        assert "No blind spots" in out


# --- cmd_refinement ---


class TestCmdRefinement:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_refinement(_ns(min_cluster=3, stale_days=14))
        out = capsys.readouterr().out
        assert "Refinement" in out or "No refinement" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_refinement(_ns(json=True, min_cluster=3, stale_days=14))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "tag_clusters" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_refinement(_ns(min_cluster=3, stale_days=14))
        out = capsys.readouterr().out
        assert "No refinement" in out


# --- cmd_context ---


class TestCmdContext:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_context(
            _ns(tags=None, project=None, since_days=None, budget=2000, debug=False)
        )
        out = capsys.readouterr().out
        assert "Context:" in out
        assert "tokens" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_context(
            _ns(
                json=True,
                tags=None,
                project=None,
                since_days=None,
                budget=2000,
                debug=False,
            )
        )
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "patterns" in data
        assert "token_estimate" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_context(
            _ns(tags=None, project=None, since_days=None, budget=2000, debug=False)
        )
        out = capsys.readouterr().out
        assert "no matching items" in out


# --- cmd_overlap ---


class TestCmdOverlap:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_overlap(_ns())
        out = capsys.readouterr().out
        assert "No command name conflicts" in out or "Command Name Conflicts" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_overlap(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_overlap(_ns())
        out = capsys.readouterr().out
        assert "No command name conflicts" in out


# --- cmd_complexity ---


class TestCmdComplexity:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_complexity(_ns(max_commands=10, max_options=5))
        out = capsys.readouterr().out
        assert "No projects exceed" in out or "Complexity Warnings" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_complexity(_ns(json=True, max_commands=10, max_options=5))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_complexity(_ns(max_commands=10, max_options=5))
        out = capsys.readouterr().out
        assert "No projects exceed" in out


# --- cmd_undocumented ---


class TestCmdUndocumented:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_undocumented(_ns())
        out = capsys.readouterr().out
        assert "Undocumented:" in out or "All decisions and patterns" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_undocumented(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "decisions" in data
        assert "patterns" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_undocumented(_ns())
        out = capsys.readouterr().out
        assert "All decisions and patterns are documented" in out


# --- cmd_drift ---


class TestCmdDrift:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_drift(_ns(tags=None, project=None, since_days=None))
        out = capsys.readouterr().out
        assert "Reversals:" in out or "No decision reversals" in out

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_drift(_ns(json=True, tags=None, project=None, since_days=None))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "reversals" in data
        assert "chains" in data

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_drift(_ns(tags=None, project=None, since_days=None))
        out = capsys.readouterr().out
        assert "No decision reversals" in out


# --- cmd_correlate ---


class TestCmdCorrelate:
    def test_produces_output(self, lore_dir, capsys):
        cli.cmd_correlate(_ns(window=24))
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_json_mode(self, lore_dir, capsys):
        cli.cmd_correlate(_ns(json=True, window=24))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)

    def test_empty_data(self, empty_lore_dir, capsys):
        cli.cmd_correlate(_ns(window=24))
        out = capsys.readouterr().out
        assert "No failures recorded" in out


# --- cmd_fleet ---


class TestCmdFleet:
    def test_produces_output(self, lore_dir, missing_fleet_db, capsys):
        cli.cmd_fleet(_ns())
        out = capsys.readouterr().out
        assert "Fleet:" in out

    def test_json_mode(self, lore_dir, missing_fleet_db, capsys):
        cli.cmd_fleet(_ns(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "status" in data

    def test_unavailable_message(self, lore_dir, missing_fleet_db, capsys):
        cli.cmd_fleet(_ns())
        out = capsys.readouterr().out
        assert "UNAVAILABLE" in out


# --- main() ---


class TestMain:
    def test_no_args_exits(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["praxis"])
        with pytest.raises(SystemExit):
            cli.main()
