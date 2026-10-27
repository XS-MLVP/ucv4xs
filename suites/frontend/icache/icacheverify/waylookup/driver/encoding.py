"""Encode typed way-lookup transactions into RTL payload dictionaries."""

from __future__ import annotations

from typing import Any

from icacheverify.waylookup.transaction.types import WayLookupEntry
from icacheverify.waylookup.transaction.types import WayLookupWrite


def encode_entry(entry: WayLookupEntry) -> dict[str, Any]:
    return {
        "vSetIdx": tuple(entry.vset_idx),
        "waymask": tuple(entry.waymask),
        "pTag": entry.ptag,
        "maybeRvcMap": tuple(entry.maybe_rvc_map),
        "metaCodes": tuple(entry.meta_codes),
        "isMmio": entry.is_mmio,
        "itlbPbmt": entry.itlb_pbmt,
    }


def encode_write(write: WayLookupWrite, *, include_exception: bool = True) -> dict[str, Any]:
    """Encode one prefetch-port write.

    firtool removes port 1's ``exceptionEntry`` because the RTL reads the
    exception only from the head port, so the second encoder must omit it.
    """
    entry = write.entry
    payload: dict[str, Any] = {
        "entry": encode_entry(entry),
        "ftqIdx": {"flag": write.ftq_flag, "value": write.ftq_value},
    }
    if include_exception:
        payload["exceptionEntry"] = {
            "itlbException_value": entry.exception.value,
            "gpAddr_addr": entry.exception.gpaddr,
            "isForVSnonLeafPTE": entry.exception.is_for_vs_non_leaf_pte,
        }
    return payload


def encode_control(
    *,
    flush: int = 0,
    s3_valid: int = 0,
    s3_flag: int = 0,
    s3_value: int = 0,
    real_two_fetch: int = 0,
) -> dict[str, int]:
    return {
        "flush": flush,
        "flushFromBpu_s3_valid": s3_valid,
        "flushFromBpu_s3_bits_flag": s3_flag,
        "flushFromBpu_s3_bits_value": s3_value,
        "fromMainPipe_realTwoFetchValid": real_two_fetch,
    }
