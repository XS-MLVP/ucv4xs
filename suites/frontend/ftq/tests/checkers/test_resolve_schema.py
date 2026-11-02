"""Independent DefaultConfig physical ABI rejection controls, no RTL credit."""
from types import SimpleNamespace

import pytest

from suites.frontend.ftq.resolve_queue.bundle.ports import ResolveQueuePorts
from suites.frontend.ftq.resolve_queue.transaction.cycle import ResolveInput

pytestmark = pytest.mark.selftest


class Signal:
    def __init__(self, width, output=False):
        self.width, self.output = width, output

    def W(self):
        return self.width

    def IsInIO(self):
        return not self.output

    def IsOutIO(self):
        return self.output


class Schema:
    def __init__(self):
        self.inputs = dict(clock=Signal(1), reset=Signal(1), io_bpuTrain_ready=Signal(1),
                           io_backendRedirect=Signal(1), io_backendRedirectPtr_flag=Signal(1),
                           io_backendRedirectPtr_value=Signal(6), io_bpuEnqueue=Signal(1),
                           io_bpuEnqueuePtr_value=Signal(6))
        for prefix in (*(f'io_backendResolve_{lane}_' for lane in range(3)), 'io_ifuResolve_'):
            for name, width in dict(valid=1, bits_ftqIdx_flag=1, bits_ftqIdx_value=6,
                bits_ftqOffset=5, bits_pc_addr=49, bits_target_addr=49, bits_taken=1,
                bits_mispredict=1, bits_attribute_branchType=2, bits_attribute_rasAction=2).items():
                self.inputs[prefix + name] = Signal(width)
        self.outputs = {f'io_bpuTrain_{name}': Signal(width, True) for name, width in
            dict(valid=1, bits_ftqIdx_flag=1, bits_ftqIdx_value=6, bits_startPc_addr=49).items()}
        for slot in range(8):
            for name, width in dict(valid=1, bits_target_addr=49, bits_taken=1, bits_cfiPosition=5,
                bits_attribute_branchType=2, bits_attribute_rasAction=2, bits_mispredict=1).items():
                self.outputs[f'io_bpuTrain_bits_branches_{slot}_{name}'] = Signal(width, True)
        self.refresh()

    def refresh(self):
        self.dut = SimpleNamespace(**self.inputs, **self.outputs)
        self._inputs = {name: signal for name, signal in self.inputs.items() if name != 'clock'}

    def input_names(self):
        return tuple(self._inputs)

    def output_names(self):
        return frozenset(self.outputs)

    def input(self, name):
        return self._inputs[name]


@pytest.mark.parametrize('name,width,output', (
    ('clock', 2, False), ('reset', 2, False), ('io_bpuTrain_ready', 2, False),
    ('io_backendResolve_0_valid', 1, True), ('io_backendResolve_2_bits_pc_addr', 50, False),
    ('io_ifuResolve_bits_target_addr', 50, False), ('io_backendRedirectPtr_flag', 2, False),
    ('io_bpuEnqueuePtr_value', 7, False), ('io_bpuTrain_bits_branches_7_bits_cfiPosition', 4, True),
    ('io_bpuTrain_bits_ftqIdx_flag', 1, False),
))
def test_incorrect_physical_width_or_direction_fails_before_driver_claim(name, width, output):
    schema = Schema()
    fields = schema.inputs if name in schema.inputs else schema.outputs
    fields[name] = Signal(width, output)
    schema.refresh()
    with pytest.raises(ValueError, match='expected'):
        ResolveQueuePorts.bind(schema)


@pytest.mark.parametrize('kind', ('missing-input', 'extra-input', 'missing-output', 'extra-output'))
def test_unknown_or_missing_field_is_not_a_silent_zero_or_new_dce(kind):
    schema = Schema()
    if kind == 'missing-input':
        del schema.inputs['io_ifuResolve_bits_pc_addr']
    elif kind == 'extra-input':
        schema.inputs['io_bpuEnqueuePtr_flag'] = Signal(1)
    elif kind == 'missing-output':
        del schema.outputs['io_bpuTrain_bits_branches_7_valid']
    else:
        schema.outputs['extra_output'] = Signal(1, True)
    schema.refresh()
    with pytest.raises((KeyError, ValueError)):
        ResolveQueuePorts.bind(schema)


@pytest.mark.parametrize('changes', (
    dict(backend=(None,)), dict(backend=(None,) * 4), dict(ifu=object()),
    dict(ready=1), dict(reset=1), dict(redirect=(True, 0)), dict(redirect=(0, 64)),
    dict(enqueue=True), dict(enqueue=64), dict(reset=True, enqueue=0),
))
def test_full_slot_cannot_bypass_source_and_control_domains(changes):
    with pytest.raises(ValueError):
        ResolveInput(**changes)
