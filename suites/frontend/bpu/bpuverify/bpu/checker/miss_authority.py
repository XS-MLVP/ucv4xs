"""Literal public feedback and actual services, not normalized miss payloads."""
from copy import deepcopy
from toffee import Scoreboard
from bpuverify.bpu.checker.main_sibling import MainSiblingChecks


class Checks(MainSiblingChecks):
    def __init__(self,env,program):
        super().__init__(env,program)
        self.board=Scoreboard('bpu.miss-payload-no-learning-authority')
        self.literal_inputs=[]

    def capture_state(self,event,row):
        super().capture_state(event,row)
        if row['training']['valid'] and row['training']['ready']:
            self.check(event.tick,self.env.checker.last_tick,'literal input and independently accepted source share this boundary')
            full=self.env.checker.current_row['complete_training']
            self.literal_inputs.append(dict(tick=event.tick,payload=deepcopy(full)))

    def completed_services(self):
        return sum(map(len,self.written[:2]))==len(self.incoming) and len(self.written[2])==len(self.directions)
