"""Two-place ordered write ledger with credit-on-consumption semantics."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Owner:
    uid: int
    input_lane: int
    write: object


class EnterSbufferModel:
    def __init__(self):
        self.order = []
        self.sequence = 0

    def expected(self, inp):
        fires = [lane < len(self.order) and inp.ready[lane] for lane in range(2)]
        capacity = 2 - len(self.order) + sum(fires)
        out = {"io_empty": int(not self.order)}
        for lane in range(2):
            prefix = f"io_toSbuffer_req_{lane}_"
            out[prefix + "valid"] = int(lane < len(self.order))
            out[f"io_fromDeqModule_{lane}_ready"] = int(capacity > lane)
            out[f"io_deqPtrMove_{lane}"] = int(fires[lane] and self.order[lane].write.credit)
            if lane < len(self.order):
                write = self.order[lane].write
                out.update({prefix + "bits_" + name: int(getattr(write, field)) for name, field in
                            (("addr", "paddr"), ("vaddr", "vaddr"), ("data", "data"), ("mask", "mask"), ("wline", "wline"))})
        return out

    def advance(self, inp):
        before = [asdict(owner) for owner in self.order]
        if inp.reset:
            self.order.clear()
            return {"reset": True, "before": before, "accepted": [], "consumed": []}
        expected = self.expected(inp)
        count = sum(lane < len(self.order) and inp.ready[lane] for lane in range(2))
        consumed = [asdict(owner) for owner in self.order[:count]]
        del self.order[:count]
        accepted = []
        for lane, offer in enumerate(inp.offers):
            if offer.valid and expected[f"io_fromDeqModule_{lane}_ready"]:
                self.sequence += 1
                owner = Owner(self.sequence, lane, offer.write)
                self.order.append(owner)
                accepted.append(asdict(owner))
        assert len(self.order) <= 2
        return {"reset": False, "before": before, "accepted": accepted, "consumed": consumed}
