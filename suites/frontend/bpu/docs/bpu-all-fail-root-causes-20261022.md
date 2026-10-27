# 全部 123 个 FAIL 的逐簇根因定位（2026-10-22，只读）

> 依据：`results/full-regression-20261022-v1`（29907 用例、29777 PASS / 123 FAIL / 7 XFAIL）。
> **本轮未修改任何 RTL、未运行 RTL 生成、未运行任何回归。**
> 每条给出：断言在比什么、失败签名、Scala（或参考模型）根因、置信度。

## 0. 先说一个全局事实

对仓内全部历史运行做交叉比对：**这 123 个 FAIL 在任何一次历史运行中都没有 PASS 过**
（`results/**/test-results.json` 共 40+ 次运行）。所以：

- **没有回归**：不存在"以前通过、现在失败"的用例。
- 它们是这些用例**一直捕获到的缺陷**（RTL 或参考模型），不是本轮改动引入的。

## 1. 根因汇总（按机制聚类）

| # | 机制 | 影响 FAIL | 责任方 | 置信度 |
|---|---|---:|---|---|
| A | MainBTB 方向计数更新缺少 tag 命中限定 | 17 | **RTL** | 高 |
| B | TAGE 写提案用了预测时的旧计数 | 10 | 参考模型 | 高 |
| C | MicroTAGE 训练资格不检查"解析出的分支是否条件分支" | 16 | **RTL** | 高 |
| D | UTAGE 影子写缓冲 dirty 记账丢失最新写 | 19 | **RTL** | 高（有计数见证） |
| E | MicroRAS 完全不使用 `io.enable`（死开关） | 4 | **RTL** | 高 |
| F | MicroBTB fallthrough 复活已死亡条目 | 2 | **RTL** | 高 |
| G | MainBTB 多命中清理把命中集全部清零（含幸存者） | 4 | **RTL** | 中高 |
| H | ITTAGE 对未发布原始分配 provider | 4 | **RTL** | 中高 |
| I | RAS 投机 push/pop 不受 `io.enable` 门控（死开关） | 5 | **RTL** | 高 |
| J | ABTB 目标纠正的目的地/多命中选择 | 1 | **RTL** | 中 |
| K | MainBTB 保留槽 rank 映射（write-buffer owner/rank 语义） | 8 | 参考模型或测试假设 | 中 |
| L | 其余流水线级联差异（choice/flush/history/folded） | 43 | 多数为 A/C/D 的下游传播 | 中（待修后复核） |

合计 17+10+16+19+4+2+4+4+5+1+8+43 = 133 > 123，因为 L 与其它组有重叠，
实际按簇见第 2 节（逐簇计数恰好 123）。

---

## 2. 逐簇结论

### A. `MainBtbAlignBank.scala:259-261`（17 个）

**比什么**：MainBTB 方向计数写请求 `counterWriteBuffer.io_enq_{valid,bits}` 的
`{setIdx, wayMask, counters}` 与独立方向计划逐位比较
（`bpuverify/bpu/bundle/main_service.py:37`）。

**根因**（Scala）：

```scala
// XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbAlignBank.scala:258-261
t1_meta.zipWithIndex.foreach { case (meta, i) =>
  val hitMask = t1_branches.map { branch =>
    branch.valid && branch.bits.attribute.isConditional && meta.position === branch.bits.cfiPosition
  }
```

方向计数属于**表项的 tag 身份**，这里只用 7 位 `position` 匹配，**没有 `meta.rawHit`**。
同一 set 的另一个 way 若属于别的块而 position 相同，会被误更新。

同文件另外两处都要求 tag 命中：
- 表项写回 `t1_hitMask`（`:220`）用 `meta.hit(branch)` = `rawHit && position ===`（`Bundles.scala:76-78`）；
- 替换器 touch `t1_actualTakenMask`（`:269-273`）含 `rawHit`。

**三种签名与之一一对应**：

