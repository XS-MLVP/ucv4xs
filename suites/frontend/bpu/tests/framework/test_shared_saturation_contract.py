"""Human-readable requirements and source associations precede native proof."""
import json
from pathlib import Path
from suites.frontend.bpu.bpu.coverage.shared_saturation import RULES,lifetime_coverage
from suites.frontend.bpu.bpu.model.tage.shared_saturation import PROGRAMS


def test_requirement_is_current_learning_ownership_not_a_storage_coordinate():
    c=json.loads(Path('docs/shared-saturation-contract.json').read_text())
    assert c['existing_feature']=='BPU-INT-087' and c['new_functional_IDs']==0
    assert c['no_bank_set_way_enumeration'] and '旧预测计数' in c['owner']
    assert c['gap_basis']['unclosed_rows']==103 and len(PROGRAMS)==2 and len(RULES)==9
    for ref in c['source_chain']:
        name,line=ref.rsplit(':',1);assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_existing_feature_keeps_the_old_capacity_requirement_and_adds_a_new_pair():
    plan=json.loads(Path('verification_plan.json').read_text())
    feature=next(p for p in plan['features'] if p['id']=='BPU-INT-087')
    for status in ('reached','checked'):
        assert 'kunminghu_v3.bpu.owned-direction-capacity.'+status in feature['evidence']['coverage'][status]
        assert lifetime_coverage(status).instance in feature['evidence']['coverage'][status]
    assert 'bpu/checker/shared_saturation.py' in feature['evidence']['checks']


def test_new_schemas_cross_only_declared_semantic_profiles_and_obligations():
    for status in ('reached','checked'):
        group=lifetime_coverage(status)
        assert group.coverage==0
        counts=group.report()['points'][0]['counts']
        assert len(counts)==18 and set(counts.values())=={0}
