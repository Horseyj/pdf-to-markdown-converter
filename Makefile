.PHONY: install install-cpu test convert clean

# Default: GPU PyTorch wheels (~2GB). Works on any system.
install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

# CPU-only PyTorch wheels (~200MB). Linux only. Use on machines without an NVIDIA GPU.
install-cpu:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]" --extra-index-url https://download.pytorch.org/whl/cpu

test:
	.venv/bin/pytest -v

convert:
	.venv/bin/pdf2md

clean:
	rm -rf .venv build dist *.egg-info src/*.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