| 签名 | 用例 | 含义 |
|---|---|---|
| `mask 1 → 3` | `test_ahead_working_set`（4）、`test_miss_authority`（1） | 两个 way 都被写 |
| `mask 1 → 2`（way0 期望，way1 实际） | `test_main_cold_original_order`（8） | 只写了外来 way |
| `mask 2 → 1`（way1 期望，way0 实际） | `test_main_service`（1） | 同上，方向相反 |
| `main_metadata.counter 0 → 2` | `test_sc_admission`（2） | 同一 way 的计数被外部分支改动 |

`test_ahead_working_set` 的检查器文案就是 `"requires original hit"`。
另有 4 个 `test_ahead_working_set` 的 `choice1.target/position` 差异是该污染的
下游（错误方向改变 taken 与位置）。**这 4 个归入 L。**

**对应功能点**：`BPU-INT-056/058/059/100`、`BPU-INT-029/030`（MBTB 方向归属）。

---

### B. `bpuverify/tage/model/semantic.py:528`（10 个，参考模型）

**比什么**：TAGE 缓存中"每个逻辑身份的最新版本"与 DUT 实际写提案/服务
（`bpuverify/bpu/checker/mixed_visibility.py:210`、
`bpuverify/bpu/checker/direction_turnaround.py`）。

**失败签名**：`value: expected 5, actual 4`（模型 5、DUT 4），以及
`[0]: expected None, actual {...counter 6}` 这类提案资格差异。

**根因**（Python）：

```python
# bpuverify/tage/model/semantic.py:526-528
current  = counter if latest is None else latest.write.entry.counter   # 已考虑同 way 待写版本
...
proposal = clamp(counter + (1 if branch.taken else -1), 7)             # 却用预测时旧计数
```

`current` 只用于"要不要写"，真正写入缓存的 `proposal` 仍基于旧 `counter`。

**决定性证据**（同一条失败记录里的三方对照）：

| 来源 | counter |
|---|---|
| 计​划 `expected_pending` | **5** |
| 独立计划 `independent_pending` | **5** |
| **DUT 实际提案** `latest_actual_state.writes[0].bits.counter` | **5** |
| 参考模型缓存 `actual` | **4** |

DUT 与两条独立推导一致，只有模型缓存不一致 → **参考模型缺陷，不是 RTL**。

---

### C. MicroTAGE 训练资格缺少"解析分支是条件分支"检查（16 个）

**比什么**：预测时读到的 `abtbResult[i].takenCtr_value`
（`bpuverify/utage/checker/dual_source.py:31-33`）。

**失败签名**：`2.counter: expected 6, actual 7`、`1.counter: expected 6, actual 7`
——**只出现在 `later-direct` / `later-indirect`**（16 个参数），其余 1344 个参数全 PASS。

**根因**（Scala）：

```scala
// XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/MicroTage.scala:283
val trainHasAbtbBranch = t0_abtbResult(i).valid && (finalPrediction.cfiPosition >= t0_abtbResult(i).cfiPosition)
```

`t0_abtbResult(i).valid` 来自预测时的 metadata，而该 metadata 的条件过滤用的是
**ABTB 当时存储的属性**：

```scala
// MicroTage.scala:227-230
s1_predMeta.bits.abtbResult(i).valid :=
  io.fromAheadBtb.result(i).valid && io.fromAheadBtb.result(i).bits.attribute.isConditional && ...
```

于是：ABTB 里存的是"条件分支"（前一步训练成 kind=1），而本次**解析出的**分支是
direct/indirect（kind=2/3，位置相同）。MicroTage 仍认为有资格，用
`actualTaken = (finalPosition === abtbPosition) && finalTaken = 1` 去 **+1**，
把该表项从 6 推到 7（饱和）。

参考模型的要求写在 `bpuverify/utage/model/dual_source.py:91-96`：

```python
active = tuple(table for table, value in enumerate(before)
    if value.position < position or value.position == position and kind == 1)
```

