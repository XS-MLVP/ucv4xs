"""Gap-derived coverage, committed only after a complete reset-derived replay.

Testcase success, cached write lists and cached expectations are not witnesses.
Each operation is derived from a real sampled input and credited only after
the next observed complete state agrees with the independent reference.
"""

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from bpuverify.common.coverage.replay import CoverageReplay
from collections import Counter
from types import SimpleNamespace

from toffee import Bin
from toffee import CheckContext
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import Scoreboard
from toffee import ScoreboardMode
from bpuverify.bpu.model.sc.model import canonical
from bpuverify.bpu.model.bypass.model import BypassReference


SOURCES = ('allocation', 'resident', 'captured_counter')
OPERATIONS = ('allocation', 'increment', 'decrement', 'saturated_high_hold',
              'saturated_low_hold', 'age_zero', 'age_nonzero')


def _group(name, labels, point):
    return CoverGroupDef(name, (CoverPointDef(point,
        {label: Bin.values(label) for label in labels}),)
        ).instantiate('kunminghu_v3.bpu.' + name)


def training_source_coverage():
    return _group('integrated_shadow_training_sources_all_banks',
        [f'bank{bank}.table{table}.{source}' for bank in range(4)
         for table in range(2) for source in SOURCES], 'bank_table_source')


def useful_operation_coverage():
    return _group('integrated_useful_behavior_all_banks',
        [f'table{table}.bank{bank}.{operation}' for table in range(2)
         for bank in range(4) for operation in OPERATIONS], 'table_bank_operation')


def lower_ring_coverage():
    return CoverGroupDef('integrated_lower_shadow_ring', (
        CoverPointDef('slot', {str(slot): Bin.values(slot) for slot in range(8)}),
        CoverPointDef('source', {name: Bin.values(name) for name in SOURCES[:2]}),
    )).instantiate('kunminghu_v3.bpu.integrated_lower_shadow_ring')


def _useful_operations(reference, inputs):
    if inputs['age']:
        return [(index, 'age_nonzero' if old else 'age_zero')
                for index, old in enumerate(reference.useful)]
    if inputs['allocate']:
        return [(reference.train_index, 'allocation')]
    if inputs['update'] and inputs['useful_valid']:
        index = reference.train_index
        old = reference.useful[index]
        operation = ('increment' if old < 3 else 'saturated_high_hold') if inputs['useful_increase'] else (
            'decrement' if old else 'saturated_low_hold')
        return [(index, operation)]
    return []


class IntegratedCoverage:
    """Reusable successful-trace collector; failure never exports partial credit."""

    def __init__(self):
        self.sources = training_source_coverage()
        self.useful = useful_operation_coverage()
        self.ring = lower_ring_coverage()

    def collect(self, trace):
        if trace.get('passed') is not True or trace.get('failure'):
            raise ValueError('functional coverage requires a successful checked scenario')
        frames = trace.get('bypass_records', trace.get('records'))
        if not frames:
            raise ValueError('functional coverage requires complete sampled boundary frames')
        replay = self.stream()
        for frame in frames:
            replay.observe(frame)
        return replay.finish(passed=True)

    def stream(self):
        return CoverageReplay(self._replay(), self._commit)

    def _replay(self):
        references = [BypassReference(table) for table in range(2)]
        board = Scoreboard('bpu.integrated_coverage_reset_replay')
        source_counts, useful_counts, ring_counts = Counter(), Counter(), Counter()
        pending = []
        previous = None
        initialized = False
        resets = frames_count = 0

        def check(expected, actual, frame, point, table=None):
            board.check(expected=canonical(expected), actual=canonical(actual),
                context=CheckContext(scoreboard=board.name, mode=ScoreboardMode.DIRECT,
                    observed_event=SimpleNamespace(tick=frame['tick']),
                    request=dict(table=table, phase=frame['phase'], point=point)))

        while (frame := (yield)) is not None:
            frames_count += 1
            check(True, frame['phase'] in ('rising', 'preedge'), frame, 'known observation phase')
            phase, row = frame['phase'], frame['value']
            if previous is None:
                check(('preedge', 1), (phase, row['reset']), frame, 'genuine reset before coverage replay')
            else:
                check(previous['tick'] + 1, frame['tick'], frame, 'complete observation cadence')
                check('rising' if previous['phase'] == 'preedge' else 'preedge', phase,
                      frame, 'alternating observation phases')
            check(2, len(row['tables']), frame, 'both complete tables observed')
            if initialized:
                for table, reference in enumerate(references):
                    check(reference.state(), row['tables'][table]['state'], frame,
                          'all shadow slots, status, selection, pointers and all512 useful values', table)
            # A preedge input alone is not execution evidence. Qualify the
            # pending operations only after both next complete states pass.
            if phase == 'rising':
                for kind, label in pending:
                    (source_counts if kind == 'source' else useful_counts if kind == 'useful'
                     else ring_counts)[label] += 1
                pending = []
            elif phase == 'preedge':
                if row['reset']:
                    resets += 1
                for table, reference in enumerate(references):
                    inputs = row['tables'][table]['inputs']
                    operations = [] if row['reset'] else _useful_operations(reference, inputs)
                    witness = reference.advance(inputs, reset=bool(row['reset']))
                    if witness['kind'] == 'write':
                        label = f"bank{witness['index'] % 4}.table{table}.{witness['source']}"
                        pending.append(('source', label))
                        if table == 0 and witness['source'] in SOURCES[:2]:
                            pending.append(('ring', (witness['slot'], witness['source'])))
                    pending.extend(('useful', f'table{table}.bank{index % 4}.{operation}')
                                   for index, operation in operations)
                initialized = True
            previous = frame

        if not initialized or frames_count < 2:
            raise ValueError('no complete reset-derived observation pair')
        summary = dict(frames=frames_count, reset_frames=resets,
            source_counts=dict(source_counts), useful_counts=dict(useful_counts),
            unobserved_final_preedge_operations_not_credited=len(pending),
            source_bins=len(source_counts), source_total_bins=24,
            useful_bins=len(useful_counts), useful_total_bins=56,
            all_addresses_or_overlap_or_full_FTQ_claimed=False)
        return summary, (source_counts, useful_counts, ring_counts)

    def _commit(self, counts):
        source_counts, useful_counts, ring_counts = counts
        # No group is changed until the entire replay, including its final
        # frame, has passed. Thus late corruption cannot create partial credit.
        for label, count in source_counts.items():
            for _ in range(count):
                self.sources.sample(dict(bank_table_source=label))
        for label, count in useful_counts.items():
            for _ in range(count):
                self.useful.sample(dict(table_bank_operation=label))
        for (slot, source), count in ring_counts.items():
            for _ in range(count):
                self.ring.sample(dict(slot=slot, source=source))

    def save(self, output, *, case):
        if not case or any(char not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for char in case):
            raise ValueError('coverage case must be a simple intent identifier')
        write_functional_coverage(CoverageDatabase((self.sources, self.useful, self.ring)), output_path(output / f'functional-coverage-integrated-{case}.json'))
