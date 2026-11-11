"""Executable source-family x response-domain inventory for the 2026-11-03 extension.

Bindings are obligations, NEVER static PASS. resolve() needs actual case verdicts;
semantic reached/checked coverage must additionally be reviewed in that run.
No exception/refill is invented for a predictor interface without that channel.
"""
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import PAYLOAD_CASES
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import RESIDENCY_CASES
from suites.frontend.bpu.testbenches.bpu.model.redirect_matrix import REDIRECT_CASES
from suites.frontend.bpu.testbenches.ras.model.guarded_lifetime import CFI_BYTES


SOURCE_FAMILIES = {
    'conditional': ('BranchUnit + ResolveQueue', 'taken/NT; sequential NT successor; type may correct a prediction'),
    'direct': ('IFU PredChecker / JAL', 'taken target, none/call action; wrong prediction may be invalidated'),
    'indirect': ('IFU/resolve JALR', 'target correction, none/call/return/pop-push hints'),
    'none': ('IFU false-CFI correction', 'branchType=None, taken=false; canTrain must remain true'),
    'lookup': ('Bpu speculative fetch', 'guarded PC, reset, enable, fire/hold/flush'),
    'recovery': ('FTQ original redirect metadata', 'original checkpoint, real guarded CFI, taken/NT'),
    'retirement': ('FTQ commit original metadata', 'original RAS action and checkpoint, not fresh lookup'),
}
DUT_RESPONSIBILITIES = {
    'bpu': 'speculative selection/repair/metadata; public target/perf DCE boundary remains open',
    'mbtb': 'branch payload/direction, Main/Victim ownership and training provenance',
    'ras': 'speculative/recovery/retirement stack state, guarded return lifetime',
    'ubtb': 'early target lookup and final-result learning; existing cases not extended here',
    'abtb': 'ahead target/replacement/learning; existing nonPASS not waived',
    'utage': 'early conditional direction/useful/shadow; missing parent probes still gaps',
    'tage': 'tagged conditional provider/useful/allocation; prior migration XFAIL remains',
    'sc': 'direction correction weights/threshold; parent role matrix blocked by legacy PHR shape',
    'ittage': 'indirect target/confidence and original provider ownership',
    'uras': 'early return peek and parent enable; historical failures remain',
}
DOMAINS = ('clean', 'correction', 'capacity-miss', 'cancel-or-overlap', 'external-fault')


def bound(nodeids):
    return dict(nodeids=tuple(nodeids), reason='Requires actual verdict AND reached/checked evidence, not collection credit.')


def gap(missing, next_action):
    return dict(status='gap', missing=missing, next_action=next_action)


def external():
    return dict(status='out-of-domain', reason='No bus error/refill/translation result channel on predictor interface.',
                owner='IFU/ICache/MMU; not verified by this BPU update')


PAYLOAD_TEST = 'testbenches/mbtb/tests/testcase/test_mbtb_learning_matrix.py::test_resolved_not_taken_preserves_owned_payload_and_neighbor'
RESIDENCY_TEST = 'testbenches/mbtb/tests/testcase/test_mbtb_learning_matrix.py::test_delayed_original_victim_feedback_rechecks_current_residency'
REDIRECT_TEST = 'testbenches/bpu/tests/testcase/test_bpu_redirect_matrix.py::test_guarded_recovery_keeps_original_history_and_fresh_consumer'
RAS_TEST = 'testbenches/ras/tests/testcase/test_ras_guard_lifetime.py::test_guarded_restored_return_survives_younger_call_and_pop'

