"""Pure source-fixture checks; NOT native LSQ functional/coverage evidence."""
import pytest
from .sources import SourceJobs


@pytest.mark.parametrize("kind",("cache","tlb"))
def test_external_jobs_keep_refused_miss_merge_and_repay_before_tag_reuse(kind):
    pool=SourceJobs(kind)
    for key in range(16):
        reply=pool.request(key,1+key,0,wanted=True)
        assert reply==dict(miss=True,full=False,identity=key,job=key+1)
    assert pool.request(99,99,1,wanted=True)==dict(miss=True,full=True,identity=0,job=None)
    assert pool.request(3,30,1)==dict(miss=True,full=False,identity=3,job=4)
    pool.return_actual(3,2)
    # No re-draw of the sampled miss after a full rejection.
    assert pool.request(99,99,3)==dict(miss=True,full=False,identity=3,job=17)
    assert pool.history[3]["UIDs"]==[4,30]
    assert pool.history[3]["returned_edge"]==2
    assert pool.history[-1]["returned_edge"] is None
    pool.return_actual(3,4)
    assert pool.request(99,100,5)==dict(miss=False,full=False,identity=0,job=None)
