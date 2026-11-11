"""Parent coverage recheck: never dismiss a live register as a port copy.

These scenarios read the same immutable stage snapshot as every other test and
check that S3 payload registers keep the last captured replay identity/cause,
then clear on a clean successor beat.
"""

import pytest

from suites.memblock.lsu.testbenches.new_load_unit.env import LoadParentEnv
from suites.memblock.lsu.testbenches.new_load_unit.transactions import CycleInput
from suites.memblock.lsu.testbenches.new_load_unit.transactions import LoadIssue
from suites.memblock.lsu.testbenches.new_load_unit.transactions import NukeQuery
from suites.memblock.lsu.testbenches.new_load_unit.transactions import ReplayCause
from suites.memblock.lsu.testbenches.new_load_unit.transactions import RobTag
from suites.memblock.lsu.testbenches.new_load_unit.transactions import SqTag
from suites.memblock.lsu.testbenches.new_load_unit.transactions import Translation


@pytest.fixture
def parent(dut_factory):
    env = LoadParentEnv(dut_factory("new_load_unit"))
    env.reset(); env.prime()
    return env


def issued(off=0, rob=0, **options):
    return CycleInput.idle().issue(LoadIssue(
        address=0x8000_0000 + off, rob=RobTag(value=rob), **options))


def translated(off=0, pbmt=0, **options):
    return CycleInput.idle().translated(Translation.hit(
        paddr=0x2000 + off, fullva=0x8000_0000 + off, pbmt=pbmt, **options))


def clean_beat(env, off=0x80):
    for plan in (issued(off=off, rob=80), translated(off=off),
                 CycleInput.idle(), CycleInput.idle()):
        env.cycle(plan, "recheck clean successor")


def test_first_nc_access_cause_zero_is_captured_and_cleared(parent):
    parent.cycle(issued(off=8, rob=50), "nc first access")
    parent.cycle(translated(off=8, pbmt=1), "nc translation")
    parent.cycle(CycleInput.idle(), "nc replay request")
    raw = parent.observe()
    assert raw.s3.lq.valid == 1
    assert raw.s3.lq.replay_cause(ReplayCause.UNCACHE_FIRST_ACCESS)
    # S3 payload registers capture on the next edge even when merge valid=0.
    parent.cycle(CycleInput.idle(), "capture cause0 into S3 head payload")
    clean_beat(parent)
    assert not parent.observe().s3.lq.replay_cause(
        ReplayCause.UNCACHE_FIRST_ACCESS)


def test_nuke_first_cause_and_identity_return_to_zero(parent):
    issued_inp = issued(off=0, rob=70, store_set_hit=True,
                        wait_sq=SqTag(value=5))
    parent.cycle(issued_inp, "nuke first issue")
    response = translated(off=0).with_nuke(0, NukeQuery(
        valid=True, rob=RobTag(value=3), sq=SqTag(value=5), paddr=0x2000,
        mask=0xFFFF, match_type=2))
    parent.cycle(response, "S1 detects nuke first")
    parent.cycle(CycleInput.idle(), "S3 observes nuke cause")
    assert parent.observe().s3.lq.replay_cause(ReplayCause.NUKE)
    parent.cycle(CycleInput.idle(), "capture nuke payload")
    clean_beat(parent)
    assert not parent.observe().s3.lq.replay_cause(ReplayCause.NUKE)


def test_rr_bank_conflict_without_grant_falls_then_recovers(parent):
    parent.cycle(issued(off=0, rob=90), "rr deny issue")
    response = translated(off=0).with_dcache(
        bank_conflict=True, rr_conflict=True)
    parent.cycle(response, "S2 candidate while beat is visible")
    assert parent.observe().s2.rr_bank_conflict_candidate == 1
    denied = CycleInput.idle().with_dcache(bank_conflict=True, rr_conflict=True)
    parent.cycle(denied, "capture RR conflict without grant")
    raw = parent.observe()
    assert raw.s3.lq.valid == 1
    assert raw.s3.lq.replay_cause(ReplayCause.BANK_CONFLICT)
    clean_beat(parent)
