"""Local reset kills old Load, NOT its accepted external NC request."""
import pytest
from .owners import RetainedUncacheProgram


@pytest.mark.parametrize("phase",("empty_after_reset","new_mid_wait_response","new_response_wait_bypass","new_bypass_s1"))
@pytest.mark.parametrize("lane",range(3))
async def test_local_reset_retains_old_SID_job_real_return_and_same_LQ_slot_new_UID_completion(lsq,phase,lane):
    trace=RetainedUncacheProgram(lsq,lane,phase)
    try:await trace.run()
    except BaseException as exc:
        trace.write(False,repr(exc));raise
    trace.write(True)
