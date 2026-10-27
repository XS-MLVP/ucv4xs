import json

from lsqverify.native import ROOT
from .types import Inputs, Offer, Write, encode


class Ports:
    def __init__(self, dut):
        self.dut, self.inputs, self.outputs = dut, {}, {}
        def walk(node, prefix=()):
            if "Pin" in node:
                name = "_".join(prefix)
                if name != "clock":
                    (self.inputs if node["Pin"] == "input" else self.outputs)[name] = getattr(dut, name)
            else:
                for name, child in node.items():
                    if isinstance(child, dict):
                        walk(child, (*prefix, name))
        walk(json.loads((ROOT / "dut/enter_sbuffer_queue/signals.json").read_text()))
        assert set(self.inputs) == set(encode(Inputs())) and len(self.inputs) == 16

    def sample(self, event):
        values = {name: pin.U() for name, pin in self.inputs.items()}
        offers = []
        for lane in range(2):
            prefix = f"io_fromDeqModule_{lane}_"
            get = lambda key: values[prefix + "bits_" + key]
            write = Write(get("addr"), get("vaddr"), get("data"), get("mask"), bool(get("wline")), bool(get("deqPtrMove")) if lane == 0 else True)
            offers.append(Offer(bool(values[prefix + "valid"]), write))
        inp = Inputs(tuple(offers), tuple(bool(values[f"io_toSbuffer_req_{lane}_ready"]) for lane in range(2)), bool(values["reset"]))
        return inp, {name: pin.U() for name, pin in self.outputs.items()}
