"""Environment and independent reference for LoadUnitS3.

S3 is the load writeback/commit stage. It owns five independent behaviours:

* **unaligned head merge** (``unalignConcat``): when the S4 head is waiting for
  its tail, S3 arbitrates between "head-then-tail" and "tail-only". A tail that
  arrives while the head is present cancels the head's writeback
  (``cancel = head.unalignHead & unalignTailValid``) and replaces its
  exception/address payload; otherwise both beats are emitted in order.
* **writeback arming**: ``headAlwaysWriteback = s3Exception | matchInvalid`` and
  ``writebackDependOnTail = shouldWriteback & ~s3Exception & ~matchInvalid`` so a
  head with an exception never waits for a tail.
* **vector / scalar dispatch**: scalar loads emit ``ldout`` (and an interrupt-RF
  write when ``shouldWakeup``); vector loads emit ``vldout`` and a vector-register
  wakeup, never a scalar RF write.
* **replay/revoke**: ``fastReplay`` to S0, ``revokeLastCycle``/``revokeLastLastCycle``
  for the replay queue, ``rollback`` on RAR violation or match-invalid.
* **LQ write**: the load-queue entry update with the merged exception vector and
  the one-hot replay cause.

Contract: docs/contracts/load-s3.md
"""
from __future__ import annotations

import random

