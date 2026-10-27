"""Semantic discovery plus deferred, query-proven write completion."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import matches

COMMON = {
    "CAM-WRITE.single": "单路写入只更新目标槽位",
    "CAM-WRITE.parallel_same_bank": "同 bank 的不同槽位并行写入",
    "CAM-WRITE.parallel_cross_bank": "跨 bank 的并行写入",
    "CAM-WRITE.lane_0": "第一个写入口交付正确值",
    "CAM-WRITE.lane_1": "第二个写入口交付正确值",
    "CAM-WRITE.lane_2": "第三个写入口交付正确值",
    "CAM-WRITE.boundary_entries": "bank 首尾槽位正确寻址",
    "CAM-WRITE.complete_pool": "完整池的每个槽位均已写入并可查询",
    "CAM-TIMING.before_edge": "同步写入前仍看到旧值",
    "CAM-TIMING.visible_on_commit": "新值在规定提交边沿后可见",
    "CAM-HOLD.idle": "无写入时保持已有数据",
    "CAM-HOLD.disabled_payload": "禁用写口的变化 payload 不污染数据",
    "CAM-PORTS.independent": "多个同时查询独立得到各自候选集合",
    "CAM-REUSE.overwrite": "重写撤销旧键并建立新键",
    "CAM-REUSE.consecutive_same_slot": "连续重写同槽位保序，无旧写覆盖新值",
    "CAM-REUSE.interleaved_banks": "跨 bank 连续重写互不污染",
}
ADDRESS = {
    "CAM-MATCH.none": "完整已知池无匹配",
    "CAM-MATCH.one": "完整已知池只有一个匹配槽位",
    "CAM-MATCH.many": "多个同键槽位共同命中",
    "CAM-MATCH.high_bit_distinction": "最高编码位不同不能误命中",
    "CAM-MATCH.low_bit_distinction": "最低编码位不同在精确模式不能误命中",
}
LINE = {
    "CAM-SCOPE.word_excludes_neighbor": "word 模式排除同 line 的其他 word",
    "CAM-SCOPE.line_includes_neighbor": "line 模式包含同 line 的其他 word",
    "CAM-SCOPE.line_excludes_other_line": "line 模式仍排除另一 line",
}
MASK = {
    "CAM-BYTES.zero_query": "零查询 mask 没有冲突",
    "CAM-BYTES.zero_entry": "零存储 mask 不参与冲突",
    "CAM-BYTES.disjoint": "非零但不相交的字节集合不冲突",
    "CAM-BYTES.partial": "部分相交即为冲突",
    "CAM-BYTES.contained": "字节集合包含关系同样命中",
    "CAM-BYTES.low_byte": "最低字节位参与冲突",
    "CAM-BYTES.high_byte": "最高字节位参与冲突",
}


class FunctionalCoverage:
    def __init__(self, key, spec, nodeid):
        self.spec = spec
        self.scenarios = dict(COMMON)
        self.scenarios.update(MASK if spec["kind"] == "byte_mask" else ADDRESS)
        if spec["kind"] == "address_line":
            self.scenarios.update(LINE)
        if spec["write_delay"] > 1:
            self.scenarios["CAM-TIMING.buffered_one_cycle"] = "有写缓冲时首拍不提前可见"
        points = (CoverPointDef("scenario", {k: Bin.values(k) for k in self.scenarios},
                               description="; ".join(f"{k}: {v}" for k, v in self.scenarios.items())),)
        self.reached = CoverGroupDef("lsq.cam.reached", points).instantiate(
            f"lsq.{key}.reached", run_metadata={"test": nodeid, "dut": key}, contract="cam.observed-legal-pins/v1")
        self.checked = CoverGroupDef("lsq.cam.checked", points).instantiate(
            f"lsq.{key}.checked", run_metadata={"test": nodeid, "dut": key}, contract="cam.compared-and-query-proven-writes/v1")
        self.pending = []
        self.previous_commits = ()

    def sample(self, scenarios, tick, *, checked):
        group = self.checked if checked else self.reached
        for scene in scenarios:
            assert scene in self.scenarios, scene
            group.sample({"scenario": scene}, metadata={"tick": tick}, details=False)

    def discover(self, pre, post, old, model, commits):
        spec = self.spec
        scenes = {}
        per_bank = spec["size"] // spec["banks"]
        known = [(i, v) for i, v in enumerate(model.entries) if v is not None]
        full = len(known) == spec["size"]

        def add(scene, addresses=None, old_queries=None):
            # Nonempty targets are versioned so later overwrites cannot falsely
            # satisfy an earlier write's verification obligation.
            targets = {}
            for address in addresses or ():
                value = model.entries[address]
                probes = {1 << bit for bit in range(spec["width"])} if spec["kind"] == "byte_mask" else {value}
                if old_queries and spec["kind"] != "byte_mask":
                    probes.update(old_queries)
                targets[address] = (model.versions[address], probes)
            scenes[scene] = targets

        if commits:
            addresses = [c.address for c in commits]
            if len(commits) == 1:
                add("CAM-WRITE.single", addresses)
            elif len({a // per_bank for a in addresses}) == 1:
                add("CAM-WRITE.parallel_same_bank", addresses)
            else:
                add("CAM-WRITE.parallel_cross_bank", addresses)
            for c in commits:
                add(f"CAM-WRITE.lane_{c.lane}", (c.address,))
                if c.address % per_bank in (0, per_bank - 1):
                    add("CAM-WRITE.boundary_entries", (c.address,))
                if c.old is not None and c.old != c.value:
                    add("CAM-REUSE.overwrite", (c.address,), (c.old,))
                if c.old is not None and any(matches(spec, q, c.old) != matches(spec, q, c.value) for q in post.queries):
                    add("CAM-TIMING.visible_on_commit")
            if self.previous_commits:
                if set(addresses) & {c.address for c in self.previous_commits}:
                    add("CAM-REUSE.consecutive_same_slot", addresses)
                if {a // per_bank for a in addresses} != {c.address // per_bank for c in self.previous_commits}:
                    add("CAM-REUSE.interleaved_banks", addresses)
            if full and any(v is None for v in old):
                add("CAM-WRITE.complete_pool", (i for i, _ in known))
        self.previous_commits = commits

        current = [w for w in pre.writes if w.enabled]
        for w in current:
            if old[w.address] is not None and any(matches(spec, q, old[w.address]) != matches(spec, q, w.value) for q in pre.queries):
                add("CAM-TIMING.before_edge")
                if spec["write_delay"] > 1 and model.entries[w.address] == old[w.address]:
                    add("CAM-TIMING.buffered_one_cycle")
        if known and not current and not commits:
            add("CAM-HOLD.idle")
            if any(w.address or w.value for w in pre.writes):
                add("CAM-HOLD.disabled_payload")
        if full:
            expected_masks = []
            for q in post.queries:
                hits = sum(matches(spec, q, value) for _, value in known)
                expected_masks.append(sum(1 << i for i, value in known if matches(spec, q, value)))
                if spec["kind"] != "byte_mask":
                    add("CAM-MATCH." + ("none" if not hits else "one" if hits == 1 else "many"))
                    if not q.line:
                        for bit, label in ((0, "low"), (spec["width"]-1, "high")):
                            if any(q.value ^ value == 1 << bit for _, value in known):
                                add(f"CAM-MATCH.{label}_bit_distinction")
                if spec["kind"] == "address_line":
                    shift = spec["line_low_bits"]
                    neighbors = [value for _, value in known if value != q.value and value >> shift == q.value >> shift]
                    if neighbors:
                        add("CAM-SCOPE.line_includes_neighbor" if q.line else "CAM-SCOPE.word_excludes_neighbor")
                    if q.line and any(q.value >> shift != value >> shift for _, value in known):
                        add("CAM-SCOPE.line_excludes_other_line")
                if spec["kind"] == "byte_mask":
                    values = [v for _, v in known]
                    if not q.value:
                        add("CAM-BYTES.zero_query")
                    if 0 in values and q.value:
                        add("CAM-BYTES.zero_entry")
                    if q.value and any(v and not v & q.value for v in values):
                        add("CAM-BYTES.disjoint")
                    if any(v & q.value and v & q.value not in (v, q.value) for v in values):
                        add("CAM-BYTES.partial")
                    if any(v & q.value and v & q.value in (v, q.value) for v in values):
                        add("CAM-BYTES.contained")
                    for bit, label in ((0, "low"), (spec["width"]-1, "high")):
                        if q.value == 1 << bit and any(v & q.value for v in values):
                            add(f"CAM-BYTES.{label}_byte")
            if len(set(post.queries)) > 1 and len(set(expected_masks)) > 1:
                add("CAM-PORTS.independent")
        return scenes

    def confirm(self, scenes, observation, model, tick):
        complete = [scene for scene, targets in scenes.items() if not targets]
        self.pending.extend((scene, targets) for scene, targets in scenes.items() if targets)
        outstanding = []
        for scene, targets in self.pending:
            if any(model.versions[address] != version for address, (version, _) in targets.items()):
                # An unproven write overwritten by a new lifecycle is not a pass.
                continue
            for _, probes in targets.values():
                probes.difference_update(q.value for q in observation.queries if not q.line)
            if any(probes for _, probes in targets.values()):
                outstanding.append((scene, targets))
            else:
                complete.append(scene)
        self.pending = outstanding
        self.sample(complete, tick, checked=True)
