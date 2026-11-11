"""Output monitor for NewLoadUnit.

This decoder turns the public output values sampled by ``LoadParentEnv`` into
an immutable :class:`LoadPipelineSnapshot`. The environment normally samples
after the clock edge; ``observe()`` reads the current outputs without advancing
time. Functional tests consume stage snapshots instead of generated names.

The full set of parent outputs is required: a missing or renamed pin fails at
environment construction, so a DUT change cannot silently drop a check.
"""
from __future__ import annotations

from suites.memblock.lsu.testbenches.new_load_unit.transactions import (
    DcacheRequest, ExceptionBits, ExceptionInfo, FpRfWrite, FtqPtr, IntRfWrite,
    LqTag, LqWrite, LoadPipelineSnapshot, MshrForwardRequest, PerfCounters,
    PrefetchTrain, RawNukeQuery, RarNukeQuery, ReplayCauses, Revoke,
    RobTag, RobWriteback, Rollback, SimpleForwardRequest, SqTag,
    Stage0Observation, Stage1Observation, Stage2Observation, Stage3Observation,
    StoreForwardRequest, TlbRequest, TldForwardRequest, UncacheBypassRequest,
    VectorRfWrite, VectorRobWriteback, VectorWakeup, Wakeup,
)

_EXCEPTION_CODES = (3, 4, 5, 6, 7, 13, 15, 19, 21, 23)
_REPLAY_CODES = tuple(range(0, 13))

_LQ_FIELDS = (
    "alignedType", "fullva", "gpaddr", "handledByMSHR", "isForVSnonLeafPTE",
    "isHyper", "isLoadReplay", "isvec", "mask", "memBackTypeMM", "mmio", "nc",
    "paddr", "rep_info_addr_inv_sq_idx_first_flag",
    "rep_info_addr_inv_sq_idx_second_flag", "rep_info_addr_inv_sq_idx_value",
    "rep_info_data_inv_sq_idx_first_flag",
    "rep_info_data_inv_sq_idx_second_flag", "rep_info_data_inv_sq_idx_value",
    "rep_info_last_beat", "rep_info_mshr_id", "rep_info_need_rep",
    "rep_info_rep_from_unalign_head", "rep_info_tlb_full", "rep_info_tlb_id",
    "schedIndex", "specialModeEligible", "specialModeRequest",
    "uop_fpWen", "uop_ftqOffset", "uop_ftqPtr_flag", "uop_ftqPtr_value",
    "uop_fuOpType", "uop_isRVC", "uop_loadWaitBit", "uop_loadWaitStrict",
    "uop_lqIdx_flag", "uop_lqIdx_value", "uop_pdest",
    "uop_perfDebugInfo_runahead_checkpoint_id", "uop_rfWen",
    "uop_robIdx_flag", "uop_robIdx_isFormer", "uop_robIdx_value",
    "uop_sqIdx_first_flag", "uop_sqIdx_second_flag", "uop_sqIdx_value",
    "uop_storeSetHit", "uop_v0Wen", "uop_vecWen",
    "uop_waitSqIdx_first_flag", "uop_waitSqIdx_second_flag",
    "uop_waitSqIdx_value", "updateAddrValid", "vaddr",
)

_PREFETCH_TRAIN_FIELDS = (
    "isFirstIssue", "isHwPrefetch", "metaSource", "miss", "paddr",
    "robIdx_flag", "robIdx_isFormer", "robIdx_value", "vaddr",
)

