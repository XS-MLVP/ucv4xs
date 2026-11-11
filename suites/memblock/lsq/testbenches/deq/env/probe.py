"""First-round passive public history and explicit directed checks.

This is not a complete Deq reference/PSQ agent. Every assertion is separately
journaled with its phase and expected pins. Full lifecycle model and legal
mixed traffic remain required before acceptance.
"""
from dataclasses import asdict, replace
import json

from suites.memblock.lsq.testbenches.deq.transactions import DeqControl
from suites.memblock.lsq.testbenches.deq.transactions import Inputs
from suites.memblock.lsq.testbenches.deq.transactions import encode


class ProbeEnv:
    def __init__(self, driver, before, after, coverage, journal, checks, nodeid):
        self.driver, self.before, self.after, self.coverage, self.journal, self.checks = driver, before, after, coverage, journal, checks
        self.nodeid, self.controls, self.last_tick = nodeid, Inputs(dequeue_controls=(DeqControl(committed=True), DeqControl(committed=True))), -1
        # Directed probes keep the deq window at an explicit pointer. Current
        # RTL selects the completion rule from the deq entry's own type
        # (isCacheable(memoryType) && !isCbo && !vecInactive), so remember the
        # last real SQ entry presented on each lane and keep its type on the
        # deq window after the read window moves on.
        self.entry_types = [(False, 0), (False, 0)]
        self.pins = self.pre_pins = None
        self.observed = self.pre_observed = None
        self.response = self.pre_response = None

    async def cycle(self, **controls):
        self.controls = replace(self.controls, **controls)
        for lane, store in enumerate(self.controls.stores):
            if store.data_valid or store.address_valid:
                self.entry_types[lane] = (store.cache_operation, store.memory_type)
        typed = []
        for lane, ctrl in enumerate(self.controls.dequeue_controls):
            operation, memory = self.entry_types[lane]
            typed.append(replace(ctrl, cache_operation=ctrl.cache_operation or operation,
                                 memory_type=ctrl.memory_type or memory))
        self.controls = replace(self.controls, dequeue_controls=tuple(typed))
        edge = await self.driver.send(self.controls)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "unobserved Deq cycle"
            self.last_tick = post.event.tick
            assert pre.value[0] == post.value[0]
            if self.last_tick == edge.tick:
                assert encode(pre.value[0]) == encode(self.controls)
            self.pre_pins, self.pins = pre.value[1], post.value[1]
            self.pre_observed, self.observed = self.pre_pins, self.pins
            self.pre_response = self.driver.ports.observe(self.pre_pins)
            self.response = self.driver.ports.observe(self.pins)
            self.journal.write(json.dumps({"nodeid": self.nodeid, "pre_tick": pre.event.tick, "post_tick": post.event.tick,
                                           "input": asdict(pre.value[0]), "post_input": asdict(post.value[0]), "before": self.pre_pins, "after": self.pins}) + "\n")
            if self.last_tick == edge.tick:
                return self.pins

    def expect(self, observation, why, *, before=False):
        expected = self.driver.ports.expected(observation)
        return self._expect_pins(expected, why, before=before)

    def expect_sbuffer_word(self, lane, word, why, *, data_mask=None, before=False):
        expected = self.driver.ports.word_expected(lane, word)
        masks = {}
        if data_mask is not None:
            pin = f"io_writeToSbuffer_req_{lane}_bits_data"
            masks[pin] = data_mask
        return self._expect_pins(expected, why, before=before, bit_masks=masks)

    def _expect_pins(self, expected, why, *, before=False, bit_masks=None):
        actual = self.pre_pins if before else self.pins
        bit_masks = bit_masks or {}
        difference = {name: [actual[name], value] for name, value in expected.items() if (actual[name] ^ value) & bit_masks.get(name, -1)}
        self.checks.write(json.dumps({"nodeid": self.nodeid, "tick": self.last_tick, "phase": "before" if before else "after", "why": why,
                                     "expected": expected, "bit_masks": bit_masks, "actual": {name: actual[name] for name in expected}, "passed": not difference}) + "\n")
        assert not difference, ("deq-public-directed", self.last_tick, why, difference)

    def begin(self, names):
        self.coverage.sample(names, self.last_tick)

    def finish(self, names):
        self.coverage.sample(names, self.last_tick, checked=True)

    async def boot(self):
        for _ in range(3):
            await self.cycle(reset=True)
        await self.cycle(reset=False)

    async def idle(self, count=1, **controls):
        return [await self.cycle(**controls) for _ in range(count)]
