"""Reset-derived full slot/T2/port comparison and held SRAM-read reference."""
from copy import deepcopy
from dataclasses import asdict

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from bpuverify.bpu.model.abtb.index import IndexReference
from bpuverify.bpu.monitor.abtb.write import ENTRY_NAMES
from bpuverify.bpu.model.abtb.write import WriteLineageReference
from bpuverify.bpu.model.abtb.write import cleanup_request
from bpuverify.bpu.monitor.abtb.history import ObservationHistory, readback_witness


def entry(payload):
    return {name: payload[name] for name in ENTRY_NAMES}


def read_inputs(values):
    inputs, boundary = values['hash_inputs'], values['index_boundary']
    token = IndexReference().token(inputs['pc'], inputs['normal_folds'][0], 0)
    pressure = [int(bool(boundary['enable'] and boundary['fire0'] and bank == token['bank']))
        for bank in range(4)]
    return pressure, token['entry_set']


def expected_ports(reference, pressure, read_index, read_data):
    """Only unqualified payloads and never-read SRAM outputs are omitted."""
    if not reference.initialized:
        raise ValueError('port comparison requires an actual reset')
    requests, _ = reference.current_requests()
    banks = []
    for bank, buffer in enumerate(reference.buffers):
        dirty = next((slot['payload'] for slot in buffer.slots if slot['dirty']), None)
        ready = int(reference.reset_remaining == 0)
        request = dict(valid=int(requests[bank] is not None))
        if requests[bank] is not None:
            request['bits'] = deepcopy(requests[bank])
        drain = dict(valid=int(dirty is not None), ready=int(ready and not pressure[bank]))
        if dirty is not None:
            drain['bits'] = deepcopy(dirty)
        write = dict(valid=int(dirty is not None and not pressure[bank]))
        if write['valid']:
            write.update(set_index=dirty['set_index'], way_mask=1 << dirty['way'],
                entries=[entry(dirty) for _ in range(4)])
        read = dict(valid=pressure[bank])
        if pressure[bank]:
            read['set_index'] = read_index
        sram = dict(ready=ready, write=write)
        if read_data[bank] is not None:
            sram['read'] = deepcopy(read_data[bank])
        banks.append(dict(slots=deepcopy(buffer.slots), plru=buffer.plru,
            request=deepcopy(request), write=request, drain=drain,
            read_input=read, reset_done=ready, sram=sram))
    return banks


