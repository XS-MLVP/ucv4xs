# 功能点以硬件事件语义为单位，不以 case 步骤为单位

## 提取规则

先从设计意图确定状态主体、数据流及应当保证的性质，再核对当前 RTL 的接纳、
资格、更新、冲刷和优先级条件。不是把每一个 RTL 分支机械翻译为功能点；
实现代码可能有缺陷，参考预期也不能只是照抄实际输出。

每个需求写清五件事：事件来源/对象、发生资格、前置状态、效果或禁止效果、
因果关联/完成边界。流水线冲突与年龄关系也是事件语义；不要求有专门的脉冲信号。

- 功能需求：在条件成立时应保证什么，身份不随测试拆分或 driver 写法变化。
- 事件实例：本次真实输入何时接纳，经过哪个阶段，影响哪个对象。
- 场景：使事件及其前置状态可达的刺激序列；次数、PC 和准备过程属于这里。
- 检查：把预期义务与实际结果关联后比较，失败由 Scoreboard 抛出、pytest 判定。
- 覆盖：事件及有意义条件/关系是否到达；效果已检查的覆盖另列。

一个 case 可以检查多个需求，一个需求也可以由多个 case 共同检查。
功能点通过率、事件覆盖率、物理覆盖率、原生行覆盖率不互相替代。
覆盖采样不得因整个 case 最终失败就抹掉已到达事件，也不能把一个 PASS 变成
枚举所有覆盖标签的权限。默认只保留累计计数及有界事件见证，不导出逐周期 JSON。

## SC：本轮实现的事件范围

主体是四个全局阈值，不是 SRAM bank/set。原 `near-bound`、`fresh-public-readback`、
`neighbor-isolation-and-drain` 混合了状态、检查动作和收尾；旧64格是历史检查清单，
不是64个同层级硬件功能需求。它仍有相应断言证据，但不能与新语义分母直接比较。

| 稳定需求 | 发生资格与上下文 | 应保证的效果 |
| --- | --- | --- |
| SC.THRESHOLD.RANGE_ACCEPT | 真实接纳反馈的合格票在T1聚合，候选在640..5040 | 提交候选，包含恰好到达上下界 |
| SC.THRESHOLD.WHOLE_DELTA_REJECT | 同一事件的候选低于640或高于5040 | 保留整个旧值，不钳位；区分原值在边界和在内部 |
| SC.THRESHOLD.INWARD_UPDATE | 边界值收到向内的有效净增量 | 有效离开边界，不因之前拒绝而冻结 |
| SC.THRESHOLD.WAY_ISOLATION | 一组票只影响参与way | 完整其他way值保持，每次提交都比较 |
| SC.THRESHOLD.OPPOSED_VOTES_CANCEL | 两条不同分支、同way、合格增减各一票 | 先求净值再判范围；内部和上下界均保持 |

前四项由保留身份的 `BPU-INT-070` 表达，新增独立义务由 `BPU-INT-071` 表达；
八个边界 case 同时检查这两个功能组，而不是一条新 case 就登记一条新功能。
071此前有纯模型 truth table，不足以证明真实 DUT 的合格混合票事件已经到达。

`Sc.scala:493–515` 是资格票、按way聚合和范围选择，`:604–605` 是阈值提交门控。
FullScChecker 保留全部已有阈值/SRAM/shadow/PLRU比较，并在可选覆盖开启时关联：
实际公开反馈接纳 → 其T1资格与投票 → 下一观察点的完整四阈值提交向量。
不在测试中增加边沿等待，不更改 picker/xreactor 或硬件。

新 schema 的 `way × rule` 共52格：内部增/减、进入上下界、离开上下界、内部越界拒绝、
边界向外拒绝，以及内部/上下界的增减抵消。分别导出 reached 和 checked 两个组，
使用同一分母。其含义是此事件范围内的规则覆盖，不是“SC全部语义100%”。
不参与的way不伪造抵消事件，隔离通过完整向量比较证明。
缺少资格导致的不更新、read-without-update及其他训练/预测事件仍属于别的覆盖范围。

每次更新在观察到实际来源后采样 reached；提交tick与整个阈值向量均通过现有
Scoreboard后才采样 checked。比较失败留下 reached 与 failure 状态；reset取消
留下 reached 与 cancelled 状态。导出放在 monitor停止后的 finally，避免后续用例
失败使先前事件消失。仅保留16条最近事件见证及每bin首末元数据。

