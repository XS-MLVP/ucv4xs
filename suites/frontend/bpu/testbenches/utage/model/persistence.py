"""Semantic write obligations; no queue, mask, physical bank or DUT dependency."""
from dataclasses import dataclass
from copy import deepcopy


@dataclass(frozen=True)
class Version:
    owner: int
    identity: tuple[int, int, int, int]
    counter: int
    phase: str

    def __post_init__(self):
        if type(self.owner) is not int or self.owner < 0 or len(self.identity) != 4:
            raise ValueError('a real original occurrence and complete identity required')
        if any(type(value) is not int or not 0 <= value < limit
               for value, limit in zip(self.identity, (2, 512, 1 << 15, 16), strict=True)):
            raise ValueError('complete logical identity is out of bounds')
        if type(self.counter) is not int or not 0 <= self.counter < 8 or not self.phase:
            raise ValueError('a defined semantic counter and phase required')

    @property
    def entry(self):
        _, _, tag, position = self.identity
        return dict(valid=1, tag=tag, position=position, counter=self.counter)


class PersistenceLedger:
    """Acceptance, learned versions and persistence are separate facts."""
    def __init__(self):
        self.sources = {}
        self.feedback = []
        self.published = []
        self.persisted = {}
        self.services = []

    def source(self, version, payload):
        if version.owner in self.sources:
            raise AssertionError('an original occurrence cannot be rebound')
        self.sources[version.owner] = (version, deepcopy(payload))

    def accept(self, payload, tick):
        ordinal = len(self.feedback)
        if ordinal >= len(self.sources):
            raise AssertionError('unexpected or duplicate public learning')
        owner, (version, original) = tuple(self.sources.items())[ordinal]
        if payload != original or tick <= owner:
            raise AssertionError('feedback must retain its complete original payload and age')
        if self.feedback and tick <= self.feedback[-1]['tick']:
            raise AssertionError('distinct learning occurrences need distinct ordered acceptances')
        self.feedback.append(dict(owner=owner, tick=tick))

    def publish(self, table, index, entry, tick):
        ordinal = len(self.published)
        if ordinal >= len(self.feedback):
            raise AssertionError('a version needs its prior actual public input')
        owner = self.feedback[ordinal]['owner']
        version = self.sources[owner][0]
        if (table, index, entry) != (version.identity[0], version.identity[1], version.entry):
            raise AssertionError(f'learned version belongs to wrong source: expected {version}, actual {(table,index,entry)}')
        if tick <= self.feedback[ordinal]['tick']:
            raise AssertionError('learning cannot precede its own accepted input')
        self.published.append(dict(version=version, tick=tick))

    def service(self, table, index, entry, tick):
        matches = [(ordinal, row) for ordinal, row in enumerate(self.published)
            if row['version'].identity[:2] == (table, index) and row['version'].entry == entry and row['tick'] <= tick]
        if not matches:
            raise AssertionError('persistent service cannot invent a learned version')
        ordinal, row = matches[-1]
        previous = self.persisted.get((table, index), -1)
        if ordinal < previous:
            raise AssertionError('an older service cannot roll back a later learned version')
        self.persisted[table, index] = ordinal
        self.services.append(dict(ordinal=ordinal, owner=row['version'].owner, tick=tick,
                                  table=table, index=index, entry=entry))

    def finish_phase(self, owners, *, persistent):
        owners = tuple(owners)
        accepted = {row['owner'] for row in self.feedback}
        published = {row['version'].owner for row in self.published}
        if not set(owners) <= accepted or not set(owners) <= published:
            raise AssertionError('every declared original needs both acceptance and actual version write')
        if persistent:
            for owner in owners:
                version = self.sources[owner][0]
                ordinal = next(i for i, row in enumerate(self.published) if row['version'].owner == owner)
                if self.persisted.get(version.identity[:2], -1) != ordinal:
                    raise AssertionError(f'latest learning is not actually persistent for original {owner}')