def qualified(actual, expected):
    """Select only qualified fields; retain missing keys/lengths as differences."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        return {key: qualified(actual[key], value) for key, value in expected.items() if key in actual}
    if isinstance(expected, list) and isinstance(actual, (list, tuple)) and len(expected) == len(actual):
        return [qualified(value, wanted) for value, wanted in zip(actual, expected, strict=True)]
    return actual


class WriteChecker:
    def __init__(self, owner, *, max_frames=20000):
        if type(max_frames) is not int or not 1 <= max_frames <= 65536:
            raise ValueError('max_frames must be an integer in 1..65536')
        self.max_frames = max_frames
        self.owner, self.reference, self.index = owner, WriteLineageReference(), IndexReference()
        self.scoreboard = Scoreboard('bpu.integrated_ABTB_full_shadow_T2_and_SRAM_ports')
        self.read_data = [None] * 4
        self.records, self.confirmed_actions, self.pending_actions = [], [], []
        if getattr(owner, 'compact_history', False):
            self.records = ObservationHistory(readback_witness)
        self.failure = self.failed_frame = self.event = None

    def check(self, expected, actual, **request):
        self.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
                observed_event=self.event, request=dict(scope='ABTB_direct_observation', **request)))

    def capture(self, phase, observation):
        sibling_failure = getattr(getattr(self.owner, 'bypass', None), 'failure', None)
        if self.failure is not None or self.owner.failure is not None or sibling_failure is not None:
            return
        try:
            self.observe(phase, observation)
        except Exception as error:
            self.failure, self.failed_frame = error, dict(phase=phase, tick=observation.event.tick,
                value=deepcopy(observation.value))
            if self.owner.failure is None:
                self.owner.failure = error

    def observe(self, phase, observation):
        self.event = observation.event
        tick = self.event.tick
        self.check(True, phase in ('rising', 'preedge'), field='known_phase')
        if self.records:
            self.check(self.records[-1]['tick'] + 1, tick, field='continuous_two_phase_observation')
            self.check(True, len(self.records) < self.max_frames, field='bounded_complete_observation',
                max_frames=self.max_frames, frames=len(self.records))
        captured = observation.value if getattr(self.owner, 'compact_history', False) else deepcopy(observation.value)
        self.records.append(dict(phase=phase, tick=tick, value=captured))
        row = self.owner.current_rise.value if phase == 'rising' else self.owner.control_records[-1]
        row_tick = self.owner.current_rise.event.tick if phase == 'rising' else row['tick']
        self.check(tick, row_tick, field='same_event_as_parent_PH_ABTB_capture')
        bypass = self.owner.bypass.records[-1]
        self.check(tick, bypass['tick'], field='same_event_as_history_hash_capture')
        self.check(phase, bypass['phase'], field='same_phase_as_history_hash_capture')
        values, abtb = bypass['value'], row['abtb']
        self.check(values['reset'], observation.value['reset'], field='same_committed_reset')
        self.check(abtb['enable'], values['index_boundary']['enable'], field='shared_enable')
        pressure, read_index = read_inputs(values)
        ref = self.reference
        if ref.initialized:
            if not values['reset']:
                self.check(ref.counter.cells, list(abtb['cells']), field='all1024_independent_counters')
                self.check(ref.counter.plru, [list(bank['states']) for bank in abtb['replacers']],
                    field='all256_independent_replacer_states')
                wanted = expected_ports(ref, pressure, read_index, self.read_data)
                self.check(wanted, qualified(observation.value['banks'], wanted),
                    field='all_full_shadow_T2_bank_and_SRAM_ports')
            if phase == 'rising' and not values['reset']:
                self.confirmed_actions.extend(dict(checked_tick=tick, **item) for item in self.pending_actions)
                self.pending_actions.clear()
        else:
            self.check(1, values['reset'], field='actual_reset_required_before_state_checks')
        self.index.check(abtb['meta1'], abtb['enable'])
        if phase != 'preedge':
            return
        accepted = None
        if not values['reset']:
            if self.owner.accepts and self.owner.accepts[-1]['tick'] == tick:
                accepted = deepcopy(self.owner.accepts[-1]['transaction'])
            self.check(int(bool(abtb['fast']['valid'] and abtb['fast']['meta']['valid'] and abtb['enable'])),
                int(accepted is not None), field='exact_already_reassociated_parent_training_accept')
        # Read old SRAM contents before this edge's drain/write commits.
        if values['reset']:
            self.read_data = [None] * 4
        elif ref.reset_remaining == 0:
            for bank in range(4):
                if pressure[bank]:
                    self.check(True, all(payload is not None for payload in ref.sram[bank][read_index]),
                        field='SRAM_read_expectation_is_reset_derived', bank=bank, set_index=read_index)
                    self.read_data[bank] = [entry(payload) for payload in ref.sram[bank][read_index]]
        inputs, boundary = values['hash_inputs'], values['index_boundary']
        fire = bool(self.index.s2_valid and abtb['capture']['fire1']
            and not (inputs['s2_override'] or inputs['s3_override'] or inputs['redirect_valid']))
        result = ref.advance(reset=values['reset'], accepted=accepted, read_pressure=pressure,
            new_cleanup=cleanup_request(abtb['meta1'], fire=fire))
        if values['reset']:
            self.pending_actions.clear()
        else:
            self.pending_actions = [dict(tick=tick, **action) for action in result['actions']]
            wanted_writes = {write['bank']: write for write in result['writes']}
            for bank, actual in enumerate(abtb['writes']):
                self.check(int(bank in wanted_writes), actual['valid'],
                    field='independent_write_response_valid', bank=bank)
                if bank in wanted_writes:
                    self.check({name: wanted_writes[bank][name] for name in ('set_index', 'way', 'reset_counter')},
                        {name: actual[name] for name in ('set_index', 'way', 'reset_counter')},
                        field='independent_write_response_identity', bank=bank)
        self.index.advance(reset=values['reset'], enable=abtb['enable'], fire0=boundary['fire0'],
            fire1=abtb['capture']['fire1'], fire2=abtb['capture']['fire2'],
            s2_override=inputs['s2_override'], s3_override=inputs['s3_override'],
            redirect=inputs['redirect_valid'], pc=inputs['pc'], folded6=inputs['normal_folds'][0], tick=tick)

    def summary(self):
        if self.failure is not None:
            raise self.failure
        parent_check = getattr(self.owner, 'raise_failure', None)
        if callable(parent_check):
            parent_check()
        return dict(frames=len(self.records), checks=asdict(self.scoreboard.status),
            confirmed_actions=len(self.confirmed_actions), unconfirmed_actions=len(self.pending_actions),
            hardware_state_seeded_reference=False, drain_ready_seeded_reference=False,
            SRAM_read_expected_from_reset_and_predicted_writes=True,
            complete_prediction_hit_or_target_selection_reference_claimed=False)
