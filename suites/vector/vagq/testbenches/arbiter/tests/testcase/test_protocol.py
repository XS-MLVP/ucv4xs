"""VAGQArbiter real-DUT scenarios with semantic request/payload checking."""

from suites.vector.vagq.testbenches.arbiter.env.native import native_request
from suites.vector.vagq.testbenches.arbiter.transactions import Beat
from suites.vector.vagq.testbenches.arbiter.transactions import LsuReq
from suites.vector.vagq.testbenches.arbiter.transactions import NativeReq
from suites.vector.vagq.testbenches.arbiter.transactions import StoreDataReq


def bypass(kind, *, valid=False, rob=0, flag=0, seed=0):
    """Choose only channel/validity/ROB identity/pattern seed.

    Physical field enumeration, width masking and ROB leaf encoding belong to
    the arbiter adapter, not this functional scenario.
    """
    return native_request(kind, valid=valid, rob_flag=flag,
                          rob_value=rob, pattern_seed=seed)


def active(index=0, *, is_load=True, rob=20, rob_flag=0, lq=10, lq_flag=0,
           sq=10, sq_first=0, sq_second=0, pc=0x4000, ftq=0x20,
           ftq_flag=0, ftq_offset=0x10, elem=8, byte=0, vaddr=0x100000,
           pdest=30, entry=None, data_size=2, data_mask=0x00ff):
    return LsuReq(
        valid=True,
        entry_idx=index if entry is None else entry,
        rob_flag=rob_flag,
        rob_value=rob,
        is_load=is_load,
        lq_flag=lq_flag,
        lq_value=lq,
        sq_first_flag=sq_first,
        sq_second_flag=sq_second,
        sq_value=sq,
        elem_idx=elem,
        data_size=data_size,
        data_mask=data_mask,
        pc=pc,
        ftq_flag=ftq_flag,
        ftq_value=ftq,
        ftq_offset=ftq_offset,
        byte_offset=byte,
        vaddr=vaddr,
        pdest=pdest,
    )


def std(valid=True, *, slot=0, data=0x1122):
    return StoreDataReq(valid, slot & 1, (slot >> 1) & 1, slot + 3, data + slot)


def scenario(**changes):
    defaults = dict(
        vagq_lsu=(LsuReq(), LsuReq(), LsuReq()),
        vagq_store_data=(StoreDataReq(), StoreDataReq()),
        issue_lda=(NativeReq(), NativeReq(), NativeReq()),
        issue_sta=(NativeReq(), NativeReq()),
        ldu_ready=(True, True, True),
        sta_ready=(True, True),
        std_busy=(False, False),
    )
    defaults.update(changes)
    return Beat(**defaults)


def test_arbiter_contract(arbiter_env):
    env = arbiter_env

    def check(beat):
        env.cycle(beat)

    # Idle and invalid native payload exercise no-grant, mixed-ready and the
    # explicit invalid-output payload boundary.
    check(scenario(ldu_ready=(True, True, True), sta_ready=(True, True)))
    check(scenario(
        issue_lda=(bypass('load', seed=3), NativeReq(), NativeReq()),
        ldu_ready=(True, False, True),
        sta_ready=(True, False),
    ))
    check(scenario(ldu_ready=(False, False, False), sta_ready=(True, True)))
    check(scenario(ldu_ready=(True, True, True), sta_ready=(False, False)))

    # Three load grants: distinct LQ order and lane reservation are observable
    # even when no native issue request participates.
    check(scenario(
        vagq_lsu=(
            active(0, rob=50, lq=20),
            active(1, rob=50, lq=5),
            active(2, rob=50, lq=5),
        ),
    ))

    # Two store grants and two independent STD requests with no busy.
    check(scenario(
        vagq_lsu=(
            active(0, is_load=False, rob=60, sq=20),
            active(1, is_load=False, rob=60, sq=5),
            LsuReq(),
        ),
        vagq_store_data=(std(slot=0), std(slot=1)),
    ))

    # Load/store mixed source: both families may issue in the same cycle and
    # metadata remains valid on both routes.
    check(scenario(
        vagq_lsu=(
            active(0, is_load=True, rob=70),
            active(1, is_load=False, rob=71),
            LsuReq(),
        ),
    ))

    # Native-only output preserves every native leaf and leaves issue ready
    # available when its target is ready.
    check(scenario(
        issue_lda=(bypass('load', valid=True, rob=8, seed=11), NativeReq(), NativeReq()),
        issue_sta=(bypass('store', valid=True, rob=9, seed=13), NativeReq()),
    ))

    # A younger native load is displaced by an older VAGQ request; target
    # backpressure suppresses fire/ready but not valid or payload selection.
    check(scenario(
        vagq_lsu=(active(0, rob=10, lq=4), LsuReq(), LsuReq()),
        issue_lda=(bypass('load', valid=True, rob=100, seed=17), NativeReq(), NativeReq()),
        ldu_ready=(False, True, True),
    ))

    # Older native requests block every VAGQ load lane; the VAGQ candidates are
    # still present and are not falsely acknowledged by ready.
    check(scenario(
        vagq_lsu=(active(0, rob=30), active(1, rob=31), active(2, rob=32)),
        issue_lda=(
            bypass('load', valid=True, rob=5, seed=20),
            bypass('load', valid=True, rob=6, seed=21),
            bypass('load', valid=True, rob=7, seed=22),
        ),
    ))

    # Corresponding store priority and STA backpressure.
    check(scenario(
        vagq_lsu=(active(0, is_load=False, rob=40), LsuReq(), LsuReq()),
        issue_sta=(bypass('store', valid=True, rob=2, seed=25), NativeReq()),
        sta_ready=(False, True),
    ))
    check(scenario(
        vagq_lsu=(active(0, is_load=False, rob=41), active(1, is_load=False, rob=42), LsuReq()),
        issue_sta=(bypass('store', valid=True, rob=100, seed=26), NativeReq()),
        sta_ready=(True, False),
    ))
    check(scenario(
        vagq_lsu=(active(0, is_load=False, rob=43), active(1, is_load=False, rob=44), LsuReq()),
        issue_sta=(
            bypass('store', valid=True, rob=100, seed=27),
            bypass('store', valid=True, rob=1, seed=28),
        ),
    ))

    # Same-pointer lane tie, ROB order and wrapped circular pointer order.
    check(scenario(
        vagq_lsu=(active(0, rob=80, lq=9), active(1, rob=80, lq=9), LsuReq()),
    ))
    check(scenario(
        vagq_lsu=(active(0, rob=90, lq=12), active(1, rob=91, lq=2), LsuReq()),
    ))
    check(scenario(
        vagq_lsu=(
            active(0, rob=1, rob_flag=1, lq=1),
            active(1, rob=0, rob_flag=0, lq=2),
            LsuReq(),
        ),
    ))

    # STD busy is per lane; cover slot0-only and slot1-only available paths.
    check(scenario(
        vagq_store_data=(std(slot=0), std(slot=1)),
        std_busy=(True, False),
    ))
    check(scenario(
        vagq_store_data=(StoreDataReq(), std(slot=1)),
        std_busy=(False, False),
    ))
    check(scenario(
        vagq_store_data=(std(slot=0), StoreDataReq()),
        std_busy=(False, False),
    ))

    env.assert_coverage(100)
    env.assert_clean()
