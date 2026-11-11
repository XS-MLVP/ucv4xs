"""One walk's cumulative history cannot satisfy the next walk's completion."""
from suites.memblock.mmu.testbenches.shared.env.execution import execution


async def test_handoff_then_response_reuses_vpn_but_not_request_identity(ptw_env):
    env=ptw_env
    async with execution(env):
        await env.reset()
        env.set_csr(satp_mode=8,satp_ppn=0x80000)
        await env.edge()
        vpn=0x12345
        env.memory.build_sv39(0x80000,vpn,0xABC)
        await env.issue(vpn,source=1)
        assert await env.wait_response(note='first LLPTW handoff') is None
        assert len(env.llptw_requests)==1

        # Change only the independent page-table memory and caller source.
        # Keep the old handoff journal to expose accidental cumulative matching.
        env.memory.build_sv39(0x80000,vpn,0x40000,level=2)
        await env.issue(vpn,source=3)
        response=await env.wait_response(note='new root leaf')
        assert response is not None
        assert response['source']==3 and response['0_v']==1
        assert response['0_pf']==0 and response['0_af']==0
        assert response['0_ppn']==0x40000>>3 and response['0_level']==2
        assert [(c.request.source,c.kind) for c in env.walk_completions]==[
            (1,'llptw'),(3,'response')]
