# MicroRAS（uras）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

MicroRAS 是早级返回地址预测器，按已知主 RAS top 和 S1/S2/S3 年龄做返回来源归约、
年轻取消和主栈接管。MicroRAS 的旁路 top 是模块输入，不是完整自主主栈或 FTQ 回归。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| enable | `MicroRas.scala` 没有引用 `BasePredictorIO.enable`，整芯片删除该输入；父级 `rasEnable` 使用资格仍是 Bpu 顶层义务 | [2026-10-29 模块复核](../verification/evidence/module-reviews/uras-module-review-20261029.md) `[验证侧依据；历史运行记录]` |
| 属性 | `specIn.attribute` / `s2OverrideData.bits.attribute` 只剩 `attribute_rasAction` 叶 | 同上 `[验证侧依据]` |
| 常量状态 | `sramResetDone` / `trainReady` 为 Scala 常量，整芯片删除引脚，按常量绑定 | 同上 `[验证侧依据]` |
| 地址 | 公共 API 是 50-bit guarded **半字**地址；半字值可为奇数，不能把公开 `addr` 的 bit0 当恒 0。半字表示省略的是**架构字节地址 bit0**（半字对齐），不是公开半字值 bit0。S2→S3 返回地址寄存器在 `s2_fire` 装载 | [`testbenches/uras/model/semantic.py:8,38-43,67`](../../../testbenches/uras/model/semantic.py)、[`testbenches/uras/env/bundle/ports.py`](../../../testbenches/uras/env/bundle/ports.py)、[2026-10-29 模块复核](../verification/evidence/module-reviews/uras-module-review-20261029.md) `[验证侧依据]` |
| 位置域 | DefaultConfig `cfiPosition` 为 5-bit 0..31，边界 16/31 必须可驱动 | 同上 `[验证侧依据]` |
| 栈来源 | 用老到年轻的已知深度归约，不复制 mux 作 golden；未知前驱只判不可用，不断言无效 target | [Scala 审查](scala-interactions-20261106.md) `[实现观察]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `URAS.stack`；001–002、007–008、010–014、016 | 有已知可用来源才给返回目标；早级旁路按年龄 push/pop，未知深度不伪造有效 top；转发到期后退回正确老来源 | 已知/未知主 RAS top、S1 CALL/RETURN/return-and-call、等待中的老 CALL 与年轻 RETURN；PopAndPush 资格与主 RAS 相同 | [MicroRAS 行为审查](../verification/evidence/reviews/micro-ras-functional-definition-review-20261016.md) `[验证侧依据]` |
| `URAS.recovery`；003–006、009、011–015 | 较老权威操作保留，年轻被取消效果不复活；主来源恢复前保持不可信，不因中性修正吞掉老 CALL | S2/S3 纠正、redirect 与年轻操作同拍或连续、neutral 操作、未知来源；“两操作同时入端口”需实际推进后的存活对照 | 同上 `[验证侧依据]` |
| `URAS.enable`；006、008、015、017 | 禁用时 MicroRAS 不提供可用目标，恢复后只有合法存活来源继续；不把旧目标当新预测 | RAS enable 由开到关、老返回待决、主栈接管；叶子无 enable 门控，父级消费需核；`URAS-017` 关闭资格普通 FAIL 保留 | [行为审查](../verification/evidence/reviews/micro-ras-functional-definition-review-20261016.md)、[中性恢复合同](../verification/contracts/bpu-neutral-recovery-contract.json) `[验证侧依据；pending handoff/reset 待设计确认]` |

## 4. 时序、服务与生命周期

- 中性 S2 修正须保留老 CALL；S3/redirect 取消年轻效果且观察撤回后不复活。`[验证侧依据]`
- `isCall`/`isReturn` 排他；PopAndPush 不等于两者同时，旧反例保留。`[实现观察]`
- 复位断言拍不比较输出；复位事件仍按原节奏推进独立模型；未知前驱不能断言无效 target。
  `[验证侧依据]`
- 关闭期间不得提供旧目标；重开后只消费合法存活来源，新 call/return 可继续。`[验证侧依据]`

## 5. 独立依据与证据边界

- 合同：[自有返回栈合同](../verification/contracts/owned-return-stack-contract-20261020.json)；
  相关顶层合同：[流水合同](../verification/contracts/pipeline-transaction-contract.md)。
  URAS 本层独立依据仍以
  [MicroRAS 行为审查](../verification/evidence/reviews/micro-ras-functional-definition-review-20261016.md) 为主。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)。
- 固定 Scala 位置：`MicroRas.scala:81-146,153-246`、`Bpu.scala:198-222,321-329`；
  实现观察不直接作为 golden。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  记录叶 seed2 MicroRAS 33 PASS/5 FAIL；旧 10-29 结果不自动继承。
- 保留反例：`BPU-BUG-05`（MicroRAS 忽略 enable）、`BPU-BUG-10`（return-and-call）、
  `BPU-URAS-016/017` 均为真实 FAIL，不删除、不登记 XFAIL。

## 6. 当前与历史边界

[2026-10-29 模块复核](../verification/evidence/module-reviews/uras-module-review-20261029.md)
的端口裁剪/地址事实可追溯；其 29 PASS/4 FAIL 与覆盖数字属于当时验证源码和选择，不自动
成为当前判定。该复核未覆盖项把“地址 bit0 恒为 0”写在半字地址名下，容易与公开半字值
混淆；当前准确表述是：恒 0 的是**架构字节地址** bit0（半字对齐），50-bit 公共半字值
可为奇数。原覆盖统计不变。2026-10-16 行为审查继续作为独立合同来源，但旧源码结论不
继承。设计 owner、逐条确认人与确认记录仍待补。
