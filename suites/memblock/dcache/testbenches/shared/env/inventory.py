"""Single source of truth for the DCache DUT inventory.

Each entry names a *real* generated SystemVerilog module from
`../../../soc-split/rtl` (kunminghu-v3 @ 893e1580) and the layer it belongs to.
The verification order in `ORDER` follows the RTL hierarchy: leaf control and
tag blocks first, then the load/miss/data mid layer, then the upper pipes, and
finally the integrated DCache.
"""
from __future__ import annotations
from pathlib import Path
from suites.memblock.dcache import ROOT


# key: (top module, layer, short human-readable role)
DUTS = {
    "duplicated_tag_array": (
        "DuplicatedTagArray", "leaf-control",
        "four duplicated tag read ports over a shared 256-set x 4-way tag SRAM",
    ),
    "ctrl_unit": (
        "CtrlUnit", "leaf-control",
        "TL register file that injects pseudo tag/data errors",
    ),
    "miss_ready_gen": (
        "MissReadyGen", "leaf-control",
        "four-way request fan-out into the miss queue with ready backpressure",
    ),
    "counter_filter": (
        "CounterFilter", "leaf-control",
        "load-history counter filter that suppresses already-seen fills",
    ),
    "miss_track": (
        "MissTrack", "mid-path",
        "16-entry speculative miss tracking table",
    ),
    "load_pipe": (
        "LoadPipe", "mid-path",
        "three-stage load pipeline (tag/meta/data/hit-miss/refill request)",
    ),
    "banked_data_array": (
        "BankedDataArray", "mid-path",
        "32-bank interleaved data array with line reads and duplicate write ports",
    ),
    "main_pipe": (
        "MainPipe", "upper",
        "store/atomic main pipeline with refill writeback and miss generation",
    ),
    "miss_queue": (
        "MissQueue", "upper",
        "MSHR/refill/release/probe handling towards L2",
    ),
    "probe_queue": (
        "ProbeQueue", "upper",
        "TileLink probe (B-channel) queue",
    ),
    "writeback_queue": (
        "WritebackQueue", "upper",
        "TileLink writeback (C-channel) queue",
    ),
    "dcache": (
        "DCache", "top",
        "integrated L1 DCache with two L2 client channels",
    ),
    "dcache_wrapper": (
        "DCacheWrapper", "top",
        "MemBlock-level DCache wrapper: pass-through DCache ports plus the "
        "cache-control TL slave and speculative-miss fabric",
    ),
}

ORDER = list(DUTS)


def rtl_dir(key: str) -> Path:
    return ROOT / "rtl" / key


def dut_dir(key: str) -> Path:
    return ROOT / "dut" / key


def export_name(key: str) -> str:
    return "".join(part.capitalize() for part in key.split("_")) + "Dut"
