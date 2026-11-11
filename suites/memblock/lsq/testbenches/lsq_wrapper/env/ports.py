"""Full passive sample; wrapper decoder is separate from its encode mapping."""
from dataclasses import asdict
import json

from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.load_queue.env.codec import encode as load_encode
from suites.memblock.lsq.testbenches.load_queue.env.ports import decode as load_decode
from suites.memblock.lsq.testbenches.load_queue.transactions import Inputs as LoadInputs
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.psq.transactions import SecondPage
from suites.memblock.lsq.testbenches.raw.transactions import FtqPtr
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.lsq_wrapper.env.codec import encode
from suites.memblock.lsq.testbenches.lsq_wrapper.env.codec import ports
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Address
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Bus
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Data
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Dispatch
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Inputs


def decode(pins):
    def pointer(prefix, kind):
        if kind == "rob":
            return RobPtr(bool(pins[prefix + "flag"]), pins[prefix + "value"], bool(pins[prefix + "isFormer"]))
        if kind == "lq":
            return QueuePtr(bool(pins[prefix + "flag"]), pins[prefix + "value"])
        return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])
    # Only an adapter shape, not inferred internal SQ values. Child-only
    # feedback placeholders are discarded: wrapper Inputs cannot expose them.
    child = load_encode(LoadInputs())
    for name in child:
        if name.startswith(("io_enq_", "io_sq_")):
            continue
        source = "io_brqRedirect_" + name[len("io_redirect_"):] if name.startswith("io_redirect_") else name
        child[name] = pins[source]
    load = load_decode(child)
    names = ("loads", "rar_queries", "raw_queries", "rar_revoke_last", "rar_revoke_older", "raw_revoke_last", "raw_revoke_older",
             "replay_ready", "address_wakeups", "data_wakeups", "refills", "l2_hints", "slow_tlb", "fast_tlb", "pending", "pending_next",
             "release", "bypass", "redirect", "reset")
    values = {name: getattr(load, name) for name in names}
    dispatch = []
    for lane in range(8):
        prefix = f"io_enq_req_{lane}_"
        dispatch.append(Dispatch(bool(pins[prefix + "valid"]), pins[f"io_enq_needAlloc_{lane}"],
                                 pointer(prefix + "bits_uop_robIdx_", "rob"), pins[prefix + "bits_uop_numLsElem"],
                                 pointer(prefix + "bits_reqStartPtr_lqIdx_", "lq"), pointer(prefix + "bits_reqEndPtr_sqIdx_", "sq")))
    addresses, attributes, data, pages = [], [], [], []
    for lane in range(2):
        p, raw = f"io_sta_storeAddrIn_{lane}_", load.stores[lane]
        addresses.append(Address(valid=bool(pins[p + "valid"]), slot=pins[p + "bits_uop_sqIdx_value"],
                                 fu_op=pins[p + "bits_uop_fuOpType"], vaddr=pins[p + "bits_vaddr"], paddr=pins[p + "bits_paddr"],
                                 size=pins[p + "bits_size"], tlb_miss=bool(pins[p + "bits_tlbMiss"]), hyper=bool(pins[p + "bits_isHyper"]),
                                 unaligned=bool(pins[p + "bits_isUnalign"]), cross_word=bool(pins[p + "bits_cross16Byte"]),
                                 last=bool(pins[p + "bits_isLastRequest"]), rob=raw.rob, ftq=FtqPtr(raw.ftq_flag, raw.ftq_value),
                                 ftq_offset=raw.ftq_offset, rvc=raw.is_rvc, mask=raw.mask, wline=raw.wline))
        p = f"io_sta_storeAddrInRe_{lane}_"
        attributes.append(Attributes(**{field: bool(pins[p + suffix]) for field, suffix in
                                       (("nc", "nc"), ("mmio", "mmio"), ("memory", "memBackTypeMM"),
                                        ("exception", "hasException"), ("last", "isLastRequest"))}))
        p = f"io_std_storeDataIn_{lane}_"
        data.append(Data(bool(pins[p + "valid"]), pointer(p + "bits_sqIdx_", "sq"), pins[p + "bits_fuOpType"], pins[p + "bits_data"]))
        p = f"io_sta_unalignQueueReq_{lane}_"
        pages.append(SecondPage(bool(pins[p + "valid"]), pointer(p + "bits_sqIdx_", "sq"), pins[p + "bits_paddr"]))
    queries, translations = [], []
    for lane in range(3):
        p = f"io_forward_{lane}_"
        queries.append(Query(bool(pins[p + "s0Req_valid"]), pins[p + "s0Req_bits_vaddr"], pointer(p + "s0Req_bits_sqIdx_", "sq"),
                             pins[p + "s0Req_bits_size"], bool(pins[p + "s0Req_bits_loadWaitBit"]),
                             bool(pins[p + "s0Req_bits_loadWaitStrict"]), pointer(p + "s0Req_bits_waitSqIdx_", "sq")))
        translations.append(Translation(pins[p + "s1Req_paddr"], bool(pins[p + "s1Kill"])))
    return Inputs(**values, dispatch=tuple(dispatch), addresses=tuple(addresses), attributes=tuple(attributes), data=tuple(data),
                  second_pages=tuple(pages), queries=tuple(queries), translations=tuple(translations),
                  bus=Bus(**asdict(load.bus), ack_to_load=bool(pins["io_uncache_idResp_bits_is2lq"]),
                          response_to_load=bool(pins["io_uncache_resp_bits_is2lq"]), outstanding=bool(pins["io_uncacheOutstanding"])),
                  sbuffer_ready=tuple(bool(pins[f"io_sbuffer_req_{lane}_ready"]) for lane in range(2)),
                  **{name: bool(pins[pin]) for name, pin in (("sbuffer_empty", "io_flushSbuffer_empty"), ("cache_ready", "io_cmoOpReq_ready"),
                     ("cache_response", "io_cmoOpResp_valid"), ("cache_denied", "io_cmoOpResp_bits_denied"),
                     ("cache_corrupt", "io_cmoOpResp_bits_corrupt"), ("writeback_ready", "io_mmioStout_ready"))})


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
        walk(json.loads((ROOT / "dut/lsq_wrapper/signals.json").read_text()))
        assert set(self.inputs) == set(ports()["input"]) == set(encode(Inputs()))
        assert set(self.outputs) == set(ports()["output"])

    def sample(self, event):
        actual = {name: signal.U() for name, signal in self.inputs.items()}
        return decode(actual), {name: signal.U() for name, signal in self.outputs.items()}, actual

    def observe(self, pins):
        return decode_observation(pins)


