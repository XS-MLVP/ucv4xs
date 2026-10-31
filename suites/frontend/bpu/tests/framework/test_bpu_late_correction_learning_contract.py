"""Human original-teaching events, separate domains and unchanged physical schema."""
import json
from pathlib import Path
from suites.frontend.bpu.bpu.model.late_correction_learning import PROFILES,PROGRAMS,RULES
from suites.frontend.bpu.bpu.coverage.late_correction_learning import lifetime_coverage


def test_contract_defines_original_teaching_before_coverage_not_physical_variants():
    value=json.loads(Path('docs/bpu-late-correction-learning-contract.json').read_text())
    assert value['existing_feature']=='BPU-INT-044' and value['new_feature_IDs']==0
    assert value['profiles']==list(PROFILES) and value['no_bank_set_way_sweep']
    assert not value['hardware_or_functional_credit_before_DUT_execution']
    assert value['new_predictor_algorithms']==0 and value['no_RTL_DUT_SDK_changes']
    assert len({p.a for p in PROGRAMS})==1 and len({p.b for p in PROGRAMS})==2
    for ref in value['source_chain']:
        name,line=ref.rsplit(':',1); assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_new_obligations_start_empty_and_are_not_44_new_functions():
    for status in ('reached','checked'):
        counts=lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts)==len(PROFILES)*len(RULES)==44 and set(counts.values())=={0}


def test_plan_retains_old_evidence_beside_independent_late_teaching():
    plan=json.loads(Path('verification_plan.json').read_text())
    feature=next(p for p in plan['features'] if p['id']=='BPU-INT-044')
    for status in ('reached','checked'):
        for family in ('block-entry-learning','cross-block-learning','late-correction-learning'):
            assert 'kunminghu_v3.bpu.'+family+'.'+status in feature['evidence']['coverage'][status]