混合票使用真实保存的预测metadata与 first-NT/last-T 的合法反馈方向向量。
下界先减后增、上界先增后减时，逐分支范围过滤会错误地产生非零变化；净值聚合
应保持边界。每个原场景只新增两笔独立来源反馈：内部抵消、边界抵消。
准备状态的长序列仍存在，不把故障超时预算改称必要等待；不扩展物理地址矩阵。

## 其他模块的语义迁移清单

| 模块/原条目 | 应当提取的事件语义 | 保留但不再作为同层功能点的内容 |
| --- | --- | --- |
| MicroRAS中性S2更正 | 更正取消更年轻S1操作、保留更老S3操作；输出按优先级选择正确返回来源 | 三次CALL、六次退休、全PHR检查、排空是构造和检查 |
| ITTAGE目录生命周期 | 目标区域分类触发旁路/已有区域复用/空闲分配/满表替换；保留指针按新区域解码且不破坏幸存项 | 第一次/第二次替换是实例；填满16项是前置状态建立 |
| TAGE候选训练算术 | 区分候选计算、有效provider/alternate更新资格、实际写入及后续消费 | 候选算术命中不能直接登记为有效训练功能完成 |
| shadow缓冲 | 接纳写与排空的同周期关系、旧值消费、覆盖优先级、dirty责任是否保留 | slot/bank身份是作用对象；读回、drain是证据或完成边界 |

MicroRAS现已完成独立事件资格、年轻RETURN补测及完整生产发布，见
[事件定义、实现与证据](micro-ras-event-semantics-20261013.md)。
集成TAGE selector也已完成独立资格与完整生产发布，精确新增11原生键、十DUT零回退，见
[合格更新、预测消费和证据范围](integrated-tage-selector-events-20261014.md)。
ITTAGE及其他表中范围仍有检查清单式schema，不能因本文列出更好的定义就称已完成迁移。
后续按事件需求逐项映射现有 checker/monitor和原生缺口，再决定是否需要新刺激；
不通过增加标签或地址枚举制造增长。

### ITTAGE下一轮的具体事件边界（尚未实现）

现有目录参考已经从reset独立重放16项状态及PLRU，并比较接受反馈、write、
下一观察点的全状态和公开target；问题在于case结束后枚举十个清单标签。
不需要重写验证框架。下一轮复用这个checker/monitor，把采样移到因果链上：

| 稳定义务 | 真正发生条件 | checked边界 |
| --- | --- | --- |
| REGION.PC_BYPASS | 实际接受的分配反馈，目标与source PC同区域 | 对应ITTAGE工作退休后没有目录write，target使用PC区域完整解码 |
| REGION.EXISTING_REUSE | 合格foreign-region write，区域已存在；目录部分占用或全满 | 复用原pointer、占用数不增、全部payload不变，并正确触碰PLRU |
| REGION.FREE_ALLOCATE | 合格write、无已有区域、至少一个空项 | 最低空pointer变有效、无其他项改变，公开target及后续读回正确 |
| REGION.FULL_REPLACE | 合格write、无已有区域且全满 | 独立PLRU选择victim、仅victim区域替换、幸存项保持 |
| REGION.POINTER_REDECODE | 真正保留旧pointer的后续预测，pointer区域已被替换 | 保留offset与当前区域组成完整公开metadata/最终S3 target，而非旧target |

第一次/第二次替换只是`FULL_REPLACE`的两个实例；填16项是满表前提，不是
16个同层功能点；reset、全survivor扫描、排空分别是初始化、检查和完成边界。
`RegionWays.scala:55–58`要求已有区域优先于空项。目前集成程序只在满表后复用，
缺少“已有区域与空项同时存在”的竞争前提。拟在部分填充后增加一个真正新source
的旧region目标，不扩展bank/set矩阵；还要通过后续独立victim验证复用触碰PLRU。

reached在接受来源及其独立前提已建立时记录，checked必须等关联write/不写义务
及完整状态/公开consumer比较通过。漏write、额外write、错pointer或错误解码均
留下已到达事件并使pytest普通FAIL；finally导出累计覆盖，不能等case全PASS再采样。
目标重写诊断的普通失败与该目录范围正交，不因目录满行或本迁移而豁免。

## 原生行归因边界

已发布 `production-sc-threshold-bounds-20261013-v1`：15160 PASS、7既有strict XFAIL、
0 SKIP；304功能点297 PASS；BPU33146/46541，相对前版增加17键、十DUT零旧键回退。
其中SC3键直接对应whole-delta range rejection；另14个TAGE键是候选算术暂存路径，
并未逐键证明有效写入资格，不登记为14项新TAGE功能。
新事件版运行与新增混合票结果应独立报告，不回写这份冻结历史证据。

