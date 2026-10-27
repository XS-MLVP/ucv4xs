"""bpuverify.ubtb.driver.encoding components."""

from __future__ import annotations
from typing import Any
from bpuverify.ubtb.transaction.types import BranchTraining
from bpuverify.ubtb.transaction.types import UbtbBatchTraining
from bpuverify.ubtb.transaction.types import PredictRequest
from bpuverify.ubtb.transaction.address import byte_address
from bpuverify.common.model.address import encode_pruned_pc


def _uint(value, width, name):
    if type(value) is not int or not 0 <= value < (1 << width):
        raise ValueError(f'MicroBTB {name} must fit {width} bits')
    return value


def _encode_lookup(transaction: PredictRequest | None, *, valid: int) -> dict[str, Any]:
    request = transaction or PredictRequest(0)
    return dict(s0_fire=_uint(valid, 1, 'lookup valid'), s1_fire=1,
                start_pc=encode_pruned_pc(byte_address(request.pc, 'lookup PC')))


def _encode_training(transaction: BranchTraining | None, *, valid: int) -> dict[str, Any]:
    request = transaction or BranchTraining(0, 0, 0, 0, 0)
    return {
        "valid": _uint(valid, 1, 'fastTrain valid'),
        "bits": {
            "start_pc": encode_pruned_pc(byte_address(request.pc, 'fastTrain PC')),
            "branch": {
                "target": encode_pruned_pc(byte_address(request.target, 'fastTrain target')),
                "taken": _uint(request.taken, 1, 'fastTrain taken'),
                "position": _uint(request.position, 4, 'fastTrain position'),
                "branch_type": _uint(request.branch_type, 2, 'fastTrain branch_type'),
                "ras_action": _uint(request.ras_action, 2, 'fastTrain ras_action'),
                "mispredict": _uint(request.mispredict, 1, 'fastTrain mispredict'),
            },
        },
    }


def _encode_resolve(
    transaction: UbtbBatchTraining | None, *, valid: int
) -> dict[str, Any]:
    request = transaction or UbtbBatchTraining(0, ())
    if len(request.branches) > 8:
        raise ValueError("MicroBTB resolve has at most eight branch slots")
    if type(request.fire) is not int or request.fire not in (0, 1):
        raise ValueError("MicroBTB resolve fire must be zero or one")
    pc = encode_pruned_pc(byte_address(request.pc, 'resolve PC'))
    if sum(
        bool(branch.valid and branch.mispredict)
        for branch in request.branches if branch is not None
    ) > 1:
        raise ValueError("FTQ resolve permits at most one valid misprediction")
    branches = []
    for branch in request.branches:
        values = {
            "valid": 0 if branch is None else branch.valid,
            "target": 0 if branch is None else encode_pruned_pc(byte_address(branch.target, 'resolve target')),
            "taken": 0 if branch is None else branch.taken,
            "position": 0 if branch is None else branch.position,
            "branch_type": 0 if branch is None else branch.branch_type,
            "ras_action": 0 if branch is None else branch.ras_action,
            "mispredict": 0 if branch is None else branch.mispredict,
        }
        for field, width in (
            ("valid", 1), ("target", 49), ("taken", 1), ("position", 4),
            ("branch_type", 2), ("ras_action", 2), ("mispredict", 1),
        ):
            _uint(values[field], width, 'resolve '+field)
        branches.append(values)
    idle = {key: 0 for key in (
        "valid", "target", "taken", "position", "branch_type",
        "ras_action", "mispredict",
    )}
    branches.extend(dict(idle) for _ in range(8 - len(branches)))
    return {"valid": _uint(valid, 1, 'resolve valid') * request.fire,
            "bits": {"start_pc": pc, "branches": tuple(branches)}}
