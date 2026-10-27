"""Return-stack programs, persistent checkpoints and committed call groups.

The model owns semantic call frames, not copies of DUT queue entries/registers.
Push/pop/return-and-call are stack operations; repeated addresses form bounded
call groups. A checkpoint restores the owned program prefix. Retirement names
an already accepted operation, never an address sampled from hardware memory.

DefaultConfig: sixteen retained committed groups, thirty-two speculative call
versions, eight calls per repeated-address group. Addresses here are bytes.
The public adapter handles halfword ports and the one-cycle retirement/repair
visibility boundary. Queue pointer details outside the checked projection
remain covered by the existing dedicated retirement/recovery checkers.
"""
from dataclasses import dataclass, replace
from bpuverify.common.model.configuration import RAS_GROUPS, RAS_SPEC_ENTRIES, RAS_POINTER_MODULUS, ALIGN_BYTES, POSITIONS
from copy import copy


@dataclass(frozen=True, slots=True)
class Frame:
    address: int = 0
    group: int = 0
    repeat: int = 0
    version: int = -1


@dataclass(frozen=True, slots=True)
class Program:
    frames: tuple[Frame, ...] = (Frame(),)
    calls: int = 0

    @property
    def head(self):
        return self.frames[-1]

    def commit_key(self):
        return self.head.group % RAS_GROUPS, self.calls % RAS_POINTER_MODULUS

    def redirect_key(self):
        return *self.commit_key(), self.head.repeat


@dataclass(frozen=True, slots=True)
class AcceptedOperation:
    before: Program
    action: int
    address: int | None
    sequence: int = 0  # Semantic lifetime, never a DUT queue pointer.


@dataclass(frozen=True, slots=True)
class Original:
    """An exact prediction lifetime, not a reconstructible pointer tuple."""
    epoch: object
    serial: int
    program: Program
    frontier: int


@dataclass(frozen=True, slots=True)
class Recovery:
    group: int
    calls: int
    repeat: int
    action: int = 0
    address: int | None = None
    origin: Original | None = None


@dataclass(frozen=True, slots=True)
class Retirement:
    group: int
    calls: int
    action: int
    origin: Original | None = None


@dataclass(frozen=True, slots=True)
class Events:
    action: int | None = None
    address: int | None = None
    recovery: Recovery | None = None
    retirement: Retirement | None = None
    enabled: bool = True
    reset: bool = False
    origin: Original | None = None


