"""Actual original contribution/error requirements, not address enumeration."""
from pathlib import Path
import json
from suites.frontend.bpu.testbenches.bpu.model.entry_protection import PROFILES
from suites.frontend.bpu.testbenches.bpu.model.entry_protection import rules
from suites.frontend.bpu.testbenches.bpu.coverage.entry_protection import lifetime_coverage


def test_requirement_keeps_original_entry_and_actual_confirmation_scope():
    value=json.loads(Path('docs/spec/verification/contracts/bpu-entry-protection-contract.json').read_text())
    assert value['existing_feature']=='BPU-INT-066' and value['new_feature_IDs']==0
    assert value['profiles']==list(PROFILES) and value['gap_basis']['remaining_integrated_low_zero_rows']==509
    assert value['no_bank_set_way_sweep'] and not value['hardware_or_functional_credit_before_DUT_execution']
    for ref in value['source_chain']:
        name,line=ref.rsplit(':',1); assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_four_semantic_programs_have74_source_obligations_not74_functions():
    for status in ('reached','checked'):
        counts=lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts)==sum(len(rules(p)) for p in PROFILES)==74 and set(counts.values())=={0}