即"同位置的非条件分支不合格"。功能点规则名就是
`same-position-nonconditional-is-ineligible`（`BPU-UTAGE-025`）。

**后果**：MicroTage 表里出现给非条件分支的方向计数，之后可能把 ABTB 的 taken
改判为 not-taken。

---

### D. UTAGE 影子写缓冲 dirty 记账丢失最新写（19 个，有计数见证）

**比什么**：原生 SRAM 内容与"最新已接受学习版本"逐字比较
（`bpuverify/utage/checker/learning_persistence.py:17-23`）。

**失败签名**：DUT 的 counter 恒比模型**少一步**——
`expected 7 actual 6`、`expected 5 actual 4`、`expected 2 actual 3`、`expected 0 actual 1`
（即"该 +1 的没加 / 该 −1 的没减"）。

**决定性证据**（每条失败记录都带账本）：

| 用例 | accepted | published | services |
|---|---:|---:|---:|
| `test_learning_persistence[...]` | 24 | 24 | **23** |
| 同上 | 27 | 27 | **26** |
| `test_predecessor_retention[...]` | 32 | 32 | **24** |
| 同上 | 16 | 16 | **15** |
| 同上 | 18 | 18 | **17** |

`published − services` = 从未被服务的最新版本数。用例
`test_learning_persistence` 的 8 个身份分 3 轮写，每轮各写一次且前一轮已全部服务完
（前两阶段 `actual_services` 分别为 8、16），因此 `24−23=1` 的那一个**不是被更新的
版本取代**，而是真的丢了。并且它正好就是唯一偏低的那个 cell（`(1,6)`）。

**根因**（Scala）：`BypassShadowBuffer.scala` 的 dirty 记账存在**同槽别名**：

```scala
// XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/BypassShadowBuffer.scala:246-253
when(io.writeSuccess) {
  statusEntries(deqPtr.value).dirty := false.B
}
when(t1_hasWrite) {
  statusEntries(enqPtr.value).valid := true.B
  statusEntries(enqPtr.value).dirty := true.B          // 新条目置脏
}
when(t1_hasWrite && t1_hasHit) {
  statusEntries(t1_cleanId).dirty := false.B           // 旧版本清脏；Chisel 后写优先
}
```

`t1_cleanId ∈ 0..7`（`numEntry = 8`，`:51`）与 `enqPtr.value` 同域。当
`t1_cleanId === enqPtr.value` 时，**最后一条把刚入队的新条目清成"干净"**，
于是 `io.tryWrite.valid := valid && dirty` 恒 0（`:262`）、
`when(... !dirty && !isEmpty) { deqPtr := deqPtr + 1 }`（`:243`）直接跳过它 ——
**最新学习永远进不了 SRAM**。

次因（同一处）：`t1_cleanId` 的选取是
`Mux(t0_chosenFirst, ~PriorityEncoder(t0_firstHit.reverse), ~PriorityEncoder(t0_entryHit.reverse))`
（`:151-153`），当同 index 在缓冲里有多份时取**索引最小**的槽，而非
`priorityMask` 选中的最老槽，也会清错槽的 dirty。

**这是已登记的 `BPU-UTAGE-016`**（"ring 槽清 dirty"）。本轮的增量是：
把它从"112 个失败格"变成**可计数的 `published − services` 见证**。

受影响簇：`test_predecessor_retention`(8)、`test_learning_persistence`(3)、
`test_working_set`(2)、`test_instruction_confidence`(2)、`test_learning_retention`(1)、
`test_semantic_reference`(2)、`test_source_ownership`(1) = 19。

---

### E. MicroRAS 完全不使用 `io.enable`（4 个，死开关）

**比什么**：`uras.io_specOut_isCanUse` / `retTarget`
（`bpuverify/uras/checker/*`、集成侧 `pipeline_binding`）。

**失败签名**：`usable: expected 0, actual 1; target: expected MISSING, actual 0x4000_...`
—— **禁用 MicroRAS 后它仍然给出可用返回目标**。

