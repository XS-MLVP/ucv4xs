"""Bounded pipeline observation; the agent retains sole ownership of all drivers."""
import asyncio
from contextlib import suppress

from toffee import Bundle,DriveStable,RisingEdge,on

from suites.frontend.bpu.testbenches.bpu.env.bundle.pipeline import pipeline_binding
from suites.frontend.bpu.testbenches.bpu.env.bundle.values import _plain
from suites.frontend.bpu.testbenches.bpu.checker.pipeline import PipelineChecker
from suites.frontend.bpu.testbenches.bpu.env.bundle.plain_sampler import compile_plain
from suites.frontend.bpu.testbenches.shared.env.wait import wait_condition
from suites.frontend.bpu.testbenches.bpu.model.projection import INTEGRATED_PIPELINE


class PipelineObservation:
    def __init__(self, agent, coverage=None, *, sources=None,with_common_history=False,common_history_state=True,
                 common_history_factory=None,common_history_binding_factory=None,binding_factory=None,
                 checker_factory=None):
        self.agent = agent
        factory = PipelineChecker if checker_factory is None else checker_factory
        self.checker = factory(coverage,sources=sources)
        self.subscription = None
        self.reset_subscription = None
        self.consumed_reset = None
        self.training_accepted = None
        self.training_preedge = None
        self.training_reads = None
        self.common=None
        self.common_history_binding_factory=common_history_binding_factory
        self.binding_factory = pipeline_binding if binding_factory is None else binding_factory
        if with_common_history:
            from suites.frontend.bpu.testbenches.bpu.checker.common_history import CommonHistoryChecks
            factory=CommonHistoryChecks if common_history_factory is None else common_history_factory
            self.common=factory(self.checker,observe_state=common_history_state)

    async def __aenter__(self):
        if self.agent.ports.prediction_target_observable or self.agent.ports.meta_perf_observable:
            raise ValueError('semantic pipeline requires review for the changed public BPU projection')
        self.checker.projection = INTEGRATED_PIPELINE
        options = dict(with_sc=True) if getattr(self.checker.model.sources,'has_own_sc',False) else {}
        if getattr(self.checker.model.sources,'has_own_ras',False):
            options['with_ras'] = True
        binding = self.binding_factory(self.agent,**options,with_tage=getattr(self.checker.model.sources,'has_own_tage',False),
            with_ahead=getattr(self.checker.model.sources,'has_own_ahead',False),
            with_early_direction=getattr(self.checker.model.sources,'has_own_utage',False),
            with_ittage=getattr(self.checker.model.sources,'has_own_ittage',False))
        if self.common is not None:
            from suites.frontend.bpu.testbenches.bpu.env.bundle.common_history import common_history_binding
            factory=common_history_binding if self.common_history_binding_factory is None else self.common_history_binding_factory
            common=factory(self.agent,observe_state=self.common.observe_state)
            sampler=compile_plain(Bundle(pipeline=binding.bits,common=common.bits))
        else:sampler = compile_plain(binding.bits)
        def capture(event):
            sampled=sampler()
            row=sampled if self.common is None else sampled['pipeline']
            row['inputs']['consumed_reset'] = self.consumed_reset
            row['inputs']['training_accepted'] = self.training_accepted
            if self.training_accepted:
                row['inputs']['training'] = self.training_preedge
            if options:
                row['inputs']['training_accepted'] = self.training_accepted
                row['observed']['statistical']['accepted_reads'] = self.training_reads
            self.checker.capture(row, event)
            if self.common is not None:self.common.capture_state(event,sampled['common'])
        async def delivered(_):
            pass
        reset_sampler = compile_plain(Bundle(reset=binding.bits.inputs.reset,
            training=binding.bits.inputs.training,
            **(dict(training_reads=binding.bits.observed.statistical.reads) if options else {})))
        def consumed_reset(_):
            before = reset_sampler()
            self.consumed_reset = bool(before['reset'])
            # All external feedback uses the producer's actual pre-edge beat.
            # Rise-mode cleanup can change valid after the native edge; it
            # must not remove or create an independently owned acceptance.
            self.training_preedge = before['training']
            self.training_accepted = bool(before['training']['valid'] and before['training']['ready'])
            if options:
                self.training_reads = before['training_reads']
        self.reset_subscription = self.agent._execution.subscribe(on(DriveStable(binding.clock),
            capture=consumed_reset,delivery='lossless',capacity=64)(delivered).bind())
        self.subscription = self.agent._execution.subscribe(on(RisingEdge(binding.clock), capture=capture,
            delivery='lossless',capacity=64)(delivered).bind())
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        for subscription in (self.subscription,self.reset_subscription):
            if subscription is None:continue
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):await subscription.task
        if exc_type is None:
            self.checker.finish()
            if self.common is not None:self.common.raise_failure()

    async def wait(self, name, condition, *, timeout_cycles=128):
        def sample():
            self.checker.raise_failure()
            if self.common is not None:self.common.raise_failure()
            return self.checker
        return await wait_condition(self.agent.dut.clock, sample=sample, satisfied=condition,
                                    name='bpu.semantic.'+name, timeout_cycles=timeout_cycles)
