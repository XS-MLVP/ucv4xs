# 从 shadow 行缺口到功能场景：部分回绕后的旧项回读

本记录包含场景设计、隔离资格、首次门禁拒绝与修正后的完整生产发布。
最新生产为 `production-sparse-boundaries-20261013-v1`：shadow cross29/30，
BPU32957/46541，14,702 PASS/7 strict XFAIL/0 SKIP，298功能点全执行；
上个稀疏场景的四格及本轮upper3/4/5都已完整比较，只有upper1未覆盖。
见 [停流后已接受任务、边界修正和最新发布](shadow-wrap-boundary-retirement-20261013.md)。
下文按历史阶段保留证据。此前 `production-semantic-partial-wrap-20261013-v2` 已发布：shadow选择cross为22/30，
相对上个生产基线净增25个 BPU 原生键、零回退。结论和剩余8格见下文发布段落。
设计起点的选跑测量（10个既有场景加 direction recovery，不含 aging）曾为19/30；
该历史数不代替后续完整测量。

## 源码依据

原始 Scala：
`XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/BypassShadowBuffer.scala`。

- 101–114：按读 index 得到 hits；优先选 hits 与 priorityMask 的交集，
  交集为空时选 hits 的最高位，相关选择结果寄存一拍后使用。
- 116–117：只有 entry payload valid 与 hasHit 同时成立，才有有效响应。
- 231–234：写入 enq slot 后，priorityMask 更新为覆盖 0 到该 slot 的前缀。
- 243–258：写回成功只清 dirty，不清掉 buffer entry 的 valid/index/payload。
  因此“已经写回 SRAM”不等于“shadow 中不存在旧索引”。

独立模型对应 `bpuverify/bpu/model/bypass/model.py` 的 `select/advance/outputs`；
模型从 reset 和实际边界输入推进，不从 DUT shadow 状态初始化。

## 真正缺少的状态组合

fallback 的前置条件不是某个 bank/set，而是：

```text
hits != 0
hits & priorityMask == 0
所选 entry 的 payload valid == 1
```

旧项位于 slot k > 0，新程序写入并部分回绕到 slot p < k；
新前缀只覆盖 0..p，而旧项仍留在 k，就能形成该条件。
回读还必须来自真正的 PC/旧 folded-history 请求，完整比较 tag、position、counter。

slot0 fallback 由 reset 清空 hits 与非零前缀总含 bit0 的不变量排除。
其余 30 个 bin 是当前未排除的本地状态组合，并不意味着已经证明每个组合
都可由集成 BPU 的合法程序到达。未命中不能直接当作不可达，也不能直接豁免。

既有 selected 测量中的 fallback 是 upper slot2、lower slot5/6；
当时其余 11 个 fallback bin 尚未命中。需要以新完整测量更新这个列表。

## 与现有两程序场景的区别

`bpuverify/bpu/case/bypass/two_program.py` 的目标是第二程序完成全部 8 slot 驱逐，
随后从 SRAM 读回旧程序。它要求返回前 shadow 中完全没有旧 index。
这与“部分回绕、旧项仍保留、mask 不选它”的 fallback 前提不同；
延长同一场景的固定运行窗口通常会把所需旧项驱逐掉，而不是补齐缺口。

下一场景应复用真实双程序、MainBTB feedback、非零 PHR 和完整被动 checker，
但将目标设为“部分回绕后仍存活的旧项回读”，不增加 bank/set 枚举。
状态准备的停止条件由 reset-derived 模型的 enq/mask/旧项存活预测决定，
不能等待一个猜测周期数，也不能看到 DUT chosen/response 命中才决定刺激。

需要先证明公共预测/反馈接口能形成该准备状态；若无法精确停止年轻流水线任务，
应记录真实接受与后续副作用，调整合法输入计划，而不是写内部 slot 或伪造 metadata。

## 避免回读前重新收敛历史导致覆盖掉旧项

现有双程序场景回到先前的 not-taken checkpoint，然后靠自然预测重建稳定历史。
这适合完整 SRAM 驱逐场景，却可能在旧索引重新出现前就覆盖掉部分回绕场景保留的 shadow。

可验证的替代是保存旧自环程序在稳定历史下**真实接受的** S3 redirect metadata，
使用该程序本身已安装的 conditional CFI、taken=1 和自环 target 进行正常重定向恢复。
不能拿这个 metadata 冒充早于 startPc 的 `pc-1` not-taken 分支。

