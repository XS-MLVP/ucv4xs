"""Different-set training survives dirty and clean multi-hit clear overlaps."""
import json
import pytest
from bpuverify.mbtb.coverage.cleanup_lifetime import Coverage
from bpuverify.mbtb.case.cleanup_lifetime import check_cleanup_lifetime


@pytest.mark.feature('BPU-MBTB-026')
@pytest.mark.mbtb_cleanup_matrix
async def test_multi_hit_cleanup_and_training_preserve_both_sets(mbtb_agent,program,request):
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:evidence.update(await check_cleanup_lifetime(mbtb_agent,program,Coverage(program)),status='PASS')
    finally:request.node.user_properties.append(('semantic_mbtb_cleanup_lifetime',json.dumps(evidence,sort_keys=True)))
