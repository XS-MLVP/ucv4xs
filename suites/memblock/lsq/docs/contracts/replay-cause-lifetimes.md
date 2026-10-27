# 同一原Load的多次Replay：原因迁移不等于完成

本合同先于新增helper/测试。固定开源`893e1580b`原样RTL，Picker/X Reactor真实
DUT及原完整参考保持；不重跑已完成的1762节点基线，不改旧helper/actor/model。
上轮61报告/933原件SHA已实际复核，无待完成后台任务。

## 语义功能点与现有功能点的缺失情形

最新完整九build中Replay源码toggle余量为叶子4970、LQ10531、Wrapper5022；
其中cause存储余892/2298/1184。原单次返回、独立metadata及少量changed-cause
用例不能代替每个实际slot的**同一原UID连续多次失败、重建依赖、最终完成**。
本轮补充LRQ-OWNER.rereplay/changed_cause、父级LQ/LSQ-REPLAY现有功能点的以下
情形，不声明覆盖全部Replay原因或关闭原strict/disabled/NC失败域。

| 功能点 | 行为和必须检查的实际证据 |
|---|---|
| CAUSE.owner | 一条原Load只dispatch一次；同一ROB/LQ/VA/opcode/FTQ/checkpoint/pdest与公开Replay slot贯穿九次输出，八次再次重放反馈不是新分配，不能释放LQ。 |
| CAUSE.translation_to_cache | 翻译完成后同一Load又遇到Cache miss；旧TLB身份的其他活跃请求回应不能解除新MSHR阻塞，只有当前匹配refill可以。 |
| CAUSE.cache_to_translation | 先前Cache依赖已完成，后续重执行再次需要翻译；相同数值旧MSHR ID绑定给另一外部活跃请求，其回应不能绕过当前TLB依赖。VA保持，只声明该次上游响应投影，不假称native TLB失效实现已测试。 |
| CAUSE.retry | MSHR nack和bank conflict的S3反馈分别保持原owner并允许再调度；将fastReplay消费者ready置0，确保公开LQ S3而不是暗中走未保留的快速通道。 |
| CAUSE.ID_history | handledByMSHR为false的C_DR/C_BC/C_TM反馈不得改写已保存的MSHR身份；仅C_DM且handled=true更新。TLB和MSHR低4位各做0→15→0的已知写入，实际Replay输出逐字段检查。 |
| CAUSE.hold | 每次公开valid都背压3拍，原slot及全部定义payload稳定；实际grant与原bank LDU S0同拍，S1/S2/S3完整推进，不能把“再次看见valid”当作执行或反馈。 |
| CAUSE.finish | 前八次需要Replay的S3都是updateAddrValid=0且同lane revoke；第九次实际重执行成功才cause0/update1，父级必须等真实LQ credit/empty才完成。叶子仅证明Replay feedback释放，不借父级结论。 |

## 合法固定源投影

每个原UID的输出原因序列固定为
`TM(0) → DM(15) → DR → BC → TM(15) → DR → DM(0) → TM(0) → BC → success`。
括号为当前依赖ID。九个原因对应九次实际grant；最后success不是第十次grant。
每层120条顺序完成Load，实际首grant必须覆盖全部public slot0..119，每owner
八次迁移都必须仍是原slot。最大一个活动原Load、不预派120未执行IQ请求、无Store。

- `NewLoadUnit.scala:1111..1127`：C_TM为TLB miss；C_DM为DCache miss，handled=true；
  C_DR投影为DCache miss且MSHR nack，S3 PriorityEncoderOH选择更高优先级C_DR，
  handled=false；C_BC为bankConflict且fastReplay未接受，miss=false。C_WF/C_MF
  在此正常源为false，本轮不驱动这些位刷覆盖，也不将它们宣称为DUT接口常量。
- C_TM的S1真实Forward kill，S2按源的粗查询dataValid=1；C_DM/C_DR/C_BC的
  dataValid=0；最终成功TLB/DCache hit dataValid=1。所有失败S3同lane revoke，
  final S3不revoke。无异常、无S4未对齐/跨页混入普通域。
- 普通LD opcode6、size3、自然对齐mask/PA页内偏移一致。4B直线指令流从64B
  块边界开始，FTQ每16条推进，offset为结束半字1/3/.../31。原UID在每次Replay
  的全部不变字段独立比较；MSHR在handled=false时保留历史而不是填0。
- 外部响应身份有界16，当前和decoy同通道不同ID，跨通道可同数值ID。每次
  绑定外部台账后才回应，当前旧依赖已经回应后才允许同ID分给另一外部请求；
  不注入未分配垃圾ID。最多2个MSHR和2个PTW filter外部身份同时活跃，不声称
  native Cache/PTW分配器真实历史已验证。错通道和错ID之后等待4拍仍必须阻塞。
