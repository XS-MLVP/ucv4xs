from dataclasses import asdict, replace
import json

from lsqverify.raw.types import SqPtr
from .types import Inputs, Query, Store, Translation, byte_count


class ForwardEnv:
    def __init__(self, driver, before, after, model, coverage, journal, *, nodeid):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.controls = Inputs()
        self.nodeid = nodeid
        self.last_tick = -1
        self.last_change = self.observed = self.pre_observed = None

    async def cycle(self, queries=None, translations=None, **controls):
        self.controls = replace(self.controls, **controls)
        queries = tuple((queries or {}).get(lane, Query()) for lane in range(3)) if isinstance(queries, (dict, type(None))) else tuple(queries)
        translations = tuple((translations or {}).get(lane, Translation()) for lane in range(3)) if isinstance(translations, (dict, type(None))) else tuple(translations)
        inp = replace(self.controls, queries=queries, translations=translations)
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert post.event.tick == self.last_tick + 2, "unobserved Forward cycle"
            self.last_tick = post.event.tick
            actual_inp = pre.value[0]
            assert actual_inp == post.value[0]
            if post.event.tick == edge.tick:
                assert actual_inp == inp
            row = {"nodeid": self.nodeid, "pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(actual_inp), "post_input": asdict(post.value[0]),
                   "before": pre.value[1], "after": post.value[1], "checked": False}
            try:
                row["expected_before"] = self.model.expected(actual_inp)
                self.compare(pre.value[1], row["expected_before"], "before")
                row["physical_safety_before"] = self.model.check_physical_safety(actual_inp, pre.value[1])
                row["change"] = change = self.model.advance(actual_inp)
                row["expected_after"] = self.model.expected(actual_inp)
                self.compare(post.value[1], row["expected_after"], "after")
                row["physical_safety_after"] = self.model.check_physical_safety(actual_inp, post.value[1])
                row["checked"] = self.model.edges >= 2
                self.coverage.observe(change, self.last_tick)
                self.last_change, self.observed, self.pre_observed = change, post.value[1], pre.value[1]
            except BaseException as exc:
                row["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(row) + "\n")
            if post.event.tick == edge.tick:
                return change

    def compare(self, actual, expected, phase):
        for name, value in expected.items():
            assert actual[name] == value, ("forward-cycle", self.last_tick, phase, name, actual[name], value)

    async def boot(self):
        for _ in range(3):
            await self.cycle()

    async def idle(self, count=1):
        return [await self.cycle() for _ in range(count)]

    def bank(self, mapping):
        return tuple(mapping.get(slot, Store()) for slot in range(64))

    def store(self, *, vaddr=0x10000, page=0xABC, size=3, data=0x8877665544332211, mask=None, ready=True):
        length = byte_count(size)
        return Store(size, vaddr, page, (1 << length) - 1 if mask is None else mask, data, 0, ready, True,
                     vaddr % 16 + length > 16, False)

    def query(self, *, vaddr=0x10000, sq=1, size=3, **kwargs):
        return Query(True, vaddr, SqPtr.encode(sq), size, **kwargs)

    def arm(self, names, uids=None):
        if uids is None:
            uids = [job["uid"] for job in self.last_change["accepted"]]
        self.coverage.arm(names, uids, self.last_tick)

    async def request(self, query, paddr, *, lane=0, scenes=(), stores=None):
        change = await self.cycle({lane: query}, **({"stores": stores} if stores is not None else {}))
        uid = change["accepted"][0]["uid"]
        if scenes:
            self.arm(scenes, [uid])
        change = await self.cycle(translations={lane: Translation(paddr)})
        assert any(answer["uid"] == uid for answer in change["responses"])
        await self.idle(2)
        return uid
