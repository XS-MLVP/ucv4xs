"""ResolveQueue monitor decoding: training entry is a full queue head."""

from __future__ import annotations

from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.resolve_queue.transaction.types import Branch
from suites.frontend.ftq.resolve_queue.transaction.types import Training


def decode_training(dut: Dut, train: Pins) -> Training | None:
    if not train.b("valid"):
        return None
    branches = []
    for slot in range(8):
        if not train.b(f"slot{slot}.valid"):
            continue
        branches.append(Branch(
            position=train.u(f"slot{slot}.bits_cfiPosition"),
            target=train.u(f"slot{slot}.bits_target_addr"),
            taken=train.u(f"slot{slot}.bits_taken"),
            mispredict=train.u(f"slot{slot}.bits_mispredict"),
            branch_type=train.u(f"slot{slot}.bits_attribute_branchType"),
            ras_action=train.u(f"slot{slot}.bits_attribute_rasAction"),
        ))
    return Training(
        index=train.u("index"),
        flag=train.u("index_flag"),
        start_pc=train.u("start_pc"),
        branches=tuple(branches),
    )


def encode_branch(branch: Branch, offset: int) -> dict[str, int]:
    """Build a comparable field view used by checkers, never by drivers."""

    return dict(position=branch.position, offset=offset, target=branch.target,
                taken=branch.taken, mispredict=branch.mispredict,
                branch_type=branch.branch_type, ras_action=branch.ras_action)
