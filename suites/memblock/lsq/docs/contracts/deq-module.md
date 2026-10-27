# DeqModule：真实Sbuffer流水、特殊store写出与出队credit

状态：**功能点先于用例定义；当前89例71 PASS/18 FAIL，本体46/46、真实闭包124/124 DA、44/46 checked，因两类严格失败未验收。** 已实现公开分阶段参考、PSQ代理及独立完整UID历史审计，旧probe和所有历史快照保留。原始`DeqModule.sv`保留真实`EnterSbufferQueue`，不得用Python队列替换其下级。源码为开源893e1580b的`NewStoreQueue.scala:847-1355`。

## 1. 实际公开边界

当前top除clock为61输入/55输出，2路rdata store数据/控制、2路deq控制、完整SQ指针、VSQ head ROB、validCnt、Sbuffer/Cache/Uncache代理握手及UQ第二页输入。只能绑定原SV保留字段：

- 无redirect、ROB retiredPtr/preCommitPtr、PSQ allocated/issuePtr/WFI接口；本块使用父PSQ已经导出的committed许可。WFI和取消后未提交项处理留在真实PSQ专项，不能虚构Deq端口。
- 无size输入；真实byteMask由PSQ按size生成连续低位，长度作为领域store记录保留用于独立PA字节参考，不从DUT内部dataQueue取数据作答案。
- Uncache返回仅resp.valid与idResp.valid/is2lq，**没有动态denied/corrupt、mid/sid/nc字段**；不能假装动态覆盖MMIO返回错误/ID匹配断言。Cache响应有实际denied/corrupt，必须检查错误信息和背压保持。
- writeBack与exceptionInfo保留ROB、exception7/19及调试MMIO/NC等有限字段；exception VA输出64位来自50位VA，验证真实零扩展。gpaddr/uopIdx/vl/vstart等删除字段不伪造覆盖。
- Sbuffer输出保留VA50/PA48/data128/mask16/wline；prefetch/vecValid等常量或未使用字段未保留，不作动态覆盖。

## 2. 合法输入与独立领域语义

1. 外部PSQ代理维护两个读取位置：rdata指向尚未进入写出流水的头部，deq指向尚未收到真实完成credit的头部；entry随着各自公开moveCnt独立推进，不能把两者强制绑成同一位置。
2. 普通store必须由committed许可，不给未就绪、已有异常或未分配项伪造committed。有效普通项addrValid/dataValid齐备；vecInactive项不得同时addr/dataValid，且不应发Sbuffer或Uncache事务。
3. 普通cacheable store按PA字节来源产生一个或两个16B对齐Sbuffer写请求；逐有效字节检查原始data和mask。不能只比较RTL同款旋转而漏掉未写字节。
4. 同页跨16B项占两个写入口，第二段PA是当前段对齐PA+16；跨页项第二PA来自匹配**完整SQ双flag**的UQ，不能用连续PA代替非连续页。UQ只在对应首段被真实流水接受时消费；完整store的credit不能重复或提前。
5. 普通同拍两个store必须按顺序接受和消费；第二项不能越过被阻塞头。真实EnterSbufferQueue两项容量、无flow-through与独立背压规则继续适用，但父块必须另证明rdata和deq关联。
6. MemoryType普通生产者为000 cacheable、001/101 NC、010 PBMT IO、111 device IO；其余编码仅接口边界，不混称合法随机。NC以正确store方向idResp确认接受，MMIO等待真实resp并writeBack后结束；来自load的idResp不能推进NC。
7. 特殊store与CBO操作期间保持head payload到规定接受/完成，不能由环境过早换头制造假失败。CBO.zero发整line零写，等待真实Sbuffer/内部流水排空再writeBack；其他CBO先flush，再Cache req/resp，再writeBack。
8. writeBack有ready；valid期间ROB、异常和有效payload必须在背压下保持，只有fire才完成。Cache denied/corrupt由真实响应捕获，对应exception7/19不得因等待ready丢失。Uncache缺失错误输入的能力边界单列。
9. 出队credit只在Sbuffer**实际输出fire**后规定的寄存延迟出现，进入内部队列不等于SQ释放；跨16B、CBO.zero、NC确认、MMIO/CBO回写、vecInactive分别记账，不能将地址读取移动与SQ完成混为一谈。