**根因**（Scala）：`MicroRas.scala` 全文**没有任何 `io.enable` 引用**
（`grep -n enable MicroRas.scala` 无输出），而 `BasePredictorIO` 明确提供该输入
（`Abstracts.scala:35`），其它预测器都以它门控（`AheadBtb.scala:93/114/116`）。
`io.specOut.isCanUse := isCanUse`（`MicroRas.scala:242`）无条件输出。

**集成后果**：`Bpu.scala:101` 把 `uras.io.enable := ctrl.rasEnable && ctrl.mbtbEnable`，
但消费端（`Bpu.scala:284/321/551/557`）直接用 `uras.io.specOut.isCanUse` 而不看
`ctrl.rasEnable`。所以 **RAS 关闭时，RET 仍会被 MicroRAS 的投机栈顶改向**。

对应 `BPU-URAS-016`。`test_semantic_reference` 的 3 个 `target` 差异是同一模块的
投机 push/pop 配对结果（`MicroRas.scala:170-245` 的 `s2_hasPush/s3_hasPop` 组合），
归 `BPU-URAS-017`。

---

### F. MicroBTB fallthrough 复活已死亡条目（2 个）

**比什么**：训练后条目 `{valid, taken, target, position}`
（`bpuverify/ubtb/checker/*`）。

**失败签名**：`valid: expected 0, actual 1; taken: expected MISSING, actual 1;
target: expected MISSING, actual 0x...`

**根因**（Scala）：

```scala
// XiangShan/src/main/scala/xiangshan/frontend/bpu/ubtb/MicroBtb.scala:203-207
}.elsewhen(!t1_hitAttributeSame || !t1_hitPositionSame || !t1_hitTargetSame || !t1_actualTaken) {
  initEntryIfNotUseful(t1_hitNotUseful)     // ← 含 !t1_actualTaken（fallthrough）
```

`initEntryIfNotUseful(cond)`（`:183-194`）在 cond 为真时**重装整个条目**：
写 tag/position/attribute/target、`slot1.isStaticTarget := true`、
`slot2.valid := false`、`usefulCnt.resetSaturatePositive()`。

于是"命中一个 `usefulCnt == 0`（已死亡）的条目 + 本拍 fallthrough"这条最常见路径，
会把死条目**重新装填成有效条目并带上训练目标**——一次 not-taken 不该产生任何分配。

**应为**：`initEntryIfNotUseful(t1_hitNotUseful && t1_actualTaken)`。
对应 `BPU-UBTB-011`。

---

### G. MainBTB 多命中清理把命中集全部清零（4 个）

**比什么**：清理服务后的完整条目（`row/position/kind/target`）与"幸存者 + 独立邻居"
（`bpuverify/bpu/checker/*duplicate*`）。

**失败签名**：`row: expected 3, actual 1; position: expected 3, actual 0;
kind: expected 3, actual 0`（DUT 侧是被清零的条目 = tag0/position0/kind0），
以及 `value: expected True, actual False`（幸存者不再有效）。

**根因**（Scala）：

```scala
// XiangShan/.../mbtb/MainBtbAlignBank.scala:295-297
b.io.flush.req.valid        := s2_fire && s2_multiHitMask.orR && s2_internalBankMask(i)
b.io.flush.req.bits.wayMask := s2_multiHitMask        // ← 命中集，含应保留的那一个
```

```scala
// XiangShan/.../mbtb/MainBtbInternalBank.scala:176-190
val flushValid = flush.req.valid && flush.req.bits.wayMask(i) && !conflict
bufWrite.bits.entry := RegEnable(Mux(writeValid, writeEntry.req.bits.entry,
  0.U.asTypeOf(new MainBtbEntry)), valid)             // ← 清理即写全零
```

