"""Fixed checker-only vectors; not producer/native coverage evidence."""
from dataclasses import fields, replace

from suites.frontend.ftq.ftq.bundle.abi import redirect_meta, resolve_meta
from suites.frontend.ftq.ftq.checker.frontend import FtqFrontend, Installed
from suites.frontend.ftq.ftq.checker.redirect import RedirectInput
from suites.frontend.ftq.ftq.checker.training import Cached, Entry, Report
from suites.frontend.ftq.ftq.transaction.cycle import FtqInput
from suites.frontend.ftq.ftq.transaction.types import (
    BackendRedirect, BackendWrite, FetchLane, FetchRequest, FlushEvent, Owner,
    Pointers, Prediction, PrefetchLane, PrefetchRequest, RedirectEvent, Topdown, TrainingEntry)
from suites.frontend.ftq.resolve_queue.transaction.types import Branch


def composition(*, redirect=False):
    model = FtqFrontend()
    model.bpu = model.pnr = 2
    model.entries[0] = Installed((0, 1, 1), 0, Prediction(0), 2, (0, 1, 1))
    model.entries[1] = Installed((0, 2, 2), 1, Prediction(16), 4, (0, 2, 2))
    reports = (Report((0, 3, 'resolve', 0), 0, 0x100, Branch(2, 0x900, 1, 1, 1, 0)),
               Report((0, 3, 'resolve', 1), 0, 0x100, Branch(5, 0x901, 0, 0, 1, 0)),
               Report((0, 3, 'resolve', 2), 0, 0x100, Branch(1, 0x902, 1, 0, 3, 2)))
    metadata = {name: (1 << width) - 1 for name, width in resolve_meta().items()}
    training = TrainingEntry(0x100, (0x100, 0x100, 0x100, 0x110),
        (reports[0].branch, reports[2].branch), 1023, 65535, 1, 5, metadata)
    model.training.cache = Cached(Entry(0, 0x100, list(reports)), training, True, (reports[0], reports[2]))
    frame = FtqInput(prediction=Prediction(64, s2_override=1, s3_override=1, s2_ptr=0, s3_ptr=1))
    data = {
        'ftq.owners': Pointers(Owner(0, 2), (Owner(0, 0), Owner(0, 1)),
                              (Owner(0, 0), Owner(0, 1)), Owner(0, 0), Owner(0, 2)),
        'ftq.backend_write': BackendWrite(True, 1, 64, True, Owner(0, 2)),
        'ftq.flush': FlushEvent(True, 0, 0, True, 0, 1, False, False, True, 0, 1),
        'ftq.redirect': None,
        'ftq.training': training,
        'ftq.prefetch': PrefetchRequest(True, 0, 32, 0, 1, False, 0, 0, 0, 1, 16, 1,
            (PrefetchLane(0, 32, 0, 1, False, Owner(0, 0)), PrefetchLane(16, 48, 0, 1, False, Owner(0, 1)))),
        'ftq.fetch': FetchRequest(True, True, 0, 0, 32, 0, 0, 1, 3, 1, 0, False, False, 1,
            (FetchLane(0, 32, 0, 1, 1, 3, 1, 0, Owner(0, 0)), FetchLane(16, 48, 0, 1, 1, 3, 16, 0, Owner(0, 1)))),
        'ftq.topdown': Topdown(dict.fromkeys((2, 3, 5, 6, 7, 8, 9), False), False, False, False, False, False, False),
    }
    if redirect:
        event = RedirectInput((0, 0, 'backend'), 'backend',
            BackendRedirect(0, pc=0x200, offset=1, target=0x1200, branch_type=3, debug_ctrl=1), 0x900)
        model.receivers.pending_backend = event
        stored = {key: (1 << width) - 1 for key, width in redirect_meta(with_target=False).items()}
        model.receivers.read_meta = {'redirectMeta_' + key: value for key, value in stored.items()}
        data['ftq.redirect'] = RedirectEvent(0x101, 0x900, 1, 3, 0, 1023, 65535, stored)
        data['ftq.backend_write'] = replace(data['ftq.backend_write'], wen=False)
        data['ftq.prefetch'] = replace(data['ftq.prefetch'], valid=False)
        data['ftq.fetch'] = replace(data['ftq.fetch'], valid=False)
        data['ftq.flush'] = replace(data['ftq.flush'], redirect_flush=True, to_ifu_redirect=True)
        data['ftq.topdown'] = replace(data['ftq.topdown'], backend_redirect=True, control_flow=True, ittage_miss=True)
    return model, frame, data


