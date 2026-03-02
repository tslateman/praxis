"""Tests for impact graph reader."""

import json
from unittest.mock import patch

import pytest
import yaml

from praxis import impact


@pytest.fixture()
def project_roots(tmp_path):
    """Create project roots with map and contract files."""
    lore_root = tmp_path / "lore"
    lore_root.mkdir()
    praxis_root = tmp_path / "praxis"
    praxis_root.mkdir()

    # spectrace-map.yaml for lore
    map_data = {
        "project": "lore",
        "modules": {
            "src/lore/reader.py": {"requirements": ["REQ-LORE-001"]},
            "src/lore/writer.py": {"requirements": ["REQ-LORE-002"]},
        },
    }
    with open(lore_root / "spectrace-map.yaml", "w") as f:
        yaml.dump(map_data, f)

    # contract.snapshot.json for lore
    contract = {
        "project": "lore",
        "version": "1.0",
        "surfaces": {
            "journal/decisions": {
                "format": "jsonl",
                "fields": ["id", "timestamp", "decision"],
            },
        },
    }
    with open(lore_root / "contract.snapshot.json", "w") as f:
        json.dump(contract, f)

    return {"lore": lore_root, "praxis": praxis_root}


class TestReadSpectraceMap:
    def test_reads_valid_map(self, project_roots):
        mappings = impact.read_spectrace_map("lore", project_roots)
        assert len(mappings) == 2
        assert any(m["requirement"] == "REQ-LORE-001" for m in mappings)

    def test_missing_file_returns_empty(self, project_roots):
        assert impact.read_spectrace_map("praxis", project_roots) == []

    def test_unknown_project_returns_empty(self, project_roots):
        assert impact.read_spectrace_map("nonexistent", project_roots) == []

    def test_invalid_yaml_returns_empty(self, project_roots):
        bad_file = project_roots["praxis"] / "spectrace-map.yaml"
        bad_file.write_text(": bad: yaml: [")
        assert impact.read_spectrace_map("praxis", project_roots) == []


class TestReadContractSnapshot:
    def test_reads_valid_contract(self, project_roots):
        snap = impact.read_contract_snapshot("lore", project_roots)
        assert snap["project"] == "lore"
        assert "journal/decisions" in snap["surfaces"]

    def test_missing_file_returns_empty(self, project_roots):
        assert impact.read_contract_snapshot("praxis", project_roots) == {}

    def test_unknown_project_returns_empty(self, project_roots):
        assert impact.read_contract_snapshot("unknown", project_roots) == {}


class TestGitChangedFiles:
    def test_returns_files_on_success(self, project_roots):
        mock_result = type("R", (), {"stdout": "a.py\nb.py\n", "returncode": 0})()
        with patch("subprocess.run", return_value=mock_result):
            files = impact.git_changed_files("lore", "HEAD~1", "HEAD", project_roots)
        assert files == ["a.py", "b.py"]

    def test_returns_empty_on_error(self, project_roots):
        import subprocess

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            files = impact.git_changed_files("lore", "HEAD~1", "HEAD", project_roots)
        assert files == []

    def test_missing_project_returns_empty(self, project_roots):
        assert (
            impact.git_changed_files("unknown", "HEAD~1", "HEAD", project_roots) == []
        )

    def test_invalid_ref_raises(self, project_roots):
        with pytest.raises(ValueError):
            impact.git_changed_files("lore", "", "HEAD", project_roots)


class TestBuildGraph:
    def test_builds_with_no_changes(self, project_roots):
        with patch("subprocess.run", side_effect=OSError("no git")):
            result = impact.build_graph("HEAD~1", "HEAD", ["lore"], project_roots)
        assert result["changed_files"] == {}
        assert result["blast"]["risk_level"] == "low"

    def test_includes_edge_summary(self, project_roots):
        mock_diff = type("R", (), {"stdout": "", "returncode": 0})()
        with patch("subprocess.run", return_value=mock_diff):
            result = impact.build_graph("HEAD~1", "HEAD", ["lore"], project_roots)
        assert "annotated" in result["edge_summary"]
        assert "inferred" in result["edge_summary"]
        assert "contract" in result["edge_summary"]


class TestImpactView:
    def test_adds_recommendations(self, project_roots):
        from praxis import synthesis

        mock_result = type("R", (), {"stdout": "", "returncode": 0})()
        with patch.object(impact, "_project_roots", return_value=project_roots):
            with patch("subprocess.run", return_value=mock_result):
                result = synthesis.impact_view("HEAD~1", "HEAD", ["lore"])
        assert "recommendations" in result
