"""Driver-side encoding for NewLoadUnit.

Tests build :class:`CycleInput` transactions; :func:`to_inputs` lowers them to
the nested encoding consumed by :class:`LoadParentEnv.drive`, which owns the
generated input binding.

The natural-language load fields (address, operation, ROB/LQ/SQ identity) stay
in :mod:`..transactions`; the dictionaries here are an encoding detail and are
not imported by functional tests.
"""
from __future__ import annotations

import random

from suites.memblock.lsu.testbenches.load_s0.env import LDIN_FIELDS
from suites.memblock.lsu.testbenches.load_s0.env import REPLAY_FIELDS
from suites.memblock.lsu.testbenches.load_s0.env import _INPUT_WIDTHS as S0_INPUT_WIDTHS
from suites.memblock.lsu.testbenches.load_s2.env import BYPASS_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import DCRESP_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import MSHR_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import SB_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import SQ_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import TLD_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import UNC_FIELDS
from suites.memblock.lsu.testbenches.store_trigger.env import TriggerConfig

from suites.memblock.lsu.testbenches.new_load_unit.transactions import CycleInput

REDIRECT_FIELDS = {"level": 1, "robIdx_flag": 1, "robIdx_value": 8,
                   "robIdx_isFormer": 1}
NUKE_FIELDS = {"robIdx_flag": 1, "robIdx_value": 8, "robIdx_isFormer": 1,
               "sqIdx_first_flag": 1, "sqIdx_second_flag": 1, "sqIdx_value": 6,
               "paddr": 48, "mask": 16, "matchType": 2}
TLB_RESP_FIELDS = {"paddr_0": 48, "paddr_1": 48, "gpaddr_0": 64, "fullva": 64,
                   "pbmt_0": 2, "miss": 1, "isForVSnonLeafPTE": 1,
                   "excp_0_vaNeedExt": 1, "excp_0_isHyper": 1,
                   "excp_0_gpf_ld": 1, "excp_0_pf_ld": 1, "excp_0_af_ld": 1}
STD_FIELDS = {"valid": 1, "first_flag": 1, "second_flag": 1, "value": 6}
FORWARD_DATA_FIELDS = {f"forwardData_{index}": 8 for index in range(16)}


def forward_bits(fields) -> dict:
    """S2 only carries the forward masks; the data path needs the bytes too."""
    bits = {name: 0 for name in fields}
    bits.update({name: 0 for name in FORWARD_DATA_FIELDS})
    return bits


def validate_input_keys(values, schema, path="inputs"):
    """Reject misspelled keys instead of silently leaving DUT inputs idle.

    Sparse bit dictionaries remain supported: absent fields deliberately mean
    zero. This is shape validation, not proof of microarchitectural legality.
    """
    if isinstance(schema, dict):
        if not isinstance(values, dict):
            raise TypeError(f"{path}: expected dict")
        unknown = set(values) - set(schema)
        if unknown:
            raise ValueError(f"{path}: unknown input keys {sorted(unknown)}")
        for key in values:
            validate_input_keys(values[key], schema[key], f"{path}.{key}")
    elif isinstance(schema, list):
        if not isinstance(values, list) or len(values) != len(schema):
            raise ValueError(f"{path}: expected list of length {len(schema)}")
        for index, (value, entry) in enumerate(zip(values, schema)):
            validate_input_keys(value, entry, f"{path}[{index}]")


def blank_trigger() -> dict:
    return {"configs": [TriggerConfig() for _ in range(4)],
            "enables": [0, 0, 0, 0], "debugMode": 0, "canRaiseBpExp": 1}


