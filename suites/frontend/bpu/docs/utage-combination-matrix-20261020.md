# UTAGE 组合矩阵与检查器审计（2026-10-20）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


> 方法来自上层 ICache 验证经验：缺陷常住在两条路径的**同拍交叉处**，而功能点、
> 模型和覆盖率都按路径组织。本文件按输入来源把 UTAGE 的交叉格逐项列出，给出
> 已有用例/证据，或显式登记“未验证”及原因；同时复核检查器是否存在全局静音、
> 死字段、死开关与按电平计数。

## 一、输入来源分组

| 组 | 来源 | 公开端口/驱动 |
|---|---|---|
| A | 正常查询（A0/A1 两拍流水） | `io.startPc`、`io.normalPathHist`、`io.fromAheadBtb` |
| B | FastTrain 反馈（单拍/相邻多拍） | `io.fastTrain` |
| C | 保护老化 | `lowTickCounter` / `highTickCounter`（内部只读） |
| D | 使能门控 | `io.enable` |
| E | 重定向 | `io.redirect` |
| F | S2/S3 恢复快照 | `io.bpuS2Override` / `io.bpuS3Override` |
| G | 单端口 SRAM 读/强制写回冲突 | `io.req` 与 `tryWrite.forceWrite` |
| H | Shadow 环满/回绕/同槽复用 | `BypassShadowBuffer` 内部 |
| I | 两张表同拍更新 | `MicroTageTable` ×2 |
| J | 复位 | `reset` |

## 二、同拍交叉格

| 格 | 组合 | 用例/证据 | 判定 |
|---|---|---|---|
| A×B | 查询与反馈同拍，且读同一索引 | `test_read_lifetime` 的 `read-with-write` 关系；`read_shadow_contexts` | **已覆盖**：读返回原版本或经 bypass 的新版本，模型比较完整预测 |
| A×A | 背靠背/重叠查询 | `test_pipeline_positions`、`test_adjacent_feedback`、`test_query_cohort` | **已覆盖**：三拍响应按请求关联；每笔 Transfer 独立 |
| A×F | 查询与 S2/S3 恢复快照 | `test_override.py`（顺序）、`test_override_with_inflight_feedback.py` | **已覆盖**：恢复在反馈落地前提交时必须重放快照（ctr 5/taken 1），而同一程序的 fresh 查询看到新状态（ctr 3/taken 0）；两者不同才证明未重读当前候选 |
| A×G | 查询与单端口 SRAM 强制写回 | `test_write_pressure_bank.py`（`BPU-UTAGE-027`） | **部分覆盖**：压力可达且同 bank 读仍返回正确条目；SRAM-only 条目被冲突压掉的最强形式仍未构造 |
| B×B | 相邻反馈写入同一环 | `test_shadow_ring`、`test_aging_learning` | **已覆盖**（并有已知持久化缺陷，见 016） |
| B×C | 同拍维护与学习 | `test_aging_learning`（真实分配失败 → 相邻原反馈 → 维护/学习同拍） | **已覆盖**：`60` 个 cross bin 在断言后闭合 |
| B×D | 禁用边界与在途学习 | `test_enable_lifetime`、`test_enable.py` | **已覆盖**：禁用期间不新增可见效果，重开后保留原状态 |
| B×I | 同一反馈更新两张表 | 所有反馈用例 | **已覆盖**：每笔反馈同时教导低/高表 |
| B×H | 反馈与 Shadow 环满/回绕/同槽复用 | `test_shadow_ring`（8 槽回绕）、`test_working_set`（32/512 上下文） | **已覆盖**（相邻模式有已知 016/工作集失败，保留普通 FAIL） |
| A×H | 查询与环内新写入同索引 | `same_index_bypass` 相位 | **已覆盖**：新写入优先于旧 meta |
| A×E | 查询与重定向同拍 | 无 | **未覆盖（见三）** |
| A×G | 查询与单端口 SRAM 强制写回同 bank | 无 | **未覆盖（见四）** |
| C×D | 老化与启用/禁用同拍 | `test_low_tick_reset`、`test_enable_lifetime` | **部分覆盖**：低 tick 复位与使能分别有检查；同一拍老化+禁用的组合未单独构造 |
| J×任何 | 复位与在途事务 | `agent.reset()` 在每程序开头；`reset_pending` 清空观测 | **已覆盖**：复位期间的事务被丢弃并重建模型；复位后的 dense useful 比较 |
| F×I | 恢复快照中 slot 2 采用上表选择 | `test_override_upper.py` 的 `..._from_a_nonzero_slot[s2|s3]`（`BPU-UTAGE-008/009`） | **已覆盖**：真实三分支 beat `(2,4,6)` 把上表 provider 放在 slot 2，恢复后 `tableId=1/cfiPosition=6/takenCtr_value=4/predTaken=1`，公开方向为 taken；行不变而 branch +1、toggle +2 |

