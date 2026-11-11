"""One restored-history ITTAGE context, driven only by accepted feedback.

The allocation proposal is a real public metadata input (the LFSR is not
replicated). Never seed table contents or expected counters from DUT state.
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Entry:
    target: int
    counter: int = 2
    useful: int = 0


class IttageContextModel:
    def __init__(self, table_count=3):
        self.table_count, self.entries = table_count, {}

    def metadata(self):
        ordered = sorted(self.entries, reverse=True)
        result = dict(provider={'valid': int(bool(ordered))},
                      altProvider={'valid': int(len(ordered) > 1)})
        if not ordered:
            return result
        provider = self.entries[ordered[0]]
        result['provider']['bits'] = ordered[0]
        result.update(providerCnt_value=provider.counter, providerTarget_addr=provider.target,
                      providerUsefulCnt_value=provider.useful)
        if len(ordered) > 1:
            alternate = self.entries[ordered[1]]
            result['altProvider']['bits'] = ordered[1]
            result.update(altProviderCnt_value=alternate.counter,
                          altProviderTarget_addr=alternate.target,
                          altDiffers=int(provider.target != alternate.target))
        return result

    def target(self):
        ordered = sorted(self.entries, reverse=True)
        if not ordered:
            return None
        provider = self.entries[ordered[0]]
        return self.entries[ordered[1]].target if provider.counter == 0 and len(ordered) > 1 else provider.target

    def advance(self, proposal, target, *, mispredict):
        """Return operations; commit coverage only after observed comparison."""
        ordered = sorted(self.entries, reverse=True)
        operations = set()
        provider = self.entries[ordered[0]] if ordered else None
        alternate = self.entries[ordered[1]] if len(ordered) > 1 else None
        allocate = mispredict and not (provider and provider.target == target and provider.counter == 0)
        table = None
        if allocate and proposal['valid']:
            table = proposal['bits']
            if type(table) is not int or not 0 <= table < self.table_count or (
                    ordered and table <= ordered[0]) or table in self.entries:
                raise ValueError(f'illegal public allocation proposal {proposal}; resident={ordered}')
        if provider is not None:
            correct = provider.target == target
            counter = min(3, provider.counter + 1) if correct else max(0, provider.counter - 1)
            operations.add(('increment' if provider.counter < 3 else 'high_hold') if correct else (
                'decrement' if provider.counter else 'low_hold'))
            useful = provider.useful if alternate is None or provider.target == alternate.target else int(correct)
            self.entries[ordered[0]] = Entry(target if provider.counter == 0 else provider.target, counter, useful)
            if provider.counter == 0:
                operations.add('zero_confidence_target_write')
            if alternate is not None:
                operations.add('provider_and_alternate')
                if provider.counter == 0:
                    operations.add('alternate_selected')
                    if mispredict:
                        self.entries[ordered[1]] = replace(alternate,
                            counter=max(0, alternate.counter - 1),
                            target=target if alternate.counter == 0 else alternate.target)
                        operations.add('alternate_penalty')
        if table is not None:
            self.entries[table] = Entry(target)
            operations.add('allocate')
        return operations
