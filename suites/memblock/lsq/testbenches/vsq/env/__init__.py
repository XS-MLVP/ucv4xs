from collections import deque
from dataclasses import asdict, dataclass, replace
import json

from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.transactions import Dispatch
from suites.memblock.lsq.testbenches.vsq.transactions import Inputs
from suites.memblock.lsq.testbenches.uncache_entry.model import is_younger


@dataclass(frozen=True)
class StoreReservation:
    uid: int
    position: int
    lane: int
    rob: RobPtr
    flows: int
    end: int


class VsqEnv:
    def __init__(self, driver, before, after, model, coverage, journal, nodeid, spec):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.spec = spec
        self.nodeid, self.controls, self.last_tick = nodeid, Inputs(), -1
        self.pins = self.pre_pins = None
        self.observed = self.last_change = None
        self.response = self.pre_response = None
        # Request-owned virtual/retired ledger: accepted uops come from the
        # sampled dispatch lanes; retirement comes from the public retiredPtr
        # and cancellation from the sampled redirect.  The model's Change list
        # is only used for comparison/coverage.
        self.outstanding = set()
        self.virtual_head = 0
        self.allocated_end = 0
        self.virtual_tail = 0
        self.retired_anchor = 0
        self.live = []
        self.uid_sequence = 0
        self.redirects = deque()

    async def cycle(self, dispatch=None, redirect=Redirect(), consumed=False, reset=False, **controls):
        self.controls = replace(self.controls, **controls)
        requests = tuple((dispatch or {}).get(lane, Dispatch()) for lane in range(8)) if isinstance(dispatch, (dict, type(None))) else tuple(dispatch)
        inp = replace(self.controls, dispatch=requests, redirect=redirect, consumed=consumed, reset=reset)
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "unobserved VSQ cycle"
            self.last_tick = post.event.tick
            actual = pre.value[0]
            assert actual == post.value[0]
            if self.last_tick == edge.tick:
                assert actual == inp
            row = {"nodeid": self.nodeid, "pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(actual), "post_input": asdict(post.value[0]),
                   "before": pre.value[1], "after": post.value[1], "checked": False}
            try:
                row["expected_before"] = self.model.expected_before(actual)
                self.compare(pre.value[1], row["expected_before"], "before")
                row["change"] = change = self.model.advance(actual)
                row["expected_after"] = self.model.expected()
                self.compare(post.value[1], row["expected_after"], "after")
                row["checked"] = self.model.initialized
                self.coverage.observe(change, self.last_tick)
                self.pins, self.pre_pins = post.value[1], pre.value[1]
                self.observed, self.pre_observed = self.pins, self.pre_pins
                self.response = self.driver.ports.observe(self.pins)
                self.pre_response = self.driver.ports.observe(self.pre_pins)
                self.last_change = self._update_ledger(actual, self.response)
            except BaseException as exc:
                row["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(row) + "\n")
            if self.last_tick == edge.tick:
                return self.last_change

    def compare(self, actual, expected, phase):
        for name, value in expected.items():
            assert actual[name] == value, ("vsq-cycle", self.last_tick, phase, name, actual[name], value)

    async def boot(self):
        for _ in range(3):
            await self.cycle(reset=True)
        await self.cycle()

    async def idle(self, count=1, **controls):
        return [await self.cycle(**controls) for _ in range(count)]

    def _sq_serial(self, ptr):
        return int(ptr.first) * 128 + int(ptr.second) * 64 + ptr.value

    def _update_ledger(self, inp, observation):
        """Use allocation requests and actual retired/recovery pointers.

        A physical credit is not a virtual uop count. A zero-flow uop at the
        current boundary is retained until later physical progress or empty
        confirms that prefix; it is never dropped merely because end == old end.
        Recovery uses the delayed public pointer, not an early model event.
        """
        accepted, retired, canceled, aborted = [], [], [], []
        recovery = None
        if inp.reset:
            aborted = sorted(self.outstanding)
            self.live.clear()
            self.outstanding.clear()
            self.virtual_head = self.virtual_tail = self.allocated_end = self.retired_anchor = 0
            self.redirects.clear()
        else:
            if inp.redirect.valid:
                self.redirects.append(inp.redirect)
            raw = self._sq_serial(observation.retired_ptr)
            self.retired_anchor += (raw - self.retired_anchor) % 256
            while self.live and (self.live[0].end < self.retired_anchor or
                                 self.live[0].flows and self.live[0].end == self.retired_anchor):
                retired.append(self.live.pop(0))
            if observation.redirect_ptr is not None:
                assert self.redirects, "VSQ recovery response without a requested redirect"
                redirect = self.redirects.popleft()
                survivors = []
                for item in self.live:
                    killed = is_younger(item.rob, redirect.rob, self.spec["rob_entries"]) or (
                        redirect.flush_self and item.rob == redirect.rob)
                    if killed:
                        canceled.append(item)
                    else:
                        assert not canceled, "VSQ redirect must cancel a suffix"
                        survivors.append(item)
                end = survivors[-1].end if survivors else self.retired_anchor
                assert observation.redirect_ptr == SqPtr.encode(end), ("VSQ recovery did not name owned prefix", end)
                self.live = survivors
                self.virtual_tail -= len(canceled)
                self.allocated_end = end
                recovery = {"end": end, "canceled_uids": [item.uid for item in canceled]}
            if observation.empty and not self.redirects:
                assert all(item.end == self.retired_anchor for item in self.live), "VSQ empty lost physical credit"
                retired.extend(self.live)
                self.live.clear()
            self.virtual_head += len(retired)
            # Valid-only dispatch is admitted under the producer contract.
            # The UNIT-INTERFACE simultaneous redirect boundary keeps the
            # original independent reference check and is not normal admission.
            if not inp.redirect.valid:
                for lane, dispatch in enumerate(inp.dispatch):
                    if not dispatch.valid or not dispatch.need_alloc:
                        continue
                    self.uid_sequence += 1
                    end = self.allocated_end + dispatch.flows
                    assert dispatch.end == SqPtr.encode(end), "VSQ dispatch is not a compact owned interval"
                    record = StoreReservation(self.uid_sequence, self.virtual_tail, lane, dispatch.rob, dispatch.flows, end)
                    self.virtual_tail += 1
                    self.allocated_end = end
                    self.live.append(record)
                    accepted.append(record)
        self.outstanding = {record.uid for record in self.live}
        return dict(accepted=[asdict(item) for item in accepted], retired=[asdict(item) for item in retired],
                    canceled=[asdict(item) for item in canceled], reset_aborted=aborted, recovery=recovery)

    def requests(self, mapping):
        """lane -> (ROB ptr or entry integer, flow count); compact end snapshots."""
        end, result = self.allocated_end, {}
        for lane, (rob, flows) in sorted(mapping.items()):
            end += flows
            result[lane] = Dispatch(True, True, RobPtr.encode(rob) if isinstance(rob, int) else rob, flows, SqPtr.encode(end))
        return result

    def arm(self, names, uids=None):
        self.coverage.arm(names, uids or [item["uid"] for item in self.last_change["accepted"]], self.last_tick)

    async def drain(self, rob_head, limit=40):
        await self.cycle(rob_head=rob_head)
        for _ in range(limit):
            await self.cycle()
            if not self.outstanding and self.response.empty and not self.response.recovery_stall:
                await self.idle(3)
                return
        raise AssertionError("VSQ did not drain by actual retired/empty outputs")