def _sq(pins, prefix):
    return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]),
                 pins[prefix + "value"])


def _lq(pins, prefix):
    return QueuePtr(bool(pins[prefix + "flag"]), pins[prefix + "value"])


def decode_observation(pins):
    """Decode one sampled public window into an immutable wrapper snapshot."""
    from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import (
        BypassResponse, CacheRequest, DeqCredit, ExceptionInfo, ForwardResponse,
        MdpTrain, NukeQuery, Observation, ReplaySlot, Rollback, SbufferWord,
        UncacheRequest, Writeback)

    def rob(prefix):
        return (pins[prefix + "value"], int(bool(pins[prefix + "flag"])),
                int(bool(pins[prefix + "isFormer"])))

    def word(lane):
        prefix = f"io_sbuffer_req_{lane}_"
        if not pins[prefix + "valid"]:
            return None
        return SbufferWord(1, pins[prefix + "bits_addr"], pins[prefix + "bits_vaddr"],
                           pins[prefix + "bits_mask"], pins[prefix + "bits_data"],
                           int(bool(pins[prefix + "bits_wline"])))

    def replay(bank):
        prefix = f"io_replay_{bank}_"
        return ReplaySlot(
            int(bool(pins[prefix + "valid"])), pins[prefix + "bits_replayQueueIdx"],
            int(bool(pins[prefix + "bits_uop_lqIdx_flag"])), pins[prefix + "bits_uop_lqIdx_value"],
            pins[prefix + "bits_uop_perfDebugInfo_runahead_checkpoint_id"],
            int(bool(pins[prefix + "bits_uop_robIdx_flag"])), pins[prefix + "bits_uop_robIdx_value"],
            int(bool(pins[prefix + "bits_uop_robIdx_isFormer"])), int(bool(pins[prefix + "bits_uop_loadWaitStrict"])),
            pins[prefix + "bits_uop_fuOpType"], pins[prefix + "bits_vaddr"], pins[prefix + "bits_mask"],
            pins[prefix + "bits_size"], pins[prefix + "bits_mshrId"], pins[prefix + "bits_entrance"],
            pins[prefix + "bits_accessType_instrType"],
            int(bool(pins[prefix + "bits_uop_sqIdx_first_flag"])),
            int(bool(pins[prefix + "bits_uop_sqIdx_second_flag"])), pins[prefix + "bits_uop_sqIdx_value"],
            sum(pins[prefix + f"bits_uop_exceptionVec_{bit}"] << bit for bit in (23, 19, 15, 7, 6)),
            pins[prefix + "bits_fullva"], int(bool(pins[prefix + "bits_ncReplay"])),
            int(bool(pins[prefix + "bits_uncacheReplay"])))

    def forward(lane):
        prefix = f"io_forward_{lane}_s2Resp_"
        mask = sum(pins[prefix + f"bits_forwardMask_{byte}"] << byte for byte in range(16))
        data = sum(pins[prefix + f"bits_forwardData_{byte}"] << (8 * byte) for byte in range(16))
        return ForwardResponse(
            valid=int(bool(pins[prefix + "valid"])), forward_invalid=int(bool(pins[prefix + "bits_forwardInvalid"])),
            match_invalid=int(bool(pins[prefix + "bits_matchInvalid"])),
            addr_invalid=int(bool(pins[prefix + "bits_addrInvalid_valid"])),
            data_invalid=int(bool(pins[prefix + "bits_dataInvalid_valid"])),
            addr_invalid_ptr=_sq(pins, prefix + "bits_addrInvalid_bits_"),
            data_invalid_ptr=_sq(pins, prefix + "bits_dataInvalid_bits_"),
            data_invalid_value=pins[prefix + "bits_dataInvalid_bits_value"], forward_mask=mask, forward_data=data)

    def bypass(lane):
        prefix = f"io_bypass_{lane}_"
        return BypassResponse(
            int(bool(pins[prefix + "s1Resp_valid"])), pins[prefix + "s1Resp_bits_paddr"],
            int(bool(pins[prefix + "s2Resp_valid"])), pins[prefix + "s2Resp_bits_data"],
            int(bool(pins[prefix + "s2Resp_bits_derr"])), int(bool(pins[prefix + "s2Resp_bits_nderr"])))

    def rollback(prefix, *, store_side):
        fields = dict(
            valid=int(bool(pins[prefix + "valid"])), rob_value=pins[prefix + "bits_robIdx_value"],
            rob_flag=int(bool(pins[prefix + "bits_robIdx_flag"])),
            rob_former=int(bool(pins[prefix + "bits_robIdx_isFormer"])),
            ftq_flag=int(bool(pins[prefix + "bits_ftqIdx_flag"])),
            ftq_value=pins[prefix + "bits_ftqIdx_value"], ftq_offset=pins[prefix + "bits_ftqOffset"],
            rvc=int(bool(pins[prefix + "bits_isRVC"])),
            checkpoint_id=pins[prefix + "bits_debug_runahead_checkpoint_id"])
        if store_side:
            fields.update(st_ftq_flag=int(bool(pins[prefix + "bits_stFtqIdx_flag"])),
                          st_ftq_value=pins[prefix + "bits_stFtqIdx_value"],
                          st_ftq_offset=pins[prefix + "bits_stFtqOffset"],
                          st_rvc=int(bool(pins[prefix + "bits_stIsRVC"])))
        else:
            fields["level"] = pins[prefix + "bits_level"]
        return Rollback(**fields, source=prefix)

    sampled_request = UncacheRequest(
            int(bool(pins["io_uncache_req_valid"])), pins["io_uncache_req_bits_cmd"], pins["io_uncache_req_bits_addr"],
            pins["io_uncache_req_bits_vaddr"], pins["io_uncache_req_bits_data"],
            pins["io_uncache_req_bits_mask"], pins["io_uncache_req_bits_id"],
            int(bool(pins["io_uncache_req_bits_nc"])), int(bool(pins["io_uncache_req_bits_memBackTypeMM"])),
            pins["io_uncache_req_bits_robIdx_value"], int(bool(pins["io_uncache_req_bits_robIdx_flag"])),
            int(bool(pins["io_uncache_req_bits_robIdx_isFormer"])))
    request = sampled_request if sampled_request.valid else None
    cmo = CacheRequest(1, pins["io_cmoOpReq_bits_address"], pins["io_cmoOpReq_bits_opcode"]) \
        if pins["io_cmoOpReq_valid"] else None
    sampled_stout = Writeback(int(bool(pins["io_mmioStout_valid"])), *rob("io_mmioStout_bits_robIdx_"),
                          int(bool(pins["io_mmioStout_bits_exceptionVec_7"])),
                          int(bool(pins["io_mmioStout_bits_exceptionVec_19"])),
                          int(bool(pins["io_mmioStout_bits_debugInfo_isMMIO"])),
                           int(bool(pins["io_mmioStout_bits_debugInfo_isNCIO"])))
    stout = sampled_stout if sampled_stout.valid else None
    ld_exception = None
    if pins["io_ldExceptionInfo_valid"]:
        ld_exception = ExceptionInfo(
            1, pins["io_ldExceptionInfo_bits_vaddr"],
            int(bool(pins["io_ldExceptionInfo_bits_isHyper"])),
            int(bool(pins["io_ldExceptionInfo_bits_exceptionVec_5"])),
            int(bool(pins["io_ldExceptionInfo_bits_exceptionVec_19"])),
            *rob("io_ldExceptionInfo_bits_robIdx_"),
            gpaddr=pins["io_ldExceptionInfo_bits_gpaddr"],
            nonleaf=int(bool(pins["io_ldExceptionInfo_bits_isForVSnonLeafPTE"])))
    sampled_st_exception = ExceptionInfo(
            int(bool(pins["io_stExceptionInfo_valid"])), pins["io_stExceptionInfo_bits_vaddr"],
            int(bool(pins["io_stExceptionInfo_bits_isHyper"])),
            int(bool(pins["io_stExceptionInfo_bits_exceptionVec_7"])),
            int(bool(pins["io_stExceptionInfo_bits_exceptionVec_19"])),
            *rob("io_stExceptionInfo_bits_robIdx_"))
    st_exception = sampled_st_exception if sampled_st_exception.valid else None
    mdp = MdpTrain(int(bool(pins["io_mdpTrain_valid"])), pins["io_mdpTrain_bits_ftqIdx_value"],
                   pins["io_mdpTrain_bits_ftqOffset"], int(bool(pins["io_mdpTrain_bits_isRVC"])),
                   pins["io_mdpTrain_bits_stFtqIdx_value"], pins["io_mdpTrain_bits_stFtqOffset"],
                   int(bool(pins["io_mdpTrain_bits_stIsRVC"])))
    perf = tuple(pins[f"io_perf_{index}_value"] for index in range(39))
    rar = tuple(NukeQuery(int(bool(pins[f"io_ldu_rarNukeQuery_{lane}_req_ready"])),
                          int(bool(pins[f"io_ldu_rarNukeQuery_{lane}_resp_valid"])),
                          int(bool(pins[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]))) for lane in range(3))
    raw = tuple(NukeQuery(req_ready=int(bool(pins[f"io_ldu_rawNukeQuery_{lane}_req_ready"])))
                for lane in range(3))
    return Observation(
        lq_empty=int(bool(pins["io_lqEmpty"])),
        sq_empty=int(bool(pins["io_sqEmpty"])), sq_full=int(bool(pins["io_sqFull"])),
        force_write=int(bool(pins["io_force_write"])), special_mode=int(bool(pins["io_specialMode"])),
        replay_allocate=int(bool(pins["io_replayAllocate"])), rob_mmio_busy=int(bool(pins["io_rob_mmioBusy"])),
        issue_ptr=_sq(pins, "io_issuePtrExt_"), sq_deq_ptr=_sq(pins, "io_sqDeqPtr_"),
        lq_redirect_ptr=_lq(pins, "io_toLsqEnqCtrl_lqRedirectPtr_bits_")
        if pins["io_toLsqEnqCtrl_lqRedirectPtr_valid"] else None,
        sq_redirect_ptr=_sq(pins, "io_toLsqEnqCtrl_sqRedirectPtr_bits_")
        if pins["io_toLsqEnqCtrl_sqRedirectPtr_valid"] else None,
        lq_recover_stall=int(bool(pins["io_toLsqEnqCtrl_lqRecoverStall"])),
        sq_recover_stall=int(bool(pins["io_toLsqEnqCtrl_sqRecoverStall"])),
        lq_dequeue=DeqCredit(int(bool(pins["io_toLsqEnqCtrl_lqDeq_valid"])),
                             pins["io_toLsqEnqCtrl_lqDeq_bits"]),
        sq_dequeue=DeqCredit(int(bool(pins["io_toLsqEnqCtrl_sqDeq_valid"])),
                             pins["io_toLsqEnqCtrl_sqDeq_bits"]),
        perf=perf, replays=tuple(replay(bank) for bank in range(3)),
        bypass=tuple(bypass(lane) for lane in range(3)),
        forward=tuple(forward(lane) for lane in range(3)),
        uncache_request=request, uncache_sample=sampled_request,
        cmo_request=cmo, cmo_response_ready=int(bool(pins["io_cmoOpResp_ready"])), mmio_stout=stout, mmio_sample=sampled_stout,
        ld_exception=ld_exception, st_exception=st_exception, st_exception_sample=sampled_st_exception,
        nack_rollback=rollback("io_nack_rollback_0_", store_side=False),
        nuke_rollback=(rollback("io_nuke_rollback_0_", store_side=True),
                       rollback("io_nuke_rollback_1_", store_side=True)),
        mdp_train=mdp, sbuffer_word_0=word(0), sbuffer_word_1=word(1),
        rar_nuke=rar, raw_nuke=raw,
        unalign_ready=tuple(int(bool(pins[f"io_sta_unalignQueueReq_{lane}_ready"])) for lane in range(2)))


