"""suites.frontend.bpu.ittage.driver.encoding components."""

from __future__ import annotations
from suites.frontend.bpu.models.address import encode_pruned_pc
from suites.frontend.bpu.ittage.transaction.types import IttageBranchFeedback


def _encode_branch_feedback(branch: IttageBranchFeedback | None) -> dict[str, int]:
    if branch is None:
        return {
            "valid": 0,
            "target": 0,
            "taken": 0,
            "branch_type": 0,
            "ras_action": 0,
            "mispredict": 0,
        }
    return {
        "valid": branch.valid,
        "target": encode_pruned_pc(branch.target),
        "taken": branch.taken,
        "branch_type": branch.branch_type,
        "ras_action": branch.ras_action,
        "mispredict": branch.mispredict,
    }