纯输入模型检查了既有 bank1 双程序配方：旧程序 PC/CFI 为 `0x40010006`，
稳定 `(lower, upper)` index 为 `(25,25)`；第二程序 PC/CFI 为 `0x40010046`，
稳定 index 为 `(121,254)`。两个稳定 PHR 都满足再执行一次真实自环的哈希不动点。
所以这一恢复计划无需先运行一长段猜测周期的重新收敛窗口。
这仅是输入配方的数学检查，尚不证明完整 BPU 中已观察到该 fallback。

## 验收边界

1. 每个公共 PC/PHR 请求与真实 S1/S3 metadata 关联，明确年轻任务和排空边界。
2. 检查所有 shadow cell、dirty/pointer/mask、useful、SRAM 端口及定义域内响应。
3. 预测选择与 payload 在刺激前由独立模型确定，禁止从实际输出复制期望。
4. required fallback bin 未出现必须抛出带状态的异常；完整 replay 成功后才导出 coverage。
5. 原始 SF/DA 行差分与对应功能路径同时记录；不改行分母，不按物理坐标扩笛卡尔积。

若新完整回归仍缺这些条件，再实现此场景。不要把已有测试通过或本文分析当作新增功能覆盖。

## 2026-10-13 上个完整生产基线

`production-representative-20261012-v2` 通过全部门禁并发布时，cross 为
**20/30**（组平均覆盖率 91.67%，不能把组平均当作 cross 闭合率）。
useful-aging 补充了 lower slot3 fallback，因此该轮缺失为：

- lower fallback：slot1、2、4、7。
- upper fallback：slot1、3、4、5、6、7。

新的 `test_shadow_partial_wrap.py` 是上述状态场景的实现候选，先独立验证，
不扩 bank/set 参数。停止条件来自 reset-derived shadow 模型，停止后仍排空
实际已接受任务，并再次确认旧项没有被年轻任务覆盖。此前完整测量不包含
这个新增候选，不能提前计入其功能点或行覆盖。

## 隔离实现记录与首次全量门禁拒绝

`BPU-INT-063` 的最终冻结源码单用例复跑已通过：
[`shadow-partial-wrap-final-20261013-v2`](../results/shadow-partial-wrap-final-20261013-v2/exit.json)。
不是把更多 bank/set 加入参数，而是以下有目的的状态序列：

1. 使用正常 MainBTB 反馈和条件／fallback 自环，分别建立两个程序的真实 upper resident；
   保留各自真实接受的 S3 checkpoint。
2. 通过完整 input-derived 模型确认旧程序的 8 个 shadow payload 均已饱和。
   短暂接受单个真实 FTQ token，退休后检查实际接受数确为 1，直到 enq 到达第一次回绕边界。
3. 恢复第二程序，模型一旦发现旧项位于 priority 前缀之外便停流；排空已接受年轻任务后，
   仍须满足 hits=0xc0、mask=0x3f，旧 payload 保留在 slot6/7，最高选择为 slot7。
4. 使用旧程序真实安装的 conditional CFI/taken/self-loop target 恢复，要求请求来自本次恢复之后。
   资格同时包含 index token、tag PC、tag folds、normal/override/redirect 输入，不看 DUT hit/provider。
5. 精确关联的新请求在 tick1641 发出，tick1642 的 slot7 fallback 全 payload 比较为
   `hit=1, data_valid=1, tag=99, position=6, counter=7`；公开 metadata 和预测结果也比较通过。
   tick 仅是该次观测证据，**不是激励代码中的等待常数**。

准备时发现的两个问题也被记录而没有放宽检查：

- S2/S3 override 可以保留 a2 index，却替换 payload/tag snapshot；只看旧 PC/index 不足以资格化返回。
- 若第一笔返回更新与缓存旧 owner 同 slot，会触发既有 dirty-copy 持久性缺陷。
  `shadow-partial-wrap-20261013-v7` 在 tick1644 正常 FAIL（dirty 期望1、实际0），不计覆盖。
  本场景将读回前置状态明确为首次回绕边界；相同 dirty 断言仍全程有效，未新加 XFAIL、未修改模型模仿缺陷。

agent 的 `refresh_stalled_prediction` 去掉了额外 ready-high 等待，并在异常时恢复背压；
机制仍由现有 control driver 承担。原 early-source 仲裁用例联合复验通过。
模型、完整输入资格、公开 payload 故障、窗口隔离、异常清理、回归门禁和行归因负向契约共 **119 PASS**。

