"""Independent event-driven public-boundary system contracts.

The classes in this module are deliberately external to the generated VAGQ
root.  They are not a replacement LSQ/VRF/ROB/VOQ implementation and do not
copy Chisel lookup tables.  Their job is to make downstream assumptions
explicit, inject adversarial timing, and check the observable public protocol.

Every component records events independently.  A passing virtual contract is
therefore reported separately from the RVV oracle and from whole-chip
acceptance, which is not observable through the current public schema.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
import heapq
from typing import Any

from .types import (
    AddrPacket,
    Beat,
    EmptyResponse,
    Response,
    VrfResponse,
)


PHASE_PRESENT = 0
PHASE_RESPONSE = 10
PHASE_WRITEBACK = 20
PHASE_RETIRE = 30
PUBLIC_ROB_MASK = (1 << 9) - 1


def _public_rob(value: int):
    """The generated public ROB leaf is nine bits wide."""
    return value & PUBLIC_ROB_MASK


def _json_value(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if is_dataclass(value):
        return _json_value(asdict(value))
    return value


@dataclass(order=True, frozen=True, slots=True)
class ScheduledEvent:
    """One deterministic event in the virtual system timeline."""

    cycle: int
    phase: int
    sequence: int
    kind: str = field(compare=False)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)

    def to_dict(self):
        return {
            "cycle": self.cycle,
            "phase": self.phase,
            "sequence": self.sequence,
            "kind": self.kind,
            "payload": _json_value(self.payload),
        }


class EventScheduler:
    """A small cycle/phase event queue with a stable insertion order."""

    def __init__(self):
        self._queue: list[ScheduledEvent] = []
        self._sequence = 0
        self.events: list[dict[str, Any]] = []

    def clear(self):
        self._queue.clear()
        self._sequence = 0
        self.events.clear()

    def schedule(self, cycle: int, phase: int, kind: str, **payload):
        if cycle < 0:
            raise ValueError(f"negative event cycle: {cycle}")
        event = ScheduledEvent(
            cycle=cycle,
            phase=phase,
            sequence=self._sequence,
            kind=kind,
            payload=payload,
        )
        self._sequence += 1
        heapq.heappush(self._queue, event)
        self.events.append({"action": "schedule", **event.to_dict()})
        return event

    def due(self, cycle: int):
        result = []
        while self._queue and self._queue[0].cycle <= cycle:
            event = heapq.heappop(self._queue)
            if event.cycle != cycle:
                raise AssertionError(
                    f"event scheduler skipped cycle {event.cycle} before {cycle}"
                )
            result.append(event)
            self.events.append({"action": "dispatch", **event.to_dict()})
        return tuple(result)

    @property
    def pending(self):
        return len(self._queue)


@dataclass(frozen=True, slots=True)
class VirtualRequest:
    kind: str
    lane: int
    cycle: int
    entry: int
    rob: int
    element: int
    byte: int
    mask: int
    address: int
    is_load: bool

    @property
    def identity(self):
        return (
            self.kind, self.entry, self.element, self.byte, self.address,
        )

    def to_dict(self):
        return {
            "kind": self.kind,
            "lane": self.lane,
            "cycle": self.cycle,
            "entry": self.entry,
            "rob": self.rob,
            "element": self.element,
            "byte": self.byte,
            "mask": self.mask,
            "address": self.address,
            "is_load": self.is_load,
        }


@dataclass(frozen=True, slots=True)
class VirtualSystemConfig:
    response_latency: int = 1
    vrf_latency: int = 1
    empty_latency: int = 1
    ldu_hold_cycles: int = 0
    sta_hold_cycles: int = 0
    empty_hold_cycles: int = 0
    ordered_sq: bool = False
    ordered_first_element: int = 0
    nack_once: bool = False
    fault_kind: str | None = None
    fault_element: int | None = None
    exception_number: int = 9
    deliver_late_response: bool = True
    response_extra_delay: tuple[tuple[int, int], ...] = ()
    vrf_data: int = 0
    max_event_cycles: int = 1024

    def __post_init__(self):
        if self.response_latency < 1 or self.vrf_latency < 1 or self.empty_latency < 1:
            raise ValueError("virtual response latencies must be positive")
        if self.fault_kind not in (None, "load", "store"):
            raise ValueError(f"unsupported virtual fault kind: {self.fault_kind}")
        if any(delay < 0 for _, delay in self.response_extra_delay):
            raise ValueError("response extra delays must be non-negative")

    def extra_delay(self, element: int):
        return dict(self.response_extra_delay).get(element, 0)


class VirtualLSQ:
    """Virtual request consumer and response scheduler.

    It models only a public LSQ/SQ contract: request fire, response identity,
    retry, exception, and optional late response delivery after a flush.
    """

    def __init__(self, scheduler: EventScheduler, config: VirtualSystemConfig):
        self.scheduler = scheduler
        self.config = config
        self.accepted: list[VirtualRequest] = []
        self.presented: list[VirtualRequest] = []
        self.accepted_empty: list[dict[str, Any]] = []
        self.response_records: list[dict[str, Any]] = []
        self.flushed_entries: set[int] = set()
        self._nack_sent = False
        self._fault_sent = False
        self._completed: set[tuple] = set()
        self._late_responses = 0
        self._flush_rules: list[tuple[int, bool]] = []

    def ready(self, cycle: int, kind: str, lane: int):
        if kind == "load":
            return cycle >= self.config.ldu_hold_cycles
        if kind == "store":
            return cycle >= self.config.sta_hold_cycles
        if kind == "empty":
            return cycle >= self.config.empty_hold_cycles
        raise ValueError(f"unknown virtual LSQ ready kind: {kind}")

    def present(self, request: VirtualRequest):
        self.presented.append(request)

    def accept(self, request: VirtualRequest):
        self.accepted.append(request)
        if any(
            request.rob >= rob if inclusive else request.rob > rob
            for rob, inclusive in self._flush_rules
        ):
            self.flushed_entries.add(request.entry)
        key = request.identity
        is_nack = self.config.nack_once and not self._nack_sent
        if is_nack:
            self._nack_sent = True

        exception = (
            self.config.fault_kind == request.kind
            and not self._fault_sent
            and (
                self.config.fault_element is None
                or request.element == self.config.fault_element
            )
        )
        if exception:
            self._fault_sent = True

        response = Response(
            valid=True,
            entry_idx=request.entry,
            issue_mask=1 << request.byte,
            is_nack=int(is_nack),
            exception=int(exception),
            exception_number=self.config.exception_number,
            fault_elem_idx=request.element,
        )
        delay = (
            self.config.response_latency
            + self.config.extra_delay(request.element)
        )
        self.scheduler.schedule(
            request.cycle + delay,
            PHASE_RESPONSE,
            "lsq-response",
            request=request,
            response=response,
        )

    def accept_empty(self, record: dict[str, Any]):
        self.accepted_empty.append(dict(record))
        response = EmptyResponse(
            valid=True,
            entry_idx=record["entry"],
            issue_mask=record["mask"],
        )
        self.scheduler.schedule(
            record["cycle"] + self.config.empty_latency,
            PHASE_RESPONSE,
            "empty-response",
            record=dict(record),
            response=response,
        )

    def flush(self, rob_value: int, cycle: int, *, inclusive=False):
        rob_value = _public_rob(rob_value)
        self._flush_rules.append((rob_value, inclusive))
        flushed = {
            request.entry for request in self.accepted
            if (request.rob >= rob_value if inclusive else request.rob > rob_value)
        }
        self.flushed_entries.update(flushed)
        self.scheduler.events.append({
            "action": "flush-lsq",
            "cycle": cycle,
            "rob": rob_value,
            "inclusive": inclusive,
            "entries": sorted(flushed),
        })

    def dispatch_response(self, event: ScheduledEvent):
        request = event.payload["request"]
        response = event.payload["response"]
        late = request.entry in self.flushed_entries
        if late:
            self._late_responses += 1
            if not self.config.deliver_late_response:
                self.response_records.append({
                    "cycle": event.cycle,
                    "kind": request.kind,
                    "entry": request.entry,
                    "element": request.element,
                    "dropped_late": True,
                })
                return None
        if not response.is_nack and not response.exception:
            if request.identity in self._completed:
                raise AssertionError(
                    f"virtual LSQ completed duplicate request {request.identity}"
                )
            self._completed.add(request.identity)
        self.response_records.append({
            "cycle": event.cycle,
            "kind": request.kind,
            "lane": request.lane,
            "entry": request.entry,
            "element": request.element,
            "issue_mask": response.issue_mask,
            "nack": bool(response.is_nack),
            "exception": bool(response.exception),
            "late": late,
        })
        return request.kind, request.lane, response

    @property
    def late_response_count(self):
        return self._late_responses


class VirtualVRF:
    """Virtual old-vector store and merge-write contract."""

    def __init__(self, scheduler: EventScheduler, config: VirtualSystemConfig):
        self.scheduler = scheduler
        self.config = config
        self.old_data: dict[int, int] = {}
        self.reads: list[dict[str, Any]] = []
        self.writes: list[dict[str, Any]] = []

    def set_old_data(self, entry: int, data: int):
        self.old_data[entry] = data

    def observe_read(self, outputs: dict[str, int], cycle: int):
        if not outputs.get("io_vrfReadReq_valid"):
            return
        entry = outputs["io_vrfReadReq_bits_entryIdx"]
        rob = outputs["io_vrfReadReq_bits_robIdx_value"]
        data = self.old_data.get(entry, self.config.vrf_data)
        record = {
            "cycle": cycle,
            "entry": entry,
            "rob": rob,
            "data": data,
        }
        self.reads.append(record)
        self.scheduler.schedule(
            cycle + self.config.vrf_latency,
            PHASE_RESPONSE,
            "vrf-response",
            response=VrfResponse(
                valid=True,
                entry_idx=entry,
                rob_value=rob,
                data=data,
            ),
        )

    def dispatch_response(self, event: ScheduledEvent):
        response = event.payload["response"]
        self.scheduler.events.append({
            "action": "vrf-dispatch",
            "cycle": event.cycle,
            "entry": response.entry_idx,
            "rob": response.rob_value,
        })
        return response

    def observe_write(self, outputs: dict[str, int], cycle: int):
        if not outputs.get("io_vrfWriteReq_valid"):
            return
        record = {
            "cycle": cycle,
            "entry": outputs["io_vrfWriteReq_bits_entryIdx"],
            "pdest": outputs["io_vrfWriteReq_bits_pdest"],
            "mask": outputs["io_vrfWriteReq_bits_mask"],
            "data": outputs["io_vrfWriteReq_bits_data"],
        }
        if not record["mask"]:
            raise AssertionError("virtual VRF write has an empty merge mask")
        self.writes.append(record)
        self.old_data[record["entry"]] = record["data"]


@dataclass(slots=True)
class VirtualROBEntry:
    entry: int
    rob: int
    uop_idx: int
    last_uop: int
    admitted_cycle: int
    flushed: bool = False
    exception: bool = False
    fault_elem: int | None = None
    writeback_cycle: int | None = None
    retired_cycle: int | None = None


class VirtualROB:
    """ROB age/flush/writeback/restart contract."""

    def __init__(self, scheduler: EventScheduler):
        self.scheduler = scheduler
        self.entries: dict[int, VirtualROBEntry] = {}
        self.writebacks: list[dict[str, Any]] = []
        self.retires: list[dict[str, Any]] = []
        self.redirects: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self._redirect_rules: list[tuple[int, bool]] = []

    def admit(self, addr: AddrPacket, cycle: int):
        previous = self.entries.get(addr.entry_idx)
        if previous is not None and not previous.flushed:
            self.errors.append(
                f"entry {addr.entry_idx} admitted before prior virtual ROB state cleared"
            )
        if previous is not None and previous.exception and previous.fault_elem is not None:
            if addr.vstart < previous.fault_elem:
                self.errors.append(
                    f"restart entry {addr.entry_idx} vstart={addr.vstart} "
                    f"before fault={previous.fault_elem}"
                )
            self.scheduler.events.append({
                "action": "restart-admission",
                "cycle": cycle,
                "entry": addr.entry_idx,
                "rob": addr.rob_value,
                "vstart": addr.vstart,
                "fault": previous.fault_elem,
            })
        self.entries[addr.entry_idx] = VirtualROBEntry(
            entry=addr.entry_idx,
            rob=_public_rob(addr.rob_value),
            uop_idx=addr.uop_idx,
            last_uop=addr.last_uop,
            admitted_cycle=cycle,
        )
        public_rob = _public_rob(addr.rob_value)
        if any(
            public_rob >= rob if inclusive else public_rob > rob
            for rob, inclusive in self._redirect_rules
        ):
            self.entries[addr.entry_idx].flushed = True

    def redirect(self, rob_value: int, cycle: int, *, inclusive=False):
        rob_value = _public_rob(rob_value)
        self._redirect_rules.append((rob_value, inclusive))
        flushed = []
        for entry in self.entries.values():
            matches = entry.rob >= rob_value if inclusive else entry.rob > rob_value
            if matches and not entry.flushed:
                entry.flushed = True
                flushed.append(entry.entry)
        self.redirects.append({
            "cycle": cycle,
            "rob": rob_value,
            "inclusive": inclusive,
            "flushed_entries": sorted(flushed),
        })

    def writeback(self, outputs: dict[str, int], cycle: int):
        if not outputs.get("io_robWriteback_valid"):
            return
        entry_idx = outputs["io_robWriteback_bits_entryIdx"]
        rob_value = outputs["io_robWriteback_bits_robIdx_value"]
        entry = self.entries.get(entry_idx)
        if entry is None:
            self.errors.append(f"writeback for unknown virtual ROB entry {entry_idx}")
            return
        if entry.flushed:
            self.errors.append(f"flushed entry {entry_idx} produced writeback")
        if entry.rob != rob_value:
            self.errors.append(
                f"entry {entry_idx} writeback ROB mismatch {rob_value} != {entry.rob}"
            )
        entry.exception = bool(outputs["io_robWriteback_bits_exception"])
        entry.writeback_cycle = cycle
        fault = outputs["io_robWriteback_bits_faultVstart"]
        entry.fault_elem = fault if entry.exception else None
        record = {
            "cycle": cycle,
            "entry": entry_idx,
            "rob": rob_value,
            "exception": entry.exception,
            "fault_vstart": fault,
        }
        self.writebacks.append(record)
        if entry.exception:
            # An exception writeback retires/clears the virtual entry from the
            # current instruction; a later admission with vstart is a restart.
            entry.flushed = True
        self.scheduler.schedule(
            cycle + 1,
            PHASE_RETIRE,
            "rob-retire",
            entry=entry_idx,
            rob=rob_value,
        )

    def dispatch_retire(self, event: ScheduledEvent):
        entry_idx = event.payload["entry"]
        entry = self.entries.get(entry_idx)
        if entry is None:
            self.errors.append(f"retire for unknown virtual ROB entry {entry_idx}")
            return
        if entry.flushed and not entry.exception:
            self.errors.append(f"flushed entry {entry_idx} retired")
        entry.retired_cycle = event.cycle
        self.retires.append({
            "cycle": event.cycle,
            "entry": entry_idx,
            "rob": event.payload["rob"],
            "exception": entry.exception,
        })

    def record_restart(self, addr: AddrPacket, cycle: int):
        candidates = [
            entry for entry in self.entries.values()
            if entry.rob == _public_rob(addr.rob_value) and entry.exception
        ]
        if candidates:
            fault = min(
                entry.fault_elem for entry in candidates
                if entry.fault_elem is not None
            )
            if addr.vstart < fault:
                self.errors.append(
                    f"restart entry {addr.entry_idx} vstart={addr.vstart} before fault={fault}"
                )
        self.scheduler.events.append({
            "action": "restart",
            "cycle": cycle,
            "entry": addr.entry_idx,
            "rob": _public_rob(addr.rob_value),
            "vstart": addr.vstart,
        })


class VirtualVOQ:
    """Virtual SQ/VOQ contract with separate order observations."""

    def __init__(self, config: VirtualSystemConfig):
        self.config = config
        self.presented: list[dict[str, Any]] = []
        self.accepted: list[dict[str, Any]] = []
        self.memory_effects: list[dict[str, Any]] = []
        self._next_element = config.ordered_first_element
        self._accepted_keys: set[tuple] = set()
        self._memory_keys: set[tuple] = set()
        self.errors: list[str] = []

    def refine_ready(self, outputs: dict[str, int], beat: Beat):
        if not self.config.ordered_sq:
            return beat
        candidates = []
        for lane in range(2):
            prefix = f"io_staReq_{lane}_"
            if outputs.get(prefix + "valid") and outputs.get(prefix + "bits_meta_valid"):
                candidates.append((
                    outputs[prefix + "bits_meta_elemIdx"], lane,
                ))
        ready = [False, False]
        for element, lane in sorted(candidates):
            if element == self._next_element:
                ready[lane] = beat.sta_ready[lane]
                break
        return replace(beat, sta_ready=tuple(ready))

    def observe_presented(self, record: dict[str, Any]):
        self.presented.append(dict(record))

    def observe_accepted(self, record: dict[str, Any]):
        self.accepted.append(dict(record))
        key = (
            record["entry"], record["element"], record["address"],
        )
        if key in self._accepted_keys:
            return
        self._accepted_keys.add(key)
        if self.config.ordered_sq:
            if record["element"] != self._next_element:
                self.errors.append(
                    f"ordered SQ accepted element {record['element']} expected {self._next_element}"
                )
            else:
                self._next_element += 1

    def observe_memory_effect(self, record: dict[str, Any]):
        key = (record["entry"], record["element"], record["address"])
        if key in self._memory_keys:
            self.errors.append(f"duplicate virtual memory effect {key}")
            return
        self._memory_keys.add(key)
        self.memory_effects.append(dict(record))

    @property
    def presented_store_order_violation(self):
        by_cycle: dict[int, list[int]] = {}
        for record in self.presented:
            by_cycle.setdefault(record["cycle"], []).append(record["element"])
        return any(len(set(elements)) > 1 for elements in by_cycle.values())


class VirtualSystem:
    """Compose the virtual components around a real DUT public boundary."""

    def __init__(self, config: VirtualSystemConfig = VirtualSystemConfig()):
        self.config = config
        self.scheduler = EventScheduler()
        self.lsq = VirtualLSQ(self.scheduler, config)
        self.vrf = VirtualVRF(self.scheduler, config)
        self.rob = VirtualROB(self.scheduler)
        self.voq = VirtualVOQ(config)
        self.errors: list[str] = []
        self._response_inputs = {
            "ldu": [Response(), Response(), Response()],
            "sta": [Response(), Response()],
            "empty": [EmptyResponse(), EmptyResponse()],
            "vrf": VrfResponse(),
        }
        self._cycle = 0

    def reset(self):
        self.__init__(self.config)

    def admit(self, addr: AddrPacket, cycle: int):
        self.rob.admit(addr, cycle)

    def restart(self, addr: AddrPacket, cycle: int):
        self.rob.record_restart(addr, cycle)

    def begin_cycle(self, cycle: int):
        self._cycle = cycle
        self._response_inputs = {
            "ldu": [Response(), Response(), Response()],
            "sta": [Response(), Response()],
            "empty": [EmptyResponse(), EmptyResponse()],
            "vrf": VrfResponse(),
        }
        for event in self.scheduler.due(cycle):
            if event.kind == "lsq-response":
                result = self.lsq.dispatch_response(event)
                if result is not None:
                    kind, lane, response = result
                    self._response_inputs["ldu" if kind == "load" else "sta"][lane] = response
            elif event.kind == "empty-response":
                record = event.payload["record"]
                response = event.payload["response"]
                if record["entry"] not in self.lsq.flushed_entries:
                    self._response_inputs["empty"][record["lane"]] = response
            elif event.kind == "vrf-response":
                self._response_inputs["vrf"] = self.vrf.dispatch_response(event)
            elif event.kind == "rob-retire":
                self.rob.dispatch_retire(event)
            else:
                self.errors.append(f"unknown virtual event {event.kind}")
        return self._response_inputs

    def response_beat(self, beat: Beat):
        return replace(
            beat,
            ldu_resp=tuple(self._response_inputs["ldu"]),
            sta_resp=tuple(self._response_inputs["sta"]),
            empty_resp=tuple(self._response_inputs["empty"]),
            vrf_resp=self._response_inputs["vrf"],
        )

    def refine_ready(self, outputs: dict[str, int], beat: Beat):
        return self.voq.refine_ready(outputs, beat)

    @staticmethod
    def _request(outputs, group, lane, cycle):
        prefix = f"io_{group}_{lane}_"
        if not (
            outputs.get(prefix + "valid")
            and outputs.get(prefix + "bits_meta_valid", 1)
        ):
            return None
        return VirtualRequest(
            kind="load" if group == "lduReq" else "store",
            lane=lane,
            cycle=cycle,
            entry=outputs[prefix + "bits_meta_entryIdx"],
            rob=outputs[prefix + "bits_req_robIdx_value"],
            element=outputs[prefix + "bits_meta_elemIdx"],
            byte=outputs[prefix + "bits_meta_byteOffset"],
            mask=outputs[prefix + "bits_meta_dataMask"],
            address=outputs[prefix + "bits_req_data_src_0"],
            is_load=group == "lduReq",
        )

    def observe_cycle(self, outputs: dict[str, int], beat: Beat, cycle: int):
        if beat.redirect.valid:
            inclusive = beat.redirect.level == 1
            self.rob.redirect(beat.redirect.rob_value, cycle, inclusive=inclusive)
            self.lsq.flush(beat.redirect.rob_value, cycle, inclusive=inclusive)

        for group, count, ready in (
            ("lduReq", 3, beat.ldu_ready),
            ("staReq", 2, beat.sta_ready),
        ):
            for lane in range(count):
                request = self._request(outputs, group, lane, cycle)
                if request is None:
                    continue
                self.lsq.present(request)
                if group == "staReq":
                    self.voq.observe_presented(request.to_dict())
                if ready[lane]:
                    self.lsq.accept(request)
                    if group == "staReq":
                        self.voq.observe_accepted(request.to_dict())

        for lane in range(2):
            prefix = f"io_lsqEmptyReq_{lane}_"
            if outputs.get(prefix + "valid") and beat.empty_ready[lane]:
                self.lsq.accept_empty({
                    "cycle": cycle,
                    "lane": lane,
                    "entry": outputs[prefix + "bits_entryIdx"],
                    "mask": outputs[prefix + "bits_issueMask"],
                })

        self.vrf.observe_read(outputs, cycle)
        self.vrf.observe_write(outputs, cycle)
        self.rob.writeback(outputs, cycle)

        # Successful store responses are the virtual memory-effect point.  The
        # corresponding request is found from the public response identity and
        # the latest accepted request with the same entry/mask.
        for response in beat.sta_resp:
            if not response.valid or response.is_nack or response.exception:
                continue
            candidates = [
                request for request in reversed(self.lsq.accepted)
                if request.kind == "store"
                and request.entry == response.entry_idx
                and response.issue_mask == (1 << request.byte)
            ]
            if candidates:
                self.voq.observe_memory_effect(candidates[0].to_dict())

    def to_dict(self):
        errors = list(self.errors)
        errors.extend(self.rob.errors)
        errors.extend(self.voq.errors)
        return {
            "virtual_contract_pass": not errors,
            "errors": errors,
            "scheduler_events": list(self.scheduler.events),
            "lsq": {
                "presented": [item.to_dict() for item in self.lsq.presented],
                "accepted": [item.to_dict() for item in self.lsq.accepted],
                "accepted_empty": list(self.lsq.accepted_empty),
                "responses": list(self.lsq.response_records),
                "late_response_count": self.lsq.late_response_count,
            },
            "vrf": {
                "reads": list(self.vrf.reads),
                "writes": list(self.vrf.writes),
            },
            "rob": {
                "writebacks": list(self.rob.writebacks),
                "retires": list(self.rob.retires),
                "redirects": list(self.rob.redirects),
            },
            "voq": {
                "presented": list(self.voq.presented),
                "accepted": list(self.voq.accepted),
                "memory_effects": list(self.voq.memory_effects),
                "presented_store_order_violation": self.voq.presented_store_order_violation,
                "accepted_elements": [item["element"] for item in self.voq.accepted],
                "memory_effect_elements": [item["element"] for item in self.voq.memory_effects],
            },
        }

    @property
    def quiescent(self):
        return self.scheduler.pending == 0
