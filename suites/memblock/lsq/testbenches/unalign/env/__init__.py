from dataclasses import asdict, dataclass
import json

from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.unalign.transactions import Inputs
from suites.memblock.lsq.testbenches.unalign.transactions import Recovery
from suites.memblock.lsq.testbenches.unalign.transactions import Request
from suites.memblock.lsq.testbenches.unalign.transactions import canceled
from suites.memblock.lsq.testbenches.unalign.transactions import distance


@dataclass(frozen=True)
class LiveSecondPage:
    uid: int
    slot: int
    input_lane: int
    request: Request


class UnalignEnv:
    def __init__(self, driver, before, after, model, coverage, journal):
        self.driver, self.before, self.after, self.model, self.coverage, self.journal = driver, before, after, model, coverage, journal
        self.last_tick = -1
        self.pins = self.pre_pins = None
        self.last_change = self.observed = self.pre_observed = None
        self.response = self.pre_response = None
        # Public second-page ownership ledger rebuilt only from sampled
        # requests plus observed acceptance/consumption/cancellation.
        self.live = []
        self.tail = 0
        self.sequence = 0

    async def cycle(self, requests=None, *, address_ready=SqPtr(), ready=False, redirect=Recovery(), reset=False):
        if requests is None:
            requests = (Request(),) * 2
        elif isinstance(requests, dict):
            requests = tuple(requests.get(lane, Request()) for lane in range(2))
        inp = Inputs(tuple(requests), address_ready, ready, redirect, reset)
        self.validate_transactions(inp)
        edge = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert post.event.tick == self.last_tick + 2, "unobserved Unalign cycle"
            self.last_tick = post.event.tick
            observed_inp = pre.value[0]
            assert observed_inp == post.value[0]
            if post.event.tick == edge.tick:
                assert observed_inp == inp
            row = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(observed_inp), "post_input": asdict(post.value[0]),
                   "before": pre.value[1], "after": post.value[1], "checked": False}
            try:
                row["expected_before"] = self.model.expected(observed_inp)
                if not observed_inp.reset:
                    self.compare(pre.value[1], row["expected_before"], "before")
                change = self.model.advance(observed_inp)
                row["change"] = change
                row["expected_after"] = self.model.expected(observed_inp)
                if not observed_inp.reset:
                    self.compare(post.value[1], row["expected_after"], "after")
                    row["checked"] = True
                self.coverage.observe(change, self.last_tick, self.model.sequence)
                self.pre_pins, self.pins = pre.value[1], post.value[1]
                self.pre_observed, self.observed = self.pre_pins, self.pins
                self.pre_response = self.driver.ports.observe(self.pre_pins)
                self.response = self.driver.ports.observe(self.pins)
                self.last_change = self._update_ledger(observed_inp, self.pre_response)
            except BaseException as exc:
                row["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(row) + "\n")
            if post.event.tick == edge.tick:
                return self.last_change

    def compare(self, actual, expected, phase):
        for key, value in expected.items():
            assert actual[key] == value, ("unalign", self.last_tick, phase, key, actual[key], value)

    async def reset(self):
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(2)

    async def idle(self, count=1, **kwargs):
        return [await self.cycle(**kwargs) for _ in range(count)]

    def request(self, sq=7, *, page=0xFEDCBA987, offset=0xABC):
        return Request(True, SqPtr.encode(sq), page << 12 | offset)

    async def enqueue(self, req, *, lane=0, **kwargs):
        return await self.cycle({lane: req}, address_ready=req.sq, **kwargs)

    def validate_transactions(self, inp):
        """Reject illegal second-page transaction sequences before driving."""
        if inp.reset:
            return
        ready = tuple(len(self.live) < 2 and not inp.redirect.valid and req.sq == inp.address_ready
                      for req in inp.requests)
        accepted = [req for lane, req in enumerate(inp.requests) if req.valid and ready[lane]]
        if len(accepted) > 1:
            raise ValueError("only one second-page request may actually fire")
        cancel = [canceled(owner.request.sq, inp.redirect) for owner in self.live]
        if any(cancel[i] and not cancel[j] for i in range(len(cancel)) for j in range(i + 1, len(cancel))):
            raise ValueError("SQ recovery must remove a suffix, not a hole")
        if cancel and cancel[0] and inp.ready:
            raise ValueError("a committed head consumption cannot also be canceled")
        if accepted and self.live and not 0 < distance(accepted[0].sq, self.live[-1].request.sq) < 128:
            raise ValueError("accepted second-page stores must be in SQ program order")

    def _update_ledger(self, inp, observation):
        """Stimulus ledger from sampled requests and public response windows."""
        before = [asdict(owner) for owner in self.live]
        if inp.reset:
            self.live.clear()
            self.tail = 0
            return {"reset": True, "before": before, "accepted": [], "consumed": [], "canceled": []}
        consumed = []
        if observation.to_deq is not None and inp.ready:
            assert self.live, "toDeqModule consumed a request this environment does not own"
            owner = self.live.pop(0)
            assert owner.request.paddr & ~((1 << 12) - 1) == observation.to_deq.paddr, (
                "consumed second page differs from the owned request", owner, observation.to_deq)
            assert owner.request.sq == observation.to_deq.sq, (
                "consumed SQ identity differs from the owned request", owner, observation.to_deq)
            consumed.append(asdict(owner))
        removed = [owner for owner in self.live if canceled(owner.request.sq, inp.redirect)]
        if removed:
            assert all(owner in self.live for owner in removed)
            for owner in removed:
                self.live.remove(owner)
            self.tail -= len(removed)
        accepted = []
        for lane, req in enumerate(inp.requests):
            if not req.valid or not observation.accept_ready[lane]:
                continue
            self.sequence += 1
            owner = LiveSecondPage(self.sequence, self.tail % 2, lane, req)
            self.live.append(owner)
            accepted.append(asdict(owner))
            self.tail += 1
        assert len(self.live) <= 2, ("more accepted second pages than the two real places", self.live)
        return {"reset": False, "before": before, "accepted": accepted, "consumed": consumed,
                "canceled": [asdict(owner) for owner in removed]}

    def arm(self, names, owners=None, *, reuse=False):
        if owners is None:
            owners = [asdict(x) for x in self.live]
        self.coverage.arm(names, owners, self.last_tick, self.sequence, reuse=reuse)

    async def drain(self):
        await self.idle(3, ready=True)
        assert not self.live and self.response.to_deq is None
        assert self.response.forward_entries == (None, None)
