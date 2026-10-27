"""Compare complete accepted inputs with their original owners."""
from bpuverify.bpu.checker.window_lifetime import WindowPipelineChecker
from bpuverify.bpu.model.feedback_gate import FeedbackGate


class FeedbackChecker(WindowPipelineChecker):
    def __init__(self, *, sources, capacity, simultaneous_training_recovery=False):
        super().__init__(sources=sources,capacity=capacity)
        if type(simultaneous_training_recovery) is not bool:
            raise TypeError('same-boundary input contract must be an explicit bool')
        self.simultaneous_training_recovery=simultaneous_training_recovery
        self.gate=FeedbackGate(self.windows.ledger)
        self.actual_inputs=[]
        self.current_row=None

    def capture(self, row, event):
        self.current_row=row
        super().capture(row,event)
        if self.failure is not None or self.last_tick!=event.tick:return
        try:
            if row['inputs']['reset']:
                self.gate.reset();self.actual_inputs.clear();return
            if self.last_cycle.metadata is not None and self.last_events.redirect is None:
                self.gate.remember(self.windows.owner(self.last_cycle.metadata),row['complete_metadata'])
        except Exception as error:self.failure=error

    def _accepted_origin(self, training, event):
        token=super()._accepted_origin(training,event)
        if self.current_row['inputs']['redirect']['valid'] and not self.simultaneous_training_recovery:
            raise NotImplementedError('this bounded feedback scope serializes external recovery and training acceptance')
        pending=self.gate.accept(self.current_row['complete_training'],
            projection=dict(history=training['history'],main=training['main']))
        if pending.source is not self.windows.owner(token):
            raise AssertionError('accepted training changed its exact logical source')
        self.actual_inputs.append(dict(tick=event.tick,source=token.sequence,pc=token.pc,
            complete_metadata_and_all_payload_fields_compared=True))
        return token
