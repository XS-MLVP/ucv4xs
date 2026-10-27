"""Original correctness is a readable semantic qualification requirement."""
import json
from pathlib import Path
from bpuverify.utage.model.delayed_protection import PROGRAMS, RULES
from bpuverify.utage.coverage.delayed_protection import lifetime_coverage


def test_requirement_is_original_correctness_not_current_wire_direction():
    contract = json.loads(Path('docs/utage-delayed-protection-contract.json').read_text())
    assert contract['existing_feature'] == 'BPU-UTAGE-021' and contract['new_feature_IDs'] == 0
    assert contract['profiles'] == [p.label for p in PROGRAMS]
    assert contract['no_bank_set_way_enumeration'] and contract['no_fixed_native_settling_delay']
    assert '原预测' in contract['owner'] and '当前' in contract['effect']
    assert contract['gap_basis']['short_provider_native_zero_rows'] == 4192
    for ref in contract['source_chain']:
        name, line = ref.rsplit(':', 1)
        assert 0 < int(line) <= len(Path(name).read_text().splitlines())


def test_existing_feature_and_old_protection_obligations_remain_registered():
    plan = json.loads(Path('verification_plan.json').read_text())
    feature = next(p for p in plan['features'] if p['id'] == 'BPU-UTAGE-021')
    for status in ('reached', 'checked'):
        for family in ('selective-protection-alias', 'long-provider-protection', 'delayed-protection'):
            assert 'kunminghu_v3.utage.'+family+'.'+status in feature['evidence']['coverage'][status]
    assert 'bpuverify/utage/checker/delayed_protection.py' in feature['evidence']['checks']


def test_new_denominator_is_declared_original_lifetimes_not_storage_coordinates():
    for status in ('reached', 'checked'):
        group = lifetime_coverage(status)
        counts = group.report()['points'][0]['counts']
        assert len(counts) == len(PROGRAMS)*len(RULES) == 48 and set(counts.values()) == {0}
