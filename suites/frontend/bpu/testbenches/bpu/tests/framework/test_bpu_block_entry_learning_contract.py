"""Entry meanings are semantic variants of044, not a physical coordinate grid."""
import json
from pathlib import Path
from suites.frontend.bpu.testbenches.bpu.model.block_entry_learning import PROGRAMS
from suites.frontend.bpu.testbenches.bpu.model.block_entry_learning import PROFILES
from suites.frontend.bpu.testbenches.bpu.model.block_entry_learning import RULES
from suites.frontend.bpu.testbenches.bpu.coverage.block_entry_learning import lifetime_coverage


def test_contract_defines_real_instruction_entries_before_native_credit():
    value=json.loads(Path('docs/spec/verification/contracts/bpu-block-entry-learning-contract.json').read_text())
    assert value['existing_feature']=='BPU-INT-044' and value['new_feature_IDs']==0
    assert value['profiles']==list(PROFILES) and value['gap_basis']['integrated_low_region_native_zero_rows']==515
    assert value['no_bank_set_way_enumeration'] and not value['hardware_or_functional_credit_before_DUT_execution']
    assert [p.pc & 7 for p in PROGRAMS] == [1,2]
    for ref in value['source_chain']:
        name,line=ref.rsplit(':',1); assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_coverage_reuses_eight_source_obligations_for_two_entry_meanings():
    for status in ('reached','checked'):
        counts=lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts)==len(PROFILES)*len(RULES)==16 and set(counts.values())=={0}
