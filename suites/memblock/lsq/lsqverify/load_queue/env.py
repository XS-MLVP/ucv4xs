from dataclasses import asdict, replace
import json

from .codec import encode
from .types import Inputs


class LoadQueueEnv:
    def __init__(self, driver, before, after, model, coverage, journal, nodeid, actor_journal):
        self.driver, self.before, self.after, self.model, self.coverage = driver, before, after, model, coverage
        self.journal, self.nodeid, self.actor_journal = journal, nodeid, actor_journal
        self.last_tick, self.pre_observed, self.observed, self.last_change = -1, None, None, None

    def compare(self, actual, expected, phase):
        difference = {pin: [actual[pin], want] for pin, want in expected.items() if actual[pin] != want}
        assert not difference, ("real-load-queue-staged", self.last_tick, phase, difference)

    async def cycle(self, inp=None, **fields):
        request = inp if inp is not None else Inputs(**fields)
        edge = await self.driver.send(request)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "missing LoadQueue sampling edge"
            self.last_tick = post.event.tick
            actual = pre.value[0]
            assert pre.value[2] == post.value[2] and encode(actual) == pre.value[2]
            if self.last_tick == edge.tick:
                assert encode(actual) == encode(request)
            self.pre_observed, self.observed = pre.value[1], post.value[1]
            row = dict(nodeid=self.nodeid, pre_tick=pre.event.tick, post_tick=post.event.tick, input=asdict(actual),
                       pins=pre.value[2], post_pins=post.value[2], before=pre.value[1], after=post.value[1], checked=False)
            try:
                row["expected_before"] = self.model.expected(actual)
                self.compare(pre.value[1], row["expected_before"], "before")
                row["change"] = change = self.model.advance(actual)
                row["expected_after"] = self.model.expected(actual)
                self.compare(post.value[1], row["expected_after"], "after")
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
        await self.idle(3)

    async def idle(self, count=1, **fields):
        for _ in range(count):
            await self.cycle(**fields)

    def reach(self, *names):
        self.coverage.sample(names, self.last_tick)

    def prove(self, *names):
        self.reach(*names)
        self.coverage.sample(names, self.last_tick, checked=True)
