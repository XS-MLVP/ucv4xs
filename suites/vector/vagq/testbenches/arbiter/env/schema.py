"""Generated-picker leaf names used only at the native binding boundary."""
from suites.vector.vagq import ROOT as _SUITE_ROOT
import json
from pathlib import Path

ROOT = _SUITE_ROOT
SCHEMA = json.loads((ROOT / 'dut/VAGQArbiter/signals.json').read_text())


def _leaves(node, prefix=''):
    result = []
    for name, value in node.items():
        path = prefix + name
        if value.get('_') is True:
            result.append((path, value['Pin']))
        else:
            result.extend(_leaves(value, path + '_'))
    return result


LEAVES = _leaves(SCHEMA)
INPUT_NAMES = tuple(name for name, pin in LEAVES if pin == 'input')
OUTPUT_NAMES = tuple(name for name, pin in LEAVES if pin == 'output')


def _widths(node, prefix=''):
    result = {}
    for name, value in node.items():
        path = prefix + name
        if value.get('_') is True:
            high, low = value['High'], value['Low']
            result[path] = 1 if high < low else high - low + 1
        else:
            result.update(_widths(value, path + '_'))
    return result


WIDTHS = _widths(SCHEMA)
INPUT_WIDTHS = {name: WIDTHS[name] for name in INPUT_NAMES}
OUTPUT_WIDTHS = {name: WIDTHS[name] for name in OUTPUT_NAMES}

LOAD_REQ_FIELDS = tuple(
    name.removeprefix('io_lduReq_0_bits_req_')
    for name in OUTPUT_NAMES
    if name.startswith('io_lduReq_0_bits_req_')
)
STORE_REQ_FIELDS = tuple(
    name.removeprefix('io_staReq_0_bits_req_')
    for name in OUTPUT_NAMES
    if name.startswith('io_staReq_0_bits_req_')
)
LOAD_META_FIELDS = tuple(
    name.removeprefix('io_lduReq_0_bits_meta_')
    for name in OUTPUT_NAMES
    if name.startswith('io_lduReq_0_bits_meta_')
)
STORE_META_FIELDS = tuple(
    name.removeprefix('io_staReq_0_bits_meta_')
    for name in OUTPUT_NAMES
    if name.startswith('io_staReq_0_bits_meta_')
)


def output_name(group, index, suffix):
    return f'io_{group}_{index}_{suffix}'


def issue_name(group, index, suffix):
    return f'io_{group}_{index}_{suffix}'
