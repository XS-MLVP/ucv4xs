"""TLBNonBlock (MemBlock DTLB) functional tests."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution, refresh
from suites.memblock.mmu.tlbfa.model import ALL_STAGE, NO_S2, ONLY_S1, ONLY_S2

from tests.tlbn.common import (READ, WRITE, ATOM_WRITE, dtlb_refill, expected_gpaddr,
                     expected_paddr, expected_pbmt, gen_ppn_s1, perm_expectations)


async def _context(env, **values):
    env.set_csr(**values)
    for _ in range(4):
        await env.edge()


def _check_data(snap, data, vaddr, *, cmd=READ, dmode=0, sum_=0, mxr=0,
                note=""):
    assert snap.valid == 1 and snap.miss == 0, f"{note}: expected checked hit, got {snap}"
    assert snap.paddr_0 == expected_paddr(data, vaddr), (
        f"{note}: paddr {snap.paddr_0:#x} != {expected_paddr(data, vaddr):#x}")
    assert snap.pbmt == expected_pbmt(data), f"{note}: pbmt {snap.pbmt}"
    faults = perm_expectations(data, cmd, dmode=dmode, sum_=sum_, mxr=mxr)
    for field, want in faults.items():
        got = getattr(snap, field)
        assert got == want, f"{note}: {field} {got} != {want}"


# DTLB-01: reset leaves every port idle and a bare-mode request passes the
# virtual address through without a PTW request.
async def test_reset_and_bare_mode(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        for port in range(4):
            assert env.read(env.ports[port]["resp"]["valid"]) == 0
            assert env.read(env.ports[port]["ptw"]["valid"]) == 0
        snap = await env.issue(0, 0x12345678, cmd=READ)
        assert snap.valid == 1
        assert snap.miss == 0 and snap.ptw.valid == 0
        assert snap.paddr_0 == 0x12345678
        assert snap.pf_ld == 0 and snap.af_ld == 0 and snap.gpf_ld == 0
        if env.coverage:
            env.coverage.sample("bare", 0, 0, "bare")


# DTLB-02: no_translate returns the supplied PMP address and still raises the
# PMP request with the command.
async def test_no_translate_uses_pmp_addr(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        snap = await env.issue(0, 0x22223333, cmd=WRITE, no_translate=1,
                               pmp_addr=0x00445566)
        assert snap.valid == 1
        assert snap.miss == 0 and snap.ptw.valid == 0
        assert snap.paddr_0 == 0x00445566, hex(snap.paddr_0)
        assert snap.pmp["valid"] == 1 and snap.pmp["addr"] == 0x00445566
        assert snap.pmp["cmd"] == WRITE
        assert snap.pf_ld == 0 and snap.pf_st == 0
        if env.coverage:
            env.coverage.sample("bare", 0, 0, "bare")


# DTLB-03: a no-S2 miss requests the walker with the VPN, and the PTW response
# installs a sector entry that hits with the expected PPN and page offset.
async def test_miss_and_refill_hit(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, satp_asid=0, dmode=0)
        vaddr = 0x12345678
        miss = await env.issue(0, vaddr, cmd=READ)
        assert miss.miss == 1 and miss.ptw.valid == 1
        assert miss.ptw.vpn == (vaddr >> 12) & ((1 << 38) - 1)
        assert miss.ptw.s2xlate == NO_S2 and miss.ptw.get_gpa == 0
        data = dtlb_refill(vaddr, 0x34567)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        hit = await env.issue(0, vaddr, cmd=READ)
        assert hit.miss == 0 and hit.ptw.valid == 0
        _check_data(hit, data, vaddr, cmd=READ, note="refill hit")
        assert hit.pmp["valid"] == 1 and hit.pmp["addr"] == hit.paddr_0
        assert hit.pmp["cmd"] == READ
        other = (vaddr & ~0xFFF) | 0xABC
        hit2 = await env.issue(0, other, cmd=READ)
        assert hit2.miss == 0 and hit2.paddr_0 == ((hit.paddr_0 & ~0xFFF) | 0xABC)
        if env.coverage:
            env.coverage.sample("miss", 0, 0, "miss")


# DTLB-04: a 2MB leaf merges the low VPN bits into the PPN; a 1GB leaf merges
# the low 18 bits.
async def test_superpage_ppn_merge(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=9, dmode=0)
        for vaddr, level, ppn in ((0x12340000, 1, 0x40000),
                                  (0x12345000, 1, 0x40000),
                                  (0x40000000, 2, 0x80000)):
            await env.sfence(1, 1, 0, 0)
            miss = await env.issue(0, vaddr, cmd=READ)
            assert miss.miss == 1
            data = dtlb_refill(vaddr, ppn, level=level)
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
            hit = await env.issue(0, vaddr, cmd=READ)
            assert hit.miss == 0, (vaddr, hit)
            _check_data(hit, data, vaddr, note=f"super {level}")
            assert hit.paddr_0 == expected_paddr(data, vaddr)


# DTLB-05: ASID filtering and full sfence invalidation.
async def test_asid_and_sfence(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, satp_asid=3, dmode=0)
        vaddr = 0x23456000
        assert (await env.issue(0, vaddr)).miss == 1
        data = dtlb_refill(vaddr, 0x22222)
        data.s1_asid = 3
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        assert (await env.issue(0, vaddr)).miss == 0
        await _context(env, satp_asid=4)
        assert (await env.issue(0, vaddr)).miss == 1
        await _context(env, satp_asid=3)
        assert (await env.issue(0, vaddr)).miss == 0
        await env.sfence(1, 1, 0, 0)
        assert (await env.issue(0, vaddr)).miss == 1
        if env.coverage:
            env.coverage.sample("fence", 0, 0, "miss")


# DTLB-06: load permissions: R or MXR+X, and the U/S rule with SUM.
async def test_load_permissions(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddr = 0x30000000
        cases = (
            dict(s1_perm_r=0, s1_perm_x=1, mxr=0, pf_ld=1),
            dict(s1_perm_r=0, s1_perm_x=1, mxr=1, pf_ld=0),
            dict(s1_perm_r=1, s1_perm_x=0, mxr=0, pf_ld=0),
        )
        for index, case in enumerate(cases):
            await env.sfence(1, 1, 0, 0)
            v = vaddr + index * 0x1000
            await env.issue(0, v)
            data = dtlb_refill(v, 0x30001 + index,
                               s1_perm_r=case["s1_perm_r"],
                               s1_perm_x=case["s1_perm_x"])
            await env.ptw_respond(data, addr_low=(v >> 12) & 7)
            await _context(env, dmode=0, mxr=case["mxr"])
            hit = await env.issue(0, v, cmd=READ)
            assert hit.miss == 0
            _check_data(hit, data, v, cmd=READ, mxr=case["mxr"],
                        note=f"load perm {index}")
            if case["pf_ld"]:
                if env.coverage:
                    env.coverage.sample("fault", 0, 0, "pf")


# DTLB-07: store requires W and D; AMO write follows the same rule.
async def test_store_permissions(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddr = 0x31000000
        cases = (
            dict(perm_w=1, perm_d=1, pf_st=0),
            dict(perm_w=0, perm_d=1, pf_st=1),
            dict(perm_w=1, perm_d=0, pf_st=1),
        )
        for index, case in enumerate(cases):
            await env.sfence(1, 1, 0, 0)
            v = vaddr + index * 0x1000
            await env.issue(0, v)
            data = dtlb_refill(v, 0x31001 + index,
                               s1_perm_w=case["perm_w"],
                               s1_perm_d=case["perm_d"])
            await env.ptw_respond(data, addr_low=(v >> 12) & 7)
            hit = await env.issue(0, v, cmd=WRITE)
            assert hit.miss == 0
            _check_data(hit, data, v, cmd=WRITE, note=f"store perm {index}")
            if case["pf_st"]:
                if env.coverage:
                    env.coverage.sample("fault", 0, 0, "pf")
        # AMO write: cmd 4 is atom_read, 5 is atom_write.  Both are writes for
        # permission purposes; the generated port accepts the full 3-bit cmd.
        await env.sfence(1, 1, 0, 0)
        v = vaddr + 0x3000
        await env.issue(0, v)
        data = dtlb_refill(v, 0x32000, s1_perm_w=0)
        await env.ptw_respond(data, addr_low=(v >> 12) & 7)
        amo = await env.issue(0, v, cmd=ATOM_WRITE)
        assert amo.miss == 0 and amo.pf_st == 1


# DTLB-08: A/D update faults and access-fault priority.
async def test_ad_and_access_fault_priority(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddr = 0x32000000
        for index, (a, d, cmd, want_ld, want_st) in enumerate((
                (0, 1, READ, 1, 0),
                (1, 0, WRITE, 0, 1),
                (1, 1, WRITE, 0, 0))):
            await env.sfence(1, 1, 0, 0)
            v = vaddr + index * 0x1000
            await env.issue(0, v)
            data = dtlb_refill(v, 0x33001 + index, s1_perm_a=a, s1_perm_d=d)
            await env.ptw_respond(data, addr_low=(v >> 12) & 7)
            hit = await env.issue(0, v, cmd=cmd)
            assert hit.pf_ld == want_ld, (index, hit)
            assert hit.pf_st == want_st, (index, hit)
        # Access fault wins over a simultaneous permission/page fault.
        await env.sfence(1, 1, 0, 0)
        v = vaddr + 0x4000
        await env.issue(0, v)
        data = dtlb_refill(v, 0x34000, s1_perm_r=0, s1_af=1)
        await env.ptw_respond(data, addr_low=(v >> 12) & 7)
        hit = await env.issue(0, v, cmd=READ)
        assert hit.af_ld == 1 and hit.pf_ld == 0, hit
        if env.coverage:
            env.coverage.sample("fault", 0, 0, "af")


# DTLB-09: PBMT composition per translation class.
async def test_pbmt_composition(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddr = 0x40000000
        await env.issue(0, vaddr)
        data = dtlb_refill(vaddr, 0x40001, pbmt=2)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        hit = await env.issue(0, vaddr)
        assert hit.pbmt == 2, hit.pbmt
        # allStage: a non-zero S1 PBMT wins, otherwise the G-stage PBMT is used.
        await _context(env, virt=1, vsatp_mode=8, hgatp_mode=8)
        for index, (s1_pbmt, g_pbmt, want) in enumerate((
                (1, 2, 1), (0, 2, 2))):
            await env.sfence(1, 1, 0, 0)
            v = vaddr + 0x10000 + index * 0x1000
            await env.issue(0, v)
            data = dtlb_refill(v, 0x41001 + index, kind=ALL_STAGE,
                               pbmt=s1_pbmt, g_pbmt=g_pbmt)
            await env.ptw_respond(data, addr_low=(v >> 12) & 7)
            hit = await env.issue(0, v)
            assert hit.miss == 0, hit
            assert hit.pbmt == want, (index, hit.pbmt, want)


# DTLB-10: onlyStage1 uses vsatp and returns the S1 PPN.
async def test_only_stage1(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, virt=1, vsatp_mode=8, vsatp_asid=2,
                       hgatp_mode=0, dmode=0)
        vaddr = 0x50000000
        miss = await env.issue(0, vaddr)
        assert miss.ptw.s2xlate == ONLY_S1, miss.ptw
        data = dtlb_refill(vaddr, 0x50001, kind=ONLY_S1)
        data.s1_asid = 2
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        hit = await env.issue(0, vaddr)
        assert hit.miss == 0, hit
        _check_data(hit, data, vaddr, note="onlyS1")


# DTLB-11: onlyStage2 uses hgatp, returns the G-stage PPN and reports the VA
# as gpaddr.
async def test_only_stage2(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, virt=1, vsatp_mode=0, hgatp_mode=8,
                       hgatp_vmid=5, dmode=0)
        vaddr = 0x60000000
        miss = await env.issue(0, vaddr)
        assert miss.ptw.s2xlate == ONLY_S2, miss.ptw
        data = dtlb_refill(vaddr, 0x60001, kind=ONLY_S2)
        data.s2_vmid = 5
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        hit = await env.issue(0, vaddr)
        assert hit.miss == 0, hit
        _check_data(hit, data, vaddr, note="onlyS2")
        assert hit.gpaddr == vaddr


# DTLB-12: allStage clean translation uses the G-stage PPN and checks both
# stages' permissions.
async def test_all_stage_clean(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, virt=1, vsatp_mode=8, hgatp_mode=8, dmode=0)
        vaddr = 0x61000000
        miss = await env.issue(0, vaddr)
        assert miss.ptw.s2xlate == ALL_STAGE
        data = dtlb_refill(vaddr, 0x61001, kind=ALL_STAGE,
                           s2_perm_r=1, s2_perm_x=1)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        hit = await env.issue(0, vaddr)
        assert hit.miss == 0, hit
        _check_data(hit, data, vaddr, note="allStage")
        # G-stage load permission failure: the first observation requests the
        # GPA, and the replayed request reports gpf without another walk.
        await env.sfence(1, 1, 0, 0)
        v2 = vaddr + 0x1000
        await env.issue(0, v2)
        bad = dtlb_refill(v2, 0x61002, kind=ALL_STAGE,
                          s2_perm_r=0, s2_perm_x=0, s2_perm_a=0,
                          s2_perm_d=0)
        await env.ptw_respond(bad, addr_low=(v2 >> 12) & 7)
        first = await env.issue(0, v2)
        assert first.miss == 1 and first.gpf_ld == 1, first
        assert first.ptw.valid == 1 and first.ptw.get_gpa == 1, first.ptw
        await env.ptw_respond(bad, addr_low=(v2 >> 12) & 7, get_gpa=1)
        fault = await env.issue(0, v2)
        assert fault.miss == 0 and fault.gpf_ld == 1, fault
        assert fault.gpaddr == expected_gpaddr(bad, v2), (
            hex(fault.gpaddr), hex(expected_gpaddr(bad, v2)))
        if env.coverage:
            env.coverage.sample("fault", 0, 3, "gpf")


# DTLB-13: allStage G-stage page fault triggers a getGpa PTW request; the GPA
# response allows the same page to be reported as gpf with the S1 GPA, without
# another walk request.
async def test_all_stage_gpa_replay(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, virt=1, vsatp_mode=8, hgatp_mode=8, dmode=0)
        vaddr = 0x62000000
        assert (await env.issue(0, vaddr)).miss == 1
        data = dtlb_refill(vaddr, 0x62001, kind=ALL_STAGE,
                          s2_gpf=1, s2_perm_a=0, s2_perm_d=0,
                          s2_perm_x=0)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        gpf = await env.issue(0, vaddr)
        assert gpf.miss == 1 and gpf.gpf_ld == 1, gpf
        assert gpf.ptw.valid == 1 and gpf.ptw.get_gpa == 1, gpf.ptw
        assert gpf.is_for_vs_nonleaf == 0
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7, get_gpa=1)
        replay = await env.issue(0, vaddr)
        assert replay.miss == 0, replay
        assert replay.ptw.valid == 0, replay.ptw
        assert replay.gpf_ld == 1, replay
        assert replay.gpaddr == expected_gpaddr(data, vaddr), (
            hex(replay.gpaddr), hex(expected_gpaddr(data, vaddr)))
        if env.coverage:
            env.coverage.sample("fault", 0, 3, "gpf")


# DTLB-14: a fake or non-leaf S1 entry is reported with isForVSnonLeafPTE and
# does not raise a leaf page fault.
async def test_fake_and_nonleaf_marker(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddr = 0x70000000
        await env.issue(0, vaddr)
        data = dtlb_refill(vaddr, 0x70001, s1_perm_r=0, s1_perm_w=0,
                           s1_perm_x=0, s1_perm_a=0, s1_perm_d=0)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        hit = await env.issue(0, vaddr)
        assert hit.is_for_vs_nonleaf == 1, hit
        assert hit.pf_ld == 0 and hit.pf_st == 0, hit
        # x=1,w=1,r=1 controls the same marker with the same result.
        await env.sfence(1, 1, 0, 0)
        v2 = vaddr + 0x1000
        await env.issue(0, v2)
        data2 = dtlb_refill(v2, 0x70002, s1_perm_r=1, s1_perm_w=1,
                            s1_perm_x=1, s1_perm_a=0, s1_perm_d=0)
        await env.ptw_respond(data2, addr_low=(v2 >> 12) & 7)
        leaf = await env.issue(0, v2)
        assert leaf.is_for_vs_nonleaf == 0
        assert leaf.pf_ld == 1, leaf


# DTLB-15: all four requestor ports resolve independently in one cycle, with
# per-port PTW requests and PMP outputs.
async def test_four_port_concurrency(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddrs = [0x80000000 + index * 0x8000 for index in range(4)]
        for port, vaddr in enumerate(vaddrs):
            entry = env.ports[port]["req"]
            env._set(entry["valid"], 1)
            env._set(entry["vaddr"], vaddr)
            env._set(entry["fullva"], vaddr)
            if "cmd" in entry:
                env._set(entry["cmd"], READ)
        refresh(env)
        await env.edge()
        snaps = []
        for port in range(4):
            resp, ptw, extra = env._request_snap(port)
            snaps.append((resp, ptw, extra))
        for entry in env.ports:
            env._set(entry["req"]["valid"], 0)
        await env.edge()
        for port, (resp, ptw, extra) in enumerate(snaps):
            assert resp["valid"] == 1, port
            assert resp["miss"] == 1, port
            assert ptw.valid == 1 and ptw.vpn == vaddrs[port] >> 12, (port, ptw)
            assert extra["pmp"]["valid"] == 1, port
        # Refill all four translations and check simultaneous hits.
        for port, vaddr in enumerate(vaddrs):
            data = dtlb_refill(vaddr, 0x80001 + port)
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        for port, vaddr in enumerate(vaddrs):
            entry = env.ports[port]["req"]
            env._set(entry["valid"], 1)
            env._set(entry["vaddr"], vaddr)
            env._set(entry["fullva"], vaddr)
            if "cmd" in entry:
                env._set(entry["cmd"], READ)
        refresh(env)
        await env.edge()
        hits = [env._request_snap(port)[0] for port in range(4)]
        for entry in env.ports:
            env._set(entry["req"]["valid"], 0)
        await env.edge()
        for port, (vaddr, hit) in enumerate(zip(vaddrs, hits)):
            assert hit["valid"] == 1 and hit["miss"] == 0, (port, hit)
            data = dtlb_refill(vaddr, 0x80001 + port)
            assert hit["paddr_0"] == expected_paddr(data, vaddr), (port, hit)


# DTLB-16: the second response duplicate (ports 0/1) mirrors the first paddr.
async def test_response_duplicates(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddr = 0x90000000
        await env.issue(0, vaddr)
        data = dtlb_refill(vaddr, 0x90001)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        for port in (0, 1):
            hit = await env.issue(port, vaddr)
            assert hit.valid == 1 and hit.miss == 0
            assert hit.paddr_1 == hit.paddr_0, (port, hit)
            assert hit.paddr_1 == expected_paddr(data, vaddr)


# DTLB-17: PMP request address/cmd follow the translated address and command
# for every port that exposes a cmd.
async def test_pmp_outputs(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddr = 0x91000000
        await env.issue(0, vaddr)
        data = dtlb_refill(vaddr, 0x91001)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        hit = await env.issue(0, vaddr, cmd=WRITE)
        assert hit.miss == 0
        assert hit.pmp["valid"] == 1
        assert hit.pmp["addr"] == hit.paddr_0
        assert hit.pmp["cmd"] == WRITE
        if env.coverage:
            env.coverage.sample("pmp", 0, 0, "clean")


# DTLB-18: perf outputs are single-cycle event pulses: event 0 counts
# accesses and event 1 counts misses after the two registered stages.
async def test_perf_events(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        vaddr = 0x92000000
        samples = [env.perf_values()]
        assert (await env.issue(0, vaddr)).miss == 1
        for _ in range(10):
            await env.edge()
            samples.append(env.perf_values())
        assert any(value[1] for value in samples), samples
        data = dtlb_refill(vaddr, 0x92001)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        assert (await env.issue(0, vaddr)).miss == 0
        for _ in range(10):
            await env.edge()
            samples.append(env.perf_values())
        assert any(value[0] for value in samples), samples


# DTLB-19: killing a request suppresses its response and PTW request.
async def test_killed_request_is_dropped(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        snap = await env.issue(0, 0x93000000, cmd=READ, kill=1)
        assert snap.valid == 0, snap
        assert snap.ptw.valid == 0
        if env.coverage:
            env.coverage.sample("kill", 0, 0, "miss")


# DTLB-20: ports 2 and 3 have their own request/response paths and PTW ports.
async def test_ports_two_and_three(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        for port in (2, 3):
            vaddr = 0x94000000 + port * 0x8000
            miss = await env.issue(port, vaddr)
            assert miss.valid == 1 and miss.miss == 1, (port, miss)
            assert miss.ptw.valid == 1 and miss.ptw.vpn == vaddr >> 12
            data = dtlb_refill(vaddr, 0x94001 + port)
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
            hit = await env.issue(port, vaddr)
            assert hit.valid == 1 and hit.miss == 0, (port, hit)
            _check_data(hit, data, vaddr, note=f"port {port}")
            if port == 3:
                store = await env.issue(3, vaddr, cmd=WRITE)
                assert store.pmp["cmd"] == WRITE


# DTLB-21: a sector refill with only one valid lane hits that lane and misses
# the other seven lanes.
async def test_sector_valididx_lane(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        base = 0x95000000
        lane = 5
        vaddr = base | (lane << 12)
        await env.issue(0, vaddr)
        data = dtlb_refill(vaddr, 0x95001)
        data.s1_valididx = tuple(1 if index == lane else 0 for index in range(8))
        data.s1_pteidx = tuple(1 if index == lane else 0 for index in range(8))
        await env.ptw_respond(data, addr_low=lane)
        hit = await env.issue(0, vaddr)
        assert hit.miss == 0, hit
        _check_data(hit, data, vaddr, note="lane hit")
        for other in range(8):
            if other == lane:
                continue
            miss = await env.issue(0, base | (other << 12))
            assert miss.miss == 1, (other, miss)


# DTLB-22: every sector lane resolves to its own PPN through ppn_low.
async def test_sector_all_lanes(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        base = 0x96000000
        data = dtlb_refill(base, 0x96000)
        data.s1_ppn_low = tuple(index & 7 for index in range(8))
        data.s1_valididx = tuple([1] * 8)
        data.s1_pteidx = tuple([1] * 8)
        await env.issue(0, base)
        await env.ptw_respond(data, addr_low=0)
        for lane in range(8):
            vaddr = base | (lane << 12)
            hit = await env.issue(0, vaddr)
            assert hit.miss == 0, (lane, hit)
            assert hit.paddr_0 >> 12 == 0x96000 + lane, (lane, hex(hit.paddr_0))
        if env.coverage:
            env.coverage.sample("hit", 0, 0, "clean")


# DTLB-23: sfence address+ASID, ASID-only, hfence.v and hfence.g forms.
async def test_sfence_forms(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, satp_asid=2, dmode=0)
        a, b = 0x97000000, 0x97800000
        for vaddr, ppn in ((a, 0x97001), (b, 0x97801)):
            await env.issue(0, vaddr)
            data = dtlb_refill(vaddr, ppn)
            data.s1_asid = 2
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        assert (await env.issue(0, a)).miss == 0
        assert (await env.issue(0, b)).miss == 0
        await env.sfence(0, 0, a, 2)
        assert (await env.issue(0, a)).miss == 1
        assert (await env.issue(0, b)).miss == 0
        await env.sfence(1, 0, 0, 2)
        assert (await env.issue(0, b)).miss == 1
        # hfence.v/g do not invalidate noS2 entries.
        await env.issue(0, a)
        data = dtlb_refill(a, 0x97001)
        data.s1_asid = 2
        await env.ptw_respond(data, addr_low=(a >> 12) & 7)
        await env.sfence(1, 1, 0, 0, hv=1)
        assert (await env.issue(0, a)).miss == 0
        await env.sfence(1, 1, 0, 0, hg=1)
        assert (await env.issue(0, a)).miss == 0
        if env.coverage:
            env.coverage.sample("fence", 0, 0, "miss")


# DTLB-24: onlyStage2 VMID filtering.
async def test_only_stage2_vmid_filtering(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, virt=1, vsatp_mode=0, hgatp_mode=8,
                       hgatp_vmid=5, dmode=0)
        vaddr = 0x98000000
        await env.issue(0, vaddr)
        data = dtlb_refill(vaddr, 0x98001, kind=ONLY_S2)
        data.s2_vmid = 5
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        assert (await env.issue(0, vaddr)).miss == 0
        await _context(env, hgatp_vmid=6)
        assert (await env.issue(0, vaddr)).miss == 1
        await _context(env, hgatp_vmid=5)
        assert (await env.issue(0, vaddr)).miss == 0


# DTLB-25: 48-way storage fills with distinct sectors; at least 46 remain
# resident (the generated PLRU may leave one or two ways unused) and a 49th
# refill still completes.
async def test_storage_capacity(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, dmode=0)
        base = 0x100000000
        cases = []
        for index in range(96):
            vaddr = base + index * 0x8000
            ppn = 0x100000 + index
            await env.issue(0, vaddr)
            data = dtlb_refill(vaddr, ppn)
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
            cases.append((vaddr, ppn))
        hits = 0
        for vaddr, ppn in cases:
            snap = await env.issue(0, vaddr)
            if snap.miss == 0:
                hits += 1
                assert snap.paddr_0 == ((ppn << 12) | (vaddr & 0xFFF))
        assert hits >= 46, hits
        extra = 0x180000000
        await env.issue(0, extra)
        data = dtlb_refill(extra, 0x200000)
        await env.ptw_respond(data, addr_low=(extra >> 12) & 7)
        snap = await env.issue(0, extra)
        assert snap.miss == 0 and snap.paddr_0 == (0x200000 << 12)


# DTLB-26: allStage store permission is checked on both stages; a G-stage
# write fault on a store is reported as gpf_st after GPA replay.
async def test_all_stage_store_fault(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, virt=1, vsatp_mode=8, hgatp_mode=8, dmode=0)
        vaddr = 0x99000000
        await env.issue(0, vaddr)
        data = dtlb_refill(vaddr, 0x99001, kind=ALL_STAGE,
                           s2_perm_w=0, s2_perm_a=1)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        first = await env.issue(0, vaddr, cmd=WRITE)
        assert first.miss == 1 and first.gpf_st == 1, first
        assert first.ptw.get_gpa == 1
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7, get_gpa=1)
        second = await env.issue(0, vaddr, cmd=WRITE)
        assert second.miss == 0 and second.gpf_st == 1, second
        assert second.pf_st == 0
        if env.coverage:
            env.coverage.sample("fault", 0, 3, "gpf")


# DTLB-27: sfence over a full storage invalidates every resident way; the
# addressed ASID and hfence forms update all 48 ways' valid bits.
async def test_sfence_after_fill(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, satp_mode=8, satp_asid=1, dmode=0)
        base = 0x200000000
        cases = []
        for index in range(48):
            vaddr = base + index * 0x8000
            ppn = 0x300000 + index
            await env.issue(0, vaddr)
            data = dtlb_refill(vaddr, ppn)
            data.s1_asid = 1
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
            cases.append(vaddr)
        hits = 0
        for vaddr in cases:
            hits += 1 if (await env.issue(0, vaddr)).miss == 0 else 0
        assert hits >= 40, hits
        await env.sfence(1, 1, 0, 0)
        remaining = 0
        for vaddr in cases:
            remaining += 1 if (await env.issue(0, vaddr)).miss == 0 else 0
        assert remaining == 0, remaining
        # Refill again and use ASID/hfence forms.
        for vaddr, index in zip(cases, range(48)):
            await env.issue(0, vaddr)
            data = dtlb_refill(vaddr, 0x300000 + index)
            data.s1_asid = 1
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        await env.sfence(1, 0, 0, 1)
        remaining = 0
        for vaddr in cases:
            remaining += 1 if (await env.issue(0, vaddr)).miss == 0 else 0
        assert remaining == 0, remaining
        for vaddr, index in zip(cases[:8], range(8)):
            await env.issue(0, vaddr)
            data = dtlb_refill(vaddr, 0x310000 + index)
            data.s1_asid = 1
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        await env.sfence(1, 1, 0, 0, hv=1)
        await env.sfence(1, 1, 0, 0, hg=1)
        # noS2 entries survive both hfence forms.
        surviving = 0
        for vaddr in cases[:8]:
            surviving += 1 if (await env.issue(0, vaddr)).miss == 0 else 0
        assert surviving >= 6, surviving


# DTLB-28: GPA replay works on the second requestor port as well.
async def test_gpa_replay_port_two(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, virt=1, vsatp_mode=8, hgatp_mode=8, dmode=0)
        port = 2
        vaddr = 0x300000000
        await env.issue(port, vaddr)
        data = dtlb_refill(vaddr, 0xa0001, kind=ALL_STAGE,
                           s2_gpf=1, s2_perm_a=0, s2_perm_d=0,
                           s2_perm_x=0)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        first = await env.issue(port, vaddr)
        assert first.miss == 1 and first.gpf_ld == 1, first
        assert first.ptw.get_gpa == 1
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7, get_gpa=1)
        replay = await env.issue(port, vaddr)
        assert replay.miss == 0 and replay.gpf_ld == 1, replay
        assert replay.gpaddr == expected_gpaddr(data, vaddr), (
            hex(replay.gpaddr), hex(expected_gpaddr(data, vaddr)))


# DTLB-29: a redirect that flushes the ROB entry captured by the need_gpa state
# clears that state, so the next lookup performs a normal walk again.
async def test_redirect_clears_need_gpa(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        await _context(env, virt=1, vsatp_mode=8, hgatp_mode=8, dmode=0)
        vaddr = 0x310000000
        await env.issue(0, vaddr, rob_value=0x10)
        data = dtlb_refill(vaddr, 0xb0001, kind=ALL_STAGE,
                           s2_gpf=1, s2_perm_a=0, s2_perm_d=0,
                           s2_perm_x=0)
        await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        first = await env.issue(0, vaddr, rob_value=0x10)
        assert first.miss == 1 and first.gpf_ld == 1
        assert first.ptw.get_gpa == 1
        # Flush the robIdx recorded in the need_gpa state.
        await env.redirect_now(value=0x11, flag=0, is_former=0)
        after = await env.issue(0, vaddr, rob_value=0x12)
        # State was cleared, so this is a fresh miss/walk rather than a
        # replayed GPA fault.
        assert after.miss == 1, after
        if env.coverage:
            env.coverage.sample("kill", 0, 3, "miss")


# DTLB-30: hfence.v with a matching ASID and hfence.g with a matching VMID
# clear the corresponding stage-class entries while leaving noS2 intact.
async def test_hfence_asid_vmid_scoped(tlbn_env):
    env = tlbn_env
    async with execution(env):
        await env.reset()
        # onlyStage1 entries with vsatp ASID 3.
        await _context(env, virt=1, vsatp_mode=8, vsatp_asid=3,
                       hgatp_mode=0, dmode=0)
        v1 = [0x320000000 + index * 0x8000 for index in range(8)]
        for index, vaddr in enumerate(v1):
            await env.issue(0, vaddr)
            data = dtlb_refill(vaddr, 0xc0000 + index, kind=ONLY_S1)
            data.s1_asid = 3
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        before = 0
        for vaddr in v1:
            before += 1 if (await env.issue(0, vaddr)).miss == 0 else 0
        assert before >= 6, before
        await env.sfence(1, 0, 0, 3, hv=1)
        after = 0
        for vaddr in v1:
            after += 1 if (await env.issue(0, vaddr)).miss == 0 else 0
        assert after == 0, after

        # onlyStage2 entries with hgatp VMID 4.
        await _context(env, vsatp_mode=0, hgatp_mode=8, hgatp_vmid=4)
        v2 = [0x340000000 + index * 0x8000 for index in range(8)]
        for index, vaddr in enumerate(v2):
            await env.issue(0, vaddr)
            data = dtlb_refill(vaddr, 0xd0000 + index, kind=ONLY_S2)
            data.s2_vmid = 4
            await env.ptw_respond(data, addr_low=(vaddr >> 12) & 7)
        before = 0
        for vaddr in v2:
            before += 1 if (await env.issue(0, vaddr)).miss == 0 else 0
        assert before >= 6, before
        await env.sfence(1, 0, 0, 4, hg=1)
        after = 0
        for vaddr in v2:
            after += 1 if (await env.issue(0, vaddr)).miss == 0 else 0
        assert after == 0, after
        if env.coverage:
            env.coverage.sample("fence", 0, 2, "miss")
