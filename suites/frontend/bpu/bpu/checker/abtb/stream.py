"""Extend existing static monitor/checker composition with independent ABTB tokens."""
from copy import deepcopy
from suites.frontend.bpu.bpu.checker.abtb.checks_aging import IntegratedChecks
from suites.frontend.bpu.bpu.checker.bypass.aging_scope import NonzeroChecks
from suites.frontend.bpu.bpu.env.bypass.aging_scope import NonzeroObservation
from suites.frontend.bpu.bpu.checker.bypass.policy import SramChecker
from suites.frontend.bpu.bpu.model.abtb.index import IndexReference
from suites.frontend.bpu.bpu.monitor.abtb.history import ObservationHistory, abtb_witness, bypass_witness
from suites.frontend.bpu.runtime.trace import trace_exports_enabled


class PairSramChecker(SramChecker):
    def observe(self, phase, observation):
        super().observe(phase, observation)
        self.owner.observe_index(phase, observation)
        if self.owner.coverage is not None:
            self.owner.coverage.observe_bypass(phase, observation.event.tick, observation.value)


class PairChecks(NonzeroChecks):
    def __init__(self, case, *, coverage=None):
        self.bypass = PairSramChecker()
        IntegratedChecks.__init__(self, case)
        self.bypass.owner = self
        self.abtb_index = IndexReference()
        self.index_tokens, self.index_records = {}, []
        self.coverage = coverage
        self.compact_history = coverage is not None and not trace_exports_enabled()
        if self.compact_history:
            self.records = ObservationHistory(abtb_witness)
            self.control_records = ObservationHistory(abtb_witness)
            self.bypass.records = ObservationHistory(bypass_witness)
        self.rises_by_tick = {}
        self.frames_by_tick = {}

    def observe(self, observation):
        super().observe(observation)
        self.rises_by_tick[observation.event.tick] = (
            self.records.by_tick[observation.event.tick] if self.compact_history else self.records[-1])
        if self.coverage is not None:
            self.coverage.observe_abtb('rising', observation.event.tick, observation.value)

    def observe_controls(self, observation):
        super().observe_controls(observation)
        if self.coverage is not None:
            self.coverage.observe_abtb('preedge', observation.event.tick, observation.value)

    def observe_index(self, phase, observation):
        self.frames_by_tick[observation.event.tick] = dict(phase=phase,
            tick=observation.event.tick, value=dict(hash_inputs=observation.value['hash_inputs']))
        tick, value = observation.event.tick, observation.value
        if phase == 'rising':
            assert self.current_rise.event.tick == tick
            row = self.current_rise.value
        else:
            row = self.control_records[-1]
            assert row['tick'] == tick
        abtb = row['abtb']
        self.compare(abtb['enable'], value['index_boundary']['enable'], field='shared_ABTB_UTAGE_enable')
        valid = self.abtb_index.check(abtb['meta1'], abtb['enable'])
        token = deepcopy(self.abtb_index.s2) if valid else None
        self.index_tokens[tick] = token
        self.index_records.append(dict(tick=tick, phase=phase, valid=valid, token=token))
        if phase == 'preedge':
            inputs, boundary = value['hash_inputs'], value['index_boundary']
            self.abtb_index.advance(reset=value['reset'], enable=abtb['enable'], fire0=boundary['fire0'],
                fire1=abtb['capture']['fire1'], fire2=abtb['capture']['fire2'],
                s2_override=inputs['s2_override'], s3_override=inputs['s3_override'],
                redirect=inputs['redirect_valid'], pc=inputs['pc'], folded6=inputs['normal_folds'][0], tick=tick)


from suites.frontend.bpu.bpu.env.abtb.write import WriteObservation as DirectObservation

PairObservation = DirectObservation
