"""Model-free RAR review environment driven by typed public transactions."""
from __future__ import annotations

from dataclasses import asdict

from suites.memblock.lsq.testbenches.rar.transactions import Inputs
from suites.memblock.lsq.testbenches.rar.transactions import Query
from suites.memblock.lsq.testbenches.rar.transactions import QueuePtr
from suites.memblock.lsq.testbenches.rar.transactions import Redirect
from suites.memblock.lsq.testbenches.rar.transactions import Release


class ReviewRarEnv:
    def __init__(self, spec, driver, before, after, nodeid):
        self.spec, self.driver, self.before, self.after = spec, driver, before, after
        self.nodeid = nodeid
        self.controls = Inputs((Query(),) * spec["query_width"], (False,) * spec["query_width"],
                               (False,) * spec["query_width"])
        self.last_tick = -1
        self.pre_response = self.post_response = None
        self.events, self.checks, self.failures = [], [], []
        self.metadata = {}

    async def step(self, queries=None, *, head=None, release=None, redirect=None, reset=False,
                   revoke_last=(), revoke_older=()):
        if isinstance(queries, dict):
            queries = tuple(queries.get(lane, Query()) for lane in range(self.spec["query_width"]))
        elif queries is None:
            queries = (Query(),) * self.spec["query_width"]
        self.controls = Inputs(
            tuple(queries),
            tuple(lane in revoke_last for lane in range(self.spec["query_width"])),
            tuple(lane in revoke_older for lane in range(self.spec["query_width"])),
            self.controls.head if head is None else head,
            Redirect() if redirect is None else redirect,
            Release() if release is None else release,
            reset)
        edge = await self.driver.send(self.controls)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            self.last_tick = post.event.tick
            self.pre_response, self.post_response = pre.value[1], post.value[1]
            if post.event.tick == edge.tick:
                return self.post_response

    async def idle(self, count=1, **fields):
        for _ in range(count):
            await self.step(**fields)

    def event(self, name, **fields):
        self.events.append(dict(event=name, tick=self.last_tick, **fields))

    def check(self, name, actual, expected, *, fatal=True):
        row = dict(label=name, tick=self.last_tick, actual=actual, expected=expected, passed=actual == expected)
        self.checks.append(row)
        if not row["passed"]:
            self.failures.append(row)
            if fatal:
                raise AssertionError(("independent-rar-contract", name, self.last_tick, actual, expected))

    def finish(self):
        assert self.checks, "a probe without obligations is not evidence"
        assert not self.failures, ("independent-rar-contract", self.failures)

    def witness(self):
        return dict(format="lsq-independent-rar-review-v1", dut="load_queue_rar", nodeid=self.nodeid,
                    sampled_cycles=self.last_tick, events=self.events, checks=self.checks,
                    metadata=self.metadata, failures=self.failures, no_model_or_private_state_oracle=True)
