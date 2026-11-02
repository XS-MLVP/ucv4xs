"""Event counts follow accepted metadata and fire, never a held/live offer."""
import pytest

from suites.frontend.ifu.ifu.types import FetchRequest, Frame, ProducerFetchRequest
from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.isa import jal

pytestmark = pytest.mark.feature('IFU-TOP-012')


@pytest.mark.parametrize('hit0,hit1,double', [(a, b, d) for a in (0, 1) for b in (0, 1) for d in (0, 1)])
async def test_registered_counts_use_the_accepted_fetch_and_fire_once_after_backpressure(ifu_agent, hit0, hit1, double):
    pc = 0x90020 if double else 0x90000
    item = ProducerFetchRequest(build_window([(c_addi(9, 1), 1)] * 32, pc), physical_address=pc)
    accepted = await ifu_agent.cycle(Frame(request=item, ibuffer_ready=0,
                                         cache_hits=(hit0, hit1), double_line=double))
    assert accepted.accepted_uid is not None
    # Pipeline movement and release see opposite *live* metadata. Events must
    # retain the accepted request's inputs, not pick up these unrelated values.
    controls = Frame(ibuffer_ready=0, cache_hits=(1 - hit0, 1 - hit1), double_line=1 - double)
    held = [await ifu_agent.cycle(controls) for _ in range(4)]
    assert held[-1].after.beat is not None and ifu_agent.beat_fires == 0
    assert all(row.after.performance == (0,) * 13 for row in held)
    release = Frame(cache_hits=controls.cache_hits, double_line=controls.double_line)
    tail = [await ifu_agent.cycle(release) for _ in range(6)]
    # Fixed truth-table answer here does not call the production event model.
    expected = (0, 1, int(not (hit0 and (not double or hit1))), 1, double,
                hit0, double & hit1, (1 - double) & hit0, (1 - double) & (1 - hit0),
                double & hit0 & hit1, double & hit0 & (1 - hit1),
                double & (1 - hit0) & hit1, double & (1 - hit0) & (1 - hit1))
    assert [row.after.performance for row in tail] == [(0,) * 13, expected] + [(0,) * 13] * 4
    assert ifu_agent.beat_fires == 1 and ifu_agent.records[-1].state == 'completed'


async def test_registered_frontend_flush_counts_the_checker_redirect_not_the_live_request(ifu_agent):
    item = FetchRequest(build_window([(jal(1, 0x40), 0)], 0xa000))
    rows = [await ifu_agent.cycle(Frame(request=item))]
    rows += [await ifu_agent.cycle() for _ in range(9)]
    assert ifu_agent.redirects == ifu_agent.beat_fires == 1
    assert sum(row.after.performance[0] for row in rows) == 1
    assert sum(row.after.performance[1] for row in rows) == 1
