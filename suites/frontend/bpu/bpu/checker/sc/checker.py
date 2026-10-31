"""Associate actual public accepts and compare derived pipeline/state via Scoreboard."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.bpu.model.sc.model import canonical
from suites.frontend.bpu.bpu.model.sc.model import encoded_payload
from suites.frontend.bpu.bpu.model.sc.model import ScReference
from suites.frontend.bpu.bpu.model.sc.model import NAMES
from suites.frontend.bpu.bpu.model.sc.model import TABLES
from suites.frontend.bpu.bpu.model.sc.model import width
from suites.frontend.bpu.bpu.model.sc.training_path import project_inputs
from suites.frontend.bpu.bpu.model.sc.training_path import train_need_write
from suites.frontend.bpu.bpu.model.sc.training_path import training_indices


class ScChecker:
    def __init__(self, case, *, fault=None, capacity=2048, record_limit=None):
        if record_limit is not None and (type(record_limit) is not int or not 2 <= record_limit <= capacity):
            raise ValueError('SC record_limit must be between two and the observation budget')
        self.case, self.fault, self.capacity = case, fault, capacity
        self.reference = ScReference()
        self.scoreboard = Scoreboard('bpu.sc.masked_feedback')
        self.phase, self.planned = 'setup', deque()
        self.records = [] if record_limit is None else deque(maxlen=record_limit)
        self.accepts, self.actions, self.drains = [], [], []
        self.observed_cycles = self.observed_controls = 0
        self.initialized, self.failure, self.event = False, None, None
        self.pending_reads, self.confirmed_reads, self.t0_accepts = {}, [], []
        self.control_records = [] if record_limit is None else deque(maxlen=record_limit)
        self.current_requests = {}
        self.current_rise, self.current_rise_phase = None, None

    def check(self, expected, actual, **details):
        self.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
                request=dict(case=self.case, phase=self.phase, **details), observed_event=self.event))

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def plan(self, transactions):
        self.raise_failure()
        self.planned.extend(canonical(asdict(tx)) for tx in transactions)

    def capture(self, observation):
        if self.failure is not None:
            return
        try:
            self.observe(observation)
        except Exception as error:
            self.failure = error

    def observe(self, observation):
        row, self.event = canonical(observation.value), observation.event
        self.current_rise, self.current_rise_phase = observation, self.phase
        self.current_requests = {}
        if self.fault is not None:
            row = self.fault(row, self)
        self.check(True, self.observed_cycles < self.capacity, field='bounded_observation_capacity')
        self.observed_cycles += 1
        if self.records:
            self.check(self.records[-1]['tick'] + 2, self.event.tick, field='continuous_observation_tick')
        self.records.append(dict(tick=self.event.tick, phase=self.phase, **deepcopy(row)))
        reset = row['buffers'][NAMES[0]]['reset']
        if not self.initialized:
            self.check(1, reset, field='initialize_from_actual_reset')
            self.initialized = True
            self.reference.reset()
            self.pending_reads.clear()
            return
        ref = self.reference
        requests = ref.pending.pop(self.event.tick, {})
        self.current_requests = requests
        for name in NAMES:
            frame = row['buffers'][name]
            self.check(reset, frame['reset'], buffer=name, field='coherent_reset')
            self.check(ref.slots[name], frame['slots'], buffer=name, field='all_four_full_slots')
            if not reset:
                self.check(int(name in requests), frame['write']['valid'], buffer=name, field='derived_t2_write_valid')
                if name in requests:
                    self.check(requests[name], frame['write']['bits'], buffer=name, field='full_derived_t2_write_payload')
                dirty = [entry for entry in ref.slots[name] if entry['dirty']]
                self.check(int(bool(dirty)), frame['drain']['valid'], buffer=name, field='derived_drain_valid')
                if dirty and frame['drain']['ready']:
                    self.check(dirty[0]['payload'], frame['drain']['bits'], buffer=name, field='full_drain_payload')
        if reset:
            ref.reset()
            self.pending_reads.clear()
            return
        self.check_training_path(row)
        train = row['training']
        if train['valid'] and train['ready'] and self.phase != 'setup':
            self.check(True, bool(self.planned), field='every_actual_accept_planned')
            planned = self.planned.popleft()
            self.check(encoded_payload(planned, len(train['bits']['branches'])), train['bits'], field='full_actual_public_payload')
            expected = ref.accept(self.event.tick, planned)
            self.accepts.append(dict(tick=self.event.tick, phase=self.phase, transaction=deepcopy(planned),
                                     full_payload=deepcopy(train['bits']), derived_requests=expected))

    def capture_controls(self, observation):
        if self.failure is not None:
            return
        try:
            self.observe_controls(observation)
        except Exception as error:
            self.failure = error

    def observe_controls(self, observation):
        row, self.event = canonical(observation.value), observation.event
        self.check(True, self.observed_controls < self.capacity, field='bounded_preedge_capture_capacity')
        self.observed_controls += 1
        self.control_records.append(dict(tick=self.event.tick, phase=self.phase,
            buffers=deepcopy(row['buffers']), t0=deepcopy(row['t0']), training=deepcopy(row['training'])))
        if self.current_rise is None:
            return
        self.check(self.current_rise.event.tick + 1, self.event.tick, field='rise_preedge_transition_alignment')
        ref, reset = self.reference, row['buffers'][NAMES[0]]['reset']
        if reset:
            ref.reset()
            self.pending_reads.clear()
            self.current_requests = {}
            return
        for name in NAMES:
            frame = row['buffers'][name]
            self.check(0, frame['reset'], buffer=name, field='coherent_preedge_reset')
            self.check(ref.slots[name], frame['slots'], buffer=name, field='full_preedge_shadow_state')
            self.check(int(name in self.current_requests), frame['write']['valid'],
                       buffer=name, field='full_preedge_derived_write_valid')
            if name in self.current_requests:
                self.check(self.current_requests[name], frame['write']['bits'],
                           buffer=name, field='full_preedge_derived_write_payload')
            dirty = [entry for entry in ref.slots[name] if entry['dirty']]
            self.check(int(bool(dirty)), frame['drain']['valid'], buffer=name, field='full_preedge_drain_valid')
            if dirty and frame['drain']['ready']:
                self.check(dirty[0]['payload'], frame['drain']['bits'],
                           buffer=name, field='full_preedge_drain_payload')
        drains, actions = ref.step(self.current_requests,
            {name: row['buffers'][name]['drain']['ready'] for name in NAMES})
        details = dict(tick=self.current_rise.event.tick, controls_tick=self.event.tick,
                       committed_tick=self.event.tick + 1, phase=self.current_rise_phase)
        self.drains.extend(dict(**details, **item) for item in drains)
        self.actions.extend(dict(**details, **item) for item in actions)
        self.current_requests = {}

    def check_training_path(self, row):
        train, t0, tick = row['training'], row['t0'], self.event.tick
        inputs = project_inputs(train['bits'])
        self.check(inputs, t0['inputs'], field='actual_SC_T0_input_projection')
        accepted = int(bool(train['valid'] and train['ready']))
        self.check(accepted, t0['stage_fire'], field='public_accept_to_actual_T0_stage_fire')
        self.check(accepted & t0['enable'], t0['fire'], field='actual_SC_enable_gate')
        self.check(t0['predict_stage_fire'] & t0['enable'], t0['predict_fire'], field='actual_prediction_enable_gate')
        self.check(1 << (t0['predict_pc'] & 1), t0['predict_bank_mask'], field='actual_prediction_bank_decode')
        need_write = train_need_write(train['bits'])
        bank, bank_mask = inputs['pc'] & 1, 1 << (inputs['pc'] & 1)
        self.check(need_write, t0['need_write'], field='independent_T0_read_eligibility')
        self.check(bank_mask, t0['bank_mask'], field='actual_T0_bank_decode')
        conflict = need_write and t0['predict_fire'] and bank_mask == t0['predict_bank_mask']
        self.check(int(not conflict), t0['ready'], field='SC_ready_from_actual_request_inputs')
        indices = training_indices(inputs['pc'], t0['folded_path'], inputs['commonHR'])
        self.check({}, self.pending_reads, field='no_delayed_sampled_response_leftover')
        next_reads = {}
        for table in TABLES:
            read = t0['reads'][table]
            enabled = table not in ('globalTable_0', 'bwTable_0') or inputs['commonHR']['valid']
            valid = int(bool(t0['fire'] and need_write and enabled))
            self.check(valid, read['valid'], table=table, field='independent_T0_read_request_valid')
            self.check(indices[table], read['set_index'], table=table, field='T0_index_from_actual_PC_history_inputs')
            self.check(bank_mask, read['bank_mask'], table=table, field='actual_T0_read_request_bank')
            if valid and self.phase != 'setup':
                name = f'{table}_bank{bank}'
                next_reads[table] = dict(accepted_tick=tick, bank=bank, set_index=indices[table],
                    data=deepcopy(self.reference.memories[name].get(indices[table], [0] * width(name))))
        if next_reads:
            debug = train['bits']['meta']['sc']['debug']
            self.check(debug['predPathIdx'][0], indices['pathTable_0'], field='captured_path_index_matches_actual_train_hash')
            self.check(debug['predImliIdx'], indices['imliTable'], field='captured_imli_index_matches_actual_train_hash')
            self.check(debug['predBiasIdx'], indices['biasTable'], field='captured_bias_index_matches_actual_train_hash')
            preceding = self.control_records[-1]
            self.check(tick - 1, preceding['tick'], field='exact_preceding_request_event')
            self.check(train, preceding['training'], field='preedge_request_matches_public_accept')
            for table, expected in next_reads.items():
                fields = ('valid', 'set_index', 'bank_mask')
                self.check({key: preceding['t0']['reads'][table][key] for key in fields},
                    {key: t0['reads'][table][key] for key in fields}, table=table,
                    field='preedge_request_matches_accepted_rising_request')
                self.check(expected['data'], t0['reads'][table]['response'], table=table,
                    field='full_reference_SRAM_response_at_exact_accepting_edge',
                    accepted_tick=tick, request_controls_tick=tick - 1)
                self.confirmed_reads.append(dict(tick=tick, table=table, **deepcopy(expected),
                    request_controls_tick=tick - 1))
            self.t0_accepts.append(dict(tick=tick, indices=indices, bank=bank, tables=tuple(next_reads)))

    def summary(self):
        self.raise_failure()
        self.check(0, len(self.planned), field='all_submitted_feedback_accepted')
        self.check({}, self.reference.pending, field='all_derived_updates_retired')
        self.check({}, self.current_requests, field='no_last_uncommitted_table_write')
        self.check(0, sum(slot['dirty'] for slots in self.reference.slots.values() for slot in slots),
                   field='all_dirty_shadow_entries_drained')
        self.check({}, self.pending_reads, field='all_training_read_responses_retired')
        return dict(observed_cycles=self.observed_cycles, accepted_feedback=len(self.accepts),
            confirmed_drains=len(self.drains), confirmed_actions=len(self.actions),
            hardware_reset_observed=self.initialized, actual_observed_prestate_seeded_reference=False,
            independently_derived_t2_payloads=True, full_four_slot_comparison=True,
            actual_T0_pipeline_inputs_sampled=True, actual_preedge_transition_controls_sampled=True,
            observed_preedge_frames=self.observed_controls,
            accepted_T0_cycles=len(self.t0_accepts), full_training_read_responses=len(self.confirmed_reads),
            training_read_response_latency_cycles=1, sampled_read_response_offset_from_accept_ticks=0,
            read_association='DriveStable request -> immediate next post-evaluation RisingEdge response',
            actual_SRAM_response_seeded_reference=False, checks=asdict(self.scoreboard.status))
