"""One readable original-agreement requirement, not a new address matrix."""
import json
from pathlib import Path
from suites.frontend.bpu.utage.model.delayed_agreement import PROGRAMS, RULES
from suites.frontend.bpu.utage.coverage.delayed_agreement import lifetime_coverage


def test_nonzero_prestate_and_direction_learning_are_explicit():
    contract = json.loads(Path('docs/utage-delayed-agreement-contract.json').read_text())
    assert contract['existing_feature'] == 'BPU-UTAGE-021' and contract['new_feature_IDs'] == 0
    assert contract['profiles'] == [p.label for p in PROGRAMS]
    assert '保护为1' in contract['event'] and '方向' in contract['effect']
    assert contract['no_bank_set_way_enumeration'] and contract['no_fixed_native_settling_delay']
    assert contract['gap_basis']['short_provider_native_zero_rows'] == 4192
    for ref in contract['source_chain']:
        name, line = ref.rsplit(':', 1)
        assert 0 < int(line) <= len(Path(name).read_text().splitlines())


def test_old_denominator_and_old_case_remain_required():
    plan = json.loads(Path('verification_plan.json').read_text())
    feature = next(p for p in plan['features'] if p['id'] == 'BPU-UTAGE-021')
    for status in ('reached', 'checked'):
        for family in ('delayed-protection', 'delayed-agreement'):
            assert 'kunminghu_v3.utage.'+family+'.'+status in feature['evidence']['coverage'][status]
    assert 'utage/env/delayed_protection.py' in feature['evidence']['checks']
    assert 'tests/utage/testcase/test_delayed_agreement.py' in feature['evidence']['checks']


def test_new_schema_crosses_only_declared_agreement_lifetimes():
    for status in ('reached', 'checked'):
        counts = lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts) == len(PROGRAMS)*len(RULES) == 60 and set(counts.values()) == {0}
