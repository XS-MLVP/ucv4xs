# ITTAGE（ittage）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

ITTAGE 负责间接目标预测、provider/alternate 目标选择、区域压缩和目录替换、并发/启停
服务。它只对唯一 taken 且 indirect 无 pop 的原件学习目标；软件构造合法形状不等于
原件真实发布。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| 历史输入 | `s1_foldedPhr_hist` / `trainFoldedPhr_hist` 只保留 9 个被 5 张表 index/tag 哈希消费的 fold（0/3/4/8/9/11/12/19/20） | [2026-10-30 模块复核](../verification/evidence/module-reviews/ittage-module-review-20261030.md) `[验证侧依据；历史运行记录]` |
| 发布资格 | 整芯片删除未被父模块消费的 `meta.valid`；适配层用 `enable && s3_fire` 作为发布资格 | 同上 `[验证侧依据]` |
| 常量状态 | `trainReady` 为 Scala 常量，按常量绑定 | 同上 `[验证侧依据]` |
| provider 元数据 | `meta` / `train.meta_ittage` 的 provider/alternate/allocate/target 字段完整保留 | 同上 `[验证侧依据]` |
| 预测输出 | `prediction` 只有 `hit` + `target_addr`；位置叶被裁 | 同上 `[验证侧依据]` |
| 地址域 | 公共 API 为字节 target；区域压缩遵守有限目录合同，不承诺受害指针永久保存旧高位 | [覆盖设计](../verification/coverage/behavior-coverage-design.json) `[验证侧依据]` |
| 分配表 | DefaultConfig 首分配表由 15 位 LFSR 选择，不固定 table 0；不能假定旧二维几何 | [Scala 审查](scala-interactions-20261106.md) `[实现观察]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `ITTAGE.select`；001–005、007、009–014、019–020 | 仅真实 taken、非返回的原件能学目标；最长 provider 置信 0 可回退 alternate；未发布原件不能训练 | 冷/已学、原已发布/未发布快照、不同 PC/历史、置信 0/正；selected target 单独比较不足以发现隐藏 provider 错误 | [ITTAGE 行为审查](../verification/evidence/reviews/ittage-functional-definition-review-20261016.md) `[验证侧依据；未发布资格反例保留]` |
| `ITTAGE.region`；008、014–015、017–018 | 复用已有 region 优先于新分配；满表只重解读受害指针，其他 target/居民不变；字节地址往返无损 | PC 区域/外部区域、同低偏移不同高位、目录有空位/满、已有区域再用及指针受害；零置信跨区重写的两个旧 FAIL 保留 | [行为审查](../verification/evidence/reviews/ittage-functional-definition-review-20261016.md)、[间接路径所有权合同](../verification/contracts/bpu-indirect-path-ownership-contract.json) `[验证侧依据；同拍目录更新待设计确认]` |
| `ITTAGE.service`；004、006、010–013、016、020 | 响应、补丁按原 PC/历史/发布资格配对；禁用不新学，fresh 原件与无资格旧原件不可互换 | 重叠查询、稀疏位置、enable 改变、读阻挡、迟到原件；并发×未发布原件×目录满尚须真实 producer 与收尾对照 | 同上 `[验证侧依据；overlap-enable-reset 分区待设计确认]` |

## 4. 时序、服务与生命周期

- `enable && s3_fire` 是父模块消费 payload 的资格；不能从 `meta.valid` 不存在推出
  所有端口压力都合法。`[验证侧依据]`
- 最长 provider 置信 0 可回退 alternate；不能只比较 selected target 而漏掉隐藏 provider
  错误。`[验证侧依据]`
- useful 维护只在无读/更新时推进，需有限公平释放；不能要求持续读下无条件完成。
  `[实现观察]`
- 复位拍输出不比较；训练从公共 branch 向量解码 kind/action，不驱动被裁 position 叶。

## 5. 独立依据与证据边界

- 相关顶层/集成合同：[间接路径所有权合同](../verification/contracts/bpu-indirect-path-ownership-contract.json)；
  ITTAGE 本层独立依据仍以
  [ITTAGE 行为审查](../verification/evidence/reviews/ittage-functional-definition-review-20261016.md) 为主。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)。
- 固定 Scala 位置：`Ittage.scala:155-168,217-307,309-416`、`IttageTable.scala:185-263`、
  `RegionWays.scala:51-90`；实现观察不直接作为 golden。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  记录完整 seed1 ITTAGE 43 PASS/3 FAIL；旧 10-30 结果不自动继承。
- 保留反例：`ITTAGE-020` 未发布资格、零置信跨区改目标两个旧 FAIL 及旧 3 个本 DUT FAIL
  仍保持；区域目录 PASS 不能关闭它们。

## 6. 当前与历史边界

[2026-10-30 模块复核](../verification/evidence/module-reviews/ittage-module-review-20261030.md)
的端口/位宽事实可追溯；其迁移后 3 条失败与覆盖数字属于当时验证源码和选择，不自动
成为当前判定。2026-10-16 行为审查继续作为独立合同来源，但旧源码结论不继承。设计
owner、逐条确认人与确认记录仍待补。