- 正确fast-TLB pulse N当拍首次valid；refill N+2拍首次valid。立即重试C_DR/C_BC
  的反馈后新输出时序须单独从固定LRQ调度推导并与原参考双检，不因失败放宽。
- 本地完成后pendingNext提前一拍、pending下一拍跟随，逐条提交不跨8项行。
  真实ROB/LQ环绕按160/120，完成前不前移，不从参考/model私有owner抄slot刺激。

## 分层、运行和保留

1. Replay叶子→真实LoadQueue→真实Wrapper，用原严格fixture。先每层2UID探测，
   再各120UID完整公开slot生命周期；原探测失败/错误纠正保留，不skip/xfail。
2. 每层fresh before/after，source/build/line/toggle/branch点全集相同；旧结果与
   stream/hit不变。精确核对cause位3/5/6/8的120项×2方向、MSHR/TLB合法低4位，
   不把定向增益回填完整分子。
3. 当前1762节点九build已完成真实产物作为完整基线，下一完整after保留所有
   native贡献（含外目录48Replay endpoint与Wrapper贡献），新增3节点预计1765。
   全196份原FAIL全文必须保持；不OR覆盖，不用三层绿色子集冒充完整九build验收。
4. 只存compact原UID/每次原因/依赖/slot/实际grant/S3/release witness、原失败、
   native dat及可复现命令。默认无逐拍JSON/波形/新完整源码副本，缓存关闭。

NC/C_UNCACHE的bus/bypass与数据保持、Store地址/数据/多重匹配依赖、真实RAW/RAR
容量nack、strict/disabled、vector/Hyper、取消/异常、混合公平排空、release-wait、
头许可、完整核资源历史、全38DUT扩大回归/最终存储审计仍开放。本轮只补上述
合法可达情形，不改变整体完成标准、原分类库存或任何历史功能失败。

## 01源投影纠正（formal02前保留）

01三层4→5PASS和完整1765结果、所有原dat/JUnit/witness保留；但新helper在改PA
页内偏移后仍继承profile0的last_beat0，60/120UID实际PA[6]=1，不满足固定源1613。
因此01必须标记`UNIT_INTERFACE_S3_LAST_BEAT_UNPROVEN_PA_PROJECTION`；原TLB/refill
接口功能与覆盖证据真实，但不能再称源正确S3轨迹。无需修改任何旧RTL/参考。

仅修正本轮新helper为last_beat=bool(PA&64)，每次S3运行断言该关系，compact
witness新增PA、首次及九次反馈last_beat，独立审计逐条核对。probe02扩大至每层
8UID，以涵盖PA[6]的0和1，不能让旧2UID探测只落在bit6=0域而漏掉纠正项。
正式02各120UID仍完整不缩小，fresh before/after02及完整after02都独立实际运行；
完整基线仍使用已核验1762原节点，不重跑基线，不合并01/02 dat。

原幂等审计01在这次必要域标注修改窗口实际exit1/191.151762秒，critical SHA
断言失败原日志/receipt保留，不能冒称终点通过或只抹去失败重写。纠正后使用
新的corrected-input/post-index guard，再审新02证据及四索引，原01域限制和失败
日志必须继续在图中可查，且完成标准、所有196旧功能失败保持。

## 参数链再次纠正：formal03以32B refill的PA[5]为准

上节PA[6]推导本身仍错：`Parameters.scala:892`固定l1BusDataWidth=256，
`cache/L1Cache.scala:44`定义refillBytes=l1BusDataWidth/8=32，故源1613取PA[5]。
`DCacheWrapper.scala:54`的blockBytes=64是整条Cache块，不是refill beat，不能
混用。精确主Scala定义扫描确认总线/拍宽只有这两处定义，固定git对象逐字核验。

01/02的所有结果仍是真实LSQ接口证据，但源正确lastBeat声明撤回；02有60/120
原UID的PA[5]与PA[6]不同。此前normal metadata、RAW owners及response payload
旧producer沿用同样PA[6]假设，其固定上游lastBeat域也显式标注未证明；不改它们
的冻结代码、原dat/JUnit、UID结果或任意失败，不让这些老PASS为新合同背书。

03只改本轮新helper为bool(PA&32)并逐S3运行断言，witness逐UID与每次S3独立检查
同一32B参数关系；保留完整八UIDprobe（覆盖PA[5]真假以及与PA[6]相反情形）、
120UID三层正式fresh before/after03，完整after03仍对已完成1762基线而不重跑它。
先核验这条完整参数链后才执行03；两个先前纠正报告、首次失败日志和源域收回
都保留并索引，不能由“最终正确03”抹去错误历史。原整体完成标准不变。
