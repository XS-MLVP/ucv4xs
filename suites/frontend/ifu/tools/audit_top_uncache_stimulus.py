"""Compare the nine old uncached scenario generators and guard with migration.

Model-backed stand-ins execute the bodies and their existing assertions. This
compares planned semantic requests/peer bytes and ordering, NOT real native
cycle timing, accepted events, or checking-chain independence. Actual native
regressions and the production agent's negative controls provide those proofs.
"""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from suites.frontend.ifu import ROOT
from suites.frontend.ifu.ifu.checker import uncached_redirect
from suites.frontend.ifu.ifu.types import BusRequest, Enqueue, FetchRequest, FetchResult
from suites.frontend.ifu.model.fetch import xor_fold
from suites.frontend.ifu.model.rvc import expand
from suites.frontend.ifu.model.uncache import Outputs
from suites.frontend.ifu.tools.audit_cached_stimulus import GeneratorStandIn, load
from suites.frontend.ifu.uncache_unit.types import BusReply


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class UncacheStandIn(GeneratorStandIn):
    def __init__(self, module):
        super().__init__(module, False)
        self.trace, self._active, self._response, self._result, self._carry = [], None, None, None, None
        module.fetch = self.old_fetch
        module.apply_window = self.apply_window
        module.uncache_accept_and_send = self.old_send
        module.uncache_collect = lambda *_args, **_kwargs: self.old_result()
        module.read_beat = lambda *_args: self.old_result()[0]
        module.read_redirect = lambda *_args: self.old_result()[1]

    def reset(self, *args, **kwargs):
        super().reset()
        self._active = self._response = self._result = self._carry = None

    reset_once = reset

    def log_request(self, window, address):
        fields = asdict(window)
        fields.pop('paddr0')  # Explicit raw halfword -> byte normalization below.
        self.trace.append(dict(kind='request', window=fields, physical_address=address))

    def old_fetch(self, harness, window, **controls):
        self.log_request(window, window.paddr0 << 1)
        return GeneratorStandIn.old_fetch(self, harness, window, **controls)

    async def fetch(self, item, **controls):
        self.log_request(item.window, item.physical_address)
        return await GeneratorStandIn.fetch(self, item, **controls)

    def apply_window(self, harness, window, *, request_valid=1, **controls):
        if request_valid:
            self.old_send(harness, window)

    def old_send(self, harness, window):
        self.log_request(window, window.paddr0 << 1)
        from dataclasses import replace
        self._active = FetchRequest(replace(window, paddr0=0), window.paddr0 << 1)
        self._response = self._result = None

    async def send_uncached(self, item, **controls):
        self.log_request(item.window, item.physical_address)
        self._active, self._response, self._result = item, None, None
        self.records.append(SimpleNamespace(shift=self.pointer & 3,
            bus=BusRequest(item.physical_address, 1 - item.window.pmp0, int(item.window.pbmt0 == 1))))
        return len(self.trace)

    def set(self, **values):
        if values.get('io_fromUncache_resp_valid'):
            self._response = BusReply(values['io_fromUncache_resp_bits_data'],
                values.get('io_fromUncache_resp_bits_corrupt', 0), values.get('io_fromUncache_resp_bits_denied', 0),
                values.get('io_fromUncache_resp_bits_needResend', 0))
            self.trace.append(dict(kind='reply', **asdict(self._response)))

    async def reply(self, uid, response, **controls):
        self._response = response
        self.trace.append(dict(kind='reply', **asdict(response)))

    characterize_reply = reply  # The differential omits provenance; regressions check it.

    async def read_uncached(self, item, response, **controls):
        uid = await self.send_uncached(item)
        await self.reply(uid, response)
        return await self.collect(uid)

    def read(self, name):
        if name == 'io_fromICache_req_ready':
            return 1
        if name == 'io_toUncache_req_valid':
            return int(self._active is not None and self._response is None)
        if name == 'io_toUncache_req_bits_addr_addr':
            return self._active.physical_address >> 1
        if name == 'io_toUncache_req_bits_memBackTypeMM':
            return 1 - self._active.window.pmp0
        if name == 'io_toUncache_req_bits_memPageTypeNC':
            return int(self._active.window.pbmt0 == 1)
        if name == 'io_toIBuffer_valid':
            return int(self._response is not None and not self._response.need_resend)
        if name == 'io_toFtq_wbRedirect_valid':
            return int(self._response is not None)
        raise ValueError(f'unexpected stand-in observation {name}')

    def refresh(self):
        pass

    def make_result(self):
        if self._result is not None:
            return self._result
        response, item, carry = self._response, self._active, self._carry
        assert response is not None and item is not None
        word = response.data if carry is None else carry.low | ((response.data & 0xffff) << 16)
        expanded, shift = expand(word), self.pointer & 3
        exception = 3 if response.denied else 5 if response.corrupt else 4 if expanded.ill else 0
        outputs = Outputs(1, 1, response.data, 3 if response.denied else 5 if response.corrupt else 0,
                          response.need_resend, 0, item.physical_address, 1 - item.window.pmp0, int(item.window.pbmt0 == 1))
        redirect = uncached_redirect(item, outputs, carry)
        beat = None
        if not response.need_resend:
            words, compressed, folds, end = [0] * 36, [0] * 36, [0] * 36, [0] * 36
            words[shift], compressed[shift] = word if expanded.ill else expanded.bits, int((word & 3) != 3)
            pc = carry.pc if carry else item.window.start0_pc
            folds[shift] = xor_fold((pc & ((1 << 50) - 1)) >> 1, 10)
            end[shift] = 0 if compressed[shift] or carry else 1
            beat = Enqueue(1 << shift, 1 << shift, tuple(words), tuple(compressed), tuple(folds),
                (item.window.ftq0,) * 36, tuple(end), (0,) * 36, 1, exception, 1 << shift,
                int(carry is not None and bool(response.corrupt)), 0, 0, (15,) * 36)
            self.pointer += 1
            self._carry = None
        else:
            self._carry = SimpleNamespace(pc=carry.pc if carry else item.window.start0_pc, low=response.data & 0xffff)
        self._result = FetchResult(len(self.trace), beat, redirect, resend=response.need_resend)
        return self._result

    def old_result(self):
        result = self.make_result()
        beat = asdict(result.beat) if result.beat is not None else None
        redirect = asdict(result.redirect)
        redirect['valid'] = 1
        return beat, redirect

    async def collect(self, uid, **controls):
        return self.make_result()


