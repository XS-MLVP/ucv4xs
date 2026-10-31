"""Environment and independent reference for LoadUnitS2.

S2 decides how a translated load is satisfied and whether it must replay. The
reference is organised around the micro-architectural predicates rather than
the RTL gate tree:

* **forward coverage / fullForward**: the SQ/Sbuffer/uncache forward masks (and
  the MSHR mask, and the TLD response) are compared against the load's byte
  mask. If nothing is left uncovered and no SQ data is invalid, the load needs
  no DCache access.
* **uncache classification**: ``pbmt`` (NC=1, MMIO=2) plus the PMP MMIO bit,
  only on a TLB hit.
* **exception update**: AF/AM/HWE are recomputed from the base exception bits,
  PMP, NC/MMIO misalignment and the denied/corrupt forward responses.
* **replay causes** (C_0..C_11): uncache replay, forward invalid, store-set
  address invalid, TLB miss (bit 2 of tlbAccessResult), SQ data invalid, MSHR
  nack, DCache miss, bank conflict, RAR/RAW nack and store-load nuke.
* **fast replay** eligibility (no prefetch/unalign/tail/TLB-miss/special) and
  the four ways the cause set allows a fast replay.
* **kill**: only the current redirect and hardware prefetch suppress the output;
  trigger breakpoints and exceptions do NOT suppress it (they write back).

Contract: docs/contracts/load-s2.md
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
    "align": 1,
    "unalignHead": 1,
    "tlbAccessResult": 3,
    "tlbException_vaNeedExt": 1,
    "tlbException_isHyper": 1,
    "pbmt": 2,
    "gpaddr": 64,
    "isForVSnonLeafPTE": 1,
    "replayQueueIdx": 7,
    "cause_11": 1,
    "specialModeRequest": 1,
    "fastReplayNukeFirst": 1,
    "uncacheReplay": 1,
    "ncReplay": 1,
    "shouldFastReplay": 1,
}
PIPEOUT_FIELDS = {
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
DCRESP_FIELDS = {
    "miss": 1,
    "mshr_id": 4,
    "meta_prefetch": 3,
    "handled": 1,
}
SQ_FIELDS = {
    "forwardMask_0": 1,
    "forwardMask_1": 1,
    "forwardMask_2": 1,
    "forwardMask_3": 1,
    "forwardMask_4": 1,
    "forwardMask_5": 1,
    "forwardMask_6": 1,
    "forwardMask_7": 1,
    "forwardMask_8": 1,
    "forwardMask_9": 1,
    "forwardMask_10": 1,
    "forwardMask_11": 1,
    "forwardMask_12": 1,
    "forwardMask_13": 1,
    "forwardMask_14": 1,
    "forwardMask_15": 1,
    "forwardInvalid": 1,
    "matchInvalid": 1,
    "addrInvalid_valid": 1,
    "addrInvalid_bits_first_flag": 1,
    "addrInvalid_bits_second_flag": 1,
    "addrInvalid_bits_value": 6,
    "dataInvalid_valid": 1,
    "dataInvalid_bits_first_flag": 1,
    "dataInvalid_bits_second_flag": 1,
    "dataInvalid_bits_value": 6,
}
SB_FIELDS = {
    "forwardMask_0": 1,
    "forwardMask_1": 1,
    "forwardMask_2": 1,
    "forwardMask_3": 1,
    "forwardMask_4": 1,
    "forwardMask_5": 1,
    "forwardMask_6": 1,
    "forwardMask_7": 1,
    "forwardMask_8": 1,
    "forwardMask_9": 1,
    "forwardMask_10": 1,
    "forwardMask_11": 1,
    "forwardMask_12": 1,
    "forwardMask_13": 1,
    "forwardMask_14": 1,
    "forwardMask_15": 1,
    "matchInvalid": 1,
}
UNC_FIELDS = {
    "forwardMask_0": 1,
    "forwardMask_1": 1,
    "forwardMask_2": 1,
    "forwardMask_3": 1,
    "forwardMask_4": 1,
    "forwardMask_5": 1,
    "forwardMask_6": 1,
    "forwardMask_7": 1,
    "forwardMask_8": 1,
    "forwardMask_9": 1,
    "forwardMask_10": 1,
    "forwardMask_11": 1,
    "forwardMask_12": 1,
    "forwardMask_13": 1,
    "forwardMask_14": 1,
    "forwardMask_15": 1,
    "matchInvalid": 1,
}
MSHR_FIELDS = {
    "forwardMask_0": 1,
    "forwardMask_1": 1,
    "forwardMask_2": 1,
    "forwardMask_3": 1,
    "forwardMask_4": 1,
    "forwardMask_5": 1,
    "forwardMask_6": 1,
    "forwardMask_7": 1,
    "forwardMask_8": 1,
    "forwardMask_9": 1,
    "forwardMask_10": 1,
    "forwardMask_11": 1,
    "forwardMask_12": 1,
    "forwardMask_13": 1,
    "forwardMask_14": 1,
    "forwardMask_15": 1,
    "denied": 1,
    "corrupt": 1,
}
TLD_FIELDS = {
    "denied": 1,
    "corrupt": 1,
}
BYPASS_FIELDS = {
    "nderr": 1,
    "derr": 1,
}
TLBHINT_FIELDS = {
    "id": 4,
    "full": 1,
}
RAR_FIELDS = {
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "paddr": 48,
    "lqIdx_flag": 1,
    "lqIdx_value": 7,
    "dataValid": 1,
    "nc": 1,
}
RAW_FIELDS = {
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "paddr": 48,
    "sqIdx_first_flag": 1,
    "sqIdx_second_flag": 1,
    "sqIdx_value": 6,
    "dataValid": 1,
    "mask": 16,
    "isRVC": 1,
    "ftqPtr_flag": 1,
    "ftqPtr_value": 6,
    "ftqOffset": 5,
    "debugInfo_runahead_checkpoint_id": 64,
}
PREFETCH_TRAIN_FIELDS = {
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "vaddr": 50,
    "paddr": 48,
    "miss": 1,
    "metaSource": 3,
    "isFirstIssue": 1,
    "isHwPrefetch": 1,
}

NUKE_FIELDS = {"robIdx_flag": 1, "robIdx_value": 8, "robIdx_isFormer": 1,
               "sqIdx_first_flag": 1, "sqIdx_second_flag": 1, "sqIdx_value": 6,
               "paddr": 48, "mask": 16, "matchType": 2}
REDIRECT_FIELDS = {"level": 1, "robIdx_flag": 1, "robIdx_value": 8,
                   "robIdx_isFormer": 1}
STD_DATA_FIELDS = {"valid": 1, "first_flag": 1, "second_flag": 1, "value": 6}

ALL_FIELDS = {
    "pipeIn": PIPEIN_FIELDS,
    "dcacheResp": DCRESP_FIELDS,
    "sq": SQ_FIELDS,
    "sb": SB_FIELDS,
    "unc": UNC_FIELDS,
    "mshr": MSHR_FIELDS,
    "tld": TLD_FIELDS,
    "bypass": BYPASS_FIELDS,
    "tlbHint": TLBHINT_FIELDS,
    "nuke": NUKE_FIELDS,
    "redirect": REDIRECT_FIELDS,
}


def ring_greater(flag_a: int, value_a: int, flag_b: int, value_b: int) -> bool:
    return bool((flag_a ^ flag_b ^ (1 if value_a > value_b else 0)) & 1)


def mask_of(bits: dict) -> int:
    value = 0
    for index in range(16):
        value |= (bits.get(f"forwardMask_{index}", 0) & 1) << index
    return value


def sqptr(first: int, second: int, value: int) -> int:
    return ((first & 1) << 7) | ((second & 1) << 6) | (value & 0x3F)


def norm(fields: dict, values: dict) -> dict:
    return dict({name: 0 for name in fields}, **(values or {}))


def redirect_kill(pipe: dict, red: dict) -> bool:
    same = (pipe["uop_robIdx_flag"] == red["robIdx_flag"]
            and pipe["uop_robIdx_value"] == red["robIdx_value"])
    level_same = bool(red["level"]) and same and (
        pipe["uop_robIdx_isFormer"] == red["robIdx_isFormer"])
    newer = ring_greater(pipe["uop_robIdx_flag"], pipe["uop_robIdx_value"],
                         red["robIdx_flag"], red["robIdx_value"])
    former = same and not pipe["uop_robIdx_isFormer"] and bool(red["robIdx_isFormer"])
    return bool(level_same or newer or former)


class S2Model:
    def __init__(self) -> None:
        self.pipe_out_valid = 0
        self.pipe_out_bits: dict | None = None
        self.perf = [[0, 0] for _ in range(4)]

    def reset(self) -> None:
        self.pipe_out_valid = 0
        self.pipe_out_bits = None
        self.perf = [[0, 0] for _ in range(4)]

    def compute(self, inputs: dict) -> dict:
        pipe = norm(PIPEIN_FIELDS, inputs["pipeIn"]["bits"])
        pipe_valid = 1 if inputs["pipeIn"]["valid"] else 0
        dcache = norm(DCRESP_FIELDS, inputs["dcacheResp"]["bits"])
        sq = norm(SQ_FIELDS, inputs["sq"]["bits"])
        sb = norm(SB_FIELDS, inputs["sb"]["bits"])
        unc = norm(UNC_FIELDS, inputs["unc"]["bits"])
        mshr = norm(MSHR_FIELDS, inputs["mshr"]["bits"])
        tld = norm(TLD_FIELDS, inputs["tld"]["bits"])
        bypass = norm(BYPASS_FIELDS, inputs["bypass"]["bits"])

        # ------------------------------------------------------- classifications
        is_mmio_replay = int(bool(pipe["uncacheReplay"]) and not pipe["ncReplay"])
        is_nc_replay = int(bool(pipe["uncacheReplay"]) and bool(pipe["ncReplay"]))
        is_hw_prefetch = int(bool((pipe["accessType_instrType"] >> 2) & 1)
                             and not ((pipe["accessType_pftType"] >> 1) & 1))
        is_sw_prefetch = int(bool((pipe["accessType_instrType"] >> 2) & 1)
                             and bool((pipe["accessType_pftType"] >> 1) & 1))
        kill = int(bool(inputs["redirect"]["valid"])
                   and redirect_kill(pipe, inputs["redirect"]["bits"]))

        pmp_unaccessable = int(bool(inputs["pmp"]["ld"])
                               and bool((pipe["tlbAccessResult"] >> 1) & 1))
        hit = (pipe["tlbAccessResult"] >> 1) & 1
        mmio_base = int(bool(hit) and not (
            pipe["uop_exceptionVec_5"] or pipe["uop_exceptionVec_13"]
            or pipe["uop_exceptionVec_21"]))
        is_nc = int(bool(mmio_base) and pipe["pbmt"] == 1)
        is_mmio = int(bool(mmio_base) and (
            pipe["pbmt"] == 2 or (pipe["pbmt"] == 0 and inputs["pmp"]["mmio"])))
        is_uncache = is_nc or is_mmio

        sq_data_invalid = int(bool(inputs["sq"]["valid"]) and sq["dataInvalid_valid"])
        forward_invalid = int(bool(inputs["sq"]["valid"]) and sq["forwardInvalid"])
        mshr_denied = int(bool(inputs["mshr"]["valid"]) and mshr["denied"])
        tld_denied = int(bool(inputs["tld"]["valid"]) and tld["denied"])
        mshr_corrupt = int(bool(inputs["mshr"]["valid"]) and mshr["corrupt"]
                           and not mshr["denied"])
        tld_corrupt = int(bool(inputs["tld"]["valid"]) and tld["corrupt"]
                          and not tld["denied"])
        bypass_denied = int(bool(inputs["bypass"]["valid"]) and bypass["nderr"])
        bypass_corrupt = int(bool(inputs["bypass"]["valid"]) and bypass["derr"])

        af = int(bool(pipe["uop_exceptionVec_5"]) or bool(pmp_unaccessable)
                 or bool((pipe["accessType_instrType"] >> 1) & 1 and is_uncache)
                 or (not pipe["align"] and bool(is_mmio))
                 or bool(mshr_denied) or bool(tld_denied)
                 or bool(bypass_denied))
        am = int(not pipe["align"] and bool(pipe["accessType_instrType"] & 1)
                 and bool(is_nc) and not pmp_unaccessable)
        hwe = int(bool(pipe["uop_exceptionVec_19"]) or bool(mshr_corrupt)
                  or bool(tld_corrupt) or bool(bypass_corrupt))
        trigger_debug = int(pipe["uop_trigger"] == 1)
        gen = [trigger_debug, pipe["uop_exceptionVec_23"],
               pipe["uop_exceptionVec_21"], hwe, pipe["uop_exceptionVec_15"],
               pipe["uop_exceptionVec_13"], pipe["uop_exceptionVec_7"],
               pipe["uop_exceptionVec_6"], af, am, pipe["uop_exceptionVec_3"]]
        gen_or = int(any(gen))

        # ------------------------------------------------------------- forwarding
        mask = pipe["mask"]
        sq_mask, sb_mask = mask_of(sq), mask_of(sb)
        unc_mask, mshr_mask = mask_of(unc), mask_of(mshr)
        # ``(~mask_union & load_mask) == 0`` == every byte of the load is
        # covered by the forward mask union.
        clause_sq_sb_unc = (((~(sq_mask | sb_mask | unc_mask)) & mask) == 0
                            and not sq_data_invalid)
        clause_mshr = (((~mshr_mask) & mask) == 0)
        tld_valid = 1 if inputs["tld"]["valid"] else 0
        full_forward = int(bool(clause_sq_sb_unc) or bool(clause_mshr)
                           or bool(tld_valid))
        need_dcache = int(not full_forward and not is_uncache
                          and not pipe["uncacheReplay"])

        # ------------------------------------------------------------------ nuke
        def nuke_match(req: dict) -> int:
            if not req["valid"]:
                return 0
            bits = req["bits"]
            if bits["matchType"] == 2:
                addr_match = (bits["paddr"] >> 6) == (pipe["paddr"] >> 6)
            else:
                addr_match = (bits["paddr"] >> 4) == (pipe["paddr"] >> 4)
            order = (ring_greater(pipe["uop_robIdx_flag"], pipe["uop_robIdx_value"],
                                  bits["robIdx_flag"], bits["robIdx_value"])
                     or (pipe["uop_robIdx_flag"] == bits["robIdx_flag"]
                         and pipe["uop_robIdx_value"] == bits["robIdx_value"]
                         and not pipe["uop_robIdx_isFormer"]
                         and bool(bits["robIdx_isFormer"])))
            overlap = bool(bits["mask"] & mask)
            return int(addr_match and order and overlap)

        nuke_hit = int(bool(nuke_match(inputs["nuke"][0]))
                       or bool(nuke_match(inputs["nuke"][1])))
        nuke = int((bool(nuke_hit) and not ((pipe["tlbAccessResult"] >> 2) & 1))
                   or bool(pipe["cause_11"]))

        trouble_maker = int(not ((pipe["accessType_instrType"] >> 2) & 1)
                            and not (gen_or or is_mmio_replay))

        raw_valid = int(not is_mmio_replay
                        and not ((pipe["accessType_instrType"] >> 2) & 1)
                        and not pipe["cause_11"] and bool(pipe_valid))
        rar_nack = int(bool(raw_valid) and not inputs["rarReady"])
        raw_nack = int(bool(raw_valid) and not inputs["rawReady"])

        cause = {}
        cause[0] = int(bool(trouble_maker) and (
            (bool(is_nc_replay) and (sq_data_invalid or rar_nack or raw_nack
                                     or nuke or forward_invalid))
            if pipe["uncacheReplay"] else bool(is_uncache)))
        cause[1] = int(bool(trouble_maker) and bool(forward_invalid))
        cause[2] = int(bool(trouble_maker) and bool(pipe["uop_storeSetHit"])
                       and bool(inputs["sq"]["valid"]) and bool(sq["addrInvalid_valid"]))
        cause[3] = int((bool(trouble_maker) and bool((pipe["tlbAccessResult"] >> 2) & 1))
                       or bool(pipe["specialModeRequest"]))
        cause[4] = int(bool(trouble_maker) and bool(sq_data_invalid))
        cause[5] = int(bool(trouble_maker) and bool(need_dcache)
                       and bool(inputs["dcacheMSHRNack"]))
        cause[6] = int(bool(trouble_maker) and bool(need_dcache)
                       and bool(dcache["miss"]))
        cause[8] = int(bool(trouble_maker) and (
            (bool(need_dcache) and bool(inputs["dcacheBankConflict"]))
            or (bool(pipe["unalignHead"]) and bool(pipe["shouldFastReplay"]))))
        cause[9] = int(bool(trouble_maker) and bool(rar_nack))
        cause[10] = int(bool(trouble_maker) and bool(raw_nack))
        cause[11] = int(bool(trouble_maker) and bool(nuke))
        cause_or = int(any(cause.values()))
        low7 = [cause[i] for i in (0, 1, 2, 3, 4, 5, 6)]

        fast_bank_conflict = int(bool(cause[8]) and not any(low7))
        fast_eligible = int(not ((pipe["entrance"] >> 2) & 1)
                            and not (pipe["unalignHead"] or (pipe["entrance"] & 1))
                            and not ((pipe["tlbAccessResult"] >> 2) & 1)
                            and not pipe["specialModeRequest"])

        wait_sq = sqptr(pipe["uop_waitSqIdx_first_flag"],
                        pipe["uop_waitSqIdx_second_flag"],
                        pipe["uop_waitSqIdx_value"])
        nuke_first = 0
        if pipe["uop_storeSetHit"]:
            for req in inputs["nuke"]:
                if req["valid"] and sqptr(req["bits"]["sqIdx_first_flag"],
                                          req["bits"]["sqIdx_second_flag"],
                                          req["bits"]["sqIdx_value"]) == wait_sq:
                    nuke_first = 1
        nuke_first_or_flag = int(bool(nuke_first) or bool(pipe["fastReplayNukeFirst"]))

        sqidx_data_invalid = sqptr(sq["dataInvalid_bits_first_flag"],
                                   sq["dataInvalid_bits_second_flag"],
                                   sq["dataInvalid_bits_value"])
        std_match = 0
        for group in ("current", "previous"):
            for index in range(2):
                entry = inputs["stdData"][group][index]
                if entry["valid"] and sqptr(entry["bits"]["first_flag"],
                                            entry["bits"]["second_flag"],
                                            entry["bits"]["value"]) == sqidx_data_invalid:
                    std_match = 1

        fast_paths = (
            int(bool(cause[5]) and not any(cause[i] for i in (0, 1, 2, 3, 4)))
            or fast_bank_conflict
            or int(bool(cause[11]) and not (
                cause[0] or cause[1]
                or (cause[2] and not nuke_first_or_flag)
                or cause[3] or cause[4] or cause[5] or cause[6] or cause[8]))
            or int(bool(cause[4]) and not any(cause[i] for i in (0, 1, 2, 3))
                   and bool(std_match)))
        should_fast_replay = int(
            bool(pipe["shouldFastReplay"])
            or (bool(fast_eligible) and bool(fast_paths) and not gen_or))

        rr_bank_conflict_fast_replay = int(
            not kill and bool(fast_eligible) and bool(fast_bank_conflict)
            and bool(inputs["dcacheRRBankConflict"]))

        should_wakeup = int(not (cause_or or pipe["shouldFastReplay"])
                            and not is_uncache and not gen_or and not is_sw_prefetch)
        should_writeback = int(
            bool(should_wakeup) or bool(trigger_debug)
            or bool(pipe["uop_exceptionVec_23"]) or bool(pipe["uop_exceptionVec_21"])
            or bool(hwe) or bool(pipe["uop_exceptionVec_15"])
            or bool(pipe["uop_exceptionVec_13"]) or bool(pipe["uop_exceptionVec_7"])
            or bool(pipe["uop_exceptionVec_6"]) or bool(af) or bool(am)
            or bool(pipe["uop_exceptionVec_3"])
            or bool(inputs["sq"]["valid"] and sq["matchInvalid"])
            or bool(inputs["sb"]["valid"] and sb["matchInvalid"])
            or bool(inputs["unc"]["valid"] and unc["matchInvalid"])
            or bool(is_sw_prefetch))
        match_invalid = int(
            bool(inputs["sq"]["valid"] and sq["matchInvalid"])
            or bool(inputs["sb"]["valid"] and sb["matchInvalid"])
            or bool(inputs["unc"]["valid"] and unc["matchInvalid"]))

        nuke_query_data_valid = int(bool(full_forward) or bool(is_nc_replay)
                                    or (bool(need_dcache) and not dcache["miss"]
                                        and not inputs["dcacheBankConflict"]))

        # ------------------------------------------------------- registered beat
        out = {name: pipe.get(name, 0) for name in PIPEOUT_FIELDS}
        out.update({
            "uop_exceptionVec_19": hwe,
            "uop_exceptionVec_5": af,
            "uop_exceptionVec_4": am,
            "pmp_mmio": int(bool(inputs["pmp"]["mmio"])),
            "nc": is_nc,
            "mmio": is_mmio,
            "mshrId": dcache["mshr_id"],
            "cause_0": cause[0], "cause_1": cause[1], "cause_2": cause[2],
            "cause_3": cause[3], "cause_4": cause[4], "cause_5": cause[5],
            "cause_6": cause[6], "cause_8": cause[8], "cause_9": cause[9],
            "cause_10": cause[10], "cause_11": cause[11],
            "handledByMSHR": dcache["handled"],
            "dataInvalidSqIdx_first_flag": sq["dataInvalid_bits_first_flag"],
            "dataInvalidSqIdx_second_flag": sq["dataInvalid_bits_second_flag"],
            "dataInvalidSqIdx_value": sq["dataInvalid_bits_value"],
            "addrInvalidSqIdx_first_flag": sq["addrInvalid_bits_first_flag"],
            "addrInvalidSqIdx_second_flag": sq["addrInvalid_bits_second_flag"],
            "addrInvalidSqIdx_value": sq["addrInvalid_bits_value"],
            "tlbId": inputs["tlbHint"]["id"],
            "tlbFull": inputs["tlbHint"]["full"],
            "shouldFastReplay": should_fast_replay,
            "causeOrR": cause_or,
            "rrBankConflictFastReplay": rr_bank_conflict_fast_replay,
            "rrBankConflictFastReplayGrant": int(bool(inputs["rrGrant"])),
            "matchInvalid": int(bool(match_invalid) and bool(trouble_maker)),
            "shouldWakeup": should_wakeup,
            "shouldWriteback": should_writeback,
        })
        prefetch_train_valid = int(
            bool(pipe_valid) and bool((pipe["tlbAccessResult"] >> 1) & 1)
            and not gen_or and not is_uncache and not pipe["uncacheReplay"]
            and bool(pipe["entrance"] & 0x60)
            and not ((pipe["accessType_instrType"] >> 1) & 1))
        rar = {name: 0 for name in RAR_FIELDS}
        rar.update({
            "robIdx_flag": pipe["uop_robIdx_flag"],
            "robIdx_value": pipe["uop_robIdx_value"],
            "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
            "paddr": pipe["paddr"],
            "lqIdx_flag": pipe["uop_lqIdx_flag"],
            "lqIdx_value": pipe["uop_lqIdx_value"],
            "dataValid": nuke_query_data_valid,
            "nc": is_nc_replay,
        })
        raw = {name: 0 for name in RAW_FIELDS}
        raw.update({
            "robIdx_flag": pipe["uop_robIdx_flag"],
            "robIdx_value": pipe["uop_robIdx_value"],
            "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
            "paddr": pipe["paddr"],
            "sqIdx_first_flag": pipe["uop_sqIdx_first_flag"],
            "sqIdx_second_flag": pipe["uop_sqIdx_second_flag"],
            "sqIdx_value": pipe["uop_sqIdx_value"],
            "dataValid": nuke_query_data_valid,
            "mask": pipe["mask"],
            "isRVC": pipe["uop_isRVC"],
            "ftqPtr_flag": pipe["uop_ftqPtr_flag"],
            "ftqPtr_value": pipe["uop_ftqPtr_value"],
            "ftqOffset": pipe["uop_ftqOffset"],
            "debugInfo_runahead_checkpoint_id":
                pipe["uop_perfDebugInfo_runahead_checkpoint_id"],
        })
        train = {name: 0 for name in PREFETCH_TRAIN_FIELDS}
        train.update({
            "robIdx_flag": pipe["uop_robIdx_flag"],
            "robIdx_value": pipe["uop_robIdx_value"],
            "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
            "vaddr": pipe["vaddr"], "paddr": pipe["paddr"],
            "miss": dcache["miss"], "metaSource": dcache["meta_prefetch"],
            "isFirstIssue": int(bool(pipe["entrance"] & 0x60)),
            "isHwPrefetch": int(bool((pipe["accessType_instrType"] >> 2) & 1)
                                and not ((pipe["accessType_pftType"] >> 1) & 1)),
        })
        return {
            "rar_valid": raw_valid, "raw_valid": raw_valid,
            "rar": rar, "raw": raw, "train": train,
            "prefetchTrain_valid": prefetch_train_valid,
            "rrCandidate": int(bool(pipe_valid)
                               and bool(rr_bank_conflict_fast_replay)),
            "next_valid": int(not (kill or is_hw_prefetch) and bool(pipe_valid)),
            "next_bits": out if pipe_valid else None,
            "unalignTailValid": int(bool(pipe_valid) and bool(pipe["entrance"] & 1)),
            "pipe": pipe, "pipe_valid": pipe_valid, "kill": kill,
            "is_hw_prefetch": is_hw_prefetch, "is_sw_prefetch": is_sw_prefetch,
            "is_nc": is_nc, "is_mmio": is_mmio, "is_uncache": is_uncache,
            "is_mmio_replay": is_mmio_replay, "is_nc_replay": is_nc_replay,
            "gen_or": gen_or, "gen": gen, "af": af, "am": am, "hwe": hwe,
            "full_forward": full_forward, "need_dcache": need_dcache,
            "nuke": nuke, "trouble_maker": trouble_maker, "cause": cause,
            "cause_or": cause_or, "should_fast_replay": should_fast_replay,
            "fast_eligible": fast_eligible,
            "fast_bank_conflict": fast_bank_conflict,
            "rr_candidate": int(bool(pipe_valid)
                                and bool(rr_bank_conflict_fast_replay)),
            "raw_valid": raw_valid, "rar_nack": rar_nack, "raw_nack": raw_nack,
            "nuke_query_data_valid": nuke_query_data_valid,
            "should_wakeup": should_wakeup, "should_writeback": should_writeback,
            "match_invalid": match_invalid,
            "dcache_kill": int(
                bool(kill) or bool(trigger_debug)
                or bool(pipe["uop_exceptionVec_23"]) or bool(pipe["uop_exceptionVec_21"])
                or bool(hwe) or bool(pipe["uop_exceptionVec_15"])
                or bool(pipe["uop_exceptionVec_13"]) or bool(pipe["uop_exceptionVec_7"])
                or bool(pipe["uop_exceptionVec_6"]) or bool(af) or bool(am)
                or bool(pipe["uop_exceptionVec_3"]) or bool(is_uncache)
                or bool(pipe["uncacheReplay"]) or bool(pipe["specialModeRequest"])),
            "out": out,
        }

    def advance(self, result: dict) -> None:
        pipe_valid = result["pipe_valid"]
        if pipe_valid:
            self.pipe_out_bits = result["out"]
        self.pipe_out_valid = result["next_valid"]
        self.perf[0] = [pipe_valid, self.perf[0][0]]
        self.perf[1] = [int(bool(pipe_valid) and not result["kill"]
                            and bool(result["cause"][6])), self.perf[1][0]]
        self.perf[2] = [int(bool(pipe_valid) and bool(result["is_hw_prefetch"])),
                        self.perf[2][0]]
        self.perf[3] = [int(bool(pipe_valid) and bool(result["is_hw_prefetch"])
                            and not result["kill"] and bool(result["cause"][6])),
                        self.perf[3][0]]

    def cycle(self, inputs: dict) -> dict:
        result = self.compute(inputs)
        self.advance(result)
        pipe_valid = result["pipe_valid"]
        pipe = result["pipe"]
        dcache = norm(DCRESP_FIELDS, inputs["dcacheResp"]["bits"])
        prefetch_train_valid = result["prefetchTrain_valid"]
        req = {name: pipe.get(name, 0) for name in PIPEIN_FIELDS}
        rar = {name: 0 for name in RAR_FIELDS}
        raw = {name: 0 for name in RAW_FIELDS}
        rar.update({
            "robIdx_flag": pipe["uop_robIdx_flag"],
            "robIdx_value": pipe["uop_robIdx_value"],
            "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
            "paddr": pipe["paddr"],
            "lqIdx_flag": pipe["uop_lqIdx_flag"],
            "lqIdx_value": pipe["uop_lqIdx_value"],
            "dataValid": result["nuke_query_data_valid"],
            "nc": result["is_nc_replay"],
        })
        raw.update({
            "robIdx_flag": pipe["uop_robIdx_flag"],
            "robIdx_value": pipe["uop_robIdx_value"],
            "robIdx_isFormer": pipe["uop_robIdx_isFormer"],
            "paddr": pipe["paddr"],
            "sqIdx_first_flag": pipe["uop_sqIdx_first_flag"],
            "sqIdx_second_flag": pipe["uop_sqIdx_second_flag"],
            "sqIdx_value": pipe["uop_sqIdx_value"],
            "dataValid": result["nuke_query_data_valid"],
            "mask": pipe["mask"],
            "isRVC": pipe["uop_isRVC"],
            "ftqPtr_flag": pipe["uop_ftqPtr_flag"],
            "ftqPtr_value": pipe["uop_ftqPtr_value"],
            "ftqOffset": pipe["uop_ftqOffset"],
            "debugInfo_runahead_checkpoint_id":
                pipe["uop_perfDebugInfo_runahead_checkpoint_id"],
        })
        train = result["train"]
        return {
            "pipeOut_valid": self.pipe_out_valid,
            "pipeOut_bits": self.pipe_out_bits,
            "unalignTailValid": int(bool(pipe_valid) and bool(pipe["entrance"] & 1)),
            "dcacheKill": result["dcache_kill"],
            "rrCandidate": result["rr_candidate"],
            "rar_valid": result["raw_valid"], "rar": rar,
            "raw_valid": result["raw_valid"], "raw": raw,
            "prefetchTrain_valid": prefetch_train_valid, "train": train,
            "perf": [self.perf[i][1] for i in range(4)],
            "detail": result,
        }


class LoadS2Env:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.pipe_valid = dut.io_pipeIn_valid
        self.pipe_bits = {name: getattr(dut, f"io_pipeIn_bits_{name}")
                          for name in PIPEIN_FIELDS}
        self.redirect_valid = dut.io_redirect_valid
        self.redirect_bits = {name: getattr(dut, f"io_redirect_bits_{name}")
                              for name in REDIRECT_FIELDS}
        self.pmp_ld = dut.io_pmp_ld
        self.pmp_mmio = dut.io_pmp_mmio
        self.tlb_id = dut.io_tlbHint_id
        self.tlb_full = dut.io_tlbHint_full
        self.dcache_resp = {name: getattr(dut, f"io_dcacheResp_bits_{name}")
                            for name in DCRESP_FIELDS}
        self.dcache_bank = dut.io_dcacheBankConflict
        self.dcache_rr = dut.io_dcacheRRBankConflict
        self.dcache_nack = dut.io_dcacheMSHRNack
        self.rr_grant = dut.io_rrBankConflictFastReplayGrant
        self.resp = {}
        for key, fields in (("sq", SQ_FIELDS), ("sb", SB_FIELDS),
                            ("unc", UNC_FIELDS), ("mshr", MSHR_FIELDS),
                            ("tld", TLD_FIELDS), ("bypass", BYPASS_FIELDS)):
            port = {"sq": "io_sqForwardResp", "sb": "io_sbufferForwardResp",
                    "unc": "io_uncacheForwardResp",
                    "mshr": "io_mshrForwardResp", "tld": "io_tldForwardResp",
                    "bypass": "io_uncacheBypassResp"}[key]
            self.resp[key] = {
                "valid": getattr(dut, f"{port}_valid"),
                "bits": {name: getattr(dut, f"{port}_bits_{name}")
                         for name in fields},
            }
        self.std = {}
        for group in ("current", "previous"):
            self.std[group] = []
            for index in range(2):
                prefix = f"io_stdDataWrite_{group}_{index}"
                self.std[group].append({
                    "valid": getattr(dut, prefix + "_valid"),
                    "bits": {name: getattr(dut, prefix + "_bits_" + name)
                             for name in ("first_flag", "second_flag", "value")},
                })
        self.nuke_valid = [dut.io_staNukeQueryReq_0_valid,
                           dut.io_staNukeQueryReq_1_valid]
        self.nuke_bits = [{name: getattr(dut, f"io_staNukeQueryReq_{i}_bits_{name}")
                           for name in NUKE_FIELDS} for i in range(2)]
        self.rar_ready = dut.io_rarNukeQueryReq_ready
        self.raw_ready = dut.io_rawNukeQueryReq_ready

        self.out_valid = dut.io_pipeOut_valid
        self.out = {name: getattr(dut, f"io_pipeOut_bits_{name}")
                    for name in PIPEOUT_FIELDS}
        self.unalign_valid = dut.io_unalignTailValid
        self.dcache_kill = dut.io_dcacheKill
        self.rr_candidate = dut.io_rrBankConflictFastReplayCandidate
        self.rar = {"valid": dut.io_rarNukeQueryReq_valid,
                    "bits": {name: getattr(dut, f"io_rarNukeQueryReq_bits_{name}")
                             for name in RAR_FIELDS}}
        self.raw = {"valid": dut.io_rawNukeQueryReq_valid,
                    "bits": {name: getattr(dut, f"io_rawNukeQueryReq_bits_{name}")
                             for name in RAW_FIELDS}}
        self.train = {"valid": dut.io_prefetchTrain_valid,
                      "bits": {name: getattr(dut, f"io_prefetchTrain_bits_{name}")
                               for name in PREFETCH_TRAIN_FIELDS}}
        self.perf = [getattr(dut, f"io_perf_{i}_value") for i in range(4)]
        self.model = S2Model()
        self.cycles = 0

    # -- drive ---------------------------------------------------------------
    def drive(self, inputs: dict) -> None:
        self.pipe_valid.Set(1 if inputs["pipeIn"]["valid"] else 0)
        for name, signal in self.pipe_bits.items():
            signal.Set(int(inputs["pipeIn"]["bits"].get(name, 0))
                       & ((1 << PIPEIN_FIELDS[name]) - 1))
        self.redirect_valid.Set(1 if inputs["redirect"]["valid"] else 0)
        for name, signal in self.redirect_bits.items():
            signal.Set(int(inputs["redirect"]["bits"].get(name, 0)))
        self.pmp_ld.Set(1 if inputs["pmp"]["ld"] else 0)
        self.pmp_mmio.Set(1 if inputs["pmp"]["mmio"] else 0)
        self.tlb_id.Set(int(inputs["tlbHint"]["id"]) & 0xF)
        self.tlb_full.Set(1 if inputs["tlbHint"]["full"] else 0)
        for name, signal in self.dcache_resp.items():
            signal.Set(int(inputs["dcacheResp"]["bits"].get(name, 0))
                       & ((1 << DCRESP_FIELDS[name]) - 1))
        self.dcache_bank.Set(1 if inputs["dcacheBankConflict"] else 0)
        self.dcache_rr.Set(1 if inputs["dcacheRRBankConflict"] else 0)
        self.dcache_nack.Set(1 if inputs["dcacheMSHRNack"] else 0)
        self.rr_grant.Set(1 if inputs["rrGrant"] else 0)
        for key, fields in (("sq", SQ_FIELDS), ("sb", SB_FIELDS),
                            ("unc", UNC_FIELDS), ("mshr", MSHR_FIELDS),
                            ("tld", TLD_FIELDS), ("bypass", BYPASS_FIELDS)):
            self.resp[key]["valid"].Set(1 if inputs[key]["valid"] else 0)
            for name, signal in self.resp[key]["bits"].items():
                signal.Set(int(inputs[key]["bits"].get(name, 0))
                           & ((1 << fields[name]) - 1))
        for group in ("current", "previous"):
            for index in range(2):
                entry = inputs["stdData"][group][index]
                self.std[group][index]["valid"].Set(1 if entry["valid"] else 0)
                for name, signal in self.std[group][index]["bits"].items():
                    signal.Set(int(entry["bits"].get(name, 0))
                               & ((1 << STD_DATA_FIELDS[name]) - 1))
        for index in range(2):
            req = inputs["nuke"][index]
            self.nuke_valid[index].Set(1 if req["valid"] else 0)
            for name, signal in self.nuke_bits[index].items():
                signal.Set(int(req["bits"].get(name, 0))
                           & ((1 << NUKE_FIELDS[name]) - 1))
        self.rar_ready.Set(1 if inputs["rarReady"] else 0)
        self.raw_ready.Set(1 if inputs["rawReady"] else 0)

    def reset(self, cycles: int = 3) -> None:
        idle = blank_inputs()
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.drive(idle)
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model.reset()
        self.cycles = 0

    def perf_value(self, index: int) -> int:
        """Read one architectural performance event through the environment."""
        if index not in range(4):
            raise ValueError("performance index must be 0..3")
        return int(self.perf[index].value)

    # -- one checked cycle ---------------------------------------------------
    def cycle(self, inputs: dict, context: str = "cycle") -> dict:
        want = self.model.cycle(inputs)
        self.drive(inputs)
        self.dut.Step(1)
        self.cycles += 1
        checks = {
            "pipeOut.valid": (int(self.out_valid.value), want["pipeOut_valid"]),
            "unalignTailValid": (int(self.unalign_valid.value),
                                 want["unalignTailValid"]),
            "dcacheKill": (int(self.dcache_kill.value), want["dcacheKill"]),
            "rrCandidate": (int(self.rr_candidate.value), want["rrCandidate"]),
            "rar.valid": (int(self.rar["valid"].value), want["rar_valid"]),
            "raw.valid": (int(self.raw["valid"].value), want["raw_valid"]),
            "prefetchTrain.valid": (int(self.train["valid"].value),
                                    want["prefetchTrain_valid"]),
        }
        for index in range(4):
            checks[f"perf{index}"] = (int(self.perf[index].value),
                                      want["perf"][index])
        for name, signal in self.rar["bits"].items():
            checks[f"rar.{name}"] = (int(signal.value), want["rar"][name])
        for name, signal in self.raw["bits"].items():
            checks[f"raw.{name}"] = (int(signal.value), want["raw"][name])
        for name, signal in self.train["bits"].items():
            checks[f"train.{name}"] = (int(signal.value), want["train"][name])
        for name, (got, exp) in checks.items():
            if got != exp:
                raise AssertionError(
                    f"{context}: {name} {got:#x} != {exp:#x} "
                    f"(pipe_valid={inputs['pipeIn']['valid']} "
                    f"kill={want['detail']['kill']} "
                    f"causes={[i for i, v in want['detail']['cause'].items() if v]})")
        if want["pipeOut_valid"]:
            for name in PIPEOUT_FIELDS:
                got = int(self.out[name].value)
                exp = want["pipeOut_bits"][name]
                if got != exp:
                    raise AssertionError(
                        f"{context}: pipeOut.{name} {got:#x} != {exp:#x} "
                        f"(kill={want['detail']['kill']} "
                        f"hwpf={want['detail']['is_hw_prefetch']} "
                        f"causes={[i for i, v in want['detail']['cause'].items() if v]})")
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


def blank_std() -> dict:
    return {"current": [{"valid": 0, "bits": blank_bits(STD_DATA_FIELDS)}
                        for _ in range(2)],
            "previous": [{"valid": 0, "bits": blank_bits(STD_DATA_FIELDS)}
                         for _ in range(2)]}


def blank_inputs() -> dict:
    return {
        "pipeIn": {"valid": 0, "bits": blank_bits(PIPEIN_FIELDS)},
        "redirect": {"valid": 0, "bits": blank_bits(REDIRECT_FIELDS)},
        "pmp": {"ld": 0, "mmio": 0},
        "tlbHint": {"id": 0, "full": 0},
        "dcacheResp": {"bits": blank_bits(DCRESP_FIELDS)},
        "dcacheBankConflict": 0, "dcacheRRBankConflict": 0,
        "dcacheMSHRNack": 0, "rrGrant": 0,
        "sq": {"valid": 0, "bits": blank_bits(SQ_FIELDS)},
        "sb": {"valid": 0, "bits": blank_bits(SB_FIELDS)},
        "unc": {"valid": 0, "bits": blank_bits(UNC_FIELDS)},
        "mshr": {"valid": 0, "bits": blank_bits(MSHR_FIELDS)},
        "tld": {"valid": 0, "bits": blank_bits(TLD_FIELDS)},
        "bypass": {"valid": 0, "bits": blank_bits(BYPASS_FIELDS)},
        "stdData": blank_std(),
        "nuke": [{"valid": 0, "bits": blank_bits(NUKE_FIELDS)} for _ in range(2)],
        "rarReady": 1, "rawReady": 1,
    }


def random_pipe_bits(rng: random.Random) -> dict:
    bits = {name: rng.randrange(1 << width)
            for name, width in PIPEIN_FIELDS.items()}
    bits["mask"] = rng.randrange(1 << 16)
    bits["tlbAccessResult"] = rng.randrange(8)
    bits["accessType_instrType"] = rng.randrange(8)
    return bits


def random_resp(rng: random.Random, fields: dict, density=0.3) -> dict:
    bits = {}
    for name, width in fields.items():
        if name.startswith("forwardMask_"):
            bits[name] = 1 if rng.random() < density else 0
        else:
            bits[name] = rng.randrange(1 << width)
    return bits


def random_inputs(rng: random.Random, pipe_valid=None) -> dict:
    inputs = blank_inputs()
    inputs["pipeIn"]["valid"] = (1 if rng.random() < 0.75 else 0)\
        if pipe_valid is None else pipe_valid
    inputs["pipeIn"]["bits"] = random_pipe_bits(rng)
    inputs["redirect"]["valid"] = 1 if rng.random() < 0.15 else 0
    inputs["redirect"]["bits"] = {name: rng.randrange(1 << width)
                                  for name, width in REDIRECT_FIELDS.items()}
    inputs["pmp"] = {"ld": rng.randrange(2), "mmio": rng.randrange(2)}
    inputs["tlbHint"] = {"id": rng.randrange(16), "full": rng.randrange(2)}
    inputs["dcacheResp"]["bits"] = random_resp(rng, DCRESP_FIELDS)
    for key in ("dcacheBankConflict", "dcacheRRBankConflict",
                "dcacheMSHRNack", "rrGrant"):
        inputs[key] = rng.randrange(2)
    for key, fields in (("sq", SQ_FIELDS), ("sb", SB_FIELDS), ("unc", UNC_FIELDS),
                        ("mshr", MSHR_FIELDS), ("tld", TLD_FIELDS),
                        ("bypass", BYPASS_FIELDS)):
        inputs[key]["valid"] = 1 if rng.random() < 0.4 else 0
        inputs[key]["bits"] = random_resp(rng, fields)
    for group in ("current", "previous"):
        for index in range(2):
            inputs["stdData"][group][index]["valid"] = 1 if rng.random() < 0.3 else 0
            inputs["stdData"][group][index]["bits"] = {
                "first_flag": rng.randrange(2), "second_flag": rng.randrange(2),
                "value": rng.randrange(64)}
    for index in range(2):
        inputs["nuke"][index]["valid"] = 1 if rng.random() < 0.4 else 0
        inputs["nuke"][index]["bits"] = {name: rng.randrange(1 << width)
                                         for name, width in NUKE_FIELDS.items()}
    inputs["rarReady"] = 1 if rng.random() < 0.7 else 0
    inputs["rawReady"] = 1 if rng.random() < 0.7 else 0
    return inputs