def blank_inputs() -> dict:
    """All idle values for one cycle; shared with reset/prime/random stimulus."""
    return {
        "redirect": {"valid": 0, "bits": {name: 0 for name in REDIRECT_FIELDS}},
        "specialMode": 0,
        "robHeadPtr": {"flag": 0, "value": 0, "isFormer": 0},
        "ldin": {"valid": 0, "bits": {name: 0 for name in LDIN_FIELDS}},
        "replay": {"valid": 0, "bits": {name: 0 for name in REPLAY_FIELDS}},
        "pmp": {"ld": 0, "mmio": 0},
        "tlbResp": {"valid": 0, "bits": {name: 0 for name in TLB_RESP_FIELDS}},
        "tlbHint": {"id": 0, "full": 0},
        "dcache": {"ready": 1, "resp": {"bits": {**{name: 0 for name in DCRESP_FIELDS}, "data": 0}},
                   "bank": 0, "rr": 0, "mq_nack": 0},
        "rrGrant": 0,
        "ldld": 0,
        "trigger": blank_trigger(),
        "nuke": [{"valid": 0, "bits": {name: 0 for name in NUKE_FIELDS}}
                 for _ in range(2)],
        "sq": {"valid": 0, "bits": forward_bits(SQ_FIELDS)},
        "sb": {"valid": 0, "bits": forward_bits(SB_FIELDS)},
        "unc": {"valid": 0, "bits": forward_bits(UNC_FIELDS)},
        "mshr": {"valid": 0, "bits": forward_bits(MSHR_FIELDS)},
        "tld0": {"valid": 0, "bits": forward_bits(TLD_FIELDS)},
        "tld1": {"valid": 0, "bits": forward_bits(TLD_FIELDS)},
        "bypass1": {"valid": 0, "bits": {"paddr": 0}},
        "bypass2": {"valid": 0, "bits": {**{name: 0 for name in BYPASS_FIELDS}, "data": 0}},
        "std": {"current": [{"valid": 0, "bits": {name: 0 for name in STD_FIELDS}}
                            for _ in range(2)],
                "previous": [{"valid": 0, "bits": {name: 0 for name in STD_FIELDS}}
                             for _ in range(2)]},
        "rarResp": {"valid": 0, "nuke": 0},
        "rarReady": 1, "rawReady": 1,
    }


