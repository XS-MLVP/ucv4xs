"""Compare complete public input transport in addition to existing semantics."""
from toffee import Bundle
from suites.frontend.bpu.testbenches.bpu.env.bundle.pipeline import pipeline_binding
from suites.frontend.bpu.testbenches.shared.env.bundle.bindings import PortBinding


def full_input_binding(agent, **options):
    binding=pipeline_binding(agent,**options)
    return PortBinding(binding.clock,Bundle(inputs=binding.bits.inputs,observed=binding.bits.observed,
        complete_metadata=agent.ports.meta.bits.resolve,
        complete_training=agent.ports.training.bits),'bpu.original-feedback-transport')


