"""Both lifetimes and source ancestry are required, not just Main correctness."""
import json
from pathlib import Path
from suites.frontend.bpu.testbenches.bpu.model.short_revisit import PROFILES
from suites.frontend.bpu.testbenches.bpu.model.short_revisit import PROGRAMS
from suites.frontend.bpu.testbenches.bpu.model.short_revisit import rules
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import FALLBACK
from suites.frontend.bpu.testbenches.bpu.coverage.short_revisit import lifetime_coverage


def test_requirement_declares_both_actual_consumers_and_no_fake_replay():
    value=json.loads(Path('docs/spec/verification/contracts/bpu-short-revisit-contract.json').read_text())
    assert value['existing_feature']=='BPU-INT-066' and value['new_feature_IDs']==0
    assert value['profiles']==list(PROFILES) and value['gap_basis']['remaining_integrated_low_zero_rows']==500
    assert value['no_bank_set_way_sweep'] and not value['hardware_or_functional_credit_before_DUT_execution']
    assert {p.positions for p in PROGRAMS}=={ (2,FALLBACK,FALLBACK,FALLBACK),(FALLBACK,)*4 }
    for ref in value['source_chain']:
        name,line=ref.rsplit(':',1); assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_four_real_paths_have116_checking_obligations_not116_functions():
    for status in ('reached','checked'):
        counts=lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts)==sum(len(rules(p)) for p in PROFILES)==116 and set(counts.values())=={0}
