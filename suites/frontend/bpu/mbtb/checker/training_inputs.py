"""Input-established feedback identity and actual-wire comparison.

IDs belong to the environment, never hardware tags or payload matches. A local
drained terminal says the isolated training work quiesced, not FTQ retirement.
Metadata is a declared upstream input here; genuine lookup ancestry is separate.
"""
from dataclasses import asdict,dataclass,replace
from toffee import Scoreboard,CheckContext,ScoreboardMode
from suites.frontend.bpu.mbtb.driver.feedback import expected_mbtb_feedback
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining
from suites.frontend.bpu.mbtb.transaction.metadata import metadata_origin


@dataclass(frozen=True,slots=True)
class TrainingInput:
    uid:int
    planned_epoch:int
    request:MbtbBatchTraining
    state:str='planned'
    offer_epoch:int|None=None
    offer_tick:int|None=None
    terminal_tick:int|None=None
    cancel_fence:int|None=None


TERMINALS=frozenset(('local-drained','reset-cancelled','reset-filtered',
    'initialization-filtered','disabled-filtered','cancelled-before-offer'))


class TrainingInputs:
    def __init__(self,*,validate_source=None):
        self._next_uid=1;self.epoch=0;self._reset_active=False;self.tick=-1
        self._rows={};self._pending=[];self._declared=[];self._terminals=[]
        self.board=Scoreboard('mbtb.planned-training-input');self.failure=None
        self.validate_source=validate_source
        self._accepted=set()

    @property
    def rows(self):return tuple(self._rows[uid] for uid in self._declared)

    def raise_failure(self):
        if self.failure is not None:raise self.failure

    def fail(self,error):
        if self.failure is None:self.failure=error

    def plan(self,transactions):
        self.raise_failure();transactions=tuple(transactions)
        if not transactions or any(type(tx) is not MbtbBatchTraining for tx in transactions):
            raise ValueError('MainBTB requires a complete validated training input plan')
        if self.validate_source is not None:
            for tx in transactions:self.validate_source(tx)
        result=[]
        for tx in transactions:
            uid=self._next_uid;self._next_uid+=1
            self._rows[uid]=TrainingInput(uid,self.epoch,tx)
            self._pending.append(uid);self._declared.append(uid);result.append(uid)
        return tuple(result)

    def _terminal(self,uid,state,tick):
        row=self._rows[uid]
        if state not in TERMINALS or row.terminal_tick is not None:
            raise AssertionError('MainBTB training requires one declared terminal per input UID')
        self._rows[uid]=replace(row,state=state,terminal_tick=tick)
        self._terminals.append((uid,state,tick))
        self._accepted.discard(uid)

    def observe(self,tick,*,reset,ready,enabled,feedback):
        """tick is the original physical rising edge, not the later model phase."""
        self.raise_failure()
        try:
            if tick<=self.tick:raise AssertionError('nonmonotonic MainBTB training input observation')
            self.tick=tick
            for uid in tuple(self._pending):
                row=self._rows[uid]
                if row.cancel_fence is not None and tick>row.cancel_fence:
                    self._pending.remove(uid);self._terminal(uid,'cancelled-before-offer',tick)
            if reset and not self._reset_active:
                self.epoch+=1
                for uid in tuple(self._accepted):self._terminal(uid,'reset-cancelled',tick)
            self._reset_active=reset
            if feedback is None:return
            if not self._pending:raise AssertionError('MainBTB feedback has no input-established UID')
            uid=self._pending[0];row=self._rows[uid]
            self.board.check(expected=expected_mbtb_feedback(row.request),actual=feedback,
                context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=uid,
                    request=dict(epoch=self.epoch,planned_epoch=row.planned_epoch,input=row.request,
                        physical_offer_tick=tick,metadata_scope='declared-upstream-input')))
            self._pending.pop(0)
            self._rows[uid]=replace(row,state='accepted',offer_epoch=self.epoch,offer_tick=tick)
            self._accepted.add(uid)
            if reset:self._terminal(uid,'reset-filtered',tick)
            elif not ready:self._terminal(uid,'initialization-filtered',tick)
            elif not enabled:self._terminal(uid,'disabled-filtered',tick)
        except Exception as error:
            self.fail(error);raise

    def drained(self,tick,ids):
        self.raise_failure()
        for uid in ids:
            row=self._rows[uid]
            if row.state=='accepted':
                if tick<row.offer_tick:raise AssertionError('MainBTB drain precedes input acceptance')
                self._terminal(uid,'local-drained',tick)
            elif row.state not in TERMINALS:
                raise AssertionError('unoffered MainBTB input is not drained')

    def cancel_inputs(self,ids,*,at):
        # An already occurred physical edge may still await model delivery.
        # It remains accepted; no later edge may invent another cancelled input.
        for uid in ids:
            row=self._rows[uid]
            if row.state=='planned':self._rows[uid]=replace(row,cancel_fence=at)

    def finish(self):
        self.raise_failure()
        assert not self._pending,'unoffered MainBTB input plan remains'
        assert not self._accepted,'accepted MainBTB input has no local terminal'
        assert self._declared==list(range(1,self._next_uid)),'MainBTB declared input UID history changed'
        assert set(self._rows)==set(self._declared),'MainBTB input identity table changed'
        assert len(self._terminals)==len(self._declared),'MainBTB training lacks an exact terminal history'
        assert {uid for uid,_,_ in self._terminals}==set(self._declared),'MainBTB terminal UID history changed'
        for uid,state,tick in self._terminals:
            row=self._rows[uid]
            assert state in TERMINALS and (row.state,row.terminal_tick)==(state,tick),'MainBTB terminal receipt changed'
        return self.rows

    def receipt(self):
        return tuple(dict(uid=row.uid,planned_epoch=row.planned_epoch,offer_epoch=row.offer_epoch,
            offer_tick=row.offer_tick,state=row.state,terminal_tick=row.terminal_tick,
            metadata_scope='verified-isolated-lookup' if metadata_origin(row.request.meta_entries) is not None else 'declared-upstream-input',
            source=None if metadata_origin(row.request.meta_entries) is None else asdict(metadata_origin(row.request.meta_entries)),
            declared_reasons=tuple(sorted({source.declared_reason for bank in row.request.meta_entries
                for source in bank if source.declared_reason is not None}))) for row in self.rows)
