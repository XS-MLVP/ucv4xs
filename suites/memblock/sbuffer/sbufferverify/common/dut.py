"""Load Picker-generated DUT packages for this project only.

Only public ports are used. The Picker build has no VPI and no internal-signal
configuration; internal-signal access is therefore unavailable by design.
A fixed Verilator seed keeps randomized register initialization reproducible.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

import xspcomm as xsp
from toffee import as_xdata

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = int(os.environ.get("SBUFFER_VERILATOR_SEED", "1"))


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
    # Picker's DUTUnifiedBase expects argv[0] to be the shared-library path and
    # inserts it when absent. Keep the list minimal and deterministic.
    return xsp.StringVector(["sbuffer-ut", f"+verilator+seed+{seed}"])


def load_sbuffer_data_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("SBUFFER_DATA_DUT_DIR", ROOT / "dut/sbuffer_data"))
    module = _load_package(directory, "_sbuffer_data_picker_dut")
    return module.DUTSbufferDataDut, _argv(seed)


def load_sbuffer_dut(seed: int = DEFAULT_SEED):
    directory = Path(os.environ.get("SBUFFER_DUT_DIR", ROOT / "dut/sbuffer"))
    module = _load_package(directory, "_sbuffer_picker_dut")
    return module.DUTSbufferDut, _argv(seed)


def initialize_inputs(dut) -> None:
    """Drive every generated top-level input to a defined idle value."""
    for signal in vars(dut).values():
        data = as_xdata(signal)
        if hasattr(data, "IsInIO") and data.IsInIO() and not data.IsOutIO():
            data.AsImmWrite()
            data.Set(0)
