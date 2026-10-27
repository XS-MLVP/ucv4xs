"""Report-driven regression helpers with independent explicit expectations."""
from mmuverify.common.runtime import execution
from mmuverify.common.checks import check_l2_success


async def check_misaligned_1g_leaf(env, prepare):
    async with execution(env.dut):
        await prepare(env)
        env.walk_script = None
        env.memory.build_sv39(0x80000, 0x70000, 0x3000, level=2)
        await env.issue(0x70000)
        snap = await env.wait_response(note="ISA misaligned 1GiB leaf")
        assert snap["valid"] == 1 and snap["s1_pf"] == 1, snap
        assert snap["s1_af"] == 0, snap
        assert snap["s2xlate"] == 0, snap


async def check_address_fence_and_neighbor(env, prepare, build):
    async with execution(env.dut):
        await prepare(env)
        env.walk_script = None
        cases = [(0x84000, 0x4000, 0x6000, 0x80300),
                 (0x86000, 0x5000, 0x7000, 0x80301)]
        for vpn, old, new, leaf in cases:
            build(env, vpn, old, mid=0x80200, leaf=leaf)
        for vpn, old, new, leaf in cases:
            await env.issue(vpn)
            check_l2_success(await env.wait_response(), ppn=old >> 3, tag=vpn >> 3, stage=0)
        for vpn, old, new, leaf in cases:
            build(env, vpn, new, mid=0x80200, leaf=leaf)
        for key, value in dict(valid=1, rs1=0, rs2=1, addr=cases[0][0] << 12, id=0).items():
            env.sfence[key].Set(value)
        for _ in range(3):
            await env.service_memory(1)
        env.sfence["valid"].Set(0)
        await env.service_memory(10)
        await env.issue(cases[0][0])
        check_l2_success(await env.wait_response(), ppn=cases[0][2] >> 3, stage=0)
        await env.issue(cases[1][0])
        check_l2_success(await env.wait_response(), ppn=cases[1][1] >> 3, stage=0)
        env.sfence["rs1"].Set(1)
        env.sfence["rs2"].Set(1)
        env.sfence["valid"].Set(1)
        await env.service_memory(3)
        env.sfence["valid"].Set(0)
        await env.service_memory(10)
        await env.issue(cases[1][0])
        check_l2_success(await env.wait_response(), ppn=cases[1][2] >> 3, stage=0)
