# BPU RTL Bug Report（9 项 · 2026-10-22）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


来源：一次全量仿真回归 `results/full-regression-20261022-v1`
（29907 个用例、29777 PASS、**123 FAIL**、7 XFAIL）。

这 9 条是其中能被追到具体 RTL 语句的缺陷，合计解释 **85 个失败**。
其余 10 个是参考模型写错、8 个是断言映射假设未定案、19 个是这些缺陷的流水线级联，
另有 1 个待定，见文末。

> **本文只做定位。RTL 未被修改，未做 RTL 生成，未跑回归。**
> 所有"实际值"都来自 DUT 的只读观测（memory-direct），没有写内部状态、
> 没有伪造 metadata、没有跳过任何检查。

## 总览

| ID | 标题 | 模块 | 失败 | 置信度 |
|---|---|---|---:|---|
| BPU-BUG-01 | 方向计数器只按位置匹配，会写到别人的表项 | MainBTB | 28 | 高 |
| BPU-BUG-02 | 非条件分支被当成条件分支学方向 | MicroTAGE | 18 | 高 |
| BPU-BUG-03 | 刚写进缓冲的学习被自己清成"干净"，永远进不了 SRAM | MicroTAGE | 17 | 高 |
| BPU-BUG-04 | RAS 关掉后投机栈仍在推入/弹出 | RAS | 5 | 高 |
| BPU-BUG-05 | MicroRAS 完全不理会 enable | MicroRAS | 4 | 高 |
| BPU-BUG-06 | 多命中清理把该保留的那一条也清零 | MainBTB | 7 | 中高 |
| BPU-BUG-07 | 没发布过的预测也会分配 ITTAGE 表项 | ITTAGE | 4 | 中高 |
| BPU-BUG-08 | 一次 not-taken 会复活已死亡的条目 | MicroBTB | 2 | 高 |
| BPU-BUG-09 | 目标纠正写到同位置同属性的另一条 | AheadBTB | 1 | 中 |

---

## BPU-BUG-01 · 方向计数器只按位置匹配，会写到别人的表项

**模块**：MainBTB（`MainBtbAlignBank`）　**严重度**：高　**失败**：28

### 一句话

更新"这条分支的方向倾向"时，代码只比对了**分支在指令块里的位置（3 bit）**，
没有确认"这个 way 里存的到底是不是这条分支"。同一个 set 里另一个块如果恰好有
同位置的分支，方向就会被写进**别人的表项**——真身没学到，路人被改坏。

### 场景

MainBTB 一个 set 有 2 个 way。两条不同的分支块（不同 tag）可以同时落在这个 set 的
两个 way 里。它们各自的第 N 个位置可能都是条件分支。这时反馈一条 taken/not-taken，
按现在的代码两个 way 都"匹配"。

### 激励（真实驱动，不是改内部状态）

| 用例 | 驱动 |
|---|---|
| `test_main_cold_original_order` | 两个真实原始分支在同一 PC 上先后解析（顺序 old-then-young / young-then-old），中间夹一次真实服务；陪跑分支是一条**独立**的未执行兄弟分支，计数 0 或 1 |
| `test_miss_authority` | 一个"外来"分支占住同 set 的另一 way（`FOREIGN_PC = PC+0x10000`，同 row 不同 tag），反馈位置与驻留分支相同 / 不同两种 |
| `test_main_service` | 旧冷源反馈一条保留记录，同 set 另有负向邻居 |
| `test_ahead_working_set` | 自然多分支工作集，逐拍比较 Main 方向提案与独立计划 |
| `test_sc_admission` | SC 队列反馈时读 Main 的 provider 计数 |
| `mbtb/test_semantic_reference` | `unhit_feedback_preserves_foreign_tag_direction[same-position]`、`coalesced_entry_reset_preserves_negative_conditional_peer[stale-metadata]` |
| `mbtb/test_depth_owner`、`test_full_capacity_learning` | 两键同 set，深度 0/1 改写 |

### 期望 vs 实际（原始观测）

```
# 两个 way 都被写
mask: expected 1, actual 3;  values.1: expected MISSING, actual 3

# 该写 way0，写成了 way1
[0].mask: expected 1, actual 2;  [0].values.0: expected 2, actual MISSING;
                                 [0].values.1: expected MISSING, actual 2

# 该写 way1，写成了 way0
mask: expected 2, actual 1;      values.1: expected 2, actual MISSING

# 模块单测里同一处：两个方向被写反
0.counter: expected 0, actual 2; 1.counter: expected 2, actual 0
```