PIPEIN_FIELDS = {
    "entrance": 8,
    "accessType_instrType": 3,
    "accessType_pftType": 2,
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_21": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_13": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_6": 1,
    "uop_exceptionVec_5": 1,
    "uop_exceptionVec_4": 1,
    "uop_exceptionVec_3": 1,
    "uop_trigger": 4,
    "uop_isRVC": 1,
    "uop_ftqPtr_flag": 1,
    "uop_ftqPtr_value": 6,
    "uop_ftqOffset": 5,
    "uop_fuOpType": 12,
    "uop_rfWen": 1,
    "uop_fpWen": 1,
    "uop_vecWen": 1,
    "uop_v0Wen": 1,
    "uop_pdest": 8,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "uop_perfDebugInfo_runahead_checkpoint_id": 64,
    "uop_storeSetHit": 1,
    "uop_waitSqIdx_first_flag": 1,
    "uop_waitSqIdx_second_flag": 1,
    "uop_waitSqIdx_value": 6,
    "uop_loadWaitBit": 1,
    "uop_loadWaitStrict": 1,
    "uop_lqIdx_flag": 1,
    "uop_lqIdx_value": 7,
    "uop_sqIdx_first_flag": 1,
    "uop_sqIdx_second_flag": 1,
    "uop_sqIdx_value": 6,
    "vaddr": 50,
    "fullva": 64,
    "size": 3,
    "mask": 16,
    "paddr": 48,
    "unalignHead": 1,
    "tlbException_vaNeedExt": 1,
    "tlbException_isHyper": 1,
    "gpaddr": 64,
    "isForVSnonLeafPTE": 1,
    "pmp_mmio": 1,
    "nc": 1,
    "mmio": 1,
    "mshrId": 4,
    "replayQueueIdx": 7,
    "cause_0": 1,
    "cause_1": 1,
    "cause_2": 1,
    "cause_3": 1,
    "cause_4": 1,
    "cause_5": 1,
    "cause_6": 1,
    "cause_8": 1,
    "cause_9": 1,
    "cause_10": 1,
    "cause_11": 1,
    "specialModeRequest": 1,
    "handledByMSHR": 1,
    "dataInvalidSqIdx_first_flag": 1,
    "dataInvalidSqIdx_second_flag": 1,
    "dataInvalidSqIdx_value": 6,
    "addrInvalidSqIdx_first_flag": 1,
    "addrInvalidSqIdx_second_flag": 1,
    "addrInvalidSqIdx_value": 6,
    "tlbId": 4,
    "tlbFull": 1,
    "uncacheReplay": 1,
    "ncReplay": 1,
    "shouldFastReplay": 1,
    "causeOrR": 1,
    "rrBankConflictFastReplay": 1,
    "rrBankConflictFastReplayGrant": 1,
    "matchInvalid": 1,
    "shouldWakeup": 1,
    "shouldWriteback": 1,
}
PIPEOUT_FIELDS = {
    "entrance": 8,
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_21": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_13": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_6": 1,
    "uop_exceptionVec_5": 1,
    "uop_exceptionVec_4": 1,
    "uop_exceptionVec_3": 1,
    "vaddr": 50,
    "fullva": 64,
    "mask": 16,
    "paddr": 48,
    "tlbException_vaNeedExt": 1,
    "gpaddr": 64,
    "isForVSnonLeafPTE": 1,
    "mshrId": 4,
    "cause_0": 1,
    "cause_1": 1,
    "cause_2": 1,
    "cause_3": 1,
    "cause_4": 1,
    "cause_5": 1,
    "cause_6": 1,
    "cause_8": 1,
    "cause_9": 1,
    "cause_10": 1,
    "cause_11": 1,
    "specialModeRequest": 1,
    "handledByMSHR": 1,
    "tlbId": 4,
    "tlbFull": 1,
    "causeOrR": 1,
    "matchInvalid": 1,
    "shouldWakeup": 1,
    "hasException": 1,
    "headAlwaysWriteback": 1,
    "writebackDependOnTail": 1,
    "shouldRarViolation": 1,
}
CONCAT_FIELDS = {
    "entrance": 8,
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_21": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_13": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_6": 1,
    "uop_exceptionVec_5": 1,
    "uop_exceptionVec_4": 1,
    "uop_exceptionVec_3": 1,
    "vaddr": 50,
    "fullva": 64,
    "mask": 16,
    "paddr": 48,
    "tlbException_vaNeedExt": 1,
    "gpaddr": 64,
    "isForVSnonLeafPTE": 1,
    "mshrId": 4,
    "cause_0": 1,
    "cause_1": 1,
    "cause_2": 1,
    "cause_3": 1,
    "cause_4": 1,
    "cause_5": 1,
    "cause_6": 1,
    "cause_8": 1,
    "cause_9": 1,
    "cause_10": 1,
    "cause_11": 1,
    "specialModeRequest": 1,
    "handledByMSHR": 1,
    "tlbId": 4,
    "tlbFull": 1,
    "causeOrR": 1,
    "matchInvalid": 1,
    "shouldWakeup": 1,
    "hasException": 1,
    "headAlwaysWriteback": 1,
    "writebackDependOnTail": 1,
    "shouldRarViolation": 1,
}
LDOUT_FIELDS = {
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "exceptionVec_23": 1,
    "exceptionVec_21": 1,
    "exceptionVec_19": 1,
    "exceptionVec_15": 1,
    "exceptionVec_13": 1,
    "exceptionVec_7": 1,
    "exceptionVec_6": 1,
    "exceptionVec_5": 1,
    "exceptionVec_4": 1,
    "exceptionVec_3": 1,
    "trigger": 4,
    "debugInfo_isMMIO": 1,
    "debugInfo_isNCIO": 1,
}
VLDOUT_FIELDS = {
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "exceptionVec_23": 1,
    "exceptionVec_21": 1,
    "exceptionVec_19": 1,
    "exceptionVec_15": 1,
    "exceptionVec_13": 1,
    "exceptionVec_7": 1,
    "exceptionVec_6": 1,
    "exceptionVec_5": 1,
    "exceptionVec_4": 1,
    "exceptionVec_3": 1,
    "trigger": 4,
}
LQWRITE_FIELDS = {
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_21": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_13": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_6": 1,
    "uop_exceptionVec_5": 1,
    "uop_exceptionVec_4": 1,
    "uop_exceptionVec_3": 1,
    "uop_isRVC": 1,
    "uop_ftqPtr_flag": 1,
    "uop_ftqPtr_value": 6,
    "uop_ftqOffset": 5,
    "uop_fuOpType": 12,
    "uop_rfWen": 1,
    "uop_fpWen": 1,
    "uop_vecWen": 1,
    "uop_v0Wen": 1,
    "uop_pdest": 8,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "uop_perfDebugInfo_runahead_checkpoint_id": 64,
    "uop_storeSetHit": 1,
    "uop_waitSqIdx_first_flag": 1,
    "uop_waitSqIdx_second_flag": 1,
    "uop_waitSqIdx_value": 6,
    "uop_loadWaitBit": 1,
    "uop_loadWaitStrict": 1,
    "uop_lqIdx_flag": 1,
    "uop_lqIdx_value": 7,
    "uop_sqIdx_first_flag": 1,
    "uop_sqIdx_second_flag": 1,
    "uop_sqIdx_value": 6,
    "vaddr": 50,
    "fullva": 64,
    "paddr": 48,
    "gpaddr": 64,
    "mask": 16,
    "nc": 1,
    "mmio": 1,
    "memBackTypeMM": 1,
    "isHyper": 1,
    "isForVSnonLeafPTE": 1,
    "specialModeEligible": 1,
    "specialModeRequest": 1,
    "isvec": 1,
    "alignedType": 3,
    "isLoadReplay": 1,
    "handledByMSHR": 1,
    "schedIndex": 7,
    "updateAddrValid": 1,
    "rep_info_mshr_id": 4,
    "rep_info_data_inv_sq_idx_first_flag": 1,
    "rep_info_data_inv_sq_idx_second_flag": 1,
    "rep_info_data_inv_sq_idx_value": 6,
    "rep_info_addr_inv_sq_idx_first_flag": 1,
    "rep_info_addr_inv_sq_idx_second_flag": 1,
    "rep_info_addr_inv_sq_idx_value": 6,
    "rep_info_last_beat": 1,
    "rep_info_need_rep": 1,
    "rep_info_cause_0": 1,
    "rep_info_cause_1": 1,
    "rep_info_cause_2": 1,
    "rep_info_cause_3": 1,
    "rep_info_cause_4": 1,
    "rep_info_cause_5": 1,
    "rep_info_cause_6": 1,
    "rep_info_cause_7": 1,
    "rep_info_cause_8": 1,
    "rep_info_cause_9": 1,
    "rep_info_cause_10": 1,
    "rep_info_cause_11": 1,
    "rep_info_cause_12": 1,
    "rep_info_tlb_id": 4,
    "rep_info_tlb_full": 1,
    "rep_info_rep_from_unalign_head": 1,
}
FAST_FIELDS = {
    "entrance": 8,
    "accessType_instrType": 3,
    "accessType_pftType": 2,
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_6": 1,
    "uop_isRVC": 1,
    "uop_ftqPtr_flag": 1,
    "uop_ftqPtr_value": 6,
    "uop_ftqOffset": 5,
    "uop_fuOpType": 12,
    "uop_rfWen": 1,
    "uop_fpWen": 1,
    "uop_vecWen": 1,
    "uop_v0Wen": 1,
    "uop_pdest": 8,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "uop_perfDebugInfo_runahead_checkpoint_id": 64,
    "uop_storeSetHit": 1,
    "uop_waitSqIdx_first_flag": 1,
    "uop_waitSqIdx_second_flag": 1,
    "uop_waitSqIdx_value": 6,
    "uop_loadWaitBit": 1,
    "uop_loadWaitStrict": 1,
    "uop_lqIdx_flag": 1,
    "uop_lqIdx_value": 7,
    "uop_sqIdx_first_flag": 1,
    "uop_sqIdx_second_flag": 1,
    "uop_sqIdx_value": 6,
    "vaddr": 50,
    "fullva": 64,
    "size": 3,
    "mask": 16,
    "paddr": 48,
    "mshrId": 4,
    "replayQueueIdx": 7,
    "uncacheReplay": 1,
    "ncReplay": 1,
}
ROLLBACK_FIELDS = {
    "ftqIdx_flag": 1,
    "ftqIdx_value": 6,
    "ftqOffset": 5,
    "isRVC": 1,
    "level": 1,
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "debug_runahead_checkpoint_id": 64,
}
EXCINFO_FIELDS = {
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "exceptionVec_23": 1,
    "exceptionVec_21": 1,
    "exceptionVec_19": 1,
    "exceptionVec_15": 1,
    "exceptionVec_13": 1,
    "exceptionVec_7": 1,
    "exceptionVec_6": 1,
    "exceptionVec_5": 1,
    "exceptionVec_4": 1,
    "exceptionVec_3": 1,
    "vaddr": 64,
    "vaNeedExt": 1,
    "isHyper": 1,
    "gpaddr": 50,
    "isForVSnonLeafPTE": 1,
}
REDIRECT_FIELDS = {
    "level": 1,
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
}

