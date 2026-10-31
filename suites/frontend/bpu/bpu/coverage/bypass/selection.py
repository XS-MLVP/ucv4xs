"""Shadow response selection credit from complete, reset-derived comparisons.

Only rising observations with independently predicted valid response payloads
earn bins. Test inputs are never selected by observed provider or slot outputs.
The full nominal 2-table x 8-slot x 2-selection schema survives partial runs.
Slot0 fallback is excluded by the reset/mask invariant, not an observed gap.
"""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from collections import Counter
from dataclasses import asdict
from types import SimpleNamespace

from toffee import Bin
from toffee import CheckContext
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef
from toffee import ScoreboardMode

from suites.frontend.bpu.runtime.artifacts import output_path
from suites.frontend.bpu.bpu.checker.bypass.checker import BypassChecker


def response_selection_coverage_model():
    axes = dict(table=range(2), slot=range(8), selection=('priority', 'fallback'))
    return CoverGroupDef('integrated_shadow_response_selection',
        tuple(CoverPointDef(axis, {str(value): Bin.values(value) for value in values})
              for axis, values in axes.items()),
        crosses=(CrossDef('all_dimensions', tuple(axes),
            ignore=(('0', '0', 'fallback'), ('1', '0', 'fallback')),
            description='30 non-excluded combinations (global reachability not assumed); '
                        'slot0 fallback impossible: reset clears hits, '
                        'and every non-reset allocation mask has bit0 set (BypassShadowBuffer.scala:90,104,234)'),)
    ).instantiate('kunminghu_v3.bpu.integrated_shadow_response_selection')


class ResponseSelectionCoverage:
    def __init__(self):
        self.coverage = response_selection_coverage_model()

    def collect(self, trace, *, required=(), required_after_tick=None):
        if trace.get('passed') is not True or trace.get('failure'):
            raise ValueError('response selection requires a complete successful scenario')
        required = tuple(required)
        if required_after_tick is not None and (type(required_after_tick) is not int or required_after_tick < 0):
            raise ValueError('required response window starts at a nonnegative integer tick')
        for table, slot, selection in required:
            if (type(table) is not int or table not in range(2)
                    or type(slot) is not int or slot not in range(8)
                    or selection not in ('priority', 'fallback')
                    or slot == 0 and selection == 'fallback'):
                raise ValueError('unsupported response selection requirement')
        frames = trace.get('bypass_records')
        if not frames:
            raise ValueError('complete native shadow observations required')
        checker = BypassChecker()
        counts, witnesses, required_counts, required_witnesses = Counter(), {}, Counter(), {}
        for frame in frames:
            checker.observe(frame['phase'], SimpleNamespace(
                event=SimpleNamespace(tick=frame['tick']), value=frame['value']))
            if frame['phase'] != 'rising' or frame['value']['reset']:
                continue
            for table, reference in enumerate(checker.references):
                observed = frame['value']['tables'][table]
                expected = reference.outputs(observed['inputs'])['response']
                if not expected['hit'] or not expected.get('data_valid'):
                    continue
                slot = (reference.chosen or reference.hits).bit_length() - 1
                selection = 'priority' if reference.chosen else 'fallback'
                key = (table, slot, selection)
                counts[key] += 1
                witnesses.setdefault(key, dict(tick=frame['tick'], table=table, slot=slot,
                    selection=selection, hits=reference.hits, chosen=reference.chosen,
                    expected=expected, actual=dict(observed['outputs']['response'])))
                if key in required and (required_after_tick is None or frame['tick'] > required_after_tick):
                    required_counts[key] += 1
                    required_witnesses.setdefault(key, dict(tick=frame['tick'], table=table, slot=slot,
                        selection=selection, hits=reference.hits, chosen=reference.chosen,
                        expected=expected, actual=dict(observed['outputs']['response'])))
        summary = checker.finish()
        for key in required:
            checker.scoreboard.check(expected=True, actual=required_counts[key] > 0,
                context=CheckContext(checker.scoreboard.name, ScoreboardMode.DIRECT,
                    request=dict(point='required_shadow_response_selection',
                                 table=key[0], slot=key[1], selection=key[2], after_tick=required_after_tick),
                    observed_event=checker.last_event))
        # Commit only after the final state/output and required-path gates pass.
        for (table, slot, selection), count in counts.items():
            for _ in range(count):
                self.coverage.sample(dict(table=table, slot=slot, selection=selection))
        return dict(frames=summary['frames'], checks=asdict(checker.scoreboard.status),
            required=[dict(table=table, slot=slot, selection=selection) for table, slot, selection in required],
            required_after_tick=required_after_tick, required_witnesses=list(required_witnesses.values()),
            witnesses=list(witnesses.values()), bins_hit=len(counts), bins_required=30, nominal_bins=32,
            excluded_combinations=[dict(table=table, slot=0, selection='fallback',
                reason='reset clears hits; every allocated prefix mask contains bit0') for table in range(2)],
            occurrences={f'table{table}.slot{slot}.{selection}': count
                         for (table, slot, selection), count in counts.items()},
            complete_selection_matrix_proven=self.coverage.cross_coverage('all_dimensions') == 100,
            observed_state_used_to_seed_reference=False, full_FTQ_legality_proven=False)

    def save(self, output, *, case):
        if not case or any(char not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for char in case):
            raise ValueError('coverage case must be a simple intent identifier')
        write_functional_coverage(CoverageDatabase([self.coverage]), output_path(
            output / f'functional-coverage-shadow-response-selection-{case}.json'))
