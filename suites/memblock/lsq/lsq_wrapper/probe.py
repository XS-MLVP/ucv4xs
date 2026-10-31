"""Explicit public-protocol probe, NOT a relaxed full-output reference.

Used to carry an actual transaction through a real WB/Sbuffer fire even when
the separate strict full-cycle reference would stop at an earlier waveform.
Every input/output remains sampled. Test/original-UID and independent audits
provide the stated assertions; no row is credited as full-reference checked.
"""
from dataclasses import asdict
import json

from .codec import encode
from .types import Inputs


class PublicProbeEnv:
    def __init__(self, driver, before, after, coverage, journal, checks, actor, nodeid):
        self.driver, self.before, self.after, self.coverage = driver, before, after, coverage
        self.journal, self.checks, self.actor_journal, self.nodeid = journal, checks, actor, nodeid
        self.last_tick, self.pre_observed, self.observed = -1, None, None

    async def cycle(self, inp=None, **fields):
        request = inp if inp is not None else Inputs(**fields)
        edge = await self.driver.send(request)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick
            self.last_tick = post.event.tick
            actual = pre.value[0]
            assert pre.value[2] == post.value[2] and encode(actual) == pre.value[2]
            if self.last_tick == edge.tick:
                assert encode(actual) == encode(request)
            self.pre_observed, self.observed = pre.value[1], post.value[1]
            self.journal.write(json.dumps(dict(nodeid=self.nodeid, pre_tick=pre.event.tick, post_tick=post.event.tick,
                               input=asdict(actual), pins=pre.value[2], post_pins=post.value[2], before=pre.value[1], after=post.value[1],
                               checked=False, full_cycle_reference_compared=False,
                               scope="explicit_public_protocol_original_uid_probe_not_full_output_reference")) + "\n")
            if self.last_tick == edge.tick:
                return

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
        assert not difference, ("real-lsq-wrapper-public-probe", self.last_tick, why, difference)
