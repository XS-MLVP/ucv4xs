"""Independent two-slot StoreDataCtrl reference model."""
from dataclasses import dataclass

from .types import (
    ALL_BYTES,
    NUM_ENTRIES,
    SPLIT,
    Beat,
    Entry,
    Observation,
    StoreDataRequest,
    Update,
    VrfReadRequest,
)


def need_flush(flag: int, value: int, redirect) -> bool:
    """Match RobPtr.needFlush, including circular flag ordering."""
    if not redirect.valid:
        return False
    equal = flag == redirect.rob_flag and value == redirect.rob_value
    after = bool((flag ^ redirect.rob_flag) ^ (value > redirect.rob_value))
    return bool((redirect.level and equal) or after)


def entry_alive(entry: Entry, redirect) -> bool:
    return entry.valid and not need_flush(entry.rob_flag, entry.rob_value, redirect)


def pending_mask(entry: Entry) -> int:
    return entry.elem_active & entry.req_ack & ~entry.data_sent & ALL_BYTES


def _oldest(candidates, matrix):
    for i, candidate in enumerate(candidates):
        if candidate and all(
            (not candidates[j]) or matrix[i][j]
            for j in range(NUM_ENTRIES)
            if j != i
        ):
            return i
    return next((i for i, candidate in enumerate(candidates) if candidate), None)


def _low_bit(mask: int) -> int:
    return (mask & -mask).bit_length() - 1


def _sq_add(first: int, second: int, value: int, offset: int):
    """Add to the 128-entry (first, second, value) SQ pointer."""
    operation = (second << 6) | value
    encoded = ((first << 7) | operation) + offset
    encoded &= 0xff
    return (encoded >> 7) & 1, (encoded >> 6) & 1, encoded & 0x3f


def _store_flow_data(data: int, elem_idx: int, deew: int) -> int:
    """Select one VRF element and repeat it across the 128-bit store bus."""
    bytes_per_element = 1 << deew
    element_bits = bytes_per_element * 8
    count = 16 // bytes_per_element
    local_index = elem_idx & (count - 1)
    element = (data >> (local_index * element_bits)) & ((1 << element_bits) - 1)
    result = 0
    for index in range(count):
        result |= element << (index * element_bits)
    return result


@dataclass(frozen=True, slots=True)
class Slot:
    valid: bool = False
    data: int = 0
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0


