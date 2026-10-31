# 集成 MicroRAS：自然早级 call/return 流水线，而不是物理地址遍历

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


后续INT-069已独立补全中性S2 correction/较老push/较年轻错误路径CALL的动态检查，
完整生产集成MicroRAS至89/91，仅剩133/134的局部集成约束。本文83→87/91及剩余
四行归因保留为该阶段过程；最新证据见 [后续修正场景](neutral-micro-ras-correction-20261013.md)。

起点为已发布的 `production-ittage-region-directory-20261013-v1`，
BPU33073/46541，集成MicroRas83/91。独立MicroRAS的91/91不能代替集成行为检查。
原集成嵌套调用主要依赖MainBTB的S2修正，修正冲刷使相邻S1的push/pop组合很少出现。

## 新需求 BPU-INT-068

只使用一组非别名程序几何：三次不同地址call，随后三次按LIFO返回。比较两种
流水线意图：立即return，或中间隔一条action0普通跳转。没有bank/set笛卡尔积，
也不把普通跳转当成虚构的neutral commit。

真实公开训练同时安装MicroBTB/MainBTB；所有反馈metadata来自因果关联的真实输出。
开启真实RAS后，要求整个输入程序由UBTB在连续S1周期接受，完整预测含PC、target、
taken、position及override标志逐项比较，S3 metadata由既有完整PHR association关联。
不得按实际provider过滤成功请求或只用晚级修正替代所需早级预测。

两种实际组合分别为：

| 输入意图 | 必须实际执行的MicroRAS组合 | 独立预期 |
| --- | --- | --- |
| 三call后立即return | S1 pop、S2 push、S3 push | 消去最年轻push，前递较老S3返回地址 |
| 插入一条普通跳转后return | S1 pop、S2中性、S3 push | 消去S3 push，返回main RAS top输入 |

[`共享纯参考`](../uras/model/pipeline.py) 按pending操作和优先级从reset
重放全部9个MicroRAS寄存器及完整输出；地址采用BPU既有halfword表示，return PC
由16-byte对齐组、CFI位置和一条halfword返回偏移独立计算。
[`静态Bundle`](../bpu/bundle/ras_micro.py) 仅用memory-direct/trace-derived只读视图；
[`@on Monitor`](../bpu/monitor/ras/micro.py) 采集完整周期输入/状态，
[`Checker`](../bpu/checker/ras/micro.py) 比较后更新独立预期，后台失败锁存后由
前台抛出。仅保留64帧内存窗口及最终6/7个语义见证，不导出逐周期JSON。

[`场景`](../bpu/case/ras/early.py) 还用既有retirement driver连续提交6笔
真实call/return metadata，比较全部8个提交单元、head和每笔接受/应用，最终head回0。
PHR从reset比较52个物理位、76个fold寄存器及完整公开来源。停止年轻请求后按实际
流水线状态排空，再要求全部MicroRAS pending操作为0；不使用经验性settle周期。
[`case入口`](../tests/bpu/testcase/test_early_ras_pipeline.py) 只选择两种输入意图。
8项契约×2种意图共16格，在所有比较和排空成功后才能导出覆盖。

边界明确：main speculative RAS的top是MicroRAS模块输入，**不是独立全main
speculative stack模型**；提交栈和已知程序目标另行独立比较。这里不声称完整FTQ
合法性或所有RAS组合，不修改RTL，不用VPI、内部写入或新增XFAIL。

## 资格与原生差分

相关纯契约173 PASS，其中新67项：27组手算pending组合、真实3-call操作次序、
修正/flush/held/cold恢复、全部9个晚期寄存器故障、两个输出故障、lossless/reset门禁、
前台异常传递、pending未排空、非法几何和每项缺失coverage门禁。没有测试移除。

同一1753文件冻结epoch的两个隔离资格均退出0，不发布根报告：

