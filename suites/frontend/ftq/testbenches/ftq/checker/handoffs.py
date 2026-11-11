"""FTQ-local handoff and ROB-target ledgers; identities come from inputs.

A fire completes only the FTQ-to-consumer handoff, not an ICache response or
full-machine retirement. Backpressured, unaccepted offers may stay visible at
finish, but must be listed separately from accepted/completed work.
"""
from dataclasses import dataclass


def after(left, right):
    return 0 < (left - right) % 128 <= 64


@dataclass(frozen=True, slots=True)
class RequestLaneOwner:
    uid: tuple
    allocation: tuple


@dataclass(frozen=True, slots=True)
class RequestObservation:
    valid: bool
    second: bool
    position: int
    lanes: tuple[RequestLaneOwner, ...]


def observation(info_entry):
    """Accept the checker's typed view, or the legacy owner-entry tuple."""

    if isinstance(info_entry, RequestObservation):
        return info_entry
    valid, second, position, installed, _ = info_entry
    lanes = ()
    if valid:
        lanes = tuple(RequestLaneOwner(item.uid, item.allocation)
                      for item in installed[:2 if second else 1])
    return RequestObservation(valid, second, position, lanes)


@dataclass(frozen=True, slots=True)
class RequestAttempt:
    uid: tuple
    channel: str
    position: int
    primary: tuple
    allocation: tuple
    retry_of: tuple | None


class RequestHandoffs:
    def __init__(self):
        self.offered, self.presentations = {}, {}
        self.accepted, self.terminals = {}, {}
        self.current, self.previous = {}, {}
        self.handoffs = []
        self.serial = 0

    def sync(self, info, epoch, tick, *, reason='replaced-offer'):
        for channel, entry in info.items():
            view = observation(entry)
            old = self.current.get(channel)
            primary = view.lanes[0] if view.valid else None
            if view.valid:
                assert primary is not None, 'FTQ request has no input owner'
            if old is not None and (not view.valid
                                    or (old.position, old.primary) != (view.position, primary.uid)):
                assert old.uid not in self.terminals
                self.terminals[old.uid] = reason, tick
                del self.current[channel]
                old = None
            if view.valid and old is None:
                self.serial += 1
                key = channel, primary.allocation
                uid = epoch, channel, self.serial
                old = RequestAttempt(uid, channel, view.position, primary.uid,
                                     primary.allocation, self.previous.get(key))
                self.offered[uid] = old
                self.presentations[uid] = []
                self.previous[key] = uid
                self.current[channel] = old
            if view.valid:
                lanes = view.lanes[:2 if view.second else 1]
                assert all(item is not None for item in lanes), 'FTQ secondary request has no input owner'
                self.presentations[old.uid].append((tick, tuple(item.uid for item in lanes), view.second))

    def consume(self, frame, info, tick):
        for channel, enabled in (('prefetch', frame.consumers.prefetch), ('fetch', frame.consumers.mainpipe)):
            view = observation(info[channel])
            if frame.reset or not view.valid or not enabled:
                continue
            count = (2 if view.second else 1) if channel == 'prefetch' else (2 if frame.consumers.real_two_fetch else 1)
            assert count == 1 or view.second, 'ICache reports realTwoFetch on an ineligible second request'
            attempt = self.current.pop(channel)
            rows = tuple(item.uid for item in view.lanes[:count])
            assert attempt.uid not in self.accepted and attempt.uid not in self.terminals
            self.accepted[attempt.uid] = tick, rows
            self.terminals[attempt.uid] = 'completed', tick
            self.handoffs.extend((channel, uid, tick) for uid in rows)

    def audit(self):
        current = {attempt.uid for attempt in self.current.values()}
        completed = {uid for uid, (status, _) in self.terminals.items() if status == 'completed'}
        assert not (current & set(self.terminals)), 'FTQ terminal request remains pending'
        assert set(self.offered) == current | set(self.terminals), 'FTQ lost request offer ancestry'
        assert set(self.accepted) == completed, 'FTQ lost request acceptance/terminal association'
        assert set(self.presentations) == set(self.offered), 'FTQ lost request presentation history'
        expected = [(self.offered[uid].channel, row, tick)
                    for uid, (tick, rows) in self.accepted.items() for row in rows]
        assert expected == self.handoffs, 'FTQ lost or duplicated an accepted request handoff'
        for uid, attempt in self.offered.items():
            if attempt.retry_of is not None:
                previous = self.offered[attempt.retry_of]
                assert (previous.channel, previous.allocation) == (attempt.channel, attempt.allocation), 'FTQ retry owner changed'
                assert attempt.retry_of in self.terminals, 'FTQ retry overlaps a still pending prior attempt'
            assert self.presentations[uid], 'FTQ empty request offer evidence'
        return current

    def receipt(self):
        pending = self.audit()
        return dict(offered=tuple(self.offered.values()), accepted=tuple(self.accepted.items()),
                    terminals=tuple(self.terminals.items()), pending_offers=tuple(sorted(pending)),
                    handoffs=tuple(self.handoffs))


class RobTargets:
    def __init__(self):
        self.offered, self.pending, self.terminals = {}, {}, {}
        self.retired = []
        self.source = None

    def advance(self, frame, epoch, slot, position, target, installed, tick):
        if frame.reset:
            for uid in self.pending:
                self.terminals[uid] = 'reset-cancelled', tick - 1
            self.pending.clear()
            self.source = None
            return
        if frame.commit is not None:
            uid = epoch, slot, 'rob-commit'
            value = 64 * frame.commit[0] + frame.commit[1]
            assert uid not in self.offered
            self.offered[uid] = value, tick
            self.source = uid
            if value == position or after(value, position):
                self.pending[uid] = value
            else:
                self.terminals[uid] = 'duplicate-old-target', tick
        if target == position or after(target, position):
            item = installed[position % 64]
            ancestor = (item.allocation if item is not None and item.identity == position
                        and item.uid[0] == epoch else None)
            self.retired.append((epoch, position, tick, self.source, ancestor))
            for uid, value in tuple(self.pending.items()):
                if value == position:
                    self.terminals[uid] = 'target-reached', tick
                    del self.pending[uid]

    def audit(self):
        assert not (set(self.pending) & set(self.terminals)), 'FTQ ROB terminal remains pending'
        assert set(self.offered) == set(self.pending) | set(self.terminals), 'FTQ lost ROB target ancestry'
        previous, seen = None, set()
        for epoch, position, tick, source, _ in self.retired:
            assert (epoch, tick) not in seen, 'FTQ repeated a ROB retirement edge'
            seen.add((epoch, tick))
            if previous is not None and previous[0] == epoch:
                assert position == (previous[1] + 1) % 128, 'FTQ duplicated or skipped a ROB retirement owner'
            previous = epoch, position
            assert source in self.offered, 'FTQ retired without an input ROB target'
        return set(self.pending)

    def receipt(self):
        pending = self.audit()
        return dict(offered=tuple(self.offered.items()), terminals=tuple(self.terminals.items()),
                    pending=tuple(sorted(pending)), retired=tuple(self.retired))
