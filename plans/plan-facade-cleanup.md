# Plan: Facade Cleanup

## Context

Praxis was restructured from a loose prototype into an ecosystem facade
(`bin/praxis` wrapping Lineage, Neo, Lore). The restructure is complete and
verified, but left four loose ends: missing `.gitignore`, naive search scoring,
unclear `yq` error messages, and a test observation in the production inbox.

None of these block usage. All improve robustness for when Praxis becomes a git
repo or sees regular use.

## What to Do

### 1. Add `.gitignore`

The test run created `src/praxis/__pycache__/` with `.pyc` files. Praxis has no
git repo yet, but should be ready for one.

Create `~/dev/praxis/.gitignore`:

```text
__pycache__/
*.pyc
```

### 2. Improve search relevance scoring

`search.py:_score_match` uses substring matching with hardcoded thresholds
(1.0/0.9/0.5/0.3). With 53 journal entries this works. As the dataset grows,
common words ("architecture", "decision") will dominate results.

Options, in order of complexity:

1. **Word-boundary matching** -- split query and text into words, match on word
   boundaries instead of substrings. Low effort, meaningful improvement.
2. **Term frequency weighting** -- count how often a term appears in a document
   vs. across all documents. Approximates TF-IDF without external deps.
3. **Fuzzy matching** -- `difflib.SequenceMatcher` from stdlib for approximate
   matching. Handles typos and partial words.

Recommend option 1 first, option 2 if search becomes a primary workflow.

Reference: `src/praxis/search.py:8-18` (`_score_match` function).

### 3. Pre-flight check for `yq`

`store._read_yaml_via_yq` and `registry._read_yaml` raise `RuntimeError` with
"yq failed on {path}" when `yq` is not installed. The actual error is buried in
stderr.

Add a check to `config.py` that runs at import time:

```python
import shutil

YQ_PATH = shutil.which("yq")
if not YQ_PATH:
    import warnings
    warnings.warn(
        "yq not found -- YAML reading will fail. Install: brew install yq"
    )
```

Then use `config.YQ_PATH` in `store._read_yaml_via_yq` and
`registry._read_yaml` instead of the bare string `"yq"`. If `YQ_PATH` is
`None`, raise a clear error before attempting subprocess.

Reference: `src/praxis/config.py`, `src/praxis/store.py:50-60`,
`src/praxis/registry.py:15-25`.

### 4. Clean up test observation

`praxis observe "Test observation from Praxis facade"` wrote `obs-0d37e7e3` to
`~/dev/lineage/inbox/data/observations.jsonl` during verification. This is real
production data.

Two actions:

1. **Remove the test entry** -- filter `obs-0d37e7e3` from
   `observations.jsonl` (the entry with `source: "praxis-test"`).
2. **Use temp dirs for future verification** -- update the verification section
   in the plan to use `LINEAGE_DIR=$(mktemp -d)` so test writes never touch
   production data.

## What NOT to Do

- Do not add external dependencies (PyYAML, fuzzywuzzy) for search
- Do not restructure the package layout -- it just landed
- Do not add a `pyproject.toml` -- the stdlib-only constraint holds

## Files to Create/Modify

| File                                          | Action | Notes                      |
| --------------------------------------------- | ------ | -------------------------- |
| `.gitignore`                                  | Create | `__pycache__/` and `*.pyc` |
| `src/praxis/search.py`                        | Modify | Word-boundary scoring      |
| `src/praxis/config.py`                        | Modify | `yq` pre-flight check      |
| `src/praxis/store.py`                         | Modify | Use `config.YQ_PATH`       |
| `src/praxis/registry.py`                      | Modify | Use `config.YQ_PATH`       |
| `~/dev/lineage/inbox/data/observations.jsonl` | Modify | Remove test entry          |

## Acceptance Criteria

- `git init && git status` shows no `__pycache__` files
- `praxis search "architecture"` returns results ranked by relevance, not
  flooded with low-quality substring matches
- Running `praxis search` without `yq` installed prints
  "yq not found -- install: brew install yq"
- `observations.jsonl` contains no entries with `source: "praxis-test"`
