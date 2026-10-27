# MicroTAGE：从高索引行缺口找出驱动层缺失的上下文

## 结论与测量边界

原来把 lower index128..511 的 useful 更新全部归为标签位宽缺陷，范围过大。
那个结论只适用于 **index PC/history 与 tag PC/history 相同** 的输入。
MicroTAGE 硬件本来支持不同阶段的上下文；验证 agent 之前没有提供这个表达能力。
新增 `BPU-UTAGE-023` 在真实独立 DUT 上证明 index462、完整 tag208 能成为
lower provider，并完成 useful 增减及两端饱和保持。

隔离资格运行
[`utage-split-context-qualified-20261013-v2`](../results/utage-split-context-qualified-20261013-v2/exit.json)
为 1 PASS，**不发布全量指标**。相对已发布的
`production-sparse-wrap-20261013-v1`，精确新增3个原生键；
完整元数据、关联、几何、既有 useful reference 及真实 DUT 契约复验为
254 PASS，收据 `evidence_complete=true`、无 integrity error。
不能把隔离场景的4,237/11,053当成新全量覆盖率。

后续完整生产
[`production-utage-split-context-20261013-v1`](../results/production-utage-split-context-20261013-v1/exit.json)
已退出0并发布：14,678 PASS、7既有strict XFAIL、0 SKIP，297功能点全部执行
（290 PASS/7 XFAIL），208组中196组达到全部目标。pytest445.72秒，完整刷新660.77秒。
十DUT相同行键分母、零旧命中丢失，MicroTAGE **9904/11053（89.60%）**，精确
重现隔离3键增量；其他9 DUT不变。useful更新物理cross **5128/8192（62.60%）**，
新语义组20/20。重新核验64份worker收据、输入文件哈希、正式JSON/HTML/LCOV、
范围基线指针及冻结源码后，记录
[`增量与发布一致性检查`](../results/production-utage-split-context-20261013-v1/split-context-increment-audit.json)。
这不是独立全动态审查，也不宣称整个目标完成。

## 硬件阶段与事务接口

源码并没有要求两组输入相同：

- [MicroTage.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/MicroTage.scala)
  的 A0 用 `startPc/normalPathHist` 计算 index，A1 用
  `newStartPc/s1PathHist` 计算预测 tag；后续 metadata 保存实际 readIndex。
- [Bpu.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala)
  将 `newStartPc` 接到 S1 next target，将 normal history 接到较早的 oldFoldedPhr。

`UtageLookup` 增加仅关键字参数 `index_pc/index_history`；`pc/folded_history`
仍表示逻辑 tag/反馈上下文。省略新参数时保持旧行为和原位置参数兼容。
agent 的 staged encoder 负责 A0/A1 对齐，不让 testcase 处理时钟边沿。
输入范围在 Scoreboard 提交及异步任务创建之前校验。

## 一个代表场景，不遍历高地址

输入模型用四节点程序 A/B/C/D=`0x40010006/16/80/1e2`，独立计算52位标量
PHR。A 的 tag 来自 D→A，index 来自更早的 C→D。模型与集成历史/index
reference 联合检查224步，而不是按 DUT 命中的物理槽位反向选择输入。

| 上下文 | lower index | upper index | 完整 lower tag |
| --- | ---: | ---: | ---: |
| positive 分支相位 | 462 | 11 | 208 |
| negative 分支相位 | 462 | 266 | 208 |
| 独立邻居 | 46 | 364 | 246 |

先通过真实冷 miss 反馈分配高地址 lower，再使用捕获的 provider metadata：
useful 1→2→3→3，base 同向时保持3，再3→2→1→0→0。
读回要求真实 lower provider 与 counter7→3；最后改用 untouched upper index266
证明 lower 结果没有被新分配的 upper 掩盖。独立低地址邻居始终保持其值。
分别执行串行和相邻反馈；每种节奏10笔实际接受反馈。

每种节奏还连续提交4个不同逻辑上下文的 lookup，通过绑定的
driver/monitor/Scoreboard 比较相同的完整输出。agent 的 `drain_predictions()`
统一收齐结果；调用者不使用 `asyncio.gather`。真实 acceptance 事件必须相邻，
每个 completion 必须满足既有两周期协议延迟。这是协议断言，不是固定 settle。

## 比较与采样门禁

比较同时检查 public hit/direction、metadata hit/provider/counter/predTaken、
base/strong-bias/valid/CFI、padding slots、readIndex 以及全部19个 folded-history
字段。反馈只复制实际观察且已检查的 metadata；不伪造 hit、不写内部状态。
1024个 useful 单元在实际更新及后续观察事件中逐一与 reference 比较，
串行19,456次、相邻14,336次单元比较，包括所有未修改邻居。

只有完整比较、pending 反馈及 Scoreboard 排空均通过后才采样：

- `utage_split_context_useful`：10项语义契约×2节奏，20/20。
- 原有 `utage_useful_update_routes`：继续保留8,192个完整物理 bin，本场景仅
  新增 index462 的4种更新作用×2节奏，共8格；不缩小分母，不冒称全地址通过。

33个 metadata 负向契约逐一破坏19个 history 或其他关键字段，必须抛出带状态的
Scoreboard mismatch，不能继续复用为反馈。burst 负向契约检查未完成、事件丢失、
接受不相邻、迟到及错配；20个驱动/几何契约检查输入和阶段兼容。

## 原生增量与未完成项

精确增量见
[`functional-line-delta.json`](../results/utage-split-context-qualified-20261013-v2/functional-line-delta.json)：
`rtl/utage/BypassShadowBuffer.sv:6796,6797,6799`，对应 bank2/row115，即 index462。
Scala 来源为 `SaturateCounter.scala:41,45,65` 和 `utage/BypassShadowBuffer.scala:93`。
RTL、行分母、memory-direct 访问方式均未改变；逐周期 JSON 和波形仍默认关闭。

既有 `BPU-UTAGE-021` 的768个 **same-PC** 受阻上下文及 strict XFAIL 保留。
它的失败不与新功能通过矛盾，也不能再用于证明其余383个高地址全局不可达。
剩余物理地址未执行不等于缺少383套独立功能；下一步应优先完善集成输入生命周期，
而不是将新场景复制383次刷行数。

本场景证明独立模块接口和 updater 行为，不声称完整 FTQ 输入生命周期合法性，
也不解决已知持久性、标签位宽、集成 shadow 余下 fallback 或其他模块缺陷。
更大的覆盖率闭环目标仍未完成。
