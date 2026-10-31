from dataclasses import asdict
import json

from .checker import compare
from .types import FtqPtr, Inputs, Query, Redirect, RobPtr, SqPtr, Store


class RawEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage, trace):
        self.key, self.spec, self.driver = key, spec, driver
        self.before, self.after, self.model, self.coverage, self.trace = before, after, model, coverage, trace
        self.last_tick = -1
        self.head_input = 0
        self.next_rob_entry = 2
        self.observed = None

    async def cycle(self, queries=(), *, stores=(), head=None, redirect=Redirect(), revoke_last=(), revoke_older=(), reset=False):
        if isinstance(queries, dict):
            queries = tuple(queries.get(i, Query()) for i in range(self.spec["query_width"]))
        elif not queries:
            queries = (Query(),) * self.spec["query_width"]
        if isinstance(stores, dict):
            stores = tuple(stores.get(i, Store()) for i in range(self.spec["store_width"]))
        elif not stores:
            stores = (Store(),) * self.spec["store_width"]
        if head is not None:
            self.head_input = head
        width = self.spec["query_width"]
        inp = Inputs(tuple(queries), tuple(stores), tuple(i in revoke_last for i in range(width)),
                     tuple(i in revoke_older for i in range(width)), SqPtr.encode(self.head_input), redirect, reset)
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= edge.tick and pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            if post.event.tick == edge.tick:
                assert pre.value[0] == inp, ("RAW requested/observed input mismatch", inp, pre.value[0])
            change = self.check_cycle(pre, post)
            if post.event.tick == edge.tick:
                return change

    def check_cycle(self, pre, post):
        inp, actual_before = pre.value
        post_input, actual_after = post.value
        record = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(inp), "post_input": asdict(post_input),
                  "before": asdict(actual_before), "after": asdict(actual_after), "checked": False}
        try:
            assert inp == post_input, "RAW passive sample must precede driver restoration"
            expected_before = self.model.outputs_for(inp)
            record["expected_before"] = asdict(expected_before)
            if not inp.reset:
                compare(actual_before, expected_before, phase="before", tick=pre.event.tick)
            change = self.model.advance(inp, actual_before.ready)
            expected_after = self.model.outputs_for(post_input)
            record.update(expected_after=asdict(expected_after), change=asdict(change))
            scenes = self.coverage.discover(inp, change, self.model, actual_before, actual_after)
            self.coverage.sample(scenes, post.event.tick, checked=False)
            if not inp.reset:
                compare(actual_after, expected_after, phase="after", tick=post.event.tick)
                self.coverage.confirm(scenes, inp, change, self.model, actual_before, actual_after, post.event.tick)
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

    def request(self, position, address, *, rob=None, mask=0xFFFF, data=True, tag=None):
        if rob is None:
            rob = RobPtr.encode(self.next_rob_entry)
            self.next_rob_entry += 1
        tag = rob.value if tag is None else tag
        return Query(True, rob, SqPtr.encode(position), address, mask, data, bool(tag & 1),
                     FtqPtr(bool(tag & 64), tag % 64), tag * 7 % 32, (0xFEDCBA9800000000 | tag) & ((1 << 64) - 1))

    def store(self, address, *, rob=None, mask=0xFFFF, wline=False, tlb_miss=False, tag=21):
        rob = rob or RobPtr.encode(1)
        return Store(True, rob, address, mask, wline, tlb_miss, bool(tag & 64), tag % 64, tag * 3 % 32, bool(tag & 1))

    async def probe(self, stores, *, expect=None):
        if not isinstance(stores, dict):
            stores = dict(enumerate(stores))
        await self.cycle(stores=stores)
        await self.idle(self.spec["selection_registers"] - 1)
        if expect is not None:
            for lane, wanted in expect.items():
                actual = self.observed.rollbacks[lane]
                assert actual.valid == (wanted is not None), (lane, actual, wanted)
                if wanted is not None:
                    assert actual.rob == wanted.rob and actual.ftq == wanted.ftq and actual.checkpoint == wanted.checkpoint
        return self.observed

    async def advance_head(self, target):
        if target < self.head_input:
            raise ValueError("SQ address-ready pointer must not move backwards")
        changes = []
        while self.head_input < target:
            changes.append(await self.cycle(head=min(target, self.head_input + 8)))
        return changes

    async def settle_free(self):
        for _ in range(self.spec["size"] + 8):
            if not any(self.model.free.waiting) and not self.model.free.selected:
                await self.idle(4)
                return
            await self.cycle()
        raise AssertionError("RAW return pipeline did not settle")
