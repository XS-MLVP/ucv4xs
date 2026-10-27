"""Compare complete public input transport in addition to existing semantics."""
from toffee import Bundle
from bpuverify.bpu.bundle.pipeline import pipeline_binding
from bpuverify.common.bundle.bindings import PortBinding


def full_input_binding(agent, **options):
    binding=pipeline_binding(agent,**options)
    return PortBinding(binding.clock,Bundle(inputs=binding.bits.inputs,observed=binding.bits.observed,
        complete_metadata=agent.ports.meta.bits.resolve,
        complete_training=agent.ports.training.bits),'bpu.original-feedback-transport')


