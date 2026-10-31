"""FTQ port binding over generated flat pins."""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.ports import prefix_pins
from suites.frontend.ftq.harness import Dut


RESOLVE_FIELDS = {
    "valid": "valid",
    "flag": "bits_ftqIdx_flag",
    "index": "bits_ftqIdx_value",
    "offset": "bits_ftqOffset",
    "pc": "bits_pc_addr",
    "target": "bits_target_addr",
    "taken": "bits_taken",
    "mispredict": "bits_mispredict",
    "branch_type": "bits_attribute_branchType",
    "ras_action": "bits_attribute_rasAction",
}


def lane(dut: Dut, prefix: str, fields: dict[str, str], name: str) -> Pins:
    return Pins(dut, {logical: prefix + pin for logical, pin in fields.items()},
                name=name)


def resolve_lane(dut: Dut, index: int) -> Pins:
    return lane(dut, f"io_fromBackend_resolve_{index}_", RESOLVE_FIELDS,
                f"ftq.resolve{index}")


def callret_lane(dut: Dut, index: int) -> Pins:
    prefix = f"io_fromBackend_callRetCommit_{index}_"
    return Pins(dut, {
        "valid": prefix + "valid",
        "ras": prefix + "bits_rasAction",
        "ptr": prefix + "bits_ftqPtr_value",
    }, name=f"ftq.callret{index}")


def training_out(dut: Dut) -> Pins:
    names = {
        "valid": "io_toBpu_train_valid",
        "start_pc": "io_toBpu_train_bits_startPcVec_dup_0_0_addr",
        "start_pc1": "io_toBpu_train_bits_startPcVec_dup_1_0_addr",
        "start_pc2": "io_toBpu_train_bits_startPcVec_dup_2_0_addr",
        "start_pc2_1": "io_toBpu_train_bits_startPcVec_dup_2_1_addr",
        "meta_phr": "io_toBpu_train_bits_meta_phr_phrPtr_value",
        "meta_ghr": "io_toBpu_train_bits_meta_commonHR_ghr",
        "meta_common_valid": "io_toBpu_train_bits_meta_commonHR_valid",
    }
    # TrainEntry carries no explicit FTQ value field; both duplicated buses
    # come from the same resolve transaction, so use slot 0 branch to derive
    # nothing and rely on checker-provided index.  The generated port only
    # exposes startPcVec, so index is tracked from the driver/monitor boundary.
    for slot in range(8):
        base = f"io_toBpu_train_bits_branches_{slot}_"
        for field in ("valid", "bits_target_addr", "bits_taken",
                      "bits_cfiPosition", "bits_attribute_branchType",
                      "bits_attribute_rasAction", "bits_mispredict"):
            names[f"slot{slot}.{field}"] = base + field
    return Pins(dut, names, name="ftq.train")


def prefetch_out(dut: Dut) -> Pins:
    names = {"valid": "io_toICache_toPrefetch_valid",
             "case": "io_toICache_toPrefetch_bits_twoPrefetchCase_value"}
    common = ("startVAddr_addr", "nextLineVAddr_addr", "vSetIdx_0",
              "vSetIdx_1", "isCrossLine", "ftqIdx_flag", "ftqIdx_value")
    for req in range(2):
        base = f"io_toICache_toPrefetch_bits_req_{req}_"
        for field in common:
            names[f"req{req}.{field}"] = base + field
    names["req0.backendException_value"] = (
        "io_toICache_toPrefetch_bits_req_0_backendException_value")
    return Pins(dut, names, name="ftq.prefetch")


def fetch_out(dut: Dut) -> Pins:
    names = {"valid": "io_toICache_toMainPipe_valid"}
    common = ("vAddr_0_addr", "vAddr_1_addr", "taken",
              "endPosition", "bankSel_0", "bankSel_1", "ftqIdx_flag",
              "ftqIdx_value")
    for req in range(2):
        base = f"io_toICache_toMainPipe_bits_req_{req}_"
        for field in common:
            names[f"req{req}.{field}"] = base + field
    names["req1.valid"] = "io_toICache_toMainPipe_bits_req_1_valid"
    names["req0.hasBackendException"] = (
        "io_toICache_toMainPipe_bits_req_0_hasBackendException")
    names["req0.hasSatpFlush"] = "io_toICache_toMainPipe_bits_req_0_hasSatpFlush"
    return Pins(dut, names, name="ftq.fetch")


