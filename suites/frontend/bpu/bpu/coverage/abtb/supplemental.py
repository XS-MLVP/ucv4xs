"""Physical counter coverage from complete, reset-derived observations.

The denominator describes the compiled MiniConfig, not the addresses a test
happened to use. Inputs, metadata registers and all counter/PLRU states are
replayed before any bin is committed. Cached transition lists are not evidence.
This complements the live PHR/transaction checker; it does not replace it or
claim an independent model of SRAM allocation/write-response generation.
"""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path
from suites.frontend.bpu.coverage.replay import CoverageReplay
from collections import Counter
from functools import lru_cache
from heapq import merge
from types import SimpleNamespace

from toffee import Bin
from toffee import CheckContext
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.abtb.model.state.counter import CounterReference
from suites.frontend.bpu.abtb.model.state.counter import coordinates
from suites.frontend.bpu.abtb.model.state.counter import index
from suites.frontend.bpu.abtb.model.state.counter import victim
from suites.frontend.bpu.bpu.model.sc.model import canonical
from suites.frontend.bpu.bpu.case.abtb.provenance import MetadataPipeline
from suites.frontend.bpu.bpu.case.abtb.provenance import eligible
from suites.frontend.bpu.bpu.case.abtb.provenance import expected_fast_train


PATHS = {
    'same_position_taken': ('inc0_1', 'inc1_2', 'inc2_3', 'inc3_3'),
    'final_not_taken': ('dec3_2', 'dec2_1', 'dec1_0', 'dec0_0'),
    'later_taken': ('dec3_2', 'dec2_1', 'dec1_0', 'dec0_0'),
}
CELLS = tuple(coordinates(cell) for cell in range(1024))


def cell_label(bank, set_index, way):
    index(bank, set_index, way)
    return f'bank{bank}.set{set_index}.way{way}'


@lru_cache(maxsize=3)
def _definition(name, paths):
    # Cross only the independent physical identity with an already-qualified
    # path. Crossing cause x inc/dec would create impossible combinations.
    points = [CoverPointDef('cell', {cell_label(*cell): Bin.values(cell_label(*cell))
        for cell in CELLS}, weight=1 if paths is None else 0)]
    crosses = ()
    if paths is not None:
        points.append(CoverPointDef('path', {path: Bin.values(path) for path in paths}, weight=0))
        crosses = (CrossDef('physical_path_matrix', ('cell', 'path'),
            max_auto_bins=1024 * len(paths)),)
    return CoverGroupDef(name, tuple(points), crosses=crosses)


def _group(name, paths=None):
    definition = _definition(name, None if paths is None else tuple(paths))
    return definition.instantiate('kunminghu_v3.bpu.' + name)


@lru_cache(maxsize=1)
def _semantic_definition():
    return CoverGroupDef('integrated_abtb_counter_semantic_paths', (
        CoverPointDef('way', {str(way): Bin.values(way) for way in range(4)}, weight=0),
        CoverPointDef('path', {f'{cause}.{path}': Bin.values(f'{cause}.{path}')
            for cause, paths in PATHS.items() for path in paths}, weight=0)),
        crosses=(CrossDef('way_path_matrix', ('way', 'path'), max_auto_bins=48),))


def _path(transaction, entry):
    if not entry['hit'] or entry['attribute']['branchType'] != 1:
        return None
    if not transaction['taken']:
        return 'final_not_taken'
    if entry['position'] < transaction['position']:
        return 'later_taken'
    if entry['position'] == transaction['position']:
        return 'same_position_taken'
    return None


