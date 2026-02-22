PYTHON ?= python3.11

.PHONY: format lint test check-generated

format:
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest

check-generated:
	PYTHON=$(PYTHON) bash scripts/ci/check_generated.sh
