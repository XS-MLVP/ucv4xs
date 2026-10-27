"""UTAGE address contexts must check normally without default trace exports."""
import gzip
import json
from types import SimpleNamespace

import pytest

from bpuverify.common.env.trace import trace_exports
from bpuverify.utage.case.useful_address_scenario import UsefulContext


@pytest.mark.parametrize('enabled', (False, True))
@pytest.mark.parametrize('failure', (None, 'body', 'summary'))
async def test_address_context_trace_is_opt_in_without_suppressing_live_checks(tmp_path, enabled, failure):
    calls = []
    error = AssertionError('live checker mismatch')
    async def close(kind, caught, traceback):
        calls.append(('close', kind, caught))
    def summary():
        calls.append(('summary',))
        if failure == 'summary':
            raise error
        return dict(cycles=2, accepted=1, checked=True)
    context = UsefulContext.__new__(UsefulContext)
    context.stack = SimpleNamespace(__aexit__=close)
    context.checker = SimpleNamespace(summary=summary, records=[dict(tick=1), dict(tick=2)])
    context.name, context.index, context.mode = 'upper-update', 7, 'adjacent'
    context.output = tmp_path / 'not-created-unless-requested'
    context.predictions, context.operations = [], []
    context.shadow = None
    body_error = error if failure == 'body' else None
    with trace_exports(enabled):
        if failure == 'summary':
            with pytest.raises(AssertionError, match='live checker mismatch'):
                await context.__aexit__(None, None, None)
        else:
            await context.__aexit__(type(error) if body_error else None, body_error, None)
    assert calls[0] == ('close', type(error) if body_error else None, body_error)
    assert len(calls) == (1 if failure == 'body' else 2)
    if not enabled:
        assert list(tmp_path.iterdir()) == []
    else:
        path = context.output / 'upper-update-007-adjacent.json.gz'
        assert list(context.output.iterdir()) == [path]
        with gzip.open(path, 'rt') as stream:
            result = json.load(stream)
        assert result['passive_trace'] == context.checker.records
        assert result['failure'] == (repr(error) if failure else None)
        assert result['summary'] == (None if failure else dict(cycles=2, accepted=1, checked=True))


async def test_disabled_address_trace_does_not_serialize_state(tmp_path):
    async def close(*args):
        return None
    context = UsefulContext.__new__(UsefulContext)
    context.stack = SimpleNamespace(__aexit__=close)
    context.checker = SimpleNamespace(summary=lambda: dict(checked=True), records=[object()])
    context.name, context.index, context.mode = 'lower-update', 0, 'serial'
    context.output, context.shadow = tmp_path / 'unused', None
    context.predictions, context.operations = [object()], [object()]
    await context.__aexit__(None, None, None)
    assert list(tmp_path.iterdir()) == []
