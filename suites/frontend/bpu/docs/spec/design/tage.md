# TAGE（tage）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

TAGE 负责长历史 provider/alternate 方向预测、基础预测回退、方向/保护学习和分配维护。
它是 S1/S2/S3 选择链的一段，本层正确不证明顶层 S3 选择或 SC 统计纠偏正确。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| 历史输入 | `fromPhr.foldedPathHist_hist` 只保留 8 张表 index/primary/secondary 哈希消费的 20 个 fold；训练历史同样稀疏 | [2026-10-30 模块复核](../verification/evidence/module-reviews/tage-module-review-20261030.md) `[验证侧依据；历史运行记录]` |
| MainBTB 输入 | `fromMainBtb.result.N.bits` 只保留 `valid`+`bits_taken`；位置由 `s1_positions` 提供，kind 来自训练元数据 | 同上 `[验证侧依据]` |
| 基础置信 | `fromMainBtb.baseConf` 10 位完整保留 | 同上 `[验证侧依据]` |
| 阶段控制 | `stageCtrl` 只有 `s0_fire`/`s1_fire`/`t0_fire`；S2/S3 由 S1 token 与基础结果驱动阶段代替 | 同上 `[验证侧依据]` |
| 训练元数据 | `train.meta.mbtb_entries` 每 bank 4 个 MainBTB way（Victim 元数据被裁）；`train.meta.tage_entries` 10 个预测槽完整 | 同上 `[验证侧依据]` |
| 输出 | `prediction.fastTakenVec` / `toSc_providerTakenCtrVec` 10 槽完整 | 同上 `[验证侧依据]` |
| 配置 | DefaultConfig 8 表；实际维度以生成闭包为准，旧 MinimalConfig 结论不继承 | [验证规格](../verification/README.md) `[验证侧依据]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `TAGE.select`；001、005、007–008、011–013、019、029–030、036 | 最长/次长与 base 回退分开；fastTaken 是 provider 候选，不是最后 weak-provider 选择；S2/S3 可能因方向而纠正 | 无 provider/弱/强、最长/次长、基础预测强弱、向量非首位、不同历史/位置；原请求输出不跟随最新 PC | [TAGE 行为审查](../verification/evidence/reviews/tage-functional-definition-review-20261016.md) `[验证侧依据]` |
| `TAGE.learn`；002–004、006、009–010、014、017–018、020–021、032 | 方向升降边界不回绕；只有合格目标申请分配，失败维护释放保护但不损坏身份；同拍意见先净聚合 | 条件 taken/NT、长表候选可/不可分配、合格弱来源、共享选择器同向/相反意见；`TAGE-032` 原资格门禁不替代其它来源 | [行为审查](../verification/evidence/reviews/tage-functional-definition-review-20261016.md)、[竞争重建合同](../verification/contracts/tage-competing-rebuild-contract-20261020.json) `[验证侧依据]` |
| `TAGE.service`；015–016、022–028、031、033–035 | 原逻辑 key 和当前 owner 决定服务，各分支方向/保护独立；禁用不新学；不串写邻居或退回旧计数 | disable、非条件、连续相邻反馈、迁移后陈旧原端口、混合稀疏反馈、同拍分配；`TAGE-026` 迁移后旧 provider-way 的 XFAIL 保留 | [行为审查](../verification/evidence/reviews/tage-functional-definition-review-20261016.md) `[验证侧依据；enable/reset 维护分区待设计确认]` |

## 4. 时序、服务与生命周期

- `t0_fire` 是训练脉冲；`s1_fire` 驱动读回应答，`t0_fire` 推进训练流水；驱动层用独立
  S1/S2 token 防止连续 S2 fire 清理陈旧读。`[验证侧依据]`
- 训练原 MBTB 身份和条件资格；meta-only 与重新读表两条路径不同，同 bank 需读才反压。
  `[实现观察]`
- 分配只在更长合法候选，随机筛选空时回退；同选择器先净票再饱和。`[实现观察]`
- useful 扫表与 entry 方向存储分离；扫表清 useful 队列不能清 tag/方向；迁移后陈旧 way
  的 XFAIL 不关闭。`[验证侧依据]`
- 复位拍输出不比较；写缓冲同拍双写/合并和满队列有界释放仍是覆盖/实验缺口。

## 5. 独立依据与证据边界

- 相关顶层/集成合同：[竞争重建合同](../verification/contracts/tage-competing-rebuild-contract-20261020.json)；
  TAGE 本层独立依据仍以
  [TAGE 行为审查](../verification/evidence/reviews/tage-functional-definition-review-20261016.md) 为主。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)。
- 固定 Scala 位置：`Tage.scala:96-189,210-255,371-460,489-658`、`TageTable.scala:118-219`；
  实现观察不直接作为 golden。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  记录完整 seed1 TAGE 248 PASS/0 FAIL/1 XFAIL；旧 10-30 结果不自动继承。
- 保留反例：`TAGE-026` 及旧 XFAIL 保持原判定；多槽 alternate、同拍写缓冲合并仍属已定义
  功能点的情况枚举缺口。

## 6. 当前与历史边界

[2026-10-30 模块复核](../verification/evidence/module-reviews/tage-module-review-20261030.md)
的端口/位宽事实可追溯；其 247 PASS/0 FAIL/1 XFAIL 与覆盖数字属于当时验证源码和选择，
不自动成为当前判定。2026-10-16 行为审查继续作为独立合同来源，但旧源码结论不继承。
设计 owner、逐条确认人与确认记录仍待补。
