"""Parent coverage recheck: never dismiss a live register as a port copy."""
import pytest

from lsuverify.new_load_unit.env import LoadParentEnv
from .test_new_load_unit import ldin, tlb_hit, idle


@pytest.fixture
def parent(dut_factory):
    env = LoadParentEnv(dut_factory("new_load_unit"))
    env.reset(); env.prime()
    return env


def clean_beat(env, off=0x80):
    for inp in (ldin(off=off, rob=80), tlb_hit(off=off), idle(), idle()):
        env.cycle(inp, "recheck clean successor")


def test_first_nc_access_cause_zero_is_captured_and_cleared(parent):
    parent.cycle(ldin(off=8, rob=50), "nc first access")
    response = tlb_hit(off=8); response["tlbResp"]["bits"]["pbmt_0"] = 1
    parent.cycle(response, "nc translation")
    parent.cycle(idle(), "nc replay request")
    raw = parent.observe_pins()
    assert raw["io_lqWrite_valid"] == 1
    assert raw["io_lqWrite_bits_rep_info_cause_0"] == 1
    # S3 payload registers capture on the next edge even when merge valid=0.
    parent.cycle(idle(), "capture cause0 into S3 head payload")
    clean_beat(parent)
    assert parent.observe_pins()["io_lqWrite_bits_rep_info_cause_0"] == 0


def test_nuke_first_cause_and_identity_return_to_zero(parent):
    issued = ldin(off=0, rob=70, storeSetHit=1, waitSqIdx_value=5)
    parent.cycle(issued, "nuke first issue")
    response = tlb_hit(off=0)
    response["nuke"][0]["valid"] = 1
    response["nuke"][0]["bits"].update(
        sqIdx_value=5, robIdx_value=3, paddr=0x2000, mask=0xFFFF, matchType=2)
    parent.cycle(response, "S1 detects nuke first")
    parent.cycle(idle(), "S3 observes nuke cause")
    assert parent.observe_pins()["io_lqWrite_bits_rep_info_cause_11"] == 1
    parent.cycle(idle(), "capture nuke payload")
    clean_beat(parent)
    assert parent.observe_pins()["io_lqWrite_bits_rep_info_cause_11"] == 0


def test_rr_bank_conflict_without_grant_falls_then_recovers(parent):
    parent.cycle(ldin(off=0, rob=90), "rr deny issue")
    response = tlb_hit(off=0)
    response["dcache"]["bank"] = 1
    response["dcache"]["rr"] = 1
    response["rrGrant"] = 0
    parent.cycle(response, "S2 candidate while beat is visible")
    assert parent.observe_pins()["io_rrBankConflictFastReplay_candidate"] == 1
    denied = idle()
    denied["dcache"]["bank"] = 1
    denied["dcache"]["rr"] = 1
    parent.cycle(denied, "capture RR conflict without grant")
    raw = parent.observe_pins()
    assert raw["io_lqWrite_valid"] == 1
    assert raw["io_lqWrite_bits_rep_info_cause_8"] == 1
    clean_beat(parent)
