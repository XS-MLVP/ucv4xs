"""Behavior coverage for each pipe instance."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import State
from .specs import Spec
from .types import Beat


class Coverage:
    def __init__(self, spec: Spec):
        self.group = CoverGroupDef(spec.group.replace('.', '_') + '_contract_v1', (
            CoverPointDef('occupancy', {'empty': Bin.values('empty'), 'full': Bin.values('full')}),
            CoverPointDef('input_fire', {'no': Bin.values('no'), 'yes': Bin.values('yes')}),
            CoverPointDef('out_ready', {'no': Bin.values('no'), 'yes': Bin.values('yes')}),
            CoverPointDef('right_fire', {'no': Bin.values('no'), 'yes': Bin.values('yes')}),
            CoverPointDef('flush', {'no': Bin.values('no'), 'yes': Bin.values('yes')}),
            CoverPointDef('resolution', {name: Bin.values(name) for name in (
                'empty', 'capture', 'hold', 'consume', 'replace', 'flush')}),
        )).instantiate(spec.group, contract='single-slot decoupled pipe/v1')

    def sample(self, state: State, beat: Beat):
        ready = bool(beat.out_ready or not state.valid)
        fire = bool(beat.in_valid and ready)
        if beat.is_flush:
            resolution = 'flush'
        elif fire and beat.right_out_fire:
            resolution = 'replace'
        elif fire:
            resolution = 'capture'
        elif state.valid and beat.right_out_fire:
            resolution = 'consume'
        elif state.valid:
            resolution = 'hold'
        else:
            resolution = 'empty'
        self.group.sample({
            'occupancy': 'full' if state.valid else 'empty',
            'input_fire': 'yes' if fire else 'no',
            'out_ready': 'yes' if beat.out_ready else 'no',
            'right_fire': 'yes' if beat.right_out_fire else 'no',
            'flush': 'yes' if beat.is_flush else 'no',
            'resolution': resolution,
        })
