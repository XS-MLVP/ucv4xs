"""A dynamic indirect update cannot relearn an unexecuted conditional sibling.

Expected predictor state remains owned by the production semantic references.
This module describes stimuli and qualifies this bounded resolved path only.
"""
from dataclasses import replace

from suites.frontend.bpu.bpu.model.main_service import PC
from suites.frontend.bpu.bpu.model.main_service import entry_payload
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.mbtb.model.semantic import Entry, Target, coordinate, tag
from suites.frontend.bpu.bpu.model.main_sibling import (
    Program as OriginalProgram, EARLIER, LATER, FALLBACK, LATER_TARGET,
    STREAM_PC, PHASES, ORIGINS)


# Different legitimate dynamic targets of the SAME indirect instruction.
# Region carry is already independently crossed by the preceding staged batch.
VERSIONS = tuple(PC + offset for offset in (0x600, 0x800, 0xA00))


class Program(OriginalProgram):
    def effect(self, version):
        return entry_payload(coordinate(PC)[2], Entry(
            tag(PC), EARLIER, 3, 0, Target.encode(PC, VERSIONS[version])))

    def state(self):
        return dict(super().state(), earlier_instruction='indirect throughout',
            initial_earlier_counter=2, dynamic_targets=VERSIONS,
            semantics='changing an earlier indirect target preserves the learned direction of its unexecuted conditional sibling',
            scope='bounded BPU feedback contract; not a complete FTQ execution proof')


def qualified_feedback(predicted, outcomes):
    """First wrong decision truncates this actual resolved path, as FTQ does.

    The prediction is independently derived from the ORIGINAL source token.
    It is not sampled SRAM state. These programs have zero or more NT branches
    followed by one taken branch and do not cover phantom predicted branches.
    """
    if (type(outcomes) is not tuple or not outcomes
            or any(type(branch) is not BpuBranchFeedback for branch in outcomes)
            or any(branch.taken not in (0, 1) for branch in outcomes)
            or not outcomes[-1].taken or any(branch.taken for branch in outcomes[:-1])
            or tuple(branch.position for branch in outcomes) != tuple(sorted(
                {branch.position for branch in outcomes}))):
        raise ValueError('one ordered resolved path ending in its only taken branch required')
    if predicted.taken and predicted.position < outcomes[-1].position and all(
            branch.position != predicted.position for branch in outcomes):
        raise ValueError('phantom predicted branch requires a different semantic program')
    result = []
    for branch in outcomes:
        wrong = (predicted.taken and predicted.position == branch.position) if not branch.taken else (
            not predicted.taken or
            (predicted.position, predicted.target, int(predicted.kind), int(predicted.action)) !=
            (branch.position, branch.target, branch.branch_type, branch.ras_action))
        result.append(replace(branch, mispredict=int(wrong)))
        if wrong:
            break  # FTQ excludes later branches after the first misprediction.
    return tuple(result)
