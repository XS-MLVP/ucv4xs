"""Diagnostic only: observe contiguous MicroBTB shaping, no functional credit."""
import json

from suites.frontend.bpu.ubtb.case.definitions import DIRECT
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining


def sequence(*directions, target=DIRECT.target):
    return tuple(
        BranchTraining(DIRECT.pc, target, taken, DIRECT.position, DIRECT.branch_type)
        for taken in directions
    )


async def test_probe_contiguous_shapes(ubtb_agent, request):
    results = {}
    for name, directions in (
        ("taken_taken", (1, 1)),
        ("taken_nt_taken_taken", (1, 0, 1, 1)),
        ("taken_nt_x4", (1, 0, 0, 0, 0)),
        ("taken_nt_x3", (1, 0, 0, 0)),
    ):
        await ubtb_agent.reset()
        transfers = await ubtb_agent.train_contiguous(sequence(*directions))
        ticks = [transfer.accepted_event.tick for transfer in transfers]
        prediction = await ubtb_agent.predict(DIRECT.pc)
        results[name] = dict(
            directions=directions,
            accepted_ticks=ticks,
            valid=prediction.valid,
            target=prediction.target,
            model=dict(
                entries=[dict(key=e.key, confidence=e.confidence, target=e.target)
                         for e in ubtb_agent.reference.model.entries if e.confidence],
            ),
        )
    request.node.user_properties.append(("ubtb_contiguous_probe", json.dumps(results)))
    print(json.dumps(results, indent=2))