def expected(observation):
    """Translate an immutable wrapper expectation into comparison keys.

    ``None`` selects a field/channel that is not constrained; ``UNSET`` leaves
    a whole response channel untouched.  A channel value of ``None`` asserts
    the absence of that response (``valid == 0``).
    """
    from suites.memblock.lsq.testbenches.shared.transactions import UNSET
    from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Observation

    if not isinstance(observation, Observation):
        raise TypeError("Wrapper checks require a typed Observation")
    out = {}
    if observation.lq_full is not None:
        raise ValueError("LsqWrapper does not retain the child lqFull observation")
    if observation.uncache_sample is not None:
        raise ValueError("Use uncache_request for expectations; uncache_sample is diagnostic metadata")
    if observation.mmio_sample is not None:
        raise ValueError("Use mmio_stout for expectations; mmio_sample is diagnostic metadata")
    if observation.st_exception_sample is not None:
        raise ValueError("Use st_exception for expectations; st_exception_sample is diagnostic metadata")
    for name, pin in (
            ("lq_empty", "io_lqEmpty"),
            ("sq_empty", "io_sqEmpty"), ("sq_full", "io_sqFull"),
            ("force_write", "io_force_write"), ("special_mode", "io_specialMode"),
            ("replay_allocate", "io_replayAllocate"), ("rob_mmio_busy", "io_rob_mmioBusy"),
            ("lq_recover_stall", "io_toLsqEnqCtrl_lqRecoverStall"),
            ("sq_recover_stall", "io_toLsqEnqCtrl_sqRecoverStall"), ("cmo_response_ready", "io_cmoOpResp_ready")):
        value = getattr(observation, name)
        if value is not None:
            out[pin] = int(value)
    if observation.issue_ptr is not None:
        out.update(_pointer("io_issuePtrExt_", observation.issue_ptr))
    if observation.sq_deq_ptr is not None:
        out.update(_pointer("io_sqDeqPtr_", observation.sq_deq_ptr))
    if observation.lq_redirect_ptr is not None:
        out["io_toLsqEnqCtrl_lqRedirectPtr_valid"] = 1
        out["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"] = int(observation.lq_redirect_ptr.flag)
        out["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"] = observation.lq_redirect_ptr.value
    if observation.sq_redirect_ptr is not None:
        out["io_toLsqEnqCtrl_sqRedirectPtr_valid"] = 1
        out.update(_pointer("io_toLsqEnqCtrl_sqRedirectPtr_bits_", observation.sq_redirect_ptr))
    for index, value in enumerate(observation.perf):
        if value is not None:
            out[f"io_perf_{index}_value"] = value
    for name, prefix in (("lq_dequeue", "io_toLsqEnqCtrl_lqDeq_"),
                         ("sq_dequeue", "io_toLsqEnqCtrl_sqDeq_")):
        credit = getattr(observation, name)
        if credit is not None:
            if credit.valid is not None:
                out[prefix + "valid"] = int(credit.valid)
            if credit.count is not None:
                out[prefix + "bits"] = credit.count
    for lane, word in ((0, observation.sbuffer_word_0), (1, observation.sbuffer_word_1)):
        if word is UNSET:
            continue
        prefix = f"io_sbuffer_req_{lane}_"
        if word is None:
            out[prefix + "valid"] = 0
            continue
        if word.valid is not None:
            out[prefix + "valid"] = int(word.valid)
        for value, suffix in ((word.addr, "bits_addr"), (word.vaddr, "bits_vaddr"),
                              (word.mask, "bits_mask"), (word.data, "bits_data"),
                              (word.wline, "bits_wline")):
            if value is not None:
                out[prefix + suffix] = int(value)
    for channel, prefix, encoder in (
            (observation.uncache_request, "io_uncache_req_", _uncache_expected),
            (observation.cmo_request, "io_cmoOpReq_", _cmo_expected),
            (observation.mmio_stout, "io_mmioStout_", _writeback_expected),
            (observation.ld_exception, "io_ldExceptionInfo_", _exception_expected),
            (observation.st_exception, "io_stExceptionInfo_", _exception_expected)):
        if channel is UNSET:
            continue
        if channel is None:
            out[prefix + "valid"] = 0
            continue
        if channel.valid is not None:
            out[prefix + "valid"] = int(channel.valid)
        payload = (_exception_expected(channel, access_bit=5 if prefix == "io_ldExceptionInfo_" else 7)
                   if encoder is _exception_expected else encoder(channel))
        out.update({prefix + key: value for key, value in payload.items()} if encoder is _exception_expected else payload)
    if observation.nack_rollback is not None:
        out.update(_rollback_expected("io_nack_rollback_0_", observation.nack_rollback))
    for lane, item in enumerate(observation.nuke_rollback):
        if item is not None:
            out.update(_rollback_expected(f"io_nuke_rollback_{lane}_", item))
    if observation.mdp_train is not None:
        for value, pin in ((observation.mdp_train.valid, "io_mdpTrain_valid"),
                           (observation.mdp_train.ftq_value, "io_mdpTrain_bits_ftqIdx_value"),
                           (observation.mdp_train.ftq_offset, "io_mdpTrain_bits_ftqOffset"),
                           (observation.mdp_train.rvc, "io_mdpTrain_bits_isRVC"),
                           (observation.mdp_train.st_ftq_value, "io_mdpTrain_bits_stFtqIdx_value"),
                           (observation.mdp_train.st_ftq_offset, "io_mdpTrain_bits_stFtqOffset"),
                           (observation.mdp_train.st_rvc, "io_mdpTrain_bits_stIsRVC")):
            if value is not None:
                out[pin] = int(value)
    for lane, item in enumerate(observation.bypass):
        if item is not None:
            out.update(_bypass_expected(lane, item))
    for bank, item in enumerate(observation.replays):
        if item is not None:
            out.update(_replay_expected(bank, item))
    for lane, item in enumerate(observation.forward):
        if item is not None:
            out.update(_forward_expected(lane, item))
    for lane, item in enumerate(observation.rar_nuke):
        if item is not None:
            out.update(_nuke_expected(f"io_ldu_rarNukeQuery_{lane}_", item, response=True))
    for lane, item in enumerate(observation.raw_nuke):
        if item is not None:
            out.update(_nuke_expected(f"io_ldu_rawNukeQuery_{lane}_", item, response=False))
    for lane, value in enumerate(observation.unalign_ready):
        if value is not None:
            out[f"io_sta_unalignQueueReq_{lane}_ready"] = int(value)
    return out