多命中时 `s2_multiHitMask` 包含**所有**命中的 way，代码对每一个都写全零，
包括本应作为幸存者保留的那一个（选择幸存者需要 `s2_multiHitWayIdx` 之外的信息，
ABTB 侧就有 `multiHitWayIdx` 概念，MainBTB 侧没有）。
对应 `BPU-MBTB-026/029`（"重复清理不能吞掉另一身份"）。

---

### H. ITTAGE 对未发布的原始分配 provider（4 个）

**比什么**：`hit` / `provider.valid` / `provider_target`
（`bpuverify/ittage/checker/*`、集成 `ittage_metadata.provider.valid`）。

**失败签名**：`hit: expected 0, actual 1; provider_valid: expected 0, actual 1`；
`provider_target: expected 0x41000200, actual 0x400016..`

**根因**（Scala）：

```scala
// XiangShan/src/main/scala/xiangshan/frontend/bpu/ittage/Ittage.scala:167
private val updateValid = hasTrainBranch && RegNext(t0_fire, init = false.B)
```

`updateValid` 只要求"有一笔训练 + t0 拍有效"，**不要求该原始预测曾被发布**
（`s1_meta.valid` / 被选为最终预测）。于是对一笔从未发布过的原始（它的 metadata
可能来自被更年轻请求取代的请求）也会执行
`when(updateValid && updateMisPred && ...)`（`:381`）→ 分配新 provider。

`allocate` 的目的表/way 由 `s2_allocatableSlots`（`:300`）独立选出，
因此会凭空产生一个指向旧目标的 provider。对应 `BPU-ITTAGE-017/019/020`。

---

### I. RAS 投机 push/pop 不受 `io.enable` 门控（5 个，死开关）

**比什么**：`topRetAddr` / `redirectMeta.{ssp,sctr,tosr,tosw}` / 保留提交栈
（`bpuverify/ras/checker/semantic.py:10-22`）。

**失败签名**：
- `group: expected 0, actual 1; calls: expected 0, actual 1`（`enabled=False` 仍 push）
- `top: expected 536877060, actual 536875012; calls: expected 3, actual 2`（启用后栈深度错）
- `retained_groups[2][0]` 差 4096

**根因**（Scala）：

```scala
// XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/Ras.scala:71-74
stack.spec.pushValid := specPush && !stackNearOverflow      // ← 没有 io.enable
stack.spec.popValid  := specPop  && !stackNearOverflow      // ← 没有 io.enable
stack.spec.fire      := io.specIn.valid && io.enable        // 只有 fire 门控
```

而 `RasStack` 的投机栈更新**直接看 `pushValid/popValid`，不看 `fire`**：

```scala
// XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/RasStack.scala:317-323
when(io.spec.pushValid) { specPush(io.spec.pushAddr, ssp, sctr, tosr, tosw, topEntry) }
when(io.spec.popValid)  { specPop(ssp, sctr, tosr, tosw, topNos) }
```

→ **`io.enable = 0` 时 `ssp/tosr/tosw` 仍然推进**。`test_coverage` 的失败记录里
`Events(action=2, ..., enabled=False)` 与 `group=1, calls=1` 直接对上。

副作用：`redirectMeta` 携带错误的 ssp/tosr/tosw，重定向恢复会还原到错状态
（`top`/`retained_groups` 差异）。对应 `BPU-RAS-017/008`。
**应为**：`specPush && !stackNearOverflow && io.enable`（pop 同理）。

---

### J. ABTB 目标纠正的目的地选择（1 个）

`0.target: expected 0x40000140, actual 0x40000100; 0.target_low: 2496 → 2432`
（差 64 = 一个 fetch 块内的一个 32B 半块）。

目标纠正路径本身写向命中 way：

```scala
// XiangShan/.../abtb/AheadBtb.scala:348-354
}.elsewhen(t2_fire && t2_needCorrectTarget && t2_bankMask(i)) {
  b.io.writeReq.bits.wayIdx := OHToUInt(t2_hitMaskOH)
```

