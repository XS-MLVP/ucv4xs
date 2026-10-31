"""Original normal scalar owners; only public outputs select replay slots."""
from dataclasses import fields, replace
import hashlib
import json

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.load_queue.types import Inputs as LqInputs, Load
from suites.memblock.lsq.lsq_wrapper.types import Dispatch as WrapperDispatch, Inputs as WrapperInputs
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import FtqPtr, Query as RawQuery, SqPtr
from suites.memblock.lsq.replay.types import Cause, Enqueue, Inputs as ReplayInputs, L2Hint, Refill, TlbHint, Uop
from suites.memblock.lsq.vlq.types import Dispatch, QueuePtr, RobPtr

PATHS = ("refill", "l2", "tlb-fast", "tlb-slow")
ALL64 = (1 << 64) - 1


def va50(low48):
    assert 0 <= low48 < 1 << 48
    return low48 | (3 << 48 if low48 >> 47 else 0)


# Each slot receives all seven normal integer opcode classes. Known zero/all1
# then zero address writes force both directions without startup randomness.
PROFILES = (
    ("lb", 0, 0),
    ("lbu", 16, va50((1 << 48) - 1)),
    ("lh", 2, va50(0x555555555554)),
    ("lhu", 18, va50(0xAAAAAAAAAAAA)),
    ("lw", 4, va50(0x333333333330)),
    ("lwu", 20, va50(0xCCCCCCCCCCFC)),
    ("ld", 6, va50(0x123456780008)),
    ("lb", 0, 0),
)


def lanes(value, lane, empty, count=3):
    return tuple(value if index == lane else empty for index in range(count))


def canonical64(address):
    assert address >> 48 == (3 if address >> 47 & 1 else 0)
    return address | (((1 << 14) - 1) << 50 if address >> 49 else 0)


def expected_public(req, mshr):
    """Independent instruction/UID projection, not ReplayModel.payload()."""
    u = req.uop
    size = (u.operation >> 1) & 7
    assert size < 4 and req.vaddr % (1 << size) == 0
    mask = ((1 << (1 << size)) - 1) << (req.vaddr % 16)
    assert mask == req.mask and mask < 1 << 16
    result = dict(
        entrance=2 if req.causes == 1 << Cause.CACHE_MISS else 8,
        accessType_instrType=1, vaddr=req.vaddr, fullva=req.vaddr,
        size=size, mask=mask, mshrId=mshr,
        forwardDChannel=int(req.causes == 1 << Cause.CACHE_MISS), uncacheReplay=0, ncReplay=0,
        uop_isRVC=0, uop_ftqPtr_flag=int(u.ftq.flag), uop_ftqPtr_value=u.ftq.value,
        uop_ftqOffset=u.offset, uop_fuOpType=u.operation, uop_rfWen=1,
        uop_fpWen=0, uop_vecWen=0, uop_v0Wen=0, uop_pdest=u.destination,
        uop_robIdx_flag=int(u.rob.flag), uop_robIdx_value=u.rob.value, uop_robIdx_isFormer=1,
        uop_perfDebugInfo_runahead_checkpoint_id=u.checkpoint,
        uop_storeSetHit=0, uop_loadWaitBit=0, uop_loadWaitStrict=0,
        uop_waitSqIdx_first_flag=0, uop_waitSqIdx_second_flag=0, uop_waitSqIdx_value=0,
        uop_lqIdx_flag=int(u.lq.flag), uop_lqIdx_value=u.lq.value,
        uop_sqIdx_first_flag=0, uop_sqIdx_second_flag=0, uop_sqIdx_value=0,
    )
    result.update({f"uop_exceptionVec_{bit}": 0 for bit in (23, 19, 15, 7, 6)})
    return result


