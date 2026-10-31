"""FTQ producer encoding: typed requests to flat input pins."""

from __future__ import annotations

from suites.frontend.ftq.ftq.transaction.types import BackendRedirect
from suites.frontend.ftq.ftq.transaction.types import IfuRedirect
from suites.frontend.ftq.ftq.transaction.types import Meta
from suites.frontend.ftq.ftq.transaction.types import Prediction
from suites.frontend.ftq.oracle import CallRet
from suites.frontend.ftq.resolve_queue.transaction.types import ResolveReport


def encode_prediction(prediction: Prediction) -> dict[str, int]:
    return {
        "valid": 1,
        "start_pc": prediction.start_pc,
        "taken": prediction.taken,
        "end_position": prediction.end_position,
        "s2_override": prediction.s2_override,
        "s3_override": prediction.s3_override,
        "s2_flag": prediction.s2_flag,
        "s2_value": prediction.s2_ptr or 0,
    }


def encode_meta(meta: Meta) -> dict[str, int]:
    return {"valid": 1, **dict(meta.fields)}


def encode_backend_redirect(redirect: BackendRedirect) -> dict[str, int]:
    return {
        "valid": 1,
        "index_flag": redirect.flag,
        "index": redirect.index,
        "pc": redirect.pc,
        "taken": redirect.taken,
        "offset": redirect.offset,
        "is_rvc": redirect.is_rvc,
        "branch_type": redirect.branch_type,
        "ras_action": redirect.ras_action,
        "target": redirect.target,
        "level": redirect.level,
        "ipf": redirect.ipf,
        "igpf": redirect.igpf,
        "iaf": redirect.iaf,
        "satp_flush": redirect.satp_flush,
        "debug_ctrl": redirect.debug_ctrl,
        "debug_memvio": redirect.debug_memvio,
    }


def encode_ifu_redirect(redirect: IfuRedirect) -> dict[str, int]:
    return {
        "valid": 1,
        "index_flag": redirect.flag,
        "index": redirect.index,
        "can_train": redirect.can_train,
        "pc": redirect.pc,
        "taken": redirect.taken,
        "offset": redirect.offset,
        "is_rvc": redirect.is_rvc,
        "branch_type": redirect.branch_type,
        "ras_action": redirect.ras_action,
        "target": redirect.target,
    }


def encode_resolve(report: ResolveReport) -> dict[str, int]:
    return {
        "valid": 1,
        "flag": report.flag,
        "index": report.index,
        "offset": report.offset,
        "pc": report.pc,
        "target": report.target,
        "taken": report.taken,
        "mispredict": report.mispredict,
        "branch_type": report.branch_type,
        "ras_action": report.ras_action,
    }


def encode_callret(row: CallRet) -> dict[str, int]:
    return {"valid": 1, "ras": row.ras, "ptr": row.ptr}
