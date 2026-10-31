"""suites.frontend.bpu.abtb.driver.encoding components."""

from __future__ import annotations
from typing import Any
from suites.frontend.bpu.abtb.transaction.types import AbtbTraining


def _encode_training(transaction: AbtbTraining) -> dict[str, Any]:
    return {
        "start_pc": transaction.pc,
        "meta": transaction.meta,
        "branch": {
            "target": transaction.target,
            "taken": transaction.taken,
            "position": transaction.position,
            "branch_type": transaction.branch_type,
            "ras_action": transaction.ras_action,
        },
    }
