"""Entry meanings are semantic variants of044, not a physical coordinate grid."""
import json
from pathlib import Path
from bpuverify.bpu.model.block_entry_learning import PROGRAMS, PROFILES, RULES
from bpuverify.bpu.coverage.block_entry_learning import lifetime_coverage


def test_contract_defines_real_instruction_entries_before_native_credit():
    value=json.loads(Path('docs/bpu-block-entry-learning-contract.json').read_text())
    assert value['existing_feature']=='BPU-INT-044' and value['new_feature_IDs']==0
    assert value['profiles']==list(PROFILES) and value['gap_basis']['integrated_low_region_native_zero_rows']==515
    assert value['no_bank_set_way_enumeration'] and not value['hardware_or_functional_credit_before_DUT_execution']
    assert [p.pc & 7 for p in PROGRAMS] == [1,2]
    for ref in value['source_chain']:
        name,line=ref.rsplit(':',1); assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_existing_feature_retains_high_tag_evidence_and_adds_interior_entries():
    plan=json.loads(Path('verification_plan.json').read_text())
    feature=next(p for p in plan['features'] if p['id']=='BPU-INT-044')
    for status in ('reached','checked'):
        assert 'kunminghu_v3.bpu.owned-early-direction.full-tag-high-bits.'+status in feature['evidence']['coverage'][status]
        assert 'kunminghu_v3.bpu.block-entry-learning.'+status in feature['evidence']['coverage'][status]


def test_coverage_reuses_eight_source_obligations_for_two_entry_meanings():
    for status in ('reached','checked'):
        counts=lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts)==len(PROFILES)*len(RULES)==16 and set(counts.values())=={0}
