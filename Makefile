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
