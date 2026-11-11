# MicroBTB（ubtb）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

MicroBTB 是早级小表 taken 目标预测器，负责冷/暖查询、可靠性维护、冲突替换、启停和
查询/复位生命周期。它的早级预测不是最终 FTQ 目标；同一 PC 的新旧来源不能自动合并。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| 预测有效性 | MicroBTB 恒为 taken 预测器；整芯片删除未被父模块使用的 `io.prediction.valid`，有效性等于“使能且存在 taken 预测” | [2026-10-29 模块复核](../verification/evidence/module-reviews/ubtb-module-review-20261029.md) `[验证侧依据；历史运行记录]` |
| 常量状态 | `io.sramResetDone` 与 `io.trainReady` 为 Scala 常量，整芯片不保留引脚，按常量绑定 | 同上 `[验证侧依据]` |
| FastTrain | `HasFastTrainIO` 的 `BranchInfo.mispredict` 未被消费而裁剪；S3 fastTrain 的语义就是纠正，resolve 使用真实位 | 同上 `[验证侧依据]` |
| 位置域 | DefaultConfig 取指块 64 字节，`cfiPosition` 为 5-bit 0..31；不接受旧 4-bit 上限 | 同上 `[验证侧依据]` |
| 存储 | 32 个条目；复位清除 tag/target/position/type/RAS/usefulness；空闲周期不改变替换状态 | 同上 `[验证侧依据]` |
| 地址 API | Standalone 事务用 50-bit unguarded **字节**地址；引脚 `PrunedAddr` 是 49-bit 半字；集成 BPU 保留自己的半字 API（`BpuPrediction.start_pc` 50 位，redirect `cfi_pc` 另带 guard） | 见下方“地址 API 分层” |

**地址 API 分层**（[`testbenches/ubtb/transactions/types.py:1-4`](../../../testbenches/ubtb/transactions/types.py)、
[`testbenches/ubtb/env/driver/encoding.py:18-31`](../../../testbenches/ubtb/env/driver/encoding.py)、
[`testbenches/bpu/model/micro_sources.py:74,79`](../../../testbenches/bpu/model/micro_sources.py)）：

- Standalone MicroBTB 的公开事务 API 是 **50-bit unguarded 字节地址**；
  [`transaction/address.py`](../../../testbenches/ubtb/transactions/address.py) 要求半字对齐，即架构字节
  地址 bit0=0。
- Standalone driver 在发引脚前经 `byte_address` + `encode_pruned_pc` 转为 49-bit
  `PrunedAddr.addr` 半字，monitor 用 `decode_pruned_pc` 解回字节
  （[`testbenches/ubtb/model/address.py`](../../../testbenches/ubtb/model/address.py)、
  [`testbenches/ubtb/env/monitor/semantic.py:8,26,34-41`](../../../testbenches/ubtb/env/monitor/semantic.py)）；字节与半字
  只在这个 adapter 转换一次。
- 集成 BPU 的公开预测/流水 API 仍是半字（`BpuPrediction.start_pc` 为 50 位；
  `BpuRedirect.cfi_pc` 是 50 位 guarded 半字，见
  [`testbenches/bpu/transactions/types.py`](../../../testbenches/bpu/transactions/types.py)）；复用独立 UBTB 模型时在
  [`testbenches/bpu/model/micro_sources.py`](../../../testbenches/bpu/model/micro_sources.py) 以 `pc*2` 进入字节域，
  不能再次移位。
- 旧修正依据：[MicroBTB 地址域修复要求与判别设计](../verification/evidence/analyses/ubtb-byte-address-repair-20261016.md)
  已记录“公开 Standalone 用字节地址、BPU 本身仍半字、乘二/除二各只做一次”，并保留
  旧 49 位误限与跨区/最高合法地址的判别证据。

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `UBTB.lookup`；001–004、013、016 | 冷态 miss；合格 taken 建立完整 target/type/位置，冷 NT 不制造 taken，响应与原请求配对 | 冷/暖、不同分支类型、稀疏 resolve、同 PC 不同原件；早级预测不是最终 FTQ 目标 | [MicroBTB 行为审查](../verification/evidence/reviews/micro-btb-functional-definition-review-20261016.md) `[验证侧依据；alias/carry 分区待设计确认]` |
| `UBTB.confidence`；005、009–012 | 可靠性饱和保持而非绕回；耗尽变 miss，新 taken 按新身份建记录，旧失效版本不压住新学习 | 原命中遇 NT、连续耗尽、紧邻新 taken、精确 taken 强化及 t0/t1 旁路；相邻训练×查询碰撞要比较最后实际存活版本 | 同上 `[验证侧依据]` |
| `UBTB.lifecycle`；006–008、014–015、017 | 只淘汰合法 victim；禁用不使用也不新学但保留已学；有资格 resolve 按优先级生效 | 冲突替换、tag/目标边界、disable、同拍 resolve/fastTrain；父级直接用 `bits.taken` 而非 valid 的启停组合风险需独立检查 | [行为审查](../verification/evidence/reviews/micro-btb-functional-definition-review-20261016.md)、[I/O 合同](../verification/contracts/cold-source-isolation-contract.json) `[验证侧依据；source/enable/reset 分区待设计确认]` |

## 4. 时序、服务与生命周期

- resolve 误预测压 fastTrain；t0 接纳后 t1 可在关闭时完成。查询与 t1 分配碰到原 victim
  须当 miss。`[实现观察]` 见 [Scala 审查](scala-interactions-20261106.md)。
- 复位断言优先于尚在 s0→s1 的响应；复位拍不比较预测；`reset-after-launch` 先等待语义
  接受再复位；不得用 DUT 实际值反推预期。`[验证侧依据]`
- 禁用只阻断新使用/新学习，不清空已学条目；恢复后的合法性需与父级 enable 资格分开。

## 5. 独立依据与证据边界

- 相关顶层/集成合同（UBTB 作为组合来源）：[冷来源隔离合同](../verification/contracts/cold-source-isolation-contract.json)、
  [工作集替换合同](../verification/contracts/bpu-working-set-replacement-contract.json)；UBTB 本层独立依据仍以
  [MicroBTB 行为审查](../verification/evidence/reviews/micro-btb-functional-definition-review-20261016.md) 为主。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  的完整 seed1（冻结验证源码 `18a8e5d…`）记录 MicroBTB **50 PASS / 0 FAIL**；同一轮的
  端口闭包、构建和冒烟结果也记录在该报告。该范围不等于旧 2026-10-29 模块复核的
  49 PASS 选择，旧判定不自动继承。
- 保留反例：`BPU-BUG-08`（microBTB fallthrough revives dead entry）等保持原判定。

## 6. 当前与历史边界

[2026-10-29 模块复核](../verification/evidence/module-reviews/ubtb-module-review-20261029.md)
的端口/位宽事实可追溯；其 49 PASS、覆盖数字属于当时验证源码和选择，不自动成为当前
判定。2026-10-16 行为审查继续作为独立合同来源，但旧源码结论不继承。设计 owner、
逐条确认人与确认记录仍待补。
