import json

from lsqverify.native import ROOT
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr
from .types import DeqControl, Inputs, SecondPage, Store, encode


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
        walk(json.loads((ROOT / "dut/deq_module/signals.json").read_text()))
        assert len(self.inputs) == 61 and len(self.outputs) == 55 and set(self.inputs) == set(encode(Inputs()))

    def sample(self, event):
        pins = {name: pin.U() for name, pin in self.inputs.items()}
        def sq(prefix):
            return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])
        stores, dequeue = [], []
        for lane in range(2):
            data, ctrl = f"io_rdataDataEntries_{lane}_", f"io_rdataCtrlEntries_{lane}_"
            stores.append(Store(pins[data + "vaddr"], pins[data + "paddrHigh"], pins[data + "byteMask"], pins[data + "data"], pins[data + "memoryType"], pins[data + "cboType"],
                                bool(pins.get(data + "isHyper", 0)), bool(pins.get(ctrl + "dataValid", 0)), bool(pins.get(ctrl + "addrValid", 0)),
                                bool(pins[ctrl + "vecInactive"]), bool(pins[ctrl + "cross16Byte"]), bool(pins.get(ctrl + "hasException", 0)), bool(pins[ctrl + "committed"]), bool(pins[ctrl + "isCbo"])))
            prefix = f"io_deqCtrlEntries_{lane}_"
            dequeue.append(DeqControl(bool(pins[prefix + "vecInactive"]), bool(pins[prefix + "committed"]), bool(pins[prefix + "handleFinish"])))
        rob = RobPtr(bool(pins["io_fromVirtualStoreQueue_headRobIdx_flag"]), pins["io_fromVirtualStoreQueue_headRobIdx_value"], bool(pins["io_fromVirtualStoreQueue_headRobIdx_isFormer"]))
        inp = Inputs(tuple(stores), tuple(dequeue), tuple(bool(pins[f"io_writeToSbuffer_req_{lane}_ready"]) for lane in range(2)), sq("io_rdataPtrExt_0_"),
                     tuple(sq(f"io_deqPtrExt_{lane}_") for lane in range(2)), rob, pins["io_validCnt"],
                     bool(pins["io_toUncacheBuffer_req_ready"]), bool(pins["io_toUncacheBuffer_idResp_valid"]), bool(pins["io_toUncacheBuffer_idResp_bits_is2lq"]), bool(pins["io_toUncacheBuffer_resp_valid"]),
                     bool(pins["io_toDCache_req_ready"]), bool(pins["io_toDCache_resp_valid"]), bool(pins["io_toDCache_resp_bits_denied"]), bool(pins["io_toDCache_resp_bits_corrupt"]),
                     bool(pins["io_writeBack_ready"]), bool(pins["io_sbufferCtrl_resp_empty"]),
                     SecondPage(bool(pins["io_fromUnalignQueue_valid"]), pins["io_fromUnalignQueue_bits_paddr"], sq("io_fromUnalignQueue_bits_sqIdx_")), bool(pins["reset"]))
        return inp, {name: pin.U() for name, pin in self.outputs.items()}