整个成功场景经过 reset-derived 完整 replay 后，新增两项此前未命中的语义组合：
lower slot4 fallback、upper slot7 fallback。lower 是准备序列中的真实已检查响应；
upper 是本次公开返回请求的必需验收路径。准备阶段的碰巧命中不能替代返回阶段：
collector 的 `required_after_tick` 门禁要求目标路径出现在所关联 A0 请求之后，
并核对它正是该请求的一拍表响应。

相对已发布生产基线的相同 46,541 个 SF/DA 键，隔离用例新增 **15** 个原生行位置：

| 来源 | 行位置数 | 与旧物理遍历的关系 |
| --- | ---: | --- |
| `BypassShadowBuffer.sv` | 7 | 旧物理遍历也未命中；slot4 fallback 的 tag/counter/valid/position 选择臂 |
| `AheadBtb.sv` | 8 | 恢复生产范围未命中的两个真实 counter cell 转换；旧物理遍历曾命中 |

原生 upper slot7 mux 的行命中并不能代替有效 payload 功能组合，因此新功能 bin 数
不与新增行数一一对应。全部逐行证据、Scala 引用和哈希见
[`functional-line-delta.json`](../results/shadow-partial-wrap-final-20261013-v2/functional-line-delta.json)。

完整生产回归 `production-semantic-partial-wrap-20261013-v1` 的 pytest 已结束：
14,540 PASS、原有7项 strict XFAIL、0 SKIP，用时749.24秒。原生门禁随后拒绝发布：
15个目标新键全部命中，但丢失9个旧 MicroBTB/MicroBtbReplacer 键，正式报告保持不变。
见 [失败终态](../results/production-semantic-partial-wrap-20261013-v1/exit.json) 和
[精确回退集合](../results/production-semantic-partial-wrap-20261013-v1/lost-baseline-lines.json)。

缩短 refresh 接受窗口去掉了旧仲裁测试顺带发生的相邻 fastTrain 转发/预测 touch；
该测试的 held-S1 断言仍通过，但不能代表恢复流动后的相邻事务也已检查。
因此正在补充独立的 resumed-pipeline 验收：恢复自然流，明确检查两笔真实相邻接受
及其完整 S1 payload、S3 source echo/conditional metadata，再排空已接受任务。
不恢复多接受一拍的隐式副作用，不放宽行回退门禁，也不把历史 raw 混入当前测量。
上述隔离结果尚不构成新的正式全量覆盖率。

### 行回退暴露的另一个功能缺口：恢复流动后的 MicroBTB 更新

`early-source-resumed-pipeline-20261013-v8` 已通过14项隔离检查，9个回退键全部
重新命中，并相对生产基线新增10个 `MicroBtb.sv` 键。这不是恢复原 refresh 的
额外接受周期，而是补充已有 `BPU-INT-017` 的真实事务场景：

1. MainBTB/AheadBTB 暂时关闭；两组同 PC 相邻 resolve burst 分别建立 target B、A。
   每组四笔真实反馈来自2位 useful 的最多三次递减加一次替换，不是等待四周期。
   driver 返回的四个硬件接受时刻必须确为相邻周期，不能仅检查提交了四个 Python 对象。
2. 每组后通过正常接受请求及其关联 S3 source echo 验证 MicroBTB target；
   不能把残留在 held 输出上的 S2 override 误认作新 MicroBTB 响应。
3. 恢复双源和真实 checkpoint，比较每笔新接受的完整 S1 payload 与 S3 source/conditional metadata，
   直到形成一对真正相邻接受的请求。恢复 bubble 可以存在，所有已接受 payload 仍必须比较。
4. 排空真实已接受任务，再关闭其他早期来源，公开读回 MicroBTB 已学到最终 target B。

旧9行中3行是同地址相邻更新对**尚未写回的 useful 递减结果**转发，原来仅顺带命中，
单纯多等待或只验证 held valid 都不能代表这个场景。源头见
`MicroBtb.scala:130..218`；其余6行是相邻更新与预测 touch 路径。
当前实现保留最小单步 refresh，增加明确的反馈 burst、恢复流动和最终读回功能 bin，
不给缺失行加豁免、不复制观测状态充当参考。

最终冻结源码的双 DUT 联合重验已完成：
[`early-source-partial-wrap-final-20261013-v1`](../results/early-source-partial-wrap-final-20261013-v1/exit.json)
为 **21 PASS**。包括两条真实 DUT 场景，以及 payload/source/metadata、三次公开读回、
缺失/非相邻反馈接受、恢复 bubble、无相邻预测接受和背压清理契约。
最终单用例重跑也通过，10行的来源与哈希见
[`early-source-functional-final-20261013-v1/functional-line-delta.json`](../results/early-source-functional-final-20261013-v1/functional-line-delta.json)。
这10行在旧物理遍历中也全部未命中。

