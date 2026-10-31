"""ICache verification package.

One subpackage per DUT. Whole-ICache integration is a peer of its subblocks,
never their parent, so that changing an outer adapter cannot reshape a
subblock's test surface.
"""

from __future__ import annotations

__all__ = [
    "waylookup", "replacer", "mshr", "databank", "metabank", "metaarray",
    "dataarray", "missunit", "mainpipe", "prefetchpipe", "icache",
]

from pathlib import Path as _Path

ROOT = _Path(__file__).resolve().parent
