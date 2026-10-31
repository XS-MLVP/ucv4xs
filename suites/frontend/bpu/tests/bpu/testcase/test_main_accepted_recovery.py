"""A later source cancellation cannot erase already accepted learning."""
import json
import pytest
from suites.frontend.bpu.bpu.model.main_accepted_recovery import Program,FATES,MOMENTS
from suites.frontend.bpu.bpu.coverage.main_accepted_recovery import Coverage
from suites.frontend.bpu.bpu.case.main_accepted_recovery import check_accepted_recovery


@pytest.mark.feature('BPU-INT-005')
@pytest.mark.feature('BPU-INT-093')
@pytest.mark.parametrize('fate',FATES)
@pytest.mark.parametrize('moment',MOMENTS)
async def test_already_accepted_learning_survives_later_prediction_recovery(bpu_agent,request,fate,moment):
    p=Program(fate,moment);evidence=dict(program=p.state(),status='INCOMPLETE')
    try:await check_accepted_recovery(bpu_agent,p,Coverage(p),evidence)
    finally:request.node.user_properties.append(('semantic_main_accepted_recovery',json.dumps(evidence,sort_keys=True)))
