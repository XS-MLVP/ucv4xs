"""Physical path requirements, separate from stimulus and trace collection."""
from collections.abc import Mapping

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode

from suites.frontend.bpu.bpu.coverage.abtb.supplemental import PATHS
from suites.frontend.bpu.bpu.coverage.abtb.supplemental import cell_label


def required_counter_paths(*, bank, entry_set, causes):
    """Name every required transition/hold in all four physical ways."""
    if type(bank) is not int or not 0 <= bank < 4:
        raise ValueError('physical bank must be an integer0..3')
    if type(entry_set) is not int or not 0 <= entry_set < 64:
        raise ValueError('physical set must be an integer0..63')
    if (not isinstance(causes, (tuple, list)) or not causes
            or any(not isinstance(cause, str) or cause not in PATHS for cause in causes)
            or len(set(causes)) != len(causes)):
        raise ValueError('counter causes must be a nonempty unique sequence of known causes')
    return tuple(f'{cell_label(bank, entry_set, way)}.{cause}.{path}'
                 for way in range(4) for cause in causes for path in PATHS[cause])


def require_counter_paths(summary, *, bank, entry_set, causes):
    """Raise a contextual pytest-native failure if any physical path is absent.

    Call after CounterCoverage's complete reset-derived replay and before
    exporting either functional collector. Aggregate totals or one observed
    way cannot stand in for a missing per-cell transition or saturation hold.
    """
    labels = required_counter_paths(bank=bank, entry_set=entry_set, causes=causes)
    counts = summary.get('transition_counts') if isinstance(summary, Mapping) else None
    if not isinstance(counts, Mapping):
        raise ValueError('checked counter summary must provide transition_counts')
    actual_counts = {label: counts.get(label, 0) for label in labels}
    if any(type(value) is not int or value < 0 for value in actual_counts.values()):
        raise ValueError('counter path counts must be nonnegative integers')
    board = Scoreboard('bpu.integrated_abtb.required_physical_counter_paths')
    board.check(expected={label: True for label in labels},
                actual={label: count > 0 for label, count in actual_counts.items()},
                context=CheckContext(scoreboard=board.name, mode=ScoreboardMode.DIRECT,
                    request=dict(bank=bank, entry_set=entry_set, causes=tuple(causes),
                                 observed_counts=actual_counts)))
    return dict(required_paths=len(labels), covered_paths=len(labels),
                bank=bank, entry_set=entry_set, ways=4, causes=tuple(causes))
