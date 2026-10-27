from dataclasses import asdict, replace
import json

from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import Redirect, RobPtr
from .types import Dispatch, Inputs


class VsqEnv:
    def __init__(self, driver, before, after, model, coverage, journal, nodeid):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.nodeid, self.controls, self.last_tick = nodeid, Inputs(), -1
        self.observed = self.last_change = None

    async def cycle(self, dispatch=None, redirect=Redirect(), consumed=False, reset=False, **controls):
        self.controls = replace(self.controls, **controls)
        requests = tuple((dispatch or {}).get(lane, Dispatch()) for lane in range(8)) if isinstance(dispatch, (dict, type(None))) else tuple(dispatch)
        inp = replace(self.controls, dispatch=requests, redirect=redirect, consumed=consumed, reset=reset)
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "unobserved VSQ cycle"
            self.last_tick = post.event.tick
            actual = pre.value[0]
            assert actual == post.value[0]
            if self.last_tick == edge.tick:
                assert actual == inp
            row = {"nodeid": self.nodeid, "pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(actual), "post_input": asdict(post.value[0]),
                   "before": pre.value[1], "after": post.value[1], "checked": False}
            try:
                row["expected_before"] = self.model.expected_before(actual)
                self.compare(pre.value[1], row["expected_before"], "before")
                row["change"] = change = self.model.advance(actual)
                row["expected_after"] = self.model.expected()
                self.compare(post.value[1], row["expected_after"], "after")
                row["checked"] = self.model.initialized
                self.coverage.observe(change, self.last_tick)
                self.observed, self.last_change = post.value[1], change
            except BaseException as exc:
                row["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(row) + "\n")
            if self.last_tick == edge.tick:
                return change

    def compare(self, actual, expected, phase):
        for name, value in expected.items():
            assert actual[name] == value, ("vsq-cycle", self.last_tick, phase, name, actual[name], value)

    async def boot(self):
        for _ in range(3):
            await self.cycle(reset=True)
        await self.cycle()

    async def idle(self, count=1, **controls):
        return [await self.cycle(**controls) for _ in range(count)]

    def requests(self, mapping):
        """lane -> (ROB ptr or entry integer, flow count); compact end snapshots."""
        end, result = self.model.allocated_end, {}
        for lane, (rob, flows) in sorted(mapping.items()):
            end += flows
            result[lane] = Dispatch(True, True, RobPtr.encode(rob) if isinstance(rob, int) else rob, flows, SqPtr.encode(end))
        return result

    def arm(self, names, uids=None):
        self.coverage.arm(names, uids or [item["uid"] for item in self.last_change["accepted"]], self.last_tick)

    async def drain(self, rob_head, limit=40):
        await self.cycle(rob_head=rob_head)
        for _ in range(limit):
            await self.cycle()
            if not self.model.outstanding and self.observed["io_empty"] and not self.observed["io_sqRecoverStall"]:
                await self.idle(3)
                return
        raise AssertionError("VSQ did not drain by actual retired/empty outputs")
