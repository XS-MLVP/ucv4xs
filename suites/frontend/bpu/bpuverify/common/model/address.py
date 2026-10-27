"""Address-field codecs shared by predictor transaction adapters.

XiangShan PrunedAddr stores halfword addresses in ``addr``. Adapters opting
into these codecs expose byte-address transactions; ITTAGE and MicroBTB do so.
Legacy adapters must be audited before migration, not silently reinterpreted.
"""

from __future__ import annotations

from operator import index


def encode_pruned_pc(address: int) -> int:
    address = index(address)
    if address < 0 or address & 1:
        raise ValueError(f"PC/target must be a nonnegative halfword-aligned byte address: {address:#x}")
    return address >> 1


def decode_pruned_pc(value: int) -> int:
    return index(value) << 1