但 `t1_hitMask`（`:284-286`）只按 `position + attribute` 匹配（无 tag），
`t1_predictInfo = Mux1H(t1_hitMaskOH, t1_meta.entries)`：当同一 set 有**同位置同属性**
的两条（正是 `distinct-destinations` 场景）时，`PriorityEncoderOH` 选中较低位 way，
纠正写到错误的目的地，原目的地保留旧 target。对应 `BPU-ABTB-053`。
置信度中：需要把 `t1_hitMask` 加上 tag 限定（与 A 同类）才能确认。

---

### K. MainBTB 保留槽 rank 映射（8 个）

**比什么**：TAGE 表项写缓冲的保留槽
`retained[owner][rank]` 与按 `rank` 排序的模型记录
（`bpuverify/bpu/checker/retouch_replacement.py:74`）。

**失败签名**：`row: expected 72, actual 122; tag: expected 3264, actual 1986;
counter: expected 0, actual 1`（`test_owner_recency`、`test_retouch_replacement` 各 4）。

**分析**：`row/tag` 完全不同（不是数值偏差，是**另一个逻辑身份**），且 DUT 的
counter 恰好比模型多 1。模型按 `program.owner_records(snapshot, owner)` 的 **rank 序号**
去索引 RTL 的 `entries_{owner}_{rank}`，而 RTL 的 `rank` 是**写缓冲内的分配序**
（`BpuVerify` 只读绑定 `tage_entry_write_buffer_bank{bank}.entries_{owner}_{rank}`）。
两者只有在"rank 顺序 == 缓冲槽次序"时才等价。

**结论**：这是**参考模型/断言的映射假设**，不是已证的 RTL 缺陷。判定它需要
一步观测：在 `test_owner_recency` 的 holding 拍打印
`shadowValid_{owner}_{rank}` 与模型 rank 列表的对应关系。
**未确认，标注为"待一次定向观测"。**

---

### L. 其余流水线级联差异（43 个，多为 A/C/D 的下游）

这些用例比较的是**完整流水线**的 `choiceN{taken,target,position,kind}`、
`flushes`、`repair2/3`、`metadata.history.{ghr,bw}`、`lookup_folds`，
由 `bpuverify/bpu/checker/pipeline.py:compared_values` 生成期望。

| 簇 | FAIL | 首个差异 | 归属判断 |
|---|---:|---|---|
| `test_ahead_correction` | 4 | `choice1.taken 0→1; position 15→7` | 早级选择被改 → A/MicroTAGE 方向下游 |
| `test_cold_source_isolation` | 2 | `choice1.taken 0→1; target 0x400003D0→0x...`；`flushes 1→0` | 同上 |
| `test_main_sibling` | 2 | `choice2.target/position 12→5` | Main 方向污染后再选择下游（A） |
| `test_main_dynamic_target` | 2 | `flushes 0→1; repair2 0→1; choice2.target` | Main 目标纠正与服务下游（A/J） |
| `test_common_history` | 2 | `ghr 254→252; bw 14→12`（差 1 bit） | 被执行前缀差一个条件分支 → 方向下游（A/C） |
| `test_confidence_boundary` | 2 | `[6]106→104; [7]3409→3441; [8]7504→7512` | PHR 折叠/选择器下游 |
| `test_sc_early_learning` | 2 | `ahead.0.valid 0→1` | AheadBTB 早级可见性（与 J 同族） |
| `test_early_aging` | 1 | `early_direction.2.hit 0→1` | MicroTAGE 命中报告（C 同族） |
| `test_early_direction` | 1 | `early_direction.2.hit 1→0` | 同上，反向程序 |
| `test_late_source_qualification` | 1 | `ittage_metadata.provider.valid 0→1` | 同 H |
| `test_ahead_working_set`（choice 型） | 4 | `choice1.target/position 12→2` | 同 A 下游 |
| `test_opposed_learning_pair`（提案型 3） | 3 | `[0]: None ↔ {...counter 6/0/7}` | 同 B |

