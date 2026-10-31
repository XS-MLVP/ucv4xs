"""Passive, bounded diagnostics for source adjudication; never changes verdicts.

Keep at most eight final public journal rows and 32 bus-event rows in memory.
Only on a real failure write one compact causal witness. No RTL/internal reads,
no changed stimulus, no altered reference predictions, no full-cycle trace.
"""
from collections import defaultdict, deque
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import re

import pytest

WINDOWS = defaultdict(lambda: defaultdict(lambda: deque(maxlen=8)))
EVENTS = defaultdict(lambda: deque(maxlen=32))
ACTORS = {}


def pytest_configure(config):
    from suites.memblock.lsq.evidence import Journal
    original = Journal.write

    def observed(self, value):
        result = original(self, value)
        if any(token in value for token in ('"before":', '"pre_observed":', '"observed":')):
            WINDOWS[self.nodeid][self.path.name].append(value)
            if re.search(r'"(?:response|ack|cache_response|uncache_response|uncache_ack_valid)": true', value):
                EVENTS[self.nodeid].append(value)
        return result

    Journal.write = observed
    from tests.lsq_wrapper.mixed_owners import MixedOwners
    original_drain = MixedOwners.drain

    async def observed_drain(self, *args, **kwargs):
        try:
            return await original_drain(self, *args, **kwargs)
        except BaseException:
            ACTORS[self.env.nodeid] = actor_state(self)
            raise

    MixedOwners.drain = observed_drain


