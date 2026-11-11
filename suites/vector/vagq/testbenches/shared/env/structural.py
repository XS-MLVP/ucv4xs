"""Randomized public-pin sweeps for native structural coverage.

This is a coverage harness, not a functional transaction layer.  The sweep
writes every generated input leaf with deterministic random values so that
RTL line/branch/toggle coverage can be collected for modules whose functional
protocol is exercised elsewhere.  It asserts no semantic expectation and is
only used by tests explicitly marked as structural/self-check.
"""
import json
from pathlib import Path
import random

from suites.vector.vagq.testbenches.shared.env.native import open_dut


def _input_widths(schema):
    def leaves(node, prefix=''):
        result = []
        for name, value in node.items():
            path = prefix + name
            if value.get('_') is True:
                high, low = value['High'], value['Low']
                width = 1 if high < low else high - low + 1
                result.append((path, value['Pin'], width))
            else:
                result.extend(leaves(value, path + '_'))
        return result

    return tuple(
        (name, width)
        for name, pin, width in leaves(schema)
        if pin == 'input' and name not in {'clock', 'reset'}
    )


def randomized_pin_sweep(module, schema_path, *, cycles, seed, clocked,
                         output, register=None):
    """Drive random values on the actual generated public input leaves."""
    inputs = _input_widths(json.loads(Path(schema_path).read_text()))
    rng = random.Random(seed)
    values = {name: 0 for name, _width in inputs}
    with open_dut(module, output, clocked=clocked, register=register) as dut:
        for name, _width in inputs:
            getattr(dut, name).AsImmWrite()

        if clocked:
            dut.reset.AsImmWrite()
            dut.reset.Set(1)
            dut.Step(2)
            dut.reset.Set(0)
            dut.Step(1)

        for _cycle in range(cycles):
            for name, width in inputs:
                values[name] = rng.getrandbits(width)
            for name, value in values.items():
                getattr(dut, name).Set(value)
            if clocked:
                dut.Step(1)
            else:
                dut.RefreshComb()