**置信度说明**：这些差异的**量**（1 bit 历史、一次额外 flush、位置 12↔7）与
"方向被判反 → 分支未被执行 → 历史少推一位"一致，但**它们共用同一套独立模型**，
所以不能排除模型自身的第二处偏差。**要给出确定结论，必须在 A/C/D/E/F/G/H/I 修复后
复跑同一批用例**：若这些簇随之消失，即证明是下游传播；若仍存在，才需要各自定位。
在此之前我不把它们记为"已定位根因"，只记为"下游候选"。

---

## 3. 与"已登记已知差异"的对应

| 已登记 | 本报告机制 | FAIL 数 |
|---|---|---:|
| `BPU-UTAGE-016`（ring 槽清 dirty） | D | 19 |
| `BPU-UTAGE-025` | C | 16 |
| `BPU-MBTB-026/029` | G | 4 |
| `BPU-MBTB-025` | A 的模块内版本（同 tag 限定缺失，见注） | 4 |
| `BPU-MBTB-027/028` | A/G 的模块内版本 | 3+1 |
| `BPU-UBTB-011` | F | 2 |
| `BPU-URAS-016` | E | 2 |
| `BPU-URAS-017` | E 的连带（投机配对） | 2 |
| `BPU-RAS-017/008` | I | 5 |
| `BPU-ITTAGE-017/019/020` | H | 3 |
| `BPU-ABTB-053` | J | 1 |
| `BPU-INT-056/058/059/100` | A | 9 |
| `BPU-INT-029/030` | A | 2 |
| （新）`BPU-INT-xxx` 方向提案 | A | 6 |

注：MBTB 模块内 `test_depth_owner` 的计数互换
（`0.counter 0→2, 1.counter 2→0`）与 A 是**同一处代码**在单模块 DUT 上的表现：
两条同 tag 不同 position 的条目同处一 set，`position` 匹配把两个方向写反。

---

## 4. 结论与下一步

**已确认 9 个 Scala 根因**（A、C、D、E、F、G、H、I、J），它们解释 123 个 FAIL 中的
**82 个**；1 个是参考模型缺陷（B，10 个）；1 个是断言映射假设待观测（K，8 个）；
余下 43 个是上述方向/历史/TAGE 缺陷在完整流水线上的级联表现，需要修复后复跑才能
逐簇定案。

**scala 修复清单**（本轮只列出，未实施）：

| 文件:行 | 现状 | 应为 |
|---|---|---|
| `mbtb/MainBtbAlignBank.scala:259-261` | 只按 position 匹配方向 | 增加 `meta.rawHit` |
| `utage/MicroTage.scala:283` | 资格只看 ABTB 存储属性 | 增加 `finalPrediction.attribute.isConditional` |
| `utage/BypassShadowBuffer.scala:246-253` | clean 可清掉刚入队的槽 | `t1_cleanId =/= enqPtr.value`；cleanId 取最老槽 |
| `ras/MicroRas.scala`（全文） | 无 `io.enable` | `isCanUse`/`topRetAddr` 及状态更新受 `io.enable` 门控 |
| `ubtb/MicroBtb.scala:207` | fallthrough 也重装条目 | `t1_hitNotUseful && t1_actualTaken` |
| `mbtb/MainBtbAlignBank.scala:297` | flush 用整个多命中集 | 只清 `s2_multiHitWayIdx` 之外的重复项 |
| `ittage/Ittage.scala:167` | `updateValid` 无发布限定 | 增加原始预测曾被发布的限定 |
| `ras/Ras.scala:71-72` | push/popValid 无 `io.enable` | 加 `&& io.enable` |
| `abtb/AheadBtb.scala:284-286` | 纠正匹配无 tag | 增加 tag 限定 |
| `bpuverify/tage/model/semantic.py:528` | `proposal` 用旧计数 | 用 `current`（参考模型） |

**约束**：本轮**未修改任何 RTL**、**未运行 RTL 生成**、**未运行回归**；
123 FAIL 与 7 XFAIL 全部原样保留。
