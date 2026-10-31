"""Sample pipeline occupancy and pending writes, without driving DUT state."""
from suites.frontend.bpu.runtime.wait import wait_condition
from suites.frontend.bpu.monitors.cycle import CycleMonitor

TRAINING_TIMEOUT_CYCLES = 256


class ActivityMonitor(CycleMonitor):
    def __init__(self, binding_and_labels):
        binding, self.labels = binding_and_labels
        super().__init__(binding, decoder=self._decode)
        self.last_wait = None

    def _decode(self, snapshot):
        return {group: {name: value.as_int() for name, value in zip(names, getattr(snapshot, group))}
                for group, names in self.labels.items()}

    async def wait_idle(self, *groups, timeout_cycles=TRAINING_TIMEOUT_CYCLES):
        return await self._wait(groups, idle=True, timeout_cycles=timeout_cycles)

    async def wait_active(self, *groups, timeout_cycles=TRAINING_TIMEOUT_CYCLES):
        return await self._wait(groups, idle=False, timeout_cycles=timeout_cycles)

    async def _wait(self, groups, *, idle, timeout_cycles):
        groups = groups or tuple(self.labels)
        if not groups or any(group not in self.labels for group in groups):
            raise ValueError(f'unknown activity groups {groups!r}; available={tuple(self.labels)}')

        def sample():
            # Only active signals are retained in diagnostics; clean resident
            # cache entries are not pending writes and are deliberately absent.
            state = self._capture(None)
            return {group: {key: value for key, value in state[group].items() if value}
                    for group in groups}

        self.last_wait = await wait_condition(
            self.binding.clock, sample=sample,
            satisfied=lambda state: bool(any(state.values())) != idle,
            name=self.binding.name + ('.idle.' if idle else '.active.') + '.'.join(groups),
            timeout_cycles=timeout_cycles)
        return self.last_wait
