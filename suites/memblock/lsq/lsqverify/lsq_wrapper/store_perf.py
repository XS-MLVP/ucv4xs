"""Store events inferred from public producer/consumer history, six-edge output.

PSQ, StoreQueue and LsqWrapper each register perf twice without reset. The
physical event span ends at the LATER address/data-ready pointer, not at the
virtual allocation tail and not at the earlier fully-ready pointer.
"""
from lsqverify.deq.model import serial
from lsqverify.psq.model import before


class StorePerfHistory:
    def __init__(self):
        self.pipeline = [None] * 6

    def expected(self):
        sample = self.pipeline[-1]
        return {} if sample is None else {f"io_perf_{27 + lane}_value": event for lane, event in enumerate(sample["events"])}

    def advance(self, physical, inp):
        _, head, _, deq, _, _ = physical.state(inp)
        pins, _ = physical.deq.expected(deq)
        address, data = (0, 0) if inp.reset else (physical.address_ready, physical.data_ready)
        # Normal pointers share the current physical window; scalar distances
        # preserve both SQ flags, including the 64/128/256 transitions.
        address_span, data_span = (address - head) % 256, (data - head) % 256
        later = data if before(address, data) else address
        physical_span = (later - head) % 256
        virtual_span = (serial(inp.enqueue) - head) % 256
        memory = deq.stores[0].memory_type
        events = (
            pins["io_toRob_mmioBusy"],
            int(bool(pins["io_toUncacheBuffer_req_valid"] and inp.uncache_ready and not pins["io_toUncacheBuffer_req_bits_nc"])),
            int(bool(pins["io_writeBack_valid"] and inp.writeback_ready and memory & 2)),
            int(bool(pins["io_writeBack_valid"] and not inp.writeback_ready and memory & 2)),
            int(physical_span < 16), int(16 < physical_span <= 32),
            int(32 < physical_span <= 48), int(physical_span > 48),
            int(virtual_span < 32), int(32 < virtual_span <= 64),
            int(64 < virtual_span <= 96), int(virtual_span > 96),
        )
        sample = dict(events=events, head=head, address_span=address_span, data_span=data_span,
                      physical_span=physical_span, virtual_span=virtual_span)
        self.pipeline = [sample] + self.pipeline[:-1]
        return sample
