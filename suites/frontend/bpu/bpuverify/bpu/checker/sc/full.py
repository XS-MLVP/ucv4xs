"""Complete SC shadow/PLRU checking plus reset-derived threshold phase checks."""
from copy import deepcopy
from bpuverify.bpu.checker.sc.history import HistoryScChecker
from bpuverify.bpu.model.sc.model import canonical
from bpuverify.bpu.model.sc.model import NAMES
from bpuverify.bpu.model.sc.full import FullScReference
from bpuverify.bpu.model.sc.used import ThresholdReference, branch_effects

def feedback_from_public(bits):
    return dict(pc=bits['start_pcs'][0][0]['addr'], resolve_meta=deepcopy(bits['meta']), branches=[dict(position=row['bits']['cfiPosition'], taken=row['bits']['taken'], branch_type=row['bits']['attribute']['branchType']) if row['valid'] else None for row in bits['branches']])

def valid_vector(effects):
    return [int(any((effect['slot'] == slot and effect['read_eligible'] for effect in effects))) for slot in range(8)]

class FullScChecker(HistoryScChecker):

    def __init__(self, case, *, threshold_coverage=None, **options):
        super().__init__(case, **options)
        self.reference = FullScReference()
        self.threshold = ThresholdReference()
        self.threshold_registered_known = False
        self.threshold_checks = 0
        self.confirmed_actions = []
        self.cancelled_actions = []
        self.action_cursor = 0
        self.threshold_coverage = threshold_coverage
        self.threshold_accept = None

    def check_registers(self, row, *, check_registered):
        pipeline = row['used_pipeline']
        self.check(list(self.threshold.values), pipeline['thresholds'], field='reset_derived_four_thresholds')
        self.check(self.threshold.prior_fire, pipeline['t1_fire'], field='derived_T1_fire_register')
        self.check(self.threshold.prior_write, pipeline['t2_write_valid'], field='derived_T2_write_valid_register')
        if check_registered and self.threshold_registered_known:
            self.check(valid_vector(self.threshold.registered_effects), pipeline['t1_registered_vec'], field='all_eight_T1_registered_qualifiers')
        self.check(self.reference.plru, row['replacement'], field='all_ten_reset_derived_PLRU_states')

    def observe(self, observation):
        initialized = self.initialized
        super().observe(observation)
        row = canonical(observation.value)
        reset = row['buffers'][NAMES[0]]['reset']
        if reset:
            self.threshold.reset()
            self.threshold_registered_known = False
            self.threshold_accept = None
            if self.threshold_coverage is not None:
                self.threshold_coverage.cancel(observation.event.tick)
        if initialized:
            if not reset and self.threshold_coverage is not None:
                self.threshold_coverage.confirm(observation.event.tick,
                    row['used_pipeline']['thresholds'],check=self.check)
            self.check_registers(row, check_registered=not reset)
            newly_confirmed = self.actions[self.action_cursor:]
            for action in newly_confirmed:
                if reset:
                    self.cancelled_actions.append(dict(**deepcopy(action), checked_tick=observation.event.tick, cancellation='hardware_reset_overrides_pending_write'))
                    continue
                self.check(action['committed_tick'], observation.event.tick, field='full_shadow_action_confirmed_at_next_checked_rising')
                self.confirmed_actions.append(dict(**deepcopy(action), checked_tick=observation.event.tick))
            self.action_cursor = len(self.actions)
        if not reset and self.threshold_coverage is not None and row['t0']['fire']:
            # The inherited checker already proved public accept == enabled T0.
            self.threshold_accept = dict(tick=observation.event.tick,phase=self.phase,
                transaction=feedback_from_public(row['training']['bits']))

    def observe_controls(self, observation):
        row = canonical(observation.value)
        reset = row['buffers'][NAMES[0]]['reset']
        if not reset:
            self.check_registers(row, check_registered=True)
        super().observe_controls(observation)
        self.control_records[-1].update({name: deepcopy(row[name]) for name in ('used_pipeline', 'replacement', 't0', 'training')})
        if reset:
            self.threshold.reset()
            self.threshold_registered_known = False
            return
        registered_effects = self.threshold.registered_effects
        expected = self.threshold.advance(feedback_from_public(row['training']['bits']), t0_fire=row['t0']['fire'])
        pipeline = row['used_pipeline']
        if self.threshold_coverage is not None and expected['t1_write_valid']:
            source = self.threshold_accept
            self.check(True, source is not None,field='threshold_event_has_actual_public_source')
            self.check(source['tick'],observation.event.tick-1,field='threshold_event_exact_source_tick')
            self.check(branch_effects(source['transaction']),registered_effects,
                field='threshold_event_registered_votes_match_accepted_payload')
            if source['phase']!='setup':
                self.threshold_coverage.reach(expected['threshold_update'],
                    accepted_tick=source['tick'],controls_tick=observation.event.tick)
        self.check(expected['t0_write_valid'], pipeline['t0_valid_vec'], field='all_eight_T0_read_qualifiers')
        self.check(expected['t1_write_valid_vec'], pipeline['t1_valid_vec'], field='all_eight_T1_gated_qualifiers')
        self.check(expected['t1_write_valid'], pipeline['t1_write_valid'], field='derived_T1_aggregate_read_qualifier')
        self.check(list(expected['after']), pipeline['next_values'], field='full_threshold_net_vote_and_range_rejection')
        self.threshold_checks += 1
        if row['t0']['fire']:
            self.threshold_registered_known = True

    def summary(self):
        result = super().summary()
        self.check(len(self.actions), len(self.confirmed_actions) + len(self.cancelled_actions), field='no_unconfirmed_full_shadow_actions')
        result.update(full_dirty_overwrite_reference_supported=True, all_ten_PLRU_states_compared=True, reset_derived_threshold_checks=self.threshold_checks, confirmed_full_shadow_actions=len(self.confirmed_actions), reset_cancelled_full_shadow_actions=len(self.cancelled_actions), full_dirty_overwrite_actions=sum((row['kind'] == 'full_overwrite' for row in self.confirmed_actions)), threshold_values=list(self.threshold.values))
        if self.threshold_coverage is not None:
            self.check(None,self.threshold_coverage.pending,field='all_threshold_events_checked_or_reset_cancelled')
            result['threshold_events']=self.threshold_coverage.summary()
        return result
