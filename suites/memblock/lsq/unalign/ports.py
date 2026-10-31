import json

from suites.memblock.lsq.native import ROOT
from suites.memblock.lsq.raw.types import SqPtr
from .types import Inputs, Recovery, Request, encode


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
        walk(json.loads((ROOT / "dut/unalign_queue/signals.json").read_text()))
        assert len(self.inputs) == 19 and set(self.inputs) == set(encode(Inputs()))

    def sample(self, event):
        values = {name: pin.U() for name, pin in self.inputs.items()}
        def pointer(prefix):
            return SqPtr(bool(values[prefix + "first_flag"]), bool(values[prefix + "second_flag"]), values[prefix + "value"])
        requests = tuple(Request(bool(values[f"io_fromStaS1_{lane}_valid"]), pointer(f"io_fromStaS1_{lane}_bits_sqIdx_"),
                                 values[f"io_fromStaS1_{lane}_bits_paddr"]) for lane in range(2))
        inp = Inputs(requests, pointer("io_fromSQ_addrReadyPtr_"), bool(values["io_toDeqModule_ready"]),
                     Recovery(bool(values["io_redirect_valid"]), pointer("io_redirect_bits_")), bool(values["reset"]))
        return inp, {name: pin.U() for name, pin in self.outputs.items()}
