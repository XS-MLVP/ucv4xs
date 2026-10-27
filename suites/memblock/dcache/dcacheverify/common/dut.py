"""Load Picker-generated DUT packages for this project only.

Public ports only. Every DUT was exported with ``--rw mem_direct -c`` and no
VPI/internal-signal configuration, so the testbench cannot peek at RTL
internals; all checks are expressed on the public interface.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

import xspcomm as xsp
from toffee import as_xdata

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = int(os.environ.get("DCACHE_VERILATOR_SEED", "1"))

sys.path.insert(0, str(ROOT / "tools"))
from duts import DUTS, dut_dir, export_name  # noqa: E402


def _load_package(directory: Path, alias: str):
    directory = directory.resolve()
    init = directory / "__init__.py"
    if not init.is_file():
        raise FileNotFoundError(
            f"generated DUT package not found at {init}; build it with tools/build_dut.py <key>"
        )
    module = sys.modules.get(alias)
    if module is None:
        spec = importlib.util.spec_from_file_location(
            alias, init, submodule_search_locations=[str(directory)])
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load generated DUT package {directory}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[alias] = module
        spec.loader.exec_module(module)
    return module


def _argv(seed: int):
    # Picker's DUTUnifiedBase expects argv[0] to be the shared-library path and
    # inserts it when absent. Keep the list minimal and deterministic.
    return xsp.StringVector(["dcache-ut", f"+verilator+seed+{seed}"])


def load_dut(key: str, seed: int = DEFAULT_SEED):
    if key not in DUTS:
        raise KeyError(f"unknown DUT key {key!r}; known: {sorted(DUTS)}")
    override = os.environ.get(f"DCACHE_DUT_DIR_{key.upper()}")
    directory = Path(override) if override else dut_dir(key)
    module = _load_package(directory, f"_dcache_{key}_picker_dut")
    return getattr(module, f"DUT{export_name(key)}"), _argv(seed)


def initialize_inputs(dut) -> None:
    """Drive every generated top-level input to a defined idle value."""
    for signal in vars(dut).values():
        data = as_xdata(signal)
        if hasattr(data, "IsInIO") and data.IsInIO() and not data.IsOutIO():
            data.AsImmWrite()
            data.Set(0)
