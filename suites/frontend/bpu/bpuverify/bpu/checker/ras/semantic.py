"""An independently owned program stack at the integrated RAS cut point."""
from collections import Counter, deque

from toffee import CheckContext, Scoreboard, ScoreboardMode

from bpuverify.ras.checker.semantic import RasSemanticChecker, projection


class RasSemanticComponentChecker(RasSemanticChecker):
    def __init__(self,*,coverage=None,return_pc=None):
        super().__init__()
        self.board = Scoreboard('bpu.ras.semantic-component')
        self.counts = Counter()
        self.boundary_coverage,self.return_pc = coverage,return_pc
        self.expected = deque(maxlen=128)
        self.last_actual = None

    def capture_input(self,event,events,*,consumer):
        if self.failure is not None:
            return
        try:
            if self.initialized and not events.reset and events.enabled and events.action==1:
                witness = consumer['valid'] and consumer['taken'] and (self.return_pc is None or consumer['pc']==self.return_pc)
                if witness and self.boundary_coverage is not None:
                    self.boundary_coverage.record('reached','return-target-owned',event.tick)
                self.board.check(expected=(1,1,self.model.projection['top'],self.return_pc if self.return_pc is not None else consumer['pc']),
                    actual=(consumer['valid'],consumer['taken'],consumer['target'],consumer['pc']),
                    context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=event.tick,
                        request=dict(point='owned RAS return consumed by S3',events=events,state=self.model.state()),
                        observed_event=event))
                self.counts['return-consumers'] += 1
                if witness and self.boundary_coverage is not None:
                    self.boundary_coverage.record('checked','return-target-owned',event.tick)
            super().capture_input(event,events)
            if self.failure is None and not events.reset and events.recovery is not None and events.enabled:
                self.counts['recoveries'] += 1
            if self.failure is None and self.boundary_coverage is not None:
                self.boundary_coverage.accept(events,self.model,event.tick)
        except Exception as error:
            self.failure = error

    def capture_output(self,event,actual,*,retained=None,consumer=None):
        super().capture_output(event,actual,retained=retained)
        if self.failure is not None or not self.initialized:
            return
        try:
            self.expected.append((event.tick,dict(self.model.projection),bool(self.events.enabled),consumer))
            self.last_actual = (actual,retained,event.tick)
            if self.boundary_coverage is not None:
                self.boundary_coverage.consume(event.tick,self.model)
        except Exception as error:
            self.failure = error

    def source_expected(self,source):
        """Coherent S3 source phase only; never search nearby same-PC frames."""
        self.raise_failure()
        try:
            context = CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=source.meta_tick,
                request=dict(point='public RAS metadata from owned source',source=source,state=self.model.state()))
            matches = [row for row in self.expected if row[0]==source.meta_tick]
            self.board.check(expected=1,actual=len(matches),context=context)
            _,wanted,enabled,consumer = matches[0]
            self.board.check(expected=(True,1,source.meta.perf.start_pc),
                actual=(enabled,consumer['valid'],consumer['pc']),context=context)
            meta = source.meta.redirect['ras']
            # FTQ redirectMeta exports the checkpoint, not the top address.
            # The latter is checked separately at the component and consumer.
            self.board.check(expected={key:wanted[key] for key in ('group','repeat','calls')},
                actual=dict(group=meta['ssp'],repeat=meta['sctr'],
                calls=16*meta['tosw']['flag']+meta['tosw']['value']),context=context)
            return dict(ssp=wanted['group'],tosw=dict(flag=wanted['calls']//16,value=wanted['calls']%16))
        except Exception as error:
            self.failure = error
            raise

    def check_survivors(self,*,calls,returns,return_pc):
        self.raise_failure()
        try:
            self._check_survivors(calls=calls,returns=returns,return_pc=return_pc)
        except Exception as error:
            self.failure = error
            raise

    def owned_program(self,source):
        """Only an exact, independently compared S3 source names a program."""
        self.source_expected(source)
        _,wanted,_,_=next(row for row in self.expected if row[0]==source.meta_tick)
        key=wanted['group'],wanted['calls'],wanted['repeat']
        program=self.model.checkpoints.get(key)
        if program is None:
            raise AssertionError(f'public source has no independently owned program: {key}')
        return program

    def _check_survivors(self,*,calls,returns,return_pc):
        actual,retained,tick = self.last_actual
        context = CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=tick,
            request=dict(point='closed-form surviving repeated frames',calls=calls,returns=returns,state=self.model.state()))
        wanted = dict(top=return_pc,group=1,repeat=calls-returns-1,calls=calls)
        if self.boundary_coverage is not None and self.model.retirements==calls+returns:
            self.boundary_coverage.record('reached','surviving-frame-intact',tick)
        self.board.check(expected=wanted,actual=projection(actual),context=context)
        self.board.check(expected=(1,return_pc,calls-returns-1,calls+returns,None),
            actual=(retained['head'],retained['cells'][1]['address'],retained['cells'][1]['counter'],
                    self.model.retirements,self.model.pending_retirement),context=context)
        if self.boundary_coverage is not None:
            self.boundary_coverage.record('checked','surviving-frame-intact',tick)

    def finish(self):
        self.raise_failure()
        if not self.initialized or not self.model.retirements or not self.counts['return-consumers']:
            raise AssertionError('RAS composition needs reset, genuine retirement and return consumption')
        if self.boundary_coverage is not None:
            self.boundary_coverage.finish()