def instruction_return(pc, position):
    """Block-relative end-of-instruction address; do not use the encoder."""
    if type(pc) is not int or not 0 <= pc < 1 << 51 or type(position) is not int or not 0 <= position < POSITIONS:
        raise ValueError('RAS PC or instruction position is out of range')
    return ((pc // ALIGN_BYTES) * ALIGN_BYTES + 2 * (position + 1)) % (1 << 51)


class RasReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.program = Program()
        self.committed = [Frame(group=group) for group in range(RAS_GROUPS)]
        self.committed_head = 0
        self.retired_calls = 0
        self.guarded = False
        self.pending_recovery = self.pending_retirement = None
        self.operations = []
        self.checkpoints = {}
        self.accepted_sequence = 0
        self.checkpoint_sequences = {}
        self.projection = dict(top=0, group=0, repeat=0, calls=0)
        self.cycles = self.retirements = 0
        self.last_applied = None
        self._original_epoch = object()
        self._original_serial = 0
        self._originals = {}
        self._original_operations = {}
        self._retired_originals = set()
        self._cancelled_originals = set()
        self.pending_retirement_origin = None
        self._remember(self.program)

    def capture_original(self):
        """Capture our own pre-operation program for one prediction owner."""
        result = Original(self._original_epoch, self._original_serial,
                          self.program, self.accepted_sequence)
        self._original_serial += 1
        self._originals[result.serial] = result
        return result

    def require_original(self, original):
        if (type(original) is not Original or original.epoch is not self._original_epoch
                or self._originals.get(original.serial) is not original):
            raise ValueError('RAS original is copied, foreign, released or from another reset epoch')
        return original

    def release_original(self, original):
        self.require_original(original)
        if ((self.pending_recovery is not None and self.pending_recovery.origin is original)
                or self.pending_retirement_origin is original):
            raise ValueError('pending RAS recovery or retirement still owns this original')
        del self._originals[original.serial]
        self._original_operations.pop(original.serial, None)
        self._retired_originals.discard(original.serial)
        self._cancelled_originals.discard(original.serial)

    def original_is_live(self, original):
        """Whether this observed original still owns an unretired operation."""
        self.require_original(original)
        operation = self._original_operations.get(original.serial)
        return (operation is not None and original.serial not in self._cancelled_originals
            and original.serial not in self._retired_originals
            and (not operation.action or any(value is operation for value in self.operations)))

    def _remember(self, program):
        key = program.redirect_key()
        self.checkpoints[key] = program
        self.checkpoint_sequences[key] = self.accepted_sequence
        # Only bounded recent source contexts can legally survive the queue.
        while len(self.checkpoints) > 128:
            expired = next(iter(self.checkpoints))
            del self.checkpoints[expired]
            del self.checkpoint_sequences[expired]

    def _accept(self, before, action, address, *, origin=None):
        self.accepted_sequence += 1
        operation = AcceptedOperation(before,action,address,self.accepted_sequence)
        self.operations.append(operation)
        if origin is not None:
            self._original_operations[origin.serial] = operation

    def _live(self, frame, program):
        return frame.version >= 0 and (frame.version - self.retired_calls) % RAS_POINTER_MODULUS < (program.calls - self.retired_calls) % RAS_POINTER_MODULUS

    def _top(self, program):
        head = program.head
        return head if self._live(head, program) else self.committed[head.group % RAS_GROUPS]

    def _pop(self, program):
        before = program.head
        if len(program.frames) > 1:
            frames = program.frames[:-1]
            head = frames[-1]
        else:
            # An empty/bottom return exposes retained bounded storage; it
            # does not invent an infinite stack of architecturally valid calls.
            group = before.group - 1
            resident = self.committed[group % RAS_GROUPS]
            head = Frame(resident.address, group, resident.repeat)
            frames = (head,)
        if before.repeat:
            head = replace(head, group=before.group, repeat=before.repeat - 1)
        elif not self._live(head, program):
            head = replace(head, repeat=self.committed[head.group % RAS_GROUPS].repeat)
        return replace(program, frames=(*frames[:-1], head))

    def _apply(self, program, action, address):
        if type(action) is not int or action not in range(4):
            raise ValueError('RAS action must be neutral, return, call or return-and-call')
        if action & 1:
            program = self._pop(program)
        if action & 2:
            if type(address) is not int or not 0 <= address < 1 << 51 or address % 2:
                raise ValueError('RAS call needs an aligned byte return address')
            top = self._top(program)
            repeat = program.head.repeat + 1 if top.address == address and program.head.repeat < 7 else 0
            group = program.head.group if repeat else program.head.group + 1
            frame = Frame(address, group, repeat, program.calls)
            program = Program((*program.frames, frame), program.calls + 1)
        elif address is not None:
            raise ValueError('a non-call RAS action cannot supply a return address')
        return program

    def _retire(self, accepted):
        before, action, address = accepted.before, accepted.action, accepted.address
        group = before.head.group % RAS_GROUPS
        if action & 1:
            # Repair the committed program cursor to the source before
            # applying its operation, rather than copying an unrelated head's
            # duplicate count into the repaired location.
            old = self.committed[group]
            if old.repeat:
                self.committed[group] = replace(old, repeat=old.repeat - 1)
            else:
                group = (group - 1) % RAS_GROUPS
        if action & 2:
            old = self.committed[group]
            if old.address == address and old.repeat < 7:
                self.committed[group] = replace(old, repeat=old.repeat + 1)
            else:
                group = (group + 1) % RAS_GROUPS
                self.committed[group] = Frame(address, group)
            self.retired_calls = before.calls
        elif (before.calls - self.retired_calls) % RAS_POINTER_MODULUS > 2:
            self.retired_calls = before.calls - 1
        if action:
            self.committed_head = group
        self.retirements += 1

    def _associate_retirement(self, retirement):
        if type(retirement.action) is not int or retirement.action not in range(4):
            raise ValueError('RAS retirement action must be neutral, return, call or return-and-call')
        if retirement.origin is not None:
            source = self.require_original(retirement.origin)
            if (retirement.group,retirement.calls) != source.program.commit_key():
                raise ValueError('retirement fields do not belong to the exact RAS original')
            if source.serial in self._retired_originals:
                raise ValueError('one RAS original cannot retire twice')
            if source.serial in self._cancelled_originals:
                raise ValueError('the original RAS operation was cancelled')
            operation = self._original_operations.get(source.serial)
            if operation is None:
                raise ValueError('retirement needs an actually observed original operation')
            if retirement.action & 2 and operation.address is None:
                raise ValueError('a foreign call address cannot be borrowed by an equal-encoding original')
            if operation.action:
                matches = [i for i,value in enumerate(self.operations) if value is operation]
                if not matches:
                    raise ValueError('the original RAS operation was cancelled or already retired')
                del self.operations[:matches[0]+1]
            self._retired_originals.add(source.serial)
            return AcceptedOperation(source.program, retirement.action,
                operation.address if retirement.action & 2 else None, operation.sequence)
        if retirement.action == 0:
            # A neutral retirement can reclaim queue credit but not stack data.
            return AcceptedOperation(Program((Frame(group=retirement.group),), retirement.calls), 0, None)
        matches = [index for index, operation in enumerate(self.operations)
                   if (not retirement.action & 2 or operation.address is not None) and operation.before.commit_key()
                   == (retirement.group, retirement.calls)]
        if not matches:
            raise AssertionError(f'RAS retirement has no owned speculative source: {retirement}')
        index = matches[0]
        operation = self.operations[index]
        # Notifications before this one may have been deliberately omitted.
        del self.operations[:index + 1]
        # Resolved attributes are an upstream UT input and need not equal the
        # earlier speculative classification. Calls must still name an owned
        # real source return address; no address is invented from metadata.
        return AcceptedOperation(operation.before, retirement.action,
                                 operation.address if retirement.action & 2 else None,operation.sequence)

    def advance(self, events=Events()):
        """A rejected semantic event cannot partially change the reference.

        Programs/frames/events are immutable. Copy only mutable bookkeeping,
        evaluate the complete boundary, then publish the successful state.
        No DUT snapshot or physical register image enters this transaction.
        """
        if type(events) is not Events:
            raise TypeError('RAS reference requires semantic Events')
        if events.reset:
            self.reset()
            return
        candidate = self.preview(events)
        self.__dict__.update(candidate.__dict__)

    def preview(self, events=Events()):
        """Forecast a semantic boundary without changing any original owner."""
        if type(events) is not Events or events.reset:
            raise ValueError('RAS preview requires a non-reset semantic boundary')
        candidate = copy(self)
        for name in ('committed','operations','checkpoints','checkpoint_sequences',
                     '_originals','_original_operations','_retired_originals','_cancelled_originals'):
            setattr(candidate, name, copy(getattr(self, name)))
        candidate._advance(events)
        return candidate

    def _advance(self, events):
        if events.origin is not None:
            source = self.require_original(events.origin)
            if source.program is not self.program or source.serial in self._original_operations:
                raise ValueError('a speculative RAS event requires its fresh, exact pre-operation original')
            if events.action is None:
                raise ValueError('an original must accompany an actual speculative event, including neutral')
        if events.recovery is not None and events.recovery.origin is not None:
            source = self.require_original(events.recovery.origin)
            if source.serial in self._cancelled_originals:
                raise ValueError('a cancelled RAS original cannot recover another lifetime')
            if source.serial not in self._original_operations:
                raise ValueError('recovery requires an actually observed original')
            if (events.recovery.group,events.recovery.calls,events.recovery.repeat) != source.program.redirect_key():
                raise ValueError('recovery fields do not belong to the exact RAS original')
        self.cycles += 1
        self.last_applied = None
        before = self.program
        occupancy = (before.calls - self.retired_calls) % RAS_POINTER_MODULUS
        recovering = self.pending_recovery
        retiring = self.pending_retirement
        self.pending_recovery = events.recovery
        self.pending_retirement = None
        self.pending_retirement_origin = None
        following = before
        if events.enabled:
            if recovering is not None:
                key = recovering.group, recovering.calls, recovering.repeat
                source = None if recovering.origin is None else self.require_original(recovering.origin)
                checkpoint = self.checkpoints.get(key) if source is None else source.program
                if checkpoint is None:
                    raise AssertionError(f'RAS recovery has no independently owned checkpoint: {key}')
                older = 0 < (before.calls - checkpoint.calls) % RAS_POINTER_MODULUS <= RAS_SPEC_ENTRIES
                if not self.guarded or older:
                    following = self._apply(checkpoint, recovering.action, recovering.address)
                    # Restoring a program also cancels its younger operation
                    # owners. Numeric commit keys may alias across repeated
                    # returns; they cannot keep wrong-path operations alive.
                    frontier = self.checkpoint_sequences[key] if source is None else source.frontier
                    self.operations = [operation for operation in self.operations if operation.sequence<=frontier]
                    if source is not None:
                        self._cancelled_originals.update(serial for serial in self._original_operations
                            if serial > source.serial)
                    self.last_applied = ('recovery', recovering.action, recovering.address)
                    if recovering.action:
                        self._accept(checkpoint,recovering.action,recovering.address,origin=source)
                    elif source is not None:
                        self._original_operations[source.serial] = AcceptedOperation(checkpoint,0,None,frontier)
            elif events.action is not None and not self.guarded:
                following = self._apply(before, events.action, events.address)
                self.last_applied = ('speculation', events.action, events.address)
                if events.action:
                    self._accept(before,events.action,events.address,origin=events.origin)
                elif events.origin is not None:
                    self._original_operations[events.origin.serial] = AcceptedOperation(before,0,None,self.accepted_sequence)
        if events.origin is not None and events.origin.serial not in self._original_operations:
            # A real prediction may be observed while its stack effect is
            # disabled/guarded; this does not invent an accepted call address.
            self._original_operations[events.origin.serial] = AcceptedOperation(before,0,None,self.accepted_sequence)
        if events.retirement is not None and events.enabled:
            self.pending_retirement = self._associate_retirement(events.retirement)
            self.pending_retirement_origin = events.retirement.origin
        # Registered top sees this cycle's stack operation but not a committed
        # cell retiring at the same boundary. The next cycle sees that commit.
        top = self._top(following)
        self.projection = dict(top=top.address // 2, group=following.head.group % RAS_GROUPS,
                               repeat=following.head.repeat, calls=following.calls % RAS_POINTER_MODULUS)
        self.program = following
        self._remember(following)
        if retiring is not None:
            self._retire(retiring)
        self.guarded = occupancy > RAS_SPEC_ENTRIES - 2
        # Checkpoints are independently generated program prefixes. This is
        # not a general FTQ trace validator or a gold model for raw pointer bits.
        if len(self.operations) > 128:
            raise AssertionError('RAS unresolved operation capacity exceeded')

    def state(self):
        return dict(cycle=self.cycles, program=self.program, committed=tuple(self.committed),
                    committed_head=self.committed_head, retired_calls=self.retired_calls,
                    guarded=self.guarded, retirements=self.retirements,
                    accepted_sequence=self.accepted_sequence,unresolved_operations=len(self.operations),
                    pending_retirement=self.pending_retirement, pending_recovery=self.pending_recovery)
