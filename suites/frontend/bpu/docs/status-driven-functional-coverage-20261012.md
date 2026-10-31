# 状态等待、DUT 版本整理与功能覆盖增量

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


2026-10-15 后续发布说明：状态等待与 DUT 整理已进入完整生产回归；最新
`production-ittage-directory-events-20261015-v1` 为15,595 PASS、7 strict XFAIL、0 SKIP，
307个功能点全部执行，BPU33257/46541，shadow选择cross29/30。
本轮067将批量十标签改为真实分配/消费事件，21分配与231消费的reached/checked
对应、四组均100%；同一case加一次未满reuse，保留全部原状态/端口/PHR/公开输出
及drain检查。十DUT原生命中集合和分母完全保持、新增0，不用分母改变叫行覆盖
上涨。集成ITTAGE维护的needReset/resetSet已在memory-direct导出，但当前committed
写状态未包含needReset，后续需按真实完成契约补齐，不以固定等待替代。见
[目录事件、完整发布和边界](ittage-region-lifecycle-20261013.md#2026-10-15事件化分配提交和预测消费分别测量)。
此前复用073容量准备，补强072的八个逻辑provider/置信度selector路由，实际完整
提交比较后的reached/checked均8/8；不增bank遍历、case或老化生命周期。完整生产
精确新增8键、十DUT零回退，七键直接提交、一键为伴随预测，均旧范围未见。见
[路由事件与正式证据](integrated-tage-selector-events-20261014.md#八个逻辑selector的输入路由加强原072不增加物理枚举)。
073新增真实TAGE useful维护生命周期，并修复committed等待未包括维护状态的问题。
两触发场景六组reached/checked完整、每例255次增量/4128清理写握手/七项保持，
完整生产精确新增92键、十DUT零回退；不是bank扫描。见
[073语义与发布](hardware-event-functional-points-20261013.md#tage-useful老化073的真实事件资格与完整发布)。
SC整体范围拒绝曾增加17原生键（SC3、TAGE候选算术14）；后续事件语义版新增
合格增减票抵消证据，52/52 reached/checked完整，原生新增0、不以分母改变宣称上涨。
MicroRAS事件迁移及年轻RETURN取消已完整发布，4/4 reached与checked均完整，
原生新增0。TAGE selector合格训练及真实预测消费现也完整发布，精确新增11键、
十DUT零回退，见 [TAGE事件证据](integrated-tage-selector-events-20261014.md)。
此前中性S2修正场景实际重叠较老push和错误路径CALL，验证老地址前递、年轻操作
冲刷及最终目标/真实退休/排空，补10语义bin及10原生键，集成MicroRAS至89/91。
其余8原生键为自然哨兵缓存路径，不做bank枚举、不增加settle猜测；70新纯契约通过。
此前连续早级call/return场景以两种pending组合补16语义bin及46原生键，集成
MicroRAS83→87/91；独立MicroRAS91/91不变。完整9寄存器/公开输出、真实退休/全部
提交单元、PHR与状态排空均检查；67项新增纯契约，不枚举bank或增加settle猜测。
此前目录生命周期场景以20个capacity/reuse/replacement输入、19笔真实写及每步全部
resident回读闭合10语义bin，新增46原生键，集成RegionWays至162/162；不是bank枚举。
独立零置信度跨region重写仍普通FAIL，不计覆盖、不新增XFAIL；目录满行不能豁免它。
此前真实集成high-index provider/base别名场景，10语义bin、70原生键通过；
66键恢复旧物理范围，4键旧范围也未见，不扩大bank枚举。upper1读响应已达到，
但后续dirty/写回检查正常FAIL，因此其完整契约仍不计覆盖。
MicroTAGE独立index/tag上下文新增20项语义bin、8项实际物理更新bin及3原生行，
至9904/11053；既有same-PC缺陷保留。新增退休感知边界场景再补upper3/4/5的27项
语义bin，去重新增10原生BPU键。此前RAS退休丢失故障场景补36语义bin及4原生键，
至569/585，六上下文逐周期比较全状态，明确不宣称正常FTQ合法性。
十DUT零回退。最新已发布64worker pytest455.64秒，完整刷新667.54秒。
见 [最新报告](../REPORT.md)、[停流与退休边界](shadow-wrap-boundary-retirement-20261013.md)、
[MicroTAGE输入分层修正](utage-split-context-useful-20261013.md)、
[RAS故障场景与真实metadata](ras-retirement-gap-20261013.md)、
[集成high-index useful](integrated-high-index-useful-20261013.md)、
[目录生命周期与普通失败](ittage-region-lifecycle-20261013.md)、
[早级MicroRAS流水线与剩余行分类](early-micro-ras-pipeline-20261013.md)、
[中性S2修正与错误路径CALL冲刷](neutral-micro-ras-correction-20261013.md) 和
[后续功能场景及行回退修复](shadow-response-gap-design.md)。下文保留2026-10-12
选跑阶段的测量边界，“未全量发布”等描述仅指当时，不代表当前状态。

本轮不修改 RTL、不扩大 bank 枚举，不使用 VPI 或内部写入。行覆盖保留原生
LCOV 的 `v_line + v_branch` statement-span 口径，不减少分母。以下是选跑验证和
隔离增量，**不是新全量回归发布**。

## 周期不再承担完成条件

原来的 reset 256/512 次轮询，以及训练后的 5/6/9/11/15/24 周期等待，分别
改为实际 resetDone、训练流水寄存器和 pending write 状态判断。共享实现位于
`suites/frontend/bpu/runtime/wait.py`、`common/monitor/activity.py`；每个 DUT 的精确
只读信号契约位于自己的 `bundle/activity.py`。绑定缺失直接报错，不退回固定等待。

这里是薄封装：使用 xreactor 正式 `PythonPredicateTrigger`、`AnyOf`、`SimTimeout`
和现有 CycleMonitor，没有另造 scheduler、task queue 或覆盖率合并框架。

等待分成两种语义：

- `pipeline` 空闲：反馈已经走完计算流水；不承诺 SRAM 已提交。
- `pipeline + writes` 空闲：流水与待写缓冲都已排空，适合串行训练读回。

同 bank 读优先时不能把两者混为一谈。需要提交的集成场景先停止 prediction
读，再等待缓冲排空；并行观察场景只等其承诺的退休条件。MicroTAGE SRAM 即使
没有 request valid 也持续选择 bank，所以不能声称只降低 FTQ ready 就能清空它。
独立 MicroTAGE 训练也不错误地要求合法的 pending shadow 必须排空。

MainBTB multi-hit cleanup 只接受所需 S2 清理脉冲，等待期间停止重复提交缓存的
clear，再按注册写请求及 pending write 状态退休。TAGE read-pressure 则由 agent
持有持续读流，训练流水退休后停止读流、收齐 Scoreboard，再等待写入提交；用例
不需要计算 `transactions + 12` 个读请求。

1024/256 是可配置失败预算，不是每次必须等待的周期。超时异常包含条件名称、
tick、采样次数和最后 pending 状态。重定向默认等待对应 PC 的 metadata；CSR
配置等待第二级实际生效寄存器。显式传入的背压持续时间、单周期脉冲、reset
宽度以及 Scoreboard 的响应延迟仍保留：它们定义激励/协议，不是经验性 settle。
测试层不增加 falling-edge 操作。

第二轮同时迁移了场景层的排空调用：alignment、三类 ABTB counter 场景、
natural、lower/force bootstrap、history/alternate、two-program/policy/aging
准备中的 `settle(16/12/8)` 改为 `observation.drain()`。它调用公共
`agent.drain_prediction_work()`，要求已经停止年轻预测，不悄悄改变 ready 或
enable。持续预测刺激窗口仍显式存在；“观察 64 周期的自然流”与“等任务完成”
是不同操作，不能把前者误当作提交保证。
PHR 恢复/修复及重复 RAS 退休的停流等待也使用同一接口；`settle` 不再带隐式
6 周期默认值，调用它必须明确提供观察窗口长度。

缩短等待暴露了两个场景准备问题，最终断言均保留：

- TAGE alternate 场景搜索 table2 时，不能把偶然分配到 table3 的候选也保护为
  useful 饱和，否则 table2→table3 所需候选被自己耗尽。只保护低表邻居。
- 集成同 bank 场景取消循环建立后的额外 24 周期，改等重定向 metadata；
  pending、接受间隔、MainBTB 更新和更长历史 provider 分配仍全部检查。

自由运行 LFSR 不保证每次分配到 table1/way0。历史上下文更新用例检查真实捕获
的 table/way 身份保持以及独立预期 counter，不把物理身份硬编码为时序常数。

## DUT 目录只保留一个 SDK ABI

10 个生成 DUT 的 `xspcomm/` 均统一为 ABI 3、0.3.0 文件和规范相对链接；移出
混杂的 0.1.0 文件及重复 ABI 别名。旧文件保存在
[`results/dut-sdk-cleanup-20261012-v1/receipt.json`](../results/dut-sdk-cleanup-20261012-v1/receipt.json)
记录的逐 DUT 备份中，可恢复。**未修改系统 ABI 1 文件**。

`tools/dut_sdk.py` 提供全体预检查、SONAME/依赖检查、规范化和异常回滚；
`tools/rebuild_memory_direct.py` 在新构建与 resume 中均执行同一规范，避免下一次
构建重新带入多版本。保留正常工作的 ABI 3 extension bytes，不为统一 build-id
而替换兼容扩展。全部 10 DUT 的真实 memory-direct monitor 绑定已通过。

## 行缺失对应的新功能点：ITTAGE 目标反馈

旧集成行缺失集中在 ITTAGE provider/alternate 计数器更新、低置信度目标改写和
对应 WriteBuffer，而独立 ITTAGE 行覆盖已满。这说明缺的是**集成反馈状态转移**，
不是再测试几个物理 bank。

新增 `BPU-INT-062`：一个真实恢复的历史上下文、13 次有目的的目标反馈，独立
`IttageContextModel` 在驱动前计算期望，Scoreboard 比较 provider/alternate 元数据
及公开 S3 目标。正常 public metadata 只提供 LFSR 分配提议，不用于生成计数器、
目标或正确性期望。10 个语义 bin 全部闭合后才发布功能覆盖：

`allocate / increment / decrement / high_hold / low_hold /
provider_and_alternate / alternate_selected / alternate_penalty /
zero_confidence_target_write / public_target_checked`。

最终源码隔离复跑 1 PASS。相对 2026-10-11 全量的相同 46,541 个行键，新增
**102 个此前零计数的原生 RTL 行位置**：

| RTL 源文件 | 新增行覆盖位置 |
| --- | ---: |
| Ittage.sv | 48 |
| IttageTable.sv | 6 |
| IttageTable_1.sv | 1 |
| WriteBuffer_28.sv | 47 |

入口是 `tests/bpu/testcase/test_ittage_target_feedback.py`，协议、参考模型、比较、
覆盖分别放在 agent/driver、model、checker、coverage 层，不在测试函数里搓时序。

[`functional-line-delta.json`](../results/ittage-semantic-feedback-final-20261012-v2/functional-line-delta.json)
列出每一行的源位置、Scala 引用、功能点和计数，记录 LCOV/RTL 哈希。
`tools/coverage_delta.py` 要求单个隔离场景 PASS、完整 pytest 收据、功能点 PASS、
相同指标/行键/RTL 身份和未改变的缺失行文本，否则拒绝归因。它不发布全量联合率。
该场景不声称覆盖全部历史 hash、region replacement 或 FTQ metadata 生命周期。

## 响应选择功能覆盖的采集缺口

原来响应选择 collector 只挂在 direction-recovery；其他已经完成独立 replay 的
集成场景未采样该组。现在 natural/lower/SRAM 等成功场景也经过同一个 reset-derived
replay、有效 payload 和最终比较门禁，所有比较通过后才保存 coverage。

最终 10 个集成场景加一个 direction-recovery 场景的独立复验，使
`integrated_shadow_response_selection` cross 从旧全量 **13/30 → 19/30**，整个组
**85.83% → 90.83%**。其中 16 个 priority bin 覆盖两个逻辑 table 的 8 个 slot，
另有 3 个真实 fallback bin：原有 upper slot2，以及非零历史/双程序场景检查的
lower slot5/6；不是靠多复制 bank 测试。对应缺失功能归因在 BPU-INT-048/049/050
的成功重放中得到补充，而不是用 testcase PASS 直接代替 response payload 比较。
nominal 32、reachable 30 的定义不变。剩余 11 个 fallback bin 仍是功能缺口，
不能因 priority 已满、测试 PASS 或行命中而计入。

最终选跑汇总与正式 coverage API 合并的数据见
[`summary.json`](../results/status-driven-qualification-20261012-v1/summary.json)、
[`selection-functional-coverage.json`](../results/status-driven-qualification-20261012-v1/selection-functional-coverage.json)。

## 剩余行缺口如何推进

下面以 2026-10-11 历史全量为定位基线；候选归因并不等于已完成可达性证明，
也不应把不可达性分类当成新的功能通过率。

| 缺失来源 | 基线缺失行位置 | 功能方向与边界 |
| --- | ---: | --- |
| 集成 BypassShadowBuffer 两种实例 | 3225 | priority/fallback、chosen/hits mask、恢复后的非零历史、读回与替换；优先补缺失语义 bin，不扩 bankset 笛卡尔积 |
| 集成 Phr | 1417 | redirect/override/commit 的真实历史写入与生命周期；旧分析的 1407 个 odd-metadata 条件行尚无全局合法性证明，不能伪造奇数指针或豁免 |
| 集成 TAGE/SC/BTB 写缓冲等 | 按源文件区分 | 将具体 write arm 映射到 owner、dirty/clean、命中/未命中及同拍冲突，再用模型预期验证；不是每个 clone 都创建一套枚举 |
| 集成 RasStack/MicroRas | 59 / 8 | 嵌套/重复返回、恢复与 committed/speculative 边界，仍需逐缺失 arm 核实 |
| 独立 SC | 336 | 已有局部矛盾条件证明，保留原生分母；不能通过刺激命中自相矛盾赋值 |
| 独立 TAGE | 120 | 历史局部证明只覆盖各自已核验的子集；其余须重新与当前缺失键求交，不能整包宣称不可达 |
| 独立 MicroTAGE | 1152 | shadow 选择/恢复/训练策略组合仍是重点；已知持久性缺陷与未覆盖路径分别记录 |
| 独立 RAS | 20 | 逐项分辨功能缺口与已知 enable 行为缺陷，不用更多物理 bank 代替判断 |

推进顺序是：缺失行 → 对应条件/状态转移 → 缺失功能 bin → 小而有目的的序列
→ 独立比较 → 功能采样 → 原生行增量复核。物理 clone 只选代表实例；只有功能
确实要求区分的状态/逻辑 slot 才参数化。

## 复验与报告范围

- 框架、各模块模型/Scoreboard、负向契约：**13,096 PASS**。
- 六个独立预测器初轮：382 PASS、4 已知 XFAIL、2 准备失败；两个失败修复后与
  两个集成同 bank 用例联合复测 **4 PASS**。初轮失败证据保留，不冒称初轮全绿。
- MainBTB 状态清理更新后的完整 testcase 与 cleanup 模型：**49 PASS**。
- 最终 BPU 时序重点：**9 PASS**；新 ITTAGE 场景另外隔离复验 **1 PASS**。
- 场景层排空迁移后的 natural/lower/SRAM/force/history/alternate/two-program/
  policy：**10 PASS**。长 useful-aging 场景没有在本轮重跑，不外推其通过状态。
- ABTB 三类物理矩阵各选一个 bank0/set0 代表：**3 PASS**，不扩 768 项枚举。
- PHR 外部恢复、S2/S3 taken/not-taken 修复和重复 RAS 退休：**12 PASS**。
- 最终 direction-recovery：**1 PASS**；包括原有 upper fallback payload 检查。
- 7 个历史全量 XFAIL 未通过本轮变更消除，也没有新增 XFAIL 来隐藏失败。

完整生产矩阵尚未重跑。正式全量指标继续属于旧报告，不能把选跑或历史/当前
数据联合标成当前正式覆盖率。逐周期 JSON 和波形仍默认关闭；仅显式诊断时导出。
