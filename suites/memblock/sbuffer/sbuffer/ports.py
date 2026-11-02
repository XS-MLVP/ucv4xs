"""Exact public-port binding and encoding for the fixed DefaultConfig DUT."""
from __future__ import annotations

from toffee import Bundle

from .model import Enq
from .transactions import Cycle, ForwardResult, Observation, Request, Status


class SbufferPorts:
    def __init__(self, dut):
        self.dut = dut
        names = ['reset', 'io_dcache_req_ready', 'io_flush_valid', 'io_flush_isCmo',
                 'io_sqempty', 'io_mshr_store_empty', 'io_force_write',
                 'io_csrCtrl_sbuffer_timeout', 'io_dcache_main_pipe_hit_resp_valid',
                 'io_dcache_main_pipe_hit_resp_bits_id', 'io_dcache_replay_resp_valid',
                 'io_dcache_replay_resp_bits_id']
        for port in range(2):
            names.append(f'io_in_req_{port}_valid')
            names.extend(f'io_in_req_{port}_bits_{field}'
                         for field in ('addr', 'vaddr', 'mask', 'data', 'wline'))
        for lane in range(3):
            names.extend(f'io_forward_{lane}_{field}' for field in (
                's0Req_valid', 's0Req_bits_vaddr', 's1Req_paddr', 's1Kill'))
        self.inputs = {name: getattr(dut, name) for name in names}
        self.bits = Bundle(**self.inputs)

    @staticmethod
    def value(signal):
        return int(signal.value)

    def encode(self, cycle: Cycle):
        """Validate the entire command before the first physical write."""
        values = dict.fromkeys(self.inputs, 0)
        controls = cycle.controls
        values.update(reset=int(cycle.reset), io_dcache_req_ready=int(cycle.accept_request),
                      io_flush_valid=int(controls.flush), io_flush_isCmo=int(controls.cmo),
                      io_sqempty=int(controls.sq_empty), io_mshr_store_empty=int(controls.misses_empty),
                      io_force_write=int(controls.force_write),
                      io_csrCtrl_sbuffer_timeout=controls.timeout)
        ports = tuple(port for port, _ in cycle.enqueues)
        if ports != tuple(sorted(set(ports))) or any(port not in (0, 1) for port in ports):
            raise ValueError('enqueue ports must be unique, increasing and in [0, 1]')
        for port, request in cycle.enqueues:
            if not isinstance(request, Enq):
                raise TypeError('enqueue requires an Enq transaction')
            for name, value, width in (('lane', request.lane, 2), ('mask', request.mask, 16),
                                       ('data', request.data, 128)):
                if not isinstance(value, int) or not 0 <= value < (1 << width):
                    raise ValueError(f'enqueue {name} does not fit {width} bits')
            if request.ptag < 0 or request.vtag < 0:
                raise ValueError('enqueue tags must be unsigned')
            if request.wline and request.data != 0:
                raise ValueError('parent wline is only legal for zero data')
            values[f'io_in_req_{port}_valid'] = 1
            for name, value in dict(addr=request.addr, vaddr=request.vaddr, mask=request.mask,
                                    data=request.data, wline=int(request.wline)).items():
                values[f'io_in_req_{port}_bits_{name}'] = value
        for kind, slot in (('main_pipe_hit', cycle.hit), ('replay', cycle.replay)):
            if slot is not None:
                if not isinstance(slot, int) or not 0 <= slot < 16:
                    raise ValueError('response slot must be in [0, 15]')
                values[f'io_dcache_{kind}_resp_valid'] = 1
                values[f'io_dcache_{kind}_resp_bits_id'] = slot
        if cycle.hit is not None and cycle.hit == cycle.replay:
            raise ValueError('one slot cannot hit and replay on the same edge')
        if cycle.forward_s0 is not None:
            lane, address = cycle.forward_s0
            if lane not in range(3):
                raise ValueError('forward load lane must be in [0, 2]')
            values[f'io_forward_{lane}_s0Req_valid'] = 1
            values[f'io_forward_{lane}_s0Req_bits_vaddr'] = address
        if cycle.forward_s1 is not None:
            lane, address, kill = cycle.forward_s1
            if lane not in range(3):
                raise ValueError('forward load lane must be in [0, 2]')
            values[f'io_forward_{lane}_s1Req_paddr'] = address
            values[f'io_forward_{lane}_s1Kill'] = int(kill)
        for name, value in values.items():
            width = max(1, int(self.inputs[name].mWidth))
            if not isinstance(value, int) or not 0 <= value < (1 << width):
                raise ValueError(f'{name} does not fit {width} bits: {value!r}')
        return values

    def request(self):
        if not self.value(self.dut.io_dcache_req_valid):
            return None
        return Request(*(self.value(getattr(self.dut, 'io_dcache_req_bits_' + name))
                         for name in ('id', 'addr', 'vaddr', 'mask', 'data')))

    def capture(self, event):
        offered = []
        for port in range(2):
            if self.value(getattr(self.dut, f'io_in_req_{port}_valid')):
                fields = {name: self.value(getattr(self.dut, f'io_in_req_{port}_bits_{name}'))
                          for name in ('addr', 'vaddr', 'mask', 'data', 'wline')}
                request = Enq(fields['addr'] >> 6, fields['vaddr'] >> 6,
                              (fields['addr'] >> 4) & 3, fields['mask'], fields['data'],
                              bool(fields['wline']))
                assert (fields['addr'], fields['vaddr']) == (request.addr, request.vaddr), (
                    'enqueue address binding/encoding mismatch', fields)
                offered.append((port, request, bool(self.value(getattr(self.dut, f'io_in_req_{port}_ready')))))
        request = self.request()
        def response(kind):
            return (self.value(getattr(self.dut, f'io_dcache_{kind}_resp_bits_id'))
                    if self.value(getattr(self.dut, f'io_dcache_{kind}_resp_valid')) else None)
        return Observation(bool(self.value(self.dut.reset)), tuple(offered), request,
                           request is not None and bool(self.value(self.dut.io_dcache_req_ready)),
                           response('main_pipe_hit'), response('replay'))

    def status(self):
        self.dut.RefreshComb()
        return Status(*(bool(self.value(getattr(self.dut, name))) for name in
                        ('io_sbempty', 'io_sbFull', 'io_dcache_req_valid', 'io_flush_empty')),
                      tuple(bool(self.value(getattr(self.dut, f'io_in_req_{port}_ready')))
                            for port in range(2)))

    def forward(self, lane):
        def read(field):
            return self.value(getattr(self.dut, f'io_forward_{lane}_s2Resp_{field}'))
        assert read('valid') == 1, 'forward response missing at s2'
        return ForwardResult(sum(read(f'bits_forwardMask_{byte}') << byte for byte in range(16)),
                             tuple(read(f'bits_forwardData_{byte}') for byte in range(16)),
                             bool(read('bits_matchInvalid')))
