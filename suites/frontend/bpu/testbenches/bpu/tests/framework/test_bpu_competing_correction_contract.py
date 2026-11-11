"""Missing native rows and missing original-lifetime proof are not synonyms."""
import json
from pathlib import Path
from suites.frontend.bpu.testbenches.bpu.model.competing_correction import PROFILES
from suites.frontend.bpu.testbenches.bpu.model.competing_correction import PROGRAMS
from suites.frontend.bpu.testbenches.bpu.model.competing_correction import RULES
from suites.frontend.bpu.testbenches.bpu.coverage.competing_correction import lifetime_coverage


def test_contract_keeps_guard_residues_separate_from_missing_arbitration_proof():
    value=json.loads(Path('docs/spec/verification/contracts/bpu-competing-correction-contract.json').read_text())
    assert value['existing_feature']=='BPU-INT-034' and value['new_feature_IDs']==0
    assert value['profiles']==list(PROFILES) and value['no_bank_set_way_sweep']
    assert not value['hardware_or_functional_credit_before_DUT_execution']
    assert not value['gap_basis']['all1420rows_caused_by_competing_corrections']
    assert value['gap_basis']['PHR_missing']==value['gap_basis']['PHR_local_guard_rows']+value['gap_basis']['PHR_owned_cursor_conditional_rows']
    for ref in value['source_chain']:
        name,line=ref.rsplit(':',1);assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_lifetime_groups_start_empty_without_bank_or_way_feature_multiplication():
    assert len({p.a for p in PROGRAMS})==1 and len({p.b for p in PROGRAMS})==2
    for status in ('reached','checked'):
        counts=lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts)==len(PROFILES)*len(RULES)==52 and set(counts.values())=={0}
