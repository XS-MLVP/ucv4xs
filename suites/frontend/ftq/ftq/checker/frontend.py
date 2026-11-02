"""Input-owned TOP-002..018 composition, checked from complete phase records.

No internal DUT value is used as payload/owner oracle. Persistent storage,
receiver transport, output handoffs and final BPU train consumption stay
separate; a prediction install is not an invented ICache/ROB completion.
"""
from dataclasses import dataclass

from toffee import Scoreboard

from suites.frontend.ftq.ftq.bundle.abi import metadata_inputs, redirect_meta
from suites.frontend.ftq.ftq.checker.redirect import RedirectSchedule
from suites.frontend.ftq.ftq.checker.requests import geometry, prefetch_case, distance_bits, fetch_size
from suites.frontend.ftq.ftq.checker.handoffs import RequestHandoffs, RobTargets
from suites.frontend.ftq.ftq.checker.training import TrainingPath, age_after
from suites.frontend.ftq.ftq.transaction.types import Owner, Pointers, PrefetchLane, FetchLane


def owner(value):
    return Owner(value // 64, value % 64)


@dataclass(frozen=True, slots=True)
class Installed:
    uid: tuple
    identity: int
    prediction: object
    tick: int
    allocation: tuple
    parent: tuple | None = None


class FtqFrontend:
    def __init__(self):
        self.scoreboard = Scoreboard('ftq.frontend-transactions')
        self.epoch = 0
        self.resetting = self.failed = False
        self.bpu = self.pnr = self.pf = self.fetch = self.commit = 0
        self.rob_commit = 127
        self.stalls = 0
        self.exception = self.satp = self.flag_owner = 0
        self.reasons = dict.fromkeys((2, 3, 5, 6, 7, 8, 9), 0)
        self.entries = [None] * 64
        self.metadata = [None] * 64
        self.meta_uids = [None] * 64
        self.meta_writes = {}
        self.receivers = RedirectSchedule()
        self.training = TrainingPath()
        self.requests, self.retirements = RequestHandoffs(), RobTargets()
        self.offers, self.prediction_done, self.installed = {}, {}, {}
        self.candidate = self.candidate_revision = None
        self.offer_serial = 0
        self.attempts = {}
        self.handoffs, self.redirect_edges = [], []
        self.prediction_edges = []
        self.unknown = set()

    def require_clean(self):
        if self.failed or self.scoreboard.status.failed:
            raise RuntimeError('FTQ frontend has a prior comparison or lifecycle failure')

    def check(self, expected, actual):
        self.scoreboard.check(expected=expected, actual=actual)

    def present(self, frame, revision):
        self.require_clean()
        if self.candidate is not None and (frame.prediction is None or revision != self.candidate_revision or frame.reset):
            self.prediction_done[self.candidate] = 'reset-cancelled-offer' if frame.reset else 'withdrawn-before-acceptance'
            self.candidate = None
        if frame.prediction is not None and self.candidate is None and not frame.reset:
            self.offer_serial += 1
            self.candidate = (self.epoch, revision, self.offer_serial)
            self.candidate_revision = revision
            self.offers[self.candidate] = frame.prediction

    def begin_slot(self, frame, revision, slot):
        if frame.reset and not self.resetting:
            self.epoch += 1
        self.present(frame, revision)
        if self.candidate is not None:
            self.attempts.setdefault(self.candidate, []).append(slot)

    def state(self, frame):
        return (0, 0, 0, 0, 0) if frame.reset else (self.bpu, self.pnr, self.pf, self.fetch, self.commit)

    def controls(self, frame, slot):
        bpu, pnr, pf, fetch, commit = self.state(frame)
        receiver = self.receivers.view(frame, self.epoch, slot)
        cache = self.training.visible(receiver.backend, reset=frame.reset)
        # DefaultConfig declared counter has log2Ceil(8)+1 =4 bits. This is
        # transport geometry, not a claim it saturates for arbitrary stalls.
        stalls = 0 if frame.reset else self.stalls
        ready = distance_bits(bpu, commit) < 64 and distance_bits(bpu, fetch) < 32 and stalls < 8
        prediction = frame.prediction
        ptr = (64 * prediction.s3_flag + prediction.s3_ptr if prediction and prediction.s3_override
               else 64 * prediction.s2_flag + prediction.s2_ptr if prediction and prediction.s2_override else bpu)
        write = bool(prediction is not None and (ready or prediction.s2_override or prediction.s3_override)
                     and receiver.selected is None)
        return receiver, cache, ready, ptr, write

    def request_info(self, frame, slot):
        bpu, pnr, pf, fetch, commit = self.state(frame)
        receiver, cache, ready, ptr, write = self.controls(frame, slot)
        info = {}
        for name, position in (('prefetch', pf), ('fetch', fetch)):
            valid = age_after(bpu, position) and receiver.selected is None
            if name == 'fetch':
                valid = valid and distance_bits(position, commit) < 63
            installed = tuple(self.entries[(position + lane) % 64] for lane in range(2))
            shapes = tuple(None if item is None else geometry(item.prediction.start_pc, item.prediction.end_position)
                           for item in installed)
            flag_owner = 0 if frame.reset else self.flag_owner
            has_flags = bool(not frame.reset and (self.exception or self.satp))
            eligible = age_after(pnr, (position + 1) % 128) and not (
                has_flags and flag_owner in (position, (position + 1) % 128))
            if name == 'prefetch':
                second = prefetch_case(*shapes, eligible=eligible) if all(shape is not None for shape in shapes) else 0
            else:
                second = bool(eligible and all(item is not None for item in installed)
                    and shapes[0].start // 2048 == shapes[1].start // 2048
                    and sum(fetch_size(item.prediction.start_pc, item.prediction.end_position) for item in installed) <= 32)
            info[name] = (valid, second, position, installed, shapes)
        return info

    def check_phase(self, frame, observations, slot):
        self.require_clean()
        receiver, cache, ready, ptr, write = self.controls(frame, slot)
        bpu, pnr, pf, fetch, commit = self.state(frame)
        expected_owners = Pointers(owner(bpu), (owner(pf), owner((pf + 1) % 128)),
            (owner(fetch), owner((fetch + 1) % 128)), owner(commit), owner(pnr))
        self.check(expected_owners, observations['ftq.owners'])
        actual = observations['ftq.backend_write']
        self.check((ready, write, owner(bpu)), (actual.ready, actual.wen, actual.bpu))
        if write:
            self.check((ptr % 64, frame.prediction.start_pc), (actual.index, actual.start_pc))
        flush = observations['ftq.flush']
        prediction = frame.prediction
        s2, s3 = bool(prediction and prediction.s2_override), bool(prediction and prediction.s3_override)
        self.check((s2, s3, s3, receiver.selected is not None, receiver.backend is not None),
                   (flush.s2_valid, flush.s3_valid, flush.ifu_s3_flush, flush.redirect_flush, flush.to_ifu_redirect))
        if s2:
            self.check((prediction.s2_flag, prediction.s2_ptr), (flush.s2_flag, flush.s2_value))
        if s3:
            self.check((prediction.s3_flag, prediction.s3_ptr) * 2,
                       (flush.s3_flag, flush.s3_value, flush.ifu_s3_flag, flush.ifu_s3_value))
        actual = observations['ftq.redirect']
        self.check(receiver.selected is not None, actual is not None)
        if receiver.selected is not None:
            value = receiver.selected
            request = value.request
            self.check((((request.pc >> 1) + request.offset) % (1 << 49), request.taken, request.branch_type, request.ras_action),
                       (actual.cfi_pc, actual.taken, actual.branch_type, actual.ras_action))
            if value.target is not None:
                self.check(value.target, actual.target)
            else:
                self.unknown.add((value.uid, 'redirect-target'))
            stored = self.receivers.read_meta
            if stored is not None:
                expected = {key: stored['redirectMeta_' + key] for key in redirect_meta(with_target=False)}
                self.check(expected, dict(actual.metadata))
                self.check((expected['phr_phrPtr_value'], expected['commonHRMeta_ghr']), (actual.meta_phr, actual.meta_ghr))
            else:
                self.unknown.add((value.uid, 'redirect-metadata'))
        actual = observations['ftq.training']
        self.check(cache is not None, actual is not None)
        if cache is not None:
            expected = cache.value
            self.check((expected.start_pc, expected.start_pc_vec, expected.branch_mask, len(expected.branches)),
                       (actual.start_pc, actual.start_pc_vec, actual.branch_mask, len(actual.branches)))
            for report, want, got in zip(cache.selected, expected.branches, actual.branches, strict=True):
                self.check((want.position, want.taken, want.mispredict, want.branch_type, want.ras_action),
                           (got.position, got.taken, got.mispredict, got.branch_type, got.ras_action))
                if report.target_known:
                    self.check(want.target, got.target)
            if cache.metadata_known:
                self.check((expected.meta_phr, expected.meta_ghr, expected.meta_common_valid, dict(expected.metadata)),
                           (actual.meta_phr, actual.meta_ghr, actual.meta_common_valid, dict(actual.metadata)))
            else:
                self.unknown.add((cache.entry.reports[0].uid, 'training-metadata'))
        for name, (valid, second, position, installed, shapes) in self.request_info(frame, slot).items():
            actual = observations['ftq.' + name]
            self.check(valid, actual.valid)
            # Pointer outputs are always defined, even for inactive payloads.
            self.check((position % 64, position // 64, (position + 1) % 64),
                       (actual.index, actual.index_flag, actual.req1_index))
            if not valid:
                continue
            self.check(second, actual.case if name == 'prefetch' else actual.req1_valid)
            for lane in range(2 if second else 1):
                item, shape = installed[lane], shapes[lane]
                assert item is not None, 'FTQ exposed an unowned request'
                pointer = owner((position + lane) % 128)
                if name == 'prefetch':
                    want = PrefetchLane(shape.start, shape.next_line, shape.set0, shape.set1, shape.cross_line, pointer)
                else:
                    want = FetchLane(shape.start, shape.next_line, shape.set0, shape.set1,
                        item.prediction.taken, item.prediction.end_position, shape.bank0, shape.bank1, pointer)
                self.check(want, actual.lanes[lane])
                if lane == 0:
                    if name == 'prefetch':
                        self.check((shape.start, shape.next_line, shape.set0, shape.set1, shape.cross_line),
                                   (actual.start, actual.next_line, actual.set0, actual.set1, actual.cross_line))
                    else:
                        self.check((shape.start, shape.start, shape.next_line, item.prediction.taken, item.prediction.end_position,
                                    shape.bank0, shape.bank1), (actual.start, actual.addr0, actual.addr1, actual.taken,
                                    actual.end_position, actual.bank0, actual.bank1))
                elif name == 'prefetch':
                    self.check(shape.start, actual.req1_start)
            flag = not frame.reset and position == self.flag_owner
            if name == 'prefetch':
                self.check(self.exception if flag else 0, actual.backend_exception)
            else:
                self.check((bool(flag and self.exception), bool(flag and self.satp)), (actual.backend_exception, actual.satp_flush))
        topdown = observations['ftq.topdown']
        if not frame.reset:
            self.check(self.reasons, dict(topdown.reasons))
        self.check(receiver.backend is not None, bool(topdown.backend_redirect))
        if receiver.backend is not None:
            request = receiver.backend.request
            self.check((request.debug_ctrl, request.debug_memvio, int(request.branch_type == 1),
                        int(request.branch_type == 3 and not (request.ras_action & 1)), int(request.ras_action == 1)),
                       (topdown.control_flow, topdown.memory_violation, topdown.tage_miss, topdown.ittage_miss, topdown.ras_miss))

    def advance_slot(self, frame, slot, before, after_snapshot, tick):
        self.require_clean()
        try:
            self.check_phase(frame, before, slot)
            receiver, cache, ready, ptr, write = self.controls(frame, slot)
            reports = self.training.reports(frame, receiver, self.epoch, slot)
            requests = self.request_info(frame, slot)
            old_bpu, old_pnr, old_pf, old_fetch, old_commit = self.state(frame)
            reason = ('reset-cancelled-offer' if frame.reset else
                      'redirect-cancelled-offer' if receiver.selected is not None else 'replaced-offer')
            self.requests.sync(requests, self.epoch, tick - 1, reason=reason)
            self.requests.consume(frame, requests, tick)
            self.training.advance(frame, reports, receiver, ptr if write and ready else None, self.metadata, tick,
                                  meta_uids=self.meta_uids)
            target = (64 * frame.commit[0] + frame.commit[1]) if frame.commit is not None else self.rob_commit
            self.retirements.advance(frame, self.epoch, slot, old_commit, target, self.entries, tick)
            if frame.prediction is not None:
                self.prediction_edges.append((self.candidate, tick, ready, write, ptr, frame.reset))
            reasons = dict.fromkeys(self.reasons, 0)
            if receiver.backend is not None:
                request = receiver.backend.request
                if request.debug_ctrl:
                    reasons[3], reasons[5], reasons[6] = int(request.branch_type == 1), int(request.branch_type == 3 and not (request.ras_action & 1)), int(request.ras_action == 1)
                elif request.debug_memvio:
                    reasons[7] = 1
                else:
                    reasons[8] = 1
            if distance_bits(old_bpu, old_commit) >= 64:
                reasons[9] = 1
            elif distance_bits(old_bpu, old_fetch) >= 32 or self.stalls >= 8:
                reasons[2] = 1
            if frame.reset:
                self.bpu = self.pnr = self.pf = self.fetch = self.commit = 0
                self.rob_commit = 127
                self.stalls = self.exception = self.satp = self.flag_owner = 0
                self.reasons = dict.fromkeys(self.reasons, 0)
            else:
                self.reasons = reasons
                self.stalls = (self.stalls + 1) % 16 if cache is not None and not frame.consumers.train else 0
                prediction = frame.prediction
                if prediction is not None and prediction.s3_override:
                    self.bpu = (64 * prediction.s3_flag + prediction.s3_ptr + 1) % 128
                elif prediction is not None and prediction.s2_override:
                    self.bpu = (64 * prediction.s2_flag + prediction.s2_ptr + 1) % 128
                elif write and ready:
                    self.bpu = (old_bpu + 1) % 128
                if frame.meta is not None:
                    self.pnr = (64 * frame.meta.flag + frame.meta.index + 1) % 128
                for name, enabled in (('prefetch', frame.consumers.prefetch), ('fetch', frame.consumers.mainpipe)):
                    valid, second, position, installed, _ = requests[name]
                    if valid and enabled:
                        count = (2 if second else 1) if name == 'prefetch' else (2 if frame.consumers.real_two_fetch else 1)
                        if name == 'fetch' and count == 2:
                            assert second, 'ICache reports realTwoFetch on an ineligible second request'
                        for lane in range(count):
                            self.handoffs.append((name, installed[lane].uid, tick))
                        setattr(self, 'pf' if name == 'prefetch' else 'fetch', (position + count) % 128)
                if prediction is not None:
                    for stage in ('s2', 's3'):
                        if getattr(prediction, stage + '_override'):
                            rewind = 64 * getattr(prediction, stage + '_flag') + getattr(prediction, stage + '_ptr')
                            for name, old in (('pf', old_pf), ('fetch', old_fetch)):
                                if old == rewind or age_after(old, rewind):
                                    setattr(self, name, rewind)
                selected = receiver.selected
                if selected is not None:
                    request = selected.request
                    itself = selected.source == 'backend' and request.level and (request.offset == 0 or request.offset == 1 and not request.is_rvc)
                    rewind = (64 * request.flag + request.index + (not itself)) % 128
                    self.bpu = self.pnr = self.pf = self.fetch = rewind
                    self.redirect_edges.append((selected.uid, tick))
                if receiver.backend is not None:
                    request = receiver.backend.request
                    self.exception = request.ipf + 2 * request.igpf + 3 * request.iaf
                    self.satp = request.satp_flush
                    if self.exception or self.satp:
                        itself = request.level and (request.offset == 0 or request.offset == 1 and not request.is_rvc)
                        self.flag_owner = (64 * request.flag + request.index + (not itself)) % 128
                elif distance_bits(old_fetch, self.flag_owner) >= 3:
                    self.exception = self.satp = 0
                if frame.commit is not None:
                    self.rob_commit = 64 * frame.commit[0] + frame.commit[1]
                if old_commit == self.rob_commit or age_after(self.rob_commit, old_commit):
                    self.commit = (old_commit + 1) % 128
            self.receivers.advance(frame, self.epoch, slot, self.metadata, meta_uids=self.meta_uids, tick=tick)
            if write:
                uid = self.candidate if self.candidate is not None else (self.epoch, slot, 'reset-store')
                previous = self.entries[ptr % 64]
                is_revision = (bool(frame.prediction.s2_override or frame.prediction.s3_override)
                    and previous is not None and previous.identity == ptr and previous.uid[0] == self.epoch)
                installed = Installed(uid, ptr, frame.prediction, tick,
                    previous.allocation if is_revision else uid, previous.uid if is_revision else None)
                self.entries[ptr % 64] = installed
                self.installed[uid] = installed
                if self.candidate is not None:
                    self.prediction_done[self.candidate] = 'installed'
                    self.candidate = None
            elif self.candidate is not None and receiver.selected is not None:
                self.prediction_done[self.candidate] = 'redirect-suppressed'
                self.candidate = None
            if frame.meta is not None:
                image = {key: frame.meta.fields.get(key, 0) for key in metadata_inputs()}
                self.metadata[frame.meta.index] = image
                meta_uid = (self.epoch, slot, 'meta')
                self.meta_uids[frame.meta.index] = meta_uid
                self.meta_writes[meta_uid] = (frame.meta.flag, frame.meta.index, image)
            self.resetting = frame.reset
            self.check_phase(frame, after_snapshot, slot)
            reason = ('reset-cancelled-offer' if frame.reset else
                'redirect-cancelled-offer' if receiver.selected is not None else
                'override-retry' if frame.prediction and (frame.prediction.s2_override or frame.prediction.s3_override)
                else 'replaced-offer')
            self.requests.sync(self.request_info(frame, slot), self.epoch, tick, reason=reason)
        except BaseException:
            self.failed = True
            raise

    def audit(self):
        self.require_clean()
        try:
            pending = self.training.audit()
            self.requests.audit()
            self.receivers.audit()
            self.retirements.audit()
            assert set(self.offers) == set(self.prediction_done) | ({self.candidate} if self.candidate is not None else set()), 'FTQ lost prediction offer ancestry'
            assert not ({self.candidate} & set(self.prediction_done)), 'FTQ terminal prediction remains pending'
            assert {uid for uid, status in self.prediction_done.items() if status == 'installed'} == set(self.installed) & set(self.offers), 'FTQ lost prediction installation ancestry'
            for uid, child in self.receivers.resolve_children.items():
                assert child in self.training.offered, 'FTQ lost forwarded IFU report ancestry'
            for _, meta_uid in self.training.response_meta.items():
                assert meta_uid is None or meta_uid in self.meta_writes, 'FTQ unowned training metadata'
            for _, meta_uid in self.receivers.response_meta.items():
                assert meta_uid is None or meta_uid in self.meta_writes, 'FTQ unowned redirect metadata'
            assert self.handoffs == self.requests.handoffs, 'FTQ lost a committed consumer handoff'
            assert self.redirect_edges == [(uid, tick) for uid, (status, tick) in self.receivers.redirect_done.items()
                                           if status == 'applied'], 'FTQ lost redirect application evidence'
            return pending
        except BaseException:
            self.failed = True
            raise

    def receipt(self):
        pending = self.audit()
        return dict(predictions=tuple(self.offers), prediction_done=tuple(self.prediction_done.items()),
                    pending_offer=self.candidate, installed=tuple(self.installed), pending_reports=tuple(sorted(pending)),
                    resolve_offered=tuple(self.training.offered), resolve_accepted=tuple(self.training.accepted),
                    resolve_done=tuple(self.training.terminals.items()), handoffs=tuple(self.handoffs),
                    redirect_edges=tuple(self.redirect_edges), unknown=tuple(sorted(self.unknown)),
                    prediction_edges=tuple(self.prediction_edges), requests=self.requests.receipt(),
                    receivers=self.receivers.receipt(), retirements=self.retirements.receipt(),
                    training_metadata=tuple(self.training.response_meta.items()),
                    training_handoffs=tuple(self.training.cache_handoffs))

    def quiet(self, frame, slot):
        if self.audit() or self.candidate is not None or self.receivers.audit() or self.retirements.audit():
            return False
        receiver = self.receivers.view(frame, self.epoch, slot)
        if receiver.selected is not None or receiver.ifu_resolve is not None:
            return False
        requests = self.request_info(frame, slot)
        return not (requests['prefetch'][0] and frame.consumers.prefetch
                    or requests['fetch'][0] and frame.consumers.mainpipe)
