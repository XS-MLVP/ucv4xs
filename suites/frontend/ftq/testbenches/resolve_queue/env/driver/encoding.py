"""ResolveQueue request encoding; no DUT state is read to build a request."""

from __future__ import annotations

from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import ResolveReport


def encode(report: ResolveReport) -> dict[str, int]:
    if type(report) is not ResolveReport:
        raise ValueError('ResolveQueue requires a validated ResolveReport')
    return {
        "valid": 1,
        "index_flag": report.flag,
        "index": report.index,
        "offset": report.offset,
        "pc": report.pc,
        "target": report.target,
        "taken": report.taken,
        "mispredict": report.mispredict,
        "branch_type": report.branch_type,
        "ras_action": report.ras_action,
    }
