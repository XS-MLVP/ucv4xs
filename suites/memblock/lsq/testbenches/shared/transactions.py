"""Shared transaction vocabulary for LSQ testbenches.

Only immutable transaction types and domain sentinels live here; pin decoding
stays in each testbench's ``env`` ports layer.
"""
from __future__ import annotations

from dataclasses import dataclass


class _Unset:
    """Sentinel: a transaction field the caller does not constrain."""

    def __repr__(self):
        return "UNSET"


UNSET = _Unset()


@dataclass(frozen=True)
class RobIdentity:
    value: int | None = None
    flag: int | None = None
    former: int | None = None


@dataclass(frozen=True)
class CacheRequest:
    address: int | None = None
    opcode: int | None = None
    valid: int | None = 1


@dataclass(frozen=True)
class UncacheRequest:
    addr: int | None = None
    vaddr: int | None = None
    data: int | None = None
    mask: int | None = None
    ident: int | None = None
    nc: int | None = None
    memory_backed: int | None = None
    rob: RobIdentity | None = None
    valid: int | None = 1


@dataclass(frozen=True)
class Writeback:
    rob: RobIdentity | None = None
    access_fault: int | None = None
    bus_error: int | None = None
    mmio: int | None = None
    ncio: int | None = None
    valid: int | None = 1


@dataclass(frozen=True)
class ExceptionInfo:
    vaddr: int | None = None
    hyper: int | None = None
    access_fault: int | None = None
    bus_error: int | None = None
    rob: RobIdentity | None = None
    valid: int | None = 1


@dataclass(frozen=True)
class SbufferWord:
    valid: int | None = 1
    addr: int | None = None
    vaddr: int | None = None
    mask: int | None = None
    data: int | None = None
    wline: int | None = None


@dataclass(frozen=True)
class ForwardResponse:
    """One ForwardModule S2 answer, decoded for the queried byte window."""

    valid: bool = False
    forward_invalid: bool = False
    match_invalid: bool = False
    addr_invalid: bool = False
    data_invalid: bool = False
    data_invalid_value: int = 0
    forward_mask: int = 0
    forward_data: int = 0


@dataclass(frozen=True)
class ForwardExpectation:
    """Partial Forward expectation: ``None`` fields are not constrained.

    A literal ``False``/``0`` is a checked value, never a sentinel.

    ``forward_mask`` constrains the DUT's forwardMask bits; it is never implied
    by a data-only expectation.  ``data_byte_mask`` selects the byte lanes whose
    forwardData payload is compared and is deliberately separate from
    ``forward_mask``: an original scenario that only checked eight data bytes
    must not silently become sixteen mask assertions.  When ``forward_data`` is
    present a byte range is required, otherwise the check would be vacuous.
    """

    valid: int | None = None
    forward_invalid: int | None = None
    match_invalid: int | None = None
    addr_invalid: int | None = None
    data_invalid: int | None = None
    data_invalid_value: int | None = None
    forward_mask: int | None = None
    forward_data: int | None = None
    data_byte_mask: int | None = None
