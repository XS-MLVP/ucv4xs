"""Full original kind stream, fixed LDU tickets, public lifecycle ledger.

Reuses the old absolute-ROB/SQ/bus effect bookkeeping, NOT its Load planner.
No DUT/model private state, change/expected fields or known-issues reads.
Admission still requires independent raw-history audit of every actual run.
"""
from dataclasses import replace

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.load_queue.types import Bypass, Load
from suites.memblock.lsq.lsq_wrapper.types import Address, Bus, Data, Inputs
from suites.memblock.lsq.psq.types import Attributes
from suites.memblock.lsq.rar.types import Query as RarQuery, Release
from suites.memblock.lsq.raw.types import Query as RawQuery, SqPtr
from suites.memblock.lsq.replay.types import Cause, Refill, StoreWakeup, TlbHint
from suites.memblock.lsq.vlq.types import Redirect
from .mixed_owners import rob_pointer
from .serialized_mixed_owners import SerializedMixedOwners


class LduMixedOwners(SerializedMixedOwners):
    def __init__(self, env, seed):
        super().__init__(env, seed)
        self.p0, self.p1, self.p2, self.tails = ([None]*3 for _ in range(4))
        self._packet = self._intent = None
        env.emit("LDU_mixed_contract", original_seeds_kinds_weights=True,
                 S0_S1_S2_S3_same_lane=True, MMIO_replay_no_RAR_RAW=True,
                 RAR_flushAfter_not_C_NK=True, split_head_tail_S4=True,
                 scope="new producer ATTEMPT; not admission or whole-random completion evidence")

    def make(self, kind, *, unique=False):
        s = super().make(kind, unique=unique)
        if s["kind"] == "load":
            s["phase"] = "ldu_new"
            s["head_s3"] = None
            if s["extra"] == Cause.WAY_PREDICTION:
                self.env.emit("LDU_pinned_disabled_C_WF_intent", uid=s["uid"], cause7_not_emitted=True,
                              source="NewLoadUnit1121 cause(C_WF):=false; original sampled intent not redrawn")
        return s

    def lookup_rob(self, pins, prefix, kind):
        raw = (pins[prefix+"flag"], pins[prefix+"value"], pins[prefix+"isFormer"])
        candidates = [s for s in self.program if s["kind"] == kind and not s["retired"] and not s["rob_cancelled"]
                      and (int(rob_pointer(s["order"]).flag), rob_pointer(s["order"]).value,
                           int(rob_pointer(s["order"]).former)) == raw]
        assert len(candidates) == 1, ("current original ROB generation", raw, [s["uid"] for s in candidates])
        return candidates[0]

    def redirect(self, order, source):
        if self.recovery is not None or self.settle:
            return None
        after = source == "LDU_RAR_flushAfter"
        cutoff = order+int(after)
        assert cutoff >= self.pending(), ("redirect precedes actual ROB head", cutoff, self.pending())
        victims = [s for s in self.program if not s["retired"] and not s["rob_cancelled"] and s["order"] >= cutoff]
        assert all(not s["consumed"] and not s["attempts"] and s["cache_req"] is None
                   for s in victims if s["kind"] == "store" and self.live(s))
        canceled_lq = [s for s in self.lq_valid.values() if s["order"] >= cutoff]
        canceled_sq = [s for s in victims if s["kind"] == "store" and self.live(s)]
        self.recovery = dict(cutoff=cutoff, source=source, victims=victims, cancelled_lq=canceled_lq,
                             lq_target=self.lq_tail-len(canceled_lq), sq_target=min((s["position"] for s in canceled_sq), default=self.sq_tail),
                             lq=None, sq=None, age=0)
        return Redirect(True, rob_pointer(order), not after)

    def ticket(self, s, *, tail=False, uncache=False):
        load, q = s["load"], s["load"].execution
        size = (q.uop.operation >> 1) & 7
        cross = q.vaddr % 16+(1 << size) > 16
        va = q.vaddr//16*16+16 if tail else q.vaddr
        pa = load.paddr//16*16+16 if tail else load.paddr
        mask = ((1 << (1 << size))-1) << (q.vaddr % 16)
        return dict(s=s, tail=tail, cross=cross, VA=va, PA=pa, mask=(mask >> 16 if tail else mask & 65535),
                    size=4 if tail else size, uncache_replay=uncache,
                    extra=s["extra"] if not s["initial"] and not tail else None, exceptions=0,
                    S0_edge=self.edge, cause=None, nuke=False, match=False)

    @staticmethod
    def nuke(item, addresses):
        s = item["s"]
        for a in addresses:
            if not a.valid or a.tlb_miss:
                continue
            old = 2*(160*int(a.rob.flag)+a.rob.value)+int(not a.rob.former)
            if not 0 < (s["order"]-old) % 640 < 320:
                continue
            shift = 6 if a.fu_op & 1 else 4
            if a.paddr >> shift == item["PA"] >> shift and a.mask & item["mask"]:
                return True
        return False

    def survive(self, item, red):
        return item is not None and self.live(item["s"]) and not (red.valid and item["s"]["order"] >= self.recovery["cutoff"])

    def cause(self, item, *, rar_denied=False, raw_denied=False, current_nuke=False):
        if item["exceptions"]:
            return None
        s, flags = item["s"], item["flags"]
        unc = s["subtype"] != "cached"
        nc_replay = item["uncache_replay"] and s["subtype"] == "nc_load"
        if item["uncache_replay"] and not nc_replay:
            return None  # isMMIOReplay -> alwaysWriteback
        reasons = []
        if unc and (not item["uncache_replay"] or nc_replay and (flags["data"] or rar_denied or raw_denied or current_nuke or flags["forward"])):
            reasons.append(Cause.UNCACHE)
        if flags["forward"]:reasons.append(Cause.STORE_MULTI_MATCH)
        if s["load"].execution.uop.store_set_hit and flags["address"]:reasons.append(Cause.ADDRESS_DEPENDENCE)
        if item["extra"] == Cause.TLB_MISS or item.get("special"):reasons.append(Cause.TLB_MISS)
        if flags["data"]:reasons.append(Cause.FORWARD_FAILURE)
        need_cache = not item["full_forward"] and not unc and not item["uncache_replay"]
        if need_cache and item["extra"] in (Cause.CACHE_REPLAY, Cause.CACHE_MISS, Cause.BANK_CONFLICT):
            reasons.append(item["extra"])
        if rar_denied:reasons.append(Cause.RAR_CAPACITY)
        if raw_denied:reasons.append(Cause.RAW_CAPACITY)
        if current_nuke:reasons.append(Cause.VIOLATION)
        return min(reasons) if reasons else None

    def plan(self, *, admit=True, execute=True, effects=True, forced=None):
        self.retired_prefix()
        intent = dict(dispatch=[], addresses=[], data=[], queries=[None]*3, loads=[None]*3, bypass=[None]*3,
                      ldu_s0=[None]*3, ldu_s2=[None]*3, ldu_s3=[None]*3)
        ready0, ready1 = (effects and self.chance(.65) for _ in range(2))
        fields = dict(pending=rob_pointer(self.pending()), pending_next=rob_pointer(self.pending()),
                      attributes=tuple(s["owner"].attributes(last=last) if s is not None else Attributes()
                                       for s,last in (x if x is not None else (None,True) for x in self.s2)),
                      sbuffer_ready=(ready0,ready0 and ready1), cache_ready=effects and self.chance(.7),
                      writeback_ready=effects and self.chance(.65))
        red = Redirect()
        if self.redirect_due is not None:
            proposed = self.redirect(*self.redirect_due)
            if proposed is not None:
                red, self.redirect_due = proposed, None
        elif admit and not self.fair and self.chance(.015):
            candidates = [s for s in self.program if not s["retired"] and not s["rob_cancelled"] and s["order"] > self.pending()]
            if candidates:red = self.redirect(self.rng.choice(candidates)["order"], "external_branch") or red
        fields["redirect"] = red
        stalled = self.recovery is not None or self.settle or self.env.observed["io_toLsqEnqCtrl_lqRecoverStall"] or self.env.observed["io_toLsqEnqCtrl_sqRecoverStall"]
        if admit and not stalled and not red.valid and self.chance(.7):
            fields["dispatch"], intent["dispatch"] = self.dispatch(self.rng.randint(1,8), forced=forced)
        addresses, data, wakes = [Address()]*2, [Data()]*2, [StoreWakeup()]*2
        if execute and not red.valid:
            bank = [s for s in self.active("store") if s["admitted_edge"] < self.edge and 0 <= s["position"]-self.sq_head < 64]
            self.rng.shuffle(bank)
            old_s2 = [x[0] for x in self.s2 if x is not None]
            for lane,s in enumerate([s for s in bank if not s["s2_done"] and s not in old_s2][:2]):
                if self.chance(.6):
                    miss = not self.fair and not s["address_parts"] and not s["misses"] and self.chance(.08)
                    addresses[lane] = s["owner"].address(tail=bool(s["address_parts"]), miss=miss)
                    if not miss:wakes[lane] = StoreWakeup(True,SqPtr.encode(s["position"]))
                    intent["addresses"].append((s,lane,addresses[lane].last,miss))
            for lane,s in enumerate([s for s in bank if not s["data_sent"]][:2]):
                if self.chance(.6):
                    data[lane] = s["owner"].data()
                    intent["data"].append(s)
        fields.update(addresses=tuple(addresses),data=tuple(data),address_wakeups=tuple(wakes))
        queries, translations, rar, raw, packets, bypass = [Query()]*3,[Translation()]*3,[RarQuery()]*3,[RawQuery()]*3,[Load()]*3,[Bypass()]*3
        one,two = [False]*3,[False]*3
        # Fixed S1: even a killed S0 must drain its real Forward request.
        for lane,item in enumerate(self.p0):
            if item is None:continue
            special = bool(self.env.observed["io_specialMode"] and item["s"]["order"] != self.pending())
            item["special"] = special
            kill = not self.survive(item,red) or item["extra"] == Cause.TLB_MISS or special
            translations[lane] = Translation(item["PA"],kill)
        # Fixed S2: NC first issue differs from NC replay; MMIO replay has no queries.
        for lane,item in enumerate(self.p1):
            if item is None:continue
            s,u = item["s"],item["s"]["load"].execution.uop
            mmio_replay = item["uncache_replay"] and s["subtype"] != "nc_load"
            active_query = not mmio_replay and not item["nuke_s1"]
            nc_replay = item["uncache_replay"] and s["subtype"] == "nc_load"
            if active_query:
                need_cache = not item["full_forward"] and s["subtype"] == "cached" and not item["uncache_replay"]
                data_valid = item["full_forward"] or nc_replay or need_cache and item["extra"] not in (Cause.CACHE_MISS,Cause.BANK_CONFLICT)
                rar[lane] = RarQuery(True,u.rob,u.lq,item["PA"],data_valid,nc_replay)
                raw[lane] = RawQuery(True,u.rob,u.sq,item["PA"],item["mask"],data_valid,u.rvc,u.ftq,u.offset,u.checkpoint)
            intent["ldu_s2"][lane] = item
        # Fixed S3, including a real S4 head joined with its following tail.
        for lane,item in enumerate(self.p2):
            if item is None:continue
            s = item["s"]
            if item["cross"] and not item["tail"]:
                one[lane] = item["cause"] is not None or bool(item["exceptions"])
                intent["ldu_s3"][lane] = item
                continue
            head = s["head_s3"] if item["tail"] else None
            assert not item["tail"] or head is not None
            head_revoke = head is not None and (head["cause"] is not None or bool(head["exceptions"]))
            tail_revoke = item["cause"] is not None or bool(item["exceptions"])
            one[lane] = tail_revoke or head_revoke
            two[lane] = head is not None and not head_revoke and tail_revoke
            cause = head["cause"] if head is not None and head["cause"] is not None else item["cause"]
            exceptions = item["exceptions"] | (head["exceptions"] if head is not None else 0)
            q = s["load"].execution
            e = replace(q,uop=replace(q.uop,exceptions=exceptions),need_replay=cause is not None,causes=0 if cause is None else 1 << cause,
                        replay_feedback=s["grant"] is not None,slot=s["grant"] or 0,handled=cause == Cause.CACHE_MISS,
                        mshr=s["mshr"],tlb_id=s["tlb_id"],address_sq=s.get("address_sq",q.uop.wait_sq),data_sq=s.get("data_sq",q.uop.wait_sq),
                        aligned_type=item["size"],unaligned_head=head is not None and head["cause"] is not None,
                        last_beat=bool(s["load"].paddr & 64),
                        special_eligible=head is not None and cause in (Cause.TLB_MISS,Cause.CACHE_REPLAY,Cause.CACHE_MISS),
                        special_request=bool((head or item).get("special")))
            packets[lane] = replace(s["load"],execution=e,exceptions=exceptions)
            intent["loads"][lane],intent["ldu_s3"][lane] = s,item
        # S0 tail injection has priority, no deletion/re-draw of original kinds.
        candidates = [s for s in self.active("load") if s["admitted_edge"] < self.edge and s["phase"] in ("ldu_new","retry","bypass")]
        if self.fair:candidates.sort(key=lambda s:s["uid"])
        else:self.rng.shuffle(candidates)
        for lane in range(3):
            item = self.tails[lane]
            if not self.survive(item,red):item = None
            if item is None and execute and not red.valid and candidates and self.chance(.6):
                s = candidates.pop(0)
                item = self.ticket(s,uncache=s["phase"] == "bypass")
            if item is None:continue
            s,q = item["s"],item["s"]["load"].execution
            queries[lane] = Query(True,item["VA"],q.uop.sq,item["size"],q.uop.load_wait,q.uop.strict,q.uop.wait_sq)
            intent["ldu_s0"][lane] = item
            if item["uncache_replay"]:
                assert not item["tail"]
                bypass[lane] = Bypass(True,q.uop.lq,q.nc,s["load"].mmio)
                intent["bypass"][lane] = s
        fields.update(queries=tuple(queries),translations=tuple(translations),rar_queries=tuple(rar),raw_queries=tuple(raw),
                      loads=tuple(packets),bypass=tuple(bypass),rar_revoke_last=tuple(one),raw_revoke_last=tuple(one),
                      rar_revoke_older=tuple(two),raw_revoke_older=tuple(two),
                      replay_ready=tuple(execute and not red.valid and self.chance(.65) for _ in range(3)))
        waiting = [s for s in self.active("load") if s["initial"] and s["phase"] == "wait"]
        misses = [s for s in waiting if s["last_cause"] == Cause.CACHE_MISS]
        tlbs = [s for s in waiting if s["last_cause"] == Cause.TLB_MISS]
        if execute and misses and self.chance(.7):fields["refills"] = (Refill(True,self.rng.choice(misses)["mshr"]),Refill())
        if execute and tlbs and self.chance(.7):fields["slow_tlb"] = TlbHint(True,self.rng.choice(tlbs)["tlb_id"])
        queried = [s for s in self.active("load") if s.get("queried")]
        if execute and queried and not self.fair and self.chance(.08):fields["release"] = Release(True,self.rng.choice(queried)["load"].paddr)
        if self.cache_job is not None and effects and self.chance(.35):fields.update(cache_response=True,cache_denied=self.cache_job["denied"],cache_corrupt=self.cache_job["corrupt"])
        outstanding = [j for j in self.jobs if j["response"] is None]
        bus = Bus(outstanding=bool(self.seed & 1),ready=effects and len(outstanding) < 16 and self.chance(.7))
        unacked = [j for j in outstanding if j["sid"] is None]
        busy = {j["sid"] for j in outstanding if j["sid"] is not None}
        if effects and unacked and len(busy) < 16 and self.chance(.6):
            job = min(unacked,key=lambda j:j["uid"]) if self.fair else self.rng.choice(unacked)
            bus = replace(bus,ack=True,ack_to_load=job["owner"]["kind"] == "load",mid=job["mid"],sid=self.rng.choice(sorted(set(range(16))-busy)))
        acked = [j for j in outstanding if j["sid"] is not None]
        if effects and acked and self.chance(.35):
            job = min(acked,key=lambda j:j["uid"]) if self.fair else self.rng.choice(acked)
            bus = replace(bus,response=True,response_to_load=job["owner"]["kind"] == "load",response_id=job["sid"],data=job["data"],error=job["error"],nderr=job["nderr"])
        fields["bus"] = bus
        self._packet,self._intent = Inputs(**fields),intent
        return self._packet,intent

    async def step(self, **options):
        old0,old1,old2 = self.p0,self.p1,self.p2
        await super().step(**options)  # strict full-output fixture + original effects
        packet,intent = self._packet,self._intent
        pre,post,tick = self.env.pre_observed,self.env.observed,self.env.last_tick
        red = packet.redirect
        # For a redirect just completed, its victims are now marked aborted.
        alive = lambda item:item is not None and self.live(item["s"])
        for lane,item in enumerate(old2):
            if not alive(item):continue
            s = item["s"]
            if item["cross"] and not item["tail"]:
                s["head_s3"] = item
                continue
            head = s["head_s3"] if item["tail"] else None
            candidates = [x for x in (head,item) if x is not None and not x["exceptions"]]
            match = any(x["match"] for x in candidates)
            nuke = any(x["nuke"] for x in candidates)
            if match or nuke:
                source = "LDU_matchInvalid_flush" if match else "LDU_RAR_flushAfter"
                if self.redirect_due is None or (s["order"],not match) < (self.redirect_due[0],self.redirect_due[1] == "LDU_RAR_flushAfter"):
                    self.redirect_due = s["order"],source
                self.env.emit("LDU_actual_rollback_intent",uid=s["uid"],absolute_ROB=s["order"],source=source)
            s["head_s3"] = None
        next2 = [None]*3
        for lane,item in enumerate(old1):
            if not alive(item):continue
            item = dict(item)
            q = packet.rar_queries[lane]
            assert q.valid == packet.raw_queries[lane].valid
            rd = bool(q.valid and not pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"])
            wd = bool(q.valid and not pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"])
            item["nuke"] = bool(q.valid and post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"])
            item["cause"] = self.cause(item,rar_denied=rd,raw_denied=wd,current_nuke=item["nuke_s1"] or self.nuke(item,packet.addresses))
            item["s"]["queried"] = item["s"].get("queried",False) or q.valid
            next2[lane] = item
            self.counts["ldu_original_S2_tickets"] += 1
        next1 = [None]*3
        for lane,item in enumerate(old0):
            if not alive(item):continue
            item = dict(item)
            flags = dict(address=False,data=False,forward=False)
            p = f"io_forward_{lane}_s2Resp_"
            killed = packet.translations[lane].kill
            assert post[p+"valid"] == int(not killed)
            if not killed:
                flags = dict(address=bool(post[p+"bits_addrInvalid_valid"]),data=bool(post[p+"bits_dataInvalid_valid"]),forward=bool(post[p+"bits_forwardInvalid"]))
                for flag,field in (("addrInvalid","address_sq"),("dataInvalid","data_sq")):
                    if post[p+"bits_"+flag+"_valid"]:
                        item["s"][field] = SqPtr(bool(post[p+"bits_"+flag+"_bits_first_flag"]),bool(post[p+"bits_"+flag+"_bits_second_flag"]),post[p+"bits_"+flag+"_bits_value"])
                mask = sum(post[p+f"bits_forwardMask_{b}"] << b for b in range(16))
                item["full_forward"] = not flags["data"] and mask & item["mask"] == item["mask"]
                item["match"] = bool(post[p+"bits_matchInvalid"])
            else:item["full_forward"],item["match"] = False,False
            item["flags"] = flags
            item["nuke_s1"] = item["extra"] != Cause.TLB_MISS and self.nuke(item,packet.addresses)
            if item["uncache_replay"]:
                job = item["s"]["attempts"][-1]
                assert job["consumed"]
                item["exceptions"] = int(job["nderr"]) << 5 | int(job["error"]) << 19
                item["s"]["phase"] = "ldu_pipe"
            next1[lane] = item
        self.p0 = intent["ldu_s0"]
        self.tails = [None]*3
        for lane,item in enumerate(self.p0):
            if item is None:continue
            s = item["s"]
            s["phase"] = "ldu_pipe"
            if item["cross"] and not item["tail"]:self.tails[lane] = self.ticket(s,tail=True)
            self.env.emit("LDU_original_S0",uid=s["uid"],lane=lane,tail=item["tail"],cross=item["cross"],uncache_replay=item["uncache_replay"],absolute_ROB=s["order"])
        self.p1,self.p2 = next1,next2
        assert not any(self.qpipe), "old simultaneous Forward/RAR query planner must stay detached"
