"""Path resolution for failure journal storage.

Failures write to Lineage's failures directory, following the same
data/ convention as journal/data/ and inbox/data/.
"""

import os
from pathlib import Path

LINEAGE_DIR = Path(os.environ.get("LINEAGE_DIR", Path.home() / "dev/lineage"))
FAILURES_DIR = LINEAGE_DIR / "failures" / "data"
FAILURES_FILE = FAILURES_DIR / "failures.jsonl"
