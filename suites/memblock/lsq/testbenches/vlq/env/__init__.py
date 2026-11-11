from dataclasses import asdict, dataclass, replace
import json

from suites.memblock.lsq.testbenches.vlq.checker import compare
from suites.memblock.lsq.testbenches.vlq.transactions import Dispatch
from suites.memblock.lsq.testbenches.vlq.transactions import Inputs
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vlq.transactions import Writeback


@dataclass
class LiveItem:
    """Request-owned VLQ lifecycle, never a reference-model event copy."""

    uid: int
    position: int
    rob_order: int
    rob: RobPtr
    completed: bool = False


@dataclass(frozen=True)
class OwnershipChange:
    old_head: int
    old_tail: int
    allocated: tuple[LiveItem, ...] = ()
    reported: tuple[LiveItem, ...] = ()


class VirtualLoadQueueEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage, trace):
        self.key, self.spec, self.driver = key, spec, driver
        self.before, self.after, self.model, self.coverage, self.trace = before, after, model, coverage, trace
        self.last_tick = -1
        self.checked_cycles = 0
        self.next_rob_entry = 0
        self.observed = None
        # Request-owned lifecycle ledger.  Release/preparation, recovery
        # pipeline and ROB unwrapping all follow the public contract; the
        # reference model's Change events are used only by the comparison and
        # coverage path, never to choose the next stimulus.
        self.entries = {}
        self.uid_sequence = 0
        self.head_position = 0
        self.tail = 0
        self.prepared = ()
        self.recoveries = [None, None]
        self.rob_anchor = None
        self.last_released = ()
        self.stall = False

    async def cycle(self, dispatch=(), writebacks=(), *, redirect=Redirect(), reset=False):
        if isinstance(dispatch, dict):
            dispatch = tuple(dispatch.get(i, Dispatch()) for i in range(self.spec["dispatch_width"]))
        elif not dispatch:
            dispatch = (Dispatch(),) * self.spec["dispatch_width"]
        if isinstance(writebacks, dict):
            writebacks = tuple(writebacks.get(i, Writeback()) for i in range(self.spec["writeback_width"]))
        elif not writebacks:
            writebacks = (Writeback(),) * self.spec["writeback_width"]
        request = Inputs(tuple(dispatch), tuple(writebacks), redirect, reset)
        accepted = await self.driver.send(request)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= accepted.tick and pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            if post.event.tick == accepted.tick:
                assert pre.value.inputs == request, ("actual inputs differ from requested beat", request, pre.value.inputs)
            change = self.check_cycle(pre, post)
            if post.event.tick == accepted.tick:
                return change

    def check_cycle(self, pre, post):
        record = {"pre_tick": pre.event.tick, "post_tick": post.event.tick,
                  "before": asdict(pre.value), "after": asdict(post.value), "checked": False}
        try:
            old = self.model.outputs
            change = self.model.advance(pre.value.inputs)
            record.update(expected_before=asdict(old), expected_after=asdict(self.model.outputs),
                          change=asdict(change), model_head=self.model.head, model_tail=self.model.tail)
            scenes = self.coverage.discover(pre.value.inputs, change, self.model)
            self.coverage.sample(scenes, post.event.tick, checked=False)
            if not pre.value.inputs.reset:
                compare(pre.value.outputs, old, phase="before", tick=pre.event.tick)
                compare(post.value.outputs, self.model.outputs, phase="after", tick=post.event.tick)
                self.coverage.confirm(scenes, pre.value.inputs, change, self.model, post.event.tick)
                self.checked_cycles += 1
                record["checked"] = True
            self.observed = post.value.outputs
            return self._update_ledger(pre.value.inputs, self.observed)
        except BaseException as error:
            record["error"] = repr(error)
            raise
        finally:
            self.trace.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not record["checked"]:
                self.trace.flush()

    @property
    def capacity(self):
        return self.spec["size"] - (self.tail - self.head_position)

    def _rob_decode(self, pointer, *, observe=False):
        """Unwrap encoded ROB slots into a nearby program-order timeline."""
        size = self.spec["rob_entries"]
        if not 0 <= pointer.value < size:
            raise ValueError("ROB value outside configured entries")
        raw = 2 * (int(pointer.flag) * size + pointer.value) + int(not pointer.former)
        period = 4 * size
        if self.rob_anchor is None:
            value = raw
        else:
            base = (self.rob_anchor - raw) // period
            choices = [raw + period * n for n in (base, base + 1)]
            distance = min(abs(item - self.rob_anchor) for item in choices)
            closest = [item for item in choices if abs(item - self.rob_anchor) == distance]
            if len(closest) != 1:
                raise ValueError("ambiguous ROB half-ring age outside legal domain")
            value = closest[0]
        if observe:
            self.rob_anchor = value if self.rob_anchor is None else max(self.rob_anchor, value)
        return value

    def _reset_ledger(self):
        self.entries = {}
        self.head_position = self.tail = 0
        self.prepared = ()
        self.recoveries = [None, None]
        self.rob_anchor = None
        self.last_released = ()
        self.stall = False

    def _update_ledger(self, inp, observation=None):
        """Independent VLQ ownership from sampled inputs and the time contract.

        Release is two-stage: a completed head prefix is prepared at N and the
        previous batch is reported/head-advanced at N+1.  Recovery rolls the
        allocated tail back two cycles after the redirect, as the public
        ``lqRecoverStall``/``lqRedirect`` contract describes.
        """
        self.last_released = ()
        old_head, old_tail = self.head_position, self.tail
        if inp.reset:
            self._reset_ledger()
            return OwnershipChange(old_head, old_tail)
        size = self.spec["size"]
        active = [(lane, dispatch) for lane, dispatch in enumerate(inp.dispatch) if dispatch.valid]
        total_flows = sum(dispatch.flows for _, dispatch in active)
        if total_flows > self.capacity:
            raise ValueError("dispatch exceeds independently owned VLQ capacity")
        if active and self.stall:
            raise ValueError("dispatch while the public recover-stall is asserted")
        previous_rob = max((item.rob_order for item in self.entries.values()), default=None)
        requests, offset = [], 0
        for lane, dispatch in active:
            if not 0 <= dispatch.flows <= self.spec["max_flows_per_request"]:
                raise ValueError("flow count outside the configured request domain")
            if dispatch.start != QueuePtr.encode(old_tail + offset, size):
                raise ValueError(f"dispatch lane {lane} does not describe the compact next interval")
            order = self._rob_decode(dispatch.rob, observe=True)
            if previous_rob is not None and order < previous_rob:
                raise ValueError("dispatch ROB slots must preserve program order")
            previous_rob = order
            requests.append((dispatch, old_tail + offset, order))
            offset += dispatch.flows
        cutoff = self._rob_decode(inp.redirect.rob) if inp.redirect.valid else None

        def canceled(order):
            return cutoff is not None and (order > cutoff or inp.redirect.flush_self and order == cutoff)

        canceled_items = tuple(item for item in self.entries.values() if canceled(item.rob_order))
        canceled_ids = {item.uid for item in canceled_items}
        enabled_wb = [wb for wb in inp.writebacks if wb.valid]
        if len({wb.index for wb in enabled_wb}) != len(enabled_wb):
            raise ValueError("multiple writebacks to the same live slot")
        by_index = {item.position % size: item for item in self.entries.values()}
        for wb in enabled_wb:
            if wb.index not in by_index or by_index[wb.index].completed:
                raise ValueError("writeback must target a live, not-yet-completed lifecycle")
        prepared = []
        for position in range(old_head, min(old_head + self.spec["release_width"], old_tail)):
            item = self.entries.get(position)
            if item is None or not item.completed or item.uid in canceled_ids:
                break
            prepared.append(item)
        reported = self.prepared
        new_head = old_head + len(reported)
        due = self.recoveries.pop(0)
        proposed_tail = old_tail - due if due is not None else old_tail + total_flows
        new_tail = max(new_head, proposed_tail)
        stall = inp.redirect.valid or due is not None or any(item is not None for item in self.recoveries)
        for item in (*prepared, *canceled_items):
            self.entries.pop(item.position, None)
        for wb in enabled_wb:
            item = by_index[wb.index]
            if not wb.replay and wb.update_address:
                item.completed = True
        canceled_dispatch = 0
        allocated = []
        for dispatch, start, order in requests:
            if canceled(order):
                canceled_dispatch += dispatch.flows
                continue
            for position in range(start, start + dispatch.flows):
                if position in self.entries:
                    raise ValueError("dispatch would overwrite an owned lifecycle")
                self.uid_sequence += 1
                self.entries[position] = LiveItem(self.uid_sequence, position, order, dispatch.rob)
                allocated.append(replace(self.entries[position]))
        self.recoveries.append(len(canceled_items) + canceled_dispatch if inp.redirect.valid else None)
        self.head_position, self.tail = new_head, new_tail
        self.prepared = tuple(prepared)
        self.stall = stall
        self.last_released = tuple(item.position for item in reported)
        assert 0 <= self.tail - self.head_position <= size, (self.head_position, self.tail)
        if observation is not None:
            assert observation.dequeue_valid == bool(reported) and (
                not reported or observation.dequeue_count == len(reported)), "VLQ credit must name the owned completed prefix"
            assert observation.head == QueuePtr.encode(self.head_position, size)
            assert observation.recovery_stall == self.stall
        return OwnershipChange(old_head, old_tail, tuple(allocated), tuple(replace(item) for item in reported))

    async def reset(self):
        self.next_rob_entry = 0
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(2)

    async def idle(self, cycles=1):
        changes = []
        for _ in range(cycles):
            changes.append(await self.cycle())
        return changes

    def build_dispatch(self, flows, *, lanes=None, robs=None):
        flows = tuple(flows)
        lanes = tuple(range(len(flows))) if lanes is None else tuple(lanes)
        if len(lanes) != len(flows) or len(set(lanes)) != len(lanes) or tuple(sorted(lanes)) != lanes:
            raise ValueError("dispatch lanes must be distinct and in lane order")
        if robs is None:
            robs = tuple(RobPtr.encode(self.next_rob_entry + i, size=self.spec["rob_entries"]) for i in range(len(flows)))
            self.next_rob_entry += len(flows)
        if len(robs) != len(flows):
            raise ValueError("each valid dispatch needs a ROB slot")
        position = self.tail
        result = {}
        for lane, flow, rob in zip(lanes, flows, robs, strict=True):
            if lane not in range(self.spec["dispatch_width"]):
                raise ValueError("dispatch lane outside actual width")
            result[lane] = Dispatch(True, rob, QueuePtr.encode(position, self.spec["size"]), flow)
            position += flow
        return result

    def wb(self, position, *, replay=False, update=True):
        return Writeback(True, position % self.spec["size"], update, replay)

    async def complete_and_drain(self, *, newest_first=False):
        released = []
        for _ in range(self.spec["size"] * 4 + 32):
            incomplete = sorted((position for position, item in self.entries.items()
                                 if not item.completed), reverse=newest_first)
            writebacks = {lane: self.wb(position) for lane, position
                          in enumerate(incomplete[:self.spec["writeback_width"]])}
            await self.cycle(writebacks=writebacks)
            released.extend(self.last_released)
            if not self.entries and not self.prepared and self.head_position == self.tail and not self.stall:
                await self.idle(2)
                return tuple(released)
        raise AssertionError("legal completed/recovered VLQ did not drain")

    async def settle_recovery(self):
        for _ in range(12):
            if not self.stall and not any(item is not None for item in self.recoveries):
                return
            await self.cycle()
        raise AssertionError("VLQ recovery did not settle")
