"""Capture a real loop, then resolve selected original sources while held."""
from bpuverify.bpu.env.ahead_working_set import AheadWorkingSetEnv
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.transaction.types import BpuBranchFeedback


class AheadCorrectionEnv(AheadWorkingSetEnv):
    async def direction_round(self, goal, ordinal):
        self.checks.begin(0, f'prepare-direction-{goal}-{ordinal}')
        edges = self.program.edges(0)
        await self.agent.set_ready(prediction=True, meta=True)
        boundary = self.checker.current_event.tick
        captured = []
        for edge in edges:
            source = await self.agent.next_transaction(start_pc=edge.pc, after_tick=boundary,
                                                       limit=4*len(edges))
            self.checker.source_token(source)
            captured.append((edge, source))
            # Selection is by S1 acceptance. Using the later S3 metadata tick
            # would discard already-overlapping next branch requests and
            # accidentally wait for another whole program iteration.
            boundary = source.prediction_tick
        await self.pause()
        before = len(self.checks.feedback_receipts)
        for edge, source in captured:
            if edge.pc not in self.program.selected: continue
            token = self.checker.source_token(source)
            matching = tuple(entry for row in source_entries(token.lookup) for entry in row
                             if entry.hit and entry.position == edge.position and entry.kind == 1)
            self.checks.check(1, len(matching), 'correction belongs to a genuinely resident original conditional')
            counter = 2-ordinal if goal == 0 else ordinal
            self.checks.check(counter, matching[0].counter, 'fresh Main source has independent previous direction')
            taken = goal != 0
            event = await self.resolve(source, BpuBranchFeedback(edge.position, edge.target, edge.kind,
                taken=int(taken), mispredict=int((counter >= 2) != taken)), retire=False)
            self.checks.accepted(source, event, edge, taken=taken)
            self.checker.retire_source(source.meta_tick)
        count = len(self.checks.feedback_receipts)-before
        self.checks.check(len(self.program.selected), count, 'all and only declared selected branches corrected')
        self.checks.rounds.append(dict(goal=goal, ordinal=ordinal, actual_feedback=count,
            first_capture_tick=captured[0][1].meta_tick, last_capture_tick=captured[-1][1].meta_tick,
            first_prediction_tick=captured[0][1].prediction_tick,
            last_prediction_tick=captured[-1][1].prediction_tick))
        # The final INDIRECT was not among the corrected sources. Its fresh
        # owned checkpoint survives all feedback while prediction was held;
        # never recover using a loop-old conditional checkpoint.
        edge, source = captured[-1]
        self.source = await self.recover(source, edge)
