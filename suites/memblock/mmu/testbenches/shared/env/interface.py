"""Read the exact signal schema shipped with a generated DUT artifact.

This module never executes the DUT and never infers a port from a Python
attribute alone. The configuration database is the artifact metadata used to
decide whether a named interface leaf is declared by the bound build.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from ucv import xscfg


MXR_PIN = "io_csr_priv_mxr"


@dataclass(frozen=True)
class MxrInputCapability:
    """Read-only public statement of whether this bound build can drive MXR."""

    driveable: bool
    reason: str | None = None


def signal_schema(schema_path: str | Path) -> tuple[frozenset[str], str]:
    """Return flattened leaf names and a digest of the decoded port tree."""
    path = Path(schema_path)
    try:
        data = xscfg.Database(path).ports
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"generated DUT signal schema is unavailable at {path}"
        ) from exc
    # Identity covers the port tree itself, not container framing, so a
    # re-packed database with identical ports keeps the same digest.
    raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode()
    leaves: set[str] = set()

    def walk(node, prefix: str) -> None:
        if not isinstance(node, dict):
            return
        if "Pin" in node:
            leaves.add(prefix.rstrip("_"))
            return
        for key, value in node.items():
            walk(value, prefix + key + "_")

    walk(data, "")
    if not leaves:
        raise RuntimeError(
            f"generated DUT signal schema at {path} declares no leaf pins"
        )
    return frozenset(leaves), hashlib.sha256(raw).hexdigest()
