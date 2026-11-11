import json

from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.forward.env.codec import encode
from suites.memblock.lsq.testbenches.forward.transactions import Inputs
from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Store
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.forward.transactions import SecondPage
from suites.memblock.lsq.testbenches.forward.transactions import Response
from suites.memblock.lsq.testbenches.forward.transactions import Observation


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
        walk(json.loads((ROOT / "dut/forward_module/signals.json").read_text()))
        assert set(self.inputs) == set(encode(Inputs())) and len(self.inputs) == 695 and len(self.outputs) == 129

    def sample(self, event):
        pins = {name: pin.U() for name, pin in self.inputs.items()}
        def ptr(prefix):
            return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])
        queries, translations, stores, pages = [], [], [], []
        for lane in range(3):
            prefix = f"io_query_{lane}_"
            queries.append(Query(bool(pins[prefix + "s0Req_valid"]), pins[prefix + "s0Req_bits_vaddr"], ptr(prefix + "s0Req_bits_sqIdx_"),
                                 pins[prefix + "s0Req_bits_size"], bool(pins[prefix + "s0Req_bits_loadWaitBit"]), bool(pins[prefix + "s0Req_bits_loadWaitStrict"]), ptr(prefix + "s0Req_bits_waitSqIdx_")))
            translations.append(Translation(pins[prefix + "s1Req_paddr"], bool(pins[prefix + "s1Kill"])))
        for slot in range(64):
            data, ctrl = f"io_dataEntriesIn_{slot}_", f"io_ctrlEntriesIn_{slot}_"
            stores.append(Store(pins[data + "size"], pins[data + "vaddr"], pins[data + "paddrHigh"], pins[data + "byteMask"], pins[data + "data"], pins[data + "cboType"],
                                bool(pins[ctrl + "dataValid"]), bool(pins[ctrl + "addrValid"]), bool(pins[ctrl + "cross16Byte"]), bool(pins[ctrl + "isCbo"])))
        for index in range(2):
            pages.append(SecondPage(bool(pins[f"io_unalignValidIn_{index}"]), pins[f"io_unalignEntriesIn_{index}_paddr"], ptr(f"io_unalignEntriesIn_{index}_sqIdx_")))
        inp = Inputs(tuple(queries), tuple(translations), tuple(stores), tuple(pages), ptr("io_ctrlInfo_deqPtr_"), ptr("io_ctrlInfo_physicalQueueUpper_"))
        return inp, {name: pin.U() for name, pin in self.outputs.items()}

    def observe(self, pins):
        """Decode one sampled public window into immutable transactions."""
        responses = []
        for lane in range(3):
            prefix = f"io_query_{lane}_s2Resp_"
            mask = 0
            data = 0
            for byte in range(16):
                mask |= bool(pins[prefix + f"bits_forwardMask_{byte}"]) << byte
                data |= pins[prefix + f"bits_forwardData_{byte}"] << (8 * byte)
            responses.append(Response(
                int(bool(pins[prefix + "valid"])), int(bool(pins[prefix + "bits_forwardInvalid"])),
                int(bool(pins[prefix + "bits_matchInvalid"])), int(bool(pins[prefix + "bits_addrInvalid_valid"])),
                int(bool(pins[prefix + "bits_dataInvalid_valid"])), mask, data))
        return Observation(tuple(responses))
