# Bpu 顶层当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有
合同、固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源
是验证合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立
设计确认。本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

Bpu 顶层负责 S0/S1 预测选择、S2/S3 纠正与提交侧交接、实际反馈到各预测器的学习
资格、历史/恢复以及版本与同拍仲裁。顶层保留真实组件 RTL；组件 DUT 的 PASS 不能
代替顶层组合、FTQ 生产者资格或公开投影的观察。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| 预测地址 | `BpuRedirect.cfi_pc` 为 50-bit guarded 半字；内部 PHR/CommonHR 只在消费点去 guard，不能按虚拟符号位重建 | [流水合同](../verification/contracts/pipeline-transaction-contract.md) `[验证侧依据]` |
| RAS 恢复地址 | 恢复 API 使用偶数 51-bit guarded 字节地址，返回地址按该域加 2 回绕 | [新基线适配](../verification/evidence/runs/baseline-update-a0c2a26cb.md) `[验证侧依据]` |
| 公开预测 | DefaultConfig 公开 prediction 只保留 `startPc/taken/endPosition/s2Override/s3Override`；`target_addr` 与 `perfMeta` 被 DCE | [流水合同](../verification/contracts/pipeline-transaction-contract.md) `[验证侧依据]` |
| metadata | 没有公开 metadata ready；只读常量仅用于 valid-only SDK 适配，不进入 driver 所有权 | [流水合同](../verification/contracts/pipeline-transaction-contract.md) `[验证侧依据]` |
| 组件投影 | MainBTB 4 way + victim、两组 alignment；MicroTAGE 4 个训练 fold（1/2/5/6），baseStrong 被裁；pipeline lookup 比较 20 个保留 fold | [流水合同](../verification/contracts/pipeline-transaction-contract.md) `[验证侧依据]` |
| 配置边界 | 完整 DefaultConfig 优化后的端口以实际生成 RTL 为准；不增加 BPU 专用生成入口或单 DUT override | [验证规格](../verification/README.md) `[验证侧依据]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `BPU.select`；001–004、006–019、032、075–079、101、109 | 各阶段按原请求及优先级选择，完整目标/类型/位置与原 metadata 配对；禁用候选不占优 | ABTB 有 valid entry 时遮住 UBTB，ABTB 全 NT 时走 fallthrough；UTAGE 只纠正 conditional；S2 比较方向/位置/属性而不比 target，目标差异留 S3 | [模块行为目录](module-behavior-matrix.md)、[Scala 审查](scala-interactions-20261106.md) `[验证侧依据；ABTB-valid/派生 enable 待设计确认]` |
| `BPU.learn`；020–031、039–051、055–062、066–074、083–093、106–107 | 各模块从同一原 S3/FTQ 来源学习自己的方向/目标/useful；未执行后缀和不合格来源不训练 | `train.ready` 为全部预测器 ready 之 AND，实际 t0 fire 才驱动学习；redirect 不全局屏蔽合法旧原件训练；FastTrain 是 s3 预测而非执行真值 | [Scala 审查](scala-interactions-20261106.md)、[流水合同](../verification/contracts/pipeline-transaction-contract.md) `[验证侧依据；FastTrain 多错误可达域待确认]` |
| `BPU.history`；005、008、033–038、043、052–054、063–065、068–069、080–081、094、096、099、105、112–114 | 计算已执行 conditional 前缀，NT 恢复不附加未执行后缀；guard 不取代虚拟地址；新请求获新 UID | PHR pending 写/旁路与 redirect 即时物理写分开；CommonHR redirect 当拍 history 无效、r1 修复并补 s1/s2；环回绕与连续 redirect 待区分 | [PHR 合同](../verification/contracts/phr-transaction-contract.md)、[Scala 审查](scala-interactions-20261106.md) `[验证侧依据；pending r0/r1 wrap 待确认]` |
| `BPU.arbitrate`；003、009–010、026–031、045–051、057、063–067、073–074、082–092、095、097–104、108、110–112 | 保留有资格原交易、唯一 owner 与版本；冲刷取消较年轻版本；最终有界 drain | S1 受 prediction.ready；S2/S3 继续排空；S2/S3 override 在 ready=0 由 FTQ 特殊写入；FTQ meta.ready 恒真；meta 按每 S3 valid 发布 | [流水合同](../verification/contracts/pipeline-transaction-contract.md)、[Scala 审查](scala-interactions-20261106.md) `[验证侧依据；meta lifetime 待确认]` |

## 4. 时序、服务与生命周期

- 启停由 CSR 传播存在延迟：UTAGE 由 ABTB 使能，RAS/MicroRAS/TAGE/SC/ITTAGE 还依赖
  MBTB；不能假设独立 UTAGE CSR。关闭后已接纳服务与关闭后新学习分开。
  `[实现观察，待设计确认]` 见 [Scala 审查](scala-interactions-20261106.md)。
- 正常 S1 受 prediction.ready 约束；S2/S3 在 ready=0 仍按 FTQ 特殊路径写入，不能当成
  一般“保持到 fire”的普通响应。`[验证侧依据]`
- 训练与实际恢复可同拍：合法旧原件可和 redirect 并行学习；投机取消、学习资格和提交
  是不同义务。`[实现观察]`
- PHR 普通预测有 pending 写与旁路，redirect 即时物理写并控制新 pending；逻辑可见值
  不能只读物理 cell。`[验证侧依据；待设计确认项见合同]`

## 5. 独立依据与证据边界

- 验证接口与来源约束：[流水事务合同](../verification/contracts/pipeline-transaction-contract.md)、
  [PHR 事务合同](../verification/contracts/phr-transaction-contract.md)。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)（含 78 条代表分区、
  11 个联合交互）与[模块行为目录](module-behavior-matrix.md)关联的稳定功能 ID。
- producer 观察：`BranchUnit.scala:26-29,73-82`、`ResolveQueue.scala:51-66,86-98,132-153,157-177`、
  `Ftq.scala:187-241,405-453,504-521`、`PredChecker.scala:128-184`；这些是固定 commit 的
  实现观察，不是独立 golden。
- 当前阻塞残余：`BPU-UPGRADE-OBS-01`（公开 target/perfMeta 不可观察）、
  `BPU-UPGRADE-SEM-01`（历史功能失败逐项定性）、`BPU-UPGRADE-SCOPE-01`（完整 producer/FTQ
  可达性）。三者保持 open，不因文档整理关闭。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  与 [2026-11-08 收口检查点](../verification/evidence/runs/closeout-20261108.md)；历史 FAIL/ERROR/
  XFAIL/SKIP 保持原判定。

## 6. 当前与历史边界

2026-10-16 的组合审查和 2026-11-02 的事务记录属于各自基线/源码的实现证据，不自动
成为当前基线的功能通过。当前基线只继承经 2026-11-03 差分确认未变的来源、UID、所有权
与收尾承诺；旧统计数字、旧选择范围和旧源码判定保留在原日期与原文中，不拼成当前
完整验收。设计 owner、逐条确认人与确认记录仍待补。
