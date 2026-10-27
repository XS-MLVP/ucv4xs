from dataclasses import asdict
import json

from .checker import compare
from .types import IdResponse, Inputs, QueuePtr, Redirect, Request, Response, RobPtr


class EntryEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage, trace):
        self.key, self.spec, self.driver = key, spec, driver
        self.before, self.after, self.model, self.coverage, self.trace = before, after, model, coverage, trace
        self.last_tick = -1
        self.pending_input = RobPtr()
        self.observed = None

    async def cycle(self, request=Request(), *, pending=None, redirect=Redirect(), bus_ready=False, id_response=IdResponse(), response=Response(),
                    mmio_wake_ready=True, nc_wake_ready=True, mmio_ready=False, nc_ready=False, reset=False):
        if pending is not None:
            self.pending_input = pending
        inp = Inputs(request, self.pending_input, redirect, bus_ready, id_response, response, mmio_wake_ready,
                     nc_wake_ready, mmio_ready, nc_ready, reset)
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= edge.tick and pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            if post.event.tick == edge.tick:
                assert pre.value[0] == inp, ("entry requested/observed input mismatch", inp, pre.value[0])
            change = self.check_cycle(pre, post)
            if post.event.tick == edge.tick:
                return change

    def check_cycle(self, pre, post):
        inp, before = pre.value
        post_input, after = post.value
        record = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(inp), "post_input": asdict(post_input),
                  "before": asdict(before), "after": asdict(after), "checked": False}
        try:
            assert inp == post_input, "passive sample must precede driver restoration"
            expected_before = self.model.outputs_for(inp)
            record["expected_before"] = asdict(expected_before)
            if not inp.reset:
                compare(before, expected_before, phase="before", tick=pre.event.tick)
            change = self.model.advance(inp)
            expected_after = self.model.outputs_for(post_input)
            record.update(expected_after=asdict(expected_after), change=asdict(change))
            scenes = self.coverage.discover(inp, change, self.model, before, after)
            self.coverage.sample(scenes, post.event.tick, checked=False)
            if not inp.reset:
                compare(after, expected_after, phase="after", tick=post.event.tick)
                self.coverage.confirm(scenes, inp, change, self.model, before, after, post.event.tick)
                record["checked"] = True
            self.observed = after
            return change
        except BaseException as error:
            record["error"] = repr(error)
            raise
        finally:
            self.trace.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not record["checked"]:
                self.trace.flush()

    async def reset(self):
        self.pending_input = RobPtr()
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(3)

    async def idle(self, cycles=1, **kwargs):
        return [await self.cycle(**kwargs) for _ in range(cycles)]

    def request(self, *, nc=True, rob=None, lq=7, paddr=0x123456780008, mask=0xA55A, tag=1, exceptions=0):
        rob = RobPtr.encode(10) if rob is None else rob
        return Request(True, rob, QueuePtr.encode(lq), (0x1234567800000 | (tag << 4)) & ((1 << 50) - 1),
                       (0xFEDCBA9800000000 | tag) & ((1 << 64) - 1), paddr, (0x8765432100000000 | tag) & ((1 << 64) - 1), mask,
                       nc, not nc, bool(tag & 1), bool(tag & 2), bool(tag & 4), exceptions)

    async def issue(self):
        for _ in range(12):
            if self.observed.bus.valid:
                change = await self.cycle(bus_ready=True)
                assert change.issued
                return change
            await self.cycle()
        raise AssertionError("entry did not produce expected bus request")

    async def complete(self, *, data=0x0123456789ABCDEF, error=False, nderr=False, sid=3):
        owner = self.model.owner
        assert owner is not None
        if self.model.phase in ("holding", "request"):
            await self.issue()
        if self.model.slave_id is None:
            await self.cycle(id_response=IdResponse(True, self.spec["entry_id"], sid))
        if self.model.phase == "response":
            await self.cycle(response=Response(True, data, error, nderr))
        if self.model.phase == "wakeup":
            await self.cycle()
        assert self.observed.nc.valid if owner.request.nc else self.observed.mmio.valid
        change = await self.cycle(nc_ready=owner.request.nc, mmio_ready=not owner.request.nc)
        assert change.consumed and change.retired and self.observed.exception.valid
        await self.idle(2)
        assert not self.observed.exception.valid and self.model.owner is None
        return change
