"""Load Picker-generated LSU DUT packages for this project only.

Public ports only. Every DUT is exported with ``--rw mem_direct -c`` and no
VPI/internal-signal configuration, so tests cannot peek at RTL internals; all
checks are expressed on the public interface.
"""
from __future__ import annotations
from suites.memblock.lsu import ROOT as _SUITE_ROOT

import importlib.util
import os
from pathlib import Path
import sys

import xspcomm as xsp
from toffee import as_xdata

ROOT = _SUITE_ROOT
DEFAULT_SEED = int(os.environ.get("LSU_VERILATOR_SEED", "1"))

from suites.memblock.lsu.inventory import DUTS, dut_dir, export_name


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
    return xsp.StringVector(["lsu-ut", f"+verilator+seed+{seed}"])


def load_dut(key: str, seed: int = DEFAULT_SEED):
    if key not in DUTS:
        raise KeyError(f"unknown DUT key {key!r}; known: {sorted(DUTS)}")
    override = os.environ.get(f"LSU_DUT_DIR_{key.upper()}")
    directory = Path(override) if override else dut_dir(key)
    module = _load_package(directory, f"_lsu_{key}_picker_dut")
    return getattr(module, f"DUT{export_name(key)}"), _argv(seed)


def initialize_inputs(dut) -> None:
    """Drive every generated top-level input to a defined idle value."""
    for signal in vars(dut).values():
        data = as_xdata(signal)
        if hasattr(data, "IsInIO") and data.IsInIO() and not data.IsOutIO():
            data.AsImmWrite()
            data.Set(0)


def reset_dut(dut, cycles: int = 4) -> None:
    """Apply synchronously: reset high, clock cycles, reset low, settle."""
    pins = set(dut.xport.GetKeys())
    if "reset" not in pins:
        return
    dut.reset.Set(1)
    for _ in range(cycles):
        dut.Step(1)
    dut.reset.Set(0)
    for _ in range(cycles):
        dut.Step(1)
