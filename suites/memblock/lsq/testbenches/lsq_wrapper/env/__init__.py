from dataclasses import asdict
from contextlib import contextmanager
import json

from suites.memblock.lsq.testbenches.lsq_wrapper.env.codec import encode
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Inputs


class WrapperEnv:
    def __init__(self, driver, before, after, model, coverage, journal, checks, actor, nodeid):
        self.driver, self.before, self.after, self.model, self.coverage = driver, before, after, model, coverage
        self.journal, self.checks, self.actor_journal, self.nodeid = journal, checks, actor, nodeid
        self.last_tick, self.pre_observed, self.observed, self.last_change = -1, None, None, None
        self.pre_response = self.response = None
        self._history_checkers = []

    def register_checker(self, checker, *, preserve_core_error=False):
        """Attach an independent history oracle to the existing sampled owner.

        Declarations/expectations remain caller-owned. The oracle has no native
        handle or driver and cannot advance the DUT. Its original request-window
        sampling and full-reference failure precedence are retained.
        """
        if any(item is checker for item, _ in self._history_checkers):
            raise ValueError("history checker already registered")
        self._history_checkers.append((checker, preserve_core_error))

    def unregister_checker(self, checker):
        for index, (registered, _) in enumerate(self._history_checkers):
            if registered is checker:
                del self._history_checkers[index]
                return
        raise ValueError("history checker is not registered")

    @contextmanager
    def checker_scope(self, checker, *, preserve_core_error=False):
        """Observe only this producer's request, including its error window.

        A completed S4 program may be extended by a filler later. It must not
        consume another program's intervening requests on the shared fixture.
        """
        self.register_checker(checker, preserve_core_error=preserve_core_error)
        try:
            yield
        finally:
            self.unregister_checker(checker)

    def _observe_history(self, request, error=None):
        for checker, preserve_error in self._history_checkers:
            if error is None:
                checker.observe(request, self.pre_response, self.response, self.last_tick)
            elif preserve_error:
                checker.core_error = repr(error)
                try:
                    checker.observe(request, self.pre_response, self.response, self.last_tick)
                except BaseException:
                    # The oracle records its separate diagnostic. Never mask
                    # the original strict full-output failure with a new one.
                    pass

    def failure_window(self):
        """Only for the retained diagnostic report schema, never to plan a drive."""
        return {"last_public_before": self.pre_observed, "last_public_after": self.observed}

    def compare(self, actual, expected, masks, phase):
        difference = {pin: [actual[pin], value] for pin, value in expected.items() if (actual[pin] ^ value) & masks.get(pin, -1)}
        assert not difference, ("real-lsq-wrapper-staged", self.last_tick, phase, difference)

    async def cycle(self, inp=None, **fields):
        request = inp if inp is not None else Inputs(**fields)
        previous = self.last_tick
        try:
            change = await self._cycle(request)
        except BaseException as exc:
            # The original CheckedEnv records even pre-drive/monitor errors,
            # but observes history only when that request advanced the fixture.
            for checker, preserve_error in self._history_checkers:
                if preserve_error:
                    checker.core_error = repr(exc)
            if self.last_tick > previous:
                self._observe_history(request, exc)
            raise
        if self.last_tick > previous:
            self._observe_history(request)
        return change

    async def _cycle(self, request):
        edge = await self.driver.send(request)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "missing mixed LSQ sample"
            self.last_tick = post.event.tick
            actual = pre.value[0]
            assert pre.value[2] == post.value[2] and encode(actual) == pre.value[2]
            if self.last_tick == edge.tick:
                assert encode(actual) == encode(request)
            self.pre_observed, self.observed = pre.value[1], post.value[1]
            self.pre_response, self.response = (self.driver.ports.observe(self.pre_observed),
                                                self.driver.ports.observe(self.observed))
            row = dict(nodeid=self.nodeid, pre_tick=pre.event.tick, post_tick=post.event.tick, input=asdict(actual),
                       pins=pre.value[2], post_pins=post.value[2], before=pre.value[1], after=post.value[1], checked=False,
                       explicitly_unimplemented_outputs=self.model.unimplemented_outputs)
            try:
                row["expected_before"], row["masks_before"] = self.model.expected(actual, before=True)
                self.compare(self.pre_observed, row["expected_before"], row["masks_before"], "before")
                row["physical_before"] = self.model.safety(actual, self.pre_observed)
                row["change"] = change = self.model.advance(actual)
                row["expected_after"], row["masks_after"] = self.model.expected(actual)
                self.compare(self.observed, row["expected_after"], row["masks_after"], "after")
                row["physical_after"] = self.model.safety(actual, self.observed)
                row["checked"] = True
                self.last_change = change
            except BaseException as exc:
                row["error"] = repr(exc)
                raise
            finally:
                self.journal.write(json.dumps(row) + "\n")
            if self.last_tick == edge.tick:
                return change

    async def boot(self):
        for _ in range(6):
            await self.cycle(reset=True)
        for _ in range(4):
            await self.cycle()

    def emit(self, event, **fields):
        self.actor_journal.write(json.dumps(dict(event=event, nodeid=self.nodeid, tick=self.last_tick, **fields)) + "\n")

    def reach(self, *names):
        self.coverage.sample(names, self.last_tick)

    def prove(self, *names):
        self.reach(*names)
        self.coverage.sample(names, self.last_tick, checked=True)

    def expect(self, observation, why, *, before=False):
        from suites.memblock.lsq.testbenches.lsq_wrapper.env.ports import expected

        self._compare_directed(expected(observation), why, before=before)

    def expect_sbuffer_word(self, lane, word, why, *, data_mask=None, before=False):
        from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Observation
        from suites.memblock.lsq.testbenches.lsq_wrapper.env.ports import expected

        field = "sbuffer_word_0" if lane == 0 else "sbuffer_word_1"
        values = expected(Observation(**{field: word}))
        masks = {} if data_mask is None else {f"io_sbuffer_req_{lane}_bits_data": data_mask}
        self._compare_directed(values, why, before=before, masks=masks)

    def _compare_directed(self, values, why, *, before=False, masks=None):
        assert values, ("empty wrapper expectation is not a check", why)
        actual, masks = self.pre_observed if before else self.observed, masks or {}
        difference = {pin: [actual[pin], value] for pin, value in values.items()
                      if (actual[pin] ^ value) & masks.get(pin, -1)}
        self.checks.write(json.dumps(dict(tick=self.last_tick, nodeid=self.nodeid, why=why,
                                        phase="before" if before else "after",
                                        actual={pin: actual[pin] for pin in values}, expected=values,
                                        masks=masks, passed=not difference)) + "\n")
        assert not difference, ("real-lsq-wrapper-directed", self.last_tick, why, difference)
