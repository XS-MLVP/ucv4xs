import json

from suites.memblock.lsq.native import ROOT
from .types import Inputs, encode


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
        walk(json.loads((ROOT / "dut/physical_store_queue/signals.json").read_text()))
        assert len(self.inputs) == 119 and len(self.outputs) == 333 and set(self.inputs) == set(encode(Inputs()))

    def sample(self, event):
        # Raw public input capture is intentionally separate from the encoder;
        # no roundtrip through domain objects is used to hide a binding error.
        return ({name: pin.U() for name, pin in self.inputs.items()}, {name: pin.U() for name, pin in self.outputs.items()})
