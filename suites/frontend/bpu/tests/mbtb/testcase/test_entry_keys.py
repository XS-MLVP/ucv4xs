"""Both pending entry keys retain their own data, in either feedback order."""
import json
import pytest
from suites.frontend.bpu.mbtb.coverage.two_key_lifetime import Coverage
from suites.frontend.bpu.mbtb.case.two_key_lifetime import check_two_key_lifetime


@pytest.mark.feature("BPU-MBTB-022")
@pytest.mark.mbtb_entry_key_matrix
async def test_two_pending_entry_keys_preserve_targets_and_neighbors_in_either_order(mbtb_agent,program,request):
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:evidence.update(await check_two_key_lifetime(mbtb_agent,program,Coverage(program)),status='PASS')
    finally:request.node.user_properties.append(('semantic_mbtb_two_key_lifetime',json.dumps(evidence,sort_keys=True)))
