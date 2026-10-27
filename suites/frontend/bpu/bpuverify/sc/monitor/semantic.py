"""Decode public SC cut-point events; no debug index or SRAM reads."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.common.model.folded_history import PHR_FOLD_LAYOUT
from bpuverify.sc.bundle.values import _plain
from bpuverify.sc.model.semantic import Context, Events
from bpuverify.sc.transaction.types import ScBaseBranch, ScBatchTraining, ScBranchFeedback


def context_value(row):
    return Context(row.path_history[PHR_FOLD_LAYOUT.index((8, 7))].foldedHist.as_int(),
                   row.global_history.as_int(), row.backward.as_int(), row.loop.as_int(),
                   bool(row.common_hr_valid.as_int()))


def decode_events(row):
    lookup, train = row.lookup, row.train
    feedback = None
    if row.train_valid.as_int():
        entries = [entry for bank in train.mbtb_meta for entry in bank]
        branches = []
        for branch in train.branches:
            if not branch.valid.as_int():
                branches.append(None)
                continue
            position, kind = branch.position.as_int(), branch.branch_type.as_int()
            hits = [i for i, entry in enumerate(entries) if entry.rawHit.as_int()
                    and entry.position.as_int() == position
                    and entry.attribute.branchType.as_int() == kind]
            branches.append(ScBranchFeedback(position, branch.taken.as_int(),
                prediction_slot=min(hits) if hits else 0, mbtb_hit=int(bool(hits)), branch_type=kind))
        if any(branch is not None for branch in branches):
            feedback = ScBatchTraining(train.start_pc.as_int(), _plain(train.sc_meta), tuple(branches))
    bases = tuple(ScBaseBranch(entry.bits.cfiPosition.as_int(), provider.bits_value.as_int(),
                    provider.valid.as_int(), entry.valid.as_int(), entry.bits.attribute.branchType.as_int())
                  for entry, provider in zip(lookup.mbtb_result, lookup.provider_counters, strict=True))
    return Events(pc=lookup.start_pc.as_int() if lookup.s0_fire.as_int() else None,
                  context=context_value(lookup), advance=bool(lookup.s1_fire.as_int()),
                  select=bool(lookup.s2_fire.as_int()), branches=bases, feedback=feedback,
                  feedback_context=context_value(train), enabled=bool(row.enabled.as_int()),
                  ready=bool(row.ready.as_int()), reset=bool(row.reset.as_int()))


class ScSemanticMonitor:
    def __init__(self, dut, ports):
        self.clock = dut.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.control.bits.enable,
            ready=ports.status.bits.reset_done, lookup=ports.lookup.bits,
            train_valid=ports.training.valid, train=ports.training.bits).compile_sampler()
        self.outputs = ports.prediction.bits.compile_sampler()
        self.launched = Events(enabled=False, ready=False)
        self.subscriptions = []
        self.execution = None

    def start(self, execution, checker):
        self.execution = execution

        def inputs(event):
            launched = decode_events(self.inputs())
            # RiseWrite exposes the pending launch, not preceding evaluated
            # inputs. This detail belongs in the adapter, never in test cases.
            checker.capture_input(event, self.launched)
            self.launched = launched

        def outputs(event):
            checker.capture_output(event, _plain(self.outputs().meta))

        async def delivered(_):
            pass

        for trigger, capture in ((DriveStable(self.clock), inputs), (RisingEdge(self.clock), outputs)):
            spec = on(trigger, delivery='lossless', capacity=64, capture=capture)(delivered)
            self.subscriptions.append(execution.subscribe(spec.bind()))
        return self

    async def aclose(self):
        for subscription in self.subscriptions:
            self.execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        self.subscriptions.clear()
