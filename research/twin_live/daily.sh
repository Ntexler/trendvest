#!/usr/bin/env bash
# The daily run (weekdays, after Asia closes and before New York opens). Recomputes the twin experiment and the
# wallet's prices from real data. Never edits rules.json.
set -euo pipefail
cd "$(dirname "$0")/../.."
python -m research.twin_live.live
python -m research.wallet.export_prices
python -m research.macro.collect
