"""Reset-scheduled SRAM sweep, independent of returned data and native state.

The macro array has no reset pin.  The wrapper holds its sweep counter at row
zero while reset is asserted, then visits one row on each main-clock edge.
Control commitment is rise-write: reset seen at the preceding rising sample is
the control consumed at this edge.  Neither ready nor a matching payload chooses
the row to clear.
"""


class SramInitialization:
    def __init__(self, sets):
        self.sets = sets
        self.index = None
        self.previous_reset = 0
        self.uid = self.epoch = 0

    def begin(self, uid, epoch):
        self.uid, self.epoch, self.index = uid, epoch, 0

    def edge(self, reset):
        if reset or self.previous_reset:
            self.index = 0
        index = self.index
        if index is not None and not reset and not self.previous_reset:
            self.index = index + 1 if index + 1 < self.sets else None
        self.previous_reset = reset
        return index
