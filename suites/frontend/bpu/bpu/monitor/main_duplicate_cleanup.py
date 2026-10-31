"""Compact actual receipts prove distinct learning lifetimes overlapped."""
from copy import deepcopy


class PreparationReceipts:
    def __init__(self,pipeline):
        self.pipeline=pipeline;self.offers=[];self.services=[[],[],[]]

    def raise_failure(self):self.pipeline.raise_failure()

    def capture_state(self,event,row):
        for owner,port in enumerate(row['incoming']):
            if port['valid']:self.offers.append(dict(tick=event.tick,owner=owner,bits=deepcopy(port['bits'])))

    def write_accepted(self,owner,transfer):
        self.services[owner].append(dict(tick=transfer.accepted_tick,bits=deepcopy(transfer.value)))

    def state(self):return deepcopy(dict(offers=self.offers,services=self.services))
