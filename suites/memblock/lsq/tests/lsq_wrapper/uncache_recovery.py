"""Cancelled Load != cancelled external request; public UID ledger only."""
from dataclasses import replace

from lsqverify.lsq_wrapper.types import Bus
from lsqverify.vlq.types import Redirect
from .uncache_owners import UncacheOwners


class UncacheRecoveryOwners(UncacheOwners):
    def __init__(self, env, *, kind="nc"):
        super().__init__(env, kind=kind)
        self.cancelled_request_uids = set()
        self.discarded = []

    async def accept(self, *, sid=None):
        for _ in range(100):
            if self.env.observed["io_uncache_req_valid"]:
                break
            await self.cycle()
        assert self.env.observed["io_uncache_req_valid"]
        before = len(self.attempts)
        await self.cycle(bus=replace(self.base.bus, ready=True))
        assert len(self.attempts) == before + 1
        attempt = self.attempts[-1]
        if sid is None:
            occupied = {a["sid"] for a in self.attempts if a["sid"] is not None and a["response"] is None}
            sid = next(sid for sid in range(16) if sid not in occupied)
        await self.cycle(bus=replace(self.base.bus, ack=True, mid=attempt["mid"], sid=sid))
        return attempt

    async def respond(self, attempt, *, error=False, nderr=False):
        assert attempt["sid"] is not None and attempt["response"] is None
        await self.cycle(bus=replace(self.base.bus, response=True, response_id=attempt["sid"],
                                    data=0xBADC0FFE00000000 + attempt["uid"], error=error, nderr=nderr))

    async def cancel(self, cutoff, *, flush_self=True):
        pins = self.env.observed
        if pins["io_uncache_req_valid"]:
            # Only the actual visible pre-redirect elastic packet can survive
            # cancellation without having fired at the top. Do not allow all
            # old cancelled owners to match a later same-address generation.
            possible = [state for state in self.loads if not state["cancelled"] and not state["sent"] and
                        state["load"].paddr == pins["io_uncache_req_bits_addr"] and
                        state["load"].execution.uop.rob.value == pins["io_uncache_req_bits_robIdx_value"] and
                        int(state["load"].execution.uop.rob.flag) == pins["io_uncache_req_bits_robIdx_flag"] and
                        int(state["load"].execution.uop.rob.former) == pins["io_uncache_req_bits_robIdx_isFormer"]]
            assert len(possible) == 1
            self.cancelled_request_uids.add(possible[0]["uid"])
        await self.cycle(redirect=Redirect(True, cutoff, flush_self))
        return await self.recover()

    async def discard_cancelled_returns(self):
        assert not any(a["response"] is None for a in self.attempts)
        # No invalid bypass query is manufactured. The strict cycle reference
        # observes the actual entry/Replay freeing and no later wake/grant.
        await self.idle(8)
        assert not self.env.observed["io_replayAllocate"] and not self.env.observed["io_uncache_req_valid"]
        assert not any(self.env.observed[f"io_replay_{bank}_valid"] for bank in range(3))
        assert not self.env.observed["io_ldExceptionInfo_valid"]
        for attempt in self.attempts:
            state = self.loads[attempt["owner_uid"] - 1]
            if state["cancelled"] and not attempt["consumed"]:
                attempt["discarded"] = True
                self.discarded.append(attempt["uid"])
        self.env.emit("uncache_cancelled_external_responses_disposed", attempts=self.discarded.copy())

    async def refill(self, count=16, *, lane=0):
        start, first = self.tail, len(self.loads)
        loads = [self.make_load(pos) for pos in range(start, start + count)]
        await self.dispatch(loads)
        await self.enqueue(list(range(first, first + count)))
        if self.kind == "nc":
            batch = [await self.transfer() for _ in range(count)]
            await self.consume_visible(range(first, first + count), lane)
        else:
            batch = []
            for index in range(first, first + count):
                self.set_head(self.loads[index]["load"].execution.uop.rob)
                batch.append(await self.transfer(wanted=self.loads[index]["position"]))
                await self.consume(index, lane)
        await self.idle(6)
        assert all(state["completed"] for state in self.loads[first:])
        return batch

    async def finish(self):
        self.base = replace(self.base, sbuffer_ready=(True, True))
        for _ in range(200):
            await self.cycle()
            if self.store_completed and all(s["completed"] or s["cancelled"] for s in self.loads) and self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"]:
                await self.idle(8)
                for attempt in self.attempts:
                    state = self.loads[attempt["owner_uid"] - 1]
                    assert attempt["response"] is not None
                    assert attempt["consumed"] or state["cancelled"] and attempt.get("discarded", False)
                assert not self.env.observed["io_uncache_req_valid"] and not self.env.observed["io_replayAllocate"]
                for old in self.loads:
                    if old["cancelled"]:
                        assert any(new["uid"] > old["uid"] and new["position"] % 120 == old["position"] % 120 and new["completed"] for new in self.loads)
                self.env.emit("uncache_recovery_all_obligations_drained", allocated=len(self.loads)+1,
                              completed=sum(s["completed"] for s in self.loads)+1, cancelled=sum(s["cancelled"] for s in self.loads),
                              attempts=len(self.attempts), discarded=len(self.discarded))
                return
        raise AssertionError("cancelled/retained/refilled original Load/Store/external bus obligations did not drain")
