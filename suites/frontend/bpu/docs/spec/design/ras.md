# Ras（ras）当前设计规格

状态：**当前基线整理稿；设计 owner 确认待完成**。适用 `public-a0c2a26cb` /
`a0c2a26cbe3c862175174bad03a1a23c406315ed` / `DefaultConfig`。本页只提炼已有合同、
固定 Scala 交互审查和验证侧端口适配中可追溯的条款；`[验证侧依据]` 表示来源是验证
合同或接口事实，`[待设计确认]` 表示策略、切点或完整 producer 前态尚无独立设计确认。
本页不是 RTL 缺陷结论，也不能替代运行证据。

## 1. 职责与边界

Ras 维护推测/提交返回栈、检查点恢复和退休动作。`Ras` 顶层包含 `MicroRas` 与
`RasStack`；主栈 top 是模块输入/输出边界，不等于完整 FTQ 返回路径。提交动作来自
`callRet` 队列的 `rasAction`，提交 `branchType` 是 DontCare。

## 2. 接口、配置与合法域

| 项目 | 当前条款 | 依据/状态 |
|---|---|---|
| 返回地址 | 恢复 API 使用偶数 51-bit **guarded 字节**地址；实际返回地址为指令末字节 +2，按 51 位回绕 | [新基线适配](../verification/evidence/runs/baseline-update-a0c2a26cb.md) `[验证侧依据]` |
| 属性 | `specIn.bits.attribute` 只剩 `attribute_rasAction` 叶，`branchType` 被裁；不再驱动/比较 | [2026-10-30 模块复核](../verification/evidence/module-reviews/ras-module-review-20261030.md) `[验证侧依据；历史运行记录]` |
| redirect/commit meta | 整芯片展平为 `meta_ras` 叶；`topRetAddr_addr` 是输出字段，不是驱动输入 | 同上 `[验证侧依据]` |
| 常量状态 | `sramResetDone` / `trainReady` 为 Scala 常量，按常量绑定 | 同上 `[验证侧依据]` |
| 阶段控制 | 只有 s1/s2/s3_fire；复位/使能顺序由 agent 管理 | 同上 `[验证侧依据]` |
| enable | `io.enable` 是真实顶层引脚，门控 spec/commit；复位后置 1；叶子 `MicroRas` 无 enable 引脚 | 同上、[Scala 审查](scala-interactions-20261106.md) `[验证侧依据；父级派生 enable 待确认]` |

## 3. 行为要求（稳定行为族）

| 行为族 / 代表 ID | 当前条款摘要 | 合法域与高风险交叉 | 依据/确认状态 |
|---|---|---|---|
| `RAS.stack`；001–005、017 | 按年龄/LIFO 消费，返回地址完整，重复组代表每一次逻辑调用；空栈不伪造有效地址 | CALL/RETURN/return-and-call、空栈/多层、同返回地址连续调用、指令长度；CALL/RETURN 同拍与等待、压缩边界、错误年轻分支取消分别比较 | [Ras 行为审查](../verification/evidence/reviews/ras-functional-definition-review-20261016.md) `[验证侧依据]` |
| `RAS.recovery`；007、009、015、018 | 回滚年轻版本并重做原操作，字节 guarded PC +2（51 位回绕）返回；原 metadata 不变 | 原 checkpoint、错误年轻路径、cfiPc 的 guard/sign 相同或不同、地址回绕；端口非规范 guard 不等于完整 FTQ 可达性 | [行为审查](../verification/evidence/reviews/ras-functional-definition-review-20261016.md)、[新基线适配](../verification/evidence/runs/baseline-update-a0c2a26cb.md) `[验证侧依据；guard×容量分区待设计确认]` |
| `RAS.retire`；006、008、010–014、016 | 只提交原调用一次，合法拒绝不冒充已接受；有界存储周转后保留原存活链；禁用不清空原栈 | speculative/committed 分离、满版本、重复组上界、遗漏退休通知、disable；守护恢复×满栈/真实 commit/同拍退休仍 gap | [退休动作合同](../verification/contracts/ras-original-commit-action-contract.json)、[行为审查](../verification/evidence/reviews/ras-functional-definition-review-20261016.md) `[验证侧依据；动态 enable 分区待设计确认]` |

## 4. 时序、服务与生命周期

- 真实 checkpoint 恢复重做并压年轻动作；commit 和 spec 是不同寿命，不能把提交请求
  当已接受，也不能用 `nearOverflow` 当接口 ready。`[验证侧依据]`
- 被抑制的操作不算 push 完成；`isCall`/`isReturn` 是排他的 Push/Pop，PopAndPush 不等于
  两者同时。`[实现观察]` 见 [Scala 审查](scala-interactions-20261106.md)。
- `spec.pushValid` 未直接与 enable/fire 合取属于叶子启停风险定位；不得因 fire=0 假设全部
  子写无副作用。`[待设计确认]`
- 复位拍输出不参与语义比较；`redirectMeta` 回灌必须投影到真实 `meta_ras` 叶。

## 5. 独立依据与证据边界

- 合同：[退休动作合同](../verification/contracts/ras-original-commit-action-contract.json)、
  [自有返回栈合同](../verification/contracts/owned-return-stack-contract-20261020.json)。
- 相关顶层合同：[相邻递归合同](../verification/contracts/ras-adjacent-recursion-contract.json)。
- 有界场景设计：[覆盖设计](../verification/coverage/behavior-coverage-design.json)；
  退休来源观察：`CommitQueue.scala:43-65`、`Ftq.scala:504-521`。
- 当前基线运行证据：[2026-11-03 适配记录](../verification/evidence/runs/baseline-update-a0c2a26cb.md)
  的 RAS 6 PASS 定向及叶 seed2 29 PASS/5 FAIL/1 XFAIL；历史数字不合并。
- 保留反例：`BPU-BUG-04`（spec push/pop 忽略 enable）、`BPU-BUG-05`（MicroRAS 忽略
  enable）、`BPU-BUG-10`（return-and-call 被当作 no-action）及既有 strict XFAIL，均保持
  原判定。

## 6. 当前与历史边界

[2026-10-30 模块复核](../verification/evidence/module-reviews/ras-module-review-20261030.md)
的端口裁剪事实可追溯到当前闭包；其 PASS/FAIL/覆盖数字属于当时验证源码和选择，不自动
成为当前判定。2026-10-16 行为审查仍是独立合同来源，但其旧基线/旧源码结论不继承。
设计 owner、逐条确认人与确认记录仍待补。
