"""Static read-only full counter/recency view composed with public pipeline IO."""
from toffee import Bundle

from bpuverify.bpu.bundle.pipeline import pipeline_binding
from bpuverify.bpu.bundle.main_service import main_service_binding
from bpuverify.bpu.bundle.main_replacement import main_replacement_binding
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names


def working_set_binding(agent, **options):
    binding = pipeline_binding(agent, **options)
    anchor, = [name for name in memory_signal_names(agent.dut) if name.endswith('.abtb.io_enable')]
    prefix = anchor.removeprefix('TOP.').removesuffix('io_enable')
    signal = lambda field: memory_signal(agent.dut, prefix + field)
    parent = lambda field: memory_signal(agent.dut, prefix.removesuffix('abtb.') + field)
    state = Bundle(counters=tuple(signal(f'takenCounter_{bank}_{row}_{way}_value')
        for bank in range(4) for row in range(64) for way in range(4)),
        recency=tuple(signal(f'replacers_{bank}.states.states_{row}') for bank in range(4) for row in range(64)),
        main_service=tuple(main_service_binding(agent, alignment=alignment, bank=bank)[0].bits
                           for alignment in range(2) for bank in range(2)),
        main_response=main_replacement_binding(agent).bits,
        tage_fast=tuple(Bundle(valid=parent(f'tage.io_prediction_fastTakenVec_{slot}_valid'),
            taken=parent(f'tage.io_prediction_fastTakenVec_{slot}_bits')) for slot in range(4)))
    observed = Bundle(**dict(binding.bits.observed), ahead_working_state=state)
    return PortBinding(binding.clock, Bundle(inputs=binding.bits.inputs, observed=observed),
                       'bpu.ahead-working-set')
