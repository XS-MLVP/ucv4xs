"""Bounded, passive scope; the agent retains sole ownership of all drivers."""
import asyncio
from contextlib import suppress

from toffee import Bundle,DriveStable,RisingEdge,on

from bpuverify.bpu.bundle.pipeline import pipeline_binding
from bpuverify.bpu.bundle.values import _plain
from bpuverify.bpu.checker.pipeline import PipelineChecker
from bpuverify.common.env.plain_sampler import compile_plain
from bpuverify.common.env.wait import wait_condition


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
        self.training_reads = None
        self.common=None
        self.common_history_binding_factory=common_history_binding_factory
        self.binding_factory = pipeline_binding if binding_factory is None else binding_factory
        if with_common_history:
            from bpuverify.bpu.checker.common_history import CommonHistoryChecks
            factory=CommonHistoryChecks if common_history_factory is None else common_history_factory
            self.common=factory(self.checker,observe_state=common_history_state)

    async def __aenter__(self):
        options = dict(with_sc=True) if getattr(self.checker.model.sources,'has_own_sc',False) else {}
        if getattr(self.checker.model.sources,'has_own_ras',False):
            options['with_ras'] = True
        binding = self.binding_factory(self.agent,**options,with_tage=getattr(self.checker.model.sources,'has_own_tage',False),
            with_ahead=getattr(self.checker.model.sources,'has_own_ahead',False),
            with_early_direction=getattr(self.checker.model.sources,'has_own_utage',False),
            with_ittage=getattr(self.checker.model.sources,'has_own_ittage',False))
        if self.common is not None:
            from bpuverify.bpu.bundle.common_history import common_history_binding
            factory=common_history_binding if self.common_history_binding_factory is None else self.common_history_binding_factory
            common=factory(self.agent,observe_state=self.common.observe_state)
            sampler=compile_plain(Bundle(pipeline=binding.bits,common=common.bits))
        else:sampler = compile_plain(binding.bits)
        def capture(event):
            sampled=sampler()
            row=sampled if self.common is None else sampled['pipeline']
            if getattr(self.checker.model.sources,'has_own_tage',False) or getattr(self.checker.model.sources,'has_own_ittage',False):
                row['inputs']['consumed_reset'] = self.consumed_reset
            if options:
                row['inputs']['training_accepted'] = self.training_accepted
                row['observed']['statistical']['accepted_reads'] = self.training_reads
            self.checker.capture(row, event)
            if self.common is not None:self.common.capture_state(event,sampled['common'])
        async def delivered(_):
            pass
        if getattr(self.checker.model.sources,'has_own_tage',False) or getattr(self.checker.model.sources,'has_own_ittage',False):
            reset_sampler = Bundle(reset=binding.bits.inputs.reset,
                **(dict(training_valid=binding.bits.inputs.training.valid,
                    training_ready=binding.bits.inputs.training.ready,
                    training_reads=binding.bits.observed.statistical.reads) if options else {})).compile_sampler()
            def consumed_reset(_):
                before = reset_sampler()
                self.consumed_reset = bool(before.reset.as_int())
                if options:
                    # The public producer samples at DriveStable. A Rise-mode
                    # control can change combinational ready *after* the edge;
                    # that is not another acceptance of a held transaction.
                    self.training_accepted = bool(before.training_valid.as_int() and before.training_ready.as_int())
                    self.training_reads = _plain(before.training_reads)
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
