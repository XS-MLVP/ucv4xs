from dataclasses import asdict
import json

from .types import Inputs, Offer, Write


class EnterSbufferEnv:
    def __init__(self, driver, before, after, model, coverage, journal):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.last_tick = -1
        self.last_change = self.observed = self.pre_observed = None

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
                self.last_change = change
                self.pre_observed, self.observed = pre.value[1], post.value[1]
            except BaseException as exc:
                record["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(record) + "\n")
            if post.event.tick == edge.tick:
                return change

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

    def arm(self, names, uids=None):
        if uids is None:
            uids = [owner.uid for owner in self.model.order]
        self.coverage.arm(names, uids, self.last_tick)

    async def drain(self):
        await self.idle(2, ready=(True, True))
        assert not self.model.order and self.observed["io_empty"]
