"""Region state from reset and independently planned, genuinely accepted writes."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict, replace
from toffee import CheckContext, Scoreboard, ScoreboardMode
from bpuverify.bpu.model.sc.model import canonical, encoded_payload
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.ittage.model.region import IttageRegionModel
from bpuverify.bpu.model.ittage_region import allocation_rule, consumption_rule
from bpuverify.bpu.checker.ittage import check_metadata, check_coherent_target


class DirectoryPhrChecks(BpuPhrChecker):
    def compare(self, expected, actual, **request):
        self.check(expected, actual, **request)


class RegionChecker:
    def __init__(self, coverage=None):
        self.coverage = coverage
        self.model = IttageRegionModel()
        self.board = Scoreboard('bpu.ittage_region_directory')
        self.plans, self.expected_writes = deque(), deque()
        self.writes, self.accepts, self.target_updates = [], [], deque(maxlen=12)
        self.initialized, self.failure, self.last_tick, self.last_phase = False, None, None, None
        self.pending_write = None
        self.allocations, self.bypass_pending, self.allocations_checked = {}, {}, set()
        self.frames = 0

    def plan_feedback(self, transaction, source=None):
        self.raise_failure()
        value = canonical(asdict(transaction))
        branch, = value['branches']
        if branch is None or branch['branch_type'] != 3 or not branch['taken']:
            raise ValueError('region reference requires one taken indirect feedback')
        metadata = value['resolve_meta']['ittage']
        provider = metadata['provider']['valid']
        correct_unconfident = (provider and metadata['providerCnt_value'] == 0
            and metadata['providerTarget_addr'] == branch['target'])
        allocated = bool(branch['mispredict'] and metadata['allocate']['valid'] and not correct_unconfident)
        if source is None and self.coverage is not None:
            raise ValueError('event coverage requires genuine prediction and metadata source identities')
        origin = {}
        if source is not None:
            self.check(source.meta.resolve, transaction.resolve_meta, 'unmodified genuine prediction metadata')
            origin = dict(prediction_tick=source.prediction_tick, meta_tick=source.meta_tick)
        self.plans.append((encoded_payload(value), value, allocated, origin))

    def check(self, expected, actual, point):
        self.board.check(expected=canonical(expected), actual=canonical(actual),
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                sequence_id=self.last_tick, request=dict(point=point, phase=self.last_phase,
                    expected_regions=self.model.regions, expected_writes=list(self.expected_writes))))

    def capture(self, phase, observation):
        if self.failure is None:
            try:
                self.observe(phase, observation)
            except Exception as error:
                self.failure = error

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def status_report(self):
        status = self.board.status
        # Exception objects need not support deepcopy; keep the original diagnostic text.
        return dict(asdict(replace(status, first_failure=None)),
            first_failure=None if status.first_failure is None else str(status.first_failure))

    def observe(self, phase, observation):
        row, tick = observation.value, observation.event.tick
        if self.last_tick is not None:
            self.check(self.last_tick + 1, tick, 'complete observation ticks')
            self.check('rising' if self.last_phase == 'preedge' else 'preedge', phase, 'alternating phases')
        self.last_tick, self.last_phase = tick, phase
        self.frames += 1
        if not self.initialized:
            self.check(('preedge', 1), (phase, row['reset']), 'genuine reset required, never seed from DUT')
        if self.initialized:
            state = [dict(valid=int(region is not None), region=region or 0) for region in self.model.regions]
            self.check(state, row['state'], 'all sixteen valid and region payloads')
            candidate = deepcopy(self.model)
            allocation = candidate.allocate(row['ports']['write_region'] << 20)
            self.check(allocation.pointer, row['ports']['write_pointer'], 'independent free/reuse/PLRU write pointer')
            for pointer, response in zip(row['ports']['requests'], row['ports']['responses'], strict=True):
                self.check(True, type(pointer) is int and 0 <= pointer < 16, 'region request pointer range')
                region = self.model.regions[pointer]
                self.check(dict(hit=int(region is not None), region=region or 0), response, 'complete region read port')
            for update in row['ports']['updates']:
                bypass = bool(row['ports']['write_valid'] and update['region'] == row['ports']['write_region'])
                hit = update['region'] in self.model.regions
                wanted = allocation.pointer if bypass else self.model.regions.index(update['region']) if hit else 0
                self.check((int(bypass or hit), wanted), (update['hit'], update['pointer']), 'update port lookup/write bypass')
        if phase == 'rising' and self.pending_write is not None:
            if self.coverage is not None:
                self.coverage.sample('allocation', 'checked', dict(self.pending_write['source'],
                    write_tick=self.pending_write['tick'], committed_tick=tick))
                self.allocations_checked.add(self.pending_write['source']['pc'])
            self.writes.append(self.pending_write)
            self.pending_write = None
        if phase != 'preedge':
            return
        if row['reset']:
            self.model = IttageRegionModel()
            self.initialized = True
            self.check(0, len(self.plans) + len(self.expected_writes), 'no planned feedback discarded by reset')
            return
        if row['feedback_valid'] and row['feedback_ready']:
            self.check(True, bool(self.plans), 'every actual feedback must be planned')
            expected, transaction, allocated, origin = self.plans.popleft()
            self.check(expected, row['feedback'], 'complete actual accepted feedback payload')
            target = transaction['branches'][0]['target']
            source = dict(tick=tick, pc=transaction['pc'], target=target, allocated=allocated, **origin)
            self.accepts.append(source)
            if allocated and self.coverage is not None:
                self.check(False, source['pc'] in self.allocations, 'one allocation source per planned predictor context')
                source.update(rule=allocation_rule(self.model.regions, source['pc'], target),
                    before_regions=self.model.regions)
                self.allocations[source['pc']] = source
                self.coverage.sample('allocation', 'reached', source)
                if source['rule'] == 'pc-region-bypass':
                    self.bypass_pending[source['pc']] = source
            if allocated and target >> 19 != transaction['pc'] >> 19:
                self.expected_writes.append(source)
        if row['ports']['write_valid']:
            self.check(True, bool(self.expected_writes), 'no unplanned region write')
            source = self.expected_writes.popleft()
            self.check(source['target'] >> 19, row['ports']['write_region'], 'region write from accepted public feedback')
            allocation = self.model.allocate(source['target'] << 1)
            self.pending_write = dict(tick=tick, pointer=allocation.pointer, reused=allocation.reused,
                evicted_region=allocation.evicted_region, region=source['target'] >> 19, source=source)
        for table, update in enumerate(row['target_updates']):
            if update['valid']:
                self.target_updates.append(dict(tick=tick, table=table, **update))

    def check_consumer(self, resident, source, phr, board):
        """Complete metadata and exact S3; directory inputs are never DUT-seeded."""
        self.raise_failure()
        row, model = resident['input'], deepcopy(resident['model'])
        pointer = resident['pointer']
        if pointer is not None:
            target = self.model.decode(pointer, resident['offset'] << 1) >> 1
            model.entries = {table: replace(entry, target=target) for table, entry in model.entries.items()}
        event = dict(rule=consumption_rule(resident, self.model.regions), pc=row['pc'], pointer=pointer,
            target=model.target(), prediction_tick=source.prediction_tick, meta_tick=source.meta_tick)
        if self.coverage is not None:
            self.coverage.sample('consumption', 'reached', event)
        context = CheckContext(board.name, ScoreboardMode.DIRECT, sequence_id=source.meta_tick,
            request=dict(input=row, expected_entries=model.entries, event=event))
        board.check(expected=row['pc'], actual=source.prediction.start_pc, context=context)
        check_metadata(board, model, source, phase='complete-resident-readback')
        check_coherent_target(board, phr, source, model.target(), row['target'], row['position'], context)
        if row['pc'] in self.bypass_pending:
            origin = self.bypass_pending[row['pc']]
            self.check(('rising', None, 0), (self.last_phase, self.pending_write, len(self.expected_writes)),
                'PC-region bypass must complete accepted feedback without a directory write')
            self.check(origin['before_regions'], self.model.regions, 'PC-region bypass preserves all directory entries')
            self.check(True, self.last_tick > origin['tick'], 'bypass consumer follows the accepted feedback')
            self.coverage.sample('allocation', 'checked', dict(origin, consumer_prediction_tick=source.prediction_tick,
                consumer_meta_tick=source.meta_tick, committed_tick=self.last_tick))
            self.allocations_checked.add(row['pc'])
            del self.bypass_pending[row['pc']]
        if self.coverage is not None:
            self.coverage.sample('consumption', 'checked', event)

    def summary(self):
        self.raise_failure()
        self.check(True, self.initialized, 'genuine reset observed')
        self.check(('rising', None, 0, 0), (self.last_phase, self.pending_write,
            len(self.plans), len(self.expected_writes)), 'all accepted feedback and region effects drained')
        self.check((0, sorted(self.allocations)), (len(self.bypass_pending), sorted(self.allocations_checked)),
            'every qualified allocation including PC bypass completed')
        return dict(frames=self.frames, writes=self.writes, accepted_feedback=self.accepts,
            regions=self.model.regions, recent_target_updates=list(self.target_updates),
            checks=self.status_report(), expected_state_seeded_from_DUT=False,
            full_prediction_hash_or_SRAM_reference_claimed=False)

    def diagnostics(self):
        return dict(last_tick=self.last_tick, phase=self.last_phase, failure=repr(self.failure),
            writes=self.writes, accepted_feedback=self.accepts, regions=self.model.regions,
            recent_target_updates=list(self.target_updates), pending_region_writes=list(self.expected_writes),
            pending_feedback=len(self.plans), pending_observed_effect=self.pending_write,
            pending_bypasses=list(self.bypass_pending.values()),
            checks=self.status_report(), expected_state_seeded_from_DUT=False)
