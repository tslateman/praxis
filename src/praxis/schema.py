"""Schema definitions and validation for ecosystem data types.

All validation is plain dict checks. No external dependencies.
Schemas match the real Lineage data formats.
"""

# Lineage journal (decisions.jsonl) -- required fields
DECISION_REQUIRED = {"id", "timestamp", "decision", "rationale"}

# Lineage inbox (observations.jsonl) -- required fields
OBSERVATION_REQUIRED = {"id", "timestamp", "content", "status"}

# Lineage patterns (patterns.yaml) -- required fields per entry
PATTERN_REQUIRED = {"id", "name", "context"}

# Neo missions (YAML) -- required metadata fields
MISSION_REQUIRED = {"metadata", "spec"}

# Valid observation statuses
OBSERVATION_STATUSES = {"raw", "promoted", "rejected"}


def validate(data: dict, required: set, label: str) -> list[str]:
    """Return list of error strings. Empty list means valid."""
    errors = []
    missing = required - set(data.keys())
    if missing:
        errors.append(
            f"{label} missing required fields: {', '.join(sorted(missing))}"
        )
    return errors


def validate_decision(data: dict) -> list[str]:
    return validate(data, DECISION_REQUIRED, "Decision")


def validate_observation(data: dict) -> list[str]:
    errors = validate(data, OBSERVATION_REQUIRED, "Observation")
    if "status" in data and data["status"] not in OBSERVATION_STATUSES:
        errors.append(
            f"Observation status must be one of: {', '.join(sorted(OBSERVATION_STATUSES))}"
        )
    return errors


def validate_pattern(data: dict) -> list[str]:
    return validate(data, PATTERN_REQUIRED, "Pattern")


def validate_mission(data: dict) -> list[str]:
    errors = validate(data, MISSION_REQUIRED, "Mission")
    if "metadata" in data:
        meta = data["metadata"]
        if not isinstance(meta, dict):
            errors.append("Mission metadata must be a dict")
        elif "id" not in meta and "name" not in meta:
            errors.append("Mission metadata must contain id or name")
    if "spec" in data:
        spec = data["spec"]
        if not isinstance(spec, dict):
            errors.append("Mission spec must be a dict")
        elif "objective" not in spec:
            errors.append("Mission spec must contain objective")
    return errors
