Analyze the current state of this project and produce a roadmap.

## Process

1. **Inventory what exists.** Read `src/praxis/synthesis.py` and `src/praxis/lore.py`
   to list all synthesis commands and data readers. Count them. Read `bin/praxis` to
   check which commands have `--json` output.

2. **Inventory what's missing.** Check for:
   - Test coverage: look for `tests/` directory and count test files
   - Caching: look for any caching in `lore.py`
   - Packaging: look for `pyproject.toml` or `setup.py`
   - CLI gaps: commands missing `--json` output
   - Undocumented functions

3. **Check external dependencies.** Read the Geordi initiative at
   `~/dev/council/initiatives/geordi-buildout.md` for endpoints that depend on
   `praxis --json`. Note any gaps.

4. **Produce the roadmap.** Format as:

   ```
   ## What Exists
   [Table of working commands and readers with counts]

   ## What's Missing
   [Bulleted list of gaps with severity]

   ## Natural Next Steps
   [Numbered list, ordered by leverage — what unblocks the most downstream work]
   ```

Keep the output concise. State facts, not aspirations.