## 2.1 父级随机发现的完成年龄遗漏（新增检查前合同）

真实StoreQueue的`sq-stream-directed-01`由独立flow账本发现年轻NC确认混入旧普通flow释放；`sq-special-order-01`三类NC/IO最小真实VSQ/PSQ probe均确认：Sbuffer ready始终false、旧普通请求消费0次，年轻SQ1确认/WB后公开sqDeqPtr却从0变1。新增`DEQ-CREDIT.special_order`/`PSQ-DEQ.special_order`，完整参考须以已实际完成的SQ身份及连续年龄前缀生成释放，不可照抄`NewStoreQueue.scala:1318-1324`对两个finish位与Sbuffer credit的无身份求和。旧46-bin Deq/45-bin PSQ证据保留；新分母分别47/46，需新原生回归核验收紧参考，不改RTL、不将这项遗漏行为当作行覆盖问题。

首批跨层补例`special-order-hierarchy-01`中PSQ三例真实失败，但Deq三例停在“特殊owner尚未finish”的用例前置条件，不是三个新增RTL反例。原因是旧PsqAgent依据源码1301注释，额外在`read!=head`时强制特殊项committed=false，实际真实PSQ/VSQ并无此门控。现按父级真实可达证据移除该过窄代理限制，旧89例完整域因此只覆盖受限域，不能继续称覆盖实际父级全部许可情形；必须重新运行独立Deq与PSQ回归。保留旧快照和三例刺激失败，不改变异常/字节/完成预期。

回归05的92例为63 PASS/29 FAIL，但其中连续消费和split后inactive共11例首先命中新参考的相位/吞吐错误，不是11个新增RTL缺陷：独立Deq的post-edge外部deq指针/组合finished及inactive控制尚未切换，而寄存Sbuffer credit脉冲已更新；完成集合删除旧owner后再按旧指针找前缀会误报0。post-edge的瞬态wire波形另行检查，但**不作为释放许可**；真正提交的pre-edge以及父级advance始终使用独立完整身份的连续完成前缀，不能用无身份求和替代安全检查。split尾段在lane1时，后继inactive可等下一head拍，不能强求与尾段同拍最优释放；lane0正常完成才支持合并后继inactive。旧1312例114 FAIL和v5未通过门禁保留，须新冻结运行确认。该回归中三个special-order例已真正到达finish并因旧普通owner未消费而严格失败，不再是代理前置条件失败。

## 3. 时间、容量与reset合同

- 对DriveStable和RisingEdge的所有实际引脚进行被动采样；fixture切换空拍也纳入连续历史。
- reset按原SV异步清空状态机、forceWrite和真实下级队列；无reset的Sbuffer credit历史寄存器需要空闲时钟排空。不得把旧credit中止当普通消费，新UID必须实际完成。
- forceWrite在validCnt>=60置1，55..59保持旧值，<55清0，响应一拍寄存；不是任意阈值随机期望。复核父级`NewStoreQueue.scala:1548/1619`后纠正：validCnt来自`virtualValidCount=enqPtr-deqPtr`，普通域为0..128，并非64项物理存储占用；旧0..64合同及运行快照保留但不算完整域覆盖。
- 请求有效时payload按对应Decoupled合同保持，ready=false不得提前推进代理；无valid payload、不活跃异常元信息和源码DontCare不比较，也不计功能通过。
- liveness依赖公平代理：Sbuffer/Uncache/Cache/writeBack最终允许握手且已接受请求返回恰好一次合法响应；随机结束必须公平排空并审计UID/credit。

## 4. 用例前功能点