def _pointer(prefix, value):
    return {prefix + suffix: int(item) for suffix, item in
            (("first_flag", value.first), ("second_flag", value.second), ("value", value.value)) if item is not None}


def _uncache_expected(value):
    out = {}
    for field, suffix in (("cmd", "bits_cmd"), ("addr", "bits_addr"), ("vaddr", "bits_vaddr"),
                          ("data", "bits_data"), ("mask", "bits_mask"), ("ident", "bits_id"),
                          ("nc", "bits_nc"), ("memory_backed", "bits_memBackTypeMM"),
                          ("rob_value", "bits_robIdx_value"), ("rob_flag", "bits_robIdx_flag"),
                          ("rob_former", "bits_robIdx_isFormer")):
        item = getattr(value, field)
        if item is not None:
            out["io_uncache_req_" + suffix] = int(item)
    return out


def _cmo_expected(value):
    out = {}
    if value.address is not None:
        out["io_cmoOpReq_bits_address"] = value.address
    if value.opcode is not None:
        out["io_cmoOpReq_bits_opcode"] = value.opcode
    return out


def _writeback_expected(value):
    out = {}
    for field, suffix in (("rob_value", "bits_robIdx_value"), ("rob_flag", "bits_robIdx_flag"),
                          ("rob_former", "bits_robIdx_isFormer"), ("access_fault", "bits_exceptionVec_7"),
                          ("bus_error", "bits_exceptionVec_19"), ("mmio", "bits_debugInfo_isMMIO"),
                          ("ncio", "bits_debugInfo_isNCIO")):
        item = getattr(value, field)
        if item is not None:
            out["io_mmioStout_" + suffix] = int(item)
    return out


