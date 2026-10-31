"""Four-bank single-port SRAM contract from reset and predicted shadow output.

No observed RAM contents, ready, resetDone, writeSuccess or read data enter the
model. A write-mode RAM output is undefined, not silently treated as held data.
"""
from copy import deepcopy


def zero_data():
    return dict(data_valid=0, tag=0, position=0, counter=0)


def pack_data(data):
    return data['data_valid'] << 16 | data['tag'] << 8 | data['position'] << 4 | data['counter'] << 1


class SramReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.memory = [None] * 512
        self.reset_active = True
        self.reset_set = 0
        self.read_addresses = [None] * 4
        self.read_bank = None
        self.conflict = False
        self.write_bank = None

    @property
    def reset_done(self):
        return int(not self.reset_active)

    def controls(self, read_index, write):
        read_bank, write_bank = read_index % 4, write['index'] % 4
        data = {key: write[key] for key in zero_data()}
        result = []
        for bank in range(4):
            read_valid = int(bank == read_bank)
            write_valid = int(bool(write['valid'] and bank == write_bank
                and (read_bank != bank or write['force'])))
            ren = int(bool(read_valid and not self.reset_active and not write_valid))
            wen = int(bool(write_valid or self.reset_active))
            result.append(dict(read_valid=read_valid, read_set=read_index // 4,
                write_valid=write_valid, write_set=write['index'] // 4, write_data=data,
                reset_active=int(self.reset_active), reset_set=self.reset_set,
                reset_done=self.reset_done, ren=ren, wen=wen,
                array=dict(address=self.reset_set if self.reset_active else
                    write['index'] // 4 if wen else read_index // 4,
                    enable=int(bool(ren or wen)), write=wen,
                    data=0 if self.reset_active else pack_data(data))))
        return result

    def response(self, shadow):
        if shadow['hit']:
            return {key: shadow[key] for key in zero_data()}
        if self.read_bank is None:
            return zero_data()
        address = self.read_addresses[self.read_bank]
        data = None if address is None else self.memory[address]
        if self.conflict and self.write_bank == self.read_bank:
            # SRAM raw data are undefined on a write-mode response. The table
            # nevertheless promises a deterministic invalid bit on conflict.
            return dict(data_valid=0)
        return None if data is None else deepcopy(data)

    def bank_response(self, bank):
        address = self.read_addresses[bank]
        return None if address is None else self.memory[address]

    def advance(self, read_index, write, *, reset=False):
        if type(read_index) is not int or read_index not in range(512):
            raise ValueError('nine-bit read index required')
        if set(write) != {'valid', 'index', 'force', 'data_valid', 'tag', 'position', 'counter'}:
            raise ValueError('complete predicted shadow write required')
        controls = self.controls(read_index, write)
        if reset:
            self.reset()
            return dict(kind='reset')
        old_reset = self.reset_active
        for bank, request in enumerate(controls):
            if request['wen']:
                address = request['array']['address'] * 4 + bank
                self.memory[address] = zero_data() if old_reset else deepcopy(request['write_data'])
                self.read_addresses[bank] = None  # raw rdata are X in write mode
            elif request['ren']:
                self.read_addresses[bank] = read_index
        if old_reset:
            self.reset_active = self.reset_set != 127
            self.reset_set = (self.reset_set + 1) % 128
        self.read_bank = read_index % 4
        self.write_bank = write['index'] % 4
        self.conflict = bool(write['valid'] and write['force'])
        return dict(kind='reset_clear' if old_reset else 'cycle', read_index=read_index,
            write_success=int(any(request['write_valid'] for request in controls)),
            forced_conflict=int(bool(write['valid'] and write['force'] and read_index % 4 == write['index'] % 4)))