## 三、死开关：`io.redirect`

- 模型明确表达重定向：`UtageReference.advance` 在 `events.redirect` 时设置
  `redirect_bubble`，把该槽的 `{slot}.valid` 压成 0，并把 frame 的条目清空。
- RTL 在 A2 阶段用 `~io_redirect` 门控 `a2_abtbHitVec_*`（`UtageDut.v:1163-1190`）。
- 但 `suites/frontend/bpu/utage/bundle/ports.py` 原本**没有绑定 `io.redirect`**，
  fast-lookup bundle 也不含该字段，driver 只发 `s0_fire/s2_fire/startPc/history/fromAheadBtb`。

这是“模型支持、激励从未置起”的死开关。**本轮已修复**：

1. `UtagePorts.lookup` 绑定 `redirect=dut.io_redirect`；
2. fast-lookup Bundle 与 idle 编码加入 `redirect`；
3. `UtageLookup` 增加 `redirect: bool`（仅关键字、显式 bool 校验）；
4. 新增功能点 `BPU-UTAGE-026` 与 `tests/utage/testcase/test_redirect_flush.py`：
   - 已训练记录命中后，在途查询遇到相邻拍重定向 → 该窗口 `hit=0` 且四个
     AheadBTB 槽 `valid=0`；
   - 随后同 PC 查询仍命中，provider 表/位置/计数原样返回 → 撤销的是发布资格；
   - **无重定向的同一程序保留命中**作为对照（否则无法排除“第二笔查询导致 miss”）；
   - idle 重定向脉冲不制造也不销毁记录。

第一次探针显示：无重定向时在途响应 `hit=1`；带重定向时同一响应 `hit=0`，
记录仍在。对照与断言都已固化进用例，避免把“脉冲被接受”当成验证。

## 四、未建表达：单端口 SRAM 读/强制写回冲突

> 附：本题“恢复时 slot 2 能选上表”的臂此前被判为开放，实际是**程序形状**
> 问题——单分支 beat 的 slot 2 回退位置永远等于 `position + 2`，在 `position`
> 训练的表项不可能是它的 provider。改用真实三分支 beat 后该臂命中
> （`results/utage-slot2-upper-20261021-v1`）；全量选测中 1100–1200 行的恢复
> 选表臂至此**全部命中**，剩余 497 个未命中 arm 全在 `BypassShadowBuffer.sv`。

`MicroTageTable.scala` 的 `writeSuccess` 只在“不同 bank 或 forceWrite”时为真；
同 bank 的强制写回与读同拍时，生成 RTL 把 `sramRealReadEntry.valid` 压 0
（`UtageDut.v` 的 `sramRealReadEntry.valid := !((writeOHNext === a1_bankOH) && needCheckConflict)`）。

**更正（2026-10-21）**：先前这里写“模型未表达该规则”，这是错的。独立模型已经有
`RecentUpdates.pressured`（未完成义务 > 6 即等于 RTL 的 forceWrite 条件），并在
`shadow is None and retiring is not None and pressured and same bank` 时把该条目
置无效。实测相邻八拍同 bank 学习后 `outstanding=8`、`pressured=True`，证明压力
状态可达。

本轮据此补了 `BPU-UTAGE-027` 与 `tests/utage/testcase/test_write_pressure_bank.py`：
在压力下每条刚学到的经验仍返回自己的命中、方向与计数，且未完成义务数随后下降。
该用例选用表 0 tag 可表示的八个折叠历史，避免与 `BPU-UTAGE-007` 混淆。

仍然**未验证**的是最强形式：某条目已被挤出写缓冲的最近窗口、只存在于 SRAM，
同时同 bank 强制写回把该 SRAM 读响应压掉——此时查询应退化为 miss。构造它必然
跨越写缓冲槽复用，与已登记的 `BPU-UTAGE-016` 持久化缺陷重叠，本轮没有制造第二个
重叠场景。

## 四之二、同拍反馈 + 恢复（已由用例覆盖，探针记录保留）

已由 `tests/utage/testcase/test_override_with_inflight_feedback.py`（2 PASS，S2/S3）
覆盖：先提交恢复、再让一笔真实 not-taken 反馈落地，响应必须重放快照
（`ctr 5 / taken 1 / table 0`），而同一程序的 fresh 查询给出 `ctr 3 / taken 0`。
两者**必须不同**，否则断言是空转。

一个被否定的假设保留在这里作为教训：曾以为“反馈先落地时恢复应等于 fresh 查询”，
实测并非如此——override 的设计就是复用**更老的** A2/A3 快照，与最新读相等
并不是义务。把“相等”写进控制组会制造假失败。

