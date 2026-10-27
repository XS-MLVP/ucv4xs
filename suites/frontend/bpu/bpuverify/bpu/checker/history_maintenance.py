"""Qualified pressure and public history consumers across global maintenance."""
from hashlib import sha256

from bpuverify.bpu.model.early_aging import FailureLedger,allocation,aged
from bpuverify.bpu.model.history_working_set import MAINTENANCE_RULES


class HistoryMaintenanceChecks:
    def __init__(self, owner):
        self.owner = owner
        self.failures = FailureLedger()
        self.pending = None
        self.receipts,self.consumers = [],{}
        self.decision = self.previous = self.protection = None

    def before(self, row, sources, tick):
        check = self.owner.check
        actual = row['observed']['early_direction']
        control = actual['maintenance']
        learning = sources.short.learning
        self.decision = None if learning is None else allocation(learning.feedback,learning.useful)
        check(self.failures.count,control['low'],'actual maintenance pressure follows qualified original outcomes')
        check((int(learning is not None),int(self.failures.aging),int(self.failures.aging)),
              (control['fire'],*(table['age'] for table in control['tables'])),
              'actual learning and global protection maintenance are separate owned events')
        if self.decision is not None:
            check((int(self.decision.wrong_position is not None),self.decision.mask),
                  (control['need'],control['mask']),'actual allocation qualification matches original guidance')
        if self.pending is not None:
            written,expected,record = self.pending
            check(written+2,tick,'global maintenance has its immediate actual poststate')
            observed = tuple(tuple(values) for values in actual['useful'])
            check(expected,observed,'ALL protection changes follow the shared maintenance prestate')
            record.update(observed_tick=tick,actual_protection_sha256=sha256(bytes(
                value for table in observed for value in table)).hexdigest())
            self.receipts.append(record)
            self.owner.coverage.maintenance('reached','shared-prestate-protection',**record)
            self.pending = None
        self.previous = dict(self.owner.ledger.states) if self.failures.aging else None
        self.protection = (tuple(tuple(table.get(index,0) for index in range(512))
            for table in sources.short.useful) if self.failures.aging else None)

    def after(self, tick, sources):
        if self.previous is not None:
            self.owner.ledger.maintain(self.previous)
            expected = aged(self.protection)
            record = dict(tick=tick,qualified_failures=self.failures.failures,
                histories=len(self.previous),learning_overlap=self.decision is not None,
                expected_protection_sha256=sha256(bytes(value for table in expected for value in table)).hexdigest())
            self.pending = tick,expected,record
            self.owner.coverage.maintenance('reached','qualified-failure-pressure',**record)
        self.failures.apply(self.decision)
        self.owner.check(self.failures.count,sources.short.low_tick,
                         'independent pressure ledger and composed reference remain aligned')

    def record_consumers(self, epoch, consumers):
        check = self.owner.check
        check({False,True},set(consumers),'both learned directions are publicly consumed after maintenance')
        check(True,epoch>0 and epoch<=len(self.receipts),'consumers belong to a confirmed actual maintenance')
        after = self.receipts[epoch-1]['observed_tick']
        check(True,all(record['prediction_tick']>after for record in consumers.values()),
              'maintenance consumers are genuinely fresh, not old equal-looking snapshots')
        check(False,epoch in self.consumers,'one qualified polarity pair per maintenance epoch')
        self.consumers[epoch] = consumers

    def finish(self):
        owner,check = self.owner,self.owner.check
        check(None,self.pending,'every maintenance crossed its actual complete-state comparison')
        check(self.failures.ages,len(self.receipts),'every independently expected maintenance was physically confirmed')
        if owner.program.profile != 'capacity-reverse':
            check(0,self.failures.ages,'turnover control does not silently exercise global protection maintenance')
            return
        check(True,self.failures.ages>0,'capacity plus selective correction really exercised global maintenance')
        check(set(range(1,len(self.receipts)+1)),set(self.consumers),
              'each maintenance has both public polarity consumers')
        last = self.receipts[-1]['observed_tick']
        restored = owner.public_consumers['restored']
        check(True,all(record['prediction_tick']>last for record in restored.values()),
              'all final resident consumers follow the last maintenance')
        for rule in MAINTENANCE_RULES[2:]:
            owner.coverage.maintenance('reached',rule,epochs=len(self.receipts),
                final_public_consumers=len(restored),original_snapshots=len(owner.originals))
        for rule in MAINTENANCE_RULES:
            owner.coverage.maintenance('checked',rule,epochs=len(self.receipts))

    def summary(self):
        return dict(qualified_failures=self.failures.failures,count=self.failures.count,
                    ages=self.failures.ages,confirmed=self.receipts,public_consumers=self.consumers)