class NormalReplayOwners:
    def __init__(self, env, dut, path):
        assert path in PATHS and dut in ("load_queue_replay", "load_queue", "lsq_wrapper")
        self.env, self.dut, self.path = env, dut, path
        self.leaf, self.wrapper = dut == "load_queue_replay", dut == "lsq_wrapper"
        self.rob = self.position = self.completed = self.grants = self.feedbacks = 0
        self.previous_pending_next = None
        self.current = None
        self.rows = []
        self.digest = hashlib.sha256()
        self.deq = "io_toLsqEnqCtrl_lqDeq_" if self.wrapper else "io_lqDeq_"
        self.external = {}

    def offer(self, pins):
        visible = [bank for bank in range(3) if pins[f"io_replay_{bank}_valid"]]
        if not visible:
            return None
        state = self.current
        assert state is not None and len(visible) == 1, ("unexpected replay", visible)
        bank = visible[0]
        prefix = f"io_replay_{bank}_bits_"
        slot = pins[prefix + "replayQueueIdx"]
        assert 0 <= slot < 120 and slot % 3 == bank
        wanted = expected_public(state["load"].execution, state["expected_mshr"])
        actual = {name: pins[prefix + name] for name in wanted}
        assert actual == wanted, ("normal original replay metadata", state["uid"], actual, wanted)
        if state["slot"] is not None:
            assert state["slot"] == slot
        return bank, slot, actual

    async def step(self, **kwargs):
        common = dict(pending=RobPtr.encode(self.rob), pending_next=RobPtr.encode(self.rob))
        if self.leaf:
            leaf_common = dict(head=RobPtr.encode(self.rob), writeback=QueuePtr.encode(self.position), sq_empty=True)
            if "loads" in kwargs:
                kwargs["enqueues"] = tuple(load.execution for load in kwargs.pop("loads"))
            packet = ReplayInputs(**dict(leaf_common, **kwargs))
            before = self.env.observed
            await self.env.cycle(packet.enqueues, **{f.name: getattr(packet, f.name) for f in fields(packet) if f.name != "enqueues"})
            ready = packet.ready
        else:
            cls = WrapperInputs if self.wrapper else LqInputs
            if not self.wrapper:
                common["sq_empty"] = True
            packet = cls(**dict(common, **kwargs))
            if self.previous_pending_next is not None:
                assert packet.pending == self.previous_pending_next
            p = packet.pending.value + 160 * int(packet.pending.flag)
            n = packet.pending_next.value + 160 * int(packet.pending_next.flag)
            delta = (n - p) % 320
            assert packet.pending.former and packet.pending_next.former and delta <= 1 and p % 8 + delta <= 8
            self.previous_pending_next = packet.pending_next
            await self.env.cycle(packet)
            before = self.env.pre_observed
            ready = packet.replay_ready
        after, tick = self.env.observed, self.env.last_tick
        state = self.current
        if state is not None:
            for bank, take in enumerate(ready):
                if before[f"io_replay_{bank}_valid"] and take:
                    offered = self.offer(before)
                    assert offered[0] == bank and state["grant_tick"] is None
                    state["bank"], state["slot"] = bank, offered[1]
                    state["grant_tick"] = tick
                    state["payload_SHA256"] = hashlib.sha256(json.dumps(offered[2], sort_keys=True).encode()).hexdigest()
                    self.grants += 1
        offered = self.offer(after)
        if offered is not None and state["first_offer_tick"] is None:
            state["first_offer_tick"] = tick
        if not self.leaf:
            assert not after["io_uncache_req_valid"]
            assert not any(after[f"io_nuke_rollback_{lane}_valid"] for lane in range(2))
            if self.wrapper:
                assert after["io_sqEmpty"] and not after["io_toLsqEnqCtrl_sqDeq_valid"]
                assert not any(after[f"io_sbuffer_req_{lane}_valid"] for lane in range(2))
            if after[self.deq + "valid"]:
                assert state is not None and state["feedback_tick"] is not None and not state["local_complete"]
                assert after[self.deq + "bits"] == 1 and state["feedback_tick"] + 4 <= tick
                assert state["position"] == self.position
                state["local_complete"] = True
                state["release_tick"] = tick
                self.completed += 1
        self.digest.update(json.dumps([tick, self.rob, self.position, self.grants, self.feedbacks, self.completed,
            [int(after[f"io_replay_{bank}_valid"]) for bank in range(3)]]).encode() + b"\n")
        return after

    async def idle(self, cycles=1):
        for _ in range(cycles):
            await self.step()

    def make(self, phase, index):
        name, operation, address = PROFILES[phase]
        size = operation >> 1 & 7
        assert address % (1 << size) == 0
        mask = ((1 << (1 << size)) - 1) << (address % 16)
        pa = 0x80000000 + self.position * 4096 + address % 4096
        identity = 0 if phase in (0, 7) else 15 if phase == 1 else (index + phase) % 16
        checkpoint = (self.position + 1) * 0x9E3779B97F4A7C15 & ALL64
        u = Uop(rob=RobPtr.encode(self.rob), lq=QueuePtr.encode(self.position), sq=SqPtr(),
            ftq=FtqPtr(bool(self.rob // 1024 % 2), self.rob // 16 % 64), offset=2 * (self.rob % 16) + 1,
            operation=operation, checkpoint=checkpoint, destination=1 + self.position % 31)
        translation = self.path.startswith("tlb")
        req = Enqueue(True, u, address, mask, aligned_type=size, handled=not translation,
            mshr=0 if translation else identity, last_beat=bool(pa & 64), need_replay=True,
            causes=1 << (Cause.TLB_MISS if translation else Cause.CACHE_MISS), tlb_id=identity)
        load = Load(req, fullva=canonical64(address), paddr=pa, update_address=False)
        state = dict(uid=self.position + 1, position=self.position, phase=phase, index=index,
            instruction=name, load=load, identity=identity, decoy=(identity + 1) % 16,
            expected_mshr=0 if translation else identity, slot=None, grant_tick=None,
            first_offer_tick=None, feedback_tick=None, local_complete=False)
        self.external = {identity: dict(owner=state["uid"], address=address),
            state["decoy"]: dict(owner="external-decoy", address=address ^ (1 << 20))}
        assert len(self.external) == 2 and all(0 <= ident < 16 for ident in self.external)
        return state

    async def dispatch(self):
        if self.leaf:
            return
        u = self.current["load"].execution.uop
        request = WrapperDispatch(True, 1, u.rob, 1, load_start=u.lq) if self.wrapper else Dispatch(True, u.rob, u.lq, 1)
        empty = WrapperDispatch() if self.wrapper else Dispatch()
        await self.step(dispatch=(request,) + (empty,) * 7)

    async def pipeline(self, *, replay=False):
        state = self.current
        load = state["load"]
        req, u = load.execution, load.execution.uop
        lane = state["bank"] if replay else (state["index"] + state["phase"]) % 3
        miss_tlb = not replay and self.path.startswith("tlb")
        if replay:
            # The actual output handshake and S0 Forward query are the same
            # edge and the same original output bank/LDU, not a new issue.
            kwargs = {"ready" if self.leaf else "replay_ready": tuple(bank == lane for bank in range(3))}
        else:
            kwargs = {}
        if self.wrapper:
            kwargs["queries"] = lanes(Query(True, req.vaddr, u.sq, (u.operation >> 1) & 7), lane, Query())
        await self.step(**kwargs)  # S0, and actual grant for replay.
        if replay:
            assert state["grant_tick"] == self.env.last_tick
        await self.step(**({"translations": lanes(Translation(load.paddr, miss_tlb), lane, Translation())} if self.wrapper else {}))  # S1
        if self.wrapper:
            prefix = f"io_forward_{lane}_s2Resp_"
            assert self.env.observed[prefix + "valid"] == int(not miss_tlb)
            if not miss_tlb:
                assert all(not self.env.observed[prefix + f"bits_forwardMask_{byte}"] for byte in range(16))
                assert all(not self.env.observed[prefix + "bits_" + flag] for flag in
                    ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"))
        # First C_TM is the pinned source's coarse S2 check followed by S3
        # revoke; first C_DM miss has no data. A retry DCache hit has data.
        data_valid = replay or miss_tlb
        if self.leaf:
            await self.step()  # Conceptual S2; no native leaf query ports.
        else:
            raw = RawQuery(True, u.rob, u.sq, load.paddr, req.mask, data_valid, u.rvc, u.ftq, u.offset, u.checkpoint)
            rar = RarQuery(True, u.rob, u.lq, load.paddr, data_valid)
            await self.step(raw_queries=lanes(raw, lane, RawQuery()), rar_queries=lanes(rar, lane, RarQuery()))
            pins = self.env.pre_observed
            assert pins[f"io_ldu_rawNukeQuery_{lane}_req_ready"] and pins[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
            assert not self.env.observed[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
        final = replace(load, execution=replace(req, replay_feedback=replay, slot=state["slot"] if replay else 0,
            need_replay=not replay, causes=0 if replay else req.causes),
            fullva=req.vaddr if replay else load.fullva, update_address=replay)
        kwargs = {"loads": lanes(final, lane, Load())}
        if not self.leaf:
            revoked = tuple(index == lane and not replay for index in range(3))
            kwargs.update(rar_revoke_last=revoked, raw_revoke_last=revoked)
        if replay:
            state["feedback_tick"] = self.env.last_tick + 2
            self.feedbacks += 1
        await self.step(**kwargs)  # Source-correct original S3 / leaf feedback.
        if replay:
            assert not self.env.observed["io_replayAllocate"]
            if self.leaf:
                state["local_complete"] = True
                state["release_tick"] = self.env.last_tick
                self.completed += 1

    async def quiet(self, count):
        for _ in range(count):
            await self.step()
            assert not any(self.env.observed[f"io_replay_{bank}_valid"] for bank in range(3))
            assert self.env.observed["io_replayAllocate"] and not self.current["local_complete"]

    async def pulse(self, identity):
        state = self.current
        assert identity in self.external
        kwargs = {}
        channel = (state["index"] + state["phase"]) % 2
        if self.path == "refill":
            kwargs["refills"] = lanes(Refill(True, identity), channel, Refill(), 2)
        elif self.path == "l2":
            kwargs["l2_hints"] = lanes(L2Hint(True, identity, bool((state["index"] + state["phase"]) % 2)), channel, L2Hint(), 2)
        else:
            kwargs["fast_tlb" if self.path == "tlb-fast" else "slow_tlb"] = TlbHint(True, identity)
        await self.step(**kwargs)
        return self.env.last_tick

    async def finish(self):
        state = self.current
        for _ in range(40):
            if state["local_complete"]:
                break
            await self.step()
        assert state["local_complete"] and self.completed == self.position + 1
        # Deliberately wait for actual recycling without treating it as a
        # reason to reset or shorten any original suite's budgets.
        await self.idle(4)
        assert not self.env.observed["io_replayAllocate"] and not any(
            self.env.observed[f"io_replay_{bank}_valid"] for bank in range(3))
        if not self.leaf:
            assert self.env.observed["io_lqEmpty"]
            await self.step(pending_next=RobPtr.encode(self.rob + 1))
        self.rob += 1
        self.position += 1
        await self.step()

    async def transaction(self, phase, index):
        self.current = state = self.make(phase, index)
        await self.dispatch()
        await self.pipeline()
        await self.quiet(4)
        wrong_tick = await self.pulse(state["decoy"])
        assert not any(self.env.observed[f"io_replay_{bank}_valid"] for bank in range(3))
        await self.quiet(4)
        assert self.external.pop(state["decoy"])["owner"] == "external-decoy"
        wake_tick = await self.pulse(state["identity"])
        for _ in range(40):
            if state["first_offer_tick"] is not None:
                break
            await self.step()
        assert state["first_offer_tick"] is not None
        beat = bool(state["load"].paddr & 64)
        keyword = bool((index + phase) % 2)
        first = beat if keyword else not beat
        latency = 0 if self.path == "tlb-fast" else 2 if self.path == "l2" and first else 4
        assert state["first_offer_tick"] == wake_tick + latency, (
            "normal replay wake edge", self.path, state["uid"], state["first_offer_tick"], wake_tick, latency)
        snapshot = self.offer(self.env.observed)
        state["bank"], state["slot"] = snapshot[:2]
        for _ in range(3):
            await self.step()
            assert self.offer(self.env.observed) == snapshot
            assert self.env.observed["io_replayAllocate"] and state["grant_tick"] is None
        await self.pipeline(replay=True)
        await self.finish()
        assert self.external.pop(state["identity"])["owner"] == state["uid"] and not self.external
        req = state["load"].execution
        self.rows.append(dict(uid=state["uid"], phase=phase, index=index, instruction=state["instruction"],
            ROB_ordinal=self.rob - 1, LQ_position=state["position"], public_slot=state["slot"], bank=state["bank"],
            opcode=req.uop.operation, vaddr50=req.vaddr, first_fullva64=state["load"].fullva,
            actual_Replay_fullva_zero_extended=req.vaddr, PA=state["load"].paddr, size=(req.uop.operation >> 1) & 7,
            mask=req.mask, last_beat=bool(req.last_beat), checkpoint=req.uop.checkpoint,
            FTQ_flag=int(req.uop.ftq.flag), FTQ_value=req.uop.ftq.value, FTQ_end_halfword_offset=req.uop.offset,
            dependency_ID=state["identity"], decoy_ID=state["decoy"], channel=(index + phase) % 2,
            keyword=keyword if self.path == "l2" else None, wrong_pulse_tick=wrong_tick,
            matched_pulse_tick=wake_tick, first_offer_tick=state["first_offer_tick"],
            grant_tick=state["grant_tick"], feedback_tick=state["feedback_tick"], actual_release_tick=state["release_tick"],
            payload_SHA256=state["payload_SHA256"], hold_cycles=3, first_S3_updateAddrValid=False,
            final_S3_updateAddrValid=True, actual_local_completion=True))
        self.current = None
        return state["slot"]


async def trace(env, output, dut, path, *, per_profile=120):
    actor = NormalReplayOwners(env, dut, path)
    passed = False
    error = None
    pools = []
    try:
        assert per_profile in (2, 120)
        for phase in range(len(PROFILES)):
            slots = [await actor.transaction(phase, index) for index in range(per_profile)]
            assert len(slots) == len(set(slots))
            if per_profile == 120:
                assert set(slots) == set(range(120))
            pools.append(dict(phase=phase, instruction=PROFILES[phase][0], actual_slots=sorted(slots), completed=per_profile))
        assert actor.completed == actor.grants == actor.feedbacks == 8 * per_profile
        if actor.leaf:
            env.coverage.sample(("LRQ-PAYLOAD.scalar", "LRQ-PAYLOAD.metadata", "LRQ-HOLD.stable"), env.last_tick, checked=True)
        elif actor.wrapper:
            env.prove("LSQ-REPLAY.tlb" if path.startswith("tlb") else "LSQ-REPLAY.refill")
        else:
            env.prove("LQ-REPLAY.metadata", "LQ-HINT.fast_tlb" if path == "tlb-fast" else
                "LQ-HINT.tlb" if path == "tlb-slow" else "LQ-HINT.l2" if path == "l2" else "LQ-HINT.refill")
        passed = True
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        output.write_text(json.dumps(dict(format="lsq-normal-load-replay-metadata-witness-v1", dut=dut, path=path,
            passed=passed, error=error, per_profile=per_profile, pools=pools, rows=actor.rows,
            original_UID_completions=actor.completed, actual_grants=actor.grants, actual_feedbacks=actor.feedbacks,
            checked_public_lifetime_stream_SHA256=actor.digest.hexdigest(),
            peak_active_Loads=1, declared_peak_external_dependency_owners=2, declared_external_ID_capacity=16,
            resets_between_profiles=0, native_upstream_allocator_proven=False,
            scope="Normal scalar fixed-source LSQ boundary producer. Leaf does not validate VLQ release. Parent completion requires actual LQ credit; no native upstream LDU/Cache/TLB/ROB or memory read-data proof."), indent=2) + "\n")