## 修正后的完整生产发布

[`production-semantic-partial-wrap-20261013-v2`](../results/production-semantic-partial-wrap-20261013-v2/exit.json)
已实际退出0并发布，64份 worker 收据完整且无 integrity error；根 native/feature/HTML
与本轮产物哈希相同，production profile索引已切换到本轮并通过三个产物哈希复核。

- pytest：14,556 PASS、原有7项 strict XFAIL、0 SKIP，755.34秒；完整刷新965.16秒。
- 功能点：295/295执行，288 PASS、7 XFAIL；206组中194组达到完整目标。
- shadow选择cross：**22/30（73.33%）**，组平均93.33%；lower slot4与upper slot7新增命中。
- 原生BPU：**32755/46541**，相对上个生产基线精确新增25键、零旧键回退。
  增量恰好等于两份独立资格差分：shadow7、AheadBTB8、MicroBTB10；其他9 DUT不变。
- 旧物理遍历也未命中的新键为17个，另外8个恢复生产 counter 路径。
  首次全量丢失的9键在本轮全部恢复，没有借用失败或历史 raw 拼接发布。
- ABTB语义矩阵48/48，完整物理分母仍12288、当前命中76；物理遍历仍为按需范围。

剩余 fallback 组合：lower slot1/2/7，upper slot1/3/4/5/6。
这8格保留为未覆盖需求，不把未命中自动当作不可达，不声称整个验证目标完成。

## 下一类输入语义：稀疏 conditional 四节点程序环（仅纯模型检查）

密集自环每次接受都可能产生 conditional shadow 写入；发现 fallback 前提后才
停止，已经接受的年轻任务可能继续覆盖低编号 survivor。下一步应考察减少
conditional 反馈密度的合法程序，不是为每个缺失槽乘一遍 bank/set。

本轮用已有完整52位 PHR 模型、独立标量递推、`IndexPipeline` 和 MainBTB
capacity 函数检查了以下**纯输入候选**；没有运行新 DUT 测试、登记新 PASS 或 coverage：

| 程序 | A/B/C/D（halfword PC） | A 的稳态 metadata lower/upper index | 用 before-A 历史计算的 hash（不是最终 tag 管线期望） |
| --- | --- | --- | --- |
| old | `0x40010006/16/26/36`（后三个省略共同高位） | 9 / 8 | 242 / 65 |
| second | `0x40010046/56/66/76`（后三个省略共同高位） | 105 / 239 | 212 / 127 |

A 在 position6 条件跳向 B，B/C/D 在 position7 无条件跳向下一节点；这里只检查
条件分支 taken=1 的环，不假定 A 的 not-taken 也会到 B。每四个正常接受请求只有
一个 conditional 更新机会。两程序共8个 MainBTB resident 分属8个物理组，
每组需求为1，不超过2-way 容量。128个输入推进中，完整 PHR 始终等于独立标量
递推；稳态 A 的 metadata index 来源明确是两次更早的 C→D 请求，不是当前 A→B。
两程序的 lower/upper index 均分离，所需 A tag 均能放入当前8位存储。

这只证明所选无 stall、无 override 的输入环在参考中的几何/历史关系。
还没有证明完整 BPU 能建立和返回所需 survivor，尤其不能由稳态表格推断暂停后
的 index/tag 关联。实现前须继续证明：

1. 公共反馈建立全部 resident 后，真实 S3 与输入程序及 metadata 关联一致。
2. 按已接受的 conditional 阶段提前停流，计入 driver 控制提交期间接受的年轻任务；
   不等 DUT chosen 命中再停止，也不靠固定周期扫描。
3. 恢复的 checkpoint 使用该环实际 CFI/taken/target；不能把自环恢复公式套进四节点程序。
4. 返回请求的 index、tag PC/folds、override 资格与完整 shadow/SRAM/reference 比较全部通过，
   再考虑补 remaining fallback bin；不能提前声称剩余8格均可达。

## 稀疏场景的独立资格：BPU-INT-064

新增场景已完成冻结源码下的独立资格验证：
[`sparse-wrap-qualified-20261013-v1`](../results/sparse-wrap-qualified-20261013-v1/exit.json)
为 **1 PASS**，未发布为生产结果。模型/输入资格/完整公开读回/恢复负向契约
与真实 xdist 调度检查为 **116 PASS**。

实验修正了两个不能由自环看出来的前提：

