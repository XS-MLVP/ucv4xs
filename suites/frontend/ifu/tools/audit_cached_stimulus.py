"""Compare planned cached windows against a frozen pre-migration test module.

This executes pure scenario generators with model-backed stand-ins. It is NOT a
native input trace, a hardware run, or checking-chain evidence. Four one-window
manual scenarios stop at the first runtime operation after constructing their
window; that boundary and their unexecuted timing are reported explicitly.
"""
import argparse
import ast
import asyncio
from dataclasses import asdict, replace
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from suites.frontend.ifu import ROOT
from suites.frontend.ifu.ifu.checker import cached_expectation, expected_redirect
from suites.frontend.ifu.ifu.types import Enqueue, FetchRequest, FetchResult, Frame, GpaWrite
from suites.frontend.ifu.model.fetch import aligned_lanes
from suites.frontend.ifu.model.pred_checker import DIRECT, POP
from suites.frontend.ifu.model.trigger import Inputs as TriggerInputs, Trigger, TriggerModel, Update


MANUAL = {
    'test_ibuffer_backpressure_holds_the_beat',
    'test_backend_redirect_discards_the_inflight_fetch',
    'test_bpu_stage3_flush_drops_the_window',
    'test_second_block_ecc_corruption_is_attached_there',
}


class RuntimeBoundary(Exception):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GeneratorStandIn:
    def __init__(self, module, manual):
        self.windows, self.records = [], []
        self.pointer, self.manual = 0, manual
        self.trigger = TriggerModel()
        builder = module.build_window

        def record(*args, **kwargs):
            window = builder(*args, **kwargs)
            self.windows.append(asdict(window))
            return window

        module.build_window = record

    def reset(self):
        self.pointer = 0
        self.trigger = TriggerModel()

    reset_once = reset

    def step(self, cycles):
        if self.manual:
            raise RuntimeBoundary()

    def read(self, name):
        return 0  # Only the old unused foldpc read reaches this stand-in.

    def set(self, **values):
        if self.manual:
            raise RuntimeBoundary()
        # The only non-manual raw setup in these cached bodies is trigger0.
        if values.get('io_frontendTrigger_tUpdate_valid'):
            self.trigger.tick(TriggerInputs(update=Update(1, 0, Trigger(action=1,
                tdata2=values['io_frontendTrigger_tUpdate_bits_tdata_tdata2'])), enable=(1, 0, 0, 0)))

    def old_fetch(self, harness, window, *, corrupt_after_accept=0, **controls):
        effective = replace(window, exc0=5) if corrupt_after_accept else window
        expected, prediction, *_ = aligned_lanes(effective, self.pointer & 3)
        values = asdict(expected)
        if controls.get('trigger'):
            values['triggered'] = self.trigger.lane_actions(
                TriggerInputs(enable=(1, 0, 0, 0), can_raise_breakpoint=0), tuple(expected.pcs))
        values['valid'] = values.pop('valid_mask')
        values['end_off'] = values.pop('end_offsets')
        values['pred'] = values.pop('pred_taken')
        values['exception_cross'] = values.pop('exception_cross_page')
        for old, new in [('gp_addr_wen', 'gp_wen'), ('gp_addr', 'gp_addr'), ('gp_ftq', 'gp_ftq'), ('gp_for_vs', 'gp_for_vs')]:
            values[new] = values.pop(old)
        fault = prediction.redirect
        redirect = None
        if fault.valid:
            block = int(bool(fault.block_sel or fault.is_cross_block))
            redirect = dict(valid=1, ftq=window.ftq1 if block else window.ftq0,
                pc=window.start1_pc if block else window.start0_pc, target=fault.target,
                taken=fault.taken, offset=fault.end_offset, is_rvc=fault.is_rvc,
                branch_type=fault.branch_type, ras_action=fault.ras_action,
                can_train=int(fault.branch_type == DIRECT or bool(fault.ras_action & POP)
                    or fault.invalid_taken or fault.not_cfi_taken))
        if window.taken0_valid and window.half0:
            values['valid'] = values['enq'] = 0
        self.pointer += values['enq'].bit_count()
        return values, redirect

    async def fetch(self, item, *, frame=Frame(), corruption=(0, 0, 0, 0)):
        w = item.window
        item = replace(item, window=replace(w, exc0=w.exc0 or (5 if any(corruption[:2]) else 0),
                                          exc1=w.exc1 or (5 if any(corruption[2:]) else 0)))
        shift = self.pointer & 3
        expected = cached_expectation(item, shift)[0]
        actions = self.trigger.lane_actions(frame.trigger, tuple(expected.pcs))
        beat = Enqueue(expected.valid_mask, expected.enq, tuple(expected.instrs), tuple(expected.is_rvc),
            tuple(expected.foldpc), tuple(expected.ftq), tuple(expected.end_offsets), tuple(expected.pred_taken),
            expected.prev_count, expected.exception_type, expected.exception_mask, expected.exception_cross_page,
            expected.is_backend_exception, expected.has_satp_flush, tuple(actions))
        gpa = GpaWrite(expected.gp_ftq, expected.gp_addr, expected.gp_for_vs) if expected.gp_addr_wen else None
        self.records.append(SimpleNamespace(shift=shift))
        self.pointer += expected.enq.bit_count()
        return FetchResult(len(self.records), beat, expected_redirect(item, shift), gpa)

    async def idle(self, cycles=1, *, frame=Frame()):
        for _ in range(cycles):
            self.trigger.tick(frame.trigger)

    async def cycle(self, frame=Frame()):
        raise RuntimeBoundary()


