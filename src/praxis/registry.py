"""Lore Registry reader.

Reads ~/dev/lore/registry/ YAML files via yq (no PyYAML dependency).
Provides project metadata, clusters, and relationships from Lore.
"""

import json
import subprocess
from pathlib import Path

from . import config


def _read_yaml(path: Path) -> dict:
    """Read YAML via yq, return parsed dict."""
    if not path.exists():
        return {}
    result = subprocess.run(
        ["yq", "-o=json", ".", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yq failed on {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _registry_path(filename: str) -> Path:
    return config.LORE_DIR / "registry" / filename


def read_metadata() -> dict:
    """Read project metadata from Lore registry."""
    data = _read_yaml(_registry_path("metadata.yaml"))
    return data.get("metadata", {})


def read_clusters() -> dict:
    """Read cluster definitions from Lore registry."""
    data = _read_yaml(_registry_path("clusters.yaml"))
    return data.get("clusters", {})


def read_relationships() -> dict:
    """Read cross-project relationships from Lore registry."""
    return _read_yaml(_registry_path("relationships.yaml"))


def read_contracts() -> dict:
    """Read contract definitions from Lore registry."""
    return _read_yaml(_registry_path("contracts.yaml"))


def list_projects() -> list[str]:
    """List all projects known to Lore via metadata or clusters."""
    projects = set()

    metadata = read_metadata()
    projects.update(metadata.keys())

    clusters = read_clusters()
    for cluster in clusters.values():
        if isinstance(cluster, dict):
            components = cluster.get("components", {})
            if isinstance(components, dict):
                projects.update(components.keys())

    return sorted(projects)


def show(project: str) -> dict:
    """Assemble all Lore knows about a project."""
    result = {"project": project}

    metadata = read_metadata()
    if project in metadata:
        result["metadata"] = metadata[project]

    clusters = read_clusters()
    for cluster_name, cluster in clusters.items():
        if isinstance(cluster, dict):
            components = cluster.get("components", {})
            if isinstance(components, dict) and project in components:
                result["cluster"] = cluster_name
                result["cluster_info"] = components[project]
                break

    relationships = read_relationships()
    deps = relationships.get("dependencies", {})
    if project in deps:
        result["dependencies"] = deps[project]

    return result


def context(project: str) -> dict:
    """Rich context for a project -- metadata, cluster, and dependencies."""
    info = show(project)

    # Add reverse dependencies (who depends on this project)
    relationships = read_relationships()
    deps = relationships.get("dependencies", {})
    dependents = []
    for dep_project, dep_info in deps.items():
        if isinstance(dep_info, dict):
            for dep in dep_info.get("depends_on", []):
                if isinstance(dep, dict) and dep.get("project") == project:
                    dependents.append(
                        {"project": dep_project, "reason": dep.get("reason", "")}
                    )

    if dependents:
        info["dependents"] = dependents

    return info