| 功能组 | 可读微架构行为与情形 | 实际检查义务 |
|---|---|---|
| DEQ-RESET | 空闲/活动/等待响应reset中止后新UID | 状态收敛、旧事务无伪credit、新事务完成 |
| DEQ-CACHE | 单/双cacheable store，rdata与deq不同步 | 原数据、顺序和实际Sbuffer消费credit |
| DEQ-BYTE | 1/2/4/8/16B、16偏移、真实连续mask | PA逐字节来源、有效mask和完整写地址 |
| DEQ-SPLIT | 同页跨16B/跨line与非连续第二页 | 两段地址/字节、UQ身份/消费与单次完成 |
| DEQ-BACKPRESSURE | 0/1/2项消费、内部满、同拍出入 | 真实下级容量，无越序/重复/过早释放 |
| DEQ-CREDIT | 正常/Split/zero/NC/MMIO/inactive信用 | rdata move和sqDeq独立、严格生命周期守恒 |
| DEQ-NC | memory/device NC、req背压、正确方向idResp | 公开ID/ROB/数据/mask、错误方向不得推进 |
| DEQ-MMIO | PBMT IO/device IO、resp与writeBack | 只接受真实响应、头部阻塞和消费完成 |
| DEQ-CBO | zero/clean/flush/inval完整路径 | Sbuffer flush与内部排空、Cache req/resp、WB |
| DEQ-EXCEPTION | Cache denied/corrupt及writeBack背压 | exception7/19、ROB/VA/isHyper及保持到fire |
| DEQ-INACTIVE | 单/双inactive与前后活跃项 | 无数据请求，仅合法前缀移动且不重复 |
| DEQ-DRAIN | CBO flush与forceWrite滞回 | 等待真实empty，60/55阈值和寄存延迟 |
| DEQ-IDENTITY | SQ四圈/ROB former-latter/元数据 | 公开路由和完整依赖身份无串单 |
| DEQ-IDLE | 无效响应、禁用旧payload、无committed项 | 不制造请求/credit，新事务仍可完成 |
| DEQ-CONCURRENT | 固定种子合法cache/特殊store交错 | 公平排空、真实子块数据和信用完整历史 |

## 5. 实施与覆盖闭环

先原样构建真实两文件闭包、核对全部61/55端口；再建立公开PSQ/总线代理与独立字节/生命周期参考，首轮测试cacheable写出、背压与普通特殊store时序。运行后逐条分析本体及真实EnterSbufferQueue的DA缺口，区分既有情形与功能遗漏，再补例重跑。已有叶子覆盖只作依赖证据，不替代本块真实下级闭包覆盖或跨块credit检查。

## 6. 首轮证据、缺口分类与下一步

原样构建与原生走钟PASS见`results/builds/20261018T094224992374Z-deq_module/report.json`；原SV SHA为`bdc38e317b1abbb6425441fd3081622d6203cab56b7ff17203a51c83e9555946`。静态61/55端口编码/独立解码核验256样本与8非法拒绝，仅是序列化证据。

首轮`deq-initial-01`为16例13 PASS/3 FAIL、本体34/46、闭包101/124、17/44 checked。当前probe逐拍保存完整实际引脚，并把显式定向预期单独写journal；不是完整生命周期参考。独立审计211条记录/280有效字节观察、10次Sbuffer消费与8个credit。全部23条缺口分为合同已有功能的缺失用例：本体12条属于整条NC/MMIO路径尚未实现，真实下级11条为奇数尾位置复用；另存`line-audit-classified.json`，不覆盖原needs_review文件或增加行排除。

`deq-expanded-01`补8个NC/IO/半部用例和1个奇数尾复用、3个真正WB fire错误检查，完整28例22 PASS/6 FAIL，本体46/46、真实闭包124/124、25/44 checked。9个正常新用例通过，6个错误用例（3等待期间+3真实WB消费）保留普通失败。DEQ-WB-001由独立`fault-audit.json`核对，192份启动文件结束SHA一致；真实父级组合可达性/架构后果未运行复现。

剩19项语义及完整生命周期参考、PSQ代理、合法混合随机、最终排空和完整公开历史审计仍必须继续；行满和首轮错误复现均不构成模块验收或结束理由。详见[阶段报告](../reports/deq-module-20261018.md)。

## 7. 生命周期补例的用例前约束