def canonical(windows):
    normalized = json.loads(json.dumps(windows))
    for w in normalized:
        w['ftq0'][0] &= 1
        w['ftq1'][0] &= 1
        for instruction in w['instructions']:
            instruction['ftq_flag'] &= 1
    return normalized


async def collect(path, name, rs1, *, migrated):
    module = load(path, 'cached_stimulus_' + ('after' if migrated else 'before'))
    stand_in = GeneratorStandIn(module, name in MANUAL)
    if migrated:
        async def reset():
            GeneratorStandIn.reset(stand_in)
        stand_in.reset = reset
    else:
        module.fetch = stand_in.old_fetch
    kwargs = {'rs1': rs1} if rs1 is not None else {}
    stopped = False
    try:
        answer = getattr(module, name)(stand_in, **kwargs)
        if inspect.isawaitable(answer):
            await answer
    except RuntimeBoundary:
        stopped = True
    if name in MANUAL:
        assert len(stand_in.windows) == 1 and (migrated or stopped), (name, len(stand_in.windows), stopped)
    else:
        assert not stopped, name
    return stand_in.windows, stopped


async def audit(before):
    after = ROOT / 'tests/ifu/test_ifu_fetch.py'
    old_tree, new_tree = ast.parse(before.read_text()), ast.parse(after.read_text())
    helpers = ('dense_compressed', 'random_compressed', 'build_cfi_window')
    helper_proofs = {}
    for helper in helpers:
        old = next(node for node in old_tree.body if isinstance(node, ast.FunctionDef) and node.name == helper)
        new = next(node for node in new_tree.body if isinstance(node, ast.FunctionDef) and node.name == helper)
        assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False), helper
        helper_proofs[helper] = hashlib.sha256(ast.dump(new, include_attributes=False).encode()).hexdigest()
    names = [node.name for node in new_tree.body if isinstance(node, ast.AsyncFunctionDef)
             and node.name.startswith('test_') and not node.name.startswith('test_uncache')]
    rows = []
    for name in names:
        variants = (0, 6) if name == 'test_recovered_half_instruction_keeps_its_completing_ftq_block' else (None,)
        for rs1 in variants:
            old, stopped_old = await collect(before, name, rs1, migrated=False)
            new, stopped_new = await collect(after, name, rs1, migrated=True)
            normalized_old, normalized_new = canonical(old), canonical(new)
            assert normalized_old == normalized_new, (name, rs1)
            changed = [index for index, (a, b) in enumerate(zip(old, new)) if digest(a) != digest(b)]
            rows.append(dict(test=name, rs1=rs1, windows=len(new), before_sha256=digest(old), after_sha256=digest(new),
                canonical_equal=True, canonical_sha256=digest(normalized_new), changed_ftq_flag_windows=changed,
                manual_runtime_boundary=stopped_old or stopped_new))
    return dict(schema=1, scope='pure planned-window generator differential, NOT native simulation or observed-port trace',
        before=str(before), after=str(after), helper_normalized_ast=helper_proofs, rows=rows,
        case_bodies=len(names), variants=len(rows), planned_windows=sum(row['windows'] for row in rows),
        normalization='Only illegal legacy FTQ flag2/3 becomes its explicit 1-bit low bit, including instruction identity; no other field normalization.',
        timing_limit='Four manual one-window bodies stop at their first runtime operation; ECC/flush/backpressure timing is covered separately by actual native regressions.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(audit(args.before)), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