## 事件版的独立资格结果

[`八场景冻结资格`](../results/integrated-sc-threshold-events-qualified-20261013-v1/exit.json)
退出0，8 PASS，pytest191.49秒、完整选测处理214.24秒；不发布为全量结果。
1764文件源码、8工作进程收据/8功能输入、JUnit和完整选测集合重新复核一致。
[`功能事件矩阵`](../results/integrated-sc-threshold-events-qualified-20261013-v1/functional-coverage.json)
的 reached/checked 均52/52、8896个事件；没有未确认、失败或取消的阈值义务。
每下界场景257笔独立延迟来源加1笔真实准备反馈，258个阈值事件；每上界1966个。
内部抵消各8次，下界抵消4次、上界抵消4次，都有真实提交检查。

相同RTL/信号表/memory-direct布局下，与已发布33146/46541基线比较，选测没有
新增原生行键。新结果补的是此前没有真实DUT证据的合格混合票功能，不把事件
分母64→52、一个覆盖组拆成两个组、或内部重复8896次解释为行覆盖提升。
同样不能将选测未命中的其他原生行称为回退；是否保留旧命中由后续完整回归判断。
145项新增/调整事件与边界纯契约通过；全BPU scoreboard兼容回归9631 PASS，
167.02秒。随后增加生产 reached/checked 完整矩阵门禁，相关事件/边界/发布契约
177 PASS；少一个事件格或缺整个组都会拒绝完整发布。
加入门禁后的完整生产回归
[`production-sc-threshold-events-20261013-v1`](../results/production-sc-threshold-events-20261013-v1/exit.json)
已退出0并发布：15228 PASS、7既有strict XFAIL、0 SKIP，305功能点298 PASS，
216个覆盖组204满目标。pytest453.97秒、完整664.33秒；52/52 reached与checked均
通过完整门禁，十DUT原生零旧键回退、新增0。BPU仍33146/46541。
独立八场景资格与后续门禁修改不冒称同一冻结epoch；完整回归检查的是最终1764文件epoch。

## TAGE useful老化：073的真实事件资格与完整发布

073提取的是一次全局生命周期，不是“填满、循环255次、读回”三个case步骤：

| 稳定义务 | 发生资格 | 效果及完成边界 |
| --- | --- | --- |
| TAGE.AGING.QUALIFIED_FAILURE_ACCUMULATION | 真正接纳的enabled conditional，存在MainBTB owner；最终方向确实错误、仍需更长历史且无可用way、无维护在途 | 每笔合格事件仅增一次8位全局计数，饱和保持；完整source/T2/T3/下一寄存器提交关联 |
| TAGE.AGING.SATURATED_T3_START | 已到255后的真实T3，无维护在途；分别需要分配或正确更新旧provider | 启动一次维护并清零计数；idle/saturation本身不启动，不要求本笔再次分配失败 |
| TAGE.AGING.CLEAR_WRITE_PRIORITY_AND_COMPLETION | 清理启动及在途的每张表/每个bank，真正SRAM写握手 | 零useful写覆盖普通useful更新，全部queue接到flush；按已接受写推进地址，全范围完成后退出全局busy |
| TAGE.AGING.ALLOCATION_AND_CONSUMER_RECOVERY | 清理完成后的新合格反馈，以及后续真正预测新tag/保留tag | 写入独立预期弱entry；完整metadata、有效TAGE数据和精确关联最终S3正确；旧项counter/tag保持而useful为零 |

使用一个固定TAGE候选bank/set中的八个不同tag建立容量压力；少量真实source PC共享
该候选集合。不同MainBTB owner由正常反馈安装，CSR临时禁用TAGE以保护已建状态。
这不是物理bank/set扫描。MainBTB base会被真实训练，所以每笔压力反馈取新鲜来源的
相反最终方向，不能固定mispredict=1或重复相同结果来假定255次合格失败。
255是计数器状态前提，不是settling周期。最高表错误预测被needAllocate排除，不能拿来累计。

实现分在`model/tage/aging.py`、`monitor/tage/aging.py`、`checker/tage/aging.py`、
`coverage/tage/aging.py`、`case/tage/aging.py`及薄pytest入口。复用现有Bundle、
CycleMonitor/@on、driver、Scoreboard和状态等待，不增加框架层scheduler或interface。
候选八cell从reset及独立预期写入重建；随机过滤mask、SRAM ready及MainBTB base
是声明的模块输入，不拿实际useful/counter寄存器给模型起算。不声称完整MainBTB、
所有TAGE SRAM/哈希或FTQ合法性模型。clear逐bank的128地址推进属于硬件全局动作，
刺激不对bank逐个发255笔反馈。