PIN_NAMES = frozenset(
    {
        "io_cancel",
        "io_dcache_is128Req",
        "io_dcache_req_bits_cmd",
        "io_dcache_req_bits_instrtype",
        "io_dcache_req_bits_lqIdx_flag",
        "io_dcache_req_bits_lqIdx_value",
        "io_dcache_req_bits_mask",
        "io_dcache_req_bits_vaddr",
        "io_dcache_req_bits_vaddr_dup",
        "io_dcache_req_valid",
        "io_dcache_s1_kill",
        "io_dcache_s1_paddr_dup_dcache",
        "io_dcache_s1_paddr_dup_lsu",
        "io_dcache_s2_kill",
        "io_exceptionInfo_valid",
        "io_ldin_ready",
        "io_ldout_toIntRf_valid",
        "io_ldout_toFpRf_valid",
        "io_ldout_toRob_valid",
        "io_lqWrite_valid",
        "io_mshrForward_s0Req_valid",
        "io_prefetchTrain_valid",
        "io_prefetchTrainHintS1",
        "io_prefetchTrainHintS2",
        "io_rarNukeQuery_req_valid",
        "io_rarNukeQuery_revokeLastCycle",
        "io_rarNukeQuery_revokeLastLastCycle",
        "io_rawNukeQuery_req_valid",
        "io_rawNukeQuery_revokeLastCycle",
        "io_rawNukeQuery_revokeLastLastCycle",
        "io_replay_ready",
        "io_rollback_valid",
        "io_rrBankConflictFastReplay_candidate",
        "io_sbufferForward_s0Req_valid",
        "io_sbufferForward_s1Kill",
        "io_sqForward_s0Req_valid",
        "io_sqForward_s1Kill",
        "io_swInstrPrefetch_valid",
        "io_tlb_req_valid",
        "io_tlb_req_kill",
        "io_uncacheBypass_s0Req_valid",
        "io_uncacheForward_s0Req_valid",
        "io_uncacheForward_s1Kill",
        "io_vldS3WakeUp_pdest",
        "io_vldS3WakeUp_wen",
        "io_vldout_pdest",
        "io_vldout_toV0Rf_valid",
        "io_vldout_toVecRf_valid",
        "io_vldout_toRob_valid",
        "io_wakeup_valid",
        "io_vldout_toV0Rf_bits",
        "io_vldout_toVecRf_bits",
        "io_ldout_toIntRf_bits_data",
        "io_ldout_toIntRf_bits_pdest",
        "io_ldout_toFpRf_bits_data",
        "io_ldout_toFpRf_bits_pdest",
        "io_swInstrPrefetch_bits_vaddr",
        "io_tlb_req_bits_vaddr",
        "io_tlb_req_bits_fullva",
        "io_tlb_req_bits_checkfullva",
        "io_tlb_req_bits_hyperinst",
        "io_tlb_req_bits_hlvx",
        "io_tlb_req_bits_kill",
        "io_tlb_req_bits_isPrefetch",
        "io_tlb_req_bits_no_translate",
        "io_tlb_req_bits_pmp_addr",
        "io_tlb_req_bits_debug_robIdx_flag",
        "io_tlb_req_bits_debug_robIdx_value",
        "io_tlb_req_bits_debug_robIdx_isFormer",
        "io_dcache_s1_paddr_dup_lsu",
        "io_sqForward_s0Req_bits_vaddr",
        "io_sqForward_s1Req_paddr",
        "io_sqForward_s0Req_bits_sqIdx_first_flag",
        "io_sqForward_s0Req_bits_sqIdx_second_flag",
        "io_sqForward_s0Req_bits_sqIdx_value",
        "io_sqForward_s0Req_bits_size",
        "io_sqForward_s0Req_bits_loadWaitBit",
        "io_sqForward_s0Req_bits_loadWaitStrict",
        "io_sqForward_s0Req_bits_waitSqIdx_first_flag",
        "io_sqForward_s0Req_bits_waitSqIdx_second_flag",
        "io_sqForward_s0Req_bits_waitSqIdx_value",
        "io_sbufferForward_s0Req_bits_vaddr",
        "io_sbufferForward_s1Req_paddr",
        "io_uncacheForward_s0Req_bits_vaddr",
        "io_uncacheForward_s1Req_paddr",
        "io_mshrForward_s0Req_bits_mshrId",
        "io_mshrForward_s1Req_paddr",
        "io_uncacheBypass_s0Req_bits_lqIdx_flag",
        "io_uncacheBypass_s0Req_bits_lqIdx_value",
        "io_uncacheBypass_s0Req_bits_isNCReplay",
        "io_uncacheBypass_s0Req_bits_isMMIOReplay",
        "io_wakeup_bits_rfWen",
        "io_wakeup_bits_fpWen",
        "io_wakeup_bits_pdest",
        "io_rarNukeQuery_req_bits_robIdx_flag",
        "io_rarNukeQuery_req_bits_robIdx_value",
        "io_rarNukeQuery_req_bits_robIdx_isFormer",
        "io_rarNukeQuery_req_bits_paddr",
        "io_rarNukeQuery_req_bits_lqIdx_flag",
        "io_rarNukeQuery_req_bits_lqIdx_value",
        "io_rarNukeQuery_req_bits_dataValid",
        "io_rarNukeQuery_req_bits_nc",
        "io_rawNukeQuery_req_bits_robIdx_flag",
        "io_rawNukeQuery_req_bits_robIdx_value",
        "io_rawNukeQuery_req_bits_robIdx_isFormer",
        "io_rawNukeQuery_req_bits_paddr",
        "io_rawNukeQuery_req_bits_sqIdx_first_flag",
        "io_rawNukeQuery_req_bits_sqIdx_second_flag",
        "io_rawNukeQuery_req_bits_sqIdx_value",
        "io_rawNukeQuery_req_bits_dataValid",
        "io_rawNukeQuery_req_bits_mask",
        "io_rawNukeQuery_req_bits_isRVC",
        "io_rawNukeQuery_req_bits_ftqPtr_flag",
        "io_rawNukeQuery_req_bits_ftqPtr_value",
        "io_rawNukeQuery_req_bits_ftqOffset",
        "io_rawNukeQuery_req_bits_debugInfo_runahead_checkpoint_id",
        "io_rollback_bits_robIdx_flag",
        "io_rollback_bits_robIdx_value",
        "io_rollback_bits_robIdx_isFormer",
        "io_rollback_bits_level",
        "io_rollback_bits_ftqIdx_flag",
        "io_rollback_bits_ftqIdx_value",
        "io_rollback_bits_ftqOffset",
        "io_rollback_bits_isRVC",
        "io_rollback_bits_debug_runahead_checkpoint_id",
        "io_ldout_toRob_bits_robIdx_flag",
        "io_ldout_toRob_bits_robIdx_value",
        "io_ldout_toRob_bits_robIdx_isFormer",
        "io_ldout_toRob_bits_trigger",
        "io_ldout_toRob_bits_debugInfo_isMMIO",
        "io_ldout_toRob_bits_debugInfo_isNCIO",
        "io_vldout_toRob_bits_robIdx_flag",
        "io_vldout_toRob_bits_robIdx_value",
        "io_vldout_toRob_bits_robIdx_isFormer",
        "io_vldout_toRob_bits_trigger",
        "io_exceptionInfo_bits_robIdx_flag",
        "io_exceptionInfo_bits_robIdx_value",
        "io_exceptionInfo_bits_robIdx_isFormer",
        "io_exceptionInfo_bits_vaddr",
        "io_exceptionInfo_bits_gpaddr",
        "io_exceptionInfo_bits_vaNeedExt",
        "io_exceptionInfo_bits_isHyper",
        "io_exceptionInfo_bits_isForVSnonLeafPTE",
    }
    | {f"io_ldout_toRob_bits_exceptionVec_{code}" for code in _EXCEPTION_CODES}
    | {f"io_vldout_toRob_bits_exceptionVec_{code}" for code in _EXCEPTION_CODES}
    | {f"io_exceptionInfo_bits_exceptionVec_{code}" for code in _EXCEPTION_CODES}
    | {f"io_lqWrite_bits_{name}" for name in _LQ_FIELDS}
    | {f"io_lqWrite_bits_uop_exceptionVec_{code}" for code in _EXCEPTION_CODES}
    | {f"io_lqWrite_bits_rep_info_cause_{code}" for code in _REPLAY_CODES}
    | {f"io_prefetchTrain_bits_{name}" for name in _PREFETCH_TRAIN_FIELDS}
    | {f"io_perf_{index}_value" for index in range(8)}
    | {f"io_tldForward_{index}_{name}"
       for index in range(2)
       for name in ("s0Req_valid", "s0Req_bits_mshrId", "s1Req_paddr")}
)


