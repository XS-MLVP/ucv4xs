"""SbufferData binding, bounded encoding, immutable whole-array sampling."""
from toffee import Bundle

from suites.memblock.sbuffer.testbenches.sbuffer_data.model import BYTES
from suites.memblock.sbuffer.testbenches.sbuffer_data.model import LANES
from suites.memblock.sbuffer.testbenches.sbuffer_data.model import LINES
from suites.memblock.sbuffer.testbenches.sbuffer_data.transactions import Frame
from suites.memblock.sbuffer.testbenches.sbuffer_data.transactions import Snapshot


class SbufferDataPorts:
    def __init__(self, dut):
        names = ['reset', 'io_maskFlushReq_0_valid', 'io_maskFlushReq_0_bits_wvec']
        for port in range(2):
            names.append(f'io_writeReq_{port}_valid')
            names.extend(f'io_writeReq_{port}_bits_{field}'
                         for field in ('wvec', 'mask', 'data', 'vwordOffset', 'wline'))
        self.inputs = {name: getattr(dut, name) for name in names}
        self.bits = Bundle(**self.inputs)
        self.masks = tuple(tuple(tuple(getattr(dut, f'io_maskOut_{line}_{lane}_{byte}')
                                       for byte in range(BYTES)) for lane in range(LANES))
                           for line in range(LINES))
        self.data = tuple(tuple(tuple(getattr(dut, f'io_dataOut_{line}_{lane}_{byte}')
                                      for byte in range(BYTES)) for lane in range(LANES))
                          for line in range(LINES))

    def encode(self, frame: Frame):
        values = dict.fromkeys(self.inputs, 0)
        values['reset'] = int(frame.reset)
        for port, request in frame.op.active():
            values[f'io_writeReq_{port}_valid'] = int(frame.writes_valid)
            for name, value in dict(wvec=request.wvec, mask=request.mask, data=request.data,
                                    vwordOffset=request.vword_offset, wline=int(request.wline)).items():
                values[f'io_writeReq_{port}_bits_{name}'] = value
        if frame.op.flush is not None:
            values['io_maskFlushReq_0_valid'] = int(frame.flush_valid)
            values['io_maskFlushReq_0_bits_wvec'] = frame.op.flush
        for name, value in values.items():
            width = max(1, int(self.inputs[name].mWidth))
            if not isinstance(value, int) or not 0 <= value < (1 << width):
                raise ValueError(f'{name} does not fit {width} bits: {value!r}')
        return values

    def capture(self, event):
        return Snapshot(
            tuple(tuple(sum(int(bit.value) << byte for byte, bit in enumerate(lane))
                        for lane in line) for line in self.masks),
            tuple(tuple(tuple(int(byte.value) for byte in lane) for lane in line) for line in self.data),
        )
