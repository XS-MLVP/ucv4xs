"""Both lifetimes and source ancestry are required, not just Main correctness."""
import json
from pathlib import Path
from suites.frontend.bpu.bpu.model.short_revisit import PROFILES,PROGRAMS,rules
from suites.frontend.bpu.bpu.model.early_opposition import FALLBACK
from suites.frontend.bpu.bpu.coverage.short_revisit import lifetime_coverage


def test_requirement_declares_both_actual_consumers_and_no_fake_replay():
    value=json.loads(Path('docs/bpu-short-revisit-contract.json').read_text())
    assert value['existing_feature']=='BPU-INT-066' and value['new_feature_IDs']==0
    assert value['profiles']==list(PROFILES) and value['gap_basis']['remaining_integrated_low_zero_rows']==500
    assert value['no_bank_set_way_sweep'] and not value['hardware_or_functional_credit_before_DUT_execution']
    assert {p.positions for p in PROGRAMS}=={ (2,FALLBACK,FALLBACK,FALLBACK),(FALLBACK,)*4 }
    for ref in value['source_chain']:
        name,line=ref.rsplit(':',1); assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_existing_original_protection_and_new_two_consumer_evidence_both_remain():
    plan=json.loads(Path('verification_plan.json').read_text()); f=next(p for p in plan['features'] if p['id']=='BPU-INT-066')
    for status in ('reached','checked'):
        assert 'kunminghu_v3.bpu.entry-protection.'+status in f['evidence']['coverage'][status]
        assert 'kunminghu_v3.bpu.short-revisit.'+status in f['evidence']['coverage'][status]


def test_four_real_paths_have116_checking_obligations_not116_functions():
    for status in ('reached','checked'):
        counts=lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts)==sum(len(rules(p)) for p in PROFILES)==116 and set(counts.values())=={0}
