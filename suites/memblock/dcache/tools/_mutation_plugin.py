"""pytest plugin that applies one registered oracle mutation (see mutation_lib)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def pytest_configure(config):
    name = os.environ.get("DCACHE_MUTATION")
    if not name:
        return
    import mutation_lib

    entry = mutation_lib.apply(name)
    print(f"\n[mutation] {entry['kind']}: {entry['name']} — {entry['describe']}")
