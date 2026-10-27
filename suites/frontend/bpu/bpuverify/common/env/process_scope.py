"""One generated DUT type per interpreter, including after Finish()."""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys

DOMAINS = ('abtb', 'bpu', 'ittage', 'mbtb', 'ras', 'sc', 'tage', 'ubtb', 'uras', 'utage')
SCOPES = ('pure', *DOMAINS)
PACKAGE = re.compile(r'^kunminghu_v3_pytest_([a-z]+)_\d+(?:\.|$)')


class DutProcessScope:
    def __init__(self, expected=None):
        if expected is not None and expected not in SCOPES:
            raise ValueError(f'unknown process DUT scope: {expected!r}')
        self.expected, self.owner, self.claims = expected, None, 0

    def claim(self, name):
        if name not in DOMAINS:
            raise ValueError(f'unknown DUT: {name!r}')
        if self.expected is not None and self.expected != name:
            raise RuntimeError(f'process scope {self.expected} cannot load DUT {name}')
        if self.owner is not None and self.owner != name:
            raise RuntimeError(f'process already owns DUT {self.owner}; {name} requires a new interpreter')
        self.owner = name
        self.claims += 1

    def observe(self, *, names, maps, dut_root):
        packages = {match.group(1) for name in names if (match := PACKAGE.match(name))}
        base = Path(dut_root).resolve()
        native = set()
        resolved_roots = {name: (base / name).resolve() for name in DOMAINS if (base / name).exists()}
        for line in maps.splitlines():
            fields = line.split(maxsplit=5)
            if len(fields) < 6 or not fields[5].startswith('/'):
                continue
            path = Path(fields[5].removesuffix(' (deleted)'))
            for name, directory in resolved_roots.items():
                if path.is_relative_to(directory):
                    native.add(name)
            if path.is_relative_to(base):
                relative = path.relative_to(base)
                if len(relative.parts) > 1 and relative.parts[0] in DOMAINS:
                    native.add(relative.parts[0])
        seen = packages | native
        allowed = self.expected if self.expected is not None else self.owner
        if seen and (allowed not in seen or seen != {allowed}):
            raise RuntimeError(f'process scope {allowed}: loaded DUTs {sorted(seen)}')
        return dict(packages=sorted(packages), native_mappings=sorted(native),
                    owner=self.owner, claims=self.claims)


_PROCESS = None


def process_scope():
    global _PROCESS
    if _PROCESS is None:
        _PROCESS = DutProcessScope(os.environ.get('BPUVERIFY_DUT_SCOPE'))
    return _PROCESS


def observe_process(root):
    return process_scope().observe(names=tuple(sys.modules), maps=Path('/proc/self/maps').read_text(),
                                   dut_root=Path(root) / 'dut')
