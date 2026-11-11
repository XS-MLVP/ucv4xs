# SC（sc）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

SC 是统计相关分支预测器：在合格条件 Main 命中和原 provider 来源上维护权重/偏置、
阈值和使用资格，对最终方向做统计纠偏。provider 存在不等于 TAGE 最终采用 provider；
SC 叶子通过不能替代顶层归属。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| 历史输入 | `foldedPathHist_hist` / `trainFoldedPathHist_hist` 只保留 SC 两段 path/global 折叠索引 3、10 | [2026-10-30 模块复核](../verification/evidence/module-reviews/sc-module-review-20261030.md) `[验证侧依据；历史运行记录]` |
| Main/provider 输入 | `mbtbResult` / `providerTakenCtrs` 为根级数组，逐元素绑定；保留 `attribute_branchType`、`cfiPosition`、`valid`、`bits_value` | 同上 `[验证侧依据]` |
| 训练 Main 元数据 | 每 bank 只有 `rawHit`、`position`；属性/counter 被裁，branch kind 由真实 branch 向量提供 | 同上 `[验证侧依据]` |
| 调试/输出 | `meta.debug` 10 槽完整；`scTakenMask` / `scUsed` 10 槽根级数组 | 同上 `[验证侧依据]` |
| enable | `io_enable` 是模块级门控，按真实引脚驱动/采样 | 同上 `[验证侧依据]` |
| 配置 | DefaultConfig 8 表；旧维度/字节 API 结论不继承 | [验证规格](../verification/README.md) `[验证侧依据]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `SC.select`；001–004、007–012 | 仅合格条件 Main 命中且原 provider 有效时才纠正方向；无 Main/无 provider/非条件不得借强统计票给预测 | 原 Main 命中、原 TAGE/provider 和历史有效性、条件/非条件、阈值内外、enable；CommonHR 无效时 global/bw 不读不训练、预测改用零权重占位，但 `getPercsum=2w+1` 仍有常量正票，策略预期待独立确认 | [SC 行为审查](../verification/evidence/reviews/sc-functional-definition-review-20261016.md) `[验证侧依据；无效历史常量票待设计确认]` |
| `SC.weights`；005–006、013–016、019–020 | 按合格净票、正确特征和共享对象更新；饱和与邻居隔离，不吞第二分支或重置未选特征 | 同拍两个合格分支、同向/相反票、不同 selector/way、弱/强及边界；权重 t1/t2 服务与阈值更新分开 | [行为审查](../verification/evidence/reviews/sc-functional-definition-review-20261016.md)、[统计前缀合同](../verification/contracts/bpu-statistical-prefix-contract.json) `[验证侧依据；shared-votes 分区待设计确认]` |
| `SC.threshold`；017–018、021–023 | 整步更新或整步拒绝，阈值严格正负；新旧权重及原来源配对，不把失败投票当干净提交 | 连续反馈/交错历史、原快照资格、更新跨上下限、读写竞争；阈值 t1 更新与权重 t2 入待写/实际服务分离 | [行为审查](../verification/evidence/reviews/sc-functional-definition-review-20261016.md) `[验证侧依据；snapshot-service 分区待设计确认]` |

## 4. 时序、服务与生命周期

- bias 使用原 provider 方向/置信，不是 `finalTaken`；path/imli/bias 并非全部关闭。
  `[实现观察]`
- 同特征净票先聚合；阈值越界整步拒绝而非夹紧；阈值变化不能当权重已服务。`[验证侧依据]`
- 训练 Main 元数据只有 rawHit/position；Victim slot 训练元数据被裁，反馈源固定为每
  bank 4 个可训练 way。`[验证侧依据]`
- 关闭/恢复只作用于合同允许的寿命；新增资格消费者恢复后不能丢原学习。`[验证侧依据]`

## 5. 独立依据与证据边界

- 相关顶层/集成合同：[SC admission](../verification/contracts/bpu-sc-admission-contract.json)、
  [SC early learning](../verification/contracts/bpu-sc-early-learning-contract.json)、
  [SC loop experience](../verification/contracts/bpu-sc-loop-experience-contract.json)、
  [统计前缀合同](../verification/contracts/bpu-statistical-prefix-contract.json)；
  SC 本层独立依据仍以
  [SC 行为审查](../verification/evidence/reviews/sc-functional-definition-review-20261016.md) 为主。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)。
- 固定 Scala 位置：`Sc.scala:151-218,241-338,375-423,487-610,615-692`、`Helpers.scala:49-94`、
  `ScTable.scala:79-126`；实现观察不直接作为 golden。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  记录完整 seed1 SC 62 PASS/0 FAIL；旧 10-30 结果不自动继承。
- 顶层 `INT-041` 旧 PHR 形状阻挡、SC 无效历史常量占位票等仍为待确认/残余，不因叶子
  PASS 关闭。

## 6. 当前与历史边界

[2026-10-30 模块复核](../verification/evidence/module-reviews/sc-module-review-20261030.md)
的端口/位宽事实可追溯；其 61 PASS/0 FAIL 与覆盖数字属于当时验证源码和选择，不自动
成为当前判定。2026-10-16 行为审查继续作为独立合同来源，但旧源码结论不继承。设计
owner、逐条确认人与确认记录仍待补。
