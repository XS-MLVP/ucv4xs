"""Toggle-directed legal stimulus for TLBFA state and public inputs."""
from __future__ import annotations

from mmuverify.common.runtime import execution
from mmuverify.tlbfa.model import ALL_STAGE, NO_S2

from .common import lookup_vpn, make_refill

ALL_ONES = (1 << 50) - 1


# TLBFA-COMBO-01: every storage bit in every way must be exercised in both
# directions. The all-ones payload is intentionally outside the normal PTW
# response distribution; it is a legal interface stimulus for storage testing.
async def test_all_storage_bits_toggle_in_every_way(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        ones = make_refill(
            ALL_STAGE,
            3,
            (1 << 35) - 1,
            (1 << 41) - 1,
            n=1,
            asid=(1 << 16) - 1,
            vmid=(1 << 14) - 1,
            perm_g=1,
            valididx=(1,) * 8,
            pteidx=(1,) * 8,
            ppn_low=(7,) * 8,
            s1_pf=1,
            s1_af=1,
            s2_gpf=1,
            s2_gaf=1,
            pbmt=3,
            g_pbmt=3,
            s2_tag=(1 << 38) - 1,
            s2_ppn=(1 << 38) - 1,
            s1_perm_r=1,
            s1_perm_w=1,
            s1_perm_x=1,
            s2_perm_a=1,
            s2_perm_x=1,
            s1_perm_a=1,
            s1_perm_u=1,
        )
        zeros = make_refill(
            NO_S2,
            0,
            0,
            0,
            valididx=(0,) * 8,
            pteidx=(0,) * 8,
            ppn_low=(0,) * 8,
            s1_perm_r=0,
            s1_perm_w=0,
            s1_perm_x=0,
            s2_perm_a=0,
            s2_perm_x=0,
            s1_perm_a=0,
            s1_perm_u=0,
            s1_v=0,
        )
        for way in range(48):
            await env.refill(ones, way, f"ones way {way}")
        # Reset clears validity but deliberately leaves the payload registers
        # intact; this is the 1->0 edge for the valid bits.
        await env.reset("with_valid_entries")
        for way in range(48):
            await env.refill(zeros, way, f"zeros way {way}")
        await env.settle(2)


# TLBFA-HIT-02: VPN and stage bits in the request path toggle, with a model
# check on every access.
async def test_request_vpn_and_stage_bits_toggle(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        entry = make_refill(NO_S2, 0, 0x31000, 0x111111111, asid=0)
        await env.refill(entry, 0, "toggle anchor")
        for vpn in (0, 0x3FFFFFFFFF, 0x1555555555, 0x2AAAAAAAAAA, 0x1):
            snap = await env.lookup(vpn, NO_S2, f"vpn {vpn:#x}")
            assert snap.hit == (1 if vpn == lookup_vpn(NO_S2, 0x31000) else 0)
        for stage in (NO_S2, 1, 2, ALL_STAGE, ALL_STAGE, NO_S2):
            await env.lookup(lookup_vpn(NO_S2, 0x31000), stage, f"stage {stage}")


# TLBFA-CTX-01: CSR context bits are all exercised.
async def test_context_input_bits_toggle(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        await env.edge()
        env.program_context(satp_asid=0xFFFF, vsatp_asid=0xFFFF, hgatp_vmid=0x3FFF, virt=1, bme=1, cmode=1)
        env.drive_raw_csr(hgatp_vmid=0xFFFF)
        await env.edge()
        assert env.read(env.csr["satp_asid"]) == 0xFFFF
        assert env.read(env.csr["vsatp_asid"]) == 0xFFFF
        assert env.read(env.csr["hgatp_vmid"]) == 0xFFFF
        env.program_context(satp_asid=0, vsatp_asid=0, hgatp_vmid=0, virt=0, bme=0, cmode=0)
        await env.edge()


# TLBFA-SFENCE-03: sfence address/id bits are exercised by legal address-only
# fences that must not match the installed translation.
async def test_sfence_address_and_asid_bits_toggle(tlbfa_env):
    env = tlbfa_env
    async with execution(env.dut):
        await env.reset()
        env.program_context(satp_asid=1)
        anchor = make_refill(NO_S2, 0, 0x32000, 0x222222222, asid=1)
        await env.refill(anchor, 0, "anchor")
        hit_vpn = lookup_vpn(NO_S2, 0x32000)
        cases = [
            (0, 0),
            (ALL_ONES, 0xFFFF),
            (0x2AAAAAAAAAAA, 0x5555),
            (0, 0),
        ]
        for addr, sfence_id in cases:
            await env.fence("addr_asid", 0, 0, addr, sfence_id, note="input bits")
            snap = await env.lookup(hit_vpn, NO_S2, "anchor survives non-matching fence")
            assert snap.hit == 1