def plain(value, depth=0):
    if depth > 12:
        return repr(value)[:200]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if is_dataclass(value):
        return plain(asdict(value), depth + 1)
    if isinstance(value, dict):
        return {str(key): plain(val, depth + 1) for key, val in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [plain(item, depth + 1) for item in value]
    return repr(value)[:300]


def selected_pins(values):
    return {pin: value for pin, value in values.items() if re.search(
        r"(?:uncache|cmoOp|toDCache|mmioStout|writeBack|ExceptionInfo|exceptionInfo|sbufferCtrl|flushSbuffer|sqDeqPtr|sqDeqCnt|deqPtrExtNext|rdataPtrMove|toLsqEnqCtrl_sqDeq|replay_|ldu_rar|ldu_raw|forward_|replayAllocate|Wakeup|bypass.*Resp|writeToSbuffer|sbuffer_req|physicalUpper|toPhysicalQueue)", pin)}


def project(text):
    try:
        row = json.loads(text)
    except ValueError:
        return dict(unparsed_tail=text[-4096:])
    out = {key: row[key] for key in ('nodeid', 'tick', 'pre_tick', 'post_tick', 'checked', 'error', 'input', 'inp') if key in row}
    for phase in ('before', 'after', 'pre_observed', 'observed'):
        if isinstance(row.get(phase), dict):
            out[phase] = selected_pins(row[phase])
    for phase in ('before', 'after'):
        actual, expected = row.get(phase), row.get('expected_' + phase)
        if isinstance(actual, dict) and isinstance(expected, dict):
            masks = row.get('masks_' + phase, {})
            out['difference_' + phase] = {pin: [actual[pin], value] for pin, value in expected.items()
                if pin in actual and (((actual[pin] ^ value) & masks.get(pin, -1))
                if isinstance(actual[pin], int) and isinstance(value, int) else actual[pin] != value)}
    if 'change' in row:
        def reduce(value):
            if not isinstance(value, dict):
                return value
            return {key: reduce(val) for key, val in value.items() if key not in ('before', 'unimplemented_outputs', 'old_entries', 'new_entries', 'perf')}
        out['reference_change_for_diagnosis_not_oracle'] = reduce(row['change'])
    return out


def actor_state(actor):
    out = dict(class_name=type(actor).__module__ + '.' + type(actor).__name__)
    for key in ('seed', 'fair', 'head', 'read', 'tail', 'sq_head', 'sq_tail', 'lq_head', 'lq_tail',
                'rob_tail', 'retired_order', 'planned_kind', 'settle', 'recovery', 'redirect_due',
                'pending', 'cache_job', 'p0', 'p1', 'p2', 'tails', 'waiting', 'stage1', 'stage2',
                'phase', 'counts', 'parts', 'finish_due', 'sbuffer_due', 'words', 'cbo_phase', 'io_phase'):
        value = getattr(actor, key, None)
        if value is not None and not callable(value):
            out[key] = plain(value)
    if hasattr(actor, 'program'):
        program = actor.program
        out['program_not_retired_or_incomplete'] = plain([{key: value for key, value in s.items()
            if key not in ('attempts', 'cache_resp', 'head_s3')} for s in program if not s['retired'] or not s['complete']][-180:])
        out['external_jobs'] = plain([dict(**{k: v for k, v in j.items() if k != 'owner'},
            owner_UID=j['owner']['uid'], owner_order=j['owner']['order'], owner_subtype=j['owner']['subtype']) for j in actor.jobs])
    for key in ('owners', 'live'):
        if hasattr(actor, key):
            out[key] = plain(getattr(actor, key))
    return out


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != 'call' or not report.failed:
        return
    path = Path(item.funcargs['tmp_path']) / 'source-review-failure.json'
    objects, locals_kept, ids = [], [], set()
    tb = call.excinfo.value.__traceback__
    while tb:
        frame = tb.tb_frame
        if '/lsq/' in frame.f_code.co_filename:
            kept = {}
            for key in ('answer', 'job', 'owner', 'seg', 'old_owner', 'req', 'snapshot', 'inp', 'request', 'expected', 'actual', 'difference'):
                if key in frame.f_locals and key not in ('actual', 'expected'):
                    val = frame.f_locals[key]
                    if isinstance(val, dict) and len(val) > 500:
                        val = selected_pins(val)
                    kept[key] = plain(val)
            if kept:
                locals_kept.append(dict(file=frame.f_code.co_filename, line=tb.tb_lineno, function=frame.f_code.co_name, locals=kept))
            for key in ('self', 'actor', 'agent', 'trace'):
                obj = frame.f_locals.get(key)
                if obj is not None and id(obj) not in ids and type(obj).__module__.startswith(('lsqverify.', 'tests.')):
                    if hasattr(obj, 'program') or hasattr(obj, 'owners') or hasattr(obj, 'stage2') or hasattr(obj, 'words') or hasattr(obj, 'live'):
                        ids.add(id(obj)); objects.append(actor_state(obj))
        tb = tb.tb_next
    forward_diagnostics = []
    for name, obj in item.funcargs.items():
        model = getattr(obj, 'model', None)
        if model is None:
            continue
        if hasattr(model, 'store'):
            model = model.store
        if hasattr(model, 'physical'):
            model = model.physical
        if hasattr(model, 'forward'):
            model = model.forward
        if type(model).__name__ == 'ForwardModel':
            forward_diagnostics.append(dict(fixture=name, stage2=plain(model.stage2)))
    result = dict(format='lsq-source-adjudication-bounded-failure-v1', nodeid=item.nodeid,
        original_exception=repr(call.excinfo.value),
        last_public_windows={name: [project(value) for value in rows] for name, rows in WINDOWS.pop(item.nodeid, {}).items()},
        last_external_response_events=[project(value) for value in EVENTS.pop(item.nodeid, ())],
        traceback_locals_for_diagnosis=locals_kept, external_actor_or_reference_state_for_diagnosis=objects,
        external_mixed_actor_at_timeout=ACTORS.pop(item.nodeid, None),
        forward_public_input_ledger_for_diagnosis=forward_diagnostics,
        scope='Bounded first-failure public evidence and external ledger only; references are diagnostic, not correctness authority. No stimulus/prediction/assertion/outcome changed.')
    with path.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