- A 的 index 来自更早的 C→D 请求，但 tag 来自**前一个 D→A 选择时的 PHR**，
  不是 A 自己公开 redirect metadata 的 before-A PHR。上表的初始 hash 因此
  不能直接当作 tag 期望。正常四节点模型现在独立检查标量52位递推、index两级
  寄存器和前一笔 tag 历史，返回时也比较公开训练 metadata 的四个 tag folds。
- 低位历史收敛不代表方向计数器已学习完成。第一次 positive 稳态甚至没有
  provider；继续经过真实方向切换后才能建立 lower。lower 已学习 positive 后
  切到 negative 会分配 upper negative；upper 接管后 lower 不一定继续递减。
  因此目标是实际形成的 **upper negative payload**，不是等待一个不再更新的 lower
  变为0。所有准备结束条件均为模型状态，512/32等上界只用于失败，不是 settling。

| 程序 | negative A metadata indices | tag历史来源 | lower/upper tag | 最终选择 |
| --- | --- | --- | --- | --- |
| old | 9 / 265 | old D 的 before-D PHR | 248 / 75 | position10 unconditional → B |
| second | 105 / 494 | second D 的 before-D PHR | 222 / 117 | position10 unconditional → B |

两程序都有真实 position6 conditional 和 position10 fallback；三个 return 节点
在 position7。共10个 MainBTB resident，每个物理组仅1个，不依赖 bank/set 遍历。
最小单 token refresh 不适合四节点环的所有阶段：停住后单步一个 token 不保证
恢复正常的 index/tag 前后文。现在恢复自然流直到下一笔 A 的关联 metadata，
再停止/排空，检查模型指针和完整 payload，而不是等待固定周期或匹配 DUT chosen。

冻结成功场景的部分回绕为 old hits `0x7c`、prefix mask `0x03`，最高 survivor
为 slot6。真实 D checkpoint 恢复 A 后，所需独立 index 请求为 source_tick2529，
tick2530 的 upper slot6 fallback 返回完整 `(valid=1, tag=75, position=6, counter=0)`。
关联的 conditional metadata 必须是 provider1、counter0、predTaken0，公开预测则
必须选择**较后的真实 position10 CFI**、taken1、target B；不能把二者混为 position6。

完整 reset-derived replay 同时命中 lower slot1/2/7 fallback。它们是明确必需的准备
响应门禁，不能替代返回阶段所需 upper slot6 的精确关联。相对生产已缺失8格，
本场景补4格；其余 upper slot1/3/4/5仍未覆盖，不宣称所有30格均全局可达。

精确 [原生增量](../results/sparse-wrap-qualified-20261013-v1/functional-line-delta.json)
为 **192个 SF/DA 键**：AheadBTB30、AheadBTBReplacer94、lower shadow27、
upper shadow10、ReplacerState27、ReplacerState_4四个。27个 lower shadow 键
在旧物理遍历中也为零，其他165个恢复生产范围路径；不能把192全称为历史新路径。
完整状态/PLRU/dirty/useful/SRAM 检查没有关闭，没有内部写入、VPI、波形或逐周期 JSON。

同范围64进程全量回归 `production-sparse-wrap-20261013-v1` 已启动；其收据、
原生零回退门禁和真实耗时尚待结束核验。独立增量不能冒充新的全量覆盖率。

### 完整生产回归终态

上述回归已实际退出0并发布：
[`production-sparse-wrap-20261013-v1/exit.json`](../results/production-sparse-wrap-20261013-v1/exit.json)。
14,616 PASS、原有7 strict XFAIL、0 SKIP；296/296功能点执行、289 PASS。
207组功能覆盖中195组完整达标，新增稀疏场景的9项契约全覆盖。
shadow cross为**26/30（86.67%）**、组平均96.67%，仍缺upper1/3/4/5。
BPU为**32947/46541**；精确增量等于独立资格的192键，十DUT均零回退，
其他9模块不变。所有64份worker收据完整且无integrity error，正式根native/
feature/HTML产物哈希与本轮相同；production profile三个产物哈希重新验证通过。

pytest耗时444.77秒、完整刷新655.00秒。最慢两个BPU场景分别在gw0/gw1，
与此前同worker初始串排不同；它们实际call416.63/321.04秒，最长独立MicroTAGE
call431.63秒，没有缩短内部状态序列或省略测试。相比上一64worker生产回归，
pytest缩短41.12%、完整刷新缩短32.14%，不是把单用例理论最大值当作全量耗时。
与旧物理范围比较仍有7504旧命中未现、154旧缺口新现；保留完整分母和范围区别，
不能声称这些损失均为物理重复。更广验证目标及独立完整动态审查仍未完成。
