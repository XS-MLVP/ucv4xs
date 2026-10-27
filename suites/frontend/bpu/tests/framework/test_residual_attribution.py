"""Negative controls for tools/attribute_integrated_residual.py.

The attribution tool must (a) collapse physical copy indices into one emission
site, (b) keep distinct sites distinct, and (c) never invent credit: the output
only counts what the native report says.
"""
from __future__ import annotations

import importlib.util

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location(
        'attribute_integrated_residual', ROOT / 'tools' / 'attribute_integrated_residual.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def report(rows, branches=()):
    return dict(dut=dict(bpu=dict(
        by_source=dict(rtl_verilog=dict(source_lines=dict(total=100, hit=50))),
        uncovered_rtl_source_lines=list(rows),
        uncovered_rtl_branches=list(branches))))


def test_multi_dut_report_attributes_the_largest_residual():
    """A whole-suite report merges every DUT; picking the first one is silent.

    `abtb` sorts before `bpu` and has zero residual, so a single-DUT reader
    reports `files=0` while the largest DUT is untouched. The tool must select
    the DUT with the most uncovered lines, and an explicit name must be honoured.
    """

    module = load()
    merged = dict(dut=dict(
        abtb=dict(by_source=dict(rtl_verilog=dict(source_lines=dict(total=10, hit=10))),
                  uncovered_rtl_source_lines=[], uncovered_rtl_branches=[]),
        bpu=dict(by_source=dict(rtl_verilog=dict(source_lines=dict(total=100, hit=50))),
                 uncovered_rtl_source_lines=[dict(file='rtl/bpu/x.sv', line=1, verilog='a <= b;')],
                 uncovered_rtl_branches=[])))
    result = module.attribute(merged)
    assert result['dut'] == 'bpu'
    assert result['uncovered_lines'] == 1
    assert module.attribute(merged, dut='abtb')['uncovered_lines'] == 0
    with pytest.raises(ValueError, match='unknown dut'):
        module.attribute(merged, dut='missing')


def test_copy_indices_collapse_into_one_site():
    module = load()
    rows = [dict(file='rtl/x.sv', line=10 + index,
                 verilog=f'states_{index} <= io_write_1_bits_state;') for index in range(64)]
    result = module.attribute(report(rows))
    f = result['files'][0]
    assert f['uncovered_lines'] == 64
    assert f['emission_sites'] == 1
    assert f['largest_sites'][0]['count'] == 64
    assert f['copies_per_site'] == {64: 1}


def test_distinct_templates_stay_distinct():
    module = load()
    rows = [
        dict(file='rtl/x.sv', line=1, verilog='a_0 <= b;'),
        dict(file='rtl/x.sv', line=2, verilog='c_0 <= d;'),
    ]
    f = module.attribute(report(rows))['files'][0]
    assert f['emission_sites'] == 2


def test_output_grants_no_credit_and_keeps_denominator():
    module = load()
    result = module.attribute(report([]))
    assert result['uncovered_lines'] == 0
    assert 'credit' in result['note']
    assert result['source_lines'] == dict(total=100, hit=50)
    assert 'functional' not in result and 'passed' not in result


def test_branch_counts_are_per_file():
    module = load()
    branches = [dict(file='rtl/x.sv', line=1, arm='else')] * 3 +\
               [dict(file='rtl/y.sv', line=2, arm='if')]
    result = module.attribute(report([], branches))
    assert result['uncovered_branches'] == 4
    assert result['branch_files'][0] == dict(file='rtl/x.sv', count=3)
