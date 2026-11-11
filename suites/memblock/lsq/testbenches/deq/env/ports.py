import json

from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.deq.transactions import DeqControl
from suites.memblock.lsq.testbenches.deq.transactions import Inputs
from suites.memblock.lsq.testbenches.deq.transactions import SecondPage
from suites.memblock.lsq.testbenches.deq.transactions import Store
from suites.memblock.lsq.testbenches.deq.transactions import encode
from suites.memblock.lsq.testbenches.deq.transactions import CacheRequest
from suites.memblock.lsq.testbenches.deq.transactions import ExceptionInfo
from suites.memblock.lsq.testbenches.deq.transactions import Observation
from suites.memblock.lsq.testbenches.deq.transactions import RobIdentity
from suites.memblock.lsq.testbenches.deq.transactions import SbufferWord
from suites.memblock.lsq.testbenches.deq.transactions import UncacheRequest
from suites.memblock.lsq.testbenches.deq.transactions import Writeback
from suites.memblock.lsq.testbenches.shared.transactions import UNSET


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
        assert len(self.inputs) == 65 and len(self.outputs) == 55 and set(self.inputs) == set(encode(Inputs()))

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
            dequeue.append(DeqControl(bool(pins[prefix + "vecInactive"]), bool(pins[prefix + "committed"]), bool(pins[prefix + "handleFinish"]),
                                      bool(pins[prefix + "isCbo"]), pins[f"io_deqDataEntries_{lane}_memoryType"]))
        rob = RobPtr(bool(pins["io_fromVirtualStoreQueue_headRobIdx_flag"]), pins["io_fromVirtualStoreQueue_headRobIdx_value"], bool(pins["io_fromVirtualStoreQueue_headRobIdx_isFormer"]))
        inp = Inputs(tuple(stores), tuple(dequeue), tuple(bool(pins[f"io_writeToSbuffer_req_{lane}_ready"]) for lane in range(2)), sq("io_rdataPtrExt_0_"),
                     tuple(sq(f"io_deqPtrExt_{lane}_") for lane in range(2)), rob, pins["io_validCnt"],
                     bool(pins["io_toUncacheBuffer_req_ready"]), bool(pins["io_toUncacheBuffer_idResp_valid"]), bool(pins["io_toUncacheBuffer_idResp_bits_is2lq"]), bool(pins["io_toUncacheBuffer_resp_valid"]),
                     bool(pins["io_toDCache_req_ready"]), bool(pins["io_toDCache_resp_valid"]), bool(pins["io_toDCache_resp_bits_denied"]), bool(pins["io_toDCache_resp_bits_corrupt"]),
                     bool(pins["io_writeBack_ready"]), bool(pins["io_sbufferCtrl_resp_empty"]),
                     SecondPage(bool(pins["io_fromUnalignQueue_valid"]), pins["io_fromUnalignQueue_bits_paddr"], sq("io_fromUnalignQueue_bits_sqIdx_")), bool(pins["reset"]))
        return inp, {name: pin.U() for name, pin in self.outputs.items()}

    PLAIN_PINS = {
        "read_pointer_moves": "io_rdataPtrMoveCnt",
        "sq_deq_count": "io_sqDeqCnt",
        "deq_pointer_next": "io_deqPtrExtNext_0_value",
        "force_write": "io_sbufferCtrl_req_forceWrite",
        "flush": "io_sbufferCtrl_req_flush",
        "unalign_ready": "io_fromUnalignQueue_ready",
        "mmio_busy": "io_toRob_mmioBusy",
        "cache_response_ready": "io_toDCache_resp_ready",
    }

    def observe(self, pins):
        return decode_observation(pins)

    def expected(self, observation):
        out = {pin: getattr(observation, name) for name, pin in self.PLAIN_PINS.items()
               if getattr(observation, name) is not None}
        if observation.cache_request is not UNSET:
            request = observation.cache_request
            if request is None or request.valid is not None:
                out["io_toDCache_req_valid"] = 0 if request is None else int(request.valid)
            if request is not None:
                if request.address is not None:
                    out["io_toDCache_req_bits_address"] = request.address
                if request.opcode is not None:
                    out["io_toDCache_req_bits_opcode"] = request.opcode
        if observation.uncache_request is not UNSET:
            request = observation.uncache_request
            if request is None or request.valid is not None:
                out["io_toUncacheBuffer_req_valid"] = 0 if request is None else int(request.valid)
            if request is not None:
                for field, pin in (
                    ("addr", "io_toUncacheBuffer_req_bits_addr"),
                    ("vaddr", "io_toUncacheBuffer_req_bits_vaddr"),
                    ("data", "io_toUncacheBuffer_req_bits_data"),
                    ("mask", "io_toUncacheBuffer_req_bits_mask"),
                    ("ident", "io_toUncacheBuffer_req_bits_id"),
                    ("nc", "io_toUncacheBuffer_req_bits_nc"),
                    ("memory_backed", "io_toUncacheBuffer_req_bits_memBackTypeMM"),
                ):
                    if getattr(request, field) is not None:
                        out[pin] = getattr(request, field)
                if request.rob is not None:
                    out.update(self._rob("io_toUncacheBuffer_req_bits_robIdx_", request.rob))
        if observation.writeback is not UNSET:
            writeback = observation.writeback
            if writeback is None or writeback.valid is not None:
                out["io_writeBack_valid"] = 0 if writeback is None else int(writeback.valid)
            if writeback is not None:
                for field, pin in (
                    ("access_fault", "io_writeBack_bits_exceptionVec_7"),
                    ("bus_error", "io_writeBack_bits_exceptionVec_19"),
                    ("mmio", "io_writeBack_bits_debugInfo_isMMIO"),
                    ("ncio", "io_writeBack_bits_debugInfo_isNCIO"),
                ):
                    if getattr(writeback, field) is not None:
                        out[pin] = getattr(writeback, field)
                if writeback.rob is not None:
                    out.update(self._rob("io_writeBack_bits_robIdx_", writeback.rob))
        if observation.exception_info is not UNSET:
            exception = observation.exception_info
            if exception is None or exception.valid is not None:
                out["io_exceptionInfo_valid"] = 0 if exception is None else int(exception.valid)
            if exception is not None:
                for field, pin in (
                    ("vaddr", "io_exceptionInfo_bits_vaddr"),
                    ("hyper", "io_exceptionInfo_bits_isHyper"),
                    ("access_fault", "io_exceptionInfo_bits_exceptionVec_7"),
                    ("bus_error", "io_exceptionInfo_bits_exceptionVec_19"),
                ):
                    if getattr(exception, field) is not None:
                        out[pin] = getattr(exception, field)
                if exception.rob is not None:
                    out.update(self._rob("io_exceptionInfo_bits_robIdx_", exception.rob))
        for lane, word in enumerate((observation.sbuffer_word_0, observation.sbuffer_word_1)):
            if word is not UNSET:
                out.update(self.word_expected(lane, word))
        return out

    def word_expected(self, lane, word, data_mask=None):
        prefix = f"io_writeToSbuffer_req_{lane}_"
        if word is None:
            return {prefix + "valid": 0}
        assert isinstance(word, SbufferWord), word
        out = {} if word.valid is None else {prefix + "valid": int(word.valid)}
        for field, suffix in (("addr", "addr"), ("vaddr", "vaddr"), ("mask", "mask"), ("data", "data"), ("wline", "wline")):
            value = getattr(word, field)
            if value is not None:
                out[prefix + "bits_" + suffix] = value
        return out

    @staticmethod
    def _rob(prefix, rob):
        out = {}
        if rob.value is not None:
            out[prefix + "value"] = rob.value
        if rob.flag is not None:
            out[prefix + "flag"] = rob.flag
        if rob.former is not None:
            out[prefix + "isFormer"] = rob.former
        return out


