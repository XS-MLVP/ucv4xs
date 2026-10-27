"""Compare actual admission, complete consumers and source-owned learning."""
from copy import deepcopy
from dataclasses import asdict
from toffee import CheckContext, Scoreboard, ScoreboardMode, TransferState

from bpuverify.utage.checker.source_ownership import actual_fields
from bpuverify.utage.model.long_history_learning import (LongHistoryLearning, RULES, PC, POSITION,
                                                       HISTORIES, PHASES, address, expected)


class LongHistoryLearningChecks:
    def __init__(self, mode, coverage):
        self.mode,self.coverage = mode,coverage
        self.ledger = LongHistoryLearning()
        self.board = Scoreboard('utage.long-history-learning')
        self.originals, self.completed, self.witnesses = [],set(),{}
        self.source_batches = []

    def check(self, wanted, actual, point):
        self.board.check(expected=wanted,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(point=point,mode=self.mode,state=self.ledger.state())))

    def reach(self, rule, **witness):
        self.completed.add(rule); self.witnesses[rule] = witness
        self.coverage.record('reached',rule,**witness)

    def response(self, path, prediction, base, *, table=1, counter=None):
        wanted = expected(path,base,table=table,counter=counter)
        self.check(wanted,actual_fields(prediction,wanted),'complete independent '+path+' prediction')
        self.originals.append((prediction,deepcopy(prediction.meta)))

    def capture(self, paths, transfers, predictions):
        self.check((len(paths),len(paths)),(len(transfers),len(predictions)),'every requested path returns once')
        self.check(True,all(t.state is TransferState.COMPLETED for t in transfers),'native query transfers complete')
        self.check(True,all(a.accepted_event.tick < b.accepted_event.tick < a.completed_event.tick
                           for a,b in zip(transfers,transfers[1:])),'actual consecutive queries overlap')
        owners = []
        for path,t,prediction in zip(paths,transfers,predictions,strict=True):
            base = int(path=='a')
            self.check((PC,POSITION,HISTORIES[path],base,PC,HISTORIES[path]),
                       (t.request.pc,t.request.position,t.request.folded_history,t.request.base_taken,
                        t.request.read_pc,t.request.read_history),
                       'actual accepted request keeps its declared path and base')
            self.response(path,prediction,base,counter=self.ledger.states[path].counter)
            owner = t.accepted_event.tick
            self.ledger.capture(owner,path,base); owners.append(owner)
        self.source_batches.append(dict(owners=owners,paths=tuple(paths),
                                        completion_ticks=[t.completed_event.tick for t in transfers]))
        self.reach('actual-overlapping-sources',batches=deepcopy(self.source_batches))
        return tuple(owners)

    def verified_phase(self, rule, batch, receipts, payloads, actual_values, consumers, *, tick, cycle_ticks):
        events,states = self.ledger.preview(batch)
        self.check(PHASES[rule],tuple((e.source.path,e.actual) for e in events),
                   'declared interleaving and semantic guidance, not just the same final totals')
        self.check(len(batch),len(receipts),'every planned original feedback actually accepted')
        self.check(tuple(payloads),tuple(payload for _,payload in receipts),'complete feedback order and contents')
        ticks = [tick for tick,_ in receipts]
        self.check(True,all((b-a==cycle_ticks if self.mode=='adjacent' else b-a>cycle_ticks)
                           for a,b in zip(ticks,ticks[1:])),'actual feedback communication shape')
        self.reach('actual-feedback-cadence',accepted_ticks=ticks,mode=self.mode)
        wanted = dict(short=0,a=states['a'].useful,b=states['b'].useful,cold_short=0,cold_long=0)
        observed = dict(short=actual_values[address('a')[0]],a=actual_values[512+address('a')[1]],
                        b=actual_values[512+address('b')[1]],cold_short=actual_values[address('cold')[0]],
                        cold_long=actual_values[512+address('cold')[1]])
        self.check(wanted,observed,'actual path-owned protection and independent shared/cold identities')
        self.check({'a','b'},set(consumers),'both fresh path consumers are mandatory')
        consumer_witness = {}
        for path,(transfer,prediction) in consumers.items():
            self.check(True,transfer.state is TransferState.COMPLETED and transfer.accepted_event.tick>tick,
                       'fresh actual consumer follows complete learning confirmation')
            fields = expected(path,int(path=='a'),counter=states[path].counter)
            self.check(fields,actual_fields(prediction,fields),'fresh path consumer keeps complete independent direction')
            consumer_witness[path] = dict(accepted_tick=transfer.accepted_event.tick,
                completed_tick=transfer.completed_event.tick,counter=states[path].counter,
                protection=states[path].useful,index=address(path)[1])
        self.ledger.commit(batch)
        self.reach('unique-feedback-once',owners=sorted(self.ledger.consumed))
        witness = dict(accepted_ticks=ticks,actual_confirmation_tick=tick,compared_protection_cells=1024,
                       events=[asdict(event) for event in events],actual_protection=observed,
                       fresh_consumers=consumer_witness)
        self.reach(rule,**witness)
        return states

    def finish(self):
        self.check(10,len(self.ledger.consumed),'ten distinct real sources, never duplicated metadata as a source')
        self.check(tuple(meta for _,meta in self.originals),tuple(p.meta for p,_ in self.originals),
                   'all original actual metadata remain immutable')
        self.reach('immutable-original-sources',predictions=len(self.originals))
        self.check(set(RULES),self.completed,'all declared semantic effects and consumers complete')
        for rule in RULES:
            self.coverage.record('checked',rule,**self.witnesses[rule])
