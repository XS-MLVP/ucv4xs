"""Independent metadata lineage, gated fastTrain, full counters and PLRU from reset."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.bpu.model.sc.model import canonical
from suites.frontend.bpu.bpu.model.sc.model import encoded_payload
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.abtb.model.state.counter import CounterReference
from suites.frontend.bpu.abtb.model.state.counter import TRANSITIONS
from suites.frontend.bpu.abtb.model.state.counter import victim
from suites.frontend.bpu.bpu.case.abtb.provenance import MetadataPipeline
from suites.frontend.bpu.bpu.case.abtb.provenance import eligible
from suites.frontend.bpu.bpu.case.abtb.provenance import expected_fast_train


class IntegratedChecks(BpuPhrChecker):
    def __init__(self, case):
        super().__init__(scope='integrated ABTB full-counter/PLRU and real S1-to-S3 fastTrain; complete nonzero history')
        self.case, self.phase = case, 'setup'
        self.counter = CounterReference()
        self.metadata = MetadataPipeline()
        self.abtb_scoreboard = Scoreboard('bpu.integrated_abtb_counter_lineage')
        self.control_records, self.accepts, self.transitions, self.confirmed, self.gates = [], [], [], [], []
        self.current_rise = None
        self.pending_confirmations = []
        self.coherent_transactions, self.feedback_accepts, self.feedback_plans = [], [], deque()

    def plan_feedback(self, transaction):
        self.raise_failure()
        self.feedback_plans.append(canonical(asdict(transaction)))

    def compare(self, expected, actual, **details):
        self.abtb_scoreboard.check(expected=canonical(expected), actual=canonical(actual),
            context=CheckContext(scoreboard=self.abtb_scoreboard.name, mode=ScoreboardMode.DIRECT,
                request=dict(case=self.case, phase=self.phase, **details), observed_event=self.abtb_event))

    def states(self, row):
        self.compare(self.counter.cells, row['cells'], field='all1024_independent_counter_cells')
        for bank, actual in enumerate(row['replacers']):
            self.compare(self.counter.plru[bank], actual['states'], field='all64_PLRU_state_registers', bank=bank)
            self.compare(self.counter.plru[bank], actual['shadow'], field='all64_PLRU_state_shadow', bank=bank)
            self.compare(victim(self.counter.plru[bank][actual['replace_set']]), actual['victim'],
                field='independent_PLRU_victim', bank=bank, set_index=actual['replace_set'])

    def observe(self, observation):
        self.current_phr_expected = deepcopy(self.reference.state) if self.initialized else None
        prior_token = deepcopy(self.association.stage3)
        super().observe(observation)
        self.abtb_event = observation.event
        row, abtb = observation.value, observation.value['abtb']
        self.current_rise = observation
        if not row['reset'] and row['public_meta']['valid']:
            self.coherent_transactions.append(canonical(asdict(self.association.completed[-1])))
        if row['reset']:
            self.counter.reset()
            self.metadata.advance(reset=1, fire1=0, fire2=0, meta=None, pc=0, tick=self.abtb_event.tick)
            self.pending_confirmations.clear()
            return
        self.states(abtb)
        feedback = abtb['feedback']
        if feedback['valid'] and feedback['ready']:
            pc = feedback['bits']['start_pcs'][0][0]['addr'] & ((1 << 49) - 1)
            candidates = [item for item in self.coherent_transactions
                if item['prediction']['start_pc'] == pc and item['meta_tick'] < self.abtb_event.tick
                and item['meta']['resolve'] == canonical(feedback['bits']['meta'])]
            self.compare(True, bool(candidates), field='every_feedback_uses_actual_earlier_full_coherent_metadata', pc=pc)
            if self.feedback_plans:
                self.compare(encoded_payload(self.feedback_plans.popleft(), len(feedback['bits']['branches'])),
                    feedback['bits'], field='complete_planned_feedback_payload')
            self.feedback_accepts.append(dict(tick=self.abtb_event.tick, phase=self.phase,
                bits=deepcopy(feedback['bits']), genuine_source_meta_tick=candidates[0]['meta_tick']))
        self.confirmed.extend(dict(checked_tick=self.abtb_event.tick, **item) for item in self.pending_confirmations)
        self.pending_confirmations.clear()
        self.compare(abtb['final']['valid'], abtb['fast']['valid'], field='S3_valid_drives_fastTrain_valid')
        if abtb['fast']['valid']:
            self.compare(True, prior_token is not None, field='genuine_associated_S1_token_reaches_S3')
            self.compare(prior_token['prediction'].start_pc & ((1 << 49) - 1), abtb['fast']['pc'],
                field='fastTrain_PC_matches_exact_associated_S1_token')

    def capture_controls(self, observation):
        if self.failure is None:
            try:
                self.observe_controls(observation)
            except Exception as error:
                self.failure = error

    def observe_controls(self, observation):
        self.abtb_event = observation.event
        row, abtb = observation.value, observation.value['abtb']
        self.compare(True, len(self.control_records) < 8192, field='bounded_preedge_observation')
        captured = row if getattr(self, 'compact_history', False) else deepcopy(row)
        self.control_records.append(dict(tick=self.abtb_event.tick, phase=self.phase, **captured))
        if self.current_rise is None:
            return
        self.compare(self.current_rise.event.tick + 1, self.abtb_event.tick, field='exact_rising_to_preedge_alignment')
        if row['reset']:
            self.counter.reset()
            self.metadata.advance(reset=1, fire1=0, fire2=0, meta=None, pc=0, tick=self.abtb_event.tick)
            self.pending_confirmations.clear()
            return
        self.states(abtb)
        for name, expected in (('meta2', self.metadata.stage2), ('meta3', self.metadata.stage3)):
            if expected is not None:
                self.compare(expected['meta'], abtb[name], field='complete_independent_metadata_register', stage=name,
                    source_S1_tick=expected['tick'])
        fast, final = abtb['fast'], abtb['final']
        self.compare(final['valid'], fast['valid'], field='full_S3_fastTrain_valid_gate')
        accepted = None
        if fast['valid']:
            self.compare(True, self.metadata.stage3 is not None, field='S3_requires_actual_S1_metadata_capture')
            expected = expected_fast_train(final, self.metadata.stage3)
            self.compare(expected, {key: fast[key] for key in expected}, field='complete_derived_fastTrain_payload',
                source_S1_tick=self.metadata.stage3['tick'])
            self.compare(final['pc'] & ((1 << 49) - 1), fast['pc'], field='parent_final_S3_PC')
            self.compare(self.metadata.stage3['meta'], abtb['meta3'], field='latched_S3_metadata_never_seeded_reference')
            passed = eligible(fast['valid'], expected['meta']['valid'], abtb['enable'])
            self.gates.append(dict(tick=self.abtb_event.tick, phase=self.phase, fast_valid=fast['valid'],
                meta_valid=expected['meta']['valid'], enabled=abtb['enable'], accepted=passed))
            if passed:
                accepted = expected
                self.accepts.append(dict(tick=self.abtb_event.tick, committed_tick=self.abtb_event.tick + 1,
                    phase=self.phase, source_S1_tick=self.metadata.stage3['tick'], transaction=deepcopy(expected)))
        self.compare(int(self.counter.pending1 is not None), abtb['t1_fire'], field='actual_delayed_eligible_T1_gate')
        tx = self.counter.pending2
        for bank, port in enumerate(abtb['replacers']):
            matching = [] if tx is None else [bool(entry['hit'] and entry['position'] == tx['position']
                and entry['attribute'] == dict(branchType=tx['branch_type'], rasAction=tx['ras_action']))
                for entry in tx['meta']['entries']]
            enabled = bool(tx and tx['taken'] and tx['meta']['bankMask'] & (1 << bank) and any(matching))
            self.compare(int(enabled), port['read_valid'], field='independent_T2_replacer_read_valid', bank=bank)
            if enabled:
                self.compare(tx['meta']['setIdx'], port['read_set'], field='independent_T2_replacer_read_set', bank=bank)
                self.compare(list(map(int, matching)), port['read_mask'], field='independent_T2_replacer_touch_mask', bank=bank)
            write = abtb['writes'][bank]
            self.compare(write['valid'], port['write_valid'], field='actual_write_response_to_PLRU_gate', bank=bank)
            if write['valid']:
                self.compare((write['set_index'], write['way']), (port['write_set'], port['write_way']),
                    field='actual_write_response_to_PLRU_identity', bank=bank)
        writes = [dict(bank=bank, **{key: value for key, value in port.items() if key != 'valid'})
            for bank, port in enumerate(abtb['writes']) if port['valid']]
        transitions = self.counter.advance(reset=0, accepted=accepted, writes=writes)
        self.pending_confirmations = [dict(tick=self.abtb_event.tick, phase=self.phase, **item) for item in transitions]
        self.transitions.extend(deepcopy(self.pending_confirmations))
        self.metadata.advance(reset=0, fire1=abtb['capture']['fire1'], fire2=abtb['capture']['fire2'],
            meta=abtb['meta1'], pc=abtb['capture']['pc1'], tick=self.abtb_event.tick)

    def summary(self):
        summary = super().summary()
        self.raise_failure()
        return dict(phr=summary, preedge_frames=len(self.control_records), actual_fastTrain_accepts=len(self.accepts),
            confirmed_transitions=len(self.confirmed), counter_and_PLRU_checks=asdict(self.abtb_scoreboard.status),
            all1024_counters_and_all256_PLRU_states_compared=True,
            hardware_observed_state_seeded_reference=False, full_ABTB_bank_SRAM_model_claimed=False,
            write_response_generation_independently_modeled=False)
