"""Source lifetime and task disposition, not predictor state or clock phases."""
from dataclasses import dataclass

MODES=('valid-old-late','flushed-before-prepare','flushed-before-launch','changed-before-launch',
       'reset-before-prepare','reset-before-launch','cancel-before-launch','defer-then-accept')
FATAL=('flushed-before-launch','changed-before-launch','reset-before-launch')


@dataclass(frozen=True)
class Program:
    mode:str

    def __post_init__(self):
        if type(self.mode) is not str or self.mode not in MODES:raise ValueError('declared source-lifetime scenario required')

    @property
    def reset(self):return self.mode.startswith('reset-')

    @property
    def terminal_driver(self):return self.mode in FATAL

    @property
    def accepts(self):return 0 if self.terminal_driver else 2 if self.mode=='valid-old-late' else 1

    def state(self):
        return dict(mode=self.mode,expected_accepts=self.accepts,expected_driver_terminal=self.terminal_driver,
            environment_contract_only=True,full_FTQ_reachability_proved=False,physical_enumeration=False)
