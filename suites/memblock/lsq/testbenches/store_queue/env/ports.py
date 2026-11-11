import json

from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.store_queue.transactions import Inputs
from suites.memblock.lsq.testbenches.store_queue.transactions import encode


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
        walk(json.loads((ROOT / "dut/store_queue/signals.json").read_text()))
        assert len(self.inputs) == 182 and len(self.outputs) == 338 and set(self.inputs) == set(encode(Inputs()))

    def sample(self, event):
        return ({name: pin.U() for name, pin in self.inputs.items()}, {name: pin.U() for name, pin in self.outputs.items()})

    def observe(self, pins):
        from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
        from suites.memblock.lsq.testbenches.store_queue.transactions import Observation
        from suites.memblock.lsq.testbenches.shared.transactions import CacheRequest, ExceptionInfo, ForwardResponse, RobIdentity, SbufferWord, UncacheRequest, Writeback

        def sq(prefix):
            return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])

        def rob(prefix):
            return RobIdentity(pins[prefix + "value"], bool(pins[prefix + "flag"]), bool(pins[prefix + "isFormer"]))

        def word(lane):
            prefix = f"io_writeToSbuffer_req_{lane}_"
            return None if not pins[prefix + "valid"] else SbufferWord(
                1, pins[prefix + "bits_addr"], pins[prefix + "bits_vaddr"], pins[prefix + "bits_mask"],
                pins[prefix + "bits_data"], bool(pins[prefix + "bits_wline"]))

        forward = []
        for lane in range(3):
            prefix = f"io_forward_{lane}_s2Resp_"
            mask = sum(bool(pins[prefix + f"bits_forwardMask_{byte}"]) << byte for byte in range(16))
            data = sum(pins[prefix + f"bits_forwardData_{byte}"] << (8 * byte) for byte in range(16))
            forward.append(ForwardResponse(
                bool(pins[prefix + "valid"]), bool(pins[prefix + "bits_forwardInvalid"]),
                bool(pins[prefix + "bits_matchInvalid"]), bool(pins[prefix + "bits_addrInvalid_valid"]),
                bool(pins[prefix + "bits_dataInvalid_valid"]), 0, mask, data))
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
            empty=bool(pins["io_sqEmpty"]), full=bool(pins["io_sqFull"]),
            force_write=bool(pins["io_sbufferCtrl_req_forceWrite"]), flush=bool(pins["io_sbufferCtrl_req_flush"]),
            mmio_busy=bool(pins["io_toRob_mmioBusy"]), cache_response_ready=bool(pins["io_toDCache_resp_ready"]),
            dequeue_valid=bool(pins["io_toLsqEnqCtrl_sqDeq_valid"]), dequeue_count=pins["io_toLsqEnqCtrl_sqDeq_bits"],
            sq_deq_ptr=sq("io_sqDeqPtr_"), physical_upper=sq("io_physicalUpperSqIdx_"),
            enq_dequeue_valid=bool(pins["io_toLsqEnqCtrl_sqDeq_valid"]),
            enq_dequeue_count=pins["io_toLsqEnqCtrl_sqDeq_bits"],
            recover_stall=bool(pins["io_toLsqEnqCtrl_sqRecoverStall"]),
            redirect_ptr=sq("io_toLsqEnqCtrl_sqRedirectPtr_bits_"),
            redirect_valid=bool(pins["io_toLsqEnqCtrl_sqRedirectPtr_valid"]),
            addr_ready_ptr=sq("io_toLoadQueue_stAddrReadySqPtr_"),
            data_ready_ptr=sq("io_toLoadQueue_stDataReadySqPtr_"),
            addr_ready_mask=sum(pins[f"io_toLoadQueue_stAddrReadyVec_{slot}"] << slot for slot in range(64)),
            data_ready_mask=sum(pins[f"io_toLoadQueue_stDataReadyVec_{slot}"] << slot for slot in range(64)),
            unalign_ready=(bool(pins["io_fromStoreUnit_unalignQueueReq_0_ready"]),
                           bool(pins["io_fromStoreUnit_unalignQueueReq_1_ready"])),
            sbuffer_word_0=word(0), sbuffer_word_1=word(1), cache_request=cache,
            uncache_request=uncache, writeback=writeback, exception_info=exception, forward=tuple(forward))

    def expected(self, observation):
        from suites.memblock.lsq.testbenches.shared.transactions import UNSET
        if observation is None:
            return {}
        out = {}
        plain = {"empty": "io_sqEmpty", "full": "io_sqFull",
                 "force_write": "io_sbufferCtrl_req_forceWrite", "flush": "io_sbufferCtrl_req_flush",
                 "mmio_busy": "io_toRob_mmioBusy", "cache_response_ready": "io_toDCache_resp_ready",
                 "recover_stall": "io_toLsqEnqCtrl_sqRecoverStall",
                 "redirect_valid": "io_toLsqEnqCtrl_sqRedirectPtr_valid"}
        for name, pin in plain.items():
            if getattr(observation, name) is not None:
                out[pin] = getattr(observation, name)
        if observation.dequeue_valid is not None:
            out["io_toLsqEnqCtrl_sqDeq_valid"] = observation.dequeue_valid
        if observation.dequeue_count is not None:
            out["io_toLsqEnqCtrl_sqDeq_bits"] = observation.dequeue_count
        if observation.enq_dequeue_valid is not None:
            out["io_toLsqEnqCtrl_sqDeq_valid"] = observation.enq_dequeue_valid
        if observation.enq_dequeue_count is not None:
            out["io_toLsqEnqCtrl_sqDeq_bits"] = observation.enq_dequeue_count
        for name, prefix in (("sq_deq_ptr", "io_sqDeqPtr_"), ("physical_upper", "io_physicalUpperSqIdx_"),
                             ("redirect_ptr", "io_toLsqEnqCtrl_sqRedirectPtr_bits_"),
                             ("addr_ready_ptr", "io_toLoadQueue_stAddrReadySqPtr_"),
                             ("data_ready_ptr", "io_toLoadQueue_stDataReadySqPtr_")):
            pointer = getattr(observation, name)
            if pointer is not None:
                out.update({prefix + "first_flag": int(pointer.first), prefix + "second_flag": int(pointer.second),
                            prefix + "value": pointer.value})
        if observation.addr_ready_mask is not None:
            out.update({f"io_toLoadQueue_stAddrReadyVec_{slot}": 1 for slot in range(64) if observation.addr_ready_mask >> slot & 1})
        if observation.data_ready_mask is not None:
            out.update({f"io_toLoadQueue_stDataReadyVec_{slot}": 1 for slot in range(64) if observation.data_ready_mask >> slot & 1})
        if observation.addr_ready_clear_mask is not None:
            out.update({f"io_toLoadQueue_stAddrReadyVec_{slot}": 0 for slot in range(64) if observation.addr_ready_clear_mask >> slot & 1})
        if observation.data_ready_clear_mask is not None:
            out.update({f"io_toLoadQueue_stDataReadyVec_{slot}": 0 for slot in range(64) if observation.data_ready_clear_mask >> slot & 1})
        if observation.unalign_ready is not UNSET:
            for lane, value in enumerate(observation.unalign_ready):
                if value is not None:
                    out[f"io_fromStoreUnit_unalignQueueReq_{lane}_ready"] = value
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
                for field, pin in (("addr", "io_toUncacheBuffer_req_bits_addr"),
                                   ("vaddr", "io_toUncacheBuffer_req_bits_vaddr"),
                                   ("data", "io_toUncacheBuffer_req_bits_data"),
                                   ("mask", "io_toUncacheBuffer_req_bits_mask"),
                                   ("ident", "io_toUncacheBuffer_req_bits_id"),
                                   ("nc", "io_toUncacheBuffer_req_bits_nc"),
                                   ("memory_backed", "io_toUncacheBuffer_req_bits_memBackTypeMM")):
                    if getattr(request, field) is not None:
                        out[pin] = getattr(request, field)
                if request.rob is not None:
                    out.update(self._rob("io_toUncacheBuffer_req_bits_robIdx_", request.rob))
        if observation.writeback is not UNSET:
            writeback = observation.writeback
            if writeback is None or writeback.valid is not None:
                out["io_writeBack_valid"] = 0 if writeback is None else int(writeback.valid)
            if writeback is not None:
                for field, pin in (("access_fault", "io_writeBack_bits_exceptionVec_7"),
                                   ("bus_error", "io_writeBack_bits_exceptionVec_19"),
                                   ("mmio", "io_writeBack_bits_debugInfo_isMMIO"),
                                   ("ncio", "io_writeBack_bits_debugInfo_isNCIO")):
                    if getattr(writeback, field) is not None:
                        out[pin] = getattr(writeback, field)
                if writeback.rob is not None:
                    out.update(self._rob("io_writeBack_bits_robIdx_", writeback.rob))
        if observation.exception_info is not UNSET:
            exception = observation.exception_info
            if exception is None or exception.valid is not None:
                out["io_exceptionInfo_valid"] = 0 if exception is None else int(exception.valid)
            if exception is not None:
                for field, pin in (("vaddr", "io_exceptionInfo_bits_vaddr"),
                                   ("hyper", "io_exceptionInfo_bits_isHyper"),
                                   ("access_fault", "io_exceptionInfo_bits_exceptionVec_7"),
                                   ("bus_error", "io_exceptionInfo_bits_exceptionVec_19")):
                    if getattr(exception, field) is not None:
                        out[pin] = getattr(exception, field)
                if exception.rob is not None:
                    out.update(self._rob("io_exceptionInfo_bits_robIdx_", exception.rob))
        for lane, item in enumerate((observation.sbuffer_word_0, observation.sbuffer_word_1)):
            if item is not UNSET:
                out.update(self.word_expected(lane, item))
        for lane, item in enumerate(observation.forward):
            if item is not UNSET:
                out.update(self.forward_expected(lane, item))
        self._supported_fields(observation)
        return out

    @staticmethod
    def _supported_fields(observation):
        known = {"empty", "full", "force_write", "flush", "mmio_busy",
                 "cache_response_ready", "dequeue_valid", "dequeue_count", "sq_deq_ptr",
                 "physical_upper", "enq_dequeue_valid", "enq_dequeue_count", "recover_stall",
                 "redirect_ptr", "redirect_valid", "addr_ready_ptr", "data_ready_ptr",
                 "addr_ready_mask", "data_ready_mask", "addr_ready_clear_mask",
                 "data_ready_clear_mask", "unalign_ready", "sbuffer_word_0",
                 "sbuffer_word_1", "cache_request", "uncache_request", "writeback",
                 "exception_info", "forward"}
        unknown = set(type(observation).__dataclass_fields__) - known
        if unknown:
            raise TypeError(f"StoreQueue expectation does not consume fields: {sorted(unknown)}")

    def word_expected(self, lane, word):
        prefix = f"io_writeToSbuffer_req_{lane}_"
        if word is None:
            return {prefix + "valid": 0}
        out = {} if word.valid is None else {prefix + "valid": int(word.valid)}
        for field, suffix in (("addr", "addr"), ("vaddr", "vaddr"), ("mask", "mask"), ("data", "data"), ("wline", "wline")):
            value = getattr(word, field)
            if value is not None:
                out[prefix + "bits_" + suffix] = value
        return out

    def forward_expected(self, lane, response):
        from suites.memblock.lsq.testbenches.shared.transactions import ForwardExpectation
        if not isinstance(response, ForwardExpectation):
            raise TypeError(f"unsupported Forward expectation {type(response)!r}")
        prefix = f"io_forward_{lane}_s2Resp_"
        out = {}
        for field, suffix in (("valid", "valid"), ("forward_invalid", "bits_forwardInvalid"),
                              ("match_invalid", "bits_matchInvalid"), ("addr_invalid", "bits_addrInvalid_valid"),
                              ("data_invalid", "bits_dataInvalid_valid")):
            value = getattr(response, field)
            if value is not None:
                out[prefix + suffix] = int(value)
        if response.data_invalid_value is not None:
            out[prefix + "bits_dataInvalid_bits_value"] = response.data_invalid_value
        if response.forward_mask is not None:
            out.update({prefix + f"bits_forwardMask_{byte}": response.forward_mask >> byte & 1
                        for byte in range(16)})
        byte_mask = response.data_byte_mask
        if response.forward_data is not None:
            if byte_mask is None:
                byte_mask = response.forward_mask
            if byte_mask is None or not byte_mask & 0xFFFF:
                raise ValueError("Forward data expectation requires a non-empty data byte range")
            out.update({prefix + f"bits_forwardData_{byte}": response.forward_data >> (8 * byte) & 0xFF
                        for byte in range(16) if byte_mask >> byte & 1})
        elif byte_mask is not None:
            raise ValueError("data_byte_mask is only meaningful with forward_data")
        return out

    @staticmethod
    def _rob(prefix, identity):
        out = {}
        if identity.value is not None:
            out[prefix + "value"] = identity.value
        if identity.flag is not None:
            out[prefix + "flag"] = identity.flag
        if identity.former is not None:
            out[prefix + "isFormer"] = identity.former
        return out
