"""Upstream-issue probes kept as ordinary FAIL when fixed RTL is wrong.

Every expected value comes from architectural intent or an explicit upstream
fix description, never from copying the implementation's current output.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(relative):
    spec = importlib.util.spec_from_file_location(
        "upstream_" + relative.replace("/", "_"), ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- 6742
def test_store_fault_tval_uses_the_tlb_masked_fullva(dut_factory):
    from lsuverify.new_store_unit.env import NewStoreUnitEnv
    t = load("tests/new_store_unit/test_new_store_unit.py")
    env = NewStoreUnitEnv(dut_factory("new_store_unit")); env.reset()
    tagged, masked = 0xAB00_0000_8020_0048, 0xFF00_0000_8020_0048
    response = t.good_tlb(fullva=masked, excp_0_pf_st=1)
    t.run(env, 1, t.stin(vaddr=tagged), tlb=response, context="masked fault issue")
    t.run(env, 0, tlb=response, context="masked fault c1")
    t.run(env, 0, tlb=response, context="masked fault c2")
    got = t.run(env, 0, tlb=response, context="masked fault c3")
    assert got["exceptionInfo_valid"] == 1
    assert int(env.exc["vaddr"].value) == masked, "store fault tval must be TLB-masked"


# ---------------------------------------------------------------- 6060
def test_cbo_on_pbmt_nc_is_not_a_store_access_fault(dut_factory):
    from lsuverify.new_store_unit.env import NewStoreUnitEnv
    t = load("tests/new_store_unit/test_new_store_unit.py")
    env = NewStoreUnitEnv(dut_factory("new_store_unit")); env.reset()
    line = 0x8000_2000
    values = t.stin(vaddr=line + 5, size=2, fu_extra=1)
    response = t.good_tlb(pbmt=1)  # Pbmt.NC
    t.run(env, 1, values, tlb=response, context="cbo nc issue")
    t.run(env, 0, tlb=response, context="cbo nc c1")
    t.run(env, 0, tlb=response, context="cbo nc c2")
    got = t.run(env, 0, tlb=response, context="cbo nc c3")
    assert int(env.stout["exceptionVec_7"].value) == 0, "CBO on NC must not raise AF"
    assert got["stout_valid"] == 1


# ---------------------------------------------------------------- 6154
def test_redirect_killed_s3_load_has_no_architectural_writeback(dut_factory):
    from lsuverify.load_s3.env import LoadS3Env
    t = load("tests/load_s3/test_load_s3.py")
    env = LoadS3Env(dut_factory("load_s3")); env.reset()
    got = t.beat(env, t.pipe(uop_robIdx_value=30, uop_rfWen=1), "killed s3",
                 redirect={"level": 0, "robIdx_flag": 0, "robIdx_value": 5,
                           "robIdx_isFormer": 0})
    assert got["detail"]["kill"] == 1
    assert (got["ldout_valid"], got["int_rf_valid"],
            got["lq_write_valid"]) == (0, 0, 0)


# ---------------------------------------------------------------- 5810
def test_match_invalid_writeback_clears_replay_cause(dut_factory):
    from lsuverify.load_s3.env import LoadS3Env
    t = load("tests/load_s3/test_load_s3.py")
    env = LoadS3Env(dut_factory("load_s3")); env.reset()
    got = t.beat(env, t.pipe(matchInvalid=1, cause_4=1, causeOrR=1), "match invalid cause")
    assert got["rollback_valid"] == 1
    assert got["lq_write_valid"] == 1
    causes = [i for i in range(13) if got["lq"][f"rep_info_cause_{i}"]]
    assert (got["lq"]["rep_info_need_rep"], causes) == (0, [])


# ---------------------------------------------------------------- 6158
def test_prefetch_w_requests_write_intent(dut_factory):
    from lsuverify.load_s0.env import LoadS0Env
    t = load("tests/load_s0/test_load_s0.py")
    env = LoadS0Env(dut_factory("load_s0")); env.reset()
    # At this commit prefetch.w is 0x05 (ldType 0010 / write, uopPrefetch bit 0);
    # MemoryOpConstants.M_PFW = 0x03, while the RTL hardwires M_PFR=0x02.
    got = t.run(env, t.make(ldin=t.ldin_bits(fu=0x05)), "prefetch.w issue")
    assert got["dcacheReq_valid"] == 1
    assert got["dcacheReq_cmd"] == 0x03, "prefetch.w must use M_PFW"
