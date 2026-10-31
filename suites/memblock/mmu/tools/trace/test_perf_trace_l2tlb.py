from suites.memblock.mmu.execution import execution
import json, os


async def _prep(env):
    await env.reset()
    env.set_csr(satp_mode=8, satp_asid=0, satp_ppn=0x80000, imode=0)
    await env.write_csr(0x3B0, (1 << 46) - 1)
    await env.write_csr(0x3A0, 0x1F)
    await env.edge()


async def _trace(env):
    await _prep(env)
    env.start_walk(0x40000, leaf_at_root=True)
    await env.issue(0x12345, 0)
    env.resp["ready"].Set(1)
    rows = []
    for cycle in range(200):
        await env.service_memory(1)
        env.dut.RefreshComb()
        row = dict(
            cycle=cycle,
            resp_valid=env.read(env.resp["valid"]),
            resp_ppn=env.read(env.resp["s1_ppn"]),
            resp_level=env.read(env.resp["s1_level"]),
            resp_v=env.read(env.resp["s1_v"]),
            req_ready=env.read(env.req["ready"]),
            a_valid=env.read(env.a["valid"]),
            a_addr=env.read(env.a["address"]),
            wfi_safe=env.read(env.wfi["safe"]) if hasattr(env, "wfi") else 0,
        )
        if hasattr(env, "perf_values"):
            row["perf"] = env.perf_values()
        else:
            row["perf"] = [env.read(getattr(env.dut, f"io_perf_{i}_value")) for i in range(19)]
        rows.append(row)
        if cycle > 20 and row["resp_valid"] == 0 and any(r["resp_valid"] for r in rows):
            break
    has = [r for r in rows if r["resp_valid"]]
    return rows, has


async def test_trace(l2tlb_env):
    env = l2tlb_env
    async with execution(env.dut):
        rows, has = await _trace(env)
        path = os.environ.get("MMU_PERF_TRACE")
        assert path, "MMU_PERF_TRACE not set"
        with open(path, "w") as f:
            json.dump(rows, f)
        assert has
