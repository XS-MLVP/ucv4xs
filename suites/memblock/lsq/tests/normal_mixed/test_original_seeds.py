"""No reduced-type replacement: original eight seeds,600 random and fair drain."""
import pytest
from .owners import NormalProducerMixedOwners


@pytest.mark.parametrize("seed",range(0x7100,0x7108))
async def test_normal_producer_original_eight_types_weights_seeds_external_jobs_and_fair(lsq,seed):
    trace=NormalProducerMixedOwners(lsq,seed)
    try:await trace.run(cycles=600)
    except BaseException as exc:
        trace.write_report(False,repr(exc));raise
    trace.write_report(True)
