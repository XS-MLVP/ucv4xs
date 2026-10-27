from bpuverify.common.model.configuration import PHR_STORAGE_BITS
from itertools import product
import pytest
from bpuverify.bpu.case.abtb.later_taken_plan import plan, joint_proof, programs


@pytest.mark.parametrize('bank,entry_set', tuple(product(range(4), range(64))))
def test_all256_input_only_full_history_index_plans(bank, entry_set):
    intent = plan(bank, entry_set)
    proof = joint_proof(intent)
    assert intent['recurrence_edges'] == (4 if bank == 0 else 5)
    assert intent['cadence_selection_from_input_bank_only'] is True
    assert intent['maximum_MainBTB_residents_per_group'] <= 4
    assert proof['full52_checks'] == 5 * 3 * ((PHR_STORAGE_BITS+7)//8+2) * intent['recurrence_edges']
    assert proof['actual_A_metadata_index_checks'] == 5 * (3 * ((PHR_STORAGE_BITS+7)//8+2) - 1)
    assert len({row['pc'] for alias in range(5) for row in programs(intent, alias)}) == 5 * intent['recurrence_edges']