@dataclass(frozen=True, slots=True)
class State:
    slots: tuple[Slot, Slot] = (Slot(), Slot())
    read_pending: bool = False
    read_pending_slot: int = 0
    read_pending_entry_idx: int = 0
    read_pending_rob_flag: int = 0
    read_pending_rob_value: int = 0

    def slot_entry(self, slot: Slot, beat: Beat) -> Entry:
        return beat.entries[slot.entry_idx]

    def slot_alive(self, slot: Slot, beat: Beat) -> bool:
        entry = self.slot_entry(slot, beat)
        return bool(
            slot.valid
            and entry.is_store
            and entry.rob_flag == slot.rob_flag
            and entry.rob_value == slot.rob_value
            and entry_alive(entry, beat.redirect)
        )

    def slot_done(self, slot: Slot, beat: Beat) -> bool:
        entry = self.slot_entry(slot, beat)
        return (entry.data_sent & entry.elem_active & ALL_BYTES) == (
            entry.elem_active & ALL_BYTES
        )

    def slot_pending(self, slot: Slot, beat: Beat) -> int:
        return pending_mask(self.slot_entry(slot, beat))

    def resident(self, beat: Beat) -> tuple[bool, ...]:
        result = [False] * NUM_ENTRIES
        for slot in self.slots:
            if self.slot_alive(slot, beat):
                result[slot.entry_idx] = True
        return tuple(result)

    def candidate_bits(self, beat: Beat) -> tuple[bool, ...]:
        resident = self.resident(beat)
        result = []
        for index, entry in enumerate(beat.entries):
            candidate = (
                entry_alive(entry, beat.redirect)
                and entry.is_store
                and entry.state == SPLIT
                and entry.ordered_can_proceed
                and beat.psrc2_ready[index]
                and not resident[index]
                and bool(pending_mask(entry))
                and not (
                    self.read_pending
                    and self.read_pending_entry_idx == index
                )
            )
            result.append(candidate)
        return tuple(result)

    def candidate_index(self, beat: Beat):
        return _oldest(self.candidate_bits(beat), beat.older_matrix)

    def reusable(self, beat: Beat) -> tuple[bool, bool]:
        return tuple(
            (not self.slot_alive(slot, beat))
            or self.slot_done(slot, beat)
            or not self.slot_pending(slot, beat)
            for slot in self.slots
        )

    def free_slot(self, beat: Beat):
        return next((index for index, free in enumerate(self.reusable(beat)) if free), None)

    def _store_request(self, slot: Slot, beat: Beat) -> StoreDataRequest | None:
        entry = self.slot_entry(slot, beat)
        pending = self.slot_pending(slot, beat)
        if not (
            self.slot_alive(slot, beat)
            and entry.ordered_can_proceed
            and pending
        ):
            return None
        byte_offset = _low_bit(pending)
        idx_offset = ((byte_offset - entry.start_byte) & 0xf) >> entry.deew
        first, second, value = _sq_add(
            entry.sq_first_flag, entry.sq_second_flag, entry.sq_value, idx_offset
        )
        return StoreDataRequest(
            first,
            second,
            value,
            _store_flow_data(slot.data, byte_offset >> entry.deew, entry.deew),
        )

    def observe(self, beat: Beat) -> Observation:
        candidate_index = self.candidate_index(beat)
        free_slot = self.free_slot(beat)
        read_valid = candidate_index is not None and free_slot is not None and not self.read_pending
        if read_valid:
            entry = beat.entries[candidate_index]
            read_req = VrfReadRequest(
                True,
                candidate_index,
                entry.rob_flag,
                entry.rob_value,
                entry.psrc2,
            )
        else:
            read_req = VrfReadRequest()

        store_data = tuple(self._store_request(slot, beat) for slot in self.slots)
        updates = tuple(
            Update(
                request is not None and beat.store_data_ready[index],
                self.slots[index].entry_idx,
                (1 << _low_bit(self.slot_pending(self.slots[index], beat)))
                if request is not None
                else 0,
            )
            for index, request in enumerate(store_data)
        )
        return Observation(read_req, store_data, updates)

    def following(self, beat: Beat):
        observation = self.observe(beat)
        read_fire = observation.vrf_read_req.valid and beat.vrf_read_req_ready
        response = beat.vrf_read_resp
        response_match = (
            self.read_pending
            and response.valid
            and response.entry_idx == self.read_pending_entry_idx
            and response.rob_flag == self.read_pending_rob_flag
            and response.rob_value == self.read_pending_rob_value
        )
        if self.read_pending:
            pending_entry = beat.entries[self.read_pending_entry_idx]
            pending_alive = (
                pending_entry.valid
                and pending_entry.rob_flag == self.read_pending_rob_flag
                and pending_entry.rob_value == self.read_pending_rob_value
                and not need_flush(
                    pending_entry.rob_flag,
                    pending_entry.rob_value,
                    beat.redirect,
                )
            )
        else:
            pending_alive = True
        pending_cancel = self.read_pending and not pending_alive

        slots = list(self.slots)
        if read_fire:
            free_slot = self.free_slot(beat)
            assert free_slot is not None
            slots[free_slot] = Slot(
                valid=False,
                data=slots[free_slot].data,
                entry_idx=slots[free_slot].entry_idx,
                rob_flag=slots[free_slot].rob_flag,
                rob_value=slots[free_slot].rob_value,
            )
        if response_match:
            slots[self.read_pending_slot] = Slot(
                valid=True,
                data=response.data,
                entry_idx=self.read_pending_entry_idx,
                rob_flag=self.read_pending_rob_flag,
                rob_value=self.read_pending_rob_value,
            )

        # The RTL cleanup observes the pre-edge slotValid and current entry
        # view.  A slot invalidated by a new read is therefore not cleared by
        # the same cleanup loop; a matched response establishes it normally.
        for index, old_slot in enumerate(self.slots):
            if old_slot.valid and (
                not self.slot_alive(old_slot, beat)
                or self.slot_done(old_slot, beat)
            ):
                slots[index] = Slot(
                    valid=False,
                    data=slots[index].data,
                    entry_idx=slots[index].entry_idx,
                    rob_flag=slots[index].rob_flag,
                    rob_value=slots[index].rob_value,
                )

        read_pending = self.read_pending
        pending_slot = self.read_pending_slot
        pending_entry_idx = self.read_pending_entry_idx
        pending_rob_flag = self.read_pending_rob_flag
        pending_rob_value = self.read_pending_rob_value
        if read_fire:
            read_pending = True
            pending_slot = self.free_slot(beat)
            pending_entry_idx = observation.vrf_read_req.entry_idx
            pending_rob_flag = observation.vrf_read_req.rob_flag
            pending_rob_value = observation.vrf_read_req.rob_value
        if response_match:
            read_pending = False
        if pending_cancel:
            read_pending = False

        return State(
            tuple(slots),
            read_pending,
            pending_slot,
            pending_entry_idx,
            pending_rob_flag,
            pending_rob_value,
        )
