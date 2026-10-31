"""Original-input ownership around the existing single FTQ train cache.

Metadata is a transport snapshot, not predictor golden state. This model owns
no SDK handles, clock or queue. Existing predictor models still judge effects.
"""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback
from suites.frontend.bpu.bpu.model.window_lifetime import freeze


def wire_payload(transaction):
    if type(transaction) is not BpuBatchTraining:
        raise TypeError('an original BPU batch training transaction is required')
    branches=transaction.branches
    if type(branches) is not tuple or not 1<=len(branches)<=8:
        raise ValueError('one immutable batch with one to eight slots required')
    active=[b for b in branches if b is not None]
    if not active or any(type(b) is not BpuBranchFeedback for b in active):
        raise ValueError('at least one semantic branch outcome required')
    if len({b.position for b in active})!=len(active) or sum(bool(b.mispredict) for b in active)>1:
        raise ValueError('positions must be unique with at most one first misprediction')
    if type(transaction.pc) is not int or not 0<=transaction.pc<1<<49:
        raise ValueError('unguarded halfword start PC required')
    for b in active:
        for value,width in ((b.position,4),(b.target,49),(b.branch_type,2),
                            (b.ras_action,2),(b.taken,1),(b.mispredict,1)):
            if type(value) is not int or not 0<=value<1<<width:
                raise ValueError('branch outcome outside the current semantic port contract')
    slots=branches+(None,)*(8-len(branches))
    return dict(meta=transaction.resolve_meta,
        start_pcs=tuple((dict(addr=transaction.pc),dict(addr=(transaction.pc+8)&~7)) for _ in range(3)),
        branches=tuple(dict(valid=int(b is not None),bits=dict(
            target_addr=0 if b is None else b.target,taken=0 if b is None else b.taken,
            cfiPosition=0 if b is None else b.position,
            attribute=dict(branchType=0 if b is None else b.branch_type,rasAction=0 if b is None else b.ras_action),
            mispredict=0 if b is None else b.mispredict)) for b in slots))


@dataclass(slots=True)
class PreparedInput:
    source:object
    transaction:BpuBatchTraining
    teaching:object
    payload:object
    launched:bool=False


class FeedbackGate:
    def __init__(self, ledger):
        self.ledger=ledger
        self.reset()

    def reset(self):
        self.originals={}
        self.pending=None
        self.launches=self.accepts=0

    def remember(self, source, metadata):
        self.ledger.known(source)
        if source.sequence in self.originals:
            self.ledger.fail('complete original metadata was already published',source)
        self.originals[source.sequence]=freeze(metadata)

    def prepare(self, source, transaction, *, receipt_metadata):
        self.ledger.known(source)
        if self.pending is not None:
            self.ledger.fail('single original training cache still occupied',source)
        original=self.originals.get(source.sequence)
        if original is None:
            self.ledger.fail('complete original metadata not published',source)
        payload=wire_payload(transaction)
        for field,expected,actual in (
                ('start PC',source.pc,transaction.pc),
                ('receipt metadata',original,freeze(receipt_metadata)),
                ('transaction metadata',original,freeze(transaction.resolve_meta))):
            if expected!=actual:
                self.ledger.fail('original '+field+' changed before launch',source,expected=expected,actual=actual)
        teaching=self.ledger.qualify(self.ledger.resolve(source,payload))
        self.pending=PreparedInput(source,transaction,teaching,freeze(payload))
        return self.pending

    def admit(self, transaction):
        pending=self.pending
        if pending is None or pending.transaction is not transaction:
            self.ledger.fail('driver launch lacks the exact prepared transaction',None)
        if pending.launched:
            self.ledger.fail('prepared transaction already launched once',pending.source)
        self.ledger.known(pending.source)
        if self.ledger.cached is not pending.teaching:
            self.ledger.fail('original teaching was invalidated before driver launch',pending.source)
        actual=freeze(wire_payload(transaction))
        if pending.payload!=actual:
            self.ledger.fail('prepared full payload changed before driver launch',pending.source,
                expected=pending.payload,actual=actual)
        pending.launched=True
        self.launches+=1
        return True

    def accept(self, actual_payload, *, projection):
        pending=self.pending
        if pending is None or not pending.launched:
            self.ledger.fail('actual input has no launched original teaching',None)
        self.ledger.accept(pending.teaching,metadata=projection,payload=actual_payload)
        self.pending=None
        self.accepts+=1
        return pending

    def cancel_unlaunched(self):
        pending=self.pending
        if pending is not None:
            if pending.launched:
                self.ledger.fail('cannot silently cancel an already launched input',pending.source)
            if self.ledger.cached is pending.teaching:self.ledger.cached=None
            self.pending=None