def to_inputs(plan: CycleInput) -> dict:
    """Lower one immutable cycle plan to the generated input encoding."""
    inp = blank_inputs()

    if plan.load is not None:
        load = plan.load
        inp["ldin"]["valid"] = 1
        bits = inp["ldin"]["bits"]
        bits["fuOpType"] = load.fu_op
        bits["src_0"] = load.address
        bits["robIdx_flag"] = load.rob.flag
        bits["robIdx_value"] = load.rob.value
        bits["robIdx_isFormer"] = load.rob.is_former
        bits["pdest"] = load.pdest
        bits["rfWen"] = int(load.rf_wen)
        bits["fpWen"] = int(load.fp_wen)
        bits["vecWen"] = int(load.vec_wen)
        bits["v0Wen"] = int(load.v0_wen)
        bits["lqIdx_value"] = load.lq_idx
        bits["sqIdx_value"] = load.sq_idx
        bits["storeSetHit"] = int(load.store_set_hit)
        if load.wait_sq is not None:
            bits["waitSqIdx_first_flag"] = load.wait_sq.first_flag
            bits["waitSqIdx_second_flag"] = load.wait_sq.second_flag
            bits["waitSqIdx_value"] = load.wait_sq.value

    if plan.replay is not None:
        replay = plan.replay
        inp["replay"]["valid"] = 1
        bits = inp["replay"]["bits"]
        bits["entrance"] = replay.entrance
        bits["vaddr"] = replay.vaddr
        bits["fullva"] = replay.fullva
        bits["size"] = replay.size
        bits["mask"] = replay.mask
        bits["uop_lqIdx_flag"] = replay.lq_idx_flag
        bits["uop_lqIdx_value"] = replay.lq_idx
        bits["uop_pdest"] = replay.pdest
        bits["uop_rfWen"] = int(replay.rf_wen)
        bits["uop_fuOpType"] = replay.fu_op
        bits["uncacheReplay"] = int(replay.uncache_replay)
        bits["ncReplay"] = int(replay.nc_replay)

    if plan.translation is not None:
        translation = plan.translation
        inp["tlbResp"]["valid"] = 1
        bits = inp["tlbResp"]["bits"]
        bits["paddr_0"] = translation.paddr
        bits["paddr_1"] = translation.paddr_1
        bits["fullva"] = translation.fullva
        bits["miss"] = int(translation.miss)
        bits["pbmt_0"] = translation.pbmt
        bits["excp_0_pf_ld"] = int(translation.page_fault)

    dcache = plan.dcache
    inp["dcache"]["ready"] = int(dcache.ready)
    inp["dcache"]["bank"] = int(dcache.bank_conflict)
    inp["dcache"]["rr"] = int(dcache.rr_conflict)
    inp["dcache"]["mq_nack"] = int(dcache.mshr_nack)
    read = plan.dcache_read
    inp["dcache"]["resp"]["bits"] = {
        "data": read.data,
        "miss": int(read.miss),
        "mshr_id": read.mshr_id,
        "meta_prefetch": read.meta_prefetch,
        "handled": int(read.handled),
    }

    inp["redirect"]["valid"] = int(plan.redirect.valid)
    inp["redirect"]["bits"] = {
        "level": plan.redirect.level,
        "robIdx_flag": plan.redirect.rob.flag,
        "robIdx_value": plan.redirect.rob.value,
        "robIdx_isFormer": plan.redirect.rob.is_former,
    }

    for slot, query in enumerate(plan.nuke):
        inp["nuke"][slot]["valid"] = int(query.valid)
        bits = inp["nuke"][slot]["bits"]
        bits["robIdx_flag"] = query.rob.flag
        bits["robIdx_value"] = query.rob.value
        bits["robIdx_isFormer"] = query.rob.is_former
        bits["sqIdx_first_flag"] = query.sq.first_flag
        bits["sqIdx_second_flag"] = query.sq.second_flag
        bits["sqIdx_value"] = query.sq.value
        bits["paddr"] = query.paddr
        bits["mask"] = query.mask
        bits["matchType"] = query.match_type

    inp["bypass1"]["valid"] = int(plan.bypass1.valid)
    inp["bypass1"]["bits"]["paddr"] = plan.bypass1.paddr
    inp["bypass2"]["valid"] = int(plan.bypass2.valid)
    inp["bypass2"]["bits"].update({
        "data": plan.bypass2.data,
        "nderr": int(plan.bypass2.nderr),
        "derr": int(plan.bypass2.derr),
    })

    if plan.trigger is not None:
        # Copy each frozen transaction slot into a fresh driver-compatible
        # object.  The shared store-trigger configuration type stays mutable on
        # purpose (it is the legacy driver encoding); the transaction layer is
        # what guarantees immutability for callers.
        inp["trigger"]["configs"] = [
            TriggerConfig(match_type=slot.match_type, select=slot.select,
                          timing=slot.timing, action=slot.action,
                          chain=slot.chain, store=slot.store,
                          tdata2=slot.tdata2)
            for slot in plan.trigger.configs
        ]
        inp["trigger"]["enables"] = [int(bit) for bit in plan.trigger.enables]
        inp["trigger"]["debugMode"] = int(plan.trigger.debug_mode)
        inp["trigger"]["canRaiseBpExp"] = int(plan.trigger.can_raise_bp_exp)

    inp["rarResp"] = {"valid": int(plan.rar.valid), "nuke": int(plan.rar.nuke)}
    inp["rarReady"] = int(plan.rar_ready)
    inp["rawReady"] = int(plan.raw_ready)
    inp["ldld"] = int(plan.ldld_check)
    inp["rrGrant"] = int(plan.rr_grant)

    if plan.sq.valid:
        inp["sq"]["valid"] = 1
        if plan.sq.data_invalid is not None:
            bits = inp["sq"]["bits"]
            bits["dataInvalid_valid"] = 1
            bits["dataInvalid_bits_first_flag"] = plan.sq.data_invalid.first_flag
            bits["dataInvalid_bits_second_flag"] = plan.sq.data_invalid.second_flag
            bits["dataInvalid_bits_value"] = plan.sq.data_invalid.value

    return inp


