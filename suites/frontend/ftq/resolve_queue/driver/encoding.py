"""ResolveQueue request encoding; no DUT state is read to build a request."""

from __future__ import annotations

from typing import Mapping

from suites.frontend.ftq.resolve_queue.transaction.types import ResolveReport


def encode(report: ResolveReport) -> dict[str, int | bool]:
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
