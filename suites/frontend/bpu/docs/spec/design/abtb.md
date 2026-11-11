# AheadBTB（abtb）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

AheadBTB 负责超前窗口的历史索引预测、目标/位置归属、方向/类型学习和 Main/Victim
驻留维护。它向 MicroTAGE 提供的 taken/branchType 是同一早级选择链的输入，不能把本层
target 命中当 S3 最终输出。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| 预测有效 | Scala 层 ABTB 没有独立的 `prediction.valid` 输出，`BasePredictorIO` 的该叶不绑定。整芯片 MicroBTB 的同类 `io.prediction.valid` 也因父模块不消费被 DCE；两者不能互相当作公开有效引脚 | [2026-10-30 模块复核](../verification/evidence/module-reviews/abtb-module-review-20261030.md)、[MicroBTB 模块复核](../verification/evidence/module-reviews/ubtb-module-review-20261029.md) `[验证侧依据；历史运行记录]` |
| 阶段控制 | `io.stageCtrl.s3_fire` 未被消费，删除绑定/驱动 | 同上 `[验证侧依据]` |
| 历史输入 | `io.normalPathHist_hist` 只保留 index 2；稀疏序列按声明元数据逐叶绑定 | 同上 `[验证侧依据]` |
| 结果/训练 | `io.result_entries` 为根级数组，逐元素绑定；`io.trainReady` 为 Scala 常量 | 同上 `[验证侧依据]` |
| FastTrain | `fastTrain.branch.mispredict` 未消费，删除编码/监视；公开 FastTrain 是较晚预测的教导，不是后端已执行真值 | 同上、[Scala 审查](scala-interactions-20261106.md) `[验证侧依据]` |
| MicroTAGE sideband | `toMicroTage.result.bits` 只提供 `taken`/`branchType`；`cfiPosition/isStrongBias/rasAction` 被裁，方向仍可观测 | 同上 `[验证侧依据]` |
| 索引/匹配 | 索引用当前 S0 历史，匹配用 next PC；S2/S3 override 分别重用两个年龄快照 | [Scala 审查](scala-interactions-20261106.md) `[实现观察]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `ABTB.lookup`；001–009、012、016–018、022–025、032–033、054 | 冷 miss、目标/位置/强弱由原快照而非最新请求决定；跨局部地址域不虚构完整目标 | 取指 PC+历史、同 PC 不同上下文、相邻索引/回绕、S2/S3 保存的原窗口；早级 Ahead 与 MicroTAGE 共享上层选择 | [AheadBTB 行为审查](../verification/evidence/reviews/ahead-btb-functional-definition-review-20261016.md) `[验证侧依据]` |
| `ABTB.learn`；010–014、036–042、047、049 | 只对合格原分支增减方向；较晚 taken 惩罚前序但不误伤后序；间接目标纠正不串入条件方向 | 前后序条件、taken/NT、同份多位置、条件与间接混合、不同历史窗口；NT 不分配但可惩罚原命中条件项 | 同上 `[验证侧依据]` |
| `ABTB.residency`；005、015、019–021、026–030、034–035、043–046、048、050–053 | 清理重复但不损失已发布预测；只动应淘汰居民，饱和与奖励各按合法身份；读优先待写最终服务 | 高索引/进位、重复副本、四路周转、读阻挡/缓冲训练、同替换状态读写竞争；旧待写不同目的身份缺陷保留 | [行为审查](../verification/evidence/reviews/ahead-btb-functional-definition-review-20261016.md)、[工作集合同](../verification/contracts/ahead-working-set-contract.json) `[验证侧依据]` |
| `ABTB.lifecycle`；001、017、031、054 | reset、enable/disable、redirect 正在途的查询窗口按原年龄撤销新发布资格；已学居民保持或按 reset 清空 | 新旧 epoch、连续 redirect 与反馈同拍由顶层 Bpu 另检查；leaf 压力不等于 Bpu 可达 | 同上 `[验证侧依据；非空 reset/enable 分区待设计确认]` |

## 4. 时序、服务与生命周期

- fastTrain 在 t0 要求原 ABTB `meta.valid`；counter reset 优先方向更新；训练 touch 与分配
  服务有独立年龄。`[实现观察]`
- 多命中清理请求在普通写后服务；ABTB 只要有有效 entry 就遮住 UBTB；ABTB 全 NT 时走
  fallthrough，即使 UBTB 有 taken。`[实现观察，待设计确认]`
- 复位拍输出不参与比较；写缓冲/计数器在复位拍与全新参考状态比较；读优先待写最终
  服务，但无通用反压不等于无限无损。`[验证侧依据]`

## 5. 独立依据与证据边界

- 相关顶层/集成合同（ABTB 作为组合来源）：[Ahead 工作集合合同](../verification/contracts/ahead-working-set-contract.json)、
  [工作集替换合同](../verification/contracts/bpu-working-set-replacement-contract.json)、
  [短分支竞争合同](../verification/contracts/bpu-short-branch-competition-contract.json)；ABTB 本层独立依据仍以
  [AheadBTB 行为审查](../verification/evidence/reviews/ahead-btb-functional-definition-review-20261016.md) 为主。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)。
- 固定 Scala 位置：`AheadBtb.scala:93-223,230-370`、`AheadBtbBank.scala:43-102`；
  这是实现观察，不是独立 golden。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  的完整 seed1（冻结验证源码 `18a8e5d…`）记录 AheadBTB **94 PASS / 1 FAIL**；同一轮的
  端口闭包、构建和冒烟结果也记录在该报告。该范围不等于旧 2026-10-30 模块复核的
  93 PASS/1 FAIL 选择，旧判定不自动继承。
- 保留反例：`BPU-BUG-09`（AheadBTB target correction wrong destination）等保持原判定。

## 6. 当前与历史边界

[2026-10-30 模块复核](../verification/evidence/module-reviews/abtb-module-review-20261030.md)
的端口裁剪/位宽事实可追溯；其 93 PASS/1 FAIL、覆盖数字属于当时验证源码和选择，不自动
成为当前判定。2026-10-16 行为审查继续作为独立合同来源，但旧源码结论不继承。设计
owner、逐条确认人与确认记录仍待补。
