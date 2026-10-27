"""bpuverify.mbtb.driver.encoding components."""

from __future__ import annotations
from bpuverify.mbtb.transaction.types import MbtbBranchFeedback


def _encode_branch_feedback(branch: MbtbBranchFeedback | None) -> dict[str, int]:
    if branch is None:
        return {
            "valid": 0,
            "target": 0,
            "taken": 0,
            "position": 0,
            "branch_type": 0,
            "ras_action": 0,
            "mispredict": 0,
        }
    return {
        "valid": 1,
        "target": branch.target,
        "taken": branch.taken,
        "position": branch.position,
        "branch_type": branch.branch_type,
        "ras_action": branch.ras_action,
        "mispredict": branch.mispredict,
    }