async def execute(path, name, migrated):
    module = load(path, 'top_uncache_differential_' + ('after' if migrated else 'before'))
    agent = UncacheStandIn(module)
    if migrated:
        async def reset(*args, **kwargs):
            UncacheStandIn.reset(agent)
        agent.reset = reset
    result = getattr(module, name)(agent)
    if inspect.isawaitable(result):
        await result
    return json.loads(json.dumps(agent.trace))


async def audit(before):
    after = ROOT / 'tests/ifu/test_ifu_fetch.py'
    import ast
    names = [node.name for node in ast.parse(after.read_text()).body
             if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith('test_uncache')]
    rows = []
    for name in names:
        old, new = await execute(before, name, False), await execute(after, name, True)
        assert old == new, name
        rows.append(dict(test=name, requests=sum(x['kind'] == 'request' for x in new),
            replies=sum(x['kind'] == 'reply' for x in new), before_sha256=digest(old), after_sha256=digest(new)))
    return dict(schema=1, scope='Pure planned semantic request/peer-data sequence, NOT native pin trace or cycle-timing equivalence',
        before=str(before), after=str(after.relative_to(ROOT)), rows=rows,
        case_bodies=len(rows), requests=sum(x['requests'] for x in rows), replies=sum(x['replies'] for x in rows),
        normalization='Only legacy raw Window.paddr0 converted to explicit physical byte address <<1; removed that obsolete field. All remaining window fields and all four reply fields/order identical.',
        limits='No native observations or acceptance credit; stand-ins do not validate timing, monitors, uncache FSM or provenance. Real tests check those separately. Guard is a separate migrated environment test, not included in these9 bodies.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(audit(args.before)), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
