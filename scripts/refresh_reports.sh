#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.run_pipeline --n-impressions "${1:-25000}"
python scripts/prepare_postgres.py
node scripts/verify_postgres.mjs
python scripts/build_tableau.py
python -m pytest -q
