"""Independent MergeCtrl response, merge-read and completion model."""
from dataclasses import dataclass

from .types import (
    ALL_BYTES,
    MERGE,
    NUM_ENTRIES,
    SPLIT,
    WB,
    Beat,
    Entry,
    Observation,
    Response,
    ResponseUpdate,
    RobWriteback,
    StateUpdate,
    VrfReadRequest,
    VrfWriteRequest,
)


def need_flush(flag: int, value: int, redirect) -> bool:
    if not redirect.valid:
        return False
    equal = flag == redirect.rob_flag and value == redirect.rob_value
    after = bool((flag ^ redirect.rob_flag) ^ (value > redirect.rob_value))
    return bool((redirect.level and equal) or after)


def entry_alive(entry: Entry, redirect) -> bool:
    return entry.valid and not need_flush(entry.rob_flag, entry.rob_value, redirect)


def _oldest(candidates, matrix):
    for i, candidate in enumerate(candidates):
        if candidate and all(
            (not candidates[j]) or matrix[i][j]
            for j in range(NUM_ENTRIES)
            if j != i
        ):
            return i
    return next((i for i, candidate in enumerate(candidates) if candidate), None)


def _priority(candidates):
    return next((i for i, candidate in enumerate(candidates) if candidate), None)


def _expand_mask(mask: int) -> int:
    result = 0
    for byte in range(16):
        if mask & (1 << byte):
            result |= 0xff << (8 * byte)
    return result