维护状态已加入现有BPU `writes`契约：`committed=True`还需要全局及所有表的
usefulResetInFlight退出，不把buffer空闲误当维护完成。硬件可以在清理期间用零
useful响应继续分配；探针验证过，但当前正式两场景选择在维护完成后验证恢复。
清理前已经按提交边界串行处理准备反馈，不冒称测试了任意在途queue payload冲刷。

reached由已接纳source及独立前提生成，checked由各义务的真实完成边界生成。
恢复分配的checked必须等新provider完整consumer比较，不能仅看到writeReq就算完成。
训练、维护和消费为三个不同事件族、各自reached/checked六组；rule不是phase标签。
失败保留已到达事件并普通FAIL，导出在monitor停止后的finally；只保留累计计数和
64帧/32事件有界诊断，不输出逐周期JSON或波形。

过程中发现并修正三个oracle边界，未削弱有效比较、未新增XFAIL：

- BpuTransaction.prediction是早级S1结果；mispredict必须关联metadata对应的最终S3。
- `useMeta=1`不发生本笔SRAM读取；无allocation需求时allocator的无选中分支输出
  可来自旧read operand，不能把这些无效组合值当本笔分配结果。实际有效T2输入、
  need/allocate门控及全部有效write仍逐项比较。
- TAGE valid=0时ParallelPriorityMux的未选中payload不一定是0；只在有效时比较
  direction，metadata与最终MainBTB fallback继续完整比较。无taken的position是
  fetch终点，用既有独立fallthrough几何检查，不假定为0。

[`最终双上下文资格`](../results/integrated-tage-aging-qualified-20261014-v2/exit.json)
2 PASS，pytest46.56秒、完整66.89秒；1779项源码、2收据/2功能输入、JUnit复核一致。
每场景273个T3事件、255次计数增量、9次有效分配、一次维护完成、4128个清理写握手；
旧tag在新分配后各有7个保持。训练rule514、维护义务3、消费17，reached/checked逐组
对应且六组均100%；不同族的同源义务不冒称独立硬件输入事件。
233项候选/selector/故障/consumer纯契约通过；较早模型/发布门禁288项通过，后者
之后的少量checker及纯fixture修改不冒称同一epoch，最终完整回归将检查当前版本。

通过的单`correct-update`候选相对已发布33157/46541基线，严格增量92键；最终双
上下文联合集合仍恰为这92键：Tage顶层42、四TageTable各12共48、useful queue2。
顶层中3键直接为失败累计/清零，24键为自然准备带出的selector上下文，3键是分配
候选算术，12键为预测/metadata路由。48键有完整清理握手/地址参考；queue两键不
单独证明完整queue状态模型。不是92项新功能，不以候选算术行命中豁免分配优先级需求。
随后完整生产
[`production-tage-useful-aging-events-20261014-v1`](../results/production-tage-useful-aging-events-20261014-v1/exit.json)
已退出0并正式发布：15522 PASS、7既有strict XFAIL、0 SKIP，307点300 PASS，
226组214满目标。pytest456.99秒、完整676.14秒。1779项源码、64收据/985功能输入、
完整JUnit、全部根报告/profile/LCOV独立核验一致；六组事件全部通过完整发布门禁。
十DUT零旧键回退，BPU精确新增92，集合与最终双资格完全相同，正式33249/46541。
其中88键在固定旧全物理基线也未命中，4键恢复旧路径。旧资格/失败报告保留，
不把历史并集回填为当时正式值。候选集与维护参考不是完整TAGE/FTQ验证，
formal_current和independent_full_dynamic_audit_complete仍为false。

ITTAGE目录事件化和其他动态需求仍未完成，完整目标没有完成。

## 072路由补强：逻辑状态对象不等于物理遍历

073之后的selector0缺口来自有效输入缺失：原准备只建立强base置信度。四provider
表×两alternate/base置信度选择八个独立的共享selector，这是硬件路由规则的
逻辑状态域，不把它扩成bank/set/way矩阵。复用同一容量准备中每表已有的两个tag，
一个保留正常分配后base2，一个正常重建base3；只用真实反馈及已检查的新鲜metadata。
原072增加明确的`TAGE.SELECTOR.PROVIDER_CONFIDENCE_ROUTING`义务，保持307个功能点。