- [`立即return`](../results/integrated-early-ras-adjacent-qualified-20261013-v1/exit.json)：
  250观察周期、783项MicroRAS检查、5711项PHR检查、823项提交检查；
  [`原生新增37键`](../results/integrated-early-ras-adjacent-qualified-20261013-v1/functional-line-delta.json)。
- [`中性间隔`](../results/integrated-early-ras-neutral-gap-qualified-20261013-v1/exit.json)：
  265观察周期、833项MicroRAS检查、6072项PHR检查、868项提交检查；
  [`原生新增42键`](../results/integrated-early-ras-neutral-gap-qualified-20261013-v1/functional-line-delta.json)。

去重并集为46键：MicroRas4、MicroBtb36、MicroBtbReplacer5、RasStack1；46键旧全
物理范围也均未命中。MicroRAS目标行190/191/192/196实际命中，预计83→87/91。
其余增量是自然调用链伴随的早级缓存写/替换和主RAS路径，不能全叫MicroRAS新功能。

## 完整生产发布

[`全量终态`](../results/production-early-ras-pipeline-20261013-v1/exit.json) 已退出0且
正式发布：14,998 PASS、7项原有strict XFAIL、0 SKIP；302功能点全执行、295 PASS。
213功能组中201达到完整目标，新组16/16格闭合。64worker pytest443.99秒，
包含原生处理/报告/门禁的完整刷新656.77秒。相对上一生产只增67纯检查和2个DUT
case，共69项，无旧case移除或旧功能/XFAIL状态变化。

[`增量/发布复核`](../results/production-early-ras-pipeline-20261013-v1/early-ras-increment-audit.json)
重新验证64收据、972功能输入及1753文件冻结epoch；两个隔离资格、全量和当时发布代码
完全一致。十DUT旧命中零丢失，唯一增量精确等于两个隔离结果的46键去重并集，
BPU33073→33119/46541，其余九DUT原生指标不变；集成MicroRAS83→87/91。
原有功能schema和每个重复命名实例保留；根JSON/HTML、canonical LCOV及profile
索引一致，两个有界语义summary与各自资格完全相同。memory-direct/VPI=False，
RTL、信号及构建身份不变。

旧全物理与当前生产仍是不同范围：旧命中丢失7428键，新命中250键，不能把所有
损失都自动解释为physical-only；完整原生分母均保留。shadow cross仍29/30，
ITTAGE目录组10/10仍保留。`formal_current=false`、
`independent_full_dynamic_audit_complete=false`、`goal_complete=false`保持。

## 剩余4行的归因，保留完整分母

133/134要求`s2_override && !s2_fire && call`。当前BPU中：
`s3_fire = s3_valid`，所以`s3_ready = s3_fire || !s3_valid = 1`，
`s2_fire = s2_valid`；而`s2_override = s2_valid && difference`。
编译RTL明确把MicroRAS的S2 fire接到`s2_valid`，因此这个局部两态条件矛盾。
裸MicroRAS仍允许独立驱动这些输入，其held-correction用例有价值，不能外推为模块
全局不可达；集成模块分母91不扣除这两行。

[`当前源码绑定的只读局部复核`](../results/micro-ras-held-correction-local-review-20261013-v1.json)
核对Scala及两份编译RTL，检查16种局部赋值，并拒绝4种连接/守卫/推进条件变异。
它不增加功能PASS，也不是完整RTL形式可达性证明。

180/181为中性S2 correction下较老S3 push的前递，该阶段仍是动态候选，未自动归类不可达。
一个有意义的后续输入是：早级三call已热，普通跳转在UBTB冷、MainBTB热，产生真实
S1 not-taken→S2 taken中性修正，与较老call重叠。单纯改错UBTB target不能保证S2
correction：当前S2只比较taken、position、attribute，而不比较target。此候选现由后续
INT-069验证，并加入真实wrong-path CALL的冲刷要求，见文首链接。

已有ITTAGE零置信度跨region重写普通FAIL、shadow upper1普通FAIL及7项strict XFAIL
均未解决，不能从本次新PASS或原生行增量推断整体目标完成。