class CounterCoverage:
    """Atomic collector shared by normal pytest scenarios and trace audits."""

    def __init__(self):
        self.transitions = _group('integrated_abtb_counter_paths_all_cells',
            (f'{path}.{transition}' for path, transitions in PATHS.items() for transition in transitions))
        self.resets = _group('integrated_abtb_counter_write_reset_all_cells')
        self.priority = _group('integrated_abtb_counter_reset_priority_all_cells',
            (f'{path}.before{before}' for path in PATHS for before in range(4)))
        self.semantic = _semantic_definition().instantiate('kunminghu_v3.bpu.integrated_abtb_counter_semantic_paths')

    @property
    def physical_groups(self):
        return self.transitions, self.resets, self.priority

    @property
    def groups(self):
        return (*self.physical_groups, self.semantic)

    def collect(self, trace):
        if trace.get('passed') is not True or trace.get('failure'):
            raise ValueError('counter coverage requires a successful checked scenario')
        rises, controls = trace.get('records'), trace.get('preedge_records')
        if not rises or not controls:
            raise ValueError('counter coverage requires complete rising and stable-input observations')
        replay = self.stream()
        for _, phase, frame in merge(
                ((row['tick'], 'preedge', row) for row in controls),
                ((row['tick'], 'rising', row) for row in rises)):
            replay.observe(dict(frame, phase=phase))
        return replay.finish(passed=True)

    def stream(self):
        return CoverageReplay(self._replay(), self._commit)

    def _replay(self):
        reference, metadata = CounterReference(), MetadataPipeline()
        board = Scoreboard('bpu.integrated_abtb_counter_coverage_reset_replay')
        counts = [Counter(), Counter(), Counter()]
        pending = []
        previous = None
        initialized = False
        reset_frames = accepted_count = checked_frames = 0

        def check(expected, actual, frame, field, **details):
            board.check(expected=canonical(expected), actual=canonical(actual),
                context=CheckContext(scoreboard=board.name, mode=ScoreboardMode.DIRECT,
                    observed_event=SimpleNamespace(tick=frame['tick']),
                    request=dict(field=field, pending1=reference.pending1,
                        pending2=reference.pending2, **details)))

        phase_ticks = {}
        while (frame := (yield)) is not None:
            tick, phase = frame['tick'], frame['phase']
            check(True, phase in ('rising', 'preedge'), frame, 'known observation phase')
            if phase in phase_ticks:
                check(phase_ticks[phase] + 2, tick, frame, f'complete {phase} observation cadence')
            phase_ticks[phase] = tick
            row = frame['abtb']
            if previous is None:
                check(('preedge', 1), (phase, frame['reset']), frame, 'genuine reset before replay')
            else:
                check(previous[0] + 1, tick, frame, 'continuous two-phase observation')
                check('rising' if previous[1] == 'preedge' else 'preedge', phase,
                    frame, 'alternating observation phases')
            check(1024, len(row['cells']), frame, 'complete physical counter grid')
            check(4, len(row['replacers']), frame, 'all physical replacer banks')
            check(4, len(row['writes']), frame, 'all write-response banks')
            if initialized:
                check(reference.cells, row['cells'], frame, 'all1024 counter cells')
                for bank, port in enumerate(row['replacers']):
                    check(reference.plru[bank], port['states'], frame, 'all64 PLRU states', bank=bank)
                    check(reference.plru[bank], port['shadow'], frame, 'all64 PLRU shadows', bank=bank)
                    check(victim(reference.plru[bank][port['replace_set']]), port['victim'],
                        frame, 'reset-derived PLRU victim', bank=bank)
                checked_frames += 1
            if phase == 'rising':
                check(previous[2], frame['reset'], frame, 'same reset at input and execution boundary')
                for kind, label in pending:
                    counts[kind][label] += 1
                pending = []
            elif frame['reset']:
                reference.reset()
                metadata.advance(reset=True, fire1=0, fire2=0, meta=None, pc=0, tick=tick)
                pending = []
                initialized = True
                reset_frames += 1
            else:
                for name, token in (('meta2', metadata.stage2), ('meta3', metadata.stage3)):
                    if token is not None:
                        check(token['meta'], row[name], frame, 'captured S1 metadata pipeline', stage=name)
                fast, final = row['fast'], row['final']
                check(final['valid'], fast['valid'], frame, 'S3 fastTrain valid')
                accepted = None
                if fast['valid']:
                    check(True, metadata.stage3 is not None, frame, 'actual earlier S1 token required')
                    expected = expected_fast_train(final, metadata.stage3)
                    check(expected, {key: fast[key] for key in expected}, frame, 'complete S1-to-S3 fastTrain')
                    check(final['pc'] & ((1 << 49) - 1), expected['pc'], frame, 'associated parent S3 PC')
                    if eligible(fast['valid'], expected['meta']['valid'], row['enable']):
                        accepted = expected
                        accepted_count += 1
                check(int(reference.pending1 is not None), row['t1_fire'], frame, 'eligible delayed T1 gate')
                tx = reference.pending2
                writes = []
                for bank, port in enumerate(row['replacers']):
                    matching = [] if tx is None else [int(bool(entry['hit']
                        and entry['position'] == tx['position']
                        and entry['attribute'] == dict(branchType=tx['branch_type'], rasAction=tx['ras_action'])))
                        for entry in tx['meta']['entries']]
                    enabled = bool(tx and tx['taken'] and tx['meta']['bankMask'] & (1 << bank) and any(matching))
                    check(int(enabled), port['read_valid'], frame, 'independent T2 touch gate', bank=bank)
                    if enabled:
                        check(tx['meta']['setIdx'], port['read_set'], frame, 'independent T2 touch set', bank=bank)
                        check(matching, port['read_mask'], frame, 'independent T2 touch ways', bank=bank)
                    write = row['writes'][bank]
                    check(write['valid'], port['write_valid'], frame, 'write-response PLRU gate', bank=bank)
                    if write['valid']:
                        check((write['set_index'], write['way']), (port['write_set'], port['write_way']),
                            frame, 'write-response PLRU identity', bank=bank)
                        writes.append(dict(bank=bank, **{name: write[name]
                            for name in ('set_index', 'way', 'reset_counter')}))
                # Same-cell reset suppresses, rather than executes, T1's update.
                tx = reference.pending1
                for write in writes:
                    if not write['reset_counter'] or tx is None:
                        continue
                    bank, set_index, way = (write[name] for name in ('bank', 'set_index', 'way'))
                    path = _path(tx, tx['meta']['entries'][way])
                    if path and tx['meta']['bankMask'] & (1 << bank) and tx['meta']['setIdx'] == set_index:
                        before = reference.cells[index(bank, set_index, way)]
                        pending.append((2, f'{cell_label(bank, set_index, way)}.{path}.before{before}'))
                transitions = reference.advance(reset=False, accepted=accepted, writes=writes)
                for transition in transitions:
                    bank, set_index, way = (transition[name] for name in ('bank', 'set_index', 'way'))
                    label = cell_label(bank, set_index, way)
                    if transition['transition'] == 'reset':
                        pending.append((1, label))
                    else:
                        tx = transition['feedback']
                        path = _path(tx, tx['meta']['entries'][way])
                        check(True, path in PATHS, frame, 'qualified counter update cause')
                        check(True, transition['transition'] in PATHS[path], frame, 'legal saturating transition')
                        pending.append((0, f"{label}.{path}.{transition['transition']}"))
                metadata.advance(reset=False, fire1=row['capture']['fire1'], fire2=row['capture']['fire2'],
                    meta=row['meta1'], pc=row['capture']['pc1'], tick=tick)
            previous = tick, phase, frame['reset']

        if not initialized or not checked_frames:
            raise ValueError('counter coverage requires at least one checked reset-derived execution boundary')
        summary = dict(frames=checked_frames + 1, reset_input_frames=reset_frames,
            accepted_fast_train=accepted_count, transition_counts=dict(counts[0]),
            write_reset_counts=dict(counts[1]), reset_priority_counts=dict(counts[2]),
            transition_total_bins=1024 * 12, write_reset_total_bins=1024,
            reset_priority_total_bins=1024 * 12,
            unobserved_final_input_events_not_credited=len(pending),
            write_response_generation_independently_modeled=False,
            PHR_or_SRAM_or_full_FTQ_checked_by_this_collector=False)
        return summary, counts

    def _commit(self, counts):
        # Counts are published only after complete successful validation.
        for group, hits in zip(self.physical_groups, counts, strict=True):
            for label, count in hits.items():
                parts = label.split('.', 3)
                sample = dict(cell='.'.join(parts[:3]))
                if len(parts) == 4:
                    sample['path'] = parts[3]
                for _ in range(count):
                    group.sample(sample, details=False)
                    if group is self.transitions:
                        # Project only fully replay-checked events. This is a
                        # distinct schema, never a reduced physical denominator.
                        self.semantic.sample(dict(way=int(parts[2].removeprefix('way')),
                                                  path=parts[3]), details=False)

    def save(self, output, *, case):
        if not case or any(char not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for char in case):
            raise ValueError('coverage case must be a simple intent identifier')
        write_functional_coverage(CoverageDatabase(self.groups), output_path(output / f'functional-coverage-integrated-abtb-{case}.json'))