class _Reader:
    """Reads one public pin and records that the monitor consumed it."""

    def __init__(self, pins) -> None:
        self.pins = pins
        self.used = set()

    def __call__(self, name: str) -> int:
        self.used.add(name)
        try:
            value = self.pins[name]
        except KeyError as error:
            raise KeyError(f"monitor requires missing output pin {name!r}") from error
        return int(value)


def _rob(read: _Reader, prefix: str) -> RobTag:
    return RobTag(value=read(f"{prefix}_value"), flag=read(f"{prefix}_flag"),
                  is_former=read(f"{prefix}_isFormer"))


def _sq(read: _Reader, prefix: str) -> SqTag:
    return SqTag(value=read(f"{prefix}_value"),
                 first_flag=read(f"{prefix}_first_flag"),
                 second_flag=read(f"{prefix}_second_flag"))


def _lq(read: _Reader, prefix: str) -> LqTag:
    return LqTag(value=read(f"{prefix}_value"), flag=read(f"{prefix}_flag"))


def _exceptions(read: _Reader, prefix: str) -> ExceptionBits:
    return ExceptionBits(bits=frozenset(
        code for code in _EXCEPTION_CODES if read(f"{prefix}_exceptionVec_{code}")))


def _single(read: _Reader, name: str) -> int:
    return read(f"io_{name}")


