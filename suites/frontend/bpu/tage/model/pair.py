"""Independent state reference for an already allocated highest two tables pair.

This models the eight-table DefaultConfig, not allocation, hashing, stale
metadata, useful aging, or a complete TAGE reference. No observed counter seeds
or updates the model. Physical ways are frozen at the earlier real allocations.
"""
from suites.frontend.bpu.models.configuration import TAGE_TABLES
from dataclasses import dataclass
from dataclasses import replace
from operator import index


@dataclass(frozen=True, slots=True)
class TageTableState:
    hit_mask: int
    counter: int
    useful: int


class TagePairModel:
    def __init__(self, direction, *, alternate_way, provider_way):
        direction, alternate_way, provider_way = map(index, (direction, alternate_way, provider_way))
        if direction not in (0, 1) or alternate_way not in (0, 1) or provider_way not in (0, 1):
            raise ValueError('pair direction and physical ways must be two-state bits')
        self.direction = direction
        self.alternate = TageTableState(1 << alternate_way, 6 if direction else 1, 3)
        self.provider = TageTableState(1 << provider_way, 3 if direction else 4, 0)
        self.selectors = (16, 16)  # weak positive five-bit useAltOnNa, by altConf

    @property
    def tables(self):
        return (None,) * (TAGE_TABLES - 2) + (self.alternate, self.provider)

    @property
    def metadata(self):
        alt_conf = int(self.alternate.counter not in (3, 4))
        use_provider = int(not (self.provider.counter in (3, 4) and self.selectors[alt_conf] >= 16))
        return {'hasProvider': 1, 'hasAlt': 1, 'providerTableIdx': TAGE_TABLES - 1,
                'providerWayIdx': self.provider.hit_mask.bit_length()-1,
                'providerTakenCtr_value': self.provider.counter,
                'providerUsefulCtr_value': self.provider.useful,
                'altOrBasePred': int(self.alternate.counter >= 4),
                'altConf': alt_conf, 'useProvider': use_provider}

    @property
    def taken(self):
        meta = self.metadata
        return int((self.provider if meta['useProvider'] else self.alternate).counter >= 4)

    def apply(self, actual, *, qualified=True):
        actual, qualified = index(actual), index(qualified)
        if actual not in (0, 1) or qualified not in (0, 1):
            raise ValueError('outcome and qualification must be two-state bits')
        if not qualified:
            return
        before = self.metadata
        provider_pred, alternate_pred = int(self.provider.counter >= 4), int(self.alternate.counter >= 4)
        step = 1 if actual else -1
        if self.provider.counter in (3, 4) and provider_pred != alternate_pred:
            selector = list(self.selectors)
            conf = before['altConf']
            selector[conf] = max(0, min(31, selector[conf] + (1 if alternate_pred == actual else -1)))
            self.selectors = tuple(selector)
        self.provider = replace(self.provider,
                                counter=max(0, min(7, self.provider.counter+step)),
                                useful=min(3, self.provider.useful + int(provider_pred == actual and provider_pred != alternate_pred)))
        if not before['useProvider']:
            self.alternate = replace(self.alternate, counter=max(0, min(7, self.alternate.counter+step)))
