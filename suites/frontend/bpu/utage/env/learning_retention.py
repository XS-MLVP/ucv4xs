"""Driver/monitor support for learning without subsequent own relearning."""
from contextlib import asynccontextmanager
from copy import deepcopy

from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.checker.learning_retention import LearningRetentionChecks
from suites.frontend.bpu.utage.coverage.working_set import WorkingSetCoverage
from suites.frontend.bpu.utage.env.working_set import working_set_env
from suites.frontend.bpu.utage.model.working_set import PC, POSITION, PHASES
from suites.frontend.bpu.utage.monitor.learning_retention import LearningRetentionMonitor
from suites.frontend.bpu.utage.transaction.types import UtageTraining


class LearningRetentionEnv:
    def __init__(self, base, shadow, coverage):
        self.base, self.shadow = base, shadow
        self.checks = LearningRetentionChecks(base, coverage)
        self.retained, self.turnover = self.checks.retained, self.checks.turnover

    async def prepare(self):
        self.checks.stage = 'normal-32-identity-admission'
        await self.base.prepare()
        await self.base.phase(PHASES[0])
        self.checks.initialize()

    async def learn(self, histories, label):
        self.checks.stage = label
        histories, transfers, predictions = await self.base.read(histories, 0)
        self.checks.predictions(histories, transfers, predictions)
        transactions = tuple(UtageTraining(PC, POSITION, 1, deepcopy(prediction.meta),
            mispredict=1 - self.checks.states[history].taken)
            for history, prediction in zip(histories, predictions, strict=True))
        payloads = tuple(UtageUsefulChecker._payload(transaction) for transaction in transactions)
        before = len(self.base.monitor.accepted_feedback)
        await self.base.send(transactions, label)
        receipts = tuple(self.base.monitor.accepted_feedback[before:])
        self.checks.accepted_learning(histories, transfers, receipts, payloads, label=label,
                                      actual_values=self.base.monitor._actual)

    async def consume(self, histories, label):
        self.checks.stage = label
        histories, transfers, predictions = await self.base.read(histories, 0)
        self.checks.consumed(histories, transfers, predictions, label=label)

    def confirm_turnover(self):
        self.checks.confirm_turnover(self.shadow.latest)

    def finish(self):
        self.checks.finish()


@asynccontextmanager
async def learning_retention_env(agent, program, coverage):
    shadow = LearningRetentionMonitor(agent)
    shadow.start(agent._execution, observer=shadow.observe)
    lifetime = None
    try:
        async with working_set_env(agent, program, WorkingSetCoverage(program)) as base:
            lifetime = LearningRetentionEnv(base, shadow, coverage)
            yield lifetime
    except BaseException as error:
        coverage.evidence = {} if lifetime is None else lifetime.checks.summary()
        coverage.evidence.update(status='FAIL', error_type=type(error).__name__,
            expected=getattr(error, 'expected', None), actual=getattr(error, 'actual', None),
            observed_tick=getattr(getattr(getattr(error, 'context', None), 'observed_event', None), 'tick', None))
        raise
    else:
        coverage.evidence = dict(lifetime.checks.summary(), status='PASS', error_type=None,
                                 expected=None, actual=None, observed_tick=None)
    finally:
        await shadow.aclose()
