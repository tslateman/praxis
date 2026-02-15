"""Path resolution for the ecosystem directories.

Each directory can be overridden via environment variable, matching how
lineage.sh resolves LINEAGE_DIR and neo resolves NEO_DIR.
"""

import os
from pathlib import Path

LINEAGE_DIR = Path(os.environ.get("LINEAGE_DIR", Path.home() / "dev/lineage"))
NEO_DIR = Path(os.environ.get("NEO_DIR", Path.home() / "dev/neo"))
LORE_DIR = Path(os.environ.get("LORE_DIR", Path.home() / "dev/lore"))
MIRROR_DIR = Path(os.environ.get("MIRROR_DIR", Path.home() / ".mirror"))

# Shell CLIs -- Praxis delegates write operations to these
LINEAGE_CLI = os.environ.get("LINEAGE_CLI", str(LINEAGE_DIR / "lineage.sh"))
NEO_SYNC = str(NEO_DIR / "scripts/sync.sh")
NEO_PROMOTE = str(NEO_DIR / "scripts/promote.sh")
NEO_START = str(NEO_DIR / "scripts/start.sh")