def _exception_expected(value, *, access_bit):
    if access_bit == 7 and (value.gpaddr is not None or value.nonleaf is not None):
        raise ValueError("Store exception interface does not retain gpaddr/nonleaf")
    out = {}
    for field, suffix in (("vaddr", "bits_vaddr"), ("hyper", "bits_isHyper"),
                          ("access_fault", f"bits_exceptionVec_{access_bit}"), ("bus_error", "bits_exceptionVec_19"),
                          ("rob_value", "bits_robIdx_value"), ("rob_flag", "bits_robIdx_flag"),
                          ("rob_former", "bits_robIdx_isFormer"), ("gpaddr", "bits_gpaddr"),
                          ("nonleaf", "bits_isForVSnonLeafPTE")):
        item = getattr(value, field)
        if item is not None:
            out[suffix] = int(item)
    return out


def _rollback_expected(prefix, value):
    if value.source is not None:
        raise ValueError("Rollback source is observed diagnostic metadata")
    out = {}
    if value.valid is not None:
        out[prefix + "valid"] = int(value.valid)
    for field, suffix in (("rob_value", "bits_robIdx_value"), ("rob_flag", "bits_robIdx_flag"),
                          ("rob_former", "bits_robIdx_isFormer"), ("ftq_flag", "bits_ftqIdx_flag"),
                          ("ftq_value", "bits_ftqIdx_value"), ("ftq_offset", "bits_ftqOffset"),
                          ("rvc", "bits_isRVC"), ("checkpoint_id", "bits_debug_runahead_checkpoint_id"),
                          ("st_ftq_flag", "bits_stFtqIdx_flag"), ("st_ftq_value", "bits_stFtqIdx_value"),
                          ("st_ftq_offset", "bits_stFtqOffset"), ("st_rvc", "bits_stIsRVC"),
                          ("level", "bits_level")):
        item = getattr(value, field)
        if item is not None:
            out[prefix + suffix] = int(item)
    return out