def mutations():
    rows = []
    for channel in ('backend_write', 'flush', 'prefetch', 'fetch', 'training'):
        value = composition()[2]['ftq.' + channel]
        for field in fields(value):
            if type(getattr(value, field.name)) in (int, bool):
                rows.append((channel, field.name, False))
    for field in fields(composition(redirect=True)[2]['ftq.redirect']):
        if field.name != 'metadata':
            rows.append(('redirect', field.name, True))
    rows.extend(('training', 'metadata.' + name, False) for name in resolve_meta())
    rows.extend(('redirect', 'metadata.' + name, True) for name in redirect_meta(with_target=False))
    for lane in range(2):
        for channel in ('prefetch', 'fetch'):
            value = composition()[2]['ftq.' + channel].lanes[lane]
            rows.extend((channel, f'lane{lane}.{field.name}', False) for field in fields(value) if field.name != 'owner')
            rows.extend((channel, f'lane{lane}.owner.{name}', False) for name in ('flag', 'value'))
        rows.extend(('training', f'branch{lane}.{field.name}', False) for field in fields(Branch(0, 0, 0, 0, 0, 0)))
    rows.extend(('training', f'vector{index}', False) for index in range(4))
    rows.extend(('topdown', f'reason{index}', False) for index in (2, 3, 5, 6, 7, 8, 9))
    rows.extend(('topdown', name, True) for name in ('backend_redirect', 'control_flow', 'memory_violation', 'tage_miss', 'ittage_miss', 'ras_miss'))
    rows.extend(('backend_write', 'bpu.' + name, False) for name in ('flag', 'value'))
    rows.extend(('flush', name, True) for name in ('redirect_flush', 'to_ifu_redirect'))
    return rows


def corrupt(value, path):
    if path.startswith('metadata.'):
        payload = dict(value.metadata)
        key = path.removeprefix('metadata.')
        payload[key] ^= 1
        return replace(value, metadata=payload)
    if path.startswith('lane'):
        prefix, inner = path.split('.', 1)
        index = int(prefix[4:])
        lanes = list(value.lanes)
        if inner.startswith('owner.'):
            name = inner.removeprefix('owner.')
            lanes[index] = replace(lanes[index], owner=replace(lanes[index].owner, **{name: getattr(lanes[index].owner, name) ^ 1}))
        else:
            lanes[index] = replace(lanes[index], **{inner: getattr(lanes[index], inner) ^ 1})
        return replace(value, lanes=tuple(lanes))
    if path.startswith(('branch0.', 'branch1.')):
        prefix, name = path.split('.', 1)
        index = int(prefix[6:])
        branches = list(value.branches)
        branches[index] = replace(branches[index], **{name: getattr(branches[index], name) ^ 1})
        return replace(value, branches=tuple(branches))
    if path.startswith('vector'):
        index = int(path[6:])
        vector = list(value.start_pc_vec)
        vector[index] ^= 1
        return replace(value, start_pc_vec=tuple(vector))
    if path.startswith('reason'):
        reasons = dict(value.reasons)
        reasons[int(path[6:])] ^= 1
        return replace(value, reasons=reasons)
    if path.startswith('bpu.'):
        name = path.removeprefix('bpu.')
        return replace(value, bpu=replace(value.bpu, **{name: getattr(value.bpu, name) ^ 1}))
    return replace(value, **{path: getattr(value, path) ^ 1})
