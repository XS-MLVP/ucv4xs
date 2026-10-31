#!/usr/bin/env python3
"""Probe the DCache top-level load/refill handshake (diagnostic, not a test).

Runs one cold load, answers the TileLink AcquireBlock with two GrantData beats,
waits for the load wakeup, then re-issues the load and prints the S2 response.
Used to debug the still-open DCache integration phase; it writes no result
directory and does not participate in coverage evidence.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from suites.memblock.dcache.inventory import dut_dir  # noqa: E402


def load_dut():
    package = dut_dir("dcache")
    spec = importlib.util.spec_from_file_location(
        "_dc_probe", package / "__init__.py",
        submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["_dc_probe"] = module
    spec.loader.exec_module(module)
    return module.DUTDcacheDut()


def value(signal) -> int:
    return int(signal.value)


def main() -> int:
    dut = load_dut()
    dut.InitClock("clock")
    for signal in list(vars(dut).values()):
        if callable(getattr(signal, "IsInIO", None)) and signal.IsInIO()\
                and not signal.IsOutIO():
            signal.AsImmWrite()
            signal.Set(0)

    def channel(index: int) -> str:
        return f"auto_client_nodes_out_{index}"

    for index in range(2):
        getattr(dut, channel(index) + "_a_ready").Set(1)
        getattr(dut, channel(index) + "_c_ready").Set(1)
        getattr(dut, channel(index) + "_e_ready").Set(1)
        getattr(dut, channel(index) + "_d_valid").Set(0)
        getattr(dut, channel(index) + "_b_valid").Set(0)
    dut.io_lqEmpty.Set(1)
    dut.reset.Set(1)
    dut.Step(5)
    dut.reset.Set(0)
    dut.Step(3)
    # The tag/meta SRAMs perform a 256-set clear sweep after reset.
    for _ in range(300):
        dut.Step(1)

    base = 0x8000
    words = [int.from_bytes(bytes(((base + beat * 32 + i) & 0xFF) for i in range(32)),
                            "little") for beat in range(2)]

    def issue(vaddr: int = 0x1000) -> None:
        dut.io_lsu_load_0_req_valid.Set(1)
        dut.io_lsu_load_0_req_bits_vaddr.Set(vaddr)
        dut.io_lsu_load_0_req_bits_vaddr_dup.Set(vaddr)
        dut.io_lsu_load_0_req_bits_mask.Set(0x00FF)
        dut.io_lsu_load_0_s1_paddr_dup_lsu.Set(base)
        dut.io_lsu_load_0_s1_paddr_dup_dcache.Set(base)

    issue()
    pending = None
    accepted_at = None
    for cycle in range(40):
        if cycle >= 3:
            dut.io_lsu_load_0_req_valid.Set(0)
        for index in range(2):
            if value(getattr(dut, channel(index) + "_a_valid"))\
                    and value(getattr(dut, channel(index) + "_a_ready")):
                pending = {"ch": index,
                           "src": value(getattr(dut, channel(index) + "_a_bits_source")),
                           "beat": 0}
                accepted_at = cycle
                print(f"{cycle}: A accepted ch{index} "
                      f"op={value(getattr(dut, channel(index) + '_a_bits_opcode'))} "
                      f"addr={value(getattr(dut, channel(index) + '_a_bits_address')):#x} "
                      f"size={value(getattr(dut, channel(index) + '_a_bits_size'))}")
        if pending and cycle >= accepted_at + 1:
            getattr(dut, channel(pending["ch"]) + "_d_valid").Set(1)
            getattr(dut, channel(pending["ch"]) + "_d_bits_opcode").Set(5)
            getattr(dut, channel(pending["ch"]) + "_d_bits_param").Set(0)
            getattr(dut, channel(pending["ch"]) + "_d_bits_size").Set(6)
            getattr(dut, channel(pending["ch"]) + "_d_bits_source").Set(pending["src"])
            getattr(dut, channel(pending["ch"]) + "_d_bits_sink").Set(0)
            getattr(dut, channel(pending["ch"]) + "_d_bits_denied").Set(0)
            getattr(dut, channel(pending["ch"]) + "_d_bits_corrupt").Set(0)
            getattr(dut, channel(pending["ch"]) + "_d_bits_echo_isKeyword").Set(0)
            getattr(dut, channel(pending["ch"]) + "_d_bits_data").Set(words[pending["beat"]])
        else:
            for index in range(2):
                getattr(dut, channel(index) + "_d_valid").Set(0)
        dut.Step(1)
        if pending and value(getattr(dut, channel(pending["ch"]) + "_d_ready")):
            pending["beat"] += 1
            if pending["beat"] >= 2:
                getattr(dut, channel(pending["ch"]) + "_d_valid").Set(0)
                pending = None
        if value(dut.io_lsu_loadWakeup_0_valid):
            print(f"{cycle}: loadWakeup mshr={value(dut.io_lsu_loadWakeup_0_bits_mshrId)}")

    issue()
    for cycle in range(6):
        accepted = value(dut.io_lsu_load_0_req_ready)
        dut.Step(1)
        print(f"reload {cycle}: ready={accepted} "
              f"miss={value(dut.io_lsu_load_0_resp_bits_miss)} "
              f"data={value(dut.io_lsu_load_0_resp_bits_data):#x}")
        if accepted:
            break
    dut.io_lsu_load_0_req_valid.Set(0)
    for _ in range(2):
        dut.Step(1)
    print("reload s2: miss=", value(dut.io_lsu_load_0_resp_bits_miss),
          "handled=", value(dut.io_lsu_load_0_resp_bits_handled))
    print("expected line[0:16] =", (words[0] & ((1 << 128) - 1)).to_bytes(16, "little").hex())
    print("observed resp data =",
          value(dut.io_lsu_load_0_resp_bits_data).to_bytes(16, "little").hex())
    dut.Finish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
