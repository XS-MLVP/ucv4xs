"""PMP/PMA standalone configuration tests."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution
from suites.memblock.mmu.l2.pmp import Cfg, PmpModel


PMP_CFG = [0x3A0, 0x3A2, 0x3A4, 0x3A6]
PMP_ADDR = 0x3B0
PMA_CFG = [0x7C0, 0x7C2, 0x7C4, 0x7C6]
PMA_ADDR = 0x7C8


def _bytes(values: list[int]) -> int:
    data = 0
    for index, value in enumerate(values):
        data |= (value & 0xFF) << (8 * index)
    return data


def _compare(env, model: PmpModel, table: str, note: str = "") -> None:
    got = env.snapshot(table)
    expected = model.snapshot(table)
    keys = expected[0].keys()
    for index, (actual, want) in enumerate(zip(got, expected)):
        for key in keys:
            assert actual[key] == want[key], (note, table, index, key, actual[key], want[key])


async def test_reset_defaults(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        _compare(env, model, "pmp", "reset")
        _compare(env, model, "pma", "reset")
        assert all(entry["mask"] == 0xFFF for entry in env.snapshot("pma")[:19])
        assert all(not any(v for k, v in entry.items() if k != "mask")
                   for entry in env.snapshot("pmp"))


async def test_cfg_coarsening_and_wr_mask(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        data = _bytes([0x1E, 0x00, 0x0F, 0x1F, 0x9F, 0x0B, 0x12, 0x07])
        await env.write(PMP_CFG[0], data)
        model.write_cfg("pmp", 0, data)
        _compare(env, model, "pmp", "cfg0")
        entry0 = env.read_entry("pmp", 0)
        assert entry0["a"] == 3 and entry0["w"] == 0 and entry0["r"] == 0
        entry2 = env.read_entry("pmp", 2)
        assert entry2["a"] == 1 and entry2["x"] == 1
        if env.coverage:
            env.coverage.sample("cfg_write", "napot", "pmp")
            env.coverage.sample("cfg_write", "tor", "pmp")


async def test_addr_modes_and_masks(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        # Entry 0 OFF, 1 TOR, 2 NAPOT, 3 NAPOT (raw NA4 coarsens to NAPOT).
        data = _bytes([0x00, 0x0F, 0x1F, 0x17])
        await env.write(PMP_CFG[0], data)
        model.write_cfg("pmp", 0, data)
        for index, value in enumerate([0x000, 0x200, 0x300, 0x401]):
            await env.write(PMP_ADDR + index, value)
            model.write_addr("pmp", index, value)
        _compare(env, model, "pmp", "addr")
        assert env.read_entry("pmp", 0)["mask"] == 0xFFF
        assert env.read_entry("pmp", 1)["mask"] == 0x1FFF
        if env.coverage:
            env.coverage.sample("addr_write", "tor", "pmp")
            env.coverage.sample("addr_write", "napot", "pmp")


async def test_napot_cfg_write_recomputes_mask(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        await env.write(PMP_ADDR, 0x400)
        model.write_addr("pmp", 0, 0x400)
        await env.write(PMP_CFG[0], _bytes([0x1F]))
        model.write_cfg("pmp", 0, _bytes([0x1F]))
        _compare(env, model, "pmp", "napot cfg")
        first_mask = env.read_entry("pmp", 0)["mask"]
        await env.write(PMP_ADDR, 0x800)
        model.write_addr("pmp", 0, 0x800)
        _compare(env, model, "pmp", "napot addr")
        assert env.read_entry("pmp", 0)["addr"] == 0x800


async def test_cfg_lock(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        data = _bytes([0x9F, 0x1F])  # entry 0 locked NAPOT, entry 1 NAPOT
        await env.write(PMP_CFG[0], data)
        model.write_cfg("pmp", 0, data)
        second = _bytes([0x00, 0x00])
        await env.write(PMP_CFG[0], second)
        model.write_cfg("pmp", 0, second)
        _compare(env, model, "pmp", "cfg lock")
        assert env.read_entry("pmp", 0)["l"] == 1 and env.read_entry("pmp", 0)["a"] == 3
        if env.coverage:
            env.coverage.sample("lock", "napot", "pmp")


async def test_addr_lock_and_tor_next_lock(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        data = _bytes([0x9F, 0x0F, 0x8F])  # 0 locked, 1 TOR, 2 locked TOR
        await env.write(PMP_CFG[0], data)
        model.write_cfg("pmp", 0, data)
        for index in range(3):
            value = 0x100 * (index + 1)
            await env.write(PMP_ADDR + index, value)
            model.write_addr("pmp", index, value)
        _compare(env, model, "pmp", "addr lock")
        # Entry 0 locked by its own L, entry 1 locked by entry 2's L+TOR.
        assert env.read_entry("pmp", 0)["addr"] == 0
        assert env.read_entry("pmp", 1)["addr"] == 0
        if env.coverage:
            env.coverage.sample("addr_write", "tor", "pmp")
            env.coverage.sample("tor_lock", "tor", "pmp")


async def test_all_pmp_entries(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        for group in range(4):
            values = []
            for offset in range(8):
                index = group * 8 + offset
                mode = [0x00, 0x0F, 0x1F, 0x17][index % 4]
                values.append(mode)
            data = _bytes(values)
            await env.write(PMP_CFG[group], data)
            model.write_cfg("pmp", group * 8, data)
        for index in range(32):
            value = 0x40 * index
            await env.write(PMP_ADDR + index, value)
            model.write_addr("pmp", index, value)
        _compare(env, model, "pmp", "all")
        if env.coverage:
            env.coverage.sample("all_entries", "napot", "pmp")


async def test_all_pma_entries(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        for group in range(4):
            values = []
            for offset in range(8):
                index = group * 8 + offset
                values.append([0x00, 0x0F, 0x5F, 0x7F][index % 4])
            data = _bytes(values)
            await env.write(PMA_CFG[group], data)
            model.write_cfg("pma", group * 8, data)
        for index in range(32):
            value = 0x80 * index + 0x100
            await env.write(PMA_ADDR + index, value)
            model.write_addr("pma", index, value)
        _compare(env, model, "pma", "all pma")
        _compare(env, model, "pmp", "pmp untouched")
        assert env.read_entry("pma", 2)["c"] == 1
        assert env.read_entry("pma", 3)["atomic"] == 1
        if env.coverage:
            env.coverage.sample("all_entries", "napot", "pma")
            env.coverage.sample("pma", "napot", "pma")


async def test_invalid_csr_ignored(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        before = env.snapshot("pmp")
        for addr in (0x3A1, 0x3A3, 0x3AF, 0x7C1, 0x7C7, 0x7FF):
            await env.write(addr, 0xFFFFFFFFFFFFFFFF)
        assert env.snapshot("pmp") == before
        _compare(env, model, "pmp", "invalid")
        _compare(env, model, "pma", "invalid")
        if env.coverage:
            env.coverage.sample("invalid_csr", "off", "pmp")


async def test_mask_reference_sweep(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        await env.write(PMP_CFG[0], _bytes([0x1F]))
        model.write_cfg("pmp", 0, _bytes([0x1F]))
        for value in (0, 1, 0x3FF, 0x400, 0x7FF, 0x800, 0x1000, 0x12345,
                      (1 << 45) - 1, (1 << 45)):
            await env.write(PMP_ADDR, value)
            model.write_addr("pmp", 0, value)
            _compare(env, model, "pmp", f"mask {value:#x}")


# PMP-12: drive all PMP/PMA address, mask, cfg and reserved bits through both
# all-ones and all-zeros values, including the lock bit.
async def test_all_bits_sweep(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        for table, cfg_bases, addr_base in (
            ("pmp", PMP_CFG, PMP_ADDR), ("pma", PMA_CFG, PMA_ADDR)
        ):
            # Unlocked NAPOT RWX with all metadata bits set except L.
            for group, base in enumerate(cfg_bases):
                data = 0x7F7F7F7F7F7F7F7F
                await env.write(base, data)
                model.write_cfg(table, group * 8, data)
            for index in range(32):
                for value in (0, (1 << 46) - 1, (1 << 46) - 2):
                    await env.write(addr_base + index, value)
                    model.write_addr(table, index, value)
            _compare(env, model, table, "sweep ones")
            for group, base in enumerate(cfg_bases):
                data = 0
                await env.write(base, data)
                model.write_cfg(table, group * 8, data)
            for index in range(32):
                await env.write(addr_base + index, 0)
                model.write_addr(table, index, 0)
            _compare(env, model, table, "sweep zeros")
            # Lock the entries last, after the address sweep.
            for group, base in enumerate(cfg_bases):
                data = 0xFFFFFFFFFFFFFFFF
                await env.write(base, data)
                model.write_cfg(table, group * 8, data)
            _compare(env, model, table, "sweep locked")


# PMP-13: exhaustive PMA cfg byte semantics across 0x7C0..0x7C6.  Every cfg
# field (C/ATOMIC/A/X/W/R) is written through the distributed CSR decoder and
# compared byte-for-byte with the documented coarsening rules; PMA address
# writes then update mask for the programmed A mode.
async def test_pma_cfg_byte_semantics(env_pmp):
    env = env_pmp
    async with execution(env):
        await env.reset()
        model = PmpModel(env.pma_default)
        for group, base in enumerate(PMA_CFG):
            values = [((group * 8 + offset) * 37 + 0x40) & 0x7F
                      for offset in range(8)]
            data = _bytes(values)
            await env.write(base, data)
            model.write_cfg("pma", group * 8, data)
            await env.write(base, data)
            model.write_cfg("pma", group * 8, data)
            _compare(env, model, "pma", f"pma cfg byte {group}")
        for index in range(32):
            value = (0x200 + index * 0x800) & ((1 << 46) - 1)
            await env.write(PMA_ADDR + index, value)
            model.write_addr("pma", index, value)
        _compare(env, model, "pma", "pma addr mask")
        # Explicit field mapping for byte 0x5F: A=NAPOT, X=1, W=1, R=1,
        # ATOMIC=0, C=1; the coarsening keeps NAPOT.
        index = 16
        data = _bytes([0x5F] + [0] * 7)
        await env.write(PMA_CFG[2], data)
        model.write_cfg("pma", 16, data)
        entry = env.read_entry("pma", 16)
        assert entry["c"] == 1 and entry["atomic"] == 0, entry
        assert entry["a"] == 3 and entry["x"] == 1, entry
        assert entry["w"] == 1 and entry["r"] == 1, entry
        if env.coverage:
            env.coverage.sample("pma", "napot", "pma")
