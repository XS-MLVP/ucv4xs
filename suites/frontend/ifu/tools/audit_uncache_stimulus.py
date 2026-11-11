"""Compare frozen old producer bodies with the byte-address transaction migration.

This is a pure planned-stimulus audit, not native sampling or RTL correctness.
The before directory must be an explicitly supplied, hash-indexed local snapshot.
"""
import argparse
import ast
import asyncio
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from suites.frontend.ifu import ROOT
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Inputs
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import UncacheModel
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import WAIT_RESP
from suites.frontend.ifu.testbenches.uncache_unit.env.ledger import RequestLedger
from suites.frontend.ifu.testbenches.uncache_unit.transactions import ReadRequest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Frozen snapshots may predate the module layout. Keep both names so old
# receipts retain their original keys and hashes.
LEGACY_PATHS = {
    'modules/uncache_unit/model/uncache.py': 'model/uncache.py',
    'modules/uncache_unit/tests/test_uncache_unit.py': 'tests/uncache_unit/test_uncache_unit.py',
}


def snapshot_file(before, frozen, name):
    """Resolve a frozen file by its current or historical relative name."""
    for candidate in (name, LEGACY_PATHS[name]):
        if candidate in frozen['frozen_files'] and (before / candidate).is_file():
            return candidate, before / candidate
    raise AssertionError(f'missing frozen file: {name}')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PlannedRecorder:
    def __init__(self):
        self._model, self._ledger = UncacheModel(), RequestLedger()
        self._tick = 0
        self.rows, self.additional_controls = [], []

    @property
    def status(self):
        return self._ledger.snapshot(self._model.phase)

    async def reset(self, *, reason=None):
        self.additional_controls.append(dict(operation='reset', reason=reason))
        self._ledger.reset(self._tick, reason or 'independent scenario reset')
        self._model = UncacheModel()

    async def cancel_pending(self, reason):
        self.additional_controls.append(dict(operation='explicit_cancel', reason=reason))
        return self._advance(Inputs(flush=1, to_ready=0), primary=False, reason=reason)

    async def characterize_cycle(self, inputs):
        return self._advance(inputs, primary=True)

    def _advance(self, inputs, *, primary, reason='explicit port-pressure flush'):
        if primary:
            row = asdict(inputs)
            row['req_paddr'] >>= 1
            self.rows.append(row)
        uid = self._ledger.offer(ReadRequest(inputs.req_paddr, inputs.req_is_mmio, inputs.req_pbmt),
                                 'port-characterization') if inputs.req_valid else None
        response_uid = self._ledger.active_uid if inputs.from_valid and self._model.phase == WAIT_RESP else None
        before = self._model.outputs(inputs)
        self._model.tick(inputs)
        after = self._model.outputs(inputs)
        self._tick += 2
        events = self._ledger.consume(inputs, before, after, self._tick, uid, response_uid, reason)
        return SimpleNamespace(before=before, after=after, events=events, status=self.status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refuse to overwrite an existing evidence output')
    frozen = json.loads((args.before / 'before.json').read_text())
    frozen_paths = {}
    for name in ('modules/uncache_unit/model/uncache.py', 'modules/uncache_unit/tests/test_uncache_unit.py'):
        key, path = snapshot_file(args.before, frozen, name)
        assert sha(path) == frozen['frozen_files'][key], f'changed before snapshot: {key}'
        frozen_paths[name] = path
    old_model = load(frozen_paths['modules/uncache_unit/model/uncache.py'], 'ifu_uncache_frozen_oracle')
    old = load(frozen_paths['modules/uncache_unit/tests/test_uncache_unit.py'], 'ifu_uncache_frozen_cases')
    old.Inputs, old.UncacheModel = old_model.Inputs, old_model.UncacheModel
    current = load(ROOT / 'testbenches/uncache_unit/tests/test_uncache_unit.py', 'ifu_uncache_current_cases')
    old_rows = []

    def old_cycle(harness, model, inputs):
        old_rows.append(asdict(inputs))
        observed = old.expected_dict(model.outputs(inputs))
        model.tick(inputs)
        return observed

    old.cycle = old_cycle
    old.start = lambda harness: old_model.UncacheModel()
    rows = []
    for name in sorted(name for name in vars(old) if name.startswith('test_')):
        old_rows.clear()
        getattr(old, name)(SimpleNamespace(reset=lambda: None))
        recorder = PlannedRecorder()
        asyncio.run(getattr(current, name)(recorder))
        assert old_rows == recorder.rows, f'changed physical primary inputs: {name}'
        rows.append(dict(nodeid='testbenches/uncache_unit/tests/test_uncache_unit.py::' + name,
            primary_requests=len(old_rows), ordered_physical_inputs_unchanged=True,
            primary_input_sha256=hashlib.sha256(json.dumps(old_rows, sort_keys=True).encode()).hexdigest(),
            added_explicit_controls=recorder.additional_controls))

    def oracle(tree):
        return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'UncacheModel')

    before_ast = ast.dump(oracle(ast.parse(frozen_paths['modules/uncache_unit/model/uncache.py'].read_text())), include_attributes=False)
    current_ast = ast.dump(oracle(ast.parse((ROOT / 'testbenches/uncache_unit/model/uncache.py').read_text())), include_attributes=False)
    assert before_ast == current_ast, 'independent FSM/comparison expectation changed'
    result = dict(scope='Pure planned producer-body equivalence, not native sampling or hardware credit.',
        original_test_bodies=len(rows), primary_requests=sum(row['primary_requests'] for row in rows),
        original700_preserved=any('test_random_sequences_' in row['nodeid'] and row['primary_requests'] == 700 for row in rows),
        ordered_physical_inputs_unchanged=True, oracle_class_normalized_ast_unchanged=True,
        address_normalization='Old raw47-bit coordinates become48-bit aligned byte addresses; ports alone shift to/from47 wires.',
        auxiliary_scope='New explicit cancels reconcile original partial scenarios; resets preserve UID history. These controls are additional and are not included in primary-stimulus equivalence.',
        tests=rows)
    assert result['original700_preserved']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'tests'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
