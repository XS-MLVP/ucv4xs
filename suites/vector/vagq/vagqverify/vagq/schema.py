"""Schema-derived public leaves for the generated VAGQ picker root."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'dut/VAGQ/signals.json').read_text())


def _leaves(node, prefix=''):
    result = []
    for name, value in node.items():
        path = prefix + name
        if value.get('_') is True:
            high, low = value['High'], value['Low']
            width = 1 if high < low else high - low + 1
            result.append((path, value['Pin'], width))
        else:
            result.extend(_leaves(value, path + '_'))
    return result


LEAVES = tuple(_leaves(SCHEMA))
WIDTHS = {name: width for name, _, width in LEAVES}
INPUT_NAMES = tuple(name for name, pin, _ in LEAVES
                    if pin == 'input' and name not in ('clock', 'reset'))
OUTPUT_NAMES = tuple(name for name, pin, _ in LEAVES if pin == 'output')
INPUT_WIDTHS = {name: WIDTHS[name] for name in INPUT_NAMES}
OUTPUT_WIDTHS = {name: WIDTHS[name] for name in OUTPUT_NAMES}


def lane_name(prefix, lane, suffix):
    return f'io_{prefix}_{lane}_{suffix}'


def field_name(prefix, lane, suffix):
    return f'io_{prefix}_{lane}_bits_{suffix}'