# ------------------------------------------------------------------ random
def random_inputs(rng: random.Random) -> dict:
    """Unconstrained port-level stress kept for the frozen random regression."""
    inp = blank_inputs()
    inp["redirect"]["valid"] = 1 if rng.random() < 0.12 else 0
    inp["redirect"]["bits"] = {name: rng.randrange(1 << REDIRECT_FIELDS[name])
                               for name in REDIRECT_FIELDS}
    inp["specialMode"] = 1 if rng.random() < 0.08 else 0
    inp["robHeadPtr"] = {"flag": rng.randrange(2), "value": rng.randrange(256),
                         "isFormer": rng.randrange(2)}
    inp["ldin"]["valid"] = 1 if rng.random() < 0.7 else 0
    inp["ldin"]["bits"] = {name: rng.randrange(1 << S0_INPUT_WIDTHS["ldin"][name])
                           for name in LDIN_FIELDS}
    inp["ldin"]["bits"]["fuOpType"] = rng.choice([0x00, 0x02, 0x04, 0x06, 0x10,
                                                  0x12, 0x14, 0x01, 0x03])
    inp["replay"]["valid"] = 1 if rng.random() < 0.3 else 0
    inp["replay"]["bits"] = {name: rng.randrange(1 << S0_INPUT_WIDTHS["replay"][name])
                             for name in REPLAY_FIELDS}
    inp["pmp"] = {"ld": rng.randrange(2), "mmio": rng.randrange(2)}
    inp["tlbHint"] = {"id": rng.randrange(16), "full": rng.randrange(2)}
    inp["tlbResp"]["valid"] = 1 if rng.random() < 0.85 else 0
    inp["tlbResp"]["bits"] = {name: rng.randrange(1 << TLB_RESP_FIELDS[name])
                              for name in TLB_RESP_FIELDS}
    inp["dcache"]["ready"] = 1 if rng.random() < 0.75 else 0
    inp["dcache"]["resp"]["bits"] = {
        "data": rng.getrandbits(128), "miss": rng.randrange(2),
        "mshr_id": rng.randrange(16), "meta_prefetch": rng.randrange(8),
        "handled": rng.randrange(2)}
    inp["dcache"]["bank"] = rng.randrange(2)
    inp["dcache"]["rr"] = rng.randrange(2)
    inp["dcache"]["mq_nack"] = rng.randrange(2)
    inp["rrGrant"] = rng.randrange(2)
    for key, fields in (("sq", SQ_FIELDS), ("sb", SB_FIELDS), ("unc", UNC_FIELDS),
                        ("mshr", MSHR_FIELDS), ("tld0", TLD_FIELDS),
                        ("tld1", TLD_FIELDS)):
        inp[key]["valid"] = 1 if rng.random() < 0.35 else 0
        bits = {name: rng.randrange(1 << fields[name]) for name in fields}
        bits.update({name: rng.randrange(256) for name in FORWARD_DATA_FIELDS})
        inp[key]["bits"] = bits
    inp["bypass1"]["valid"] = 1 if rng.random() < 0.2 else 0
    inp["bypass1"]["bits"] = {"paddr": rng.getrandbits(48)}
    inp["bypass2"]["valid"] = 1 if rng.random() < 0.2 else 0
    inp["bypass2"]["bits"] = {"data": rng.getrandbits(128),
                              "nderr": rng.randrange(2), "derr": rng.randrange(2)}
    for index in range(2):
        inp["nuke"][index]["valid"] = 1 if rng.random() < 0.35 else 0
        inp["nuke"][index]["bits"] = {name: rng.randrange(1 << NUKE_FIELDS[name])
                                      for name in NUKE_FIELDS}
    inp["rarReady"] = 1 if rng.random() < 0.7 else 0
    inp["rawReady"] = 1 if rng.random() < 0.7 else 0
    inp["rarResp"] = {"valid": 1 if rng.random() < 0.2 else 0,
                      "nuke": 1 if rng.random() < 0.5 else 0}
    inp["ldld"] = 1 if rng.random() < 0.6 else 0
    inp["trigger"]["configs"] = [
        TriggerConfig(match_type=rng.randrange(4), select=rng.randrange(2),
                      timing=rng.randrange(2),
                      action=rng.choice([0, 1, 2, 4, 15]),
                      chain=rng.randrange(2), store=rng.randrange(2),
                      tdata2=rng.getrandbits(64)) for _ in range(4)]
    inp["trigger"]["enables"] = [rng.randrange(2) for _ in range(4)]
    inp["trigger"]["debugMode"] = rng.randrange(2)
    inp["trigger"]["canRaiseBpExp"] = rng.randrange(2)
    for group in ("current", "previous"):
        for index in range(2):
            inp["std"][group][index]["valid"] = 1 if rng.random() < 0.3 else 0
            inp["std"][group][index]["bits"] = {
                "first_flag": rng.randrange(2), "second_flag": rng.randrange(2),
                "value": rng.randrange(64)}
    return inp
