from dataclasses import asdict
import json

from .checker import compare
from .types import Inputs, Query, QueuePtr, Redirect, Release, RobPtr


class RarEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage, trace):
        self.key, self.spec, self.driver = key, spec, driver
        self.before, self.after, self.model, self.coverage, self.trace = before, after, model, coverage, trace
        self.last_tick = -1
        self.checked_cycles = 0
        self.head_input = 0
        self.next_rob_entry = 2
        self.observed = None

    async def cycle(self, queries=(), *, head=None, release=Release(), redirect=Redirect(), revoke_last=(), revoke_older=(), reset=False):
        if isinstance(queries, dict):
            queries = tuple(queries.get(i, Query()) for i in range(self.spec["query_width"]))
        elif not queries:
            queries = (Query(),) * self.spec["query_width"]
        if head is not None:
            self.head_input = head
        width = self.spec["query_width"]
        inp = Inputs(tuple(queries), tuple(i in revoke_last for i in range(width)), tuple(i in revoke_older for i in range(width)),
                     QueuePtr.encode(self.head_input), redirect, release, reset)
        accepted = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= accepted.tick and pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            if post.event.tick == accepted.tick:
                assert pre.value[0] == inp, ("requested/observed RAR input mismatch", inp, pre.value[0])
            change = self.check_cycle(pre, post)
            if post.event.tick == accepted.tick:
                return change

    def check_cycle(self, pre, post):
        inp, actual_before = pre.value
        post_input, actual_after = post.value
        record = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(inp),
                  "post_input": asdict(post_input), "before": asdict(actual_before), "after": asdict(actual_after), "checked": False}
        try:
            assert inp == post_input, "sampling phase must precede the driver's return to idle"
            old = self.model.outputs_for(inp)
            record["expected_before"] = asdict(old)
            if not inp.reset:
                compare(actual_before, old, phase="before", tick=pre.event.tick)
            change = self.model.advance(inp, actual_before.ready)
            expected = self.model.outputs_for(post_input)
            record.update(expected_after=asdict(expected), change=asdict(change))
            scenes = self.coverage.discover(inp, change, self.model, actual_before, actual_after)
            self.coverage.sample(scenes, post.event.tick, checked=False)
            if not inp.reset:
                compare(actual_after, expected, phase="after", tick=post.event.tick)
                self.coverage.confirm(scenes, inp, change, self.model, actual_before, actual_after, post.event.tick)
                self.checked_cycles += 1
                record["checked"] = True
            self.observed = actual_after
            return change
        except BaseException as error:
            record["error"] = repr(error)
            raise
        finally:
            self.trace.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not record["checked"]:
                self.trace.flush()

    async def reset(self):
        self.head_input = 0
        self.next_rob_entry = 2
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(3)

    async def idle(self, cycles=1):
        return [await self.cycle() for _ in range(cycles)]

    def request(self, position, address, *, rob=None, nc=True, data=True):
        if rob is None:
            rob = RobPtr.encode(self.next_rob_entry)
            self.next_rob_entry += 1
        return Query(True, rob, QueuePtr.encode(position), address, data, nc)

    async def probe(self, addresses, *, rob=None, lanes=None, expect=None):
        addresses = tuple(addresses)
        lanes = tuple(range(len(addresses))) if lanes is None else tuple(lanes)
        if rob is None:
            oldest = min((item.rob_order for item in self.model.entries.values()), default=2 * self.next_rob_entry)
            rob = RobPtr.encode(oldest // 2 - 1)
        queries = {lane: Query(True, rob, QueuePtr.encode(self.head_input), address) for lane, address in zip(lanes, addresses, strict=True)}
        change = await self.cycle(queries)
        if expect is not None:
            for lane, wanted in zip(lanes, expect, strict=True):
                assert self.observed.responses[lane].valid and self.observed.responses[lane].nuke == wanted
        return change

    async def advance_head(self, target):
        if target < self.head_input:
            raise ValueError("head must not move backwards")
        changes = []
        while self.head_input < target:
            changes.append(await self.cycle(head=min(target, self.head_input + 8)))
        return changes

    async def settle_free(self):
        for _ in range(self.spec["size"] + 6):
            if not any(self.model.free.waiting) and not self.model.free.selected:
                await self.idle(3)
                return
            await self.cycle()
        raise AssertionError("RAR return pipeline did not settle")
