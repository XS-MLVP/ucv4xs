"""L2TlbPrefetch leaf UT."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution
from suites.memblock.mmu.l2.l2pf import next_line


# L2PF-01, L2PF-02
async def test_prefetch_next_line_and_history_suppression(l2pf_env):
    env = l2pf_env
    async with execution(env):
        await env.reset()
        env.set_context(virt=0, vsatp_mode=0, hgatp_mode=0)
        vpn = 0x8000
        await env.cycle(in_valid=1, in_vpn=vpn, out_ready=0)
        assert env.read(env.out_valid) == 1
        assert env.read(env.out_vpn) == next_line(vpn)
        await env.cycle(out_ready=1)
        # Same request's next line is now in history; it is suppressed.
        await env.cycle(in_valid=1, in_vpn=vpn, out_ready=0)
        assert env.read(env.out_valid) == 0
        if env.coverage is not None:
            env.coverage.pf.sample({"event": "suppressed", "s2xlate": 0,
                                    "next_line": "normal"}, details=False)
        # A different input is still prefetched.
        await env.cycle(in_valid=1, in_vpn=vpn + 8, out_ready=0)
        assert env.read(env.out_valid) == 1
        assert env.read(env.out_vpn) == next_line(vpn + 8)


# L2PF-03
async def test_prefetch_flush_and_s2xlate_classes(l2pf_env):
    env = l2pf_env
    async with execution(env):
        await env.reset()
        for virt, vs, hg, expect in (
            (0, 8, 8, 0), (1, 8, 0, 1), (1, 0, 8, 2), (1, 8, 8, 3)
        ):
            env.set_context(virt=virt, vsatp_mode=vs, hgatp_mode=hg)
            await env.cycle(in_valid=1, in_vpn=0x9000, out_ready=0)
            assert env.read(env.out_s2) == expect
            await env.cycle(out_ready=1, flush=1)
            assert env.read(env.out_valid) == 0


# L2PF-04: next-line addition wraps at the VPN high bit.
async def test_prefetch_next_line_wrap(l2pf_env):
    env = l2pf_env
    async with execution(env):
        await env.reset()
        env.set_context()
        vpn = ((1 << 35) - 1) << 3
        await env.cycle(in_valid=1, in_vpn=vpn, out_ready=0)
        assert env.read(env.out_vpn) == 0
        if env.coverage is not None:
            env.coverage.pf.sample({"event": "issue", "s2xlate": 0,
                                    "next_line": "wrap"}, details=False)


# L2PF-05: consume four prefetches so all history slots and the index wrap are
# exercised.
async def test_prefetch_history_all_slots_and_index_wrap(l2pf_env):
    env = l2pf_env
    async with execution(env):
        await env.reset()
        env.set_context()
        for index in range(4):
            vpn = 0xA000 + index * 8
            await env.cycle(in_valid=1, in_vpn=vpn, out_ready=0)
            assert env.read(env.out_vpn) == next_line(vpn)
            await env.cycle(out_ready=1)
        for index in range(4):
            vpn = 0xA000 + index * 8
            await env.cycle(in_valid=1, in_vpn=vpn, out_ready=0)
            assert env.read(env.out_valid) == 0
            await env.cycle(out_ready=1)


# L2PF-06: CSR mode/change and input VPN bits are exercised in both directions.
async def test_prefetch_input_and_csr_bits_toggle(l2pf_env):
    env = l2pf_env
    async with execution(env):
        await env.reset()
        # Toggle the changed bits with an empty history; they are an
        # independent flush source and do not affect a pending entry here.
        for signal in env.csr.values():
            signal.Set(1)
        await env.edge()
        for signal in env.csr.values():
            signal.Set(0)
        await env.edge()
        env.set_context(virt=1, vsatp_mode=0xF, hgatp_mode=0xF)
        await env.cycle(in_valid=1, in_vpn=(1 << 38) - 1, out_ready=0)
        assert env.read(env.out_valid) == 1
        assert env.read(env.out_vpn) == 0
        assert env.read(env.out_s2) == 3
        await env.cycle(out_ready=1, flush=1)
        await env.cycle(out_ready=1)
        env.set_context(virt=0, vsatp_mode=0, hgatp_mode=0)
        await env.cycle(in_valid=1, in_vpn=0, out_ready=1)


# L2PF-07: high output/history VPN bits toggle through varied next lines.
async def test_prefetch_output_and_history_high_bits(l2pf_env):
    env = l2pf_env
    async with execution(env):
        await env.reset()
        env.set_context()
        patterns = [
            0, (1 << 38) - 1, 0x2AAAAAAAAA, 0x1555555555,
            (1 << 38) - 1, 0, 0x1555555555, 0x2AAAAAAAAA,
        ]
        for vpn in patterns:
            await env.cycle(in_valid=1, in_vpn=vpn, out_ready=0)
            await env.cycle(out_ready=1)
        # Toggle the flush source explicitly in both directions.
        env.sfence.Set(1)
        await env.edge()
        env.sfence.Set(0)
        await env.edge()
