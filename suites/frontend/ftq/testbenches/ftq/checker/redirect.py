"""Input-owned ahead/registered redirect schedule and selected-target capture."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RedirectInput:
    uid: tuple
    source: str
    request: object
    target: int | None  # Public halfword target; None is uninitialized RAS data.
    target_meta_uid: tuple | None = None


@dataclass(frozen=True, slots=True)
class ReceiverView:
    backend: RedirectInput | None
    selected: RedirectInput | None
    ifu_resolve: RedirectInput | None
    read_index: int
    ahead_match: bool


class RedirectSchedule:
    def __init__(self):
        self.ahead = None
        self.pending_backend = self.pending_ifu = self.pending_resolve = None
        self.read_meta = None
        self.read_meta_uid = None
        self.offered, self.redirect_done, self.resolve_done = {}, {}, {}
        self.response_meta, self.resolve_children = {}, {}
        self.ahead_inputs = {}

    def view(self, frame, epoch, slot):
        current = frame.backend_redirect
        matched = current is not None and (current.flag, current.index) == self.ahead
        backend = (RedirectInput((epoch, slot, 'backend'), 'backend', current, current.target >> 1)
                   if matched else self.pending_backend)
        if current is not None and not matched:
            index = current.index
        elif current is None and frame.ahead is not None:
            index = frame.ahead[1]
        else:
            index = frame.ifu_redirect.index if frame.ifu_redirect is not None else 0
        return ReceiverView(backend, backend if backend is not None else self.pending_ifu,
            None if frame.reset else self.pending_resolve, index, matched)

    def advance(self, frame, epoch, slot, metadata, *, meta_uids=None, tick=None):
        before = self.view(frame, epoch, slot)
        backend = (RedirectInput((epoch, slot, 'backend'), 'backend', frame.backend_redirect,
            frame.backend_redirect.target >> 1) if frame.backend_redirect is not None else None)
        value = frame.ifu_redirect
        if value is not None:
            if value.ras_action == 1:
                stored = metadata[value.index]
                target = None if stored is None else stored['redirectMeta_ras_topRetAddr_addr']
                target_meta = None if meta_uids is None else meta_uids[value.index]
            else:
                target = value.target >> 1
                target_meta = None
            ifu = RedirectInput((epoch, slot, 'ifu'), 'ifu', value, target, target_meta)
        else:
            ifu = None
        for event in (backend, ifu):
            if event is not None:
                assert event.uid not in self.offered, 'FTQ duplicate redirect offer UID'
                self.offered[event.uid] = event
        if before.selected is not None:
            uid = before.selected.uid
            assert uid in self.offered and uid not in self.redirect_done, 'FTQ duplicate/unowned redirect application'
            self.redirect_done[uid] = ('reset-suppressed-application' if frame.reset else 'applied'), tick
            self.response_meta[uid] = self.read_meta_uid
        if self.pending_ifu is not None and before.backend is not None:
            uid = self.pending_ifu.uid
            assert uid not in self.redirect_done
            self.redirect_done[uid] = 'backend-arbitration-cancelled', tick
        if self.pending_resolve is not None:
            uid = self.pending_resolve.uid
            assert uid not in self.resolve_done
            self.resolve_done[uid] = ('reset-cancelled' if frame.reset else 'forwarded-to-resolve'), tick
            if not frame.reset:
                self.resolve_children[uid] = uid + ('resolve',)
        if ifu is not None:
            if before.backend is not None:
                self.redirect_done[ifu.uid] = 'backend-blocked-at-receive', tick
                self.resolve_done[ifu.uid] = 'backend-blocked-at-receive', tick
            elif not ifu.request.can_train:
                self.resolve_done[ifu.uid] = 'can-train-filtered', tick
            elif frame.reset:
                self.resolve_done[ifu.uid] = 'reset-cancelled-before-register', tick
        if frame.ahead is not None:
            self.ahead_inputs[(epoch, slot, 'ahead')] = frame.ahead, tick
        self.read_meta = metadata[before.read_index]
        self.read_meta_uid = None if meta_uids is None else meta_uids[before.read_index]
        self.ahead = frame.ahead if backend is None else None
        self.pending_backend = backend if backend is not None and not before.ahead_match else None
        self.pending_ifu = ifu if before.backend is None else None
        self.pending_resolve = ifu if (self.pending_ifu is not None and ifu.request.can_train and not frame.reset) else None
        return before

    def audit(self):
        pending = {event.uid for event in (self.pending_backend, self.pending_ifu) if event is not None}
        assert not (pending & set(self.redirect_done)), 'FTQ terminal redirect remains pending'
        assert set(self.offered) == pending | set(self.redirect_done), 'FTQ lost redirect offer ancestry'
        ifu = {uid for uid, event in self.offered.items() if event.source == 'ifu'}
        resolve_pending = {self.pending_resolve.uid} if self.pending_resolve is not None else set()
        assert not (resolve_pending & set(self.resolve_done)), 'FTQ IFU resolve terminal remains pending'
        assert ifu == resolve_pending | set(self.resolve_done), 'FTQ lost IFU resolve forwarding obligation'
        assert set(self.resolve_children) == {uid for uid, (status, _) in self.resolve_done.items()
                                             if status == 'forwarded-to-resolve'}, 'FTQ lost forwarded IFU resolve child'
        assert set(self.response_meta) == {uid for uid, (status, _) in self.redirect_done.items()
                                           if status in ('applied', 'reset-suppressed-application')}, 'FTQ lost redirect metadata association'
        return pending | resolve_pending

    def receipt(self):
        pending = self.audit()
        return dict(offered=tuple(self.offered.values()), redirects=tuple(self.redirect_done.items()),
                    resolves=tuple(self.resolve_done.items()), response_meta=tuple(self.response_meta.items()),
                    resolve_children=tuple(self.resolve_children.items()), ahead=tuple(self.ahead_inputs.items()),
                    pending=tuple(sorted(pending)))
