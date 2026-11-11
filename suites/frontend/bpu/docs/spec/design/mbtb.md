# MainBTB（mbtb）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

MainBTB 负责多分支目标记录、窗口查询与过滤、条件方向/类型纠正、Main/Victim 驻留
和写回服务。它保存原预测暴露的 metadata；顶层复用同一自主 Main 模型，但组件 DUT
的结论只覆盖该组件接口边界。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| lookup 地址 | 50-bit **半字** `GuardedPc.addr`，可带 guard 和真实 offset，不当作字节地址 | [当前事务合同](../verification/contracts/mbtb-transaction-contract.md) `[验证侧依据]` |
| 训练 PC/target | 49-bit **半字** `Pc.addr`；后继对齐窗口在 49 位域回绕 | 同上 `[验证侧依据]` |
| 预测结果 | 两 align ×（4 个 Main way + 1 个 Victim），target 为 50-bit guarded 半字 | 同上 `[验证侧依据]` |
| 预测 metadata | 每 align 五槽；Main 槽完整属性/counter/position/rawHit，Victim 无 attribute | 同上 `[验证侧依据]` |
| 训练 metadata | 每 align 四个完整 Main 槽；预测快照的第五槽只投影真实训练 wire 的 `rawHit/position`，counter 是输出观察而非新训练叶 | 同上、[新基线适配](../verification/evidence/runs/baseline-update-a0c2a26cb.md) `[验证侧依据]` |
| resolve vector | 最多八槽，显式 `None` 空槽保留；位置唯一，最多一个 mispredict | [当前事务合同](../verification/contracts/mbtb-transaction-contract.md) `[验证侧依据]` |
| 生成端口裁剪 | `s3_takenMask` 只保留父模块消费的槽 4/9；预测侧每 bank 五槽完整；训练侧每 bank 四 Main way；`trainReady` 为常量；`stageCtrl` s0..s3 与 t0 保留 | [2026-10-30 模块复核](../verification/evidence/module-reviews/mbtb-module-review-20261030.md) `[验证侧依据；历史运行记录]` |
| 物理坐标 | 16 字节对齐偏移 3 位、align bank 1 位（PC[4]）、internal bank 2 位（PC[6:5]）、set 8 位（PC[14:7]）、tag 16 位（PC[30:15]） | 同上 `[验证侧依据]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `MBTB.lookup`；001–003、007–009、012–013、018 | 窗口查询返回完整有效位、顺序、位置、类型、方向和目标；过滤不删除后续居民，重叠响应不互换 | 冷/暖、两 align、起点跳过旧分支、跨页、低偏移同区/跨区；一次窗口多条 CFI；真实消费者前态未全证 | [模块行为目录](module-behavior-matrix.md)、[当前合同](../verification/contracts/mbtb-transaction-contract.md) `[验证侧依据]` |
| `MBTB.learn`；004–005、014–016、027–028、032–033 | 合格条件方向更新；NT 不创建、不改型或污染旧 target；None 可失效，邻居保持；foreign tag/未执行分支不能借资格学习 | conditional NT 只消费方向，resolve target 是顺序后继；明确纠正为 conditional 的 NT 可削弱原方向计数，但不得改写旧预测 payload；缺失第五槽、补造 attribute 或混合 lookup 祖先拒绝 | [当前合同](../verification/contracts/mbtb-transaction-contract.md)、[输入/输出矩阵](../verification/coverage/io-matrix-extension-20261103.md) `[验证侧依据]` |
| `MBTB.residency`；006、017、019、023–026、029–031、034 | 当前仍驻留且原预测暴露项就地更新；隐藏或已淘汰项按原身份分配 Main；清理旧副本、保持幸存者及原 UID，不从 fresh lookup 改写旧 metadata | “现在在 VBTB 有副本”与“原预测实际展示该逻辑分支”分别判断；同拍 victim 替换×迟到反馈、零键清理仍为待确认/反例 | 同上 `[验证侧依据；同拍替换分区待设计确认]` |
| `MBTB.service`；010–011、020–022、025–026、030 | 接受的不同 owner 都结清；同一逻辑记录以最新完整版本服务；禁用不新学，恢复保留原已学；不丢其他未完成版本 | 有界 dirty 容量与读优先服务；reset/disable 的已接纳/排队终态与 FTQ 退休分开；持续读×满待写仍待实验 | [当前合同](../verification/contracts/mbtb-transaction-contract.md)、[共享服务 owner 合同](../verification/contracts/mbtb-shared-service-owner-contract.json) `[验证侧依据；reset/disable 分区待设计确认]` |

## 4. 时序、服务与生命周期

- lookup 复用框架异步单周期 Driver 与固定延迟 Scoreboard；`DriveStable` 保存 pre-edge
  ready，实际 `RisingEdge` 才采输入；下一 `DriveStable` 消费保存输入，取消后不产生幻影接受。
  `[验证侧依据]` 见 [当前合同](../verification/contracts/mbtb-transaction-contract.md)。
- 接受后 reset、S0/S1 之间 disable 由 `MbtbLookupDisposition` 交付原 UID/epoch/reason；
  控制变化前已产生的结果保留为真正响应，不能 reset 后追溯取消。
- cleanup 使用输入 reset-LRU 计划：original/displacer=3，changed/extra=2，keep2/clear3；
  shared-service 两行同 bank，真实 tag0/1 坐标与旧 `0x40000020+(tag<<11)` 明确不同。
- `finish(timeout_cycles=...)` 只等待已提交尾部和自主训练写回；不自动补 reset、enable、
  training、metadata 或 S2 来清债；关闭 monitor/清空视图不是事务完成。
- 当前 checked-close 只启用于 MainBTB 及 cleanup-reset 派生 agent，不签核其他九 DUT。

## 5. 独立依据与证据边界

- 当前合同：[MainBTB 当前事务合同](../verification/contracts/mbtb-transaction-contract.md)；
  独立 owner/清理合同：[shared-service owner](../verification/contracts/mbtb-shared-service-owner-contract.json)、
  [cleanup semantic regression](../verification/contracts/mbtb-cleanup-semantic-regression-contract.json)。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)、
  [输入/输出矩阵](../verification/coverage/io-matrix-extension-20261103.md)。
- 独立 producer 观察（固定 commit）：`BranchUnit.scala:26-29,73-81` 的 NT 顺序后继、
  `ResolveQueue.scala:76-79,142-145` 的 resolve 传递、`PredChecker.scala:179` 与
  `Ifu.scala:742-745` 的 None canTrain、`Ftq.scala:387-392` 的 guarded CFI PC。
  这些是实现观察，不是 golden。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  （完整 seed1 MainBTB 171 PASS/9 FAIL；叶 seed2 166/9，不是同一选择）与
  [2026-11-08 收口检查点](../verification/evidence/runs/closeout-20261108.md)。
- 真实 FAIL 保留：shared retained-owner 丢纠正、foreign-tag 同位置计数污染、旧 cold
  第二深度方向污染、联合 zero-key 清错 owner 及四个满容量同位置计数反例。原对照、
  metadata 来源和完整 payload 要求不删，不加 XFAIL。

## 6. 当前与历史边界

- 当前基线 `public-a0c2a26cb` 的第五槽训练、真实 rawHit/position 区分、conditional NT
  不改 payload 见上方当前合同；旧 `public-893e1580b` 的统计与四路训练条款已移到
  [历史合同原文](../verification/evidence/reviews/mbtb-transaction-contract-893e1580b.md)，
  只属于所列旧版运行，不与当前条款拼接。
- [2026-10-30 模块复核](../verification/evidence/module-reviews/mbtb-module-review-20261030.md)
  的端口裁剪/坐标事实可追溯，但其 PASS/FAIL/覆盖数字属于当时验证源码和选择，不自动
  成为当前判定。
- 设计 owner、逐条确认人与确认记录仍待补；本页不伪造签核。