以下为最初探针记录（现在只作为发现过程的证据，不单独构成验证）：

本轮尝试构造“反馈与 S2/S3 恢复同拍”，做法是在 `asyncio.create_task(train(...))`
期间立即发出 `recover_prediction(stage=..., override_pc=...)`。实测（两个 stage 各一次）：

```
warm 1 1 4
override 0 0 0          ← 恢复窗口无效
other 1 1 4             ← 另一笔学习确实生效
warm-again 1 1 4        ← 原记录仍在
```

**为什么不能算通过**：独立模型对这次组合也给出 `hit=0`，所以“模型与 DUT 一致”
在这里不能证明“恢复被正确抑制”。可能有两种解释，而当前证据无法区分：

1. 训练在该拍占用了流水，恢复快照确实没有形成可发布的窗口；
2. 恢复快照存在，但被并发学习冲掉——这会是缺陷。

要判定必须先把两者拆开：让恢复与训练落在**可区分的拍**上，并只读观测恢复源的
产生时刻。这需要新增只读观测点，本轮没有做，因此该格保持 **未验证**，探针输出
不写入任何功能 PASS/XFAIL。

## 五、检查器审计

| 项目 | 结论 |
|---|---|
| 全局静音 | UTAGE 环境没有 `allow_unexpected`/时间窗静音；`suppress(asyncio.CancelledError)` 只用于协程取消，不跳过比较 |
| 有界放行 | 本轮新增两类：`allow_known_miss(pc, position)` 与 `allow_known_counter_difference(table, index)`；只删除声明的字段，其他字段照常比较，每次使用写入 `allowed_events` |
| 放行边界用例 | `tests/utage/scoreboard/test_bounded_allowances.py`：7 项纯检查，覆盖“非声明地址不丢、反向差异不丢、混合命中差异保留整表比较、counter 差在声明单元才丢、非 counter 字段仍失败、非法声明被拒绝” |
| 死字段 | `prediction_values` 对模型可能产生的每个字段都有观测映射：hits/meta_valid/indices/history 与每槽 valid/base/strong/hit/taken/predicted/position/provider/counter；未发现只在模型计算而从不比较的字段 |
| 死开关 | `io.redirect`（见三）；`counter_fields` 的 `high` 在两表构建中被综合删除，monitor 显式跳过并记录原因，不伪装成比较 |
| 计数方式 | 预测按 `Scoreboard` 的每笔 Transfer 计数；反馈按 `PulseDriver` 的握手/活动监测，按拍而非按电平累计；`send_shadow_feedback` 显式检查相邻间距为 2 |
| 断言可见性 | 生成 RTL 已裁掉 Scala 断言；本套检查全部由公开输出/只读 memory-direct 承担，不依赖未编译的断言 |

## 六、三问复盘：本轮三个“FAIL 变回 XFAIL”

| 问题 | 结论 |
|---|---|
| 功能点缺了哪条语义 | **没有**。007/016/021 的义务早已写在合同里；失败的是判定映射，不是需求缺失 |
| 检查器漏了哪个视角 | **异常映射**。独立参考比场景自己的异常更早发现同一差异，抛 `ScoreboardMismatch`；marker 只接受场景声明的异常，于是已知缺陷被报成普通 FAIL。修复是“同一差异形状的有界转换”，不是放宽比较 |
| 激励缺了哪一格 | **没有**。016 的 16 种矩阵和 021 的 512 地址矩阵本来就存在；此前在第一次差异处中止，现在跑完整矩阵后再由场景自己的收集器判定 |

对应的负对照：

- 007：`test_utage_guarded_pc_tag_width` 现在是 strict XFAIL；若 DUT 修复会 XPASS 失败。
- 016：`test_saturated_rows_survive...` 现在是 strict XFAIL；`before/neighbor` 读仍要求正确
  counter，只有 `after` 的声明单元允许 stale 值，收集器仍逐个记录 112 个失败格。
- 021：`test_useful_update_full_required_address_matrix` 现在跑完 512×2 并抛
  `UtageUsefulProviderBlocked`（strict XFAIL），不再在第一个高 tag 处中止。
- 020（分配矩阵）**仍保留普通 FAIL**：它要求的高 tag 命中确实被 007 阻断；没有给它
  加放行，避免把“分配已初始化”冒充成“预测命中正确”。

## 七、仍开放的组合格

1. `io.redirect` 同拍查询（死开关，见三）。
2. 单端口 SRAM 强制写回与读冲突（模型未表达，见四）。
3. 反馈与 S2/S3 恢复快照同拍（现有恢复用例是顺序的）。
4. 老化与禁用同拍（分别有检查，未合成一格）。
5. 完整 FTQ 寿命、真实重定向流与组合 BPU 仲裁不在本 UT 合同内。