reached按独立资格票和真实接纳/来源生成；checked要等实际T3索引/投票及完整八
寄存器提交比较，邻selector损坏同样普通FAIL。两者各八个逻辑格，不是八套饱和
或八次完整老化。prediction/meta/accepted/commit身份可追溯，只记录计数和首末见证。
两个原073场景仍各只有一个老化生命周期，原072饱和/消费case继续独立执行。

最终三用例资格3 PASS，纯路由/selector/aging248 PASS，发布门禁78 PASS；两种老化
合并的routing reached/checked各16笔，每index2笔。严格隔离与联合资格一致新增8个
原生键，七个直接selector0提交、一个伴随预测来源。随后完整生产已正式发布，
15543 PASS、7既有strict XFAIL、0 SKIP，307点300 PASS，228组216满目标；
源码/64收据/987功能输入/根报告/LCOV核验一致。十DUT零旧键回退，精确重现8键，
正式BPU33257/46541，集成Tage3011/3021、剩10键。八键在旧全物理范围也未见；
不是两个额外通过功能点或bank遍历。详见
[输入、关联、负向契约和资格证据](integrated-tage-selector-events-20261014.md#八个逻辑selector的输入路由加强原072不增加物理枚举)。

## ITTAGE目录迁移：不在case结束后批量填标签

迁移前067的reset、free/reuse/PLRU、完整目录端口和每个resident的同源最终target
比较是实际检查；但十个coverage标签在整个case通过后统一采样，其中reset、
first/second replacement、drain混杂了前提、顺序和事件。这是本轮修正的测量层，
不能把旧10/10称十种同层硬件事件，也不能在迁移后用分母变化冒称功能/行覆盖增长。

按`RegionWays.scala`真实优先级，稳定分配义务是：目标在PC region时绕过目录；
外region先复用已有项，再选空项，最后在满表无命中时选择PLRU victim。占用未满
与已满是“复用优先级”必须区分的资格上下文。迁移前输入仅有满表复用，缺少尚有
空项时仍复用旧项的真实反馈，应在原容量生命周期中加一次早期复用，不遍历bank。
same-cycle update查询的write bypass是独立组合端口义务，不应被“写后读回”替代。

分配提交与预测消费仍是两族事件：

- 分配reached关联真正接纳的taken indirect、原预测metadata及独立目录前态；
  checked要等对应writeRegion/writePointer、下一完整16项状态和端口比较。
  PC-region绕过要明确无关联目录写的完成边界，不因idle一拍就给信用。
- 消费reached来自真实预测的provider region指针/offset及已知目录生命周期；
  checked需要完整metadata和精确关联最终S3 target/taken/position。指针被替换
  后旧entry按新region重解码，与未替换resident保持，必须分别比较。

reset、完整状态、来源关联和最终drain是每个事件的合同，不单列为平级覆盖bin；
“第一次/第二次替换”不是两种功能规则。只导出实际发生事件的计数和首末来源，
负向故障应保留reached并普通FAIL、不给checked。框架继续复用现有monitor/Scoreboard，
不增加scheduler或case内的手写底层周期。067现有比较保留，跨region零置信度
重写普通失败不被目录事件化豁免。

上述迁移现已实现：同一生命周期增加八项占用时的真实reuse，保留一项DUT case，
共21context/20目录写。allocation五种规则和consumption三种规则各reached/checked，
四组均完整。所有reset/目录端口/PHR/全部resident/同源最终S3及drain检查继续保留；
case不再在结尾批填coverage标签，consumer参考与事件比较封回checker。
真实候选1 PASS，1781源码及回执/JUnit复核；21分配与231消费各逐事件对应，
未满reuse前态8项、实际pointer3、无eviction。94项目录/事件纯契约、90项发布门禁
通过，wrong-source、错pointer、漏effect、邻项和完整输出故障均普通FAIL且不给checked。
严格隔离及完整生产原生新增均0，不用新分母冒称行覆盖或功能点通过率上升。
`production-ittage-directory-events-20261015-v1` 已退出0并正式发布：15595 PASS、
7既有strict XFAIL、0 SKIP，307点300 PASS，231组219满目标。pytest455.64秒、
完整667.54秒；1781源码/64收据/987功能输入/全部报告及真实事件计数独立核验。
十DUT原生命中集合逐键保持，旧目录十标签实例不混入新测量，BPU仍33257/46541。
详见 [事件边界、资格和原生零增量](ittage-region-lifecycle-20261013.md#2026-10-15事件化分配提交和预测消费分别测量)。
