"""Fixture-owned Picker resources and exact installed-tool validation."""
from __future__ import annotations
from suites.memblock.lsq import ROOT as _SUITE_ROOT
import ucv.runtime as ucv_paths

import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys

from .evidence import Journal

ROOT = _SUITE_ROOT


from ucv.runtime import validate_runtime


class DutFactory:
    def __init__(self, register, output: Path, *, nodeid="", trace=False, trace_max_bytes=16*1024*1024, waveforms=False):
        validate_runtime()
        self.register, self.output = register, output
        self.nodeid,self.trace,self.trace_max_bytes,self.waveforms=nodeid,trace,trace_max_bytes,waveforms
        self._instances = []

    def journal(self,filename):
        return Journal(self.output/filename,nodeid=self.nodeid,trace=self.trace,max_bytes=self.trace_max_bytes)

    def create(self, key: str):
        directory = ROOT / "dut" / key
        name = f"lsq_native_{key}_{len(self._instances)}"
        spec = importlib.util.spec_from_file_location(name, directory / "__init__.py",
                                                     submodule_search_locations=[str(directory)])
        if spec is None or spec.loader is None:
            raise RuntimeError(f"missing native DUT: {directory}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        cls = next(v for k, v in vars(module).items() if k.startswith("DUT"))
        self.output.mkdir(parents=True, exist_ok=True)
        dut = cls(module.xsp.StringVector([key, ucv_paths.native_seed()]),
                  waveform_filename=str(self.output / f"{key}.fst") if self.waveforms else "", coverage_filename="")
        try:
            if not dut.dut.GetXSignalCFGBasePtr() or not dut.GetCovMetrics() & 1:
                raise RuntimeError("DUT needs mem_direct access and native line coverage")
            if module.xsp.abi_version() != 3 or module.xsp.XTriggerEngine.CoverageVersion() != 5:
                raise RuntimeError("generated DUT xcomm ABI/coverage mismatch")
            dut.InitClock("clock")
            reset = getattr(dut, "reset", None)
            for signal in vars(dut).values():
                if callable(getattr(signal, "IsInIO", None)) and signal.IsInIO():
                    signal.AsImmWrite()
                    signal.Set(1 if signal is reset else 0)
            self.register(dut)
        except BaseException:
            dut.Finish()
            raise
        self._instances.append(dut)
        return dut

    def close(self):
        while self._instances:
            self._instances.pop().Finish()