@dataclass(frozen=True, slots=True)
class State:
    merge_read_valid: bool = False
    merge_pending_entry_idx: int = 0
    merge_pending_rob_flag: int = 0
    merge_pending_rob_value: int = 0
    merge_pending_pdest: int = 0
    merge_pending_write_mask: int = 0
    merge_pending_agnostic_mask: int = 0
    merge_resp_valid: bool = False
    merge_resp_data: int = 0

    def merge_needs_old(self, entry: Entry) -> bool:
        return bool(entry.merge_write & ~entry.elem_agnostic & ALL_BYTES)

    def merge_candidates(self, beat: Beat) -> tuple[bool, ...]:
        return tuple(
            entry_alive(entry, beat.redirect)
            and entry.state == MERGE
            and (
                not self.merge_needs_old(entry)
                or beat.psrc2_ready[index]
            )
            for index, entry in enumerate(beat.entries)
        )

    def wb_candidates(self, beat: Beat) -> tuple[bool, ...]:
        return tuple(
            entry_alive(entry, beat.redirect) and entry.state == WB
            for entry in beat.entries
        )

    def split_done_candidates(self, beat: Beat) -> tuple[bool, ...]:
        result = []
        for entry in beat.entries:
            data_done = (
                not entry.is_store
                or (entry.data_sent & entry.elem_active & ALL_BYTES)
                == (entry.elem_active & ALL_BYTES)
            )
            result.append(
                entry_alive(entry, beat.redirect)
                and entry.state == SPLIT
                and entry.ordered_can_proceed
                and (entry.req_ack & ALL_BYTES) == ALL_BYTES
                and data_done
            )
        return tuple(result)

    def merge_index(self, beat: Beat):
        return _oldest(self.merge_candidates(beat), beat.older_matrix)

    def split_done_index(self, beat: Beat):
        return _priority(self.split_done_candidates(beat))

    def wb_index(self, beat: Beat):
        return _priority(self.wb_candidates(beat))

    def pending_entry(self, beat: Beat) -> Entry:
        return beat.entries[self.merge_pending_entry_idx]

    def pending_alive(self, beat: Beat) -> bool:
        entry = self.pending_entry(beat)
        return bool(
            entry.state == MERGE
            and entry.rob_flag == self.merge_pending_rob_flag
            and entry.rob_value == self.merge_pending_rob_value
            and entry_alive(entry, beat.redirect)
        )

    def _response_update(self, response: Response, beat: Beat, *, public_exception=True):
        hit = (
            (1 << response.entry_idx)
            if response.valid and entry_alive(beat.entries[response.entry_idx], beat.redirect)
            else 0
        )
        nack_clear = response.is_nack and not response.exception
        return ResponseUpdate(
            set_req_ack=response.issue_mask if not nack_clear else 0,
            clear_req_sent=response.issue_mask if nack_clear else 0,
            exception=response.exception if public_exception else False,
            exception_number=response.exception_number if public_exception else 0,
            fault_elem=response.fault_elem if public_exception else 0,
            entry_hit_oh=hit,
        )

    def _rob_writeback(self, beat: Beat) -> RobWriteback:
        index = self.wb_index(beat)
        if index is None:
            return RobWriteback()
        entry = beat.entries[index]
        return RobWriteback(
            valid=True,
            entry_idx=index,
            rob_flag=entry.rob_flag,
            rob_value=entry.rob_value,
            exception=entry.exception,
            exception_number=entry.exception_number if entry.exception else 0,
            fault_vstart=entry.fault_elem if entry.exception else 0,
            uop_type=entry.uop_type,
            uop_idx=entry.uop_idx,
            deew=entry.deew,
            nf=entry.nf,
            lq_flag=entry.lq_flag,
            lq_value=entry.lq_value,
            sq_first_flag=entry.sq_first_flag,
            sq_second_flag=entry.sq_second_flag,
            sq_value=entry.sq_value,
            # TriggerAction is a validity-derived public encoding in this
            # generated top: every selected writeback entry produces 4'hf;
            # it is not an input leaf of MergeCtrl.
            trigger=0xf,
            vsew=entry.vsew,
            vlmul=entry.vlmul,
            perf_eliminated=entry.perf_eliminated,
            perf_rename=entry.perf_rename,
            perf_dispatch=entry.perf_dispatch,
            perf_enq_rs=entry.perf_enq_rs,
            perf_select=entry.perf_select,
            perf_issue=entry.perf_issue,
            perf_runahead=entry.perf_runahead,
            perf_tlb_first=entry.perf_tlb_first,
            perf_tlb_resp=entry.perf_tlb_resp,
            debug_seq_num=entry.debug_seq_num,
            debug_uop_idx=entry.debug_uop_idx,
        )

    def observe(self, beat: Beat) -> Observation:
        responses = beat.ldu_resp + beat.sta_resp + beat.empty_resp
        updates = tuple(
            self._response_update(response, beat, public_exception=index < 5)
            for index, response in enumerate(responses)
        )

        split_index = self.split_done_index(beat)
        if split_index is None:
            split_done = StateUpdate()
        else:
            entry = beat.entries[split_index]
            next_state = WB if entry.is_store or not entry.merge_write or entry.skip_merge else MERGE
            split_done = StateUpdate(True, 1 << split_index, next_state)

        merge_index = self.merge_index(beat)
        has_merge = merge_index is not None
        merge_needs_old = has_merge and self.merge_needs_old(beat.entries[merge_index])
        merge_can_start = has_merge and not self.merge_read_valid and not self.merge_resp_valid
        vrf_read = VrfReadRequest()
        if merge_can_start and merge_needs_old:
            entry = beat.entries[merge_index]
            vrf_read = VrfReadRequest(True, merge_index, entry.rob_flag, entry.rob_value, entry.psrc2)

        pending_alive = self.pending_alive(beat)
        vrf_write = VrfWriteRequest()
        if self.merge_resp_valid and pending_alive:
            vrf_write = VrfWriteRequest(
                True,
                self.merge_pending_entry_idx,
                self.merge_pending_pdest,
                self.merge_resp_data | _expand_mask(self.merge_pending_agnostic_mask),
                self.merge_pending_write_mask,
            )

        wb = self._rob_writeback(beat)
        rob_clear = StateUpdate(wb.valid, 1 << wb.entry_idx if wb.valid else 0, 0)
        # The generated public top optimizes the constant wb stateNext field
        # away for mergeDoneUpdate; only valid and entryIdxOH are observable.
        merge_done = StateUpdate(vrf_write.valid, 1 << vrf_write.entry_idx if vrf_write.valid else 0, 0)
        entry = beat.entries[wb.entry_idx] if wb.valid else Entry()
        wake = wb.valid and not wb.exception and not entry.skip_merge and entry.is_load
        return Observation(
            updates,
            split_done,
            merge_done,
            rob_clear,
            vrf_read,
            vrf_write,
            wb,
            wake,
            entry.pdest if wake else 0,
        )

    def following(self, beat: Beat):
        observation = self.observe(beat)
        merge_index = self.merge_index(beat)
        has_merge = merge_index is not None
        merge_needs_old = has_merge and self.merge_needs_old(beat.entries[merge_index])
        merge_can_start = has_merge and not self.merge_read_valid and not self.merge_resp_valid
        read_fire = observation.vrf_read.valid and beat.vrf_read_req_ready
        merge_without_read = merge_can_start and not merge_needs_old

        pending_alive = self.pending_alive(beat)
        resp_alive = (
            self.merge_read_valid
            and pending_alive
            and beat.vrf_read_resp_valid
            and beat.vrf_read_resp_entry_idx == self.merge_pending_entry_idx
            and beat.vrf_read_resp_rob_flag == self.merge_pending_rob_flag
            and beat.vrf_read_resp_rob_value == self.merge_pending_rob_value
        )
        write_valid = observation.vrf_write.valid

        read_valid = self.merge_read_valid
        if self.merge_read_valid:
            if not pending_alive or resp_alive:
                read_valid = False
        elif read_fire:
            read_valid = True

        pending_entry_idx = self.merge_pending_entry_idx
        pending_rob_flag = self.merge_pending_rob_flag
        pending_rob_value = self.merge_pending_rob_value
        pending_pdest = self.merge_pending_pdest
        pending_write_mask = self.merge_pending_write_mask
        pending_agnostic = self.merge_pending_agnostic_mask
        if read_fire or merge_without_read:
            entry = beat.entries[merge_index]
            pending_entry_idx = merge_index
            pending_rob_flag = entry.rob_flag
            pending_rob_value = entry.rob_value
            pending_pdest = entry.pdest
            pending_write_mask = entry.merge_write
            pending_agnostic = entry.elem_agnostic & entry.merge_write

        resp_valid = self.merge_resp_valid
        resp_data = self.merge_resp_data
        if self.merge_resp_valid:
            if not pending_alive or write_valid:
                resp_valid = False
        elif resp_alive or merge_without_read:
            resp_valid = True
            resp_data = 0 if merge_without_read else beat.vrf_read_resp_data

        return State(
            read_valid,
            pending_entry_idx,
            pending_rob_flag,
            pending_rob_value,
            pending_pdest,
            pending_write_mask,
            pending_agnostic,
            resp_valid,
            resp_data,
        )
