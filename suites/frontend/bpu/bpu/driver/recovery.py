"""Normal flowing recovery, associated at actual acceptance, not pulse cleanup."""
from asyncio import Future, TaskGroup

from suites.frontend.bpu.bpu.model.early_aging import require_recovery_window
from suites.frontend.bpu.bpu.model.path_history import WIDTH, LAYOUT, SHIFT
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect


class RecoveryDriver:
    def __init__(self, agent, checker):
        self.agent, self.checker = agent, checker

    async def send(self, source, *, position=4, branch_type=3, until=None, target=None, taken=True):
        # Ready and redirect are already owned by the agent's distinct drivers.
        # Flow may proceed while the redirect pulse finishes; serializing ready
        # AFTER pulse cleanup changes which A0/A1 read ancestors are available.
        if type(position) is not int or not 0 <= position < 16:
            raise ValueError('recovery position must be a declared four-bit branch position')
        if type(taken) is not bool:
            raise ValueError('recovery direction must be a semantic bool')
        if until is not None and (not isinstance(until, Future) or until.done()):
            raise ValueError('recovery requires a fresh actual-acceptance future')
        if self.checker.model.stages[1:] != (None, None) or self.checker.model.sources.main_pending():
            raise RuntimeError('flowing recovery must start after old S2/S3 learning is drained')
        token = self.checker.source_token(source)
        require_recovery_window(self.checker.model.history.taken_edges, token.history.taken_edges,
            capacity=WIDTH, history_bits=max(length for length, _ in LAYOUT), shift=SHIFT)
        request = BpuRedirect(token.pc if target is None else target, source.meta.redirect,
            cfi_pc=source.prediction.start_pc+position, taken=int(taken), branch_type=branch_type)
        request.payload()  # Validate before registering an owned input plan.
        self.checker.plan_redirect(source, request)
        checks = self.checker.coverage
        previous = checks.redirect_count
        # Both native drivers launch while the old S2/S3 work is drained.
        # Advancing ready before redirect would create new, then cancelled S3
        # work; advancing it after pulse cleanup loses the original read window.
        async with TaskGroup() as tasks:
            if until is None:
                control = self.agent.set_ready(prediction=True, meta=True)
            else:
                control = self.agent.accept_predictions_until(until,
                    name='bpu.recovery.original_source_accepted', failure=lambda: self.checker.failure)
            tasks.create_task(control)
            tasks.create_task(self.agent.redirect(request))
        self.checker.raise_failure()
        if (checks.redirect_count != previous+1 or checks.last_redirect[1] is not token.history
                or checks.last_redirect[2] is not True):
            raise AssertionError('owned recovery requires one actual acceptance with prediction flow enabled')
        return checks.last_redirect[0]