# Exception bits that S3 ORs to decide "this beat has an exception".
EXC_BITS = ("uop_exceptionVec_23", "uop_exceptionVec_21", "uop_exceptionVec_19",
            "uop_exceptionVec_15", "uop_exceptionVec_13", "uop_exceptionVec_7",
            "uop_exceptionVec_6", "uop_exceptionVec_5", "uop_exceptionVec_4",
            "uop_exceptionVec_3")
CAUSE_KEYS = (0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11)
# One-hot encoding used by the LQ replay-cause field: index -> bit position.
CAUSE_OH = {0: 1, 1: 2, 2: 4, 3: 8, 4: 0x10, 5: 0x20, 6: 0x40,
            8: 0x100, 9: 0x200, 10: 0x400, 11: 0x800}
REDIRECT_FIELDS = {"level": 1, "robIdx_flag": 1, "robIdx_value": 8,
                   "robIdx_isFormer": 1}


def ring_greater(flag_a: int, value_a: int, flag_b: int, value_b: int) -> bool:
    return bool((flag_a ^ flag_b ^ (1 if value_a > value_b else 0)) & 1)


def redirect_kill(pipe: dict, red: dict) -> bool:
    same = (pipe["uop_robIdx_flag"] == red["robIdx_flag"]
            and pipe["uop_robIdx_value"] == red["robIdx_value"])
    level_same = bool(red["level"]) and same and (
        pipe["uop_robIdx_isFormer"] == red["robIdx_isFormer"])
    newer = ring_greater(pipe["uop_robIdx_flag"], pipe["uop_robIdx_value"],
                         red["robIdx_flag"], red["robIdx_value"])
    former = same and not pipe["uop_robIdx_isFormer"] and bool(red["robIdx_isFormer"])
    return bool(level_same or newer or former)


def norm(fields: dict, values: dict | None) -> dict:
    return dict({name: 0 for name in fields}, **(values or {}))


