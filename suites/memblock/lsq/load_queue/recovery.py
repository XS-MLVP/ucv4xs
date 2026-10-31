"""External recovery/reset bookkeeping based on actual public LQ responses."""
from dataclasses import asdict

from .actor import LoadActor
from .types import Inputs


def younger(left, right):
    def raw(ptr):
        return 2 * (int(ptr.flag) * 160 + ptr.value) + int(not ptr.former)
    delta = (raw(left) - raw(right)) % 640
    assert delta != 320
    return 0 < delta < 320


class RecoveringActor(LoadActor):
    def __init__(self, env):
        super().__init__(env)
        self.cancelled, self.aborted, self.reuse = {}, {}, {}
        self.pending_tail = None

    async def dispatch(self, *args, **kwargs):
        assert self.pending_tail is None and not self.env.observed["io_lqRecoverStall"]
        return await super().dispatch(*args, **kwargs)

    async def step(self, inp=None, *, new_owners=()):
        inp = inp or Inputs()
        old_done = set(self.completed)
        doomed = []
        if inp.redirect.valid:
            assert self.pending_tail is None
            doomed = [owner for owner in self.live.values() if younger(owner.rob, inp.redirect.rob) or inp.redirect.flush_self and owner.rob == inp.redirect.rob]
            positions = sorted(owner.position for owner in doomed)
            assert not positions or positions == list(range(positions[0], self.tail)), "redirect must cancel a young suffix"
            self.pending_tail = self.tail - len(doomed)
        post = await super().step(inp, new_owners=new_owners)
        if inp.redirect.valid:
            for owner in doomed:
                assert owner.uid not in self.completed
                self.cancelled[owner.uid] = owner
                self.live.pop(owner.position)
                self.issued.pop(owner.uid, None)
            self.emit("cancel", old_uids=[owner.uid for owner in doomed], positions=[owner.position for owner in doomed],
                      expected_tail=self.pending_tail, redirect=asdict(inp.redirect))
        if post["io_lqRedirect_valid"]:
            assert self.pending_tail is not None
            expected = max(self.head, self.pending_tail)
            actual = 120 * post["io_lqRedirect_bits_flag"] + post["io_lqRedirect_bits_value"]
            assert actual == expected % 240
            self.tail = expected
            self.pending_tail = None
            self.emit("recover_response", tail=self.tail, pointer=actual)
        for uid in self.completed - old_done:
            owner = self.all[uid]
            for old_uid, old in {**self.cancelled, **self.aborted}.items():
                if old_uid < uid and old.position % 120 == owner.position % 120 and old_uid not in self.reuse:
                    self.reuse[old_uid] = uid
                    self.emit("reuse_completed", old_uid=old_uid, new_uid=uid, slot=owner.position % 120)
        return post

    async def settle(self):
        for _ in range(12):
            if self.pending_tail is None and not self.env.observed["io_lqRecoverStall"]:
                return
            await self.step()
        raise AssertionError("actual shared LoadQueue recovery did not settle")

    async def reset(self):
        old = dict((owner.uid, owner) for owner in self.live.values())
        for _ in range(6):
            await self.env.cycle(Inputs(reset=True))
        self.aborted.update(old)
        self.live.clear()
        self.issued.clear()
        self.head = self.tail = 0
        self.pending_tail = None
        self.emit("reset_abort", old_uids=sorted(old), positions=[old[uid].position for uid in sorted(old)])
        for _ in range(3):
            await self.step()
        return sorted(old)

    def prove_reuse(self, names, old_uids):
        for uid in old_uids:
            assert uid in self.reuse and self.reuse[uid] in self.completed and uid not in self.completed
        self.env.prove(*names)
        self.emit("reuse_checked", names=names, old_uids=old_uids, witnesses={uid: self.reuse[uid] for uid in old_uids})
