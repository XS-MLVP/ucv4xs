"""Typed model-free review environment for the LoadQueueUncache parent DUT.

The review fixtures drive only public parent transactions (enqueue, bus fire,
ID/SID bind, data response, bypass consume).  Assertions in the review tests
read immutable snapshots, never the reference model or raw pin dictionaries.
"""
from __future__ import annotations

import json

from suites.memblock.lsq.testbenches.uncache_entry.transactions import QueuePtr
from suites.memblock.lsq.testbenches.uncache_entry.transactions import RobPtr


class ReviewLoadUncacheEnv:
    def __init__(self, ports, driver, before, after, nodeid):
        self.ports, self.driver, self.before, self.after = ports, driver, before, after
        self.nodeid = nodeid
        self.pending = RobPtr.encode(10)
        self.last_tick = -1
        self.last_input = {}
        self.pre, self.post = {}, {}
        self.pre_response = self.post_response = None
        self.wakes = set()
        self.events, self.checks, self.failures = [], [], []
        self.metadata = {}
        self.cycles = 0

    def _drive(self, values=None):
        drive = dict.fromkeys(self.ports.inputs, 0)
        drive.update(io_rob_pendingPtr_flag=int(self.pending.flag),
                     io_rob_pendingPtr_value=self.pending.value,
                     io_rob_pendingPtr_isFormer=int(self.pending.former))
        for name, value in (values or {}).items():
            if name not in drive:
                raise ValueError(f"not an actual parent input: {name}")
            drive[name] = int(value)
        return drive

    async def step(self, values=None, *, pending=None):
        if pending is not None:
            self.pending = pending
        drive = self._drive(values)
        self.last_input = drive
        edge = await self.driver.send(drive)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick
            assert self.last_tick < post.event.tick <= edge.tick
            self.last_tick = post.event.tick
            self.cycles += 1
            if post.event.tick == edge.tick:
                assert pre.value[0] == drive
            self.pre, self.post = pre.value[1], post.value[1]
            self.pre_response = self.ports.observe(self.pre)
            self.post_response = self.ports.observe(self.post)
            for kind in ("nc", "mmio"):
                if self.pre[f"io_{kind}Wakeup_valid"]:
                    self.wakes.add((kind, bool(self.pre[f"io_{kind}Wakeup_bits_flag"]),
                                    self.pre[f"io_{kind}Wakeup_bits_value"]))
            if post.event.tick == edge.tick:
                return self.post_response

    async def idle(self, count=1):
        for _ in range(count):
            await self.step()

    def event(self, name, **fields):
        self.events.append(dict(event=name, tick=self.last_tick, **fields))

    def check(self, label, actual, expected, *, fatal=True):
        row = dict(label=label, tick=self.last_tick, actual=actual, expected=expected,
                   passed=actual == expected)
        self.checks.append(row)
        if not row["passed"]:
            self.failures.append(row)
            if fatal:
                raise AssertionError(("load-uncache-review", label, self.last_tick, actual, expected))

    def finish(self):
        assert self.checks, "a review without obligations is not evidence"
        assert not self.failures, ("load-uncache-review", self.failures)

    async def enqueue(self, owner, lane, *, pending=None):
        fields = {f"io_req_{lane}_valid": 1,
                  f"io_req_{lane}_bits_uop_robIdx_value": owner["rob"],
                  f"io_req_{lane}_bits_uop_robIdx_isFormer": 1,
                  f"io_req_{lane}_bits_uop_lqIdx_value": owner["lq"],
                  f"io_req_{lane}_bits_uop_ftqOffset": 2 * owner["uid"] - 1,
                  f"io_req_{lane}_bits_uop_perfDebugInfo_runahead_checkpoint_id": owner["uid"],
                  f"io_req_{lane}_bits_vaddr": owner["va"],
                  f"io_req_{lane}_bits_fullva": owner["va"],
                  f"io_req_{lane}_bits_paddr": owner["pa"],
                  f"io_req_{lane}_bits_mask": 255,
                  f"io_req_{lane}_bits_nc": 1,
                  f"io_req_{lane}_bits_rep_info_need_rep": 1,
                  f"io_req_{lane}_bits_rep_info_cause_0": 1}
        await self.step(fields, pending=pending)

    async def bus_fire(self, sid, owner):
        for _ in range(60):
            if self.post_response.request is not None:
                break
            await self.step()
        request = self.post_response.request
        self.check("bus request offered", request is not None, True)
        await self.step({"io_uncache_req_ready": 1})
        self.check("request actual fire", self.pre_response.request is not None, True)
        self.check("bus owner", (self.pre_response.request.addr, self.pre_response.request.vaddr,
                                 self.pre_response.request.mask, self.pre_response.request.nc,
                                 self.pre_response.request.rob.value),
                   (owner["pa"], owner["va"], 255, 1, owner["rob"]))
        mid = self.pre_response.request.mid
        self.event("bus_request_fire", uid=owner["uid"], mid=mid, PA=owner["pa"], VA=owner["va"])
        await self.step({"io_uncache_idResp_valid": 1, "io_uncache_idResp_bits_mid": mid,
                         "io_uncache_idResp_bits_sid": sid})
        self.event("SID_ack", uid=owner["uid"], mid=mid, sid=sid)
        return mid

    async def respond(self, owner, sid, data, *, error=False, nderr=False):
        await self.step({"io_uncache_resp_valid": 1, "io_uncache_resp_bits_id": sid,
                         "io_uncache_resp_bits_data": data,
                         "io_uncache_resp_bits_error": int(error),
                         "io_uncache_resp_bits_nderr": int(nderr)})
        self.event("response_valid_SID_returned", uid=owner["uid"], sid=sid, data=data,
                   error=bool(error), nderr=bool(nderr))
        key = ("nc", False, owner["lq"])
        for _ in range(40):
            if key in self.wakes:
                break
            await self.step()
        self.check("original LQ wakeup", key in self.wakes, True)
        return key

    async def bypass(self, lane, owner, *, nc=True, mmio=False, redirect=None, self_flush=False):
        fields = {f"io_bypass_{lane}_s0Req_valid": 1,
                  f"io_bypass_{lane}_s0Req_bits_lqIdx_value": owner["lq"],
                  f"io_bypass_{lane}_s0Req_bits_isNCReplay": int(nc),
                  f"io_bypass_{lane}_s0Req_bits_isMMIOReplay": int(mmio)}
        if redirect is not None:
            fields.update({"io_redirect_valid": 1,
                           "io_redirect_bits_robIdx_flag": int(redirect.flag),
                           "io_redirect_bits_robIdx_value": redirect.value,
                           "io_redirect_bits_robIdx_isFormer": int(redirect.former),
                           "io_redirect_bits_level": int(self_flush)})
        await self.step(fields)
        return self.post_response

    async def bypass_many(self, owners):
        """Drive several real bypass s0 requests in one parent cycle."""
        fields = {}
        for lane, owner in owners.items():
            fields.update({f"io_bypass_{lane}_s0Req_valid": 1,
                           f"io_bypass_{lane}_s0Req_bits_lqIdx_value": owner["lq"],
                           f"io_bypass_{lane}_s0Req_bits_isNCReplay": 1})
        await self.step(fields)
        return self.post_response

    def request_input_valid(self, lane):
        return bool(self.last_input.get(f"io_req_{lane}_valid", 0))

    def witness(self):
        return dict(format="lsq-load-uncache-review-v1", dut="load_queue_uncache",
                    nodeid=self.nodeid, metadata=self.metadata, sampled_cycles=self.cycles,
                    events=self.events, checks=self.checks, failures=self.failures,
                    no_model_or_private_state_oracle=True)