def _bypass_expected(lane, value):
    out = {}
    for field, suffix in (("s1_valid", "s1Resp_valid"), ("s1_paddr", "s1Resp_bits_paddr"),
                          ("s2_valid", "s2Resp_valid"), ("s2_data", "s2Resp_bits_data"),
                          ("s2_derr", "s2Resp_bits_derr"), ("s2_nderr", "s2Resp_bits_nderr")):
        item = getattr(value, field)
        if item is not None:
            out[f"io_bypass_{lane}_{suffix}"] = int(item)
    return out


def _replay_expected(bank, value):
    out = {}
    for field, suffix in (("valid", "valid"), ("replay_queue_idx", "bits_replayQueueIdx"),
                          ("lq_idx_flag", "bits_uop_lqIdx_flag"), ("lq_idx_value", "bits_uop_lqIdx_value"),
                          ("checkpoint_id", "bits_uop_perfDebugInfo_runahead_checkpoint_id"),
                          ("rob_idx_flag", "bits_uop_robIdx_flag"), ("rob_idx_value", "bits_uop_robIdx_value"),
                          ("rob_idx_former", "bits_uop_robIdx_isFormer"),
                          ("strict", "bits_uop_loadWaitStrict"), ("operation", "bits_uop_fuOpType"),
                          ("vaddr", "bits_vaddr"), ("mask", "bits_mask"), ("size", "bits_size"),
                          ("mshr_id", "bits_mshrId"), ("entrance", "bits_entrance"),
                          ("instr_type", "bits_accessType_instrType"),
                          ("sq_idx_first", "bits_uop_sqIdx_first_flag"),
                          ("sq_idx_second", "bits_uop_sqIdx_second_flag"), ("sq_idx_value", "bits_uop_sqIdx_value"),
                          ("fullva", "bits_fullva"), ("nc_replay", "bits_ncReplay"), ("uncache_replay", "bits_uncacheReplay")):
        item = getattr(value, field)
        if item is not None:
            out[f"io_replay_{bank}_{suffix}"] = int(item)
    if value.exceptions is not None:
        bits = (23, 19, 15, 7, 6)
        if value.exceptions & ~sum(1 << bit for bit in bits):
            raise ValueError("Replay expectation contains a non-retained exception bit")
        out.update({f"io_replay_{bank}_bits_uop_exceptionVec_{bit}": value.exceptions >> bit & 1 for bit in bits})
    return out


