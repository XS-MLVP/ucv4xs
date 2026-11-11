"""Incremental reset-derived validation with an explicit atomic commit."""
from __future__ import annotations


class CoverageReplay:
    """Keep model state and counters, not the complete sampled frame history.

    The validator returns a summary and uncommitted counts. Validation and
    commit are separate so a scenario can validate all collectors and its
    requirements before publishing any credit.
    """

    def __init__(self, validator, commit):
        self._validator = validator
        self._commit = commit
        self._counts = self.summary = None
        self._closed = self._committed = False
        self._failure = None
        next(validator)

    def observe(self, frame):
        if self._failure is not None:
            raise self._failure
        if self._closed:
            raise RuntimeError('coverage replay is closed')
        try:
            self._validator.send(frame)
        except BaseException as error:
            self._failure = error
            self._closed = True
            raise

    def validate(self, *, passed):
        if self._failure is not None:
            raise self._failure
        if self._closed:
            raise RuntimeError('coverage replay is closed')
        if passed is not True:
            self.abort()
            raise ValueError('coverage requires a successful checked scenario')
        try:
            self._validator.send(None)
        except StopIteration as result:
            self.summary, self._counts = result.value
            self._closed = True
            return self.summary
        except BaseException as error:
            self._failure = error
            self._closed = True
            raise
        raise RuntimeError('coverage validator did not finish')

    def commit(self):
        if self._failure is not None:
            raise self._failure
        if self.summary is None or self._committed:
            raise RuntimeError('coverage commit requires one successful validation')
        self._commit(self._counts)
        self._committed = True
        self._counts = None
        return self.summary

    def finish(self, *, passed):
        self.validate(passed=passed)
        return self.commit()

    def abort(self):
        self._validator.close()
        self._closed = True
        self._counts = self.summary = None
