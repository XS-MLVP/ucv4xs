"""Ordered cross-page second-address ownership, never a DUT register oracle."""
from dataclasses import asdict, dataclass

from .types import canceled, distance


@dataclass(frozen=True)
class Owner:
    uid: int
    slot: int
    input_lane: int
    request: object


class UnalignModel:
    def __init__(self):
        self.order = []
        self.tail = self.sequence = 0

    def expected(self, inp):
        result = {"io_toDeqModule_valid": int(bool(self.order))}
        for lane, req in enumerate(inp.requests):
            result[f"io_fromStaS1_{lane}_ready"] = int(len(self.order) < 2 and not inp.redirect.valid and req.sq == inp.address_ready)
        def packet(prefix, owner):
            req = owner.request
            result.update({prefix + "paddr": req.paddr & ~4095, prefix + "sqIdx_first_flag": int(req.sq.first),
                           prefix + "sqIdx_second_flag": int(req.sq.second), prefix + "sqIdx_value": req.sq.value})
        if self.order:
            packet("io_toDeqModule_bits_", self.order[0])
        for slot in range(2):
            owner = next((owner for owner in self.order if owner.slot == slot), None)
            result[f"io_forwardValid_{slot}"] = int(owner is not None)
            if owner:
                packet(f"io_forwardEntries_{slot}_", owner)
        return result

    def validate(self, inp):
        if inp.reset:
            return
        expected = self.expected(inp)
        accepted = [req for lane, req in enumerate(inp.requests) if req.valid and expected[f"io_fromStaS1_{lane}_ready"]]
        if len(accepted) > 1:
            raise ValueError("only one second-page request may actually fire")
        cancel = [canceled(owner.request.sq, inp.redirect) for owner in self.order]
        if any(cancel[i] and not cancel[j] for i in range(len(cancel)) for j in range(i + 1, len(cancel))):
            raise ValueError("SQ recovery must remove a suffix, not a hole")
        if cancel and cancel[0] and inp.ready:
            raise ValueError("a committed head consumption cannot also be canceled")
        if accepted and self.order and not 0 < distance(accepted[0].sq, self.order[-1].request.sq) < 128:
            raise ValueError("accepted second-page stores must be in SQ program order")

    def advance(self, inp):
        before = [asdict(owner) for owner in self.order]
        if inp.reset:
            self.order, self.tail = [], 0
            return {"reset": True, "before": before, "accepted": [], "consumed": [], "canceled": []}
        self.validate(inp)
        expected = self.expected(inp)
        removed = [owner for owner in self.order if canceled(owner.request.sq, inp.redirect)]
        consumed = self.order[:1] if self.order and inp.ready else []
        self.order = [owner for owner in self.order if owner not in removed and owner not in consumed]
        self.tail -= len(removed)
        accepted = []
        for lane, req in enumerate(inp.requests):
            if not req.valid or not expected[f"io_fromStaS1_{lane}_ready"]:
                continue
            self.sequence += 1
            owner = Owner(self.sequence, self.tail % 2, lane, req)
            assert all(old.slot != owner.slot for old in self.order)
            self.tail += 1
            self.order.append(owner)
            accepted.append(owner)
        assert len(self.order) <= 2
        return {"reset": False, "before": before, "accepted": [asdict(x) for x in accepted],
                "consumed": [asdict(x) for x in consumed], "canceled": [asdict(x) for x in removed]}
