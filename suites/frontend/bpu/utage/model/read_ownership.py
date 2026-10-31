"""Logical records and immutable query ownership, not physical shadow slots."""
from copy import deepcopy
from dataclasses import dataclass, replace

from suites.frontend.bpu.utage.model.semantic import tag
from suites.frontend.bpu.utage.model.source_ownership import PC, Profile


RETAINED_VERSIONS = 8
RULES = ('distinct-original-records', 'original-feedback-once',
         'actual-inflight-reuse', 'complete-original-response',
         'fresh-records-preserved', 'immutable-original-sources')


@dataclass(frozen=True, slots=True)
class ReadOwnershipProgram:
    original: Profile = Profile('original', PC, 0xA6B, 3)
    learning: Profile = Profile('learning', PC, 0xA7B, 7)
    neighbor: Profile = Profile('cold-neighbor', PC, 0xA8C, None)

    @property
    def reinforcements(self):
        # One A allocation and one B allocation, then the remaining B versions
        # fill the configured retention capacity. These are real feedbacks,
        # not cycle waits or a physical coordinate matrix.
        return RETAINED_VERSIONS - 2

    @property
    def preparation(self):
        return (self.original, replace(self.learning, counter=4), *tuple(
            replace(self.learning, counter=min(7, 5 + index))
            for index in range(self.reinforcements)))

    def query_expected(self):
        return self.original.expected(0, override_history=self.learning.history)

    def state(self):
        return dict(original=self.original, learning=self.learning, neighbor=self.neighbor,
                    retained_versions=RETAINED_VERSIONS, query=self.query_expected())

    def validate(self):
        if len({p.indices[0] for p in (self.original, self.learning, self.neighbor)}) != 3:
            raise ValueError('ownership witnesses require three distinct logical records')
        if self.original.counter != 3 or self.learning.counter != 7:
            raise ValueError('ownership witnesses require discriminating NT3 / T7 records')
        if tag(self.original.pc, self.original.context, 0) == tag(self.learning.pc, self.learning.context, 0):
            raise ValueError('original and learning identities must have distinct tags')
        if self.query_expected()['hit']:
            raise ValueError('the original query must reject the different matching context')


class FeedbackLedger:
    """Each fresh semantic source may teach exactly once; retain source values."""
    def __init__(self):
        self.sources = {}
        self.consumed = set()

    def capture(self, token, record, metadata):
        if token in self.sources:
            raise ValueError('query source identity was captured twice')
        self.sources[token] = (record, deepcopy(metadata))

    def consume(self, token):
        if token not in self.sources or token in self.consumed:
            raise ValueError('feedback requires an unconsumed original query')
        self.consumed.add(token)
        return self.sources[token]