- `DeqModel`仅使用公开输入维护两项写出账本和协议阶段，按原始字节地址构造期望；`PsqAgent`独立维护递增UID、读取头和释放头。通过逐拍比较后仍须按实际公开moveCnt/fire核验所有权，不能仅靠模型返回的“完成”计数。
- 补例矩阵：5种长度×16个偏移；两项满池阻塞及单/双消费与同拍接收；普通、跨16B、跨line、非连续第二页；四圈SQ及ROB flag/former/latter；CBO 0/1/2/3全流程和zero的无早期credit；inactive单/双及两种混合次序；队列活动、等待Cache/Uncache响应及等待WB的reset；固定种子合法交错并公平排空。
- CBO.zero的零data来自真实PSQ的StoreData写入路径（`NewStoreQueue.scala:1966`），Deq负责`wline`写出及flush/WB，不虚构由Deq生成零值。NC的`handleFinish`由真实PSQ在store方向idResp置位（1658–1659），SQ释放使用随后一拍deq控制；不等待已被优化移除的NC数据响应。
- UQ同slot不同双flag作为显式接口身份反例；普通跨页流量必须提供正确匹配第二页，不用缺失UQ制造数据错误后声称生产者可达。
- reset中止单列，旧UID不得混入完成；同槽新UID须通过真实总线或Sbuffer消费及公开SQ credit完成。每例结束保存分配、读取、消费、回写、完成和reset中止事件，随机不得只以运行拍数结束。
- 错误响应继续严格保持到WB.fire。完整参考若再次暴露`DEQ-WB-001`，作为普通失败保存，不使用问题清单改变oracle。

## 8. 随机首轮驱动的新功能点与校正

`deq-lifecycle-expanded-01`为70例57 PASS/13 FAIL：9个WB错误，1个随机split尾段`wline`污染，3个新参考错误。`pipelineConnectFireNum`的split编码只代表一个SQ读取位置，不能因两个片段被接受就同时移动下一inactive；修正参考，首轮原实现/结果不重写。

新增第45项`DEQ-SPLIT.zero_neighbor`：普通split的两个片段的整line写控制都属于原头store，不能由相邻即使未committed的CBO.zero决定。对照相邻inval/clean/flush，定向检查zero的已/未committed、延迟与立即Sbuffer消费；源1272不复用head的isCbo/cboType，需真实父级可达性进一步确认。该安全功能点在原“逐有效字节来源”检查外被随机发现，因此归类为**遗漏整体控制所有权功能点**，不是DA缺行，也不能将尾段`wline`掩掉。

剩余随机仍使用同样的合法混合域，遇到该缺陷保留普通失败；另补不含zero邻接的必要条件对照只用于完成其他生命周期证据，不替换原混合随机或宣称整个随机已通过。

第46项`DEQ-CONCURRENT.controlled`单列不含zero的随机必要条件对照；它的checked不填补完整域`DEQ-CONCURRENT.seeded`。历史44项分母保持在旧快照，新增两项的46项目录仅用于新运行。

## 9. 生命周期冻结重跑与证据边界

`deq-lifecycle-expanded-03`完整89例71 PASS/18 FAIL：`DEQ-WB-001`9例，`DEQ-SPLIT-WLINE-001`9例（3个完整域随机、2个最小入队后检查、4个实际Sbuffer fire）。44/46 checked，未通过held与zero_neighbor，不以行满宣布通过。首轮19个语义缺口中18个已新增完成检查，其余错误保持到fire仍为FAIL。

`tools/audit_deq_lifecycle.py`不导入领域参考或DUT内部信号，重建9746条连续记录、3035 UID=2835完成+4 reset中止+196失败保留；2547次真实Sbuffer fire、452次WB、220次NC确认、全部256 SQ编码与4条reset同槽新UID完成见证。全部201份启动文件的结束SHA一致、artifact/build哈希通过。完整域随机4种子中1个400 UID公平排空、3个在wline错误处停止；另4个不含zero的对照各400 UID完整排空，不能替代失败的完整域。

现有证据足以确认独立Deq公开接口的两类违反合同，但未证明真实PSQ/更高层producer可达性或架构后果；接续真实PSQ，不因局部失败使整体目标unmet。`audit_deq_codec_v2.py`单列修正0..128占用域，v1的65拒绝及旧快照保留为历史合同错误，不能继续当完整域依据。