def _forward_expected(lane, value):
    prefix = f"io_forward_{lane}_s2Resp_"
    out = {}
    for field, suffix in (("valid", "valid"), ("forward_invalid", "bits_forwardInvalid"),
                          ("match_invalid", "bits_matchInvalid"), ("addr_invalid", "bits_addrInvalid_valid"),
                          ("data_invalid", "bits_dataInvalid_valid")):
        item = getattr(value, field)
        if item is not None:
            out[prefix + suffix] = int(item)
    if value.addr_invalid_ptr is not None:
        out.update(_pointer(prefix + "bits_addrInvalid_bits_", value.addr_invalid_ptr))
    if value.data_invalid_ptr is not None:
        out.update(_pointer(prefix + "bits_dataInvalid_bits_", value.data_invalid_ptr))
    if value.data_invalid_value is not None:
        if value.data_invalid_ptr is not None and value.data_invalid_ptr.value is not None:
            if value.data_invalid_ptr.value != value.data_invalid_value:
                raise ValueError("conflicting Forward dependency value and pointer")
        out[prefix + "bits_dataInvalid_bits_value"] = value.data_invalid_value
    if value.forward_mask is not None:
        if not 0 <= value.forward_mask <= 0xFFFF:
            raise ValueError("Forward expected mask outside 16-byte window")
        byte_mask = 0xFFFF if value.mask_byte_mask is None else value.mask_byte_mask
        if not 0 < byte_mask <= 0xFFFF:
            raise ValueError("Forward mask comparison requires a nonempty byte selection")
        out.update({prefix + f"bits_forwardMask_{byte}": value.forward_mask >> byte & 1
                    for byte in range(16) if byte_mask >> byte & 1})
    elif value.mask_byte_mask is not None:
        raise ValueError("Forward mask byte selection without an expected mask")
    if value.forward_data is not None:
        byte_mask = value.data_byte_mask if value.data_byte_mask is not None else value.forward_mask
        if byte_mask is None or not 0 < byte_mask <= 0xFFFF or not 0 <= value.forward_data < (1 << 128):
            raise ValueError("Forward data requires a valid expected byte window and 128-bit value")
        out.update({prefix + f"bits_forwardData_{byte}": value.forward_data >> (8 * byte) & 255
                    for byte in range(16) if byte_mask >> byte & 1})
    elif value.data_byte_mask is not None:
        raise ValueError("Forward data byte selection without expected data")
    return out


def _nuke_expected(prefix, value, *, response):
    if not response and (value.resp_valid is not None or value.nuke is not None):
        raise ValueError("RAW query interface does not retain a response channel")
    out = {}
    if value.req_ready is not None:
        out[prefix + "req_ready"] = int(value.req_ready)
    if response:
        if value.resp_valid is not None:
            out[prefix + "resp_valid"] = int(value.resp_valid)
        if value.nuke is not None:
            out[prefix + "resp_bits_nuke"] = int(value.nuke)
    return out