class S3Model:
    def __init__(self) -> None:
        self.pipe_out_valid = 0
        self.pipe_out_bits: dict | None = None

    def reset(self) -> None:
        self.pipe_out_valid = 0
        self.pipe_out_bits = None

    def compute(self, inputs: dict) -> dict:
        pipe = norm(PIPEIN_FIELDS, inputs["pipeIn"]["bits"])
        concat = norm(CONCAT_FIELDS, inputs["concat"]["bits"])
        concat_valid = 1 if inputs["concat"]["valid"] else 0
        pipe_valid = 1 if inputs["pipeIn"]["valid"] else 0
        redirect = inputs["redirect"]
        tail_valid = 1 if inputs["unalignTailValid"] else 0
        ldld = 1 if inputs["ldldCheck"] else 0

        kill = int(bool(redirect["valid"]) and redirect_kill(pipe, redirect["bits"]))
        cancel = int(bool(pipe["unalignHead"]) and bool(tail_valid))

        # The head's exception vector is replaced by the tail's when a tail
        # exists and reports an exception; otherwise the head's own vector is
        # used.
        use_tail_exc = int(bool(concat_valid) and bool(concat["hasException"]))
        exc = {}
        for name in EXC_BITS:
            exc[name] = (concat[name] if use_tail_exc else pipe[name]) & 1
        s3_exception = int(any(pipe[name] & 1 for name in EXC_BITS)
                           or (pipe["uop_trigger"] == 1))
        s4_head_revoke = int(bool(concat["hasException"]) or bool(concat["causeOrR"]))
        s3_revoke = int(bool(s3_exception) or bool(pipe["causeOrR"]))
        s3_rar_violation = int(bool(inputs["rarResp"]["valid"])
                               and bool(inputs["rarResp"]["nuke"]) and bool(ldld)
                               and not s3_exception)
        s3_match_invalid = int(bool(pipe["matchInvalid"]) and not s3_exception)
        match_invalid = int(bool(s3_match_invalid)
                            or (bool(concat_valid) and bool(concat["matchInvalid"])))
        cancel_effective = cancel

        # shouldWakeup is the head's, further qualified by the tail's own bit.
        should_wakeup = int(bool(pipe["shouldWakeup"])
                            and (not concat_valid or bool(concat["shouldWakeup"])))
        allow_rr = int(not (bool(pipe["shouldFastReplay"])
                            and bool(pipe["rrBankConflictFastReplay"]))
                       or bool(pipe["rrBankConflictFastReplayGrant"]))

        if concat_valid:
            base_writeback = int(bool(concat["headAlwaysWriteback"])
                                 or (bool(concat["writebackDependOnTail"])
                                     and bool(pipe["shouldWriteback"])))
        else:
            base_writeback = int(bool(pipe["shouldWriteback"]))
        writeback_armed = int(bool(pipe_valid) and bool(base_writeback))
        ldout_valid = int(bool(writeback_armed) and not pipe["uop_vecWen"]
                          and not cancel_effective)
        vldout_valid = int(bool(writeback_armed) and bool(pipe["uop_vecWen"])
                           and not cancel_effective)
        vld_wakeup = int(bool(pipe["uop_vecWen"]) and bool(pipe_valid)
                         and not cancel_effective and bool(should_wakeup))
        int_rf_valid = int(bool(pipe["uop_rfWen"]) and bool(pipe_valid)
                           and not cancel_effective and bool(should_wakeup))
        fp_rf_valid = int(bool(pipe["uop_fpWen"]) and bool(pipe_valid)
                          and not cancel_effective and bool(should_wakeup))
        v0_rf_valid = int(bool(pipe["uop_v0Wen"]) and bool(pipe_valid)
                          and not cancel_effective and bool(should_wakeup))
        lq_write_valid = int(bool(pipe_valid) and not (
            bool(pipe["shouldFastReplay"]) and bool(inputs["fastReplayReady"])
            and bool(allow_rr)) and not cancel_effective)
        fast_replay_valid = int(bool(pipe_valid) and not kill
                                and bool(pipe["shouldFastReplay"]) and bool(allow_rr))
        rollback_valid = int(bool(pipe_valid)
                             and (bool(s3_rar_violation)
                                  or (bool(concat_valid)
                                      and bool(concat["shouldRarViolation"]))
                                  or bool(match_invalid))
                             and not cancel_effective)
        exception_info_valid = int(bool(ldout_valid)
                                   and not (bool(pipe["uncacheReplay"])
                                            and not pipe["ncReplay"]))
        io_cancel = int(bool(pipe_valid)
                        and (bool(cancel_effective)
                             or (not should_wakeup
                                 and bool(pipe["accessType_instrType"] & 1))))

        # LQ cause one-hot: a tail replay overrides the head's cause set.
        use_head_replay = int(bool(concat_valid) and bool(concat["causeOrR"]))
        cause_src = concat if use_head_replay else pipe
        cause_oh = 0
        for index in CAUSE_KEYS:
            if cause_src.get(f"cause_{index}", 0):
                cause_oh = CAUSE_OH[index]
                break
        paddr = concat["paddr"] if concat_valid else pipe["paddr"]
        lq_nc = int(bool(pipe["nc"]) or (bool(pipe["uncacheReplay"])
                                         and bool(pipe["ncReplay"])))
        last_beat = (paddr >> 5) & 1
        is_replay = int(bool(pipe["entrance"] & 0x0A)
                        or (bool(concat_valid) and bool(concat["entrance"] & 0x0A)))
        handled_by_mshr = (concat["handledByMSHR"]
                           if (concat_valid and concat["cause_6"])
                           else pipe["handledByMSHR"])
        mshr_id = (concat["mshrId"] if (concat_valid and concat["cause_6"])
                   else pipe["mshrId"])

        # ------------------------------------------------------------ pipeOut reg
        out = {}
        for name in PIPEOUT_FIELDS:
            out[name] = pipe.get(name, 0)
        # pipeOut passes the *S3 input* exception vector through unchanged; the
        # head/tail merge only affects the ldout/lqWrite/exceptionInfo views.
        out.update({name: pipe[name] for name in EXC_BITS})
        out.update({
            "matchInvalid": s3_match_invalid,
            "hasException": s3_exception,
            "headAlwaysWriteback": int(bool(s3_exception) or bool(s3_match_invalid)),
            "writebackDependOnTail": int(bool(pipe["shouldWriteback"])
                                         and not s3_exception
                                         and not s3_match_invalid),
            "shouldRarViolation": s3_rar_violation,
        })

        # ------------------------------------------------------- exception view
        def exc_bits(prefix: str) -> dict:
            return {name: exc[name] for name in EXC_BITS}

        ldout = {name: 0 for name in LDOUT_FIELDS}
        ldout.update({"robIdx_flag": pipe["uop_robIdx_flag"],
                      "robIdx_value": pipe["uop_robIdx_value"],
                      "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
                      "trigger": pipe["uop_trigger"],
                      "debugInfo_isMMIO": int(bool(pipe["uncacheReplay"])
                                              and not pipe["ncReplay"]),
                      "debugInfo_isNCIO": int(bool(pipe["uncacheReplay"])
                                              and bool(pipe["ncReplay"])
                                              and bool(pipe["pmp_mmio"]))})
        ldout.update({f"exceptionVec_{name.split('_')[-1]}": value
                      for name, value in exc.items()})
        vldout = {name: 0 for name in VLDOUT_FIELDS}
        vldout.update({"robIdx_flag": pipe["uop_robIdx_flag"],
                       "robIdx_value": pipe["uop_robIdx_value"],
                       "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
                       "trigger": pipe["uop_trigger"]})
        vldout.update({f"exceptionVec_{name.split('_')[-1]}": value
                       for name, value in exc.items()})

        entry = {name: pipe.get(name, 0) for name in LQWRITE_FIELDS}
        entry.update({"isHyper": pipe["tlbException_isHyper"]})
        entry.update(exc)
        entry.update({
            "vaddr": concat["vaddr"] if concat_valid else pipe["vaddr"],
            "fullva": concat["fullva"] if use_tail_exc else pipe["fullva"],
            "paddr": paddr,
            "gpaddr": concat["gpaddr"] if use_tail_exc else pipe["gpaddr"],
            "mask": concat["mask"] if concat_valid else pipe["mask"],
            "nc": lq_nc,
            "memBackTypeMM": int(not pipe["pmp_mmio"]),
            "isForVSnonLeafPTE": (concat["isForVSnonLeafPTE"] if use_tail_exc
                                  else pipe["isForVSnonLeafPTE"]),
            "specialModeEligible": int(
                bool(concat_valid)
                and bool(cause_src["cause_3"] or cause_src["cause_5"]
                         or cause_src["cause_6"])),
            "specialModeRequest": (concat["specialModeRequest"]
                                   if use_head_replay
                                   else pipe["specialModeRequest"]),
            "isvec": int(bool(pipe["accessType_instrType"] & 0x2)),
            "alignedType": pipe["size"],
            "isLoadReplay": is_replay,
            "handledByMSHR": handled_by_mshr,
            "schedIndex": pipe["replayQueueIdx"],
            "updateAddrValid": int(bool(ldout_valid) or bool(vldout_valid)),
            "rep_info_mshr_id": mshr_id,
            "rep_info_last_beat": last_beat,
            "rep_info_need_rep": int(bool(use_head_replay)
                                     or bool(pipe["causeOrR"])),
            "rep_info_tlb_id": (concat["tlbId"] if use_head_replay
                                else pipe["tlbId"]),
            "rep_info_tlb_full": (concat["tlbFull"] if use_head_replay
                                  else pipe["tlbFull"]),
            "rep_info_rep_from_unalign_head": use_head_replay,
        })
        for index in range(13):
            entry[f"rep_info_cause_{index}"] = (cause_oh >> index) & 1
        for src, dst in (("dataInvalidSqIdx_first_flag",
                          "rep_info_data_inv_sq_idx_first_flag"),
                         ("dataInvalidSqIdx_second_flag",
                          "rep_info_data_inv_sq_idx_second_flag"),
                         ("dataInvalidSqIdx_value", "rep_info_data_inv_sq_idx_value"),
                         ("addrInvalidSqIdx_first_flag",
                          "rep_info_addr_inv_sq_idx_first_flag"),
                         ("addrInvalidSqIdx_second_flag",
                          "rep_info_addr_inv_sq_idx_second_flag"),
                         ("addrInvalidSqIdx_value", "rep_info_addr_inv_sq_idx_value")):
            entry[dst] = pipe[src]

        fast = {name: 0 for name in FAST_FIELDS}
        for name in FAST_FIELDS:
            if name in pipe:
                fast[name] = pipe[name]
        rollback = {name: 0 for name in ROLLBACK_FIELDS}
        rollback.update({
            "ftqIdx_flag": pipe["uop_ftqPtr_flag"],
            "ftqIdx_value": pipe["uop_ftqPtr_value"],
            "ftqOffset": pipe["uop_ftqOffset"],
            "isRVC": pipe["uop_isRVC"],
            "level": match_invalid,
            "robIdx_flag": pipe["uop_robIdx_flag"],
            "robIdx_value": pipe["uop_robIdx_value"],
            "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
            "debug_runahead_checkpoint_id":
                pipe["uop_perfDebugInfo_runahead_checkpoint_id"],
        })
        excinfo = {name: 0 for name in EXCINFO_FIELDS}
        excinfo.update({
            "robIdx_flag": pipe["uop_robIdx_flag"],
            "robIdx_value": pipe["uop_robIdx_value"],
            "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
            "vaddr": concat["fullva"] if use_tail_exc else pipe["fullva"],
            "vaNeedExt": (concat["tlbException_vaNeedExt"] if use_tail_exc
                          else pipe["tlbException_vaNeedExt"]),
            "isHyper": pipe["tlbException_isHyper"],
            "gpaddr": (concat["gpaddr"] if use_tail_exc else pipe["gpaddr"]) & ((1 << 50) - 1),
            "isForVSnonLeafPTE": (concat["isForVSnonLeafPTE"] if use_tail_exc
                                  else pipe["isForVSnonLeafPTE"]),
        })
        excinfo.update({f"exceptionVec_{name.split('_')[-1]}": value
                        for name, value in exc.items()})

        return {
            "next_valid": int(not (kill or not cancel)
                              and bool(inputs["pipeIn"]["valid"])),
            "next_bits": out if inputs["pipeIn"]["valid"] else None,
            "pipe": pipe, "concat": concat, "kill": kill,
            "cancel": cancel, "s3_exception": s3_exception,
            "s3_rar_violation": s3_rar_violation, "match_invalid": match_invalid,
            "should_wakeup": should_wakeup, "ldout_valid": ldout_valid,
            "vldout_valid": vldout_valid, "lq_write_valid": lq_write_valid,
            "fast_replay_valid": fast_replay_valid, "rollback_valid": rollback_valid,
            "exception_info_valid": exception_info_valid, "cancel_out": io_cancel,
            "revoke_last": int(bool(s3_revoke)
                               or (bool(concat_valid) and bool(s4_head_revoke))),
            "revoke_last_last": int(bool(concat_valid) and not s4_head_revoke
                                    and bool(s3_revoke)),
            "exc": exc, "ldout": ldout, "vldout": vldout, "lq": entry,
            "fast": fast, "rollback": rollback, "excinfo": excinfo,
            "vld_wakeup": vld_wakeup, "pdest": pipe["uop_pdest"] & 0x7F,
            "vldout_pdest": pipe["uop_pdest"],
            "int_rf": int_rf_valid, "fp_rf": fp_rf_valid, "v0_rf": v0_rf_valid,
            "out": out, "cause_oh": cause_oh,
        }

    def advance(self, inputs: dict, result: dict) -> None:
        if inputs["pipeIn"]["valid"]:
            self.pipe_out_bits = result["out"]
        self.pipe_out_valid = result["next_valid"]

    def cycle(self, inputs: dict) -> dict:
        result = self.compute(inputs)
        self.advance(inputs, result)
        return {
            "pipeOut_valid": self.pipe_out_valid,
            "pipeOut_bits": self.pipe_out_bits,
            "vld_wakeup": result["vld_wakeup"],
            "vldout_pdest": result.get("vldout_pdest", 0),
            "pdest": result["pdest"],
            "ldout_valid": result["ldout_valid"],
            "ldout": result["ldout"],
            "vldout_valid": result["vldout_valid"],
            "vldout": result["vldout"],
            "lq_write_valid": result["lq_write_valid"],
            "lq": result["lq"],
            "fast_replay_valid": result["fast_replay_valid"],
            "fast": result["fast"],
            "revoke_last": result["revoke_last"],
            "revoke_last_last": result["revoke_last_last"],
            "rollback_valid": result["rollback_valid"],
            "rollback": result["rollback"],
            "exception_info_valid": result["exception_info_valid"],
            "excinfo": result["excinfo"],
            "cancel": result["cancel"],
            "vec_rf_valid": result["vld_wakeup"],
            "cancel_out": result["cancel_out"],
            "int_rf_valid": result["int_rf"], "fp_rf_valid": result["fp_rf"],
            "v0_rf_valid": result["v0_rf"],
            "detail": result,
        }


