"""Independent public-pin probes; no LSQ reference-model predictions."""
import hashlib
import json

import pytest
from toffee import DriveStable, Execution, FallingEdge, RisingEdge, SamplingMonitor, SyncDriver, XCommClockBackend

from lsqverify.native import ROOT


class ReviewPorts:
    def __init__(self, dut, key):
        self.dut = dut
        self.inputs, self.outputs = {}, {}

        def walk(node, prefix=()):
            if "Pin" in node:
                name = "_".join(prefix)
                if name != "clock":
                    target = self.inputs if node["Pin"] == "input" else self.outputs
                    target[name] = getattr(dut, name)
                return
            for name, child in node.items():
                if isinstance(child, dict):
                    walk(child, (*prefix, name))

        walk(json.loads((ROOT / "dut" / key / "signals.json").read_text()))

    def sample(self, event):
        return ({name: pin.U() for name, pin in self.inputs.items()},
                {name: pin.U() for name, pin in self.outputs.items()})


class PinDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(tuple(ports.inputs.values()), name="fail-review-public-pins")

    async def _drive_one(self, values):
        assert set(values) == set(self.ports.inputs)
        await FallingEdge(self.ports.dut.clock)
        for name, pin in self.ports.inputs.items():
            pin.Set(values[name])
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            for name, pin in self.ports.inputs.items():
                if name == "reset" or name.endswith("valid") or name.endswith("ready"):
                    pin.Set(0)


class ReviewEnv:
    def __init__(self, key, nodeid, ports, driver, before, after):
        self.key, self.nodeid, self.ports = key, nodeid, ports
        self.driver, self.before, self.after = driver, before, after
        self.tick, self.cycles = -1, 0
        self.pre, self.post, self.input = {}, {}, {}
        self.events, self.checks, self.failures, self.wakes = [], [], [], set()
        self.metadata = {}
        self.digest = hashlib.sha256()
        self.probe_completed = False

    async def step(self, values=None):
        drive = dict.fromkeys(self.ports.inputs, 0)
        assert set(values or ()) <= set(drive), set(values or ()) - set(drive)
        drive.update({name: int(value) for name, value in (values or {}).items()})
        edge = await self.driver.send(drive)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.tick < post.event.tick <= edge.tick
            assert pre.value[0] == post.value[0]
            if post.event.tick == edge.tick:
                assert pre.value[0] == drive, "requested input must equal actually sampled pins"
            self.tick, self.input = post.event.tick, pre.value[0]
            self.pre, self.post = pre.value[1], post.value[1]
            self.cycles += 1
            self.digest.update(json.dumps([self.tick, self.input, self.pre, self.post], sort_keys=True).encode())
            for kind in ("nc", "mmio"):
                prefix = f"io_{kind}Wakeup_"
                if self.pre.get(prefix + "valid", 0):
                    identity = (kind, self.pre[prefix + "bits_flag"], self.pre[prefix + "bits_value"])
                    self.wakes.add(identity)
                    self.event("wakeup", kind=kind, LQ_flag=identity[1], LQ_value=identity[2])
            if post.event.tick == edge.tick:
                return self.post

    async def idle(self, count=1, values=None):
        for _ in range(count):
            await self.step(values)

    def event(self, name, **fields):
        self.events.append(dict(event=name, tick=self.tick, **fields))

    def check(self, name, actual, expected, *, fatal=True):
        row = dict(label=name, tick=self.tick, actual=actual, expected=expected, passed=actual == expected)
        self.checks.append(row)
        if not row["passed"]:
            self.failures.append(row)
            if fatal:
                raise AssertionError(("independent-public-contract", name, self.tick, actual, expected))

    def finish(self):
        self.probe_completed = True
        assert self.checks, "a probe without obligations is not evidence"
        assert not self.failures, ("independent-public-contract", self.key, self.failures)

    def save(self, path):
        result = dict(format="lsq-independent-fail-review-witness-v1", dut=self.key, nodeid=self.nodeid,
            metadata=self.metadata, probe_completed=self.probe_completed, sampled_cycles=self.cycles,
            checked_pin_stream_SHA256=self.digest.hexdigest(), events=self.events, checks=self.checks,
            failures=self.failures, no_model_or_private_state_oracle=True,
            scope="Named public protocol obligations, not a general full-output reference. Deferred checks retain every mismatch and still produce an ordinary FAIL. No per-cycle trace or waveform.")
        with path.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")


@pytest.fixture
async def review_dut(request, dut_factory, tmp_path):
    key = request.param
    dut = dut_factory.create(key)
    ports = ReviewPorts(dut, key)
    driver = PinDriver(ports)
    before = SamplingMonitor(DriveStable(dut.clock), capture=ports.sample, capacity=8)
    after = SamplingMonitor(RisingEdge(dut.clock), capture=ports.sample, capacity=8)
    backend = XCommClockBackend(dut.GetXClock())
    env = ReviewEnv(key, request.node.nodeid, ports, driver, before, after)
    try:
        async with Execution(backend, max_batch_ticks=16) as execution:
            async with driver, before.start(execution), after.start(execution):
                for _ in range(6):
                    await env.step({"reset": 1})
                await env.idle(3)
                yield env
    finally:
        env.save(tmp_path / "fail-review-witness.json")
        backend.close()
