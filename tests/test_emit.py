"""Tests for praxis.emit — fleet dispatch payload emission."""

import re
from argparse import Namespace
from unittest.mock import patch

import yaml

import praxis.emit as emit

# ---------------------------------------------------------------------------
# emit_payload
# ---------------------------------------------------------------------------


class TestEmitPayload:
    def test_writes_valid_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        tasks = [{"name": "fix", "title": "Fix bug", "agent_type": "builder"}]
        path = emit.emit_payload("my-team", tasks)

        assert path.exists()
        content = yaml.safe_load(path.read_text())
        assert content["team"] == "my-team"
        assert content["runtime"] == "local"
        assert len(content["tasks"]) == 1
        assert content["tasks"][0]["title"] == "Fix bug"

    def test_filename_contains_timestamp_and_team(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        tasks = [{"name": "t", "title": "T", "agent_type": "builder"}]
        path = emit.emit_payload("alpha-squad", tasks)

        # Format: YYYYMMDDTHHMMSS_teamname.yaml
        assert re.match(r"\d{8}T\d{6}_alpha-squad\.yaml", path.name)

    def test_yaml_content_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        tasks = [
            {"name": "a", "title": "A", "agent_type": "builder"},
            {"name": "b", "title": "B", "agent_type": "reviewer"},
        ]
        path = emit.emit_payload("duo", tasks, runtime="remote")

        content = yaml.safe_load(path.read_text())
        assert content["team"] == "duo"
        assert content["runtime"] == "remote"
        assert len(content["tasks"]) == 2
        assert content["tasks"][1]["agent_type"] == "reviewer"

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b" / "c"
        monkeypatch.setattr(emit, "INBOX_DIR", nested)
        tasks = [{"name": "t", "title": "T", "agent_type": "builder"}]
        path = emit.emit_payload("deep", tasks)

        assert nested.exists()
        assert path.exists()

    def test_env_var_overrides_default_path(self, tmp_path, monkeypatch):
        custom = tmp_path / "custom_inbox"
        monkeypatch.setattr(emit, "INBOX_DIR", custom)
        tasks = [{"name": "t", "title": "T", "agent_type": "builder"}]
        path = emit.emit_payload("env-team", tasks)

        assert path.parent == custom
        assert path.exists()


# ---------------------------------------------------------------------------
# emit_from_triggers
# ---------------------------------------------------------------------------


class TestEmitFromTriggers:
    def test_no_triggers_above_threshold_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        triggers = [{"error_type": "ImportError", "count": 2, "projects": ["foo"]}]
        paths = emit.emit_from_triggers(triggers, threshold=5)

        assert paths == []
        assert list(tmp_path.iterdir()) == []

    def test_one_trigger_above_threshold(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        triggers = [{"error_type": "ImportError", "count": 7, "projects": ["lore"]}]
        paths = emit.emit_from_triggers(triggers, threshold=5)

        assert len(paths) == 1
        assert paths[0].exists()
        content = yaml.safe_load(paths[0].read_text())
        assert content["team"] == "fix-importerror"
        assert content["tasks"][0]["title"] == "Fix recurring ImportError in lore"
        assert content["tasks"][0]["agent_type"] == "builder"
        assert content["tasks"][0]["scope_in"] == ["lore/**"]

    def test_two_triggers_above_threshold(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        triggers = [
            {"error_type": "ImportError", "count": 6, "projects": ["lore"]},
            {"error_type": "KeyError", "count": 10, "projects": ["praxis"]},
        ]
        paths = emit.emit_from_triggers(triggers, threshold=5)

        assert len(paths) == 2
        teams = {yaml.safe_load(p.read_text())["team"] for p in paths}
        assert teams == {"fix-importerror", "fix-keyerror"}

    def test_trigger_below_threshold_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        triggers = [
            {"error_type": "ImportError", "count": 4, "projects": ["lore"]},
            {"error_type": "KeyError", "count": 10, "projects": ["praxis"]},
        ]
        paths = emit.emit_from_triggers(triggers, threshold=5)

        assert len(paths) == 1
        content = yaml.safe_load(paths[0].read_text())
        assert content["team"] == "fix-keyerror"

    def test_trigger_with_no_projects_uses_unknown(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        triggers = [{"error_type": "RuntimeError", "count": 8, "projects": []}]
        paths = emit.emit_from_triggers(triggers, threshold=5)

        assert len(paths) == 1
        content = yaml.safe_load(paths[0].read_text())
        assert content["tasks"][0]["title"] == "Fix recurring RuntimeError in unknown"
        assert content["tasks"][0]["scope_in"] == []

    def test_team_name_from_error_type(self, tmp_path, monkeypatch):
        monkeypatch.setattr(emit, "INBOX_DIR", tmp_path)
        triggers = [{"error_type": "Type Mismatch", "count": 5, "projects": ["forge"]}]
        paths = emit.emit_from_triggers(triggers, threshold=5)

        content = yaml.safe_load(paths[0].read_text())
        assert content["team"] == "fix-type-mismatch"


# ---------------------------------------------------------------------------
# CLI integration — cmd_emit
# ---------------------------------------------------------------------------


class TestCmdEmit:
    def test_from_triggers_no_triggers_prints_nothing_emitted(self, capsys):
        from praxis.cli import cmd_emit

        args = Namespace(from_triggers=True, threshold=5)
        with (
            patch("praxis.cli.synthesis") as mock_synth,
            patch("praxis.cli.emit_module") as mock_emit,
        ):
            mock_synth.triggers.return_value = []
            mock_emit.emit_from_triggers.return_value = []
            cmd_emit(args)

        out = capsys.readouterr().out
        assert "Nothing emitted" in out

    def test_team_task_agent_calls_emit_payload(self, capsys):
        from praxis.cli import cmd_emit

        args = Namespace(
            from_triggers=False,
            team="my-team",
            task=["Do Y"],
            agent_type=["builder"],
            runtime="local",
        )
        with patch("praxis.cli.emit_module") as mock_emit:
            mock_emit.emit_payload.return_value = "/fake/path.yaml"
            cmd_emit(args)

        mock_emit.emit_payload.assert_called_once()
        call_args = mock_emit.emit_payload.call_args
        assert call_args[0][0] == "my-team"
        assert len(call_args[0][1]) == 1
        assert call_args[0][1][0]["title"] == "Do Y"
        assert call_args[0][1][0]["agent_type"] == "builder"
        assert call_args[1]["runtime"] == "local"

    def test_missing_team_without_from_triggers(self, capsys):
        from praxis.cli import cmd_emit

        args = Namespace(
            from_triggers=False, team=None, task=["X"], agent_type=["builder"]
        )
        cmd_emit(args)

        out = capsys.readouterr().out
        assert "--team is required" in out

    def test_mismatched_task_agent_type_counts(self, capsys):
        from praxis.cli import cmd_emit

        args = Namespace(
            from_triggers=False,
            team="t",
            task=["A", "B"],
            agent_type=["builder"],
            runtime="local",
        )
        cmd_emit(args)

        out = capsys.readouterr().out
        assert "must be paired" in out

    def test_missing_task_prints_error(self, capsys):
        from praxis.cli import cmd_emit

        args = Namespace(
            from_triggers=False,
            team="t",
            task=None,
            agent_type=["builder"],
            runtime="local",
        )
        cmd_emit(args)

        out = capsys.readouterr().out
        assert "--task" in out or "required" in out.lower()

    def test_missing_agent_type_prints_error(self, capsys):
        from praxis.cli import cmd_emit

        args = Namespace(
            from_triggers=False,
            team="t",
            task=["A"],
            agent_type=None,
            runtime="local",
        )
        cmd_emit(args)

        out = capsys.readouterr().out
        assert "--task" in out or "required" in out.lower()
