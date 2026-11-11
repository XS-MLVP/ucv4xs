# BPU Design spec

状态：**当前条款索引；设计 owner 确认待完成**。本页面向设计/验证共同 review，按模块
职责、接口、行为、时序、合法域与独立依据组织。适用基线为 `public-a0c2a26cb` /
DefaultConfig；实际选用版本由 `ucv info bpu` 给出。现有材料包含旧基线的历史证据，
引用时须保留各自适用范围。

本页和逐模块规格中的 `[验证侧依据]` 表示条款来自验证合同、已审计的生成端口事实或
接口核对；`[实现观察]` 表示来自固定 Scala/实现路径的观察，可用于构造场景但不能直接
作为 golden；`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
三类都不等于设计 owner 签核，也不把源码观察或既有 PASS 当成 golden。

## 1. 范围与层次

本工程包含 Bpu 顶层与九个独立组件 DUT。顶层保留真实组件 RTL；组件 UT 的结论只覆盖
该组件的接口边界。顶层组合、FTQ 生产者资格与独立组件能力需要分别确认。

| DUT 键 | 设计对象 | 当前职责摘要 | 稳定规格 |
|---|---|---|---|
| bpu | Bpu | 预测选择、流水交接、历史更新和恢复 | [bpu.md](bpu.md) |
| abtb | AheadBtb | 超前目标预测、反馈学习与驻留维护 | [abtb.md](abtb.md) |
| mbtb | MainBtb | 多分支目标记录、方向更新、Main/Victim 驻留 | [mbtb.md](mbtb.md) |
| ubtb | MicroBtb | 早级目标预测与置信度维护 | [ubtb.md](ubtb.md) |
| tage | Tage | 带历史的方向选择、学习与维护 | [tage.md](tage.md) |
| utage | MicroTage | 早级历史方向预测与学习 | [utage.md](utage.md) |
| ittage | Ittage | 间接目标预测与学习 | [ittage.md](ittage.md) |
| sc | Sc | 统计纠正及学习资格 | [sc.md](sc.md) |
| ras | Ras | 推测/提交返回栈、检查点和恢复 | [ras.md](ras.md) |
| uras | MicroRas | 早级返回预测与流水交互 | [uras.md](uras.md) |

源码路径由 [workspace.json](../../../workspace.json) 声明，`ucv info bpu --dut mbtb`
自动展开精确 commit 的链接和本地路径。端口实际可见性以该配置生成的 RTL 为准。

## 2. 接口与配置

各模块的输入/输出含义、地址单位、有效域、时序、接受条件和 reset/redirect/enable 优先级
维护在逐模块规格的“接口、配置与合法域”和“时序、服务与生命周期”章节，来源限定为
当前事务合同、固定 Scala 审查和已审计的生成端口事实。

当前明确的公共边界：

- `BpuRedirect.cfi_pc` 为 50-bit guarded 半字；内部历史只消费去 guard 后的虚拟 PC；
  当前自主 pipeline 模型只将恢复 CFI 扩为 50 位，target/reset 仍受既有 49 位模型域限制。
- 完整 DefaultConfig 优化后的 Bpu 公开输出不含未被 FTQ 消费的 prediction
  target/perfMeta；这些输出的观察义务登记为 `BPU-UPGRADE-OBS-01`。
- DefaultConfig 维度以当前闭包为准：MainBTB 4 way + victim、MicroTAGE 两表 5/9 历史、
  TAGE/SC 八表；旧 MinimalConfig 尺寸/布局结论不晋升。
- 位置域为 64 字节取指块下的 5-bit `cfiPosition` 0..31。

## 3. 行为要求及依据

稳定行为族与代表功能 ID 维护在 [模块行为目录](module-behavior-matrix.md)，逐模块条款
和确认状态见上表稳定规格。当前索引如下；`module-contract` 只表示已有模块合同/源码
审查来源，不表示所有分区均已独立确认。

| 设计要求来源 | 模块 | 行为族 | 当前确认状态 |
|---|---|---|---|
| [bpu.md](bpu.md) | Bpu | `BPU.select`、`BPU.learn`、`BPU.history`、`BPU.arbitrate` | 含公开投影 blocked 与待确认分区 |
| [mbtb.md](mbtb.md) | MainBTB | `MBTB.lookup`、`MBTB.learn`、`MBTB.residency`、`MBTB.service` | 当前合同可读；含 reset/同拍替换待确认 |
| [ras.md](ras.md) | Ras | `RAS.stack`、`RAS.recovery`、`RAS.retire` | 含 guard×容量、动态 enable 待确认 |
| [ubtb.md](ubtb.md) | MicroBTB | `UBTB.lookup`、`UBTB.confidence`、`UBTB.lifecycle` | 含 alias/enable/reset 待确认 |
| [abtb.md](abtb.md) | AheadBTB | `ABTB.lookup`、`ABTB.learn`、`ABTB.residency`、`ABTB.lifecycle` | 含非空 reset/enable 待确认 |
| [utage.md](utage.md) | MicroTAGE | `UTAGE.select`、`UTAGE.learn`、`UTAGE.service` | 含失败分配/force-read 待确认 |
| [tage.md](tage.md) | TAGE | `TAGE.select`、`TAGE.learn`、`TAGE.service` | 含 enable/reset 维护待确认 |
| [sc.md](sc.md) | SC | `SC.select`、`SC.weights`、`SC.threshold` | 含无效历史常量票待确认 |
| [ittage.md](ittage.md) | ITTAGE | `ITTAGE.select`、`ITTAGE.region`、`ITTAGE.service` | 含同拍目录更新待确认 |
| [uras.md](uras.md) | MicroRAS | `URAS.stack`、`URAS.recovery`、`URAS.enable` | 含 pending handoff/reset 待确认 |

行为到场景、独立预期和检查义务的有界设计在
[验证覆盖设计](../verification/coverage/behavior-coverage-design.json)；稳定功能 ID、合同
和未证明范围从[验证规格](../verification/README.md)进入既有正文。场景证据引用不自动
给新设计授 PASS。

## 4. 时序、服务与生命周期

公共时序边界：

- 正常 S1 预测选择受 `prediction.ready`；S2/S3 继续排空，meta 按每 S3 valid 发布。
  S2/S3 override 在 ready=0 由 FTQ 特殊写入，不能当成一般必须保持到 fire 的普通响应。
- 训练 `ready` 为全部预测器 ready 之 AND，实际 t0 fire 才驱动学习；redirect 不直接
  全局屏蔽合法旧原件训练。
- 启停由 CSR 传播存在延迟：UTAGE 由 ABTB 使能，RAS/MicroRAS/TAGE/SC/ITTAGE 还依赖
  MBTB；在途已接纳服务与关闭后新学习分开登记。
- 恢复地址、PHR/CommonHR 双拍恢复、写缓冲有界释放和 reset/disable 终态按各模块规格
  的引用阅读；不得从实际输出反推期望。

## 5. 已有材料入口与历史边界

- [模块行为目录](module-behavior-matrix.md)：33 个稳定行为族、代表 ID、合法输入/历史、
  预期输出和禁止副作用；是需求分解，不是全组合证明。
- [Scala 交互审查](scala-interactions-20261106.md)：固定当前 Scala 的交互语义与覆盖设计；
  实现观察，不是独立 golden。
- [MainBTB 当前事务合同](../verification/contracts/mbtb-transaction-contract.md)：当前
  `public-a0c2a26cb` 条款可直接阅读；旧 `public-893e1580b` 统计/四路训练条款在
  [历史合同原文](../verification/evidence/reviews/mbtb-transaction-contract-893e1580b.md)。
- [流水事务合同](../verification/contracts/pipeline-transaction-contract.md)、
  [PHR 合同](../verification/contracts/phr-transaction-contract.md)：验证接口与来源约束。
- [验证规格](../verification/README.md)：场景、独立预期、观察与开放项的分类入口。
- [2026-11-03 基线适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)与
  [2026-11-08 收口检查点](../verification/evidence/runs/closeout-20261108.md)：运行证据，
  不替代设计确认。

2026-10-29/30 的模块复核和 2026-10-16 的行为审查属于各自日期、基线和验证源码的
历史材料；其端口/位宽事实可追溯，PASS/FAIL/覆盖结论不自动适用于当前基线。旧统计、
旧四路训练和旧 MinimalConfig 维度不拼入当前合同。

## 6. 待确认问题

- 各模块行为要求的设计 owner、独立依据及确认记录。
- 组件端口压力与真实 FTQ/Frontend 生产者可达行为的边界。
- Bpu 被裁剪输出的集成层观察和验证责任。
- 动态 enable 切点、FastTrain 多相对错误、SC 无效历史常量票及同拍线性化等
  `[待设计确认]` 条款。

规格变更使用 Git review；review 结论关联稳定行为/功能 ID 和适用基线。运行结果由
`ucv report` 提供，本页维护设计要求本身。
