# MicroTAGE（utage）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

MicroTAGE 是早级条件方向预测/纠正与保护结构，使用两表 5/9 历史，向早级流水提供
takenVec/hitVec 和训练元数据。它只纠正 ABTB 的真实条件位置；完整多相对错误准入和
所有折叠历史碰撞未证明。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| 历史输入 | `normalPathHist_hist` 只保留 index 2/7；`s1PathHist_hist`、`overridePathHist_hist` 与训练历史只保留 1/2/5/6 | [2026-10-30 模块复核](../verification/evidence/module-reviews/utage-module-review-20261030.md) `[验证侧依据；历史运行记录]` |
| FastTrain | `fastTrain.bits.branch` 只有 `taken`/`cfiPosition`/`attribute_branchType`；无 `mispredict`、`ras_action` | 同上 `[验证侧依据]` |
| 发布资格 | `io.meta_valid` 被父模块删除，语义上等于“任一 public hit” | 同上 `[验证侧依据]` |
| ABTB 输入 | `fromAheadBtb.result.bits` 只有 `taken`/`attribute_branchType`；位置由独立 `fastPositions` 提供 | 同上 `[验证侧依据]` |
| 预测输出 | `io.prediction.takenVec/hitVec` 为 4 槽完整 | 同上 `[验证侧依据]` |
| 位置/历史域 | `cfiPosition` 为 5-bit 0..31；模型接受 532 位循环历史存储域，但只使用自身低 `length` 位折叠（≤397） | 同上 `[验证侧依据]` |
| 表配置 | 两表 5/9 历史（DefaultConfig）；不能从旧四表注释推相同 maintenance 域 | [Scala 审查](scala-interactions-20261106.md) `[实现观察]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `UTAGE.select`；001–002、005–010、013–014、018–019、023–025 | 只用原资格的 tag/历史输出，别的分支不占用 provider；无合法条件结果不学方向 | 冷/暖、短/长历史、原读索引与 tag 祖先、同低位不同高位、未执行条件与非条件；S2 取 A2、S3 取 A3 重匹配，redirect 清 hit，次拍原 ABTB 结果不许训练 | [MicroTAGE 行为审查](../verification/evidence/reviews/utage-functional-definition-review-20261016.md) `[验证侧依据]` |
| `UTAGE.learn`；003–004、011、017、020–021、028 | 计数/有用性按真实合格结果升降、两端保持、反向可恢复；老化不删除方向 | taken/NT、计数上下界、弱/强、初始保护、长期分配失败/整表老化；`lowTickCounter` bit7 驱动 aging，128 次失败分配触发 | [行为审查](../verification/evidence/reviews/utage-functional-definition-review-20261016.md)、[学习持久合同](../verification/contracts/utage-learning-persistence-contract.json) `[验证侧依据；失败分配维护分区待设计确认]` |
| `UTAGE.service`；006、008–009、012、015–016、022、026–027 | 版本、原 owner 与新消费者一一对应，禁止年轻覆盖旧来源；禁用/取消只作用合同允许的寿命 | 保存的中/晚级快照、相邻反馈、缓冲强制写回、同 bank 查询、enable/redirect；强制写回使同 bank 读无效，应有明确 miss/重试观察 | [行为审查](../verification/evidence/reviews/utage-functional-definition-review-20261016.md)、[工作集合同](../verification/contracts/utage-working-set-contract.json) `[验证侧依据；force-read 分区待设计确认]` |

## 4. 时序、服务与生命周期

- index 与 tag 来自不同相位；连续同索引用最新版本旁路；S2/S3 快照年龄分开，不能把
  A2 结果用于 A3 匹配。`[实现观察]`
- `Context.from_recent` 只用自身低 `length` 位折叠，不把 532 位存储域当全部有效历史。
  `[验证侧依据]`
- 复位拍不比较输出，并在同一拍清模型状态；被裁 fold 的负对照不得翻转不可观测 fold。
  `[验证侧依据]`
- 训练/维护实际完成后由 fresh consumer 确认；稳定方向不能代替计数/保护到边界，
  维护不抹 tag/方向。`[验证侧依据]`

## 5. 独立依据与证据边界

- 合同：[UTAGE 工作集合合同](../verification/contracts/utage-working-set-contract.json)、
  [学习持久合同](../verification/contracts/utage-learning-persistence-contract.json)、
  [查询身份合同](../verification/contracts/utage-query-identity-contract.json)、
  [长保护合同](../verification/contracts/utage-long-protection-contract.json)。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)。
- 固定 Scala 位置：`MicroTage.scala:52-243,252-389`、`MicroTageTable.scala:70-133`、
  `BypassShadowBuffer.scala:99-268`；实现观察不直接作为 golden。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  记录完整 seed1 MicroTAGE 235 PASS/35 FAIL/1 XFAIL；旧 10-30 结果不自动继承。
- 保留反例：35 个旧 FAIL（含 16 条 two-warm-providers、8 条 multiple-incoming-edges 等）
  与 strict XFAIL 保持原判定，不以覆盖提升改写为通过。

## 6. 当前与历史边界

[2026-10-30 模块复核](../verification/evidence/module-reviews/utage-module-review-20261030.md)
的端口/位宽事实可追溯；其 234 PASS/35 FAIL/1 XFAIL 与覆盖数字属于当时验证源码和选择，
不自动成为当前判定。2026-10-16 行为审查继续作为独立合同来源，但旧源码结论不继承。
设计 owner、逐条确认人与确认记录仍待补。