@dataclass(frozen=True)
class FtqPorts:
    prediction: Pins
    prediction_ready: Pins
    meta: Pins
    backend_redirect: Pins
    ifu_redirect: Pins
    resolve: tuple[Pins, Pins, Pins]
    callret: tuple[Pins, ...]
    commit: Pins
    consumers: Pins
    ahead: Pins
    train: Pins
    commit_out: Pins
    redirect_out: Pins
    prefetch: Pins
    fetch: Pins
    flush: Pins
    topdown: Pins
    backend: Pins
    bpu_ptr: Pins

    @classmethod
    def bind(cls, dut: Dut, *, commit_width: int = 8) -> "FtqPorts":
        prediction = Pins(dut, {
            "valid": "io_fromBpu_prediction_valid",
            "start_pc": "io_fromBpu_prediction_bits_startPc_addr",
            "taken": "io_fromBpu_prediction_bits_taken",
            "end_position": "io_fromBpu_prediction_bits_endPosition",
            "s2_override": "io_fromBpu_prediction_bits_s2Override",
            "s3_override": "io_fromBpu_prediction_bits_s3Override",
            "s2_flag": "io_fromBpu_s2FtqPtr_flag",
            "s2_value": "io_fromBpu_s2FtqPtr_value",
        }, name="ftq.prediction")
        prediction_ready = Pins(dut, {
            "ready": "io_fromBpu_prediction_ready",
        }, name="ftq.prediction_ready")
        meta = Pins(dut, {
            "valid": "io_fromBpu_meta_valid",
            "s3_flag": "io_fromBpu_s3FtqPtr_flag",
            "s3_value": "io_fromBpu_s3FtqPtr_value",
            **prefix_pins(dut, "io_fromBpu_meta_bits_", name="ftq.meta"),
        }, name="ftq.meta")
        backend_redirect = lane(dut, "io_fromBackend_redirect_", {
            "valid": "valid",
            "index_flag": "bits_ftqIdx_flag",
            "index": "bits_ftqIdx_value",
            "pc": "bits_pc",
            "taken": "bits_taken",
            "offset": "bits_ftqOffset",
            "is_rvc": "bits_isRVC",
            "branch_type": "bits_attribute_branchType",
            "ras_action": "bits_attribute_rasAction",
            "target": "bits_target",
            "level": "bits_level",
            "ipf": "bits_backendIPF",
            "igpf": "bits_backendIGPF",
            "iaf": "bits_backendIAF",
            "satp_flush": "bits_satpFlush",
            "debug_ctrl": "bits_debugIsCtrl",
            "debug_memvio": "bits_debugIsMemVio",
        }, "ftq.backend_redirect")
        ifu_redirect = lane(dut, "io_fromIfu_wbRedirect_", {
            "valid": "valid",
            "index_flag": "bits_ftqIdx_flag",
            "index": "bits_ftqIdx_value",
            "can_train": "bits_canTrain",
            "pc": "bits_pc",
            "taken": "bits_taken",
            "offset": "bits_ftqOffset",
            "is_rvc": "bits_isRVC",
            "branch_type": "bits_attribute_branchType",
            "ras_action": "bits_attribute_rasAction",
            "target": "bits_target",
        }, "ftq.ifu_redirect")
        resolve = tuple(resolve_lane(dut, index) for index in range(3))
        callret = tuple(callret_lane(dut, index) for index in range(commit_width))
        commit = Pins(dut, {
            "valid": "io_fromBackend_commit_valid",
            "flag": "io_fromBackend_commit_bits_flag",
            "ptr": "io_fromBackend_commit_bits_value",
        }, name="ftq.commit")
        consumers = Pins(dut, {
            "prefetch": "io_toICache_toPrefetch_ready",
            "mainpipe": "io_toICache_toMainPipe_ready",
            "train": "io_toBpu_train_ready",
            "real_two_fetch": "io_fromICache_fromMainPipe_realTwoFetchValid",
        }, name="ftq.consumers")
        ahead = Pins(dut, {
            "valid": "io_fromBackend_ftqIdxAhead_valid",
            "flag": "io_fromBackend_ftqIdxAhead_bits_flag",
            "value": "io_fromBackend_ftqIdxAhead_bits_value",
        }, name="ftq.ahead")
        train = training_out(dut)
        commit_out = Pins(dut, {
            "valid": "io_toBpu_commit_valid",
            "ras": "io_toBpu_commit_bits_attribute_rasAction",
            "meta_ssp": "io_toBpu_commit_bits_meta_ras_ssp",
            "meta_tosw_flag": "io_toBpu_commit_bits_meta_ras_tosw_flag",
            "meta_tosw_value": "io_toBpu_commit_bits_meta_ras_tosw_value",
        }, name="ftq.commit_out")
        redirect_out = Pins(dut, {
            "valid": "io_toBpu_redirect_valid",
            "cfi_pc": "io_toBpu_redirect_bits_cfiPc_addr",
            "target": "io_toBpu_redirect_bits_target_addr",
            "taken": "io_toBpu_redirect_bits_taken",
            "branch_type": "io_toBpu_redirect_bits_attribute_branchType",
            "ras_action": "io_toBpu_redirect_bits_attribute_rasAction",
            "meta_phr": "io_toBpu_redirect_bits_meta_phr_phrPtr_value",
            "meta_ghr": "io_toBpu_redirect_bits_meta_commonHRMeta_ghr",
        }, name="ftq.redirect_out")
        prefetch = prefetch_out(dut)
        fetch = fetch_out(dut)
        flush = Pins(dut, {
            "s2_valid": "io_toICache_flushFromBpu_s2_valid",
            "s2_flag": "io_toICache_flushFromBpu_s2_bits_flag",
            "s2_value": "io_toICache_flushFromBpu_s2_bits_value",
            "s3_valid": "io_toICache_flushFromBpu_s3_valid",
            "s3_flag": "io_toICache_flushFromBpu_s3_bits_flag",
            "s3_value": "io_toICache_flushFromBpu_s3_bits_value",
            "redirect_flush": "io_toICache_redirectFlush",
            "to_ifu_redirect": "io_toIfu_redirect_valid",
            "ifu_s3_flush": "io_toIfu_flushFromBpu_s3_valid",
        }, name="ftq.flush")
        topdown = Pins(dut, {
            **{f"reason{index}": f"io_toIfu_topdownInfo_reasons_{index}"
               for index in (2, 3, 5, 6, 7, 8, 9)},
            "backend_redirect": "io_backendRedirectTopdown_backendRedirect",
            "control_flow": "io_backendRedirectTopdown_controlFlowRedirect",
            "memory_violation": "io_backendRedirectTopdown_memoryViolationRedirect",
            "tage_miss": "io_backendRedirectTopdown_tageMissBubble",
            "ittage_miss": "io_backendRedirectTopdown_ittageMissBubble",
            "ras_miss": "io_backendRedirectTopdown_rasMissBubble",
        }, name="ftq.topdown")
        backend = Pins(dut, {
            "wen": "io_toBackend_wen",
            "index": "io_toBackend_ftqIdx",
            "start_pc": "io_toBackend_startPc_addr",
        }, name="ftq.backend")
        bpu_ptr = Pins(dut, {
            "flag": "io_toBpu_bpuPtr_flag",
            "value": "io_toBpu_bpuPtr_value",
        }, name="ftq.bpu_ptr")
        return cls(prediction, prediction_ready, meta,
                   backend_redirect, ifu_redirect, resolve, callret, commit,
                   consumers, ahead, train, commit_out, redirect_out,
                   prefetch, fetch, flush, topdown, backend, bpu_ptr)
