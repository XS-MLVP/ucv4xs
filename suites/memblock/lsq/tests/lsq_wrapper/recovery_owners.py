"""Ordinary-memory shared recovery/reset histories, no private/reference reads."""
from dataclasses import replace

from lsqverify.lsq_wrapper.types import Inputs
from lsqverify.vlq.types import QueuePtr, Redirect
from .memory_owners import MemoryOwners, rob_number


class RecoveryOwners(MemoryOwners):
    def __init__(self, env):
        super().__init__(env)
        self.store_history, self.abort_history = [], []
        self.recovered_sq_tail = None

    async def dispatch(self, stores=(), loads=(), **fields):
        await super().dispatch(stores, loads, **fields)
        self.store_history.extend(self.stores[owner.position] for owner in stores)

    async def cancel(self, cutoff, *, flush_self=True, **fields):
        def killed(rob):
            delta = (rob_number(rob) - rob_number(cutoff)) % 640
            assert delta != 320
            return 0 < delta < 320 or flush_self and delta == 0
        victims_s = [s for s in self.stores.values() if not s["completed"] and killed(s["owner"].rob)]
        victims_l = [s for s in self.loads if not s["completed"] and not s["cancelled"] and killed(s["load"].execution.uop.rob)]
        assert victims_s or victims_l
        for state in victims_s:
            assert not state["consumed"] and rob_number(state["owner"].rob) >= rob_number(self.base.pending)
            state["aborted"] = "redirect"
        for state in victims_l:
            state["cancelled"] = True
            state["aborted"] = "redirect"
            self.cancelled.append(state)
        self.abort_history.extend(victims_s + victims_l)
        await self.cycle(redirect=Redirect(True, cutoff, flush_self), **fields)
        lq = sq = None
        for _ in range(50):
            await self.cycle()
            post = self.env.observed
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                lq = QueuePtr(bool(post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]), post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"])
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                sq = 128*post["io_toLsqEnqCtrl_sqRedirectPtr_bits_first_flag"]+64*post["io_toLsqEnqCtrl_sqRedirectPtr_bits_second_flag"]+post["io_toLsqEnqCtrl_sqRedirectPtr_bits_value"]
            if lq is not None and sq is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                await self.idle(4)
                for state in victims_s:
                    assert not state["completed"] and not state["consumed"]
                    del self.stores[state["owner"].position]
                removed = {state["owner"].position for state in victims_s}
                self.fragment_order = [item for item in self.fragment_order if item[0] not in removed]
                self.recovered_sq_tail = sq
                self.env.emit("shared_memory_recovered_original_owners", load_uids=[s["uid"] for s in victims_l],
                              store_uids=[s["uid"] for s in victims_s], lq_tail=int(lq.flag)*120+lq.value, sq_tail=sq)
                return lq, sq
        raise AssertionError("real shared memory recovery did not settle both response pointers")

    async def reset(self):
        stores = [s for s in self.stores.values() if not s["completed"]]
        loads = [s for s in self.loads if not s["completed"] and not s["cancelled"]]
        assert stores and loads and not self.fragments_fired
        for state in stores:
            assert not state["consumed"]
            state["aborted"] = "reset"
        for state in loads:
            state["aborted"], state["cancelled"] = "reset", True
            self.cancelled.append(state)
        self.abort_history.extend(stores + loads)
        self.stores, self.fragment_order, self.fragments_fired = {}, [], []
        self.sq_head, self.pending_s2 = 0, (None, None)
        self.env.emit("shared_system_reset_original_uids", stores=[s["uid"] for s in stores], loads=[s["uid"] for s in loads],
                      external_reset_aborted=[], late_pre_reset_response_not_in_common_reset_contract=True)
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(6)
        assert self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"]
        assert not self.env.observed["io_replayAllocate"]
        return stores, loads

    async def finish(self, *, pending=None):
        await super().finish(pending=pending)
        for old in self.abort_history:
            if "owner" in old:
                assert any(new["uid"] > old["uid"] and new["owner"].position % 64 == old["owner"].position % 64 and new["completed"]
                           for new in self.store_history)
            else:
                assert any(new["uid"] > old["uid"] and new["load"].execution.uop.lq.value == old["load"].execution.uop.lq.value and new["completed"]
                           for new in self.loads)
        self.env.emit("shared_memory_all_original_and_reused_uids_complete", store_allocations=len(self.store_history), load_allocations=len(self.loads),
                      store_completed=sum(s["completed"] for s in self.store_history), load_completed=sum(s["completed"] for s in self.loads),
                      aborted=len(self.abort_history))
