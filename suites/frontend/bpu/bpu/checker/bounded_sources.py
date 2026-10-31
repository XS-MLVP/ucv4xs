"""Account for all actual admissions, not only selected receipts."""
from copy import deepcopy
from suites.frontend.bpu.bpu.checker.feedback_gate import FeedbackChecker
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.monitor.admission_window import AdmissionWindow
from suites.frontend.bpu.bpu.model.main_service import PC


class BoundedChecker(FeedbackChecker):
    def __init__(self, *, capacity=8, simultaneous_training_recovery=False):
        super().__init__(sources=BranchTargetSources(),capacity=capacity,
            simultaneous_training_recovery=simultaneous_training_recovery)
        self.selection=AdmissionWindow()
        self.read_context=[]
        self.first_failure_read=None

    def capture(self,row,event):
        if (not row['inputs']['reset'] and row['observed']['fires'][1]
                and row['read_diagnostic']['pc1']==PC+2):
            self.read_context.append(dict(tick=event.tick,read=deepcopy(row['read_diagnostic'])))
            self.read_context=self.read_context[-2:]
        super().capture(row,event)
        if self.failure is not None and self.first_failure_read is None:
            self.first_failure_read=dict(tick=event.tick,read=deepcopy(row['read_diagnostic']))
        if self.failure is not None or self.last_tick!=event.tick or row['inputs']['reset']:return
        try:self.selection.capture(event,self.last_cycle)
        except Exception as error:self.failure=error


