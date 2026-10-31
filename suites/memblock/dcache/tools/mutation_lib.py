"""P03/P04/P06/P12: checker-sensitivity experiments (expected readback faults).

Each entry deliberately corrupts one *oracle* — a model prediction or an observed
value — and the paired test must FAIL.  If the test still passes, the assertion is
not区分性 (it does not actually depend on the value it claims to check).

These are checker experiments, not RTL mutants: nothing under `rtl/` changes.

Usage: `DCACHE_MUTATION=<name> pytest <nodeid>` via tools/selfcheck_checkers.py.
"""
from __future__ import annotations

import os

REGISTRY: dict[str, dict] = {}


def _register(name: str, target: str, kind: str, describe: str):
    def deco(fn):
        REGISTRY[name] = {"name": name, "target": target, "kind": kind,
                          "describe": describe, "apply": fn}
        return fn
    return deco


def _xor_low_bit(value, mask: int = 1):
    return value ^ mask


@_register("bda_readback", "suites.memblock.dcache.banked_data_array.model",
           "readback_fault", "first read-window bank flipped after the model answer")
def _bda_readback():
    from suites.memblock.dcache.banked_data_array import model as mod

    original = mod.BankedDataArrayModel.read_result

    def patched(self, addr, addr_dup, way_en, bank_mask, previous=None):
        out = list(original(self, addr, addr_dup, way_en, bank_mask, previous))
        out[0] = _xor_low_bit(out[0])
        return out

    mod.BankedDataArrayModel.read_result = patched


@_register("cf_expected", "suites.memblock.dcache.counter_filter.model",
           "expected_mutation", "query hit/miss inverted")
def _cf_expected():
    from suites.memblock.dcache.counter_filter import model as mod

    original = mod.CounterFilterModel.query

    def patched(self, idx, way, valid):
        return not original(self, idx, way, valid)

    mod.CounterFilterModel.query = patched


@_register("dta_readback", "suites.memblock.dcache.duplicated_tag_array.model",
           "readback_fault", "tag word low bit flipped after the model answer")
def _dta_readback():
    from suites.memblock.dcache.duplicated_tag_array import model as mod

    target = getattr(mod, "DuplicatedTagArrayModel")
    original = target.read

    def patched(self, index, *args, **kwargs):
        words = list(original(self, index, *args, **kwargs))
        words[0] = _xor_low_bit(words[0])
        return words

    target.read = patched


@_register("mq_expected", "suites.memblock.dcache.miss_queue.env",
           "expected_mutation", "refill beat recombination flipped")
def _mq_expected():
    from suites.memblock.dcache.miss_queue import env as mod

    original = mod.line_from_beats

    def patched(beat0, beat1):
        return _xor_low_bit(original(beat0, beat1))

    mod.line_from_beats = patched


@_register("lp_expected", "suites.memblock.dcache.load_pipe.env",
           "expected_mutation", "DCache index oracle shifted")
def _lp_expected():
    from suites.memblock.dcache.load_pipe import env as mod

    original = mod.dcache_index
    mod.dcache_index = lambda vaddr: (original(vaddr) + 1) & 0xFF


@_register("mp_expected", "suites.memblock.dcache.miss_queue.env",
           "expected_mutation", "alias oracle shifted")
def _mp_expected():
    from suites.memblock.dcache.miss_queue import env as mod

    original = mod.dcache_alias
    mod.dcache_alias = lambda vaddr: (original(vaddr) + 1) & 0x3


@_register("dcache_readback", "suites.memblock.dcache.dcache.env",
           "readback_fault", "load response data low bit flipped")
def _dcache_readback():
    from suites.memblock.dcache.dcache import env as mod

    original = mod.DcacheEnv.load_response

    def patched(self, lane):
        out = dict(original(self, lane))
        out["data"] = _xor_low_bit(out["data"])
        return out

    mod.DcacheEnv.load_response = patched


@_register("store_hit_readback", "suites.memblock.dcache.dcache.env",
           "readback_fault", "store hit id flipped, response otherwise intact")
def _store_hit_readback():
    from suites.memblock.dcache.dcache import env as mod

    original = mod.DcacheEnv.wait_store_hit

    def patched(self, limit=10, **kwargs):
        out = original(self, limit, **kwargs)
        if out is not None:
            out["hit_id"] = _xor_low_bit(out["hit_id"])
        return out

    mod.DcacheEnv.wait_store_hit = patched


def apply(name: str) -> dict:
    if name not in REGISTRY:
        raise SystemExit(f"unknown mutation {name!r}; known: {sorted(REGISTRY)}")
    entry = REGISTRY[name]
    entry["apply"]()
    return entry
