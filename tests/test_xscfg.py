"""Synthetic configuration databases must round-trip through Picker's reader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ucv import xscfg
from ucv.common import UcvError

# Reading goes through `picker config`, so these cases need the built tool.
# Writing and the pure path checks below do not.
PICKER = Path(__file__).resolve().parents[1] / '.tools/bin/picker'
requires_picker = pytest.mark.skipif(
    not PICKER.is_file(), reason='requires ucv setup native tool build')


def sections():
    return {
        'metadata': {
            'generator': {'native_abi': 6, 'rw_type': 'MEM_DIRECT', 'simulator': 'verilator'},
            'ports': {
                'clock': {'_': True, 'Pin': 'input', 'High': 0, 'Low': 1},
                'reset': {'_': True, 'Pin': 'input', 'High': 0, 'Low': 1},
                'io': {'req': {'valid': {'_': True, 'Pin': 'input', 'High': -1, 'Low': 0},
                               'bits': {'addr': {'_': True, 'Pin': 'input', 'High': 47, 'Low': 0}}}},
            },
        },
        'variables': {
            'TOP.model.field': {'type': 'CData', 'mem_bytes': 1, 'rtl_width': 3, 'offset': 16},
            'TOP.model.wide': {'type': 'QData', 'mem_bytes': 8, 'rtl_width': 48, 'offset': 24},
            'TOP.model.array': {'type': 'CData', 'mem_bytes': 1, 'rtl_width': 8,
                                'offset': 40, 'array_size': 4,
                                'array_dimensions': [4], 'array_strides': [1]},
        },
        'signals': {
            'TOP.sig.projection': {'kind': 'projection', 'source': 'TOP.model.field',
                                   'expr': '1U', 'rtl_width': 1, 'deps': ['TOP.model.field']},
            'TOP.sig.expr': {'kind': 'expr', 'expr': '2U', 'rtl_width': 2, 'deps': []},
        },
    }


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'SynthDut.xscfg'
    xscfg.write_database(path, sections(), model='synthetic')
    return path


@requires_picker
def test_written_database_is_readable_by_the_picker_reader(database):
    reader = xscfg.Database(database)
    assert reader.generator == sections()['metadata']['generator']
    assert reader.ports == sections()['metadata']['ports']
    assert reader.variables == sections()['variables']
    assert reader.signals == sections()['signals']
    assert sorted(reader.names()) == sorted(
        [*sections()['variables'], *sections()['signals']])


@requires_picker
def test_negative_and_nested_values_survive_the_round_trip(database):
    ports = xscfg.Database(database).ports
    assert ports['io']['req']['bits']['addr'] == {'_': True, 'Pin': 'input', 'High': 47, 'Low': 0}


def test_database_path_requires_exactly_one_database(tmp_path):
    (tmp_path / 'a.xscfg').write_bytes(b'x')
    (tmp_path / 'b.xscfg').write_bytes(b'x')
    with pytest.raises(UcvError, match='exactly one'):
        xscfg.database_path(tmp_path)


def test_empty_and_unknown_sections_are_rejected(tmp_path):
    with pytest.raises(UcvError, match='at least one record'):
        xscfg.write_database(tmp_path / 'empty.xscfg', {})
    with pytest.raises(UcvError, match='unknown configuration section'):
        xscfg.write_database(tmp_path / 'bad.xscfg', {'retired': {'x': 1}})


@requires_picker
def test_addressable_and_lookup_separate_storage_from_traces(database):
    reader = xscfg.Database(database)
    assert reader.addressable('TOP.model.field')['offset'] == 16
    assert reader.addressable('TOP.sig.expr') is None
    assert reader.lookup('TOP.sig.expr')['kind'] == 'expr'
    assert reader.lookup('missing') is None


@requires_picker
def test_written_records_are_found_by_name_not_only_enumerated(database):
    """The index hash must match upstream byte-for-byte, not just list order."""
    reader = xscfg.Database(database)
    for name, record in sections()['variables'].items():
        assert reader.addressable(name) == record
