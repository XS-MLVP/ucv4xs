from dataclasses import asdict
import json

from .codec import encode
from .types import Inputs


class WrapperEnv:
    def __init__(self, driver, before, after, model, coverage, journal, checks, actor, nodeid):
        self.driver, self.before, self.after, self.model, self.coverage = driver, before, after, model, coverage
        self.journal, self.checks, self.actor_journal, self.nodeid = journal, checks, actor, nodeid
        self.last_tick, self.pre_observed, self.observed, self.last_change = -1, None, None, None

    def compare(self, actual, expected, masks, phase):
        difference = {pin: [actual[pin], value] for pin, value in expected.items() if (actual[pin] ^ value) & masks.get(pin, -1)}
        assert not difference, ("real-lsq-wrapper-staged", self.last_tick, phase, difference)

    async def cycle(self, inp=None, **fields):
        request = inp if inp is not None else Inputs(**fields)
        edge = await self.driver.send(request)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "missing mixed LSQ sample"
            self.last_tick = post.event.tick
            actual = pre.value[0]
            assert pre.value[2] == post.value[2] and encode(actual) == pre.value[2]
            if self.last_tick == edge.tick:
                assert encode(actual) == encode(request)
            self.pre_observed, self.observed = pre.value[1], post.value[1]
            row = dict(nodeid=self.nodeid, pre_tick=pre.event.tick, post_tick=post.event.tick, input=asdict(actual),
                       pins=pre.value[2], post_pins=post.value[2], before=pre.value[1], after=post.value[1], checked=False,
                       explicitly_unimplemented_outputs=self.model.unimplemented_outputs)
            try:
                row["expected_before"], row["masks_before"] = self.model.expected(actual, before=True)
                self.compare(self.pre_observed, row["expected_before"], row["masks_before"], "before")
                row["physical_before"] = self.model.safety(actual, self.pre_observed)
                row["change"] = change = self.model.advance(actual)
                row["expected_after"], row["masks_after"] = self.model.expected(actual)
                self.compare(self.observed, row["expected_after"], row["masks_after"], "after")
                row["physical_after"] = self.model.safety(actual, self.observed)
                row["checked"] = True
                self.last_change = change
            except BaseException as exc:
                row["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(row) + "\n")
            if self.last_tick == edge.tick:
                return change

    async def boot(self):
        for _ in range(6):
            await self.cycle(reset=True)
        for _ in range(4):
            await self.cycle()

    def emit(self, event, **fields):
        self.actor_journal.write(json.dumps(dict(event=event, nodeid=self.nodeid, tick=self.last_tick, **fields)) + "\n")

    def reach(self, *names):
        self.coverage.sample(names, self.last_tick)

    def prove(self, *names):
        self.reach(*names)
        self.coverage.sample(names, self.last_tick, checked=True)

    def expect(self, values, why, *, before=False, masks=None):
        actual, masks = self.pre_observed if before else self.observed, masks or {}
        difference = {pin: [actual[pin], value] for pin, value in values.items() if (actual[pin] ^ value) & masks.get(pin, -1)}
        self.checks.write(json.dumps(dict(tick=self.last_tick, nodeid=self.nodeid, why=why, phase="before" if before else "after",
                                        actual={pin: actual[pin] for pin in values}, expected=values, masks=masks, passed=not difference)) + "\n")
        assert not difference, ("real-lsq-wrapper-directed", self.last_tick, why, difference)
