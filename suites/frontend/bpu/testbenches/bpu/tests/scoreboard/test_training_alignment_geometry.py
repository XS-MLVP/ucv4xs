from dataclasses import asdict
import pytest
from suites.frontend.bpu.testbenches.bpu.env.driver.encoding import _encode_training
from suites.frontend.bpu.testbenches.bpu.model.sc.model import encoded_payload
from suites.frontend.bpu.testbenches.bpu.model.sc.model import canonical
from suites.frontend.bpu.testbenches.bpu.model.alignment import ALL_CASES
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBatchTraining
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBranchFeedback


class RecordingBits:
    branches = (None,) * 8

    def drive(self, value):
        self.value = value


def test_full_legal_domain_is_784_not_an_arbitrary_position_subset():
    assert len(ALL_CASES) == 784
    assert {(case.first_align, case.offset, case.position) for case in ALL_CASES} == {
        (align, offset, position) for align in (0, 1) for offset in range(16)
        for position in range(32) if position >= offset}


@pytest.mark.parametrize('case', ALL_CASES, ids=[case.label for case in ALL_CASES])
def test_actual_driver_and_independent_reference_use_real_ftq_geometry(case):
    bits = RecordingBits()
    tx = BpuBatchTraining(case.pc, {'actual_source_marker': 17},
        (BpuBranchFeedback(case.position, case.target, 1),))
    _encode_training(bits, tx)
    # The first two consumers only retain the head; MainBTB's third copy still
    # needs both real logical windows, including the aligned successor.
    head, successor = case.logical_start_pcs
    expected = [[{'addr': head}], [{'addr': head}], [{'addr': head}, {'addr': successor}]]
    assert canonical(bits.value['start_pcs']) == expected
    assert encoded_payload(canonical(asdict(tx)))['start_pcs'] == expected
    assert bits.value['meta'] == tx.resolve_meta
    assert canonical(bits.value) == encoded_payload(canonical(asdict(tx)))
