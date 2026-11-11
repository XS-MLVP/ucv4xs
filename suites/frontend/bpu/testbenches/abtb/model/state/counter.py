"""Counter/PLRU reference derived only from accepted public feedback."""
from copy import deepcopy


TRANSITIONS = ('inc0_1', 'inc1_2', 'inc2_3', 'inc3_3',
               'dec3_2', 'dec2_1', 'dec1_0', 'dec0_0')


def index(bank, set_index, way):
    if not 0 <= bank < 4 or not 0 <= set_index < 64 or not 0 <= way < 4:
        raise ValueError((bank, set_index, way))
    return bank * 256 + set_index * 4 + way


def coordinates(cell):
    return cell // 256, (cell % 256) // 4, cell % 4


def touch(state, way):
    child = way // 2
    return (state & ~(4 | (1 << child))) | ((1 - child) << 2) | ((1 - way % 2) << child)


def victim(state):
    pair = state >> 2
    return 2 * pair + ((state >> pair) & 1)


class CounterReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.cells = [0] * 1024
        self.plru = [[0] * 64 for _ in range(4)]
        self.pending1 = None
        self.pending2 = None

    def advance(self, *, reset, accepted, writes):
        if reset:
            self.reset()
            return []
        next_cells = self.cells[:]
        next_plru = [row[:] for row in self.plru]
        transitions = {}
        if self.pending1 is not None:
            tx = self.pending1
            for bank in range(4):
                if not tx['meta']['bankMask'] & (1 << bank):
                    continue
                s = tx['meta']['setIdx']
                for way, entry in enumerate(tx['meta']['entries']):
                    if not entry['hit'] or entry['attribute']['branchType'] != 1:
                        continue
                    old = self.cells[index(bank, s, way)]
                    operation = None
                    if not tx['taken'] or entry['position'] < tx['position']:
                        new, operation = max(0, old - 1), 'dec'
                    elif entry['position'] == tx['position']:
                        new, operation = min(3, old + 1), 'inc'
                    if operation is not None:
                        cell = index(bank, s, way)
                        next_cells[cell] = new
                        transitions[cell] = dict(bank=bank,set_index=s,way=way,
                            before=old,after=new,transition=f'{operation}{old}_{new}',
                            feedback=deepcopy(tx))
        if self.pending2 is not None and self.pending2['taken']:
            tx = self.pending2
            matching = [way for way, entry in enumerate(tx['meta']['entries'])
                if entry['hit'] and entry['position'] == tx['position']
                and entry['attribute'] == dict(branchType=tx['branch_type'],rasAction=tx['ras_action'])]
            for bank in range(4):
                if tx['meta']['bankMask'] & (1 << bank):
                    s = tx['meta']['setIdx']
                    value = self.plru[bank][s]
                    for way in matching:
                        value = touch(value, way)
                    next_plru[bank][s] = value
        for write in writes:
            bank,s,way = write['bank'],write['set_index'],write['way']
            next_plru[bank][s] = touch(self.plru[bank][s],way)
            if write['reset_counter']:
                cell = index(bank,s,way)
                next_cells[cell] = 2
                transitions[cell] = dict(bank=bank,set_index=s,way=way,
                    before=self.cells[cell],after=2,transition='reset',feedback=None)
        self.cells, self.plru = next_cells, next_plru
        self.pending2, self.pending1 = self.pending1, deepcopy(accepted)
        return list(transitions.values())