def decode_snapshot(pins, cycle: int = 0) -> LoadPipelineSnapshot:
    read = _Reader(pins)

    tld_forward = tuple(
        TldForwardRequest(valid=read(f"io_tldForward_{index}_s0Req_valid"),
                          mshr_id=read(f"io_tldForward_{index}_s0Req_bits_mshrId"),
                          s1_paddr=read(f"io_tldForward_{index}_s1Req_paddr"))
        for index in range(2))

    s0 = Stage0Observation(
        ldin_ready=_single(read, "ldin_ready"),
        replay_ready=_single(read, "replay_ready"),
        tlb=TlbRequest(
            valid=read("io_tlb_req_valid"),
            vaddr=read("io_tlb_req_bits_vaddr"),
            fullva=read("io_tlb_req_bits_fullva"),
            check_fullva=read("io_tlb_req_bits_checkfullva"),
            hyperinst=read("io_tlb_req_bits_hyperinst"),
            hlvx=read("io_tlb_req_bits_hlvx"),
            kill=read("io_tlb_req_bits_kill"),
            is_prefetch=read("io_tlb_req_bits_isPrefetch"),
            no_translate=read("io_tlb_req_bits_no_translate"),
            debug_rob=_rob(read, "io_tlb_req_bits_debug_robIdx")),
        dcache=DcacheRequest(
            valid=read("io_dcache_req_valid"),
            cmd=read("io_dcache_req_bits_cmd"),
            vaddr=read("io_dcache_req_bits_vaddr"),
            vaddr_dup=read("io_dcache_req_bits_vaddr_dup"),
            mask=read("io_dcache_req_bits_mask"),
            instr_type=read("io_dcache_req_bits_instrtype"),
            lq=LqTag(value=read("io_dcache_req_bits_lqIdx_value"),
                     flag=read("io_dcache_req_bits_lqIdx_flag")),
            is_128=read("io_dcache_is128Req")),
        wakeup=Wakeup(
            valid=read("io_wakeup_valid"),
            rf_wen=read("io_wakeup_bits_rfWen"),
            fp_wen=read("io_wakeup_bits_fpWen"),
            pdest=read("io_wakeup_bits_pdest")),
        store_forward=StoreForwardRequest(
            valid=read("io_sqForward_s0Req_valid"),
            vaddr=read("io_sqForward_s0Req_bits_vaddr"),
            sq=_sq(read, "io_sqForward_s0Req_bits_sqIdx"),
            size=read("io_sqForward_s0Req_bits_size"),
            load_wait_bit=read("io_sqForward_s0Req_bits_loadWaitBit"),
            load_wait_strict=read("io_sqForward_s0Req_bits_loadWaitStrict"),
            wait_sq=_sq(read, "io_sqForward_s0Req_bits_waitSqIdx")),
        sbuffer_forward=SimpleForwardRequest(
            valid=read("io_sbufferForward_s0Req_valid"),
            vaddr=read("io_sbufferForward_s0Req_bits_vaddr")),
        uncache_forward=SimpleForwardRequest(
            valid=read("io_uncacheForward_s0Req_valid"),
            vaddr=read("io_uncacheForward_s0Req_bits_vaddr")),
        mshr_forward=MshrForwardRequest(
            valid=read("io_mshrForward_s0Req_valid"),
            mshr_id=read("io_mshrForward_s0Req_bits_mshrId")),
        tld_forward=tld_forward,
        uncache_bypass=UncacheBypassRequest(
            valid=read("io_uncacheBypass_s0Req_valid"),
            lq=LqTag(value=read("io_uncacheBypass_s0Req_bits_lqIdx_value"),
                     flag=read("io_uncacheBypass_s0Req_bits_lqIdx_flag")),
            replay_is_nc=read("io_uncacheBypass_s0Req_bits_isNCReplay"),
            replay_is_mmio=read("io_uncacheBypass_s0Req_bits_isMMIOReplay")),
    )

    s1 = Stage1Observation(
        prefetch_train_hint=_single(read, "prefetchTrainHintS1"),
        sw_prefetch=SimpleForwardRequest(
            valid=read("io_swInstrPrefetch_valid"),
            vaddr=read("io_swInstrPrefetch_bits_vaddr")),
        tlb_kill=read("io_tlb_req_kill"),
        tlb_pmp_addr=read("io_tlb_req_bits_pmp_addr"),
        dcache_kill=read("io_dcache_s1_kill"),
        dcache_s1_paddr_lsu=read("io_dcache_s1_paddr_dup_lsu"),
        dcache_s1_paddr_dcache=read("io_dcache_s1_paddr_dup_dcache"),
        store_forward_paddr=read("io_sqForward_s1Req_paddr"),
        store_forward_kill=read("io_sqForward_s1Kill"),
        sbuffer_forward_paddr=read("io_sbufferForward_s1Req_paddr"),
        sbuffer_forward_kill=read("io_sbufferForward_s1Kill"),
        uncache_forward_paddr=read("io_uncacheForward_s1Req_paddr"),
        uncache_forward_kill=read("io_uncacheForward_s1Kill"),
        mshr_forward_paddr=read("io_mshrForward_s1Req_paddr"),
    )

    s2 = Stage2Observation(
        rar_nuke_query=RarNukeQuery(
            valid=read("io_rarNukeQuery_req_valid"),
            rob=_rob(read, "io_rarNukeQuery_req_bits_robIdx"),
            paddr=read("io_rarNukeQuery_req_bits_paddr"),
            lq=_lq(read, "io_rarNukeQuery_req_bits_lqIdx"),
            data_valid=read("io_rarNukeQuery_req_bits_dataValid"),
            nc=read("io_rarNukeQuery_req_bits_nc")),
        raw_nuke_query=RawNukeQuery(
            valid=read("io_rawNukeQuery_req_valid"),
            rob=_rob(read, "io_rawNukeQuery_req_bits_robIdx"),
            paddr=read("io_rawNukeQuery_req_bits_paddr"),
            sq=_sq(read, "io_rawNukeQuery_req_bits_sqIdx"),
            data_valid=read("io_rawNukeQuery_req_bits_dataValid"),
            mask=read("io_rawNukeQuery_req_bits_mask"),
            is_rvc=read("io_rawNukeQuery_req_bits_isRVC"),
            ftq=FtqPtr(value=read("io_rawNukeQuery_req_bits_ftqPtr_value"),
                       flag=read("io_rawNukeQuery_req_bits_ftqPtr_flag")),
            ftq_offset=read("io_rawNukeQuery_req_bits_ftqOffset"),
            debug_id=read(
                "io_rawNukeQuery_req_bits_debugInfo_runahead_checkpoint_id")),
        rr_bank_conflict_candidate=read("io_rrBankConflictFastReplay_candidate"),
        dcache_kill=read("io_dcache_s2_kill"),
        prefetch_train_hint=_single(read, "prefetchTrainHintS2"),
    )

    lq = LqWrite(
        valid=read("io_lqWrite_valid"),
        paddr=read("io_lqWrite_bits_paddr"),
        vaddr=read("io_lqWrite_bits_vaddr"),
        fullva=read("io_lqWrite_bits_fullva"),
        gpaddr=read("io_lqWrite_bits_gpaddr"),
        mask=read("io_lqWrite_bits_mask"),
        aligned_type=read("io_lqWrite_bits_alignedType"),
        is_vec=read("io_lqWrite_bits_isvec"),
        is_for_vs_non_leaf_pte=read("io_lqWrite_bits_isForVSnonLeafPTE"),
        is_hyper=read("io_lqWrite_bits_isHyper"),
        mmio=read("io_lqWrite_bits_mmio"),
        nc=read("io_lqWrite_bits_nc"),
        mem_back_type_mm=read("io_lqWrite_bits_memBackTypeMM"),
        sched_index=read("io_lqWrite_bits_schedIndex"),
        special_mode_request=read("io_lqWrite_bits_specialModeRequest"),
        special_mode_eligible=read("io_lqWrite_bits_specialModeEligible"),
        tlb_id=read("io_lqWrite_bits_rep_info_tlb_id"),
        tlb_full=read("io_lqWrite_bits_rep_info_tlb_full"),
        mshr_id=read("io_lqWrite_bits_rep_info_mshr_id"),
        handled_by_mshr=read("io_lqWrite_bits_handledByMSHR"),
        need_rep=read("io_lqWrite_bits_rep_info_need_rep"),
        last_beat=read("io_lqWrite_bits_rep_info_last_beat"),
        rep_from_unalign_head=read(
            "io_lqWrite_bits_rep_info_rep_from_unalign_head"),
        update_addr_valid=read("io_lqWrite_bits_updateAddrValid"),
        is_load_replay=read("io_lqWrite_bits_isLoadReplay"),
        replay_causes=ReplayCauses(frozenset(
            code for code in _REPLAY_CODES
            if read(f"io_lqWrite_bits_rep_info_cause_{code}"))),
        uop_rob=_rob(read, "io_lqWrite_bits_uop_robIdx"),
        uop_lq=_lq(read, "io_lqWrite_bits_uop_lqIdx"),
        uop_sq=_sq(read, "io_lqWrite_bits_uop_sqIdx"),
        uop_fu_op=read("io_lqWrite_bits_uop_fuOpType"),
        uop_ftq=FtqPtr(value=read("io_lqWrite_bits_uop_ftqPtr_value"),
                       flag=read("io_lqWrite_bits_uop_ftqPtr_flag")),
        uop_ftq_offset=read("io_lqWrite_bits_uop_ftqOffset"),
        uop_is_rvc=read("io_lqWrite_bits_uop_isRVC"),
        uop_load_wait_bit=read("io_lqWrite_bits_uop_loadWaitBit"),
        uop_load_wait_strict=read("io_lqWrite_bits_uop_loadWaitStrict"),
        uop_debug_id=read(
            "io_lqWrite_bits_uop_perfDebugInfo_runahead_checkpoint_id"),
        uop_pdest=read("io_lqWrite_bits_uop_pdest"),
        uop_rf_wen=read("io_lqWrite_bits_uop_rfWen"),
        uop_fp_wen=read("io_lqWrite_bits_uop_fpWen"),
        uop_vec_wen=read("io_lqWrite_bits_uop_vecWen"),
        uop_v0_wen=read("io_lqWrite_bits_uop_v0Wen"),
        uop_store_set_hit=read("io_lqWrite_bits_uop_storeSetHit"),
        uop_wait_sq=_sq(read, "io_lqWrite_bits_uop_waitSqIdx"),
        addr_invalid_sq=_sq(read, "io_lqWrite_bits_rep_info_addr_inv_sq_idx"),
        data_invalid_sq=_sq(read, "io_lqWrite_bits_rep_info_data_inv_sq_idx"),
        exceptions=ExceptionBits(bits=frozenset(
            code for code in _EXCEPTION_CODES
            if read(f"io_lqWrite_bits_uop_exceptionVec_{code}"))),
    )

    s3 = Stage3Observation(
        ldout=RobWriteback(
            valid=read("io_ldout_toRob_valid"),
            rob=_rob(read, "io_ldout_toRob_bits_robIdx"),
            exceptions=_exceptions(read, "io_ldout_toRob_bits"),
            trigger=read("io_ldout_toRob_bits_trigger"),
            is_mmio=read("io_ldout_toRob_bits_debugInfo_isMMIO"),
            is_nc=read("io_ldout_toRob_bits_debugInfo_isNCIO")),
        vldout=VectorRobWriteback(
            valid=read("io_vldout_toRob_valid"),
            rob=_rob(read, "io_vldout_toRob_bits_robIdx"),
            exceptions=_exceptions(read, "io_vldout_toRob_bits"),
            trigger=read("io_vldout_toRob_bits_trigger")),
        vldout_pdest=read("io_vldout_pdest"),
        int_rf=IntRfWrite(
            valid=read("io_ldout_toIntRf_valid"),
            pdest=read("io_ldout_toIntRf_bits_pdest"),
            data=read("io_ldout_toIntRf_bits_data")),
        fp_rf=FpRfWrite(
            valid=read("io_ldout_toFpRf_valid"),
            pdest=read("io_ldout_toFpRf_bits_pdest"),
            data=read("io_ldout_toFpRf_bits_data")),
        vec_rf=VectorRfWrite(valid=read("io_vldout_toVecRf_valid"),
                             data=read("io_vldout_toVecRf_bits")),
        v0_rf=VectorRfWrite(valid=read("io_vldout_toV0Rf_valid"),
                            data=read("io_vldout_toV0Rf_bits")),
        vector_wakeup=VectorWakeup(wen=read("io_vldS3WakeUp_wen"),
                                   pdest=read("io_vldS3WakeUp_pdest")),
        lq=lq,
        rar_revoke=Revoke(last_cycle=read("io_rarNukeQuery_revokeLastCycle"),
                          last_last_cycle=read(
                              "io_rarNukeQuery_revokeLastLastCycle")),
        raw_revoke=Revoke(last_cycle=read("io_rawNukeQuery_revokeLastCycle"),
                          last_last_cycle=read(
                              "io_rawNukeQuery_revokeLastLastCycle")),
        rollback=Rollback(
            valid=read("io_rollback_valid"),
            rob=_rob(read, "io_rollback_bits_robIdx"),
            level=read("io_rollback_bits_level"),
            ftq=FtqPtr(value=read("io_rollback_bits_ftqIdx_value"),
                       flag=read("io_rollback_bits_ftqIdx_flag")),
            ftq_offset=read("io_rollback_bits_ftqOffset"),
            is_rvc=read("io_rollback_bits_isRVC"),
            debug_id=read("io_rollback_bits_debug_runahead_checkpoint_id")),
        exception_info=ExceptionInfo(
            valid=read("io_exceptionInfo_valid"),
            rob=_rob(read, "io_exceptionInfo_bits_robIdx"),
            vaddr=read("io_exceptionInfo_bits_vaddr"),
            gpaddr=read("io_exceptionInfo_bits_gpaddr"),
            va_need_ext=read("io_exceptionInfo_bits_vaNeedExt"),
            is_hyper=read("io_exceptionInfo_bits_isHyper"),
            is_for_vs_non_leaf_pte=read(
                "io_exceptionInfo_bits_isForVSnonLeafPTE"),
            exceptions=_exceptions(read, "io_exceptionInfo_bits")),
        cancel=_single(read, "cancel"),
    )

    prefetch_train = PrefetchTrain(
        valid=_single(read, "prefetchTrain_valid"),
        rob=_rob(read, "io_prefetchTrain_bits_robIdx"),
        vaddr=read("io_prefetchTrain_bits_vaddr"),
        paddr=read("io_prefetchTrain_bits_paddr"),
        miss=read("io_prefetchTrain_bits_miss"),
        meta_source=read("io_prefetchTrain_bits_metaSource"),
        is_first_issue=read("io_prefetchTrain_bits_isFirstIssue"),
        is_hw_prefetch=read("io_prefetchTrain_bits_isHwPrefetch"),
    )

    perf = PerfCounters(values=tuple(
        read(f"io_perf_{index}_value") for index in range(8)))

    if read.used != PIN_NAMES:
        missing = sorted(PIN_NAMES - read.used)
        extra = sorted(read.used - PIN_NAMES)
        raise RuntimeError(
            f"NewLoadUnit monitor pin set drift: missing={missing} extra={extra}")

    return LoadPipelineSnapshot(cycle=cycle, s0=s0, s1=s1, s2=s2, s3=s3,
                                prefetch_train=prefetch_train, perf=perf)


def check_pin_inventory(output_pins) -> None:
    """Fail when the generated DUT and the monitor no longer agree."""
    expected = set(PIN_NAMES)
    actual = set(output_pins)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise RuntimeError(
            "NewLoadUnit output pin inventory mismatch: "
            f"missing={missing} unmonitored={extra}")
