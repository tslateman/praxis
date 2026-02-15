"""Path resolution for failure journal storage.

Failures write to Lore's failures directory, following the same
data/ convention as journal/data/ and inbox/data/.
"""

import os
from pathlib import Path

LORE_DIR = Path(os.environ.get("LORE_DIR", Path.home() / "dev/lore"))
NEO_DIR = Path(os.environ.get("NEO_DIR", Path.home() / "dev/neo"))
MIRROR_DIR = Path(os.environ.get("MIRROR_DIR", Path.home() / "dev/mirror"))

FAILURES_DIR = LORE_DIR / "failures" / "data"
FAILURES_FILE = FAILURES_DIR / "failures.jsonl"
JOURNAL_FILE = LORE_DIR / "journal" / "data" / "decisions.jsonl"
INBOX_FILE = LORE_DIR / "inbox" / "data" / "observations.jsonl"
NEO_LOGS_DIR = NEO_DIR / "logs"
