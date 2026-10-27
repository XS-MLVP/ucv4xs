"""Single source of truth for the LSU DUT inventory.

Each entry names a real generated SystemVerilog module from
``../../soc-split/rtl`` (kunminghu-v3 @ 893e1580) and the verification layer.
``ORDER`` is strictly bottom-up within each family: leaves first, stage
pipelines next, parent last. ``StdExeUnit`` has no generated child module.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOC_RTL = (ucv_paths.soc_rtl_for(ROOT)).resolve()

# key: (top module, family, layer, short human-readable role)
DUTS = {
    # NewStoreUnit family, bottom-up.
    "store_arbiter": (
        "Arbiter3_StoreStageIO", "store", "leaf",
        "three-input store issue arbiter with fixed lane priority",
    ),
    "store_trigger": (
        "MemTrigger_3", "store", "leaf",
        "store address/mask trigger matcher (four trigger slots)",
    ),
    "store_delay": (
        "DelayPipeline", "store", "leaf",
        "one-cycle delayed store payload pipeline",
    ),
    "store_s0": (
        "StoreUnitS0", "store", "stage",
        "store S0: issue arbitration, redirect/illegal-issue kill, TLB/PMP, "
        "trigger, unaligned head/tail injection",
    ),
    "store_s1": (
        "StoreUnitS1", "store", "stage",
        "store S1: address calculation, TLB request, STA nuke query",
    ),
    "store_s2": (
        "StoreUnitS2", "store", "stage",
        "store S2: TLB response, exception formation, SQ address write",
    ),
    "store_s3": (
        "StoreUnitS3", "store", "stage",
        "store S3: unaligned queue request, non-cacheable flags, delay pipeline",
    ),
    "store_s4": (
        "StoreUnitS4", "store", "stage",
        "store S4: final writeback and exception information",
    ),
    "new_store_unit": (
        "NewStoreUnit", "store", "parent",
        "integrated store-address pipeline with real S0-S4",
    ),
    # StdExeUnit is a standalone leaf with no generated child module.
    "std_exe_unit": (
        "StdExeUnit", "std", "leaf",
        "store-data unit: scalar/vector STD arbitration, SQ data, AMO data",
    ),
    # NewLoadUnit family, bottom-up.
    "load_arbiter": (
        "Arbiter7_LoadStageIO", "load", "leaf",
        "seven-input load issue arbiter with fixed lane priority",
    ),
    "load_trigger": (
        "MemTrigger", "load", "leaf",
        "load address/mask trigger matcher (four trigger slots)",
    ),
    "load_datapath": (
        "LoadUnitDataPath", "load", "leaf",
        "load S2/S3 data path: forward/bypass/cache byte selection and align",
    ),
    "load_s0": (
        "LoadUnitS0", "load", "stage",
        "load S0: issue arbitration, forward/bypass request, redirect/kill",
    ),
    "load_s1": (
        "LoadUnitS1", "load", "stage",
        "load S1: physical address, cache/TLB request, early kill",
    ),
    "load_s2": (
        "LoadUnitS2", "load", "stage",
        "load S2: TLB/PMP/cache response, RAR/RAW query, replay cause",
    ),
    "load_s3": (
        "LoadUnitS3", "load", "stage",
        "load S3: replay/exception revocation, data select, LQ write",
    ),
    "load_s4": (
        "LoadUnitS4", "load", "stage",
        "load S4: cross-16B head/tail merge, final writeback and exception",
    ),
    "new_load_unit": (
        "NewLoadUnit", "load", "parent",
        "integrated load pipeline with real S0-S4 and data path",
    ),
}

ORDER = list(DUTS)

FAMILY_ORDER = {
    "store": [key for key in ORDER if DUTS[key][1] == "store"],
    "std": [key for key in ORDER if DUTS[key][1] == "std"],
    "load": [key for key in ORDER if DUTS[key][1] == "load"],
}


def rtl_dir(key: str) -> Path:
    return ROOT / "rtl" / key


def dut_dir(key: str) -> Path:
    return ROOT / "dut" / key


def export_name(key: str) -> str:
    return "".join(part.capitalize() for part in key.split("_")) + "Dut"
