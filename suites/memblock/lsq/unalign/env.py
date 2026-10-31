from dataclasses import asdict
import json

from suites.memblock.lsq.raw.types import SqPtr
from .types import Inputs, Recovery, Request


class UnalignEnv:
    def __init__(self, driver, before, after, model, coverage, journal):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.last_tick = -1
        self.last_change = self.observed = self.pre_observed = None

    async def cycle(self, requests=None, *, address_ready=SqPtr(), ready=False, redirect=Recovery(), reset=False):
        if requests is None:
            requests = (Request(),) * 2
        elif isinstance(requests, dict):
            requests = tuple(requests.get(lane, Request()) for lane in range(2))
        inp = Inputs(tuple(requests), address_ready, ready, redirect, reset)
        self.model.validate(inp)
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert post.event.tick == self.last_tick + 2, "unobserved Unalign cycle"
            self.last_tick = post.event.tick
            observed_inp = pre.value[0]
            assert observed_inp == post.value[0]
            if post.event.tick == edge.tick:
                assert observed_inp == inp
            row = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(observed_inp), "post_input": asdict(post.value[0]),
                   "before": pre.value[1], "after": post.value[1], "checked": False}
            try:
                row["expected_before"] = self.model.expected(observed_inp)
                if not observed_inp.reset:
                    self.compare(pre.value[1], row["expected_before"], "before")
                change = self.model.advance(observed_inp)
                row["change"] = change
                row["expected_after"] = self.model.expected(observed_inp)
                if not observed_inp.reset:
                    self.compare(post.value[1], row["expected_after"], "after")
                    row["checked"] = True
                self.coverage.observe(change, self.last_tick, self.model.sequence)
                self.last_change = change
                self.pre_observed, self.observed = pre.value[1], post.value[1]
            except BaseException as exc:
                row["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(row) + "\n")
            if post.event.tick == edge.tick:
                return change

    def compare(self, actual, expected, phase):
        for key, value in expected.items():
            assert actual[key] == value, ("unalign", self.last_tick, phase, key, actual[key], value)

    async def reset(self):
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(2)

    async def idle(self, count=1, **kwargs):
        return [await self.cycle(**kwargs) for _ in range(count)]

    def request(self, sq=7, *, page=0xFEDCBA987, offset=0xABC):
        return Request(True, SqPtr.encode(sq), page << 12 | offset)

    async def enqueue(self, req, *, lane=0, **kwargs):
        return await self.cycle({lane: req}, address_ready=req.sq, **kwargs)

    def arm(self, names, owners=None, *, reuse=False):
        if owners is None:
            owners = [asdict(x) for x in self.model.order]
        self.coverage.arm(names, owners, self.last_tick, self.model.sequence, reuse=reuse)

    async def drain(self):
        await self.idle(3, ready=True)
        assert not self.model.order and not self.observed["io_toDeqModule_valid"]
        assert not any(self.observed[f"io_forwardValid_{slot}"] for slot in range(2))
