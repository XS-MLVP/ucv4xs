"""Public pytest collection/filter hooks; xdist scheduling stays unmodified."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from suites.frontend.bpu.runtime.process_scope import DOMAINS, SCOPES, observe_process
from suites.frontend.bpu.pytest_plugins.evidence import collection_digest, write_json


def item_scope(item):
    markers = list(item.iter_markers('dut'))
    if len(markers) > 1:
        raise ValueError(f'{item.nodeid}: multiple DUT owners')
    explicit = None
    if markers:
        marker = markers[0]
        if len(marker.args) != 1 or marker.kwargs or marker.args[0] not in DOMAINS:
            raise ValueError(f'{item.nodeid}: dut marker needs one canonical DUT name')
        explicit = marker.args[0]
    fixtures = set(item.fixturenames)
    if 'dut_factory' not in fixtures:
        if explicit is not None:
            raise ValueError(f'{item.nodeid}: DUT marker without factory ownership')
        return 'pure'
    agents = {name for name in DOMAINS if f'{name}_agent' in fixtures}
    parts = Path(item.nodeid.split('::', 1)[0]).parts
    directory = parts[1] if len(parts) >= 2 and parts[0] == 'tests' and parts[1] in DOMAINS else None
    owners = agents | ({directory} if directory else set()) | ({explicit} if explicit else set())
    if len(owners) != 1:
        raise ValueError(f'{item.nodeid}: native DUT ownership must be explicit and unique: {sorted(owners)}')
    return owners.pop()


def collection_index(items):
    rows = [dict(nodeid=item.nodeid, scope=item_scope(item),
                 features=sorted({marker.args[0] for marker in item.iter_markers('feature')})) for item in items]
    names = [row['nodeid'] for row in rows]
    if not names or len(names) != len(set(names)):
        raise ValueError('empty or duplicate regression collection')
    return dict(format='bpu-dut-partition-index', version=1, collection_sha256=collection_digest(names),
                count=len(rows), cases=rows)


def selected_ids(index, scope):
    if index.get('format') != 'bpu-dut-partition-index' or index.get('version') != 1 or scope not in SCOPES:
        raise ValueError('invalid DUT partition index or scope')
    rows = index['cases']
    names = [row['nodeid'] for row in rows]
    if (index['count'] != len(rows) or len(names) != len(set(names))
            or index['collection_sha256'] != collection_digest(names)
            or any(row['scope'] not in SCOPES for row in rows)
            or any(not isinstance(row.get('features'), list)
                   or any(not isinstance(name, str) for name in row['features'])
                   or len(row['features']) != len(set(row['features'])) for row in rows)):
        raise ValueError('changed DUT partition index')
    return [row['nodeid'] for row in rows if row['scope'] == scope]


def pytest_addoption(parser):
    parser.addoption('--bpu-partition-index', type=Path)
    parser.addoption('--bpu-partition-sha256')
    parser.addoption('--bpu-write-partition', type=Path)
    parser.addoption('--bpu-dut-scope', choices=SCOPES)


def pytest_configure(config):
    config.addinivalue_line('markers', 'dut(name): unique generated DUT process owner')
    scope = config.getoption('bpu_dut_scope')
    if scope is not None and os.environ.get('BPUVERIFY_DUT_SCOPE') != scope:
        raise pytest.UsageError('DUT process scope must agree with the launcher environment')
    if scope is not None:
        if not config.option.collectonly and not config.getoption('toffee_output', default=None):
            raise pytest.UsageError('DUT-scoped execution requires toffee managed output')
        observe_process(config.rootpath)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    try:
        current = collection_index(items)
        scope = config.getoption('bpu_dut_scope')
        source = config.getoption('bpu_partition_index')
        if source is not None:
            raw = source.read_bytes()
            if sha256(raw).hexdigest() != config.getoption('bpu_partition_sha256'):
                raise ValueError('partition input hash changed')
            index = json.loads(raw)
            wanted = selected_ids(index, scope)
            if current != index:
                raise ValueError('current collection differs from the frozen complete partition')
            wanted_set = set(wanted)
            kept = [item for item in items if item.nodeid in wanted_set]
            discarded = [item for item in items if item.nodeid not in wanted_set]
            if [item.nodeid for item in kept] != wanted:
                raise ValueError('selected DUT collection changed')
            config.hook.pytest_deselected(items=discarded)
            items[:] = kept
        elif scope is not None:
            raise ValueError('DUT-scoped execution requires a frozen partition index')
        target = config.getoption('bpu_write_partition')
        if target is not None:
            if not config.option.collectonly or hasattr(config, 'workerinput'):
                raise ValueError('partition index is written only by serial collect-only')
            observe_process(config.rootpath)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x') as stream:
                json.dump(current, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise pytest.UsageError(str(error)) from error


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    config = session.config
    scope = config.getoption('bpu_dut_scope')
    if scope is None or config.option.collectonly:
        return
    snapshot = observe_process(config.rootpath)
    root = Path(config.getoption('toffee_output')) / 'processes'
    root.mkdir(exist_ok=True)
    worker = getattr(config, 'workerinput', {}).get('workerid', 'main')
    write_json(root / f'{worker}-{os.getpid()}.json', dict(
        scope=scope, pid=os.getpid(), worker=worker, snapshot=snapshot, pytest_exitstatus=int(exitstatus)))
