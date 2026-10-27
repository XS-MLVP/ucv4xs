"""MissReadyGen UT: combinational fan-out and ready pass-through."""
from __future__ import annotations

import random

import pytest

from dcacheverify.miss_ready_gen.coverage import READY_CLASSES, MissReadyGenCoverage
from dcacheverify.miss_ready_gen.env import CH0_FIELDS, CH_FIELDS, MissReadyGenEnv


@pytest.fixture
def mrg(dut_factory):
    dut = dut_factory("miss_ready_gen")
    return MissReadyGenEnv(dut, MissReadyGenCoverage())


def wide_payload(seed: int) -> dict[str, int]:
    return {
        "source": seed & 0xF,
        "pf_source": (seed >> 4) & 0x7,
        "cmd": (seed * 3) & 0x1F,
        "addr": (seed * 0x10001) & ((1 << 48) - 1),
        "vaddr": (seed * 0x10003) & ((1 << 50) - 1),
        "vaddrAlias": (seed >> 2) & 0x3,
        "vaddrSet": (seed * 7) & 0xFF,
        "full_overwrite": seed & 1,
        "word_idx": (seed >> 1) & 0x7,
        "amo_data": (seed * 0x9E3779B97F4A7C15) & ((1 << 128) - 1),
        "amo_mask": (seed << 3) & 0xFFFF,
        "amo_cmp": (seed * 0xC2B2AE3D27D4EB4F) & ((1 << 128) - 1),
        "req_coh_state": seed & 0x3,
        "id": seed & 0x3F,
        "isBtoT": (seed >> 5) & 1,
        "occupy_way": (seed >> 6) & 0xF,
        "cancel": (seed >> 7) & 1,
        "store_data": (seed * 0xD6E8FEB86659FD93) & ((1 << 512) - 1),
        "store_mask": (seed * 0x2545F4914F6CDD1D) & ((1 << 64) - 1),
    }


def narrow_payload(seed: int) -> dict[str, int]:
    return {
        "source": seed & 0xF,
        "cmd": (seed >> 3) & 0x1F,
        "addr": (seed * 0x10001) & ((1 << 48) - 1),
        "vaddr": (seed * 0x10003) & ((1 << 50) - 1),
        "vaddrAlias": (seed >> 1) & 0x3,
        "vaddrSet": (seed * 5) & 0xFF,
        "req_coh_state": (seed >> 2) & 0x3,
        "id": seed & 0x3F,
        "isBtoT": (seed >> 4) & 1,
        "occupy_way": (seed >> 5) & 0xF,
        "cancel": (seed >> 6) & 1,
        "isSpecMiss": (seed >> 7) & 1,
    }


# MRG-FP-001, MRG-FP-005
async def test_zero_vector_is_transparent(mrg):
    mrg.drive_ready(0)
    for ch in range(4):
        mrg.drive(ch, False, {})
    mrg.eval()
    mrg.check("all zero")
    mrg.coverage.sample_independence("none", "stable")
    mrg.coverage.sample_field("zero", "address")
    mrg.coverage.sample_field("zero", "metadata")
    mrg.coverage.sample_field("zero", "amo")
    mrg.coverage.sample_field("zero", "store")
    # Holding the same inputs must keep the outputs unchanged.
    for _ in range(3):
        mrg.eval()
        mrg.check("all zero held")
    mrg.coverage.sample_independence("none", "stable")


# MRG-FP-002, MRG-FP-003
async def test_ready_matrix_is_per_channel(mrg):
    for ready_mask in READY_CLASSES.values():
        mrg.drive_ready(ready_mask)
        for ch in range(4):
            mrg.drive(ch, True, wide_payload(10 + ch) if ch == 0
                      else narrow_payload(20 + ch))
        mrg.eval()
        mrg.check(f"ready mask {ready_mask:#x}")
        got = [int(signal.value) for signal in mrg.in_ready]
        want = [(ready_mask >> ch) & 1 for ch in range(4)]
        assert got == want, (ready_mask, got, want)
    mrg.coverage.sample_independence("all", "changed")
    mrg.coverage.sample_field("random", "address")
    mrg.coverage.sample_field("random", "metadata")
    mrg.coverage.sample_field("random", "amo")
    mrg.coverage.sample_field("random", "store")


# MRG-FP-004
async def test_walking_bit_all_payload_fields(mrg):
    mrg.drive_ready(0xF)
    for ch, fields in ((0, CH0_FIELDS), (1, CH_FIELDS), (2, CH_FIELDS), (3, CH_FIELDS)):
        for name, width in fields.items():
            for bit in range(width):
                payload = {key: 0 for key in fields}
                payload[name] = 1 << bit
                mrg.drive(ch, True, payload)
                for other in range(4):
                    if other != ch:
                        mrg.drive(other, False, {})
                mrg.eval()
                mrg.check(f"walking {ch}/{name} bit {bit}")
            # All ones for this field.
            payload = {key: 0 for key in fields}
            payload[name] = (1 << width) - 1
            mrg.drive(ch, True, payload)
            mrg.eval()
            mrg.check(f"all ones {ch}/{name}")
        group = {
            "addr": "address", "vaddr": "address", "vaddrAlias": "address",
            "vaddrSet": "address", "source": "metadata", "cmd": "metadata",
            "pf_source": "metadata", "req_coh_state": "metadata", "id": "metadata",
            "isBtoT": "metadata", "occupy_way": "metadata", "cancel": "metadata",
            "isSpecMiss": "metadata", "word_idx": "metadata", "full_overwrite": "metadata",
            "amo_data": "amo", "amo_mask": "amo", "amo_cmp": "amo",
            "store_data": "store", "store_mask": "store",
        }
        mrg.coverage.sample_field("walking_bit", group[name])
        mrg.coverage.sample_field("all_ones", group[name])
    mrg.coverage.sample_independence("single", "changed")


# MRG-FP-003, MRG-FP-005
async def test_valid_patterns_and_independence(mrg):
    mrg.drive_ready(0x5)
    for pattern in ("none", "single", "multi", "all"):
        selected = {
            "none": [],
            "single": [2],
            "multi": [0, 3],
            "all": [0, 1, 2, 3],
        }[pattern]
        for ch in range(4):
            mrg.drive(ch, ch in selected, wide_payload(ch * 31 + 5) if ch == 0
                      else narrow_payload(ch * 17 + 3))
        mrg.eval()
        mrg.check(f"pattern {pattern}")
        valid = [int(signal.value) for signal in mrg.out_valid]
        assert valid == [1 if ch in selected else 0 for ch in range(4)]
        mrg.coverage.sample_independence(pattern, "changed")
        # Stable check for this pattern.
        mrg.eval()
        mrg.check(f"pattern {pattern} stable")
        mrg.coverage.sample_independence(pattern, "stable")


# MRG-FP-001..004
async def test_random_vectors(mrg):
    rng = random.Random(0x4D52_2026)
    for step in range(300):
        ready_mask = rng.randrange(16)
        mrg.drive_ready(ready_mask)
        for ch in range(4):
            valid = rng.random() < 0.6
            payload = wide_payload(rng.getrandbits(20)) if ch == 0\
                else narrow_payload(rng.getrandbits(20))
            mrg.drive(ch, valid, payload)
        mrg.eval()
        mrg.check(f"random vector {step}")
        mrg.coverage.sample_field("random", "address")
        mrg.coverage.sample_field("random", "metadata")
        if step % 7 == 0:
            mrg.coverage.sample_field("random", "amo")
            mrg.coverage.sample_field("random", "store")
