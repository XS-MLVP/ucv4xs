
import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.deq.types import Store


@pytest.mark.parametrize("denied,corrupt", ((True, False), (False, True), (True, True)))
async def test_delayed_writeback_fire_consumes_original_cache_error(deq, denied, corrupt):
    """Check the actual ready/valid transfer, not just stability during stall."""
    env = deq
    store = Store(vaddr=0x12340, page=0xABC, byte_mask=0xF, data=0x11223344,
                  data_valid=True, address_valid=True, committed=True, cache_operation=True, cbo=0)
    env.begin(("DEQ-EXCEPTION.held",))
    await env.cycle(stores=(store, Store()), sbuffer_empty=True)
    await env.cycle()
    env.expect({P.p_toDCache_req_valid: 1}, "CBO requests cache after real drain")
    await env.cycle(cache_ready=True)
    env.expect({P.p_toDCache_resp_ready: 1}, "cache request actually accepted")
    await env.cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt, writeback_ready=False)
    env.expect({P.p_writeBack_valid: 1, P.p_writeBack_bits_exceptionVec_7: int(denied),
                P.p_writeBack_bits_exceptionVec_19: int(corrupt)}, "accepted Cache response has its original errors")
    await env.cycle(cache_response=False, cache_denied=False, cache_corrupt=False)
    env.expect({P.p_writeBack_valid: 1}, "writeback still pending while ready is low")
    await env.cycle(writeback_ready=True)
    env.expect({P.p_writeBack_valid: 1, P.p_rdataPtrMoveCnt: 1, P.p_writeBack_bits_exceptionVec_7: int(denied),
                P.p_writeBack_bits_exceptionVec_19: int(corrupt)}, "actual ready/valid fire must consume original response errors", before=True)
    await env.cycle(stores=(Store(), Store()))
    env.finish(("DEQ-EXCEPTION.held",))
