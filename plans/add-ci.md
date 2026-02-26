# Add GitHub Actions CI

## Context

Praxis is a Python 3.10+ project that reads from Lore's data files and
synthesizes actionable views. It has no Makefile, no linter configuration in
`pyproject.toml`, and no existing CI workflow.

### What exists

- **Source**: `src/praxis/` -- three modules (`cli.py`, `lore.py`,
  `synthesis.py`)
- **Tests**: `tests/` -- 98 pytest tests across `test_lore.py` and
  `test_synthesis.py`, with shared fixtures in `conftest.py`
- **Dependencies**: PyYAML (sole runtime dep), pytest (test dep)
- **Packaging**: `pyproject.toml` with setuptools backend and a
  `console_scripts` entry point
- **Linting**: ruff is used locally (`.ruff_cache/` exists, ruff 0.8.0
  installed) but has no config in `pyproject.toml`
- **No Makefile**: tests run via `python -m pytest`; no `make test` or
  `make check` targets
- **No git remote**: the repo has no push target yet
- **No `.github/` directory**

### Sibling conventions

Council and Tutor both use `.github/workflows/ci.yml` triggered on push to
`main` and on pull requests. Both run on `ubuntu-latest`. Council uses
`actions/checkout@v4` and `actions/setup-node@v4`. Tutor adds a weekly cron
schedule. Both install tools globally and run checks in sequence within a single
job.

Praxis is a Python project, not a docs-only repo, so the workflow should use
`actions/setup-python@v5` instead of Node tooling.

## What to Do

### 1. Add ruff configuration to `pyproject.toml`

**File**: `~/dev/praxis/pyproject.toml`

Append a `[tool.ruff]` section so CI and local linting share the same config:

```toml
[tool.ruff]
target-version = "py310"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "W"]
```

This enables pyflakes, pycodestyle errors/warnings, and isort -- a minimal,
opinionated set that catches real bugs without generating noise.

### 2. Add pytest configuration to `pyproject.toml`

**File**: `~/dev/praxis/pyproject.toml`

Append a `[tool.pytest.ini_options]` section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 3. Create the CI workflow

**File**: `~/dev/praxis/.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  check:
    name: Lint & Test
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install ruff pytest pyyaml
          pip install -e .

      - name: Lint (ruff check)
        run: ruff check src/ tests/

      - name: Format check (ruff format)
        run: ruff format --check src/ tests/

      - name: Test
        run: pytest
```

Key decisions:

- **Single job, sequential steps** -- matches sibling convention. Praxis is
  small; parallelizing lint and test adds complexity without saving time.
- **Python 3.13** -- matches the locally installed version (pyenv 3.13.0).
  `requires-python = ">=3.10"` in `pyproject.toml` sets the floor; CI tests
  against the version the author uses.
- **No dependency caching** -- `pip install` for three packages takes seconds.
  Add caching later if the dep list grows.
- **`pip install -e .`** -- installs praxis as a package so pytest can import
  `praxis.*` without `PYTHONPATH` hacks.
- **ruff check + ruff format** -- two separate steps with clear names. `ruff
check` catches lint errors; `ruff format --check` catches formatting drift.

### 4. Add a Makefile

**File**: `~/dev/praxis/Makefile`

```makefile
.PHONY: lint format test check

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

test:
	pytest

check: lint
	ruff format --check src/ tests/
	pytest
```

This gives local parity with CI: `make check` runs the same sequence as the
workflow. `make format` fixes formatting; `make lint` checks without fixing.

### 5. Add a git remote and push

Before CI can run, the repo needs a GitHub remote. Create the repo and push:

```bash
gh repo create tslater/praxis --private --source=. --push
```

This step is manual and outside the scope of the CI implementation itself.

## What NOT to Do

- **Do not add a matrix build** for multiple Python versions. One version is
  enough for a personal tool. Add a matrix if the project gains external users.
- **Do not add a cron schedule**. Praxis has no external links or time-sensitive
  checks. Weekly runs waste Actions minutes.
- **Do not add Node tooling** (prettier, markdownlint, vale). Praxis is a
  Python project. Markdown quality checks belong in Council or Tutor.
- **Do not add mypy or type checking**. The codebase has no type annotations
  beyond `list[dict]` and `dict`. Add mypy after annotating the codebase.
- **Do not add coverage enforcement**. Add coverage reporting after the test
  suite stabilizes.
- **Do not install Lore as a dependency**. Tests use `monkeypatch` to set
  `LORE_DIR` to a temp directory -- they never touch real Lore data.
- **Do not add `workflow_dispatch`**. Manual triggers add no value for a repo
  with automatic push/PR triggers.

## Acceptance Criteria

1. `ruff check src/ tests/` exits 0 locally
2. `ruff format --check src/ tests/` exits 0 locally
3. `pytest` exits 0 locally (98 tests pass)
4. `make check` runs lint, format check, and tests in sequence and exits 0
5. `.github/workflows/ci.yml` exists and matches the structure above
6. After pushing to GitHub, the Actions tab shows a green CI run on `main`
