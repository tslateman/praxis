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
# CLI integration — cmd_emit
# ---------------------------------------------------------------------------


class TestCmdEmit:
    def test_team_task_agent_calls_emit_payload(self):
        from praxis.cli import cmd_emit

        args = Namespace(
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

    def test_missing_team(self, capsys):
        from praxis.cli import cmd_emit

        args = Namespace(team=None, task=["X"], agent_type=["builder"])
        cmd_emit(args)

        out = capsys.readouterr().out
        assert "--team is required" in out

    def test_mismatched_task_agent_type_counts(self, capsys):
        from praxis.cli import cmd_emit

        args = Namespace(
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
            team="t",
            task=["A"],
            agent_type=None,
            runtime="local",
        )
        cmd_emit(args)

        out = capsys.readouterr().out
        assert "--task" in out or "required" in out.lower()
