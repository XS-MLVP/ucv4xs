"""All40 inputs and257 real outputs, plus the proven slot31 cross constant."""
from toffee import Bundle

from suites.frontend.ifu.model.boundary import BoundaryInput, BoundaryOutput, SLOTS

from .types import Interface


INPUTS = {
    'block0_size': ('io_req_fetchBlock_0_size', 6),
    'taken_valid': ('io_req_fetchBlock_0_takenCfiOffset_valid', 1),
    'taken_offset': ('io_req_fetchBlock_0_takenCfiOffset_bits', 5),
    'block1_valid': ('io_req_fetchBlock_1_valid', 1),
    'first_instr_is_half_rvi': ('io_req_firstInstrIsHalfRvi', 1),
    'total_end_pos': ('io_req_totalEndPos', 5),
    'maybe_rvc': ('io_req_ifuData_maybeRvcMap', SLOTS),
    'block_sel': ('io_req_ifuData_blockSel', SLOTS),
}
VECTORS = {
    'valid': ('io_resp_rawInstrVec_{}_valid', 1),
    'is_rvc': ('io_resp_rawInstrVec_{}_isRvc', 1),
    'is_cross_block': ('io_resp_rawInstrVec_{}_isCrossBlockInstr', 1),
    'instr_end_mask': ('io_resp_instrEndMask_{}', 1),
    'start_offset': ('io_resp_rawInstrVec_{}_startOffset', 5),
    'end_offset': ('io_resp_rawInstrVec_{}_endOffset', 5),
    'block_sel': ('io_resp_rawInstrVec_{}_blockSel', 1),
    'index': ('io_resp_rawInstrVec_{}_index', 5),
}
SCALARS = {'first_end_is_half_rvi': 'io_resp_firstEndIsHalfRvi',
           'total_end_is_half_rvi': 'io_resp_totalEndIsHalfRvi'}


class BoundaryPorts:
    interface = Interface()

    def __init__(self, dut):
        def bind(name, width, *, output=False):
            signal = getattr(dut, name)
            if max(1, int(signal.mWidth)) != width:
                raise ValueError(f'{name}: expected native width {width}, got {signal.mWidth}')
            if ((output and not signal.IsOutIO())
                    or (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f'{name}: wrong native port direction')
            return signal

        self.bits = Bundle(**{field: bind(name, width) for field, (name, width) in INPUTS.items()},
            index=tuple(bind(f'io_req_ifuData_index_{slot}', 5) for slot in range(SLOTS)))
        self._outputs = Bundle(**{
            field: tuple(bind(pattern.format(slot), width, output=True)
                         for slot in range(SLOTS - (field == 'is_cross_block')))
            for field, (pattern, width) in VECTORS.items()
        }, **{field: bind(name, 1, output=True) for field, name in SCALARS.items()})
        pruned = 'io_resp_rawInstrVec_31_isCrossBlockInstr'
        if hasattr(dut, pruned):
            raise ValueError(f'{pruned}: proven pruned constant now exists; migrate explicitly')
        actual = {name for name, signal in vars(dut).items()
                  if name != 'dut' and callable(getattr(signal, 'IsInIO', None))
                  and signal.IsInIO() and not signal.IsOutIO()}
        expected = {name for name, _ in INPUTS.values()} | {
            f'io_req_ifuData_index_{slot}' for slot in range(SLOTS)}
        if actual != expected:
            raise ValueError(f'InstrBoundary input ownership mismatch: {actual ^ expected}')

    @staticmethod
    def encode(request):
        if not isinstance(request, BoundaryInput):
            raise TypeError('InstrBoundary requires a semantic BoundaryInput')
        return {field: getattr(request, field) for field in INPUTS} | {'index': request.index}

    def capture(self, event):
        snapshot = self._outputs.sample()
        values = {field: tuple(int(value) for value in snapshot[field]) for field in VECTORS}
        values['is_cross_block'] += (0,)  # Absence checked above; independent proof in tests.
        values.update((field, int(snapshot[field])) for field in SCALARS)
        return BoundaryOutput(**values)
