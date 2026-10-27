"""Real STA is shared with RAW; public rollback drives real shared recovery."""
from dataclasses import replace

import pytest

from lsqverify.load_queue.types import Load
from lsqverify.lsq_wrapper.types import Address
from lsqverify.rar.types import Query as RarQuery, Release
from lsqverify.raw.types import Query as RawQuery
from lsqverify.replay.types import Cause
from lsqverify.vlq.types import QueuePtr, RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load
from .test_forward_memory import check_bytes


def raw_query(load):
    u = load.execution.uop
    return RawQuery(True, u.rob, u.sq, load.paddr, load.execution.mask, True, u.rvc, u.ftq, u.offset, u.checkpoint)


def expect_rollback(env, lane, load, address):
    p, u = f"io_nuke_rollback_{lane}_", load.execution.uop
    env.expect({p + "valid": 1, p + "bits_robIdx_flag": int(u.rob.flag), p + "bits_robIdx_value": u.rob.value,
                p + "bits_robIdx_isFormer": int(u.rob.former), p + "bits_ftqIdx_flag": int(u.ftq.flag),
                p + "bits_ftqIdx_value": u.ftq.value, p + "bits_ftqOffset": u.offset, p + "bits_isRVC": int(u.rvc),
                p + "bits_debug_runahead_checkpoint_id": u.checkpoint, p + "bits_stFtqIdx_flag": int(address.ftq.flag),
                p + "bits_stFtqIdx_value": address.ftq.value, p + "bits_stFtqOffset": address.ftq_offset,
                p + "bits_stIsRVC": int(address.rvc)}, "RAW keeps original Load and actual shared STA recovery identities")


