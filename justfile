set shell := ["bash", "-c"]

# run the local web UI (binds 127.0.0.1 only)
serve:
	uv run drillpad serve

# run the test suite
test:
	uv run pytest -q

# lint with ruff
lint:
	uv run ruff check .

# what the Makefile's check target runs: lint then test
check:
	make check
