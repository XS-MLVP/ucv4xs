# BPU 失败用例的 Scala 根因定位（2026-10-22，只读分析）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


> 依据一次全量回归 `results/full-regression-20261022-v1`（29907 用例，123 FAIL / 7 XFAIL）。
> **本文只做定位，不修改任何 RTL，也没有运行 RTL 生成或回归。**
> 每条结论都给出 `文件:行` 与触发条件；分三档：已确认 RTL 缺陷 / 参考模型缺陷 / 已登记已知项。

## 汇总

| 分类 | FAIL 数 | 结论 |
|---|---:|---|
| A. MainBTB 方向计数更新缺少 tag 命中限定 | ~17 | **已确认 RTL 缺陷**（单点根因） |
| B. TAGE 写入提案用了过期的预测时计数 | ~10 | **参考模型缺陷**（DUT 与独立计划一致） |
| C. 已登记的已知差异 | 26 | UTAGE-016 / 021 / 025 |
| D. 尚未定位 | ~70 | 见第四节，给出每簇的判别问题 |

---

## 一、A 类：`MainBtbAlignBank.scala:260`（已确认）

### 现象（三处不同签名，同一机制）

| 用例 | 检查器报的差异 | 含义 |
|---|---|---|
| `test_ahead_working_set`（8） | `mask: expected 1, actual 3; values.1: expected MISSING, actual 3` | 期望只更新 1 个 way，DUT 更新了 **2 个** |
| `test_main_cold_original_order`（8） | `[N].mask: expected 1, actual 2; values.0: expected 2, actual MISSING; values.1: actual 2` | 期望更新 way0，DUT 更新了 **way1** |
| `test_main_service`（1） | `mask: expected 2, actual 1` | 期望 way1，DUT 更新了 **way0** |

三者的观测点相同：`MainBtbInternalBank.counterWriteBuffer.io_enq_valid/bits`
（`suites/frontend/bpu/bpu/bundle/main_service.py:37` 把 `direction` 绑到这里）。
检查器在 `test_ahead_working_set` 里的断言文案直接点了题：
*"Main direction proposal requires original hit and selected allocation ownership"*。

### 根因

`XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbAlignBank.scala:259-261`：

```scala
val hitMask = t1_branches.map { branch =>
  branch.valid && branch.bits.attribute.isConditional && meta.position === branch.bits.cfiPosition
}
```

方向计数器是**表项自己的属性**，但这里只用 7 位 `position` 做匹配，**没有要求
`meta.rawHit`（tag 命中）**。同一 set 的另一个 way 若属于别的分支块而 `position` 恰好
相等，就会被当成命中：

- 若外来 way 也在同一 set → 两个 way 都被写（`mask=3`）；
- 若外来 way 先被扫到、而真正命中的 way 的 `position` 不同 → 只写外来 way
  （`mask=2`，`way0`→`way1` 互换）；
- 反之同理（`mask=1`，`way1`→`way0`）。

同一文件里的另外两处**都要求了 tag 命中**，只有计数更新漏了：

| 用途 | 代码 | 是否要求 tag |
|---|---|---|
| 表项写回 | `MainBtbAlignBank.scala:220` `t1_hitMask = PriorityEncoderOH(... meta.hit(t1_mispredictInfo.bits))`，而 `MainBtbMetaEntry.hit` = `rawHit && position === branch.cfiPosition`（`Bundles.scala:76-78`） | **是** |
| 替换器 touch | `MainBtbAlignBank.scala:269-273` `t1_actualTakenMask` 含 `meta.rawHit` | **是** |
| **方向计数更新** | `MainBtbAlignBank.scala:259-261` | **否** ← 缺陷 |

### 为什么这是真缺陷而不是测试假设错

- 计数器的语义是"这个分支的方向历史"，它挂在具体表项（tag）上；把一个分支的结果
  写进另一个块的表项，会同时污染两个身份：真身分没学到，外来身份被凭空改动。
- 该 set 的读出来自 `t1_train.meta.mbtb`，`meta.rawHit` 在
  `MainBtbAlignBank.scala:183` 已由 `s2_rawHitMask(i) && io.enable` 正确生成，信息是可得的。
- 后续预测会读到被污染的计数，从而改变 `taken` 与目标/位置，因此也会表现为
  `choice1.target/position` 差异（`test_ahead_working_set` 的另一半签名）。

### 影响面

A 类解释了 17 个 FAIL；此外 `test_main_duplicate_cleanup` 的
`row: expected 3, actual 1; position: expected 3, actual 0; kind: expected 3, actual 0`
（DUT 写了一个 `position=0, kind=0` 的占位条目）**不符合**本机制，单独归入 D 类。

---

## 二、B 类：`suites/frontend/bpu/tage/model/semantic.py:528`（参考模型，不是 RTL）

### 现象

`test_opposed_learning_pair`（7）+ `test_direction_turnaround`（3）：
`value: expected 5, actual 4`，断言点是
*"each current result has its own latest version and service obligation"*
（`suites/frontend/bpu/bpu/checker/mixed_visibility.py:210`）。

