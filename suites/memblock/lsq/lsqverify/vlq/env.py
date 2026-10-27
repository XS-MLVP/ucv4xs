from dataclasses import asdict
import json

from .checker import compare
from .types import Dispatch, Inputs, QueuePtr, Redirect, RobPtr, Writeback


class VirtualLoadQueueEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage, trace):
        self.key, self.spec, self.driver = key, spec, driver
        self.before, self.after, self.model, self.coverage, self.trace = before, after, model, coverage, trace
        self.last_tick = -1
        self.checked_cycles = 0
        self.next_rob_entry = 0
        self.observed = None

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
            return change
        except BaseException as error:
            record["error"] = repr(error)
            raise
        finally:
            self.trace.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not record["checked"]:
                self.trace.flush()

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
        position = self.model.tail
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
            incomplete = sorted((pos for pos, item in self.model.entries.items() if not item.completed), reverse=newest_first)
            writebacks = {lane: self.wb(pos) for lane, pos in enumerate(incomplete[:self.spec["writeback_width"]])}
            change = await self.cycle(writebacks=writebacks)
            released.extend(item.position for item in change.reported)
            if not self.model.entries and not self.model.prepared and self.model.head == self.model.tail and not self.model.outputs.recovery_stall:
                await self.idle(2)
                return tuple(released)
        raise AssertionError("legal completed/recovered VLQ did not drain")

    async def settle_recovery(self):
        for _ in range(12):
            if not self.model.outputs.recovery_stall and not any(self.model.recoveries):
                return
            await self.cycle()
        raise AssertionError("VLQ recovery did not settle")
