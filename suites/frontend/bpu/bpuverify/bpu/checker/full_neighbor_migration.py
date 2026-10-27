"""Both stale inputs must hit a full retained set without losing a neighbor."""
from copy import deepcopy
from bpuverify.bpu.checker.neighbor_migration import NeighborMigrationChecks
from bpuverify.bpu.coverage.full_neighbor_migration import RULES
from bpuverify.bpu.model.tage.full_neighbor_migration import (
    HISTORY_PATHS, NEIGHBOR_NAMES, INPUT_NAMES, preparation, expected_profile)


class FullNeighborMigrationChecks(NeighborMigrationChecks):
    history_paths = HISTORY_PATHS
    neighbor_names = NEIGHBOR_NAMES
    input_names = INPUT_NAMES
    rules = RULES
    neighbor_steps = staticmethod(preparation)
    history_profile = staticmethod(expected_profile)

    def __init__(self, pipeline, coverage):
        super().__init__(pipeline, coverage)
        self.full_hits = []

    def observe_retained_hit(self, index, event, row):
        if index < self.service_count:
            return
        self.check(((1, 1, 1, 1),) * 2, tuple(tuple(v) for v in row['dirty']),
                   'both current owners actually full at each stale migrated-key update')
        self.full_hits.append(dict(index=index, source=self.input_names[index], tick=event.tick,
            dirty=deepcopy(row['dirty']), bits=tuple(deepcopy(p['bits']) for p in row['incoming']),
            requested_owners=(0, 1), current_owners=(1, 0)))

    def pending(self):
        self.check(self.input_count, len(self.offered), 'all declared proposals exist before full-hit association')
        old_indices = tuple(range(self.service_count, self.input_count))
        self.check(old_indices, tuple(h['index'] for h in self.full_hits), 'both actual full-capacity stale-hit witnesses mandatory')
        self.check(tuple(self.offered[i]['tick'] for i in old_indices), tuple(h['tick'] for h in self.full_hits),
                   'full witnesses belong to the two actual old-source proposals')
        super().pending()
        self.reach(self.rules[8], actual_full_hits=deepcopy(self.full_hits), independent_pending_histories=len(self.neighbor_names),
                   logical_results_per_current_owner=self.service_count, reference_overflow_unchanged=True)