观测点是 `counterWriteBuffer.io_enq_valid` / `io_enq_bits_{wayMask,counters}`
（只读绑定 `suites/frontend/bpu/bpu/bundle/main_service.py:37`）。

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbAlignBank.scala:258-261`

```scala
t1_meta.zipWithIndex.foreach { case (meta, i) =>
  val hitMask = t1_branches.map { branch =>
    branch.valid && branch.bits.attribute.isConditional && meta.position === branch.bits.cfiPosition
  }
                                                       // ↑ 只比位置，没有 meta.rawHit
```

### 为什么确定是 RTL 而不是测试写错

同一个文件里另外两处**都要求了 tag 命中**，只有计数更新漏了：

| 用途 | 代码 | 是否要求 tag |
|---|---|---|
| 表项写回 | `:220` `t1_hitMask` → `meta.hit(branch)`，而 `MainBtbMetaEntry.hit` = `rawHit && position ===`（`Bundles.scala:76-78`） | 是 |
| 替换器 touch | `:269-273` `t1_actualTakenMask` 含 `meta.rawHit` | 是 |
| **方向计数** | `:259-261` | **否** |

`meta.rawHit` 在 `:183` 已经由 `s2_rawHitMask(i) && io.enable` 正确生成，
信息是现成的。而且失败用例的名字就叫
`unhit_feedback_preserves_foreign_tag_direction`（未命中的反馈不该动外来 tag 的方向）。

### 建议修复

```scala
branch.valid && branch.bits.attribute.isConditional && meta.rawHit &&
  meta.position === branch.bits.cfiPosition
```

### 影响

方向被污染 → 后续预测的 taken / 目标 / 位置全错。`test_ahead_working_set` 的
`choice1.target 0x40020000→0x40010000`、`choice1.position 12→2` 就是这个的下游。

**功能点**：`BPU-INT-056/058/059/100`、`BPU-INT-029/030`、`BPU-MBTB-025~029`

---

## BPU-BUG-02 · 非条件分支被当成条件分支学方向

**模块**：MicroTAGE　**严重度**：高　**失败**：18

### 一句话

MicroTAGE 只预测"条件分支的方向"，是 AheadBTB 的纠错表。但它判断"这条分支该不该学"
时看的是 **AheadBTB 表里存的旧属性**，而不是**本次真正解析出来的分支属性**。
如果表里写的是"条件分支"、而实际解析出的是直接/间接跳转（位置相同），
MicroTAGE 照样给它 ±1。

### 场景

一个 PC 上先学了一个条件分支（表项 counter 升到 6）。之后同一 PC 同一位置，
真实解析出的是 `direct` 或 `indirect` 跳转。这个跳转不属于 MicroTAGE 的职责，
表项应该原样保留 6。

### 激励

`tests/utage/testcase/test_dual_source.py`，参数
`later-direct` / `later-indirect`（16 个参数化）：

- 预置两个热 provider：短表位置 2、长表位置 12 各学到 counter 6
- 解析出一笔分支，位置 12，taken=1，类型 `direct`（kind=2）或 `indirect`（kind=3）
- 随后重新查询，逐项比较 4 个槽的 `{position, base, valid, hit, provider, counter, taken}`

### 期望 vs 实际

```
2.counter: expected 6, actual 7        # 表项被 +1（饱和方向）
1.counter: expected 6, actual 7
```

另外 `utage/test_semantic_reference` 的
`resolved_nonconditional_same_position_preserves_warm_conditional[direct|indirect]`：

```
(0, 0): expected 1, actual 0            # 热的条件分支被非条件分支覆盖
```

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/MicroTage.scala:283`

```scala
val trainHasAbtbBranch = t0_abtbResult(i).valid &&
  (finalPrediction.cfiPosition >= t0_abtbResult(i).cfiPosition)
                                  // ↑ 只有位置关系
```

而 `t0_abtbResult(i).valid` 来自预测时写入 metadata 的条件过滤
（`:227-230`，用的是 `io.fromAheadBtb.result(i).bits.attribute.isConditional`，
即 **ABTB 表里存的旧属性**）。

于是 `actualTaken` 被算成 `(finalPosition === abtbPosition) && finalTaken` = 1，
`getUpdate(1)` → 6+1 = 7。

### 为什么确定是 RTL

参考模型的要求写在 `suites/frontend/bpu/utage/model/dual_source.py:91-96`：

```python
active = tuple(table for table, value in enumerate(before)
    if value.position < position or value.position == position and kind == 1)
```

即"同位置时，只有 kind==1（条件分支）才合格"。功能点规则名就叫
`same-position-nonconditional-is-ineligible`。而且**16 个失败全部集中在
`later-direct` / `later-indirect` 两类**，其余 1344 个参数全 PASS——精确对应。

### 建议修复

```scala
val trainHasAbtbBranch = t0_abtbResult(i).valid &&
  finalPrediction.attribute.isConditional &&
  (finalPrediction.cfiPosition >= t0_abtbResult(i).cfiPosition)
```

或者更严格：同位置时要求 `finalPrediction.attribute.isConditional`。

### 影响

MicroTAGE 表里出现"给跳转用的方向计数"，之后可能把 AheadBTB 的 taken 改判成
not-taken。`test_early_aging` / `test_early_direction` 的
`early_direction.2.hit` 反向差异很可能是同族（未最终确认）。

**功能点**：`BPU-UTAGE-025`

---

## BPU-BUG-03 · 刚写进缓冲的学习被自己清成"干净"，永远进不了 SRAM

**模块**：MicroTAGE（影子写缓冲 `BypassShadowBuffer`）　**严重度**：高　**失败**：17

### 一句话

写缓冲里有三条赋值都去改 `statusEntries[x].dirty`。当"清旧槽"和"写新槽"落在
**同一个槽号**时，Chisel 后写优先——**刚入队的新条目被清成"干净"**。
"干净"意味着不需要写回 SRAM，于是这条学习被直接跳过、永久丢失。

### 场景

短表（table 0）连续学习多个逻辑身份（固定 PC、不同折叠历史）。写缓冲只有 8 个槽，
学习速度超过 SRAM 写回时，入队指针会绕回、与"被合并的旧槽"撞号。

### 激励

| 用例 | 驱动 |
|---|---|
| `test_learning_persistence` | `retained-window`(8 条) / `first-retirement`(9 条)，三阶段 `short → allocate → reward → reward-again`，每条身份只在第一阶段写一次 |
| `test_predecessor_retention` | 6 个相位（allocate/reward/upper-protection/direction-boundary/saturated-reward/base-agreement），taken 与 not-taken 各一套 |
| `test_working_set`、`test_learning_retention`、`test_instruction_confidence`、`test_source_ownership` | 同类"多身份学习后回读 SRAM" |

### 期望 vs 实际

```
(1, 6).counter: expected 5, actual 4        # 少了一次 +1
(0, 384).counter: expected 7, actual 6
(0, 70).counter: expected 2, actual 3        # 该 -1 的没减
```

### 决定性证据：账本里有"发布了但从未被服务"的版本

每条失败记录都带模型账本，恒等式 `published − services` 就是**丢了几个版本**：

| 用例 | accepted | published | services | 丢 |
|---|---:|---:|---:|---:|
| `test_learning_persistence` | 24 | 24 | **23** | 1 |
| 同上 | 27 | 27 | **26** | 1 |
| `test_predecessor_retention` | 32 | 32 | **24** | 8 |
| 同上 | 16 | 16 | **15** | 1 |
| 同上 | 18 | 18 | **17** | 1 |

以 `test_learning_persistence` 为例：三阶段各写 8 条，前两阶段的
`actual_services` 分别是 8 和 16（**全部服务完**），所以第 3 阶段只服务了 7 条，
剩下那一条不可能"被更新的版本取代"——它就是丢了。而且丢的正好是计数偏低的那一格
`(1,6)`。

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/BypassShadowBuffer.scala:246-253`

```scala
when(io.writeSuccess) {
  statusEntries(deqPtr.value).dirty := false.B
}
when(t1_hasWrite) {
  statusEntries(enqPtr.value).valid := true.B
  statusEntries(enqPtr.value).dirty := true.B        // ← 新条目置脏
}
when(t1_hasWrite && t1_hasHit) {
  statusEntries(t1_cleanId).dirty := false.B         // ← 后写优先，可能清掉刚置脏的那个
}
```

`t1_cleanId ∈ 0..7`，与 `enqPtr.value` 同域（`numEntry = 8`，`:51`）。
`t1_cleanId === enqPtr.value` 时新条目当拍变"干净"。

后果链：

```scala
io.tryWrite.valid := statusEntries(deqPtr.value).valid && statusEntries(deqPtr.value).dirty   // :262 恒 0
when(io.writeSuccess || (!statusEntries(deqPtr.value).dirty && !isEmpty)) {
  deqPtr := deqPtr + 1.U                                                   // :243 直接跳过
}
```

→ 这条学习既不写 SRAM，也不留任何痕迹。

次要问题（同一处）：`t1_cleanId` 的选择是

```scala
// :151-153
Mux(t0_chosenFirst, ~PriorityEncoder(t0_firstHit.reverse), ~PriorityEncoder(t0_entryHit.reverse))
```

同 index 在缓冲里有多份时取的是**索引最小**的槽，而不是 `priorityMask` 选中的
最老槽，也会清错槽。

### 为什么确定是 RTL

模型侧 `suites/frontend/bpu/utage/model/persistence.py:63-77` 只接受"被服务版本不得回退、
服务必须对应已发布版本"，且 `finish_phase(persistent=True)` 会断言
"每个原始身份的最新学习必须已经落盘"。也就是说：**同一套账本在别的模块
（如 SC、TAGE）能通过，只有 UTAGE 短表对不上**。

### 建议修复

1. `t1_cleanId =/= enqPtr.value` 时才可以清脏；
2. 或者把置脏改成"清脏之后"（调整 `when` 顺序，把 `t1_hasWrite` 的置脏放最后）；
3. `t1_cleanId` 应取 `priorityMask` 选中的最老槽，而不是 `PriorityEncoder` 最小号。

### 影响

学习丢失 → SRAM 里是旧方向 → 后续预测方向错。这是 `BPU-UTAGE-016` 已经登记的
缺陷（"112 个失败格"），本报告把它变成了**可计数的 `published − services` 见证**。

**功能点**：`BPU-UTAGE-016`（strict XFAIL 范围）

---

## BPU-BUG-04 · RAS 关掉后投机栈仍在推入/弹出

**模块**：RAS（`Ras` / `RasStack`）　**严重度**：高　**失败**：5

### 一句话

关闭 RAS（`io.enable = 0`）时，`spec.fire` 被门控了，但 `pushValid` / `popValid`
没有门控，而 `RasStack` 的投机栈更新**只看 pushValid/popValid、不看 fire**。
结果：**RAS 关了，栈指针和恢复元数据照样在动。**

### 场景

`io.enable = 0` 时来一条 CALL（或 RET）。期望：什么都不发生。
实际：`ssp/tosr/tosw` 前进，`committed` 组的 calls 计数 +1，重定向元数据带上错的
栈状态。

### 激励

`tests/ras/testcase/test_coverage.py` 的
`test_ras_functional_coverage_closes_defined_bins`，
事件为 `Events(action=2, address=0x8000_07D0, enabled=False, reset=False)`；
以及 `test_semantic_reference` 的
`test_speculative_return_and_call_replaces_only_the_youngest_frame`、
`test_recovery_return_and_call_restores_before_redo`、`test_commit_action`。

### 期望 vs 实际

```
# enable = 0 却发生了 push
group: expected 0, actual 1;  calls: expected 0, actual 1
commit_group: expected 0, actual 1;  commit_calls: expected 0, actual 1

# 启用后栈深度错了一位
top: expected 536877060 (0x2000_0784), actual 536875012 (0x2000_0704)
calls: expected 3, actual 2;  commit_calls: expected 3, actual 2

# 提交栈里的保留地址错
retained_groups[2][0]: expected 1073754120, actual 1073750024
```

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/Ras.scala:71-74`

```scala
stack.spec.pushValid := specPush && !stackNearOverflow     // ← 没有 && io.enable
stack.spec.popValid  := specPop  && !stackNearOverflow     // ← 没有 && io.enable
stack.spec.fire      := io.specIn.valid && io.enable       // 只有 fire 有
```

`XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/RasStack.scala:317-323`

```scala
when(io.spec.pushValid) { specPush(io.spec.pushAddr, ssp, sctr, tosr, tosw, topEntry) }
when(io.spec.popValid)  { specPop(ssp, sctr, tosr, tosw, topNos) }
```

**更新不看 `io.spec.fire`。** 所以 `enable=0` 时栈照动。

### 为什么确定是 RTL

同一文件里 `stack.redirect.valid`（`:98`）、`commitValid`（`:105`）都带了
`&& io.enable`，只有 spec push/pop 漏了。这是同一模块内的**不一致**，
不是测试假设。

### 建议修复

```scala
stack.spec.pushValid := specPush && !stackNearOverflow && io.enable
stack.spec.popValid  := specPop  && !stackNearOverflow && io.enable
```

或者在 `RasStack` 里把 `when(io.spec.pushValid)` 改为
`when(io.spec.pushValid && io.spec.fire)`（需要同时把 fire 传进 Stack IO）。

### 影响

RAS 关闭/切换时栈被污染；之后重新启用就是错的栈。`redirectMeta` 带着错的
`ssp/tosr/tosw`，重定向恢复会把错误状态"还原"回来。

**功能点**：`BPU-RAS-017`、`BPU-RAS-008`

---

## BPU-BUG-05 · MicroRAS 完全不理会 enable

**模块**：MicroRAS（`MicroRas`）　**严重度**：高　**失败**：4

### 一句话

`MicroRas.scala` **全文没有任何一处引用 `io.enable`**。它无条件输出
`isCanUse = 1` 和一个投机返回地址。上层把 `uras.io.enable` 接好了，
但消费端不看 `ctrl.rasEnable`，于是 **RAS 关闭时 RET 仍被 MicroRAS 改向**。

### 场景

`ctrl.rasEnable = 0`。一条 RET 进来。期望：没有可用的返回目标（`usable=0`）。
实际：`usable=1`，并且给出一个具体地址。

### 激励

`tests/uras/testcase/test_enable_gate.py` 的
`test_disabled_micro_ras_withholds_the_armed_return_target`；
以及 `test_semantic_reference` 的三个程序
`test_return_and_call_replaces_top_instead_of_becoming_neutral`
（`pending-correction` / `speculation` / `retiring-correction`）。

### 期望 vs 实际

```
usable: expected 0, actual 1;  target: expected MISSING, actual 0x4000_0A64
target: expected 0x4000_088C, actual 0x4000_0064      # 投机配对错
target: expected 0x4000_088C, actual 0x4000_4C96      # retiring 场景更偏
```

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/MicroRas.scala`

```scala
// :242 —— 无条件输出
io.specOut.isCanUse  := isCanUse
io.specOut.retTarget := topRetAddr
```

`grep -n "enable" MicroRas.scala` → **无任何输出**。

而 `BasePredictorIO` 明确提供该输入（`Abstracts.scala:35`），
同目录其它预测器都以它门控（`AheadBtb.scala:93/114/116`、`Ras.scala:74`）。

上层：

```scala
// Bpu.scala:101
uras.io.enable := ctrl.rasEnable && ctrl.mbtbEnable
// 但消费端（:284 / :321 / :551 / :557）直接用 uras.io.specOut.isCanUse
```

### 为什么确定是 RTL

参考模型 `suites/frontend/bpu/uras/model/semantic.py:148-152` 明确：

```python
# A disabled MicroRAS must not expose a usable return target.
if not events.enabled:
    self.result = UrasResult(0, 0)
```

而且"模块有 enable 端口却完全不用"属于典型**死开关**，
ICache 验证经验里这是必查项。

### 建议修复

```scala
io.specOut.isCanUse  := isCanUse && io.enable
io.specOut.retTarget := Mux(io.enable, topRetAddr, 0.U.asTypeOf(GuardedPc()))
```

若要连内部状态一起冻结，还需把 `s2_hasPush/s3_hasPop/...` 的更新也加 `io.enable`。

### 影响

RAS 关闭无效；MicroRAS 的投机栈顶会覆盖主 RAS 的返回预测。
`test_semantic_reference` 的三个 target 差异是投机 push/pop 配对
（`MicroRas.scala:170-245` 的 `s2_hasPush/s3_hasPop` 组合）在 enable 之外的
**第二处问题**，对应已登记的 `BPU-URAS-017`。

**功能点**：`BPU-URAS-016`、`BPU-URAS-017`

---

## BPU-BUG-06 · 多命中清理把该保留的那一条也清零

**模块**：MainBTB（`MainBtbAlignBank` + `MainBtbInternalBank`）　**严重度**：中高　**失败**：7

### 一句话

一处 set 里出现多命中（同位置的两条分支）要清理掉多余的那条。代码把
**整个命中集合**都写成了全零，包括本来应该留下当幸存者的那一条。

### 场景

同 set 两条分支位置相同 → `detectMultiHit` 发现多命中 → 需要保留一条、清掉另一条。
实际两条都被清成 tag=0/position=0/kind=0。

### 激励

`tests/bpu/testcase/test_main_duplicate_cleanup.py`（4 个参数：
neighbor-already-learned / neighbor-learns-now × 两个顺序），
以及 `mbtb/test_semantic_reference` 的
`test_duplicate_clear_owns_destination_not_zero_payload_key[zero-tag-and-position]`、
`mbtb/test_shared_service` 的
`test_capacity-safe_distinct_target_correction_and_invalidation_both_service_exactly_once`。

### 期望 vs 实际

```
row: expected 3, actual 1;  position: expected 3, actual 0;
kind: expected 3, actual 0;  offset: expected 6752, actual 0
value: expected True, actual False           # 幸存者不再有效

# 模块单测：被清零的正是应该保留的那一条
0.valid: expected 1, actual 0; 0.raw_hit: expected 1, actual 0;
0.meta_kind: expected 3, actual 0

# 服务侧的 tag 也变成 0
[1]: expected {... 'tag': 1, 'position': 5 ...}, actual {... 'tag': 0 ...}
```

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbAlignBank.scala:295-297`

```scala
b.io.flush.req.valid        := s2_fire && s2_multiHitMask.orR && s2_internalBankMask(i)
b.io.flush.req.bits.wayMask := s2_multiHitMask        // ← 整个命中集，含幸存者
```

`XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbInternalBank.scala:176-190`

```scala
val flushValid = flush.req.valid && flush.req.bits.wayMask(i) && !conflict
bufWrite.bits.entry := RegEnable(
  Mux(writeValid, writeEntry.req.bits.entry, 0.U.asTypeOf(new MainBtbEntry)), valid)
                                             // ← 清理 = 写全零 Entry
```

`s2_multiHitMask` 包含**所有**命中 way。AheadBTB 侧有 `multiHitWayIdx` 概念
（只清重复项），MainBTB 侧没有对应处理。

### 为什么确定是 RTL

功能点 `BPU-MBTB-026` 的文字就是"重复清理与不同记录训练同拍时，**清除不吞掉另一身份**"，
`BPU-MBTB-029` 是"重复清理拥有目的地而不是零 payload key"。
失败签名正是"幸存者变成 0 payload"。

### 建议修复

清理掩码改成 `s2_multiHitMask & ~(1 << keeper)`，keeper 由
`PriorityEncoderOH(s2_multiHitMask)` 或 replacer 的 recency 选出。

### 影响

一次多命中会把两条分支都删掉 → 后续全部 miss → 预测精度与目标都错。

**功能点**：`BPU-MBTB-026`、`BPU-MBTB-029`

---

## BPU-BUG-07 · 没发布过的预测也会分配 ITTAGE 表项

**模块**：ITTAGE（`Ittage`）　**严重度**：中高　**失败**：4

### 一句话

ITTAGE 训练只看"有一笔训练 + t0 拍有效"，**不检查这笔原始预测是否真的被发布过**
（是否被选为最终预测）。于是对被更年轻请求取代的原始预测，也会执行分配，
凭空生出指向旧目标的 provider。

### 场景

一个原始间接预测被更年轻的请求取代（没有发布）。它的反馈迟到。
期望：不产生任何 provider / 命中。实际：分配了新表项，`hit=1`，目标还是旧的。

### 激励

`tests/ittage/testcase/test_late_source_qualification.py` 的
`test_late_feedback_for_an_unpublished_original_does_not_create_a_target`，
以及 `test_semantic_reference` 的
`test_zero_confidence_retarget_preserves_full_region_without_new_table[existing-region|new-region]`，
集成侧 `tests/bpu/testcase/test_late_source_qualification.py`。

### 期望 vs 实际

```
hit: expected 0, actual 1;  provider_valid: expected 0, actual 1
provider_target: expected 0x4100_0200 (1090524160), actual 0x4001_6C00 (1073746944)
target:          expected 0x4100_0200, actual 0x4001_6C00
ittage_metadata.provider.valid: expected 0, actual 1
```

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/ittage/Ittage.scala:167`

```scala
private val updateValid = hasTrainBranch && RegNext(t0_fire, init = false.B)
```

`updateValid` 不含"原始预测曾被发布"的限定。而分配逻辑在 `:381`：

```scala
when(updateValid && updateMisPred && !(providerCorrect && providerUnconf)) {
  ...
  when(allocate.valid) {
    updateMask(allocate.bits)     := true.B
    updateAlloc(allocate.bits)    := true.B
    updateTargetOffset(allocate.bits) := updateRealTargetOffset
  }
}
```

`allocate` 来自 `s2_allocatableSlots`（`:300-306`），是独立选出来的，
所以会凭空造出一个指向 `updateRealTargetOffset` 的表项。

### 为什么确定是 RTL

功能点要求是"late feedback does not create a target for an unpublished original"。
判别点：如果只是模型过严，那么同族用例（已发布版本）应当也失败；
实际上只有"未发布"这一族失败，已发布的全部 PASS。

### 建议修复

给 `updateValid`（或 `allocate` 的使用条件）增加"该原始预测已在 s1/s2 被选中/发布"
的限定，例如 `t1_meta.valid`（metadata 有效）或对应的 `s1_prediction.valid`。

### 影响

ITTAGE 表被过期目标污染，之后间接跳转预测到旧地址。

**功能点**：`BPU-ITTAGE-017`、`BPU-ITTAGE-019`、`BPU-ITTAGE-020`

---

## BPU-BUG-08 · 一次 not-taken 会复活已死亡的条目

**模块**：MicroBTB（`MicroBtb`）　**严重度**：高　**失败**：2

### 一句话

命中一个"已经死掉"（`usefulCnt = 0`）的条目、而本拍实际是 **not-taken** 时，
代码会把整个条目**重新装填**：写 tag/位置/属性/目标、`isStaticTarget := true`、
清掉第二个槽、把 `usefulCnt` 重置为强正。
**一次 not-taken 不应该产生任何分配。**

### 场景

s1 命中一条老化到 `usefulCnt = 0` 的条目；本拍该分支是 fallthrough（不跳）。
期望：条目保持死亡（`valid=0`）。实际：被复活成有效条目并带上训练目标。

### 激励

`tests/ubtb/testcase/test_contiguous_training.py` 的
`test_fallthrough_does_not_revive_a_dead_entry_with_its_target`，
以及 `test_semantic_reference` 的
`test_contiguous_fallthrough_does_not_reallocate_a_dead_entry[consecutive]`。

### 期望 vs 实际

```
valid: expected 0, actual 1;  taken: expected MISSING, actual 1;
target: expected MISSING, actual 0x8000_2A10;  position: expected MISSING, actual ...
valid: expected 0, actual 1;  target: actual 0x8000_2A30
```

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/ubtb/MicroBtb.scala:203-207`

```scala
}.elsewhen(!t1_hitAttributeSame || !t1_hitPositionSame || !t1_hitTargetSame || !t1_actualTaken) {
  initEntryIfNotUseful(t1_hitNotUseful)     // ← 条件里含 !t1_actualTaken
```

而 `initEntryIfNotUseful`（`:183-194`）在条件为真时**重装整条**：

```scala
private def initEntryIfNotUseful(notUseful: Bool): Unit =
  when(notUseful) {
    t1_updatedEntry.tag := t1_tag
    t1_updatedEntry.usefulCnt.resetSaturatePositive()
    t1_updatedEntry.slot1.position  := t1_position
    t1_updatedEntry.slot1.attribute := t1_attribute
    t1_updatedEntry.slot1.target    := t1_target
    t1_updatedEntry.slot1.isStaticTarget := true.B
    t1_updatedEntry.slot2.valid := false.B
  }.otherwise {
    t1_updatedEntry.usefulCnt := t1_hitEntry.usefulCnt.getDecrease()
  }
```

于是"命中死条目 + fallthrough"这条常见路径触发了重装。

### 为什么确定是 RTL

`t1_allocate := !t1_hit && t1_actualTaken`（`:217`）——**真正的分配只在 taken 时**。
而 `initEntryIfNotUseful` 在 not-taken 时也会重装，两者语义矛盾。
功能点 `BPU-UBTB-011` 的名字就是"fallthrough 不能复活死条目"。

### 建议修复

```scala
}.elsewhen(!t1_hitAttributeSame || !t1_hitPositionSame || !t1_hitTargetSame || !t1_actualTaken) {
  initEntryIfNotUseful(t1_hitNotUseful && t1_actualTaken)
```

### 影响

死条目被 not-taken 复活并带错误目标 → 下次命中就预测到错地址。

**功能点**：`BPU-UBTB-011`

---

## BPU-BUG-09 · 目标纠正写到同位置同属性的另一条

**模块**：AheadBTB（`AheadBtb`）　**严重度**：中　**失败**：1

### 一句话

纠正间接分支目标时，用 `t1_hitMask` 选目的地，而 `t1_hitMask` 只比
`position + attribute`、**不比 tag**。同 set 里有"同位置同属性"的两条时，
`PriorityEncoderOH` 会选到较低位的 way，纠正写到错的目的地，**原目的地保留旧目标**。

### 场景

同 set 两条间接分支，位置与属性相同、tag 不同（`distinct-destinations`）。
其中一条解析出新的目标，需要纠正。

### 激励

`tests/abtb/testcase/test_semantic_reference.py` 的
`test_pending_target_corrections_preserve_destination_ownership[distinct-destinations]`。

### 期望 vs 实际

```
0.target: expected 1073744320 (0x4000_0140), actual 1073744256 (0x4000_0100)
0.target_low: expected 2496, actual 2432
```

差值 64 字节 = 一个 fetch 块内两个 32B 半块的距离，即"写到了另一条同位置条目"。

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/abtb/AheadBtb.scala:284-286`

```scala
private val t1_hitMask = t1_meta.entries.map { e =>
  e.hit && e.position === t1_trainPosition && e.attribute === t1_trainAttribute
}                                                // ← 无 tag 比较
```

`:348-354` 用它选写回 way：

```scala
}.elsewhen(t2_fire && t2_needCorrectTarget && t2_bankMask(i)) {
  b.io.writeReq.bits.wayIdx := OHToUInt(t2_hitMaskOH)     // ← 可能选到另一条
```

`:288` 读纠正源也用它：

```scala
private val t1_predictInfo = Mux1H(t1_hitMaskOH, t1_meta.entries)
```

### 置信度：中

与 BPU-BUG-01 是**同一类**（匹配缺 tag）。但这里还没做到"把 `t1_hitMask` 加 tag 后
复跑验证"。所以标为中等置信度——**代码形态和签名吻合，但未做判别实验**。

### 建议修复

```scala
private val t1_hitMask = t1_meta.entries.map { e =>
  e.hit && e.tag === t1_trainTag && e.position === t1_trainPosition &&
    e.attribute === t1_trainAttribute
}
```

（需确认 `t1_trainTag` 在该处可得；`t1_train.startPc` 派生即可。）

### 影响

纠正写到错误的表项 → 该条目标永远修不好，另一条被污染。

**功能点**：`BPU-ABTB-053`

---

## 附录 A · 这 9 条解释了多少

| ID | 失败数 | 主要用例 |
|---|---:|---|
| 01 | 28 | `test_ahead_working_set`(8)、`test_main_cold_original_order`(8)、`mbtb/test_full_capacity_learning`(4) 等 |
| 02 | 18 | `utage/test_dual_source`(16)、`utage/test_semantic_reference`(2) |
| 03 | 17 | `utage/test_predecessor_retention`(8)、`test_learning_persistence`(3) 等 |
| 04 | 5 | `ras/test_semantic_reference`(3)、`test_coverage`、`test_commit_action` |
| 05 | 4 | `uras/test_semantic_reference`(3)、`test_enable_gate` |
| 06 | 7 | `test_main_duplicate_cleanup`(4)、`mbtb/test_shared_service`(2) 等 |
| 07 | 4 | `ittage/test_semantic_reference`(2)、两个 `late_source_qualification` |
| 08 | 2 | `ubtb/test_contiguous_training`、`ubtb/test_semantic_reference` |
| 09 | 1 | `abtb/test_semantic_reference` |
| **合计** | **86** | |

## 附录 B · 剩下的 37 个

| 类别 | 数 | 说明 |
|---|---:|---|
| 参考模型缺陷 | 10 | TAGE 写提案用了预测时的旧计数（`suites/frontend/bpu/tage/model/semantic.py:528`）。三方对照：程序计划 5、独立计划 5、**DUT 实际 5**、模型 4 |
| 断言映射假设未定案 | 8 | `test_owner_recency` / `test_retouch_replacement`：模型按"保留槽序号"索引，RTL 按写缓冲分配序，映射未验证 |
| 流水线级联 | 19 | `choice/flush/history/folded` 差异。差异的量与"方向判反 → 分支未被执行 → 历史少推一位"一致，但共用同一套模型，**需修完上面 9 条后复跑才能定案** |

## 附录 C · 怎么复现

```bash
# 1) 单簇复现（任选）
python3 tests/run_all.py --workers 4 \
  --run-dir results/repro-bug01 --select tests/bpu/testcase/test_main_cold_original_order.py
python3 tests/run_all.py --workers 4 \
  --run-dir results/repro-bug03 --select tests/utage/testcase/test_learning_persistence.py

# 2) 看失败签名（JUnit 里带完整期望/实际与账本）
grep -A20 'differences' results/repro-bugNN/pytest.xml
```

复现纪律（与 ICache 验证经验一致）：

- 运行前用 `tools/run_cost.py --select <path>` 预览，别把小时级用例混进秒级定向；
- 运行期间**冻结工作树**，结束后用 `--epoch-delta` 核对 `changed=0`；
- 选测结果**不替代**全量回归。

## 附录 D · 本轮边界

- **未修改任何 RTL**：`git diff <原始提交> -- src/main/scala/` 为空。
- **未做 RTL 生成**、**未运行任何回归**；DUT 二进制仍是 2026-10-12 那份。
- 123 个 FAIL 与 7 个 XFAIL 全部原样保留，没有放宽、没有跳过。
- 所有"实际值"来自 memory-direct 只读观测；没有写内部状态、没有伪造 metadata。
