"""Small phase summaries, not per-cycle traces or audit logs."""
from contextlib import contextmanager
from time import perf_counter
import json


class CaseTiming:
    def __init__(self):
        self.started = perf_counter()
        self.phases = {}

    @contextmanager
    def phase(self, name):
        started = perf_counter()
        try:
            yield
        finally:
            self.phases[name] = self.phases.get(name, 0.0) + perf_counter() - started

    def save(self, path, *, passed):
        path.write_text(json.dumps(dict(passed=passed, elapsed_seconds=perf_counter() - self.started,
            phases_seconds=self.phases), indent=2) + '\n', encoding='utf-8')
