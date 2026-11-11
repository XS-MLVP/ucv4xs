from dataclasses import asdict
import json

from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import Inputs
from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import Offer
from suites.memblock.lsq.testbenches.enter_sbuffer.transactions import Write


class EnterSbufferEnv:
    def __init__(self, driver, before, after, model, coverage, journal):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.last_tick = -1
        self.pins = self.pre_pins = None
        self.last_change = self.observed = self.pre_observed = None
        self.response = self.pre_response = None
        # Public ledger from accepted/consumed transaction responses.  Tests
        # use it for setup control instead of reading the reference model.
        self.live = []
        self.accepted_count = 0

    async def cycle(self, *writes, ready=(False, False), reset=False, offers=None):
        if offers is None:
            offers = tuple(Offer(True, w) for w in writes) + (Offer(),) * (2 - len(writes))
        inp = Inputs(tuple(offers), tuple(ready), reset)
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert post.event.tick == self.last_tick + 2, "unobserved EnterSbuffer cycle"
            self.last_tick = post.event.tick
            actual_inp = pre.value[0]
            assert actual_inp == post.value[0]
            if post.event.tick == edge.tick:
                assert actual_inp == inp
            record = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(actual_inp),
                      "post_input": asdict(post.value[0]), "before": pre.value[1], "after": post.value[1], "checked": False}
            try:
                record["expected_before"] = self.model.expected(actual_inp)
                if not actual_inp.reset:
                    self.compare(pre.value[1], record["expected_before"], "before")
                change = self.model.advance(actual_inp)
                record["change"] = change
                record["expected_after"] = self.model.expected(actual_inp)
                if not actual_inp.reset:
                    self.compare(post.value[1], record["expected_after"], "after")
                    record["checked"] = True
                self.coverage.observe(change, self.last_tick)
                self.pre_pins, self.pins = pre.value[1], post.value[1]
                self.pre_observed, self.observed = self.pre_pins, self.pins
                self.pre_response = self.driver.ports.observe(self.pre_pins)
                self.response = self.driver.ports.observe(self.pins)
                self.last_change = self._update_ledger(actual_inp, self.pre_response)
            except BaseException as exc:
                record["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(record) + "\n")
            if post.event.tick == edge.tick:
                return self.last_change

    def compare(self, actual, expected, phase):
        for name, value in expected.items():
            assert actual[name] == value, ("enter-sbuffer", self.last_tick, phase, name, actual[name], value)

    async def reset(self):
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(2)

    async def idle(self, count=1, **kwargs):
        return [await self.cycle(**kwargs) for _ in range(count)]

    def write(self, tag=1, *, credit=True):
        return Write((0xFEDCBA000000 | tag * 16) & ((1 << 48) - 1), (0x3ABCDEF000000 | tag * 32) & ((1 << 50) - 1),
                     ((0xFEDCBA98765432100123456789ABCDEF * tag) ^ tag) & ((1 << 128) - 1), (tag * 17027) & 65535, bool(tag % 2), credit)

    def _update_ledger(self, inp, observation):
        """Stimulus ledger from sampled requests and public response pulses.

        The reference ``change`` event list is never read here: consumption is
        the actual valid/ready fire at the pre-edge output, and acceptance is
        the actual offer/ready fire derived from the same sampled window.
        """
        before = list(self.live)
        if inp.reset:
            self.live.clear()
            return {"reset": True, "before": before, "accepted": [], "consumed": []}
        consumed = []
        for lane in range(2):
            word = observation.sbuffer_word_0 if lane == 0 else observation.sbuffer_word_1
            if word is None or not inp.ready[lane]:
                continue
            assert self.live, ("Sbuffer consumption without an owned write", lane)
            owner = self.live.pop(0)
            consumed.append(owner)
            write = owner["write"]
            assert (word.addr, word.vaddr, word.data, word.mask, word.wline) == (
                write["paddr"], write["vaddr"], write["data"], write["mask"], write["wline"]), (
                    "Sbuffer fire changed the original write", lane, owner, word)
            credit = bool(owner["write"]["credit"])
            actual = observation.deq_pointer_moves[lane]
            assert actual == int(credit), ("deqPtrMove differs from owned credit",
                                           lane, actual, credit, owner)
        old_count = len(self.live) + len(consumed)
        fires = []
        for lane, offer in enumerate(inp.offers):
            fire = bool(offer.valid and observation.accept_ready[lane])
            if lane and fire and not fires[0]:
                raise AssertionError("accepted lane1 without the required lane0 prefix")
            if fire:
                assert old_count - len(consumed) + len(fires) < 2, (
                    "acceptance outside the two owned places", lane)
            fires.append(fire)
        accepted = []
        for lane, offer in enumerate(inp.offers):
            if not fires[lane]:
                continue
            self.accepted_count += 1
            accepted.append({"uid": self.accepted_count, "input_lane": lane, "write": asdict(offer.write)})
        self.live.extend(accepted)
        return {"reset": False, "before": before, "accepted": accepted, "consumed": consumed}

    def expect(self, observation, why, *, before=False):
        expected = self.driver.ports.expected(observation)
        actual = self.pre_pins if before else self.pins
        difference = {name: [actual[name], value] for name, value in expected.items() if actual[name] != value}
        self.journal.write(json.dumps({"tick": self.last_tick, "phase": "before" if before else "after", "why": why,
                                       "expected": expected, "actual": {name: actual[name] for name in expected},
                                       "passed": not difference}) + "\n")
        assert not difference, ("enter-sbuffer-directed", self.last_tick, why, difference)

    def arm(self, names, uids=None):
        if uids is None:
            uids = [owner["uid"] for owner in self.live]
        self.coverage.arm(names, uids, self.last_tick)

    async def drain(self):
        await self.idle(2, ready=(True, True))
        assert not self.live and self.response.empty