# Deliberately explicit keys: extending a model's family registry without
# updating this inventory fails the matrix selftest (no fallback "other").
MATRIX = {
    'guarded-stack-lifetime': {
        'source': 'recovery',
        'clean': bound(f'{RAS_TEST}[{pc}]' for pc in CFI_BYTES),
        'correction': bound(f'{RAS_TEST}[{pc}]' for pc in CFI_BYTES),
        'capacity-miss': gap('Guard recovery not crossed with speculative/committed stack capacity.', 'Use original overflow/repeat histories with each guarded PC.'),
        'cancel-or-overlap': gap('No guarded commit or same-cycle redirect/retirement cross.', 'Retire original actions around recovery and check retained committed cells.'),
        'external-fault': external(),
    },
    **{mode: {
        'source': 'none' if mode == 'false-hit' else 'conditional',
        'clean': gap('No separate clean sample for this correction property.', 'Use adjacent existing MainBTB correct-feedback controls.'),
        'correction': bound(f'{PAYLOAD_TEST}[{c.label}]' for c in PAYLOAD_CASES if c.mode == mode),
        'capacity-miss': gap('Payload correction under full pending capacity not crossed.', 'Construct full retained entries and independent neighbor witnesses.'),
        'cancel-or-overlap': gap('New NT/type transition not crossed with cancellation and read pressure.', 'Cross accepted/queued feedback with reset, enable and lookup service boundaries.'),
        'external-fault': external(),
    } for mode in ('cold-nt', 'conditional-nt', 'reclassified-nt', 'false-hit')},
    **{mode: {
        'source': 'indirect',
        'clean': bound(f'{RESIDENCY_TEST}[{c.label}]' for c in RESIDENCY_CASES if c.mode == mode),
        'correction': bound(f'{RESIDENCY_TEST}[{c.label}]' for c in RESIDENCY_CASES if c.mode == mode),
        'capacity-miss': (bound(f'{RESIDENCY_TEST}[{c.label}]' for c in RESIDENCY_CASES if c.mode == mode)
                          if mode == 'evicted' else gap('Resident control does not pressure capacity.', 'Compare evicted row under normal allocations.')),
        'cancel-or-overlap': gap('Residency transition concurrent with snapshot/feedback not separately driven.', 'Bracket accepted training vs eviction insertion and read-priority service.'),
        'external-fault': external(),
    } for mode in ('resident', 'evicted')},
    **{history: {
        'source': 'recovery',
        'clean': bound(f'{REDIRECT_TEST}[{c.label}]' for c in REDIRECT_CASES if c.history == history),
        'correction': bound(f'{REDIRECT_TEST}[{c.label}]' for c in REDIRECT_CASES if c.history == history),
        'capacity-miss': gap('No long-ring/wrap checkpoint lifetime cross.', 'Build normal histories past PHR physical wrap before the guarded redirect.'),
        'cancel-or-overlap': gap('Active predictor learning/S2-S3 arbitration not crossed.', 'Use producer-owned Main learning and same-cycle repair/redirect witnesses.'),
        'external-fault': external(),
    } for history in ('empty', 'nonzero')},
}
UNCLASSIFIED = (
    dict(input='type-correction full FTQ reachability', missing='Module resolve contract is known; complete instruction/FTQ history not constructed.', next_action='Build IFU/FTQ producer history; keep port-only credit until then.'),
    dict(input='remaining seven leaf predictor input/outcome crosses', missing='This extension inventories responsibility but does not requalify their existing full matrices.', next_action='Use per-DUT contracts and outstanding nonPASS before adding classes.'),
    dict(input='guarded target API outside pipeline49 target model', missing='Public API is 50 bits but composed target/reset model remains 49 bits.', next_action='Prove address-domain producer mapping and widen independent selection models before claiming coverage.'),
)


def validate(matrix=MATRIX):
    from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import PAYLOAD_KINDS
    from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import RESIDENCY_KINDS
    from suites.frontend.bpu.testbenches.bpu.model.redirect_matrix import HISTORY_KINDS
    from suites.frontend.bpu.testbenches.ras.model.guarded_lifetime import LIFETIME_KINDS
    if set(matrix) != set(PAYLOAD_KINDS + RESIDENCY_KINDS + HISTORY_KINDS + LIFETIME_KINDS):
        raise ValueError('new model class requires an explicit matrix row')
    for row in matrix.values():
        if row['source'] not in SOURCE_FAMILIES or set(row) != {'source', *DOMAINS}:
            raise ValueError('missing source or response domain')
        for domain in DOMAINS:
            cell = row[domain]
            if 'nodeids' in cell:
                if not cell['nodeids'] or len(set(cell['nodeids'])) != len(cell['nodeids']):
                    raise ValueError('bound outcome needs unique actual tests')
            elif cell.get('status') == 'gap':
                if not cell.get('missing') or not cell.get('next_action'):
                    raise ValueError('gap requires missing evidence and next experiment')
            elif cell.get('status') not in ('na', 'out-of-domain') or not cell.get('reason'):
                raise ValueError('unproved outcome cannot be a static PASS')


def resolve(verdicts):
    validate()
    rows = {}
    for name, row in MATRIX.items():
        rows[name] = {'source': row['source']}
        for domain in DOMAINS:
            cell = row[domain]
            if 'nodeids' not in cell:
                rows[name][domain] = dict(cell)
                continue
            selected = {node: verdicts.get(node, 'NOT_RUN') for node in cell['nodeids']}
            status = ('fail' if any(v in ('FAIL', 'ERROR', 'XPASS') for v in selected.values()) else
                      'pass' if all(v == 'PASS' for v in selected.values()) else 'gap')
            rows[name][domain] = dict(status=status, verdicts=selected,
                limit='Case verdict is not proof of reached/checked; audit the native functional reports too.')
    return rows
