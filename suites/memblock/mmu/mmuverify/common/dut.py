"""Load Picker-generated DUT packages for this project only.

The Picker build uses memory-direct public-port access, no VPI and no internal
signal configuration. A fixed Verilator seed keeps randomized register init
reproducible.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

import xspcomm as xsp
from toffee import as_xdata

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = int(os.environ.get("MMU_VERILATOR_SEED", "1"))


def _load_package(directory: Path, alias: str):
    directory = directory.resolve()
    init = directory / "__init__.py"
    if not init.is_file():
        raise FileNotFoundError(
            f"generated DUT package not found at {init}; build it with tools/build_dut.py"
        )
    module = sys.modules.get(alias)
    if module is None:
        spec = importlib.util.spec_from_file_location(
            alias, init, submodule_search_locations=[str(directory)]
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load generated DUT package {directory}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[alias] = module
        spec.loader.exec_module(module)
    return module


def _argv(seed: int):
    return xsp.StringVector(["mmu-ut", f"+verilator+seed+{seed}"])


def load_tlbfa_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_TLBFA_DUT_DIR", ROOT / "dut/tlbfa"))
    module = _load_package(directory, "_tlbfa_picker_dut")
    return module.DUTTlbfaDut, _argv(seed)


def load_wrapper_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_WRAPPER_DUT_DIR", ROOT / "dut/wrapper"))
    module = _load_package(directory, "_wrapper_picker_dut")
    return module.DUTTlbStorageWrapperDut, _argv(seed)


def load_tlb_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_TLB_DUT_DIR", ROOT / "dut/tlb"))
    module = _load_package(directory, "_tlb_picker_dut")
    return module.DUTTlbDut, _argv(seed)


def load_l2mq_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_L2MQ_DUT_DIR", ROOT / "dut/l2mq"))
    module = _load_package(directory, "_l2mq_picker_dut")
    return module.DUTL2TlbMissQueueDut, _argv(seed)


def load_l2pf_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_L2PF_DUT_DIR", ROOT / "dut/l2pf"))
    module = _load_package(directory, "_l2pf_picker_dut")
    return module.DUTL2TlbPrefetchDut, _argv(seed)


def load_ptwrepeater_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_PTWREPEATER_DUT_DIR", ROOT / "dut/ptwrepeater"))
    module = _load_package(directory, "_ptwrepeater_picker_dut")
    return module.DUTPtwRepeaterNBDut, _argv(seed)


def load_ptwfilter_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_PTWFILTER_DUT_DIR", ROOT / "dut/ptwfilter"))
    module = _load_package(directory, "_ptwfilter_picker_dut")
    return module.DUTPtwFilterDut, _argv(seed)


def load_ptwcache_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_PTWCACHE_DUT_DIR", ROOT / "dut/ptwcache"))
    module = _load_package(directory, "_ptwcache_picker_dut")
    return module.DUTPtwCacheDut, _argv(seed)


def load_llptw_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_LLPTW_DUT_DIR", ROOT / "dut/llptw"))
    module = _load_package(directory, "_llptw_picker_dut")
    return module.DUTLlptwDut, _argv(seed)


def load_pmp_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_PMP_DUT_DIR", ROOT / "dut/pmp"))
    module = _load_package(directory, "_pmp_picker_dut")
    return module.DUTPmpDut, _argv(seed)


def load_bitmapcache_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_BITMAPCACHE_DUT_DIR", ROOT / "dut/bitmapcache"))
    module = _load_package(directory, "_bitmapcache_picker_dut")
    return module.DUTBitmapCacheDut, _argv(seed)


def load_bitmap_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_BITMAP_DUT_DIR", ROOT / "dut/bitmap"))
    module = _load_package(directory, "_bitmap_picker_dut")
    return module.DUTBitmapDut, _argv(seed)


def load_ptw_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_PTW_DUT_DIR", ROOT / "dut/ptw"))
    module = _load_package(directory, "_ptw_picker_dut")
    return module.DUTPtwDut, _argv(seed)


def load_hptw_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_HPTW_DUT_DIR", ROOT / "dut/hptw"))
    module = _load_package(directory, "_hptw_picker_dut")
    return module.DUTHptwDut, _argv(seed)


def load_tlbn_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_TLBN_DUT_DIR", ROOT / "dut/tlbn"))
    module = _load_package(directory, "_tlbn_picker_dut")
    return module.DUTTlbNonBlockDut, _argv(seed)


def load_l2tlbwrapper_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_L2TLBWRAPPER_DUT_DIR", ROOT / "dut/l2tlbwrapper"))
    module = _load_package(directory, "_l2tlbwrapper_picker_dut")
    return module.DUTL2TlbWrapperDut, _argv(seed)


def load_l2tlb_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("MMU_L2TLB_DUT_DIR", ROOT / "dut/l2tlb"))
    module = _load_package(directory, "_l2tlb_picker_dut")
    return module.DUTL2TlbDut, _argv(seed)


def initialize_inputs(dut) -> None:
    """Drive every generated top-level input to a defined idle value."""
    for signal in vars(dut).values():
        data = as_xdata(signal)
        if hasattr(data, "IsInIO") and data.IsInIO() and not data.IsOutIO():
            data.AsImmWrite()
            data.Set(0)