同一条失败记录里还有：

- `expected_pending`（由程序独立推出）= `counter 5`
- `independent_pending` = `counter 5`
- `latest_actual_state.writes[0].bits.counter`（**DUT 实际提案**）= `5`
- `actual = pending_plan(...)`（**参考模型缓存**）= `4`

即：**DUT 与独立计划都是 5，只有参考模型的缓存是 4。**

### 根因

`suites/frontend/bpu/tage/model/semantic.py`：

```scala
526:                current = counter if latest is None else latest.write.entry.counter
...
528:                proposal = clamp(counter + (1 if branch.taken else -1), 7)
```

`current`（已考虑同 way 待写版本的最新值）只用于判断"要不要写"，真正写进缓存载荷的
`proposal` 却仍用预测时读到的 `counter`。当同一 way 已有一个待写版本时，
新版本的载荷会退回旧值，缓存因此停在 4，而 DUT 的写缓冲合并后是 5。

**判别**：这不是 RTL 缺陷——DUT 与两条独立推导（程序计划、独立 pending 计划）一致，
唯一不一致的是模型自身的 `proposal` 取值。

---

## 三、C 类：已登记的已知差异（26 个）

| 用例簇 | FAIL | 关联功能点 | 已有结论 |
|---|---:|---|---|
| `test_dual_source`（仅 `later-direct` / `later-indirect`） | 16 | `BPU-UTAGE-025` | 已登记真实差异 |
| `test_predecessor_retention` | 8 | `BPU-UTAGE-016`（strict XFAIL：ring 槽清 dirty） | 已登记 |
| `test_learning_persistence` | 3 | `BPU-UTAGE-016` | 同上 |
| `test_working_set` | 2 | `BPU-UTAGE-021` | 同上（被 007 阻断） |
| `test_instruction_confidence` | 2 | `BPU-UTAGE-021` | 同上 |

这些**不是新 Bug**，但它们的失败签名（`counter expected 7 actual 6`、
`expected 6 actual 7`）与 UTAGE-016 的 dirty 清槽机制一致，不应另立功能点。

> 注意：`test_dual_source` 的 16 个失败**全部**落在 `later-direct`/`later-indirect`
> 两个结果上，其余 1344 个参数全 PASS。这是"同一机制、特定结果"的形态，
> 与 UTAGE-025 的已登记范围吻合。

---

## 四、D 类：尚未定位（按簇给出判别问题）

| 用例簇 | FAIL | 首个差异 | 下一步要回答的唯一问题 |
|---|---:|---|---|
| `test_ahead_working_set`（choice 签名） | 4/8 | `choice1.target/position` | 与 A 类同源（被污染计数改变 taken 与目标），修 A 后再看 |
| `test_owner_recency` + `test_retouch_replacement` | 8 | `row 72 tag 3264` vs `row 122 tag 1986` | 参考模型的 `read.rows/entries` 快照与 RTL 写缓冲的 slot 归属是否用了同一 rank 顺序？（`checker/retouch_replacement.py:74` 的 `retained[owner][rank]` 假设） |
| `test_main_duplicate_cleanup` | 4 | `row 3→1, position 3→0, kind 3→0`；`value True→False` | 多命中清理路径是否把真实条目替换成了 `0.U.asTypeOf(new MainBtbEntry)` 占位（`MainBtbInternalBank.scala:176-190` 的 flush 分支） |
| `test_cold_source_isolation` / `test_common_history` | 4 | `ghr/bw`、`choice/repair` | PHR/CommonHR 在冷源被禁用时是否仍推进 |
| `test_confidence_boundary` / `test_miss_authority` | 4 | 数组元素与 `value` | TAGE useful/altConf 的边界值与模型 `isWeak` 定义是否同源 |
| `test_sc_admission` / `test_sc_early_learning` | 4 | `main_metadata.counter`、`tage altOrBasePred` | SC 与 TAGE 在同一拍的 provider 计数是否取自同一次读 |
| `test_main_dynamic_target` / `test_main_sibling` | 4 | `flushes/repair/choice target` | 间接目标纠正与未执行兄弟分支的可见性 |
| `test_early_aging` / `test_early_direction` | 2 | `early_direction.hit`、`raw_hits` | UTAGE 老化与早级可见性 |
| `test_read_ownership` | 1 | `hits[0]: expected 0, actual 1` | 同一 index 的新写在途时，旧查询是否应看到"未命中"（`BPU-UTAGE-006`） |

我**没有**对这些簇给出根因结论——目前只有失败签名，还不足以区分"RTL 缺陷 /
参考模型 / 测试假设"。把猜测写成根因正是过去几轮已经犯过的错
（TAGE bucket 4/6 被误判为"不可达"）。

---

## 五、约束与状态

- **未修改任何 RTL**；**未运行 RTL 生成**；**未运行任何回归**。
- 本文所有数字来自已完成的全量运行 `results/full-regression-20261022-v1`。
- 123 个 FAIL 与 7 个 XFAIL 全部原样保留，没有放宽或跳过。
