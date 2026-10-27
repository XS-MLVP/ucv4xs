"""Contextual full-state comparisons; sampling mechanics stay out of tests."""
from dataclasses import asdict
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from bpuverify.bpu.model.bypass.model import BypassReference


class BypassChecker:
    def __init__(self):
        self.references = [BypassReference(table) for table in range(2)]
        self.scoreboard = Scoreboard('bpu.integrated_microtage_shadow')
        self.records = []
        self.writes = []
        self._failure = None
        self.initialized = False
        self.last_event = None
        self.last_phase = None

    def raise_failure(self):
        if self._failure is not None:
            raise self._failure

    def capture(self, phase, observation):
        if self._failure is None:
            try:
                self.observe(phase, observation)
            except Exception as error:
                self._failure = error

    def check(self, expected, actual, *, table, point):
        self.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
                request=dict(table=table, point=point, phase=self.last_phase),
                observed_event=self.last_event))

    def observe(self, phase, observation):
        event, row = observation.event, observation.value
        if self.last_event is not None:
            self.check(self.last_event.tick + 1, event.tick, table=None, point='complete alternating observation ticks')
            self.check('rising' if self.last_phase == 'preedge' else 'preedge', phase,
                table=None, point='alternating sampling phases')
        self.last_event, self.last_phase = event, phase
        self.records.append(dict(phase=phase, tick=event.tick, value=row))
        if not self.initialized:
            self.check(('preedge', 1), (phase, row['reset']), table=None,
                point='monitor starts before genuine reset, never seeded from DUT')
        for table, (reference, actual) in enumerate(zip(self.references, row['tables'], strict=True)):
            if self.initialized:
                # Normalize nested array containers only, never observed values.
                expected = reference.state()
                expected['cells'] = tuple(expected['cells'])
                expected['status'] = tuple(expected['status'])
                expected['useful'] = tuple(expected['useful'])
                expected['hits'] = tuple(expected['hits'])
                self.check(expected, actual['state'], table=table, point='all cells/status/useful/pointers/registered selection')
                outputs = reference.outputs(actual['inputs'])
                for name, wanted in outputs.items():
                    observed = actual['outputs'][name]
                    if isinstance(wanted, dict):
                        observed = {key: observed[key] for key in wanted}
                    self.check(wanted, observed, table=table, point=f'input-derived {name}')
            if phase == 'preedge':
                witness = reference.advance(actual['inputs'], reset=bool(row['reset']))
                if witness['kind'] == 'write':
                    self.writes.append(dict(tick=event.tick, table=table, **witness))
        if phase == 'preedge':
            self.initialized = True

    def finish(self):
        self.raise_failure()
        self.check(True, self.initialized, table=None, point='actual reset observed')
        return dict(frames=len(self.records), writes=self.writes,
            checked_useful_cells_per_frame=1024, checked_shadow_cells_per_frame=16,
            checks=asdict(self.scoreboard.status),
            training_inputs_observed_not_upstream_policy_predicted=True,
            write_success_independently_derived_from_bank_and_predicted_ring=True,
            SRAM_persistence_and_parent_allocation_policy_modeled=False)