@pytest.mark.parametrize("variant", ("dual", "mask", "age", "miss", "revoke_one", "revoke_two"))
async def test_actual_two_sta_raw_conflict_negatives_and_recovered_same_lq_owners(lsq, variant):
    trace = MemoryOwners(lsq)
    older_load = variant == "age"
    stores = [StoreOwner(pos, RobPtr.encode(12 + pos if older_load else 10 + pos),
                         0x11000 + pos * 4096 + (8 if variant == "mask" else 0),
                         0xA011000 + pos * 4096 + (8 if variant == "mask" else 0),
                         value=0x1234567812345600 + pos) for pos in range(2)]
    loads = [cached_load(pos, 10 + pos if older_load else 12 + pos, 0 if older_load else 2,
                         0x11000 + pos * 4096, 0xA011000 + pos * 4096) for pos in range(2)]
    await trace.dispatch(stores, loads)
    await trace.cycle(data=tuple(s.data() for s in stores))
    first_lane = ("dual", "mask", "age", "miss", "revoke_one", "revoke_two").index(variant) % 3
    queries = [RawQuery()] * 3
    queries[first_lane], queries[(first_lane + 1) % 3] = raw_query(loads[0]), raw_query(loads[1])
    await trace.cycle(raw_queries=tuple(queries))
    assert all(lsq.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"] for lane in (first_lane, (first_lane + 1) % 3))
    if variant.startswith("revoke"):
        if variant == "revoke_two":
            await trace.cycle()
        await trace.cycle(**{"raw_revoke_last" if variant == "revoke_one" else "raw_revoke_older": tuple(q.valid for q in queries)})
    await trace.cycle()
    addresses = tuple(s.address(miss=variant == "miss") for s in stores)
    lsq.reach("LSQ-RAW.dual" if variant == "dual" else "LSQ-RAW.mask_negative" if variant == "mask" else
              "LSQ-RAW.age_negative" if variant == "age" else "LSQ-RAW.tlb_miss" if variant == "miss" else "LSQ-RAW.revoke")
    await trace.cycle(addresses=addresses)
    await trace.idle(2)
    positive = variant == "dual"
    lsq.expect({f"io_nuke_rollback_{lane}_valid": int(positive) for lane in range(2)}, "two actual STA nuke only true younger-byte conflicts")
    if variant == "miss":
        # The first STA is a real TLB miss, not a fake RAW-only input. Retry
        # BOTH real stores; now their actual successful addresses must nuke.
        addresses = tuple(s.address() for s in stores)
        await trace.cycle(addresses=addresses)
        await trace.idle(2)
        positive = True
    if positive:
        for lane in range(2):
            expect_rollback(lsq, lane, loads[lane], addresses[lane])
        u, a = loads[0].execution.uop, addresses[0]
        lsq.expect({"io_mdpTrain_valid": 1, "io_mdpTrain_bits_ftqIdx_value": u.ftq.value,
                    "io_mdpTrain_bits_ftqOffset": u.offset, "io_mdpTrain_bits_isRVC": int(u.rvc),
                    "io_mdpTrain_bits_stFtqIdx_value": a.ftq.value, "io_mdpTrain_bits_stFtqOffset": a.ftq_offset,
                    "io_mdpTrain_bits_stIsRVC": int(a.rvc)}, "MDP training belongs to oldest original load/store pair")
        # Choose the real externally observed oldest rollback, not a private
        # model candidate. Redirect applies simultaneously to both queues.
        actual = lsq.observed
        cutoff = RobPtr(bool(actual["io_nuke_rollback_0_bits_robIdx_flag"]), actual["io_nuke_rollback_0_bits_robIdx_value"],
                        bool(actual["io_nuke_rollback_0_bits_robIdx_isFormer"]))
        recovered = await trace.recover_load_suffix(cutoff)
        assert recovered == QueuePtr()
        new = [cached_load(pos, 14 + pos, 2, load.execution.vaddr, load.paddr) for pos, load in enumerate(loads)]
        await trace.dispatch(loads=new)
        for pos, load in enumerate(new):
            await trace.forward(load, pos)
            check_bytes(lsq, load, stores, pos)
    await trace.finish()
    names = (["LSQ-RAW.conflict", "LSQ-RAW.dual", "LSQ-RAW.train", "LSQ-RECOVER.partial", "LSQ-RECOVER.reuse"] if positive else [])
    names += {"mask": ["LSQ-RAW.mask_negative"], "age": ["LSQ-RAW.age_negative"], "miss": ["LSQ-RAW.tlb_miss"],
              "revoke_one": ["LSQ-RAW.revoke"], "revoke_two": ["LSQ-RAW.revoke"]}.get(variant, [])
    lsq.prove(*names)


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("window", ("current", "previous", "none"))
async def test_real_cached_rar_release_window_replay_feedback_and_vlq_completion(lsq, lane, window):
    trace = MemoryOwners(lsq)
    old = cached_load(0, 10, 0, 0x24040, 0xC020040)
    young = cached_load(1, 11, 0, 0x35040, 0xC020040)
    await trace.dispatch(loads=[old, young])
    release = Release(True, young.paddr)
    if window == "previous":
        await trace.cycle(release=release)
    queries = [RarQuery()] * 3
    queries[lane] = RarQuery(True, young.execution.uop.rob, young.execution.uop.lq, young.paddr, True)
    lsq.reach("LSQ-RAR.previous_release" if window == "previous" else "LSQ-RAR.current_release")
    await trace.cycle(rar_queries=tuple(queries), release=release if window == "current" else Release())
    assert lsq.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
    probe_lane = (lane + 1) % 3
    probe = [RarQuery()] * 3
    probe[probe_lane] = RarQuery(True, old.execution.uop.rob, old.execution.uop.lq, old.paddr)
    await trace.cycle(rar_queries=tuple(probe))
    lsq.expect({f"io_ldu_rarNukeQuery_{probe_lane}_resp_valid": 1,
                f"io_ldu_rarNukeQuery_{probe_lane}_resp_bits_nuke": int(window != "none")},
               "original older Load sees only released younger same-line reader")
    await trace.execute([young])
    if window != "none":
        replay = replace(old, execution=replace(old.execution, need_replay=True, causes=1 << Cause.VIOLATION))
        await trace.execute([replay])
        await trace.replay_complete(replay)
    await trace.finish()
    if window != "none":
        lsq.prove("LSQ-RAR.previous_release" if window == "previous" else "LSQ-RAR.current_release")


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("age", (1, 2))
async def test_real_cached_rar_revoke_exact_query_history_before_older_load_probe(lsq, lane, age):
    trace = MemoryOwners(lsq)
    old = cached_load(0, 10, 0, 0x24040, 0xC020040)
    young = cached_load(1, 11, 0, 0x35040, 0xC020040)
    await trace.dispatch(loads=[old, young])
    queries = [RarQuery()] * 3
    queries[lane] = RarQuery(True, young.execution.uop.rob, young.execution.uop.lq, young.paddr, True)
    await trace.cycle(rar_queries=tuple(queries), release=Release(True, young.paddr))
    if age == 2:
        await trace.cycle()
    await trace.cycle(**{"rar_revoke_last" if age == 1 else "rar_revoke_older": tuple(n == lane for n in range(3))})
    probe_lane, probes = (lane + 1) % 3, [RarQuery()] * 3
    probes[probe_lane] = RarQuery(True, old.execution.uop.rob, old.execution.uop.lq, old.paddr)
    await trace.cycle(rar_queries=tuple(probes))
    lsq.expect({f"io_ldu_rarNukeQuery_{probe_lane}_resp_valid": 1, f"io_ldu_rarNukeQuery_{probe_lane}_resp_bits_nuke": 0},
               "revoked original reader cannot survive as a ghost release conflict")
    await trace.finish()
    lsq.prove("LSQ-RAR.revoke")
