import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_claude_md_format_doc_matches_makefile_recipe():
    claude_md = (ROOT / "CLAUDE.md").read_text()
    makefile = (ROOT / "Makefile").read_text()

    doc_match = re.search(r"^make format\s+#\s*(.+)$", claude_md, re.MULTILINE)
    assert doc_match, "CLAUDE.md must document `make format`"
    documented_command = doc_match.group(1).strip()

    recipe_match = re.search(r"^format:\n\t(.+)$", makefile, re.MULTILINE)
    assert recipe_match, "Makefile must define a format recipe"
    actual_command = recipe_match.group(1).strip()

    assert documented_command == actual_command, (
        f"CLAUDE.md documents `make format` as `{documented_command}` "
        f"but the Makefile actually runs `{actual_command}`"
    )