class LoadS3Env:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.pipe_valid = dut.io_pipeIn_valid
        self.pipe_bits = {name: getattr(dut, f"io_pipeIn_bits_{name}")
                          for name in PIPEIN_FIELDS}
        self.redirect_valid = dut.io_redirect_valid
        self.redirect_bits = {name: getattr(dut, f"io_redirect_bits_{name}")
                              for name in REDIRECT_FIELDS}
        self.tail_valid = dut.io_unalignTailValid
        self.concat_valid = dut.io_unalignConcat_valid
        self.concat_bits = {name: getattr(dut, f"io_unalignConcat_bits_{name}")
                            for name in CONCAT_FIELDS}
        self.fast_ready = dut.io_fastReplay_ready
        self.rar_valid = dut.io_rarNukeQueryResp_valid
        self.rar_nuke = dut.io_rarNukeQueryResp_bits_nuke
        self.ldld = dut.io_csrCtrl_ldld_vio_check_enable

        self.out_valid = dut.io_pipeOut_valid
        self.out = {name: getattr(dut, f"io_pipeOut_bits_{name}")
                    for name in PIPEOUT_FIELDS}
        self.vld_wakeup = dut.io_vldS3WakeUp_wen
        self.pdest = dut.io_vldS3WakeUp_pdest
        self.ldout_valid = dut.io_ldout_toRob_valid
        self.ldout = {name: getattr(dut, f"io_ldout_toRob_bits_{name}")
                      for name in LDOUT_FIELDS}
        self.int_rf_valid = dut.io_ldout_toIntRf_valid
        self.int_rf_pdest = dut.io_ldout_toIntRf_bits_pdest
        self.fp_rf_valid = dut.io_ldout_toFpRf_valid
        self.fp_rf_pdest = dut.io_ldout_toFpRf_bits_pdest
        self.vldout_valid = dut.io_vldout_toRob_valid
        self.vldout = {name: getattr(dut, f"io_vldout_toRob_bits_{name}")
                       for name in VLDOUT_FIELDS}
        self.vldout_pdest = dut.io_vldout_pdest
        self.vec_rf_valid = dut.io_vldout_toVecRf_valid
        self.v0_rf_valid = dut.io_vldout_toV0Rf_valid
        self.lq_write_valid = dut.io_lqWrite_valid
        self.lq = {name: getattr(dut, f"io_lqWrite_bits_{name}")
                   for name in LQWRITE_FIELDS}
        self.fast_valid = dut.io_fastReplay_valid
        self.fast = {name: getattr(dut, f"io_fastReplay_bits_{name}")
                     for name in FAST_FIELDS}
        self.revoke_last = dut.io_revokeLastCycle
        self.revoke_last_last = dut.io_revokeLastLastCycle
        self.rollback_valid = dut.io_rollback_valid
        self.rollback = {name: getattr(dut, f"io_rollback_bits_{name}")
                         for name in ROLLBACK_FIELDS}
        self.exception_info_valid = dut.io_exceptionInfo_valid
        self.exception_info = {name: getattr(dut, f"io_exceptionInfo_bits_{name}")
                               for name in EXCINFO_FIELDS}
        self.cancel = dut.io_cancel
        self.model = S3Model()
        self.cycles = 0

    # -- drive ---------------------------------------------------------------
    def drive(self, inputs: dict) -> None:
        self.pipe_valid.Set(1 if inputs["pipeIn"]["valid"] else 0)
        for name, signal in self.pipe_bits.items():
            signal.Set(int(inputs["pipeIn"]["bits"].get(name, 0))
                       & ((1 << PIPEIN_FIELDS[name]) - 1))
        self.redirect_valid.Set(1 if inputs["redirect"]["valid"] else 0)
        for name, signal in self.redirect_bits.items():
            signal.Set(int(inputs["redirect"]["bits"].get(name, 0))
                       & ((1 << REDIRECT_FIELDS[name]) - 1))
        self.tail_valid.Set(1 if inputs["unalignTailValid"] else 0)
        self.concat_valid.Set(1 if inputs["concat"]["valid"] else 0)
        for name, signal in self.concat_bits.items():
            signal.Set(int(inputs["concat"]["bits"].get(name, 0))
                       & ((1 << CONCAT_FIELDS[name]) - 1))
        self.fast_ready.Set(1 if inputs["fastReplayReady"] else 0)
        self.rar_valid.Set(1 if inputs["rarResp"]["valid"] else 0)
        self.rar_nuke.Set(1 if inputs["rarResp"]["nuke"] else 0)
        self.ldld.Set(1 if inputs["ldldCheck"] else 0)

    def reset(self, cycles: int = 3) -> None:
        idle = blank_inputs()
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.drive(idle)
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model.reset()
        self.cycles = 0

    # -- one checked cycle ---------------------------------------------------
    def cycle(self, inputs: dict, context: str = "cycle") -> dict:
        want = self.model.cycle(inputs)
        self.drive(inputs)
        self.dut.Step(1)
        self.cycles += 1
        checks = {
            "pipeOut.valid": (int(self.out_valid.value), want["pipeOut_valid"]),
            "vldWakeup": (int(self.vld_wakeup.value), want["vld_wakeup"]),
            "pdest": (int(self.pdest.value), want["pdest"]),
            "ldout.valid": (int(self.ldout_valid.value), want["ldout_valid"]),
            "vldout.valid": (int(self.vldout_valid.value), want["vldout_valid"]),
            "vldout.pdest": (int(self.vldout_pdest.value), want["vldout_pdest"]),
            "intRf.valid": (int(self.int_rf_valid.value), want["int_rf_valid"]),
            "intRf.pdest": (int(self.int_rf_pdest.value),
                            want["detail"]["pipe"]["uop_pdest"]),
            "fpRf.valid": (int(self.fp_rf_valid.value), want["fp_rf_valid"]),
            "fpRf.pdest": (int(self.fp_rf_pdest.value),
                           want["detail"]["pipe"]["uop_pdest"]),
            "vecRf.valid": (int(self.vec_rf_valid.value), want["vld_wakeup"]),
            "v0Rf.valid": (int(self.v0_rf_valid.value), want["v0_rf_valid"]),
            "lqWrite.valid": (int(self.lq_write_valid.value),
                              want["lq_write_valid"]),
            "fastReplay.valid": (int(self.fast_valid.value),
                                 want["fast_replay_valid"]),
            "revokeLastCycle": (int(self.revoke_last.value),
                                want["revoke_last"]),
            "revokeLastLastCycle": (int(self.revoke_last_last.value),
                                    want["revoke_last_last"]),
            "rollback.valid": (int(self.rollback_valid.value),
                               want["rollback_valid"]),
            "exceptionInfo.valid": (int(self.exception_info_valid.value),
                                    want["exception_info_valid"]),
            "cancel": (int(self.cancel.value), want["cancel_out"]),
        }
        for name, signal in self.ldout.items():
            checks[f"ldout.{name}"] = (int(signal.value), want["ldout"][name])
        for name, signal in self.vldout.items():
            checks[f"vldout.{name}"] = (int(signal.value), want["vldout"][name])
        for name, signal in self.lq.items():
            checks[f"lq.{name}"] = (int(signal.value), want["lq"][name])
        for name, signal in self.fast.items():
            checks[f"fast.{name}"] = (int(signal.value), want["fast"][name])
        for name, signal in self.rollback.items():
            checks[f"rollback.{name}"] = (int(signal.value), want["rollback"][name])
        for name, signal in self.exception_info.items():
            checks[f"excinfo.{name}"] = (int(signal.value), want["excinfo"][name])
        for name, (got, exp) in checks.items():
            if got != exp:
                raise AssertionError(
                    f"{context}: {name} {got:#x} != {exp:#x} "
                    f"(pipe_valid={inputs['pipeIn']['valid']} "
                    f"kill={want['detail']['kill']} "
                    f"cancel={want['detail']['cancel']} "
                    f"s3exc={want['detail']['s3_exception']} "
                    f"we={want['detail']['should_wakeup']})")
        if want["pipeOut_valid"]:
            for name in PIPEOUT_FIELDS:
                got = int(self.out[name].value)
                exp = want["pipeOut_bits"][name]
                if got != exp:
                    raise AssertionError(
                        f"{context}: pipeOut.{name} {got:#x} != {exp:#x}")
        elif self.coverage is not None and self.model.pipe_out_bits is not None:
            for name in PIPEOUT_FIELDS:
                got = int(self.out[name].value)
                exp = self.model.pipe_out_bits[name]
                if got != exp:
                    raise AssertionError(
                        f"{context}: pipeOut.{name} not held on an empty beat: "
                        f"{got:#x} != {exp:#x}")
        if self.coverage is not None:
            self.coverage.observe(want=want, inputs=inputs)
        return want


