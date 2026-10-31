"""Repeated real grants of an immutable Load; public slot, no model controls."""
from dataclasses import replace
import hashlib
import json

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.load_queue.types import Load
from suites.memblock.lsq.normal_replay_metadata import NormalReplayOwners, lanes
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery
from suites.memblock.lsq.replay.types import Cause, Refill, TlbHint

SEQUENCE = (
    (Cause.TLB_MISS, 0), (Cause.CACHE_MISS, 15), (Cause.CACHE_REPLAY, None),
    (Cause.BANK_CONFLICT, None), (Cause.TLB_MISS, 15), (Cause.CACHE_REPLAY, None),
    (Cause.CACHE_MISS, 0), (Cause.TLB_MISS, 0), (Cause.BANK_CONFLICT, None),
)


class CauseOwners(NormalReplayOwners):
    def __init__(self, env, dut):
        super().__init__(env, dut, "tlb-fast")
        self.attempts = []

    def make_owner(self, index):
        state = super().make(0, index)
        address = 0x10000 + index * 16 + 8
        pa = 0x80000000 + index * 4096 + address % 4096
        old = state["load"]
        req = replace(old.execution, vaddr=address, mask=0xFF00, aligned_type=3, last_beat=bool(pa & 32),
            uop=replace(old.execution.uop, operation=6), handled=False)
        state.update(instruction="ld", load=replace(old, execution=req, fullva=address,
            paddr=pa), last_tlb=0, last_mshr=0,
            expected_mshr=0, cause_index=0, initial_S3_tick=None)
        self.external = {}
        self.attempts = []
        return state

    async def execute(self, target, *, initial=False):
        """A real output grant is S0; target describes this execution's S3."""
        state = self.current
        previous = state["load"]
        req, u = previous.execution, previous.execution.uop
        assert req.last_beat == bool(previous.paddr & 32), "256-bit bus / 8 = 32B refill; S3 lastBeat must be PA[5]"
        lane = index_lane = state["index"] % 3 if initial else state["bank"]
        target_cause, identity = SEQUENCE[target] if target is not None else (None, None)
        tlb_miss = target_cause == Cause.TLB_MISS
        controls = {} if initial else {"ready" if self.leaf else "replay_ready": tuple(i == lane for i in range(3))}
        if self.wrapper:
            controls["queries"] = lanes(Query(True, req.vaddr, u.sq, 3), lane, Query())
        await self.step(**controls)
        grant = None
        if not initial:
            assert state["grant_tick"] == self.env.last_tick
            grant = dict(cause_index=state["cause_index"], cause=req.causes.bit_length() - 1,
                public_slot=state["slot"], bank=lane, first_offer_tick=state["first_offer_tick"],
                grant_tick=state["grant_tick"], payload_SHA256=state["payload_SHA256"],
                expected_MSHR_ID=state["expected_mshr"], hold_cycles=3, **state["wake_evidence"])
        await self.step(**({"translations": lanes(Translation(previous.paddr, tlb_miss), lane, Translation())} if self.wrapper else {}))
        if self.wrapper:
            prefix = f"io_forward_{lane}_s2Resp_"
            assert self.env.observed[prefix + "valid"] == int(not tlb_miss)
            if not tlb_miss:
                assert not any(self.env.observed[prefix + f"bits_forwardMask_{i}"] for i in range(16))
                assert not any(self.env.observed[prefix + "bits_" + name] for name in
                    ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"))
        data_valid = target is None or tlb_miss
        if self.leaf:
            await self.step()
        else:
            raw = RawQuery(True, u.rob, u.sq, previous.paddr, req.mask, data_valid,
                u.rvc, u.ftq, u.offset, u.checkpoint)
            rar = RarQuery(True, u.rob, u.lq, previous.paddr, data_valid)
            await self.step(raw_queries=lanes(raw, lane, RawQuery()), rar_queries=lanes(rar, lane, RarQuery()))
            assert self.env.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
            assert self.env.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
            assert not self.env.observed[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
        feedback_tick = self.env.last_tick + 2
        updated = replace(req, replay_feedback=not initial, slot=state["slot"] if not initial else 0,
            causes=0 if target is None else 1 << target_cause, need_replay=target is not None,
            handled=target_cause == Cause.CACHE_MISS,
            mshr=identity if target_cause == Cause.CACHE_MISS else 7,
            tlb_id=identity if tlb_miss else 7)
        # All original instruction/VA/ROB/LQ/FTQ/checkpoint fields are immutable.
        assert updated.uop == req.uop and updated.vaddr == req.vaddr and updated.mask == req.mask
        final = replace(previous, execution=updated, update_address=target is None)
        state["load"] = final
        if target_cause == Cause.CACHE_MISS:
            state["last_mshr"] = state["expected_mshr"] = identity
        if tlb_miss:
            state["last_tlb"] = identity
        if target is None:
            state["feedback_tick"] = feedback_tick
        else:
            state.update(cause_index=target, first_offer_tick=None, grant_tick=None)
        kwargs = dict(loads=lanes(final, index_lane, Load()))
        if not self.leaf:
            revoked = tuple(i == lane and target is not None for i in range(3))
            kwargs.update(raw_revoke_last=revoked, rar_revoke_last=revoked)
        if not initial:
            self.feedbacks += 1
        await self.step(**kwargs)
        if initial:
            state["initial_S3_tick"] = feedback_tick
        if grant is not None:
            grant.update(feedback_tick=feedback_tick, next_cause=target_cause,
                feedback_need_replay=target is not None, feedback_updateAddrValid=target is None,
                feedback_handledByMSHR=updated.handled, feedback_MSHR_pin=updated.mshr,
                feedback_last_beat=bool(updated.last_beat),
                retained_MSHR_ID_after_feedback=state["expected_mshr"])
            self.attempts.append(grant)
        if target is None:
            assert not self.env.observed["io_replayAllocate"]
            if self.leaf:
                state["local_complete"] = True
                state["release_tick"] = self.env.last_tick
                self.completed += 1
        else:
            assert self.env.observed["io_replayAllocate"] and not state["local_complete"]

    async def blocked(self, cycles=4):
        for _ in range(cycles):
            await self.step()
            assert self.env.observed["io_replayAllocate"] and not self.current["local_complete"]
            assert not any(self.env.observed[f"io_replay_{i}_valid"] for i in range(3))

    async def pulse(self, kind, identity):
        job = self.external.pop((kind, identity))
        assert 0 <= identity < 16
        if kind == "TLB":
            await self.step(fast_tlb=TlbHint(True, identity))
        else:
            channel = (self.current["index"] + self.current["cause_index"]) % 2
            await self.step(refills=lanes(Refill(True, identity), channel, Refill(), 2))
        return self.env.last_tick, job["owner"]

    async def wait_offer(self):
        state = self.current
        cause, identity = SEQUENCE[state["cause_index"]]
        evidence = dict(dependency_ID=identity, wrong_channel_tick=None, wrong_ID_tick=None,
            matched_tick=None, channel=(state["index"] + state["cause_index"]) % 2,
            initial_S3_or_previous_feedback_tick=self.env.last_tick)
        if cause in (Cause.TLB_MISS, Cause.CACHE_MISS):
            kind = "TLB" if cause == Cause.TLB_MISS else "MSHR"
            other = "MSHR" if kind == "TLB" else "TLB"
            other_id = state["last_mshr"] if other == "MSHR" else state["last_tlb"]
            decoy = (identity + 1) % 16
            address = state["load"].execution.vaddr
            self.external = {(kind, identity): dict(owner=state["uid"], address=address),
                (kind, decoy): dict(owner="same-channel-decoy", address=address ^ (1 << 20)),
                (other, other_id): dict(owner="old-ID-other-active-request", address=address ^ (1 << 21))}
            assert len(self.external) == 3
            await self.blocked()
            tick, who = await self.pulse(other, other_id)
            assert who == "old-ID-other-active-request"
            evidence["wrong_channel_tick"] = tick
            await self.blocked()
            tick, who = await self.pulse(kind, decoy)
            assert who == "same-channel-decoy"
            evidence["wrong_ID_tick"] = tick
            await self.blocked()
            tick, who = await self.pulse(kind, identity)
            assert who == state["uid"] and not self.external
            evidence["matched_tick"] = tick
            latency = 0 if kind == "TLB" else 4
        else:
            assert cause in (Cause.CACHE_REPLAY, Cause.BANK_CONFLICT)
            latency = 2
            tick = self.env.last_tick
        for _ in range(40):
            if state["first_offer_tick"] is not None:
                break
            await self.step()
        assert state["first_offer_tick"] == tick + latency, (
            "reReplay exact next valid", self.dut, cause, state["uid"], state["first_offer_tick"], tick, latency)
        snapshot = self.offer(self.env.observed)
        state["bank"], slot = snapshot[:2]
        if state["slot"] is None:
            state["slot"] = slot
        else:
            assert state["slot"] == slot
        for _ in range(3):
            await self.step()
            assert self.offer(self.env.observed) == snapshot and self.env.observed["io_replayAllocate"]
        state["wake_evidence"] = evidence

    async def owner(self, index):
        self.current = state = self.make_owner(index)
        await self.dispatch()
        await self.execute(0, initial=True)
        for phase in range(len(SEQUENCE)):
            assert state["cause_index"] == phase
            await self.wait_offer()
            await self.execute(phase + 1 if phase + 1 < len(SEQUENCE) else None)
        assert len(self.attempts) == 9 and len({a["public_slot"] for a in self.attempts}) == 1
        assert [a["cause"] for a in self.attempts] == [int(cause) for cause, _ in SEQUENCE]
        await self.finish()
        req = state["load"].execution
        self.rows.append(dict(uid=state["uid"], public_slot=state["slot"], ROB_ordinal=self.rob - 1,
            LQ_position=self.position - 1, vaddr=req.vaddr, mask=req.mask, operation=req.uop.operation,
            PA=state["load"].paddr, initial_S3_last_beat=bool(req.last_beat),
            FTQ_value=req.uop.ftq.value, FTQ_end_offset=req.uop.offset, checkpoint=req.uop.checkpoint,
            initial_S3_tick=state["initial_S3_tick"], actual_release_tick=state["release_tick"],
            grants=self.attempts, original_UID_completion=True))
        self.current = None
        return state["slot"]


async def trace(env, output, dut, *, count=120):
    actor = CauseOwners(env, dut)
    passed, error = False, None
    try:
        assert count in (8, 120)
        slots = [await actor.owner(index) for index in range(count)]
        assert len(set(slots)) == count
        if count == 120:
            assert set(slots) == set(range(120))
        assert actor.completed == count and actor.grants == actor.feedbacks == 9 * count
        if actor.leaf:
            env.coverage.sample(("LRQ-OWNER.rereplay", "LRQ-OWNER.changed_cause", "LRQ-HOLD.stable"), env.last_tick, checked=True)
        elif actor.wrapper:
            env.prove("LSQ-REPLAY.tlb", "LSQ-REPLAY.refill")
        else:
            env.prove("LQ-REPLAY.metadata", "LQ-HINT.fast_tlb", "LQ-HINT.refill")
        passed = True
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        output.write_text(json.dumps(dict(format="lsq-Replay-cause-lifetime-witness-v1", dut=dut, passed=passed,
            error=error, count=count, rows=actor.rows, completed=actor.completed, actual_grants=actor.grants,
            actual_feedbacks=actor.feedbacks, checked_lifetimes_SHA256=actor.digest.hexdigest(),
            reset_between_owners=False, peak_live_Loads=1, native_upstream_allocator_proven=False,
            scope="Immutable normal scalar original UID; nine real Replay grants/eight rereplays/final feedback. Leaf proves only Replay free; parents wait real LQ credit. No native TLB invalidation/Cache pipeline or data-return validation."), indent=2) + "\n")
