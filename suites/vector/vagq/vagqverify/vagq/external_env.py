"""Public-boundary external environment for generated VAGQ.

This is deliberately a consumer/response model, not a second VAGQ model and
not a whole-chip simulator.  It drives only the public ``Beat`` boundary and
uses the real picker DUT clock.  The environment can consume every request so
that a DUT transaction reaches writeback even when no real LSQ/VRF/ROB is
connected.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
import json
from pathlib import Path

from .driver import response_beat
from .types import (
    AddrPacket,
    Beat,
    DataPacket,
    EmptyResponse,
    Redirect,
    Response,
    VrfResponse,
)
from .virtual_system import VirtualSystem


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    packets: tuple[tuple[AddrPacket, DataPacket], ...]
    response_latency: int = 1
    ldu_hold_cycles: int = 0
    sta_hold_cycles: int = 0
    empty_hold_cycles: int = 0
    ordered_sq: bool = False
    ordered_first_element: int = 0
    nack_once: bool = False
    fault_kind: str | None = None
    fault_element: int | None = None
    exception_number: int = 9
    redirect_cycle: int | None = None
    redirect_rob_value: int = 0
    std_busy_cycles: frozenset[int] = frozenset()
    vrf_data: int = 0
    expected_writebacks: int | None = None
    min_cycles: int = 0
    max_cycles: int = 320

    def __post_init__(self):
        if self.response_latency < 1:
            raise ValueError('response latency must be at least one cycle')
        if self.fault_kind not in (None, 'load', 'store'):
            raise ValueError(f'unsupported fault kind: {self.fault_kind}')


@dataclass(slots=True)
class RunLog:
    scenario: str
    stimulus: dict = field(default_factory=dict)
    completed: bool = False
    timed_out: bool = False
    cycles: int = 0
    accepted_addresses: list[dict] = field(default_factory=list)
    presented_requests: list[dict] = field(default_factory=list)
    accepted_requests: list[dict] = field(default_factory=list)
    accepted_empty_requests: list[dict] = field(default_factory=list)
    responses: list[dict] = field(default_factory=list)
    vrf_reads: list[dict] = field(default_factory=list)
    std_outputs: list[dict] = field(default_factory=list)
    writebacks: list[dict] = field(default_factory=list)
    public_same_cycle_store_elements: list[list[int]] = field(default_factory=list)
    sq_accepted_elements: list[int] = field(default_factory=list)
    duplicate_memory_bytes: dict[str, int] = field(default_factory=dict)
    extra_active_elements: list[int] = field(default_factory=list)
    extra_empty_masks: list[int] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    virtual_contract: dict = field(default_factory=dict)

    @property
    def presented_store_order_violation(self):
        return any(len(set(elements)) > 1 for elements in self.public_same_cycle_store_elements)

    @property
    def sq_order_is_monotonic(self):
        return self.sq_accepted_elements == sorted(self.sq_accepted_elements)

    def to_dict(self):
        return {
            'scenario': self.scenario,
            'stimulus': self.stimulus,
            'completed': self.completed,
            'timed_out': self.timed_out,
            'cycles': self.cycles,
            'accepted_addresses': self.accepted_addresses,
            'presented_requests': self.presented_requests,
            'accepted_requests': self.accepted_requests,
            'accepted_empty_requests': self.accepted_empty_requests,
            'responses': self.responses,
            'vrf_reads': self.vrf_reads,
            'std_outputs': self.std_outputs,
            'writebacks': self.writebacks,
            'public_same_cycle_store_elements': self.public_same_cycle_store_elements,
            'sq_accepted_elements': self.sq_accepted_elements,
            'presented_store_order_violation': self.presented_store_order_violation,
            'sq_order_is_monotonic': self.sq_order_is_monotonic,
            'duplicate_memory_bytes': self.duplicate_memory_bytes,
            'extra_active_elements': self.extra_active_elements,
            'extra_empty_masks': self.extra_empty_masks,
            'assumptions': self.assumptions,
            'virtual_contract': self.virtual_contract,
        }


class PublicVAGQEnvironment:
    """Drive a real VAGQ root with a deterministic external consumer model."""

    def __init__(self, *, log_root=None):
        self.log_root = Path(log_root) if log_root is not None else None

    @staticmethod
    def _input_beat(packet, *, ldu_ready, sta_ready, empty_ready,
                    std_busy, redirect):
        if packet is None:
            return Beat(
                ldu_ready=ldu_ready,
                sta_ready=sta_ready,
                empty_ready=empty_ready,
                std_busy=std_busy,
                redirect=redirect,
            )
        addr, data = packet
        indexed = addr.uop_type >= 4
        return Beat(
            addr=(addr, None),
            addr_valid=(True, False),
            stride=(data, None) if not indexed else (None, None),
            stride_valid=(True, False) if not indexed else (False, False),
            index=(data, None) if indexed else (None, None),
            index_valid=(True, False) if indexed else (False, False),
            ldu_ready=ldu_ready,
            sta_ready=sta_ready,
            empty_ready=empty_ready,
            std_busy=std_busy,
            redirect=redirect,
        )

    @staticmethod
    def _valid_output(outputs, group, lane):
        prefix = f'io_{group}_{lane}_'
        return bool(
            outputs.get(prefix + 'valid') and
            (group == 'lsqEmptyReq' or outputs.get(prefix + 'bits_meta_valid', 1))
        )

    @staticmethod
    def _request_record(outputs, group, lane, cycle):
        prefix = f'io_{group}_{lane}_'
        if group == 'lsqEmptyReq':
            return {
                'cycle': cycle,
                'kind': 'empty',
                'lane': lane,
                'entry': outputs[prefix + 'bits_entryIdx'],
                'mask': outputs[prefix + 'bits_issueMask'],
            }
        return {
            'cycle': cycle,
            'kind': 'load' if group == 'lduReq' else 'store',
            'lane': lane,
            'entry': outputs[prefix + 'bits_meta_entryIdx'],
            'element': outputs[prefix + 'bits_meta_elemIdx'],
            'byte': outputs[prefix + 'bits_meta_byteOffset'],
            'mask': outputs[prefix + 'bits_meta_dataMask'],
            'address': outputs[prefix + 'bits_req_data_src_0'],
        }

    def _probe_cycle(self, dut_env, beat, *, scenario, cycle, sq_next,
                     virtual_system=None):
        """Sample once, optionally let a virtual SQ refine STA ready, tick once."""
        dut_env.driver.drive(beat)
        outputs = dut_env.sample()
        final_beat = beat
        if virtual_system is not None:
            final_beat = virtual_system.refine_ready(outputs, beat)
            dut_env.driver.drive(final_beat)
            outputs = dut_env.sample()
        elif scenario.ordered_sq:
            ready = [False, False]
            if cycle >= scenario.sta_hold_cycles:
                candidates = []
                for lane in range(2):
                    if self._valid_output(outputs, 'staReq', lane):
                        prefix = f'io_staReq_{lane}_'
                        candidates.append((
                            outputs[prefix + 'bits_meta_elemIdx'], lane,
                        ))
                if candidates:
                    candidates.sort()
                    chosen_element, chosen_lane = next(
                        (
                            item for item in candidates
                            if sq_next is None or item[0] == sq_next
                        ),
                        candidates[0],
                    )
                    ready[chosen_lane] = True
            final_beat = replace(beat, sta_ready=tuple(ready))
            dut_env.driver.drive(final_beat)
            outputs = dut_env.sample()
        dut_env.driver.tick()
        return outputs, final_beat

    @staticmethod
    def _schedule_response(pending, cycle, lane, response):
        pending[cycle][lane] = response

    def _write_log(self, log):
        if self.log_root is None:
            return
        self.log_root.mkdir(parents=True, exist_ok=True)
        path = self.log_root / f'{log.scenario}.json'
        path.write_text(json.dumps(log.to_dict(), indent=2, sort_keys=True) + '\n')

    def run(self, dut_env, scenario: Scenario, *,
            virtual_system: VirtualSystem | None = None,
            reset_virtual: bool = True):
        """Run a scenario to writeback or the configured timeout."""
        log = RunLog(
            scenario.name,
            stimulus={
                'response_latency': scenario.response_latency,
                'ldu_hold_cycles': scenario.ldu_hold_cycles,
                'sta_hold_cycles': scenario.sta_hold_cycles,
                'empty_hold_cycles': scenario.empty_hold_cycles,
                'ordered_sq': scenario.ordered_sq,
                'ordered_first_element': scenario.ordered_first_element,
                'nack_once': scenario.nack_once,
                'fault_kind': scenario.fault_kind,
                'fault_element': scenario.fault_element,
                'exception_number': scenario.exception_number,
                'redirect_cycle': scenario.redirect_cycle,
                'redirect_rob_value': scenario.redirect_rob_value,
                'std_busy_cycles': sorted(scenario.std_busy_cycles),
                'vrf_data': scenario.vrf_data,
                'expected_writebacks': scenario.expected_writebacks,
                'min_cycles': scenario.min_cycles,
                'max_cycles': scenario.max_cycles,
                'packets': [
                    {'addr': {
                        key: getattr(addr, key)
                        for key in addr.__dataclass_fields__
                    }, 'data': {
                        key: getattr(data, key)
                        for key in data.__dataclass_fields__
                    }}
                    for addr, data in scenario.packets
                ],
            },
        )
        log.assumptions.extend((
            'External consumer model drives only VAGQ public Beat leaves.',
            'A response is scheduled after the configured public request latency.',
            'ordered_sq=True serializes SQ acceptance, but does not erase presented order.',
            'No whole-chip architectural state is claimed by this environment.',
        ))
        if virtual_system is not None and reset_virtual:
            virtual_system.reset()
            log.assumptions.append(
                'Virtual LSQ/VRF/ROB/VOQ are independent public-boundary contracts, not whole-chip RTL.'
            )
        dut_env.reset()
        pending_ldu = defaultdict(dict)
        pending_sta = defaultdict(dict)
        pending_empty = defaultdict(dict)
        pending_vrf = {}
        packet_index = 0
        current_packet = None
        accepted_nack = False
        fault_sent = False
        sq_next = scenario.ordered_first_element if scenario.ordered_sq else None
        expected_writebacks = (
            len(scenario.packets)
            if scenario.expected_writebacks is None
            else scenario.expected_writebacks
        )
        response_seen = defaultdict(int)
        byte_counter = Counter()

        # A neutral cycle establishes a clean post-reset public environment.
        neutral = self._input_beat(
            None,
            ldu_ready=(True, True, True),
            sta_ready=(True, True),
            empty_ready=(True, True),
            std_busy=(False, False),
            redirect=Redirect(),
        )
        dut_env.driver.drive(neutral)
        dut_env.sample()
        dut_env.driver.tick()

        for cycle in range(scenario.max_cycles):
            if current_packet is None and packet_index < len(scenario.packets):
                current_packet = scenario.packets[packet_index]

            ldu_ready = (
                (False, False, False)
                if cycle < scenario.ldu_hold_cycles
                else (True, True, True)
            )
            sta_ready = (
                (False, False)
                if cycle < scenario.sta_hold_cycles
                else (True, True)
            )
            empty_ready = (
                (False, False)
                if cycle < scenario.empty_hold_cycles
                else (True, True)
            )
            redirect = Redirect(
                valid=scenario.redirect_cycle == cycle,
                level=1 if scenario.redirect_cycle == cycle else 0,
                rob_value=scenario.redirect_rob_value,
            )
            beat = self._input_beat(
                current_packet,
                ldu_ready=ldu_ready,
                sta_ready=sta_ready,
                empty_ready=empty_ready,
                std_busy=tuple(cycle in scenario.std_busy_cycles for _ in range(2)),
                redirect=redirect,
            )
            # Responses due this cycle are presented alongside the consumer
            # ready signals; they are consumed by the real merge/entry logic.
            ldu_resp = [Response() for _ in range(3)]
            sta_resp = [Response() for _ in range(2)]
            empty_resp = [EmptyResponse() for _ in range(2)]
            if virtual_system is None:
                for lane, response in pending_ldu.pop(cycle, {}).items():
                    ldu_resp[lane] = response
                for lane, response in pending_sta.pop(cycle, {}).items():
                    sta_resp[lane] = response
                for lane, response in pending_empty.pop(cycle, {}).items():
                    empty_resp[lane] = response
                vrf_response = pending_vrf.pop(cycle, VrfResponse())
            else:
                virtual_inputs = virtual_system.begin_cycle(cycle)
                ldu_resp = list(virtual_inputs['ldu'])
                sta_resp = list(virtual_inputs['sta'])
                empty_resp = list(virtual_inputs['empty'])
                vrf_response = virtual_inputs['vrf']
            beat = replace(
                beat,
                ldu_resp=tuple(ldu_resp),
                sta_resp=tuple(sta_resp),
                empty_resp=tuple(empty_resp),
                vrf_resp=vrf_response,
            )

            outputs, final_beat = self._probe_cycle(
                dut_env, beat, scenario=scenario, cycle=cycle, sq_next=sq_next,
                virtual_system=virtual_system,
            )
            log.cycles = cycle + 1

            if current_packet is not None and outputs.get('io_addrUop_0_ready'):
                addr, data = current_packet
                log.accepted_addresses.append({
                    'cycle': cycle,
                    'entry': addr.entry_idx,
                    'uop_idx': addr.uop_idx,
                    'uop_type': addr.uop_type,
                })
                if virtual_system is not None:
                    virtual_system.admit(addr, cycle)
                packet_index += 1
                current_packet = None

            store_elements = []
            for group, lanes, ready_attr, pending in (
                ('lduReq', 3, 'ldu_ready', pending_ldu),
                ('staReq', 2, 'sta_ready', pending_sta),
            ):
                for lane in range(lanes):
                    if not self._valid_output(outputs, group, lane):
                        continue
                    record = self._request_record(outputs, group, lane, cycle)
                    log.presented_requests.append(record)
                    ready = getattr(final_beat, ready_attr)[lane]
                    if group == 'staReq':
                        store_elements.append(record['element'])
                    if not ready:
                        continue
                    log.accepted_requests.append(record)
                    if group == 'staReq' and scenario.ordered_sq:
                        log.sq_accepted_elements.append(record['element'])
                        sq_next = record['element'] + 1
                    if virtual_system is None:
                        issue_mask = 1 << record['byte']
                        exception = False
                        is_nack = False
                        if scenario.nack_once and not accepted_nack:
                            is_nack = True
                            accepted_nack = True
                        if (
                            scenario.fault_kind == record['kind'] and
                            not fault_sent and
                            (scenario.fault_element is None or
                             record['element'] == scenario.fault_element)
                        ):
                            exception = True
                            fault_sent = True
                        response = Response(
                            valid=True,
                            entry_idx=record['entry'],
                            issue_mask=issue_mask,
                            is_nack=int(is_nack),
                            exception=int(exception),
                            exception_number=scenario.exception_number,
                            fault_elem_idx=record.get('element', 0),
                        )
                        pending[cycle + scenario.response_latency][lane] = response
                        log.responses.append({
                            'scheduled_cycle': cycle + scenario.response_latency,
                            'kind': record['kind'],
                            'lane': lane,
                            'entry': record['entry'],
                            'element': record.get('element'),
                            'nack': is_nack,
                            'exception': exception,
                        })
                        if record['kind'] in ('load', 'store'):
                            for byte in range(16):
                                if record['mask'] & (1 << byte):
                                    byte_counter[record['address'] + byte] += 1
            if store_elements:
                log.public_same_cycle_store_elements.append(store_elements)

            for lane in range(2):
                if self._valid_output(outputs, 'lsqEmptyReq', lane):
                    record = self._request_record(outputs, 'lsqEmptyReq', lane, cycle)
                    if final_beat.empty_ready[lane]:
                        log.accepted_empty_requests.append(record)
                        if virtual_system is None:
                            pending_empty[cycle + scenario.response_latency][lane] = EmptyResponse(
                                valid=True,
                                entry_idx=record['entry'],
                                issue_mask=record['mask'],
                            )

            if outputs.get('io_vrfReadReq_valid'):
                log.vrf_reads.append({
                    'cycle': cycle,
                    'entry': outputs['io_vrfReadReq_bits_entryIdx'],
                    'rob': outputs['io_vrfReadReq_bits_robIdx_value'],
                })
                if virtual_system is None:
                    pending_vrf[cycle + scenario.response_latency] = VrfResponse(
                        valid=True,
                        entry_idx=outputs['io_vrfReadReq_bits_entryIdx'],
                        rob_value=outputs['io_vrfReadReq_bits_robIdx_value'],
                        data=scenario.vrf_data,
                    )
            for lane in range(2):
                prefix = f'io_vagqStdData_{lane}_'
                if outputs.get(prefix + 'valid'):
                    log.std_outputs.append({
                        'cycle': cycle,
                        'lane': lane,
                        'sq': outputs[prefix + 'bits_sqIdx_value'],
                    })
            if outputs.get('io_robWriteback_valid'):
                log.writebacks.append({
                    'cycle': cycle,
                    'entry': outputs['io_robWriteback_bits_entryIdx'],
                    'exception': outputs['io_robWriteback_bits_exception'],
                })

            if virtual_system is not None:
                virtual_system.observe_cycle(outputs, final_beat, cycle)

            if (
                packet_index == len(scenario.packets) and
                cycle + 1 >= scenario.min_cycles and
                len(log.writebacks) >= expected_writebacks and
                (
                    virtual_system is not None and virtual_system.quiescent
                    or virtual_system is None and not pending_ldu and not pending_sta
                    and not pending_empty and not pending_vrf
                )
            ):
                log.completed = True
                break

        log.timed_out = not log.completed
        log.duplicate_memory_bytes = {
            hex(address): count for address, count in byte_counter.items()
            if count > 1
        }
        if scenario.name.startswith('fractional'):
            expected = {0, 1} if scenario.packets else set()
            log.extra_active_elements = sorted({
                item['element'] for item in log.accepted_requests
                if item.get('kind') == 'load' and item.get('element') not in expected
            })
            log.extra_empty_masks = [
                item['mask'] & ~0x3 for item in log.accepted_empty_requests
                if item['mask'] & ~0x3
            ]
        if virtual_system is not None:
            log.virtual_contract = virtual_system.to_dict()
            log.responses.extend(virtual_system.lsq.response_records)
            log.sq_accepted_elements = [
                item['element'] for item in virtual_system.voq.accepted
            ]
            by_cycle = defaultdict(list)
            for item in virtual_system.voq.presented:
                by_cycle[item['cycle']].append(item['element'])
            log.public_same_cycle_store_elements = [
                elements for _, elements in sorted(by_cycle.items())
            ]
        self._write_log(log)
        return log
