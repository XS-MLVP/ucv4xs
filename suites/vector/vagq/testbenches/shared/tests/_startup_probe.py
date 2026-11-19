"""Fresh-process metadata isolation probe used by test_dut_startup.py.

All signals are synthetic. Any real native/RTL access is rejected, and the
configuration-database reader is replaced by one that records which DUT
directory was asked for, so an unselected read fails before any file opens.
This process never runs hardware tests.
"""
import asyncio
from contextlib import contextmanager
import importlib
import inspect
import json
import os
from pathlib import Path
import sys

import pytest
import suites.vector.vagq as suite


# Picker-shaped synthetic leaves, not copied from any generated DUT.
SYNTHETIC_PORTS = {
    'clock': {'_': True, 'Pin': 'input', 'High': 0, 'Low': 1},
    'reset': {'_': True, 'Pin': 'input', 'High': 0, 'Low': 1},
    'io_synthetic_input': {'_': True, 'Pin': 'input', 'High': 7, 'Low': 0},
    'io_synthetic_output': {'_': True, 'Pin': 'output', 'High': 7, 'Low': 0},
}


def main():
    mode, dut, resource_root, selection, destination = sys.argv[1:]
    actual_root = suite.ROOT
    suite.ROOT = Path(resource_root)
    allowed = (suite.ROOT / 'dut' / dut).resolve()
    reads = []

    class SelectedMetadataRead(Exception):
        pass

    def guard(event, args):
        if event == 'import' and (args[0] == 'dut' or args[0].startswith('dut.')):
            raise AssertionError('native import is forbidden in this control')
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).absolute()
        if any(path.is_relative_to(actual_root / directory) for directory in ('dut', 'rtl', 'XiangShan')):
            raise AssertionError(f'real design/native access is forbidden: {path}')

    sys.addaudithook(guard)

    # Suites read generated metadata through ucv.xscfg. Replacing the reader
    # here records the requested DUT directory directly, which is the
    # invariant under test: only the selected DUT may be asked for metadata.
    from ucv import xscfg as xscfg_module

    def synthetic_open(directory):
        requested = Path(directory).resolve()
        assert requested == allowed, f'unselected metadata read: {requested}'
        reads.append(str(requested))
        if mode == 'fixture':
            raise SelectedMetadataRead(dut)
        instance = xscfg_module.Database.__new__(xscfg_module.Database)
        instance.path = requested / 'synthetic.xscfg'
        instance._picker = None
        instance._cache = {'metadata': {'ports': SYNTHETIC_PORTS}}
        return instance

    xscfg_module.open_dut = synthetic_open
    if mode == 'fixture':
        registry = importlib.import_module('suites.vector.vagq.conftest')
        for plugin in registry.pytest_plugins:
            importlib.import_module(plugin)
        assert reads == [], 'fixture registration must not read any DUT metadata'
        from suites.vector.vagq.testbenches.shared.env import native

        @contextmanager
        def no_native(*args, **kwargs):
            yield object()

        native.open_dut = no_native
        plugin, fixture_name = selection.rsplit(':', 1)
        fixture_module = importlib.import_module(plugin)
        if hasattr(fixture_module, 'open_dut'):
            fixture_module.open_dut = no_native
        fixture = getattr(fixture_module, fixture_name).__wrapped__
        generator = fixture(None, suite.ROOT / 'output')
        try:
            if inspect.isasyncgen(generator):
                asyncio.run(anext(generator))
            else:
                next(generator)
        except SelectedMetadataRead as error:
            assert str(error) == dut
        else:
            raise AssertionError('using the fixture did not request its own metadata')
        assert reads == [str(allowed)]
        result = {'mode': mode, 'dut': dut, 'metadata_reads': reads, 'registration_reads': []}
    else:
        class Collected:
            def pytest_collection_finish(self, session):
                self.items = [item.nodeid for item in session.items]

        collected = Collected()
        status = pytest.main([
            '-q', '--collect-only', '-p', 'no:cacheprovider', '-p', 'pytest_asyncio.plugin',
            '-c', str(actual_root / 'pytest.ini'), str(actual_root / selection),
        ], plugins=[collected])
        assert status == 0, f'isolated collection failed: {status}'
        assert collected.items
        result = {'mode': mode, 'dut': dut, 'metadata_reads': reads, 'items': collected.items}
    Path(destination).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
