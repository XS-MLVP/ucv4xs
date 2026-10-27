"""Read-only status binding; DUT-specific selectors live beside each DUT's ports."""
import re

from toffee import Bundle
from icacheverify.common.bundle.bindings import PortBinding
from icacheverify.common.env.memory_direct import memory_signal, memory_signal_names


def bind_activity(dut, hierarchy, groups, *, name):
    prefix = '.' + hierarchy + '.'
    available = {key.split(prefix, 1)[1]: key for key in memory_signal_names(dut) if prefix in key}
    labels, fields = {}, {}
    for group, patterns in groups.items():
        selected = set()
        for pattern in patterns:
            matches = {key for key in available if re.fullmatch(pattern, key)}
            if not matches:
                raise RuntimeError(f'{name}.{group}: required status pattern {pattern!r} is absent; '
                                   'update the RTL contract, do not fall back to a delay')
            selected.update(matches)
        labels[group] = tuple(sorted(selected))
        fields[group] = tuple(memory_signal(dut, available[key].split('.', 1)[1])
                              for key in labels[group])
    return PortBinding(dut.clock, Bundle(**fields), name), labels
