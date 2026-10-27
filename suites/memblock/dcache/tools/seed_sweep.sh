#!/bin/sh
# Multi-seed regression sweep for the DCache UT.
#
# Purpose: prove the suite is stable under a different Verilator random-seed and
# Python-seed, not to re-derive coverage numbers.  A full audit of one run takes
# ~10 minutes (the per-point JSON is 260 MB before compaction), so auditing is
# opt-in via `--audit`; the canonical coverage numbers come from the seed-1 full
# regression instead.
#
# Usage: tools/seed_sweep.sh [--audit] 1 2 3 4
set -eu
cd "$(dirname "$0")/.."
PY=/home/xyl/xreactor/output/toffee-migration/venv/bin/python
export PYTHONPATH="/usr/local/share/picker/python:$PWD"

AUDIT=0
if [ "${1:-}" = "--audit" ]; then
  AUDIT=1
  shift
fi

for seed in "$@"; do
  name="seed-sweep-$(printf '%02d' "$seed")"
  echo "=== seed $seed -> $name"
  DCACHE_VERILATOR_SEED="$seed" DCACHE_TEST_RANDOM_SEED="$seed" \
    "$PY" tools/run.py --name "$name" --workers 4 tests
  if [ "$AUDIT" = "1" ]; then
    "$PY" tools/coverage_audit.py "$name"
    "$PY" tools/compact_results.py "$name"
  fi
done
