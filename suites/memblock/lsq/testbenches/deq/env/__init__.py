from dataclasses import asdict
import json

from suites.memblock.lsq.testbenches.deq.transactions import Inputs
from suites.memblock.lsq.testbenches.deq.transactions import encode


class DeqEnv:
    def __init__(self, driver, before, after, model, coverage, journal, nodeid, agent_journal):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.nodeid, self.last_tick = nodeid, -1
        self.pins = self.pre_pins = None
        self.observed = self.pre_observed = self.last_change = None
        self.agent_journal = agent_journal

    def compare(self, actual, expected, masks, phase):
        difference = {key: [actual[key], value] for key, value in expected.items() if (actual[key] ^ value) & masks.get(key, -1)}
        assert not difference, ("deq-staged-public", self.last_tick, phase, difference)

    async def cycle(self, inp=Inputs()):
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "unobserved Deq model cycle"
            self.last_tick = post.event.tick
            actual = pre.value[0]
            self.pre_pins, self.pins = pre.value[1], post.value[1]
            self.pre_observed, self.observed = self.pre_pins, self.pins
            self.pre_response = self.driver.ports.observe(self.pre_pins)
            self.response = self.driver.ports.observe(self.pins)
            assert actual == post.value[0]
            if self.last_tick == edge.tick:
                assert encode(actual) == encode(inp)
            row = {"nodeid": self.nodeid, "pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(actual), "post_input": asdict(post.value[0]),
                   "before": pre.value[1], "after": post.value[1], "checked": False}
            try:
                row["expected_before"], row["masks_before"] = self.model.expected(actual)
                self.compare(pre.value[1], row["expected_before"], row["masks_before"], "before")
                row["change"] = change = self.model.advance(actual)
                row["expected_after"], row["masks_after"] = self.model.expected(actual, after=True)
                self.compare(post.value[1], row["expected_after"], row["masks_after"], "after")
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
        for _ in range(3):
            await self.cycle(Inputs(reset=True))
        await self.cycle()
