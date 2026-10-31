"""Load a test-case module by path so framework checks can reuse its helpers."""

from __future__ import annotations
from suites.frontend.ifu import ROOT as _SUITE_ROOT

import importlib.util
from pathlib import Path
import sys

ROOT = _SUITE_ROOT


def load_case_module(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
