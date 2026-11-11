"""Cross-block meaning and unchanged physical coverage denominators."""
import json
from pathlib import Path
from suites.frontend.bpu.testbenches.bpu.model.cross_block_learning import PROFILES
from suites.frontend.bpu.testbenches.bpu.model.cross_block_learning import PROGRAMS
from suites.frontend.bpu.testbenches.bpu.model.cross_block_learning import RULES
from suites.frontend.bpu.testbenches.bpu.coverage.cross_block_learning import lifetime_coverage


def test_contract_uses_real_edges_not_free_UT_read_coordinates():
    value=json.loads(Path('docs/spec/verification/contracts/bpu-cross-block-learning-contract.json').read_text())
    assert value['existing_feature']=='BPU-INT-044' and value['new_feature_IDs']==0
    assert value['profiles']==list(PROFILES) and value['no_bank_set_way_sweep']
    assert not value['hardware_or_functional_credit_before_DUT_execution']
    assert len({p.a for p in PROGRAMS})==1 and len({p.b for p in PROGRAMS})==2
    for ref in value['source_chain']:
        name,line=ref.rsplit(':',1); assert 0<int(line)<=len(Path(name).read_text().splitlines())


def test_cross_block_group_starts_empty_and_obligations_are_not_new_feature_IDs():
    for status in ('reached','checked'):
        counts=lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts)==len(PROFILES)*len(RULES)==40 and set(counts.values())=={0}
