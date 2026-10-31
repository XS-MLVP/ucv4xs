# ITTAGE region 行缺口：目录生命周期与零置信度重定向是两个需求

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


本文前半记录067首次目录闭合时的历史证据；当前事件化实现见末尾
[事件边界与未满复用](#2026-10-15事件化分配提交和预测消费分别测量)。旧10/10是
阶段/检查清单的历史测量，不能与新事件分母直接比较来宣称覆盖增长。

起点为已发布 `production-integrated-high-index-useful-20261013-v1`：BPU33027/46541。
`rtl/bpu/RegionWays.sv` 的46个未命中行，旧全物理范围也均未命中，涉及远目标 region
写入、满表复用及PLRU替换。原 INT-062 的13笔反馈均在 PC region 内，不能验证这些条件。
不能从独立 ITTAGE DUT 的1398/1398推断集成层也已验证。

## 新功能点 BPU-INT-067：真实目录生命周期

20个输入 context 包含一个PC-region控制、16个不同foreign region填满目录、一个
满表已有region复用及两次新region替换。数量来自**容量+复用+替换前提**，不是
bank/set笛卡尔积；仅使用一组非别名输入，三个预测表的分配提案来自真实公开metadata，
验证其合法性，不选择某个字面table号或按实际provider过滤成功请求。

所有地址采用BPU既有halfword单位。RTL TargetWidth为20个byte位，因此region为
`target >> 19`，offset为低19个halfword位；复用独立region模型时显式乘2转成byte，
重建目标后再除2，不偷偷改变模块agent的地址约定。

静态 [`bundle`](../bpu/bundle/ittage_region.py) 绑定 memory-direct/trace-derived
只读信号；[`monitor`](../bpu/monitor/ittage_region.py) 用@on处理preedge/rising。
[`checker`](../bpu/checker/ittage_region.py) 从reset维护独立16项目录及PLRU，
比较所有valid/region、每个读/更新端口、同拍write-bypass及free/reuse/victim pointer。
期望写请求从真实接受的完整公开反馈及分配资格推导，不根据DUT write-valid生成。
仅在下一rising完整状态比较成功后记录写效果。

[`case`](../bpu/case/ittage_capacity.py) 使用真实cold checkpoint/反馈，保留
完整52位PHR比较，并要求每次回读均为计划中的零history context。每次插入或替换
之后检查**所有resident**的完整provider metadata及精确关联的最终S3 target。
旧entry按设计保留pointer，region被替换后必须按新region重建旧offset；survivor和
PC-region控制必须不变。满表reuse触碰PLRU后，两次预期victim为8和0，均实际核对。
最终排空accepted反馈及全部写效果，十项语义契约全部通过才导出覆盖。

输入源整理也修正了一点：两个PC可共享同一个16-halfword对齐的cold源，不能在
已走过的fall-through流中再次等待同一个地址。现在每个lead仅捕获一次，后续恢复
仍使用各自真实metadata；旧单源几何默认不变，有专门契约检查。

最终相关纯契约147 PASS，其中新增54项覆盖目录/source/晚期故障、T1写效果缺失、
coherent S3关联、容量几何、共享cold源及每项缺失coverage契约。真实候选1 PASS，
2587个周期/5174帧、62162项目录检查和909项公开检查；19笔实际目录写均比较。
[`冻结隔离资格`](../results/integrated-ittage-region-directory-qualified-20261013-v1/exit.json)
退出0，10/10语义格，精确新增
[`46个原生键`](../results/integrated-ittage-region-directory-qualified-20261013-v1/functional-line-delta.json)，
全部在RegionWays.sv，补齐该文件原缺口。不把它们叫46个新功能点。

## 完整生产发布与一致性复核

[`完整生产终态`](../results/production-ittage-region-directory-20261013-v1/exit.json)
已退出0并发布：14,929 PASS、7项原有strict XFAIL、0 SKIP；301个计划功能点全部
执行，294 PASS/7 XFAIL。212个功能组中200个达到完整目标。
64worker pytest445.75秒，含原生处理/报告/门禁的完整刷新657.08秒。
相对上一生产版本仅增加54项纯契约和1项DUT case，没有移除测试或改变旧功能状态。

[`增量与发布一致性复核`](../results/production-ittage-region-directory-20261013-v1/region-directory-increment-audit.json)
重新验证64收据、970功能输入及1745文件冻结epoch；正向资格、独立普通失败、
全量运行和当时发布的代码完全一致。十DUT原生分母及构建身份保持，memory-direct/
VPI=False；十DUT零旧键丢失，完整新增集合精确等于隔离46键，全部在RegionWays。
该文件116→162/162，BPU33027→33073/46541，其余九DUT不变。
新目录组10/10与生产场景的19笔实际写、62162目录检查、909公开检查均复核一致，
生产/隔离的有界语义summary完全相同；根JSON/HTML、canonical LCOV及profile
索引都指向本次完整运行。原有覆盖schema保留，重复命名的实例也逐个核验。

生产与旧全物理范围仍分开报告：旧命中丢失7428键，新命中204键；没有把这些
跨范围丢失全部自动解释为physical-only。shadow选择cross仍29/30，不把组平均
99.17%当成cross；upper1完整consumer契约仍开放。正式状态继续保留
`formal_current=false`、`independent_full_dynamic_audit_complete=false`、
`goal_complete=false`，这不是一次独立完整动态审计或全部验证目标完成。

## 独立未完成需求：已存在的远region在零置信度更新时仍被错误编码

完整cross-region target-feedback诊断保持普通FAIL，不新增XFAIL，不导入其raw。
[`最终冻结失败`](../results/integrated-ittage-region-retarget-causal-failure-20261013-v1/exit.json)
与正向资格使用相同1745文件epoch；
[`有界因果复核`](../results/integrated-ittage-region-retarget-causal-failure-20261013-v1/known-region-causal-audit.json)
检查了以下真实序列：

| tick | 独立核验的事实 |
| --- | --- |
| 297→299 | genuine feedback将foreign region0x801写入pointer0；后续目录始终保持正确 |
| 599 | 接受target=`0x40080090`的反馈，真实provider confidence0、allocate.valid0；region0x801已存在 |
| 603 | table2实际registered update为alloc0/old_counter0/pointer0/offset0x90，却带usePcRegion1 |
| 618 | 公开providerTarget期望`0x40080090`、实际`0x40000090`；altDiffers期望0、实际1 |

7436项完整目录检查及7094项PHR/关联检查均无失配；没有丢失目录写或伪造metadata。
该笔反馈的mispredict实际为0：confidence0使用的alternate已正确给出foreign target，
不能误把“provider和真实目标不同”写成“本笔最终预测错误”。初版只读因果脚本
曾错误断言该flag为1并退出，未生成审计PASS；最终脚本按真实字段0复核。
最初的raw-stream候选也曾复现，但精确coherent观测改变了LFSR分配次序，不能假定
每次都是0/1/2表。最终固定**输入意图**为先分配foreign region，再进入PC region，
最后在无新table分配的情况下回到已存在foreign region；四种合法表次序均有纯模型控制。

[`Ittage.scala:320`](../XiangShan/src/main/scala/xiangshan/frontend/bpu/ittage/Ittage.scala:320)
把`!updateAlloc.orR`直接并入usePcRegion；
[`IttageTable.scala:259`](../XiangShan/src/main/scala/xiangshan/frontend/bpu/ittage/IttageTable.scala:259)
又在old confidence为0时写入该targetOffset。编译RTL Ittage.sv:424–426/615及真实
registered update吻合这条因果链，而region本身已由独立模型证明存在。

这份失败直接证明providerTarget/altDiffers契约违例，**不单独宣称已造成架构跳转错误**：
confidence0时alternate仍可能遮盖即时预测效果。诊断位于
`tests/bpu/diagnostics/ittage_region_feedback.py`，不是默认PASS功能点。
INT-067的目录capacity闭合不豁免它；原七项strict XFAIL亦未涵盖或解决它。
完整零置信度跨region更新需求仍未完成，RTL未修改。也不声称完整FTQ、全部hash或
ITTAGE SRAM/write-buffer的独立全状态参考；没有VPI、内部写入、波形或逐周期JSON。

## 2026-10-15事件化：分配提交和预测消费分别测量

源码优先级为已有region、空项、满表PLRU。原输入只检查满表已有项复用，不能证明
“还有空项时已有项优先”。因此在同一容量生命周期填入八项之后增加一次真实
foreign-region复用；完整输入21个context、20笔目录写，case数仍为一，没有bank/set
遍历。该前提属于原067，而不是另设一个同义功能点。

新事件模型不再把reset、第几次替换、drain与真实操作放在同一维度：

| 事件族 | 稳定资格上下文 | checked边界 |
| --- | --- | --- |
| 分配 | PC-region绕过、空项选择、未满已有项复用、满表已有项复用、无命中满表PLRU替换 | 真正accepted public反馈→对应writeRegion/writePointer→下一完整16项状态及全部端口比较；PC绕过另等无关联写及完整consumer |
| 预测消费 | PC region、保留resident指针、替换后旧指针重解码 | 真正新预测及同源metadata→独立预期目标→精确关联最终S3 PC/target/taken/position；必要更正的valid也检查 |

各族分别导出reached/checked，总计四组、每个状态8个语义格。没有phase、序号、
bank/way轴或cross；reset、完整目录、来源关联、全PHR和最终drain仍是强制合同。
reached来自被接纳的完整未改写payload及reset-derived前态，不由实际write pointer
生成；checked要等完整效果，不拿候选写算术或case结尾一轮sample当完成。
每步继续回读所有resident，所以被替换旧指针和未替换邻项都必须保持规定目标。
硬件分配proposal仍是声明的public输入，没有把LFSR或完整ITTAGE SRAM参考假装完成。

仍用既有Bundle/memory-direct、@on/monitor、driver/状态等待与Scoreboard。
case只组织生命周期，consumer期望生成、比较、事件采样收回checker；失败在finally
关闭monitor后导出部分覆盖。误路由、漏写、邻项损坏、wrong-source/完整输出错误
普通FAIL，保留已到达事件，不给未完成checked。目录故障状态序列化直接保留
Scoreboard.first_failure文本，避免深拷贝异常遮盖真正错误点与状态；不修改SDK。

[`最终源码候选`](../results/integrated-ittage-directory-events-candidate-20261015-v1/exit.json)
1 PASS，pytest20.13秒、完整40.57秒；1781项源码、当前回执/功能输入及JUnit复核一致。
5604个两相观察帧、21次真实接纳、20笔目录写均通过。allocation reached/checked
各21次：free16、未满reuse1、满表reuse1、PLRU2、PC绕过1；consumption各231次：
PC-region21、保留pointer207、替换pointer3。每个新预测只采样一次，四组均100%。
未满复用实际pointer3、前态占用8项、无eviction；完整下一状态及后续消费者均检查。
目录/新事件纯契约94 PASS（含34项新契约及旧缺失bin测试的事件化），发布门禁90 PASS。

[`严格单场景原生差分`](../results/integrated-ittage-directory-events-candidate-20261015-v1/functional-line-delta.json)
相对已发布33257/46541基线为**0新增键**：新的优先级输入和可追溯事件改善功能证据，
但不把分母变化或多个sample叫行覆盖上涨。原RegionWays162/162不代表优先级输入
早已完整，更不豁免零置信跨region普通失败。
随后64进程完整生产
[`production-ittage-directory-events-20261015-v1`](../results/production-ittage-directory-events-20261015-v1/exit.json)
已退出0并正式发布：15595 PASS、7既有strict XFAIL、0 SKIP；307点全执行、300 PASS，
231功能组219满目标。pytest455.64秒、完整667.54秒。1781源码保持冻结，64收据/
987功能输入、完整JUnit、全部根报告/profile/LCOV及上述真实事件计数均独立复核。
四组完整门禁通过，旧十标签实例不混入新测量。十DUT原生分母和命中集合与前版
逐键完全相同，BPU仍33257/46541；不是补零计数行或功能点通过率上涨。
旧物理范围比较和完整分母不变，既有七项XFAIL及独立跨region普通失败继续保留。
集成ITTAGE tick/useful维护及其他动态需求仍未完成，不标完整目标完成。