# ------------------------------------------------------------------ stimulus
def blank_bits(fields) -> dict:
    return {name: 0 for name in fields}


def blank_inputs() -> dict:
    return {
        "pipeIn": {"valid": 0, "bits": blank_bits(PIPEIN_FIELDS)},
        "redirect": {"valid": 0, "bits": blank_bits(REDIRECT_FIELDS)},
        "unalignTailValid": 0,
        "concat": {"valid": 0, "bits": blank_bits(CONCAT_FIELDS)},
        "fastReplayReady": 1,
        "rarResp": {"valid": 0, "nuke": 0},
        "ldldCheck": 0,
    }


def random_inputs(rng: random.Random, pipe_valid=None) -> dict:
    inputs = blank_inputs()
    inputs["pipeIn"]["valid"] = (1 if rng.random() < 0.7 else 0)\
        if pipe_valid is None else pipe_valid
    inputs["pipeIn"]["bits"] = {name: rng.randrange(1 << width)
                                for name, width in PIPEIN_FIELDS.items()}
    inputs["redirect"]["valid"] = 1 if rng.random() < 0.15 else 0
    inputs["redirect"]["bits"] = {name: rng.randrange(1 << width)
                                  for name, width in REDIRECT_FIELDS.items()}
    inputs["unalignTailValid"] = 1 if rng.random() < 0.25 else 0
    inputs["concat"]["valid"] = 1 if rng.random() < 0.35 else 0
    inputs["concat"]["bits"] = {name: rng.randrange(1 << width)
                                for name, width in CONCAT_FIELDS.items()}
    inputs["fastReplayReady"] = 1 if rng.random() < 0.7 else 0
    inputs["rarResp"]["valid"] = 1 if rng.random() < 0.2 else 0
    inputs["rarResp"]["nuke"] = 1 if rng.random() < 0.4 else 0
    inputs["ldldCheck"] = 1 if rng.random() < 0.6 else 0
    return inputs
