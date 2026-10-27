"""Decode sampled way-lookup signals into transactions.

Decoding only reports what the wires say; it never predicts or compares.
"""

from __future__ import annotations

from typing import Any

from icacheverify.waylookup.transaction.types import ItlbException
from icacheverify.waylookup.transaction.types import WayLookupEntry
from icacheverify.waylookup.transaction.types import WayLookupRead


def _plain(value: Any) -> Any:
    """Normalise toffee BundleValue/LogicValue trees into plain Python."""
    if hasattr(value, "as_dict"):
        return {key: _plain(item) for key, item in value.as_dict().items()}
    if isinstance(value, dict):
        if value and all(str(key).isdigit() for key in value):
            return tuple(_plain(value[key]) for key in sorted(value, key=int))
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_plain(item) for item in value)
    if hasattr(value, "as_int"):
        return value.as_int()
    return value


def decode_entry(value: Any) -> WayLookupEntry:
    data = _plain(value)
    exception = data.get("exceptionEntry", {}) if isinstance(data, dict) else {}
    entry = data["entry"] if "entry" in data else data
    return WayLookupEntry(
        vset_idx=tuple(entry["vSetIdx"]),
        waymask=tuple(entry["waymask"]),
        ptag=int(entry["pTag"]),
        maybe_rvc_map=tuple(entry["maybeRvcMap"]),
        meta_codes=tuple(entry["metaCodes"]),
        is_mmio=int(entry.get("isMmio", 0)),
        itlb_pbmt=int(entry.get("itlbPbmt", 0)),
        exception=ItlbException(
            value=int(exception.get("itlbException_value", 0)),
            gpaddr=int(exception.get("gpAddr_addr", 0)),
            is_for_vs_non_leaf_pte=int(exception.get("isForVSnonLeafPTE", 0)),
        ),
    )


def decode_read(sample: Any) -> WayLookupRead | None:
    """Return a beat only when ``valid && ready`` was true at the edge."""
    data = _plain(sample)
    if not data.get("valid") or not data.get("ready"):
        return None
    # The payload binding is the ``Vec[WayLookupInfo]`` itself, one entry per
    # read slot, so slot 0 is the head of the queue.
    slots = data["bits"]
    first = slots[0]
    # Slot 0's valid is tied to constant true in RTL, so firtool removes the
    # leaf entirely; its absence means "always valid", not "unknown".
    if not first.get("valid", 1):
        return None
    return WayLookupRead(valid=1, entry=decode_entry(first["bits"]))