def decode_observation(pins):
    """Decode one sampled public window into immutable Deq responses."""
    def rob(prefix):
        return RobIdentity(pins[prefix + "value"], bool(pins[prefix + "flag"]), bool(pins[prefix + "isFormer"]))

    def word(lane):
        prefix = f"io_writeToSbuffer_req_{lane}_"
        return None if not pins[prefix + "valid"] else SbufferWord(
            1, pins[prefix + "bits_addr"], pins[prefix + "bits_vaddr"], pins[prefix + "bits_mask"],
            pins[prefix + "bits_data"], pins[prefix + "bits_wline"])

    cache = CacheRequest(pins["io_toDCache_req_bits_address"], pins["io_toDCache_req_bits_opcode"]) \
        if pins["io_toDCache_req_valid"] else None
    uncache = UncacheRequest(
        pins["io_toUncacheBuffer_req_bits_addr"], pins["io_toUncacheBuffer_req_bits_vaddr"],
        pins["io_toUncacheBuffer_req_bits_data"], pins["io_toUncacheBuffer_req_bits_mask"],
        pins["io_toUncacheBuffer_req_bits_id"], bool(pins["io_toUncacheBuffer_req_bits_nc"]),
        bool(pins["io_toUncacheBuffer_req_bits_memBackTypeMM"]),
        rob("io_toUncacheBuffer_req_bits_robIdx_")) if pins["io_toUncacheBuffer_req_valid"] else None
    writeback = Writeback(
        rob("io_writeBack_bits_robIdx_"), bool(pins["io_writeBack_bits_exceptionVec_7"]),
        bool(pins["io_writeBack_bits_exceptionVec_19"]), bool(pins["io_writeBack_bits_debugInfo_isMMIO"]),
        bool(pins["io_writeBack_bits_debugInfo_isNCIO"])) if pins["io_writeBack_valid"] else None
    exception = ExceptionInfo(
        pins["io_exceptionInfo_bits_vaddr"], bool(pins["io_exceptionInfo_bits_isHyper"]),
        bool(pins["io_exceptionInfo_bits_exceptionVec_7"]), bool(pins["io_exceptionInfo_bits_exceptionVec_19"]),
        rob("io_exceptionInfo_bits_robIdx_")) if pins["io_exceptionInfo_valid"] else None
    return Observation(
        pins["io_rdataPtrMoveCnt"], pins["io_sqDeqCnt"], pins["io_deqPtrExtNext_0_value"],
        bool(pins["io_sbufferCtrl_req_forceWrite"]), bool(pins["io_sbufferCtrl_req_flush"]),
        bool(pins["io_fromUnalignQueue_ready"]), bool(pins["io_toRob_mmioBusy"]),
        bool(pins["io_toDCache_resp_ready"]), cache, uncache, writeback, exception, word(0), word(1))
