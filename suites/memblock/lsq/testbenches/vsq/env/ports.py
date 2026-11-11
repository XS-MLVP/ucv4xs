import json

from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.transactions import Dispatch
from suites.memblock.lsq.testbenches.vsq.transactions import Inputs
from suites.memblock.lsq.testbenches.vsq.transactions import encode
from suites.memblock.lsq.testbenches.vsq.transactions import Observation


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
        walk(json.loads((ROOT / "dut/virtual_store_queue/signals.json").read_text()))
        assert len(self.inputs) == 85 and len(self.outputs) == 19 and set(self.inputs) == set(encode(Inputs()))

    def sample(self, event):
        pins = {name: pin.U() for name, pin in self.inputs.items()}
        def sq(prefix):
            return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])
        def rob(prefix):
            return RobPtr(bool(pins[prefix + "flag"]), pins[prefix + "value"], bool(pins[prefix + "isFormer"]))
        requests = []
        for lane in range(8):
            prefix = f"io_enq_req_{lane}_"
            requests.append(Dispatch(bool(pins[prefix + "valid"]), bool(pins[prefix + "bits_needAlloc"]), rob(prefix + "bits_uop_robIdx_"),
                                     pins[prefix + "bits_uop_numLsElem"], sq(prefix + "bits_reqEndPtr_sqIdx_")))
        inp = Inputs(tuple(requests), rob("io_fromRob_robHeadPtr_"), sq("io_fromPhysicalQueue_deqPtr_"), bool(pins["io_fromPhysicalQueue_deqCount_valid"]),
                     Redirect(bool(pins["io_redirect_valid"]), rob("io_redirect_bits_robIdx_"), bool(pins["io_redirect_bits_level"])), bool(pins["reset"]))
        return inp, {name: pin.U() for name, pin in self.outputs.items()}

    def observe(self, pins):
        """Decode one sampled public window into immutable transactions."""
        def sq(prefix):
            return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])

        return Observation(
            bool(pins["io_empty"]), bool(pins["io_sqRecoverStall"]),
            RobPtr(bool(pins["io_toPhysicalQueue_headRobIdx_flag"]), pins["io_toPhysicalQueue_headRobIdx_value"],
                   bool(pins["io_toPhysicalQueue_headRobIdx_isFormer"])),
            sq("io_toPhysicalQueue_physicalQueueEnqPtr_"), sq("io_toPhysicalQueue_retiredPtr_"),
            sq("io_toPhysicalQueue_preCommitPtr_bits_") if pins["io_toPhysicalQueue_preCommitPtr_valid"] else None,
            sq("io_toPhysicalQueue_redirectPtr_bits_") if pins["io_toPhysicalQueue_redirectPtr_valid"] else None)
