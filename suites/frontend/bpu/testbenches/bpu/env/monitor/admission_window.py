"""One declared set of actual S1 admissions, closed by existing control driver.

Pre-edge candidacy only schedules closure. A following independently compared
rising acceptance is required; candidacy never constitutes a receipt itself.
"""
import asyncio
from dataclasses import dataclass


@dataclass(slots=True)
class Window:
    pc:int
    quota:int
    prepared:object
    accepted:object
    receipts:list
    requires_preparation:bool=True


class AdmissionWindow:
    def __init__(self):self.current=None

    def arm(self,pc,quota,*,available,requires_preparation=True):
        if self.current is not None:raise RuntimeError('one owned prediction window at a time')
        if type(pc) is not int or pc<0 or type(quota) is not int or quota<1:
            raise ValueError('nonnegative PC and positive actual-admission quota required')
        if quota>available:raise ValueError('prediction quota exceeds remaining logical-window capacity')
        loop=asyncio.get_running_loop()
        self.current=Window(pc,quota,loop.create_future(),loop.create_future(),[],requires_preparation)
        return self.current

    def candidate(self,event,row):
        window=self.current
        if window is None or not window.requires_preparation or window.prepared.done() or row['reset']:return
        if (row['fire'] and not row['flush'] and row['pc']==window.pc
                and len(window.receipts)==window.quota-1):window.prepared.set_result(event)

    def capture(self,event,cycle):
        window=self.current
        if window is None or not cycle.fires[1] or cycle.flushes[0]:return
        token=cycle.tokens[0]
        if token.pc!=window.pc:raise AssertionError('unexpected PC accepted inside an owned prediction window')
        if len(window.receipts)>=window.quota:raise AssertionError('prediction control accepted beyond its declared quota')
        window.receipts.append((event.tick,token.sequence))
        if len(window.receipts)==window.quota:
            if window.requires_preparation and (not window.prepared.done() or event.tick!=window.prepared.result().tick+1):
                raise AssertionError('actual final admission lacks its exact pre-edge closure candidate')
            window.accepted.set_result(event)

    def finish(self,window,event):
        if self.current is not window or not window.accepted.done() or window.accepted.result() is not event:
            raise AssertionError('owned window needs the exact accepting event returned by its driver')
        if len(window.receipts)!=window.quota:raise AssertionError('incomplete actual-admission quota')
        self.current=None
        return tuple(window.receipts)

    def cancel(self,window):
        if self.current is window:
            for future in (window.prepared,window.accepted):
                if not future.done():future.cancel()
            self.current=None
