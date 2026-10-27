"""S1-to-S3 metadata registers: derive from captured S1 inputs, never seed S3 state."""
from copy import deepcopy


class MetadataPipeline:
    def __init__(self):
        self.stage2 = self.stage3 = None

    def advance(self, *, reset, fire1, fire2, meta, pc, tick):
        if reset:
            self.stage2 = self.stage3 = None
            return
        old2 = self.stage2
        if fire2:
            self.stage3 = deepcopy(old2)
        if fire1:
            self.stage2 = dict(meta=deepcopy(meta), pc=pc, tick=tick)


def expected_fast_train(parent, token):
    if token is None:
        raise ValueError('valid S3 fastTrain lacks an independently captured S1 token')
    return dict(pc=token['pc'] & ((1 << 49) - 1), target=parent['target'] & ((1 << 49) - 1),
        taken=parent['taken'], position=parent['position'], branch_type=parent['branch_type'],
        ras_action=parent['ras_action'], meta=deepcopy(token['meta']))


def eligible(valid, meta_valid, enabled):
    return bool(valid and meta_valid and enabled)
