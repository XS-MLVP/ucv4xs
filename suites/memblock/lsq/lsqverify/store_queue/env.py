from dataclasses import asdict, replace
import json

from .decode import decode
from .types import Inputs, encode


class StoreQueueEnv:
    def __init__(self, driver, before, after, model, coverage, journal, checks, nodeid):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.checks, self.nodeid, self.last_tick, self.controls = checks, nodeid, -1, Inputs()
        self.pre_observed = self.observed = self.last_change = None

    def compare(self, pins, expected, masks, phase):
        diff = {key: [pins[key], want] for key, want in expected.items() if (pins[key] ^ want) & masks.get(key, -1)}
        assert not diff, ("real-store-queue-staged", self.last_tick, phase, diff)

    async def cycle(self, **controls):
        self.controls = replace(self.controls, **controls)
        edge = await self.driver.send(self.controls)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "unobserved StoreQueue cycle"
            self.last_tick = post.event.tick
            assert pre.value[0] == post.value[0]
            actual = decode(pre.value[0])
            assert encode(actual) == pre.value[0]
            if self.last_tick == edge.tick:
                assert encode(actual) == encode(self.controls)
            self.pre_observed, self.observed = pre.value[1], post.value[1]
            row = {"nodeid": self.nodeid, "pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": pre.value[0], "post_input": post.value[0],
                   "decoded_input": asdict(actual), "before": self.pre_observed, "after": self.observed, "checked": False}
            try:
                if self.model is not None:
                    row["expected_before"], row["masks_before"] = self.model.expected(actual, before=True)
                    self.compare(self.pre_observed, row["expected_before"], row["masks_before"], "before")
                    row["physical_before"] = self.model.safety(actual, self.pre_observed)
                    row["change"] = self.model.advance(actual)
                    row["expected_after"], row["masks_after"] = self.model.expected(actual)
                    self.compare(self.observed, row["expected_after"], row["masks_after"], "after")
                    row["physical_after"] = self.model.safety(actual, self.observed)
                    row["checked"] = True
                self.last_change = row.get("change")
            except BaseException as exc:
                row["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(row) + "\n")
            if self.last_tick == edge.tick:
                return self.last_change

    async def idle(self, count=1, **controls):
        return [await self.cycle(**controls) for _ in range(count)]

    async def boot(self):
        for _ in range(4):
            await self.cycle(reset=True)
        for _ in range(4):
            await self.cycle(reset=False)

    def begin(self, names):
        self.coverage.sample(names, self.last_tick)

    def finish(self, names):
        self.coverage.sample(names, self.last_tick, checked=True)

    def expect(self, expected, why, *, before=False, bit_masks=None):
        pins = self.pre_observed if before else self.observed
        masks = bit_masks or {}
        diff = {key: [pins[key], want] for key, want in expected.items() if (pins[key] ^ want) & masks.get(key, -1)}
        self.checks.write(json.dumps({"nodeid": self.nodeid, "tick": self.last_tick, "phase": "before" if before else "after", "why": why,
                                     "expected": expected, "actual": {key: pins[key] for key in expected}, "bit_masks": masks, "passed": not diff}) + "\n")
        assert not diff, ("real-store-queue-directed", self.last_tick, why, diff)
