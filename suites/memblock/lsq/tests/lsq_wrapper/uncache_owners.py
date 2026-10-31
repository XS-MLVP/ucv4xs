"""Public original-UID NC/MMIO actor; bus attempts and completion are distinct.

No domain-model state or private DUT probes. Strict WrapperEnv continues to
compare every retained defined output; this is NOT the protocol-only fixture.
"""
from dataclasses import asdict, replace

from suites.memblock.lsq.load_queue.types import Bypass, Load
from suites.memblock.lsq.lsq_wrapper.types import Address, Bus, Data, Dispatch, Inputs
from suites.memblock.lsq.psq.types import Attributes
from suites.memblock.lsq.raw.types import FtqPtr, SqPtr
from suites.memblock.lsq.replay.types import Enqueue, Uop
from suites.memblock.lsq.vlq.types import QueuePtr, Redirect, RobPtr
from .memory_owners import StoreOwner, rob_number


class UncacheOwners:
    def __init__(self, env, *, kind="nc"):
        self.env, self.kind = env, kind
        self.base = Inputs(pending=RobPtr.encode(10), pending_next=RobPtr.encode(10), bus=Bus(outstanding=True))
        self.store = StoreOwner(0, RobPtr.encode(10), 0x20000, 0xA020000, value=0x8877665544332211)
        self.store_written = self.store_s2 = self.store_consumed = self.store_completed = False
        self.s2_pending, self.last_store_fire, self.sq_head = False, None, 0
        self.loads, self.active, self.attempts = [], {}, []
        self.load_head = self.tail = 0

    def make_load(self, position, *, rob=None, same_pa=None):
        nc = self.kind == "nc"
        pa = same_pa if same_pa is not None else 0xE0104000 + position * 256
        va = 0x1ABC04000 + (position * 4096 + pa % 4096 if same_pa is not None else position * 256)
        u = Uop(rob=rob or RobPtr.encode(11 + position, former=not bool(position & 1)), lq=QueuePtr.encode(position), sq=SqPtr.encode(1),
                operation=6, ftq=FtqPtr(bool(position & 1), 17 + position % 32), offset=position % 32,
                rvc=bool(position & 1), checkpoint=0x123400 + position, destination=1 + position % 200)
        return Load(Enqueue(True, u, vaddr=va, mask=255, nc=nc, need_replay=True, causes=1),
                    fullva=va, paddr=pa,
                    gpaddr=0x123400000 + va - 0x1ABC04000, hyper=bool(position & 1), nonleaf=bool(position & 2),
                    mmio=not nc, memory_backed=self.kind != "io", update_address=True)

    async def cycle(self, **fields):
        options = dict(attributes=(Attributes(), Attributes()))
        options.update(fields)
        packet = replace(self.base, **options)
        await self.env.cycle(packet)
        pre, post, tick = self.env.pre_observed, self.env.observed, self.env.last_tick
        if self.s2_pending:
            assert packet.attributes[0] == Attributes()
            self.store_s2 = True
        self.s2_pending = packet.addresses[0].valid
        if any(address.valid for address in packet.addresses):
            assert packet.addresses == (self.store.address(), Address()) and not self.store_written
            assert packet.data == (Data(), self.store.data())
            self.store_written = True
        for load in packet.loads:
            q = load.execution
            if not q.valid:
                continue
            state = self.active[q.uop.lq]
            assert q.uop == state["load"].execution.uop and not state["completed"] and not state["cancelled"]
            if q.replay_feedback:
                assert state.get("grant") == q.slot
                state["grant"] = None
                state["feedbacks"] += 1
            else:
                assert not state["initial_s3"] and q.need_replay and q.causes == 1
                state["initial_s3"] = True
            state["cause"] = q.causes
            if not q.need_replay:
                assert state["attempts"] and state["attempts"][-1]["consumed"] and not state["sent"]
                state["sent"] = True
        if pre["io_uncache_req_valid"] and packet.bus.ready:
            candidates = [state for state in self.loads if (not state["cancelled"] or state["uid"] in getattr(self, "cancelled_request_uids", ())) and not state["sent"] and state["cause"] == 1 and
                          state["load"].paddr == pre["io_uncache_req_bits_addr"] and
                          (int(state["load"].execution.uop.rob.flag), state["load"].execution.uop.rob.value, int(state["load"].execution.uop.rob.former)) ==
                          (pre["io_uncache_req_bits_robIdx_flag"], pre["io_uncache_req_bits_robIdx_value"], pre["io_uncache_req_bits_robIdx_isFormer"]) and
                          (not state["attempts"] or state["attempts"][-1]["consumed"])]
            assert len(candidates) == 1
            state, mid = candidates[0], pre["io_uncache_req_bits_id"]
            load = state["load"]
            self.env.expect({"io_uncache_req_bits_cmd": 0, "io_uncache_req_bits_vaddr": load.execution.vaddr,
                             "io_uncache_req_bits_mask": load.execution.mask, "io_uncache_req_bits_nc": int(load.execution.nc),
                             "io_uncache_req_bits_memBackTypeMM": int(load.memory_backed)}, "full-entry original Load bus attempt", before=True)
            assert not any(a["mid"] == mid and not a["consumed"] and not a.get("discarded", False) for a in self.attempts)
            attempt = dict(uid=len(self.attempts) + 1, owner_uid=state["uid"], position=state["position"], mid=mid,
                           request_tick=tick, sid=None, response=None, consumed=False)
            self.attempts.append(attempt)
            state["attempts"].append(attempt)
            self.env.emit("uncache_original_request_fire", attempt=attempt.copy())
        bus = packet.bus
        if bus.ack:
            assert bus.ack_to_load
            matches = [a for a in self.attempts if a["mid"] == bus.mid and a["sid"] is None]
            assert len(matches) == 1 and not any(a["sid"] == bus.sid and a["response"] is None for a in self.attempts)
            matches[0].update(sid=bus.sid, ack_tick=tick)
        if bus.response:
            assert bus.response_to_load
            matches = [a for a in self.attempts if a["sid"] == bus.response_id and a["response"] is None]
            assert len(matches) == 1
            matches[0]["response"] = dict(tick=tick, data=bus.data, error=bus.error, nderr=bus.nderr)
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p + "valid"] and packet.replay_ready[bank]:
                key = QueuePtr(bool(pre[p + "bits_uop_lqIdx_flag"]), pre[p + "bits_uop_lqIdx_value"])
                state = self.active[key]
                assert state.get("grant") is None and not state["cancelled"] and state["attempts"][-1]["response"] is not None
                slot = pre[p + "bits_replayQueueIdx"]
                assert state.get("original_slot", slot) == slot and slot % 3 == bank
                state.update(grant=slot, original_slot=slot)
                state["grants"] += 1
        if packet.redirect.valid:
            cutoff = rob_number(packet.redirect.rob)
            victims = [s for s in self.loads if not s["completed"] and not s["cancelled"] and
                       (rob_number(s["load"].execution.uop.rob) > cutoff or packet.redirect.flush_self and rob_number(s["load"].execution.uop.rob) == cutoff)]
            assert victims and rob_number(self.store.rob) < cutoff
            for state in victims:
                state["cancelled"] = True
            self.env.emit("uncache_branch_cancel", uids=[s["uid"] for s in victims])
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p + "valid"] and packet.sbuffer_ready[lane]:
                assert self.store_written and self.store_s2 and not self.store_consumed
                va, pa, mask, value = self.store.words()[0]
                self.env.expect({p + "bits_vaddr": va, p + "bits_addr": pa, p + "bits_mask": mask,
                                 p + "bits_data": value, p + "bits_wline": 0}, "old ordinary Store survives all Load bus/recovery activity", before=True,
                                masks={p + "bits_data": (1 << 64) - 1})
                self.store_consumed, self.last_store_fire = True, tick
        head = 128 * post["io_sqDeqPtr_first_flag"] + 64 * post["io_sqDeqPtr_second_flag"] + post["io_sqDeqPtr_value"]
        if head != self.sq_head:
            assert self.sq_head == 0 and head == 1 and self.store_consumed and self.last_store_fire + 2 == tick
            assert post["io_toLsqEnqCtrl_sqDeq_valid"] and post["io_toLsqEnqCtrl_sqDeq_bits"] == 1
            self.store_completed = True
        self.sq_head = head
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            live = [s for s in self.loads if not s["completed"] and not s["cancelled"]]
            assert 0 < count <= len(live)
            for state in live[:count]:
                assert state["sent"] and all(a["response"] and a["consumed"] for a in state["attempts"])
                state["completed"] = True
                self.load_head += 1
        assert not pre["io_mmioStout_valid"] and not pre["io_cmoOpReq_valid"]

    async def idle(self, count=1, **fields):
        for _ in range(count):
            await self.cycle(**fields)

    async def dispatch(self, loads, *, with_store=False):
        items = [Dispatch(True, 2, self.store.rob, 1, store_end=SqPtr.encode(1))] if with_store else []
        for load in loads:
            pos = self.tail
            assert load.execution.uop.lq == QueuePtr.encode(pos)
            state = dict(uid=len(self.loads) + 1, position=pos, load=load, initial_s3=False, sent=False,
                         cancelled=False, completed=False, attempts=[], grants=0, feedbacks=0, cause=0)
            self.loads.append(state)
            self.active[load.execution.uop.lq] = state
            items.append(Dispatch(True, 1, load.execution.uop.rob, 1, load_start=load.execution.uop.lq))
            self.tail += 1
        self.env.emit("uncache_allocate_originals", loads=[asdict(load) for load in loads], with_store=with_store)
        for first in range(0, len(items), 8):
            batch = items[first:first + 8]
            await self.cycle(dispatch=tuple(batch) + (Dispatch(),) * (8 - len(batch)))
        if with_store:
            await self.cycle(addresses=(self.store.address(), Address()), data=(Data(), self.store.data()))
            await self.idle(3)

    async def enqueue(self, positions):
        for first in range(0, len(positions), 3):
            batch = [self.loads[pos]["load"] for pos in positions[first:first + 3]][::-1]
            await self.cycle(loads=tuple(batch) + (Load(),) * (3 - len(batch)))
        await self.idle(4)

    def set_head(self, rob):
        self.base = replace(self.base, pending=rob, pending_next=rob)

    async def transfer(self, *, wanted=None, error=False, nderr=False, value=None):
        for _ in range(100):
            if self.env.observed["io_uncache_req_valid"]:
                break
            await self.cycle()
        assert self.env.observed["io_uncache_req_valid"]
        before = len(self.attempts)
        await self.cycle(bus=replace(self.base.bus, ready=True))
        assert len(self.attempts) == before + 1
        attempt = self.attempts[-1]
        if wanted is not None:
            assert attempt["position"] == wanted
        sid = before % 16
        await self.cycle(bus=replace(self.base.bus, ack=True, mid=attempt["mid"], sid=sid))
        await self.cycle(bus=replace(self.base.bus, response=True, response_id=sid,
                                    data=value if value is not None else 0x1122334400000000 + attempt["owner_uid"], error=error, nderr=nderr))
        return attempt

    async def grant(self, position):
        state = self.loads[position]
        u = state["load"].execution.uop
        for _ in range(100):
            bank = next((bank for bank in range(3) if self.env.observed[f"io_replay_{bank}_valid"] and
                         self.env.observed[f"io_replay_{bank}_bits_uop_lqIdx_value"] == u.lq.value and
                         self.env.observed[f"io_replay_{bank}_bits_uop_lqIdx_flag"] == int(u.lq.flag)), None)
            if bank is not None:
                break
            await self.cycle()
        assert bank is not None
        await self.cycle(replay_ready=tuple(source == bank for source in range(3)))
        assert state.get("grant") is not None

    async def bypass(self, position, lane):
        state, queries = self.loads[position], [Bypass()] * 3
        load, attempt = state["load"], state["attempts"][-1]
        assert state.get("grant") is not None and attempt["response"] is not None and not attempt["consumed"]
        queries[lane] = Bypass(True, load.execution.uop.lq, load.execution.nc, load.mmio)
        await self.cycle(bypass=tuple(queries))
        p, response, u = f"io_bypass_{lane}_", attempt["response"], load.execution.uop
        self.env.expect({p + "s1Resp_valid": 1, p + "s1Resp_bits_paddr": load.paddr,
                         "io_ldExceptionInfo_valid": 1, "io_ldExceptionInfo_bits_robIdx_flag": int(u.rob.flag),
                         "io_ldExceptionInfo_bits_robIdx_value": u.rob.value, "io_ldExceptionInfo_bits_robIdx_isFormer": int(u.rob.former),
                         "io_ldExceptionInfo_bits_vaddr": load.fullva, "io_ldExceptionInfo_bits_gpaddr": load.gpaddr,
                         "io_ldExceptionInfo_bits_isHyper": int(load.hyper), "io_ldExceptionInfo_bits_isForVSnonLeafPTE": int(load.nonleaf),
                         "io_ldExceptionInfo_bits_exceptionVec_19": int(response["error"]),
                         "io_ldExceptionInfo_bits_exceptionVec_5": int(response["nderr"])}, "original full-entry Load s1 metadata/errors")
        await self.cycle()
        self.env.expect({p + "s2Resp_valid": 1, p + "s2Resp_bits_data": response["data"] * ((1 << 64) + 1),
                         p + "s2Resp_bits_derr": int(response["error"]), p + "s2Resp_bits_nderr": int(response["nderr"])},
                        "original full-entry Load s2 response bytes/errors")
        attempt["consumed"] = True

    async def feedback(self, position, *, retry_nc=False, redirect=None):
        state = self.loads[position]
        q = replace(state["load"].execution, replay_feedback=True, slot=state["grant"],
                    need_replay=retry_nc, causes=int(retry_nc))
        await self.cycle(loads=(replace(state["load"], execution=q), Load(), Load()), redirect=redirect or Redirect())

    async def consume(self, position, lane):
        await self.grant(position)
        await self.bypass(position, lane)
        await self.feedback(position)

    async def consume_visible(self, positions, lane):
        pending = set(positions)
        for _ in range(250):
            if not pending:
                return
            visible = []
            for bank in range(3):
                p, pins = f"io_replay_{bank}_", self.env.observed
                if pins[p + "valid"]:
                    key = QueuePtr(bool(pins[p + "bits_uop_lqIdx_flag"]), pins[p + "bits_uop_lqIdx_value"])
                    index = self.active[key]["uid"] - 1
                    if index in pending:
                        visible.append(index)
            if visible:
                # Prefer program order only when already visible. A valid
                # held candidate must be consumed to allow a different one;
                # Replay grants are NOT an in-order retirement interface.
                index = min(pending) if min(pending) in visible else min(visible)
                await self.consume(index, lane)
                pending.remove(index)
            else:
                await self.cycle()
        raise AssertionError("fair original-UID Replay consumer failed to make progress")

    async def recover(self):
        lq = sq = None
        for _ in range(40):
            await self.cycle()
            post = self.env.observed
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                lq = QueuePtr(bool(post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]), post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"])
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                sq = 128 * post["io_toLsqEnqCtrl_sqRedirectPtr_bits_first_flag"] + 64 * post["io_toLsqEnqCtrl_sqRedirectPtr_bits_second_flag"] + post["io_toLsqEnqCtrl_sqRedirectPtr_bits_value"]
            if lq is not None and sq is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                assert sq == 1
                self.tail = int(lq.flag) * 120 + lq.value
                await self.idle(4)
                return lq
        raise AssertionError("real two-branch Uncache recovery did not settle")

    async def finish(self):
        self.base = replace(self.base, sbuffer_ready=(True, True))
        for _ in range(200):
            await self.cycle()
            if self.store_completed and all(s["completed"] or s["cancelled"] for s in self.loads) and self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"]:
                await self.idle(8)
                assert all(a["response"] is not None and a["consumed"] for a in self.attempts)
                assert not self.env.observed["io_uncache_req_valid"] and not self.env.observed["io_replayAllocate"]
                for old in self.loads:
                    if old["cancelled"]:
                        assert any(new["uid"] != old["uid"] and new["position"] % 120 == old["position"] % 120 and new["completed"] for new in self.loads)
                self.env.emit("uncache_all_original_obligations_drained", loads=len(self.loads), attempts=len(self.attempts),
                              cancelled=sum(s["cancelled"] for s in self.loads))
                return
        raise AssertionError("original full-entry Load/Store/bus obligations did not actually drain")
