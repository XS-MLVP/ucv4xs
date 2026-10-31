# BPU RTL 行覆盖率与功能缺口分析

## 最新发布边界：2026-10-15

当前正式结果以 [REPORT.md](../REPORT.md) 和
`production-ittage-directory-events-20261015-v1` 为准：代表坐标生产回归
15,595 PASS、7 strict XFAIL、0 SKIP，307个功能点全部执行；BPU为33257/46541。
不要把下文历史物理遍历的40039/40297与代表范围直接当作同范围覆盖率增减。
两种范围保留相同原生分母和独立基线，完整物理遍历按需执行。

本轮目录事件化补了未满时优先reuse的真实输入，21分配及231消费的reached/checked
逐一对应、四组均完整；原有状态/端口/全部resident/PHR和精确最终S3检查保留。
完整生产十DUT原生分母和命中集合逐键完全保持，新增0，不用新事件分母宣称
行覆盖上涨。RegionWays162/162不能证明此前缺失的优先级输入，反映行/功能测量
不是同一件事。1781源码/64收据/987功能输入、JUnit及全部发布链接独立核验。见
[事件边界和正式零增量](ittage-region-lifecycle-20261013.md#2026-10-15事件化分配提交和预测消费分别测量)。
集成ITTAGE tick/useful维护两键和对应完成契约仍待补，memory-direct观测已具备；
不要用独立模块满行或目录满行豁免这个动态需求。

此前把selector0缺口归因到有效provider/base置信度输入路由，补强原072而非再
造一项功能。复用容量准备的八个逻辑对象，actual source/T3投票及完整八寄存器
提交关联后两组routing均8/8；不做bank/set遍历、不增老化case。完整生产精确新增
8键，集合与最终三用例资格相同，十DUT零旧键回退；七键直接selector0提交，
一键为伴随预测路径，均旧全物理范围未见。1780源码、64收据、987功能输入、
JUnit与根报告/profile/LCOV重新核验。集成Tage缺口18→10；剩余有效预测来源和
useful写入资格仍待补，不用候选算术命中代替提交。见
[路由输入与资格证据](integrated-tage-selector-events-20261014.md#八个逻辑selector的输入路由加强原072不增加物理枚举)。

073将TAGE全局老化缺口归因到真正合格的失败事件与饱和后的T3启动，不以等待
周期或mispredict字段代替资格。两触发场景、完整维护写握手与公开consumer通过；
完整生产精确新增92键，集合与双场景资格相同，十DUT零回退。Tage42、四表清理
48、queue flush2；88键在旧全物理范围也未命中，4键恢复旧路径。1779源码哈希、
64收据、985功能输入、JUnit及根报告/profile/LCOV再次独立核验。
集成Tage缺口60→18，但候选/flush命中不代表全部分配或queue功能完成。见
[事件、资格边界及发布](hardware-event-functional-points-20261013.md#tage-useful老化073的真实事件资格与完整发布)。

最新070补SC自定义阈值范围拒绝，完整生产相对前版精确新增17键、十DUT零回退。
SC3键对应已检查的整个增量拒绝；TAGE14键是候选算术暂存，未逐键证明有效写表。
旧64格是阶段/检查清单，不代表同层级硬件事件需求；SC事件版及合格混合票抵消
现已完整发布，52格reached/checked均完整，十DUT原生零旧键回退、新增0。
MicroRAS事件迁移及年轻RETURN取消也已完整发布，4/4 reached与checked均完整，
同样原生新增0。集成TAGE selector现也完整生产发布，精确新增11键，其中8键直接
对应已检查更新提交，2键为分配候选、1键为预测数据选择；十DUT零旧键回退。
64收据/983功能输入/1772源码epoch、JUnit及根报告/profile/LCOV均独立复核。
见 [TAGE事件证据](integrated-tage-selector-events-20261014.md)。
见 [事件提取规则](hardware-event-functional-points-20261013.md) 与
[070冻结证据](integrated-sc-threshold-bounds-20261013.md)。

此前BPU-INT-069补实际中性S2 correction与较老S3 push、较年轻错误路径CALL重叠。
不靠错target假定S2 override；通过最后准备冷MicroBTB/热MainBTB中性跳转形成
真实taken差异，检查老地址前递、年轻pending取消、公开S2修正和每笔最终S3目标，
并要求错误路径无最终metadata/main RAS操作。完整MicroRAS/PHR/提交单元和排空
比较后10/10语义格闭合，完整生产精确重现独立10键，十DUT零旧键丢失。
MicroRAS180/181两键关闭，其余8键来自自然哨兵缓存路径；旧全物理范围也均未见。
集成MicroRAS87→89/91，只剩133/134的当前连接局部约束，分母不减；独立DUT91/91不变。
64收据/973功能输入/1758文件epoch及根JSON/HTML/LCOV/profile索引重新核验一致。
见 [输入、关联、负向门禁和发布](neutral-micro-ras-correction-20261013.md)。

此前BPU-INT-068将集成MicroRAS缺口归因为连续早级call/return的pending操作组合：
三次真实不同call直接跟return或隔一条普通跳转，要求UBTB连续S1接受及精确S3关联。
完整reset-derived MicroRAS/PHR、全部提交单元、已知程序公开目标及排空检查后，
16/16语义格闭合。两个隔离场景37/42原生键去重为46，完整生产精确重现并集，
十DUT零回退。MicroRas4、MicroBtb36、其替换器5、RasStack1，旧全物理范围也均未见；
不是bank/set枚举，不把伴随路径全部称为MicroRAS新功能。
该阶段集成MicroRAS83→87/91；133/134由当前BPU推进/override连接局部排除，180/181
的中性S2修正与较老push现由069补动态证据，分母不减；独立MicroRAS DUT仍91/91。
64收据/972功能输入/1753文件epoch及根JSON/HTML/LCOV/profile索引重新核验一致。
见 [新需求、模型范围、负向检查及发布](early-micro-ras-pipeline-20261013.md)。

此前BPU-INT-067将集成RegionWays的46个缺失键归因为目录生命周期需求：
PC-region控制、16项填满、满表复用、两次PLRU替换，每次检查所有resident及
完整公开metadata/精确S3关联，目录/PHR从reset独立重放并检查真实反馈及排空。
10/10语义格通过，完整生产精确新增46键，RegionWays116→162/162，十DUT零回退。
46键在旧全物理范围也未见；20个context来自容量前提，不扩大bank/set枚举。
64收据/970功能输入/1745文件epoch及JSON/HTML/LCOV/profile索引重新核验一致。
同一epoch的独立零置信度重写诊断仍普通FAIL：foreign region已存在且目录/PHR正确，
无新table allocation时usePcRegion却为1，公开providerTarget/altDiffers失配。
不计原生覆盖、不新增XFAIL，不冒称即时架构跳转已经错误或目录满行就代表功能完成。
见 [目录生命周期与开放重写需求](ittage-region-lifecycle-20261013.md)。

此前BPU-INT-066用真实分离的index/tag祖先及一个base-alias返回节点，完成
高index462 lower provider 的useful增减、分配和一致保持，10/10语义格闭合。
完整生产精确新增70键、十DUT零旧键丢失；66键恢复旧物理范围，4键是旧范围也
未命中的lower useful非分配更新体。不是70个新功能点，也不扩展bank枚举。
64收据/969功能输入/1736文件epoch及JSON/HTML/LCOV/profile索引全部重新核验。
见 [集成high-index useful](integrated-high-index-useful-20261013.md)。upper1读响应
已真实达到，但后续dirty冲突普通FAIL，完整shadow选择cross仍29/30，见
[slot1因果范围](shadow-slot1-dirty-collision-20261013.md)。

此前BPU-RAS-016将4个BOS距离回收缺口归因为显式退休通知丢失故障需求，
使用真实pre-operation metadata而非action0 neutral commit，检查距离2/3与
push优先级、同代/跨代指针、全部提交单元及持续操作。36语义格通过，完整
生产精确重现独立4键增量，RAS565→569/585，十DUT零回退。剩余16键保留分母，
其局部守卫/顶层译码排除不外推为全RTL形式证明，也不豁免enable-metadata缺陷。
见 [功能场景、合法性范围与发布](ras-retirement-gap-20261013.md)。

此前BPU-INT-065通过同一四节点程序的退休感知回绕边界，补upper3/4/5的有效
payload响应；27/27语义格通过，shadow cross26/30→29/30。原生精确新增10键，
与三个独立场景0/10/3键的去重并集相同，十DUT零回退。这10键都是恢复旧物理
范围路径，不能称为旧全量未见的新行；slot3则补功能格而不增加行。
见 [边界准备失败、修正及完整发布](shadow-wrap-boundary-retirement-20261013.md)。

新增部分回绕场景的隔离验证关闭15个生产缺失原生键，但新全量v1虽有
14,540 PASS/7 strict XFAIL，仍因9个 MicroBTB 旧键回退而拒绝发布。
失败运行没有覆盖正式报告；补充真实相邻反馈、恢复流动仲裁和最终 MicroBTB
读回后，v2完整重跑通过全部门禁并发布。相对上个生产基线新增25键、零回退，
shadow response-selection cross 从20/30提升至22/30；其余9 DUT原生指标不变。
见 [场景与门禁终态](shadow-response-gap-design.md)。

此前稀疏四节点 negative payload 场景通过独立资格和完整生产回归：
相对v2精确新增192键、十DUT无回退，shadow cross22/30→26/30。
其中27个lower shadow键在旧物理遍历中也未命中，其他165个恢复生产路径。
新增需求检查不同 index/tag 输入祖先、真实D→A恢复、old负向counter返回以及
同block较后fallback CFI，未扩大 bank 枚举。64worker pytest为444.77秒，
完整刷新655秒；收据完整、原生集合与独立增量完全相同后才发布。

本轮重新按当前缺失键核对 TAGE 的112个局部矛盾赋值，并明确保留8个未正式
分类块头；MicroTAGE 原先1152个缺口对应384个高地址 useful 单元。现有 same-PC
上下文确受 tag-width 缺陷阻塞，但不能外推为整个流水线不可达。新功能点023已用
独立index/tag PC及history在真实DUT完成高地址provider更新，两节奏20语义bin全满，
原8192物理格仅新增8格；完整生产9901→9904/11053，精确新增3键、十DUT零回退。
剩余1149键对应383个未执行高地址，不能再全归为位宽阻塞，也不复制383次刷行。
模块接口证据不等于完整FTQ合法性；原7个strict XFAIL保持不变。
见 [输入层缺口与真实反馈验证](utage-split-context-useful-20261013.md)。各模块的分类边界、源码与复核证据见
[当前行缺口归因](coverage-gap-triage-20261013.md)。以下各日期均为历史记录。

## 当前状态：2026-10-11 11:29 北京时间

旧全量实际终态11786 PASS/7 strict XFAIL/1 FAIL/0 SKIP，失败来自过时的
双调用AST契约，未发布。已合入该契约修正、真实双对齐训练地址/独立字节
参考和SC接受边沿响应相位修复；生产9582项组合检查完整退出0。
新200训练几何、48 SC-used与299既有SC场景共547项正在32进程重验，
通过完整新矩阵/收据/源码检查后自动衔接15163项全量。详见
[本次迁移](../results/coverage-repair-20261011-promotion-v1/promotion.json)。

正式行覆盖仍为BPU40039/46541；已资格候选集合并集40297不是发布结果。
正式FC组均值98.52%也不能代表闭环：物理counter路径8200/12288、reset
优先级834/12288。多CFI的v6虽在12组合中实现四个稳定驻留CFI，仍没有
要求的同cell负向reset冲突；v7三节点沿用二节点索引相位而失败，均不计信用。
v8目录仅准备，尚未通过联合相位模型和原生验证。

其余模块、真实FTQ的五个redirect失败、完整动态审查均未宣称完成。
下方23:59及更早“尚未合入/运行中”等描述按当时历史版本理解。

## 当前状态：2026-10-10 23:59 北京时间

真实双对齐训练实验发现验证适配错误：生产
`suites/frontend/bpu/bpu/driver/encoding.py:38`把两份逻辑startPc都写成pc，
`suites/frontend/bpu/bpu/model/sc/model.py:35`又镜像同一错误，因此旧payload比较
不能发现问题。实际FTQ见`Ftq.scala:424–432`：第二份PC应推进一个
16-byte对齐块，halfword表示为`(pc + 8) & ~7`；MainBtb.scala:111
起会把该向量旋转到物理align bank。原Driver在真实DUT上对
`align1.offset0.position8`普通FAIL，实际metadata无对应rawHit，未加XFAIL。

隔离修复候选现已实际完成6168项契约PASS和200项原生PASS。定义域为两个
first-align × offset0..7 × position从offset到15，共200种合法几何组合，
每种检查分配、增减与两端饱和十阶段；2000/2000功能bin、2000笔完整真实
反馈、MainBTB counter及父级S3结果经独立检查。保留原PHR、1024计数器、
256 PLRU及写缓冲/SRAM检查，不捏造metadata、不写内部状态。39项审查器
正负对照PASS。零偏移首次训练可能选择更早的等价冷fetch，精确身份已在线
核对，但该中间事务未全部保留在紧凑摘要中；不把离线payload核对冒称完整
身份重放。此矩阵也不代表所有PC/set/target或FTQ系统合法性。资格见
[对齐修复完整原生资格](../results/line-gap-probes/training-alignment-v3/qualification.json)。

重要的是：该修复相对正式46541源行键新增0行，却能揭示真实适配错误，
说明行覆盖不能替代功能检查。过程中还发现先前新增第三个ABTB场景后，
静态契约仍硬编码两个helper调用；首轮6167 PASS/1 FAIL保留，新候选逐一
核对三个场景身份、单一await和kind参数后6168 PASS。另一版场景诊断参数
重名导致200 FAIL，亦保留源码/日志/JUnit，不当作RTL缺陷或隐藏失败。
仅删除这些被替代版本243份可重跑native文件，释放5819004369字节；
原地址缺陷native与通过的v3证据保留。生产冻结源码尚未改动。

reset-priority节拍v1实际11 PASS/1 FAIL，因缺必需四-way路径而拒绝。
后续4开/1停和8开/1停完整24 PASS、61项契约PASS，独立核对60次冲突、
14个bin；相对正式834/12288没有新增priority bin，两个负向原因及way3
缺口仍在。相同46541源行集合新增6行，但它们全部已在later-taken全256
候选内，不增加潜在联合收益。见
[节拍v2终态分析](../results/line-gap-probes/reset-priority-cadence-v2/analysis.json)。
逐LCOV键联合正式、later-taken、SC-used、节拍及对齐候选，潜在联合为
40297/46541，即仅256+2新增，不能重复相加；这还不是组合源码回归或正式
发布。见[候选集合比较](../results/line-gap-probes/qualified-bpu-candidate-line-union-v1.json)。

当前原生全量PID140132/140135在23:59仍由PS确认运行；不因静态契约问题
中途更改冻结输入，最终若失败必须保留并拒绝不合格发布。下一步应使用已验证
的双对齐训练构造真正多CFI同cell分配/reset与旧条件metadata重叠，不继续只
盲调节拍或缩减12288分母。接续信息见
[本轮完整进展](../results/coverage-gap-progress-20261010-v10.json)。

首要任务仍是覆盖率缺口闭合。新布局完整11269项、32个独立worker实际结束：
11262 PASS、7 strict XFAIL、0 SKIP；SC累计快照的恢复后处理现已实际退出0。
独立发布审计逐项核对73397个bin计数／provenance及HTML/JSON/十DUT LCOV，
正式报告已刷新，BPU为40039/46541（86.03%，比旧35734增加4305行），其他
模块无退步。原owner因重复快照退出1的记录保留，不把恢复当作原owner成功。

四份SC覆盖对象生命周期修复及全256 later-taken场景现已迁入生产，隔离和
生产各331项契约PASS。新BPU-INT-058使计划增至290点；完整12288-bin路径
矩阵成为全量发布门禁，缺任意一个bin都会拒绝发布。新全量已实际收集11794
项并以32个CPU-active独立worker运行，1634份源码／DUT／依赖再次冻结。
当前正式指标属于上一版289点测量，summary明确标注新源码等待全量，不提前
计入新场景增益。见[生产迁移与终态入口](pytest-parallel-migration-20261009.md)。
后续实验仍在独立目录运行，不能混入冻结回归或提前改写正式报告。

本轮新增两项实证结果。SC-used 已用修复后的 request/response 关联完整
重跑48例：48 PASS、2911模型契约PASS、59620完整帧、264笔公开反馈、
1008个完整SRAM响应及208个raw故障拒绝；24/24物理角色和48/48非零历史
定义bin全部核对。与当前正式46541源行键完全一致，候选新增2行，位于
`rtl/bpu/Tage.sv:460`、`:462`的alt-counter mux源行范围；这只是源行
footprint，不独立证明所有alternate/provider条件已经闭合。资格见
[SC新相位完整复验](../results/line-gap-probes/sc-used-phase-v2/qualification.json)。
尚未迁入冻结生产版，也不能用该范围外推全部历史位／深槽／FTQ。

FTQ的backend redirect九格矩阵在v16/v17两次复现5个普通FAIL，发现
年轻项在flushed提交前出队、trainCache保护窗口已经结束，随后实际训练。
未修改RTL、未改XFAIL，见[缺陷及只读时序证据](ftq-backend-redirect-young-training.md)。
后续v20完整102项为97 PASS、同样5 FAIL；新增first-mispredict的8位置×
正反反馈顺序16格全部PASS，输入接受事件另与committed Monitor对齐。
独立26项检查通过；所有9格backend native均排除后，旧26例加新16例
相对v15新增205条native LCOV命中且无丢失。其中32条是picker包装，
实际DUT RTL新增173条（Ftq 53、ResolveQueue 18等）。原87298键集合
未缩改；另列包装1753键、DUT RTL85545键，见
[完整掩码资格](../results/line-gap-probes/ftq-memory-direct-v5/probe-v20/mispredict-qualification.json)和
[包装／RTL分项](../results/line-gap-probes/ftq-memory-direct-v5/probe-v20/native-scope-breakdown.json)。
这不是FTQ全套通过，也不能加到正式十DUT的46541行分母中。

v18的Driver提交契约错误和v19的过早accepted_event均保留拒绝原因，
只由v20替代。两版过时、可重跑native raw共102份已删除，释放
6412880454字节（约5.97GiB）；保留源码归档、日志、JUnit和紧凑输入输出，
不删除v16/v17缺陷证据或v20的有效原生输入／合并结果。

已结束试验和正式覆盖率必须分开：

| 需求 | 当前证据 | 未完成部分 |
|---|---|---|
| SC full-dirty完整交叉 | 两bank原定80/80物理bin、4343完整帧、22个原始故障拒绝；独立FC/LCOV核验通过 | 尚未迁入正式源码；相对原35734行基线新增0行 |
| SC-used物理/非零历史 | 新相位完整48 PASS，24/24及48/48定义交叉，208个故障拒绝；相同46541键新增2行 | 生产迁入待冻结全量结束；不能外推全部历史/深槽/FTQ |
| later-taken四way路径 | 完整256组实际256 PASS，独立审查确认8192/8192要求路径，32收据及512份FC逐项核对；原12288-bin交叉为66.6667%，不缩分母 | 已迁入生产BPU-INT-058，等待新全量；不代替final-not-taken或reset-priority完整矩阵 |
| 实例化FTQ合法性 | v15完整49 PASS；v20新增first-mispredict完整16格PASS及173条DUT RTL命中，旧用例保留；backend矩阵真实5 FAIL未掩盖 | redirect泄漏未修复，call-ret、full-drop、非均匀metadata完整矩阵仍未闭合；未替换生产DUT或报告 |

历史两cell later-taken资格与正式LCOV使用完全相同的46541行集合；相对当时35734行基线，
两项实际PASS命中54个原未命中行：AheadBtb 18、BypassShadowBuffer 4、
BypassShadowBuffer_1 28、ReplacerState_4 4。输入节拍只依据bank选择，
不依据DUT观察筛way；每个cell仍要求四way的32条增/减/饱和保持路径。
这些是原两cell隔离候选增益。全256后续独立审查实际退出0，相同46541行集合中
相对当时已发布35734行基线新增4561个零命中行：AheadBtb 3003、BypassShadowBuffer 466、
BypassShadowBuffer_1 1086、ReplacerState_4 6；候选单独命中34009行，不能与
正式35734简单相加。见[完整256资格](../results/line-gap-probes/later-taken-full256-v8/qualification.json)。
旧两cell结果见
[原生资格](../results/line-gap-probes/later-taken-resident-v7/qualification.json)和
[逐行位置](../results/line-gap-probes/later-taken-resident-v7/newly-hit-baseline-lines.json)。

FTQ探针另揭示输入观察边界：可写XData读取的是待提交RiseWrite值，不能直接
把该ready当作RTL已接受。保持AsRiseWrite、改用独立committed-memory观察后，
框架标准ReadyValidMonitor准确收到七个有序fetch；没有向用例增加边沿等待。
原先的提前接受失败与使能配置失败分别保留，不能相互掩盖。详见
[FTQ构建与探针](../results/line-gap-probes/ftq-memory-direct-v5/README.md)。

FTQ v10独立资格使用与v6完全相同的87298个源行键，新增命中2348行；
其中Ftq为4882→6615/7086（新增1733），ResolveQueue为3857→4190/9535
（新增333），CommitQueue维持2013/3576。这是新子系统自身的增量，
不能加到正式十DUT的BPU 46541行分母里。其余新增行属于该配置的BPU／
预测器／包装顶层，逐行位置见[新增源行](../results/line-gap-probes/ftq-memory-direct-v5/probe-v10/newly-hit-vs-v6.json)。
同一资格也直接核对多周期输入接受间隔：禁止overlap为两周期，允许overlap
为一周期；八槽组为连续三周期。见[完整独立资格](../results/line-gap-probes/ftq-memory-direct-v5/probe-v10/qualification.json)。

后续v12的全环绕资格在相同87298源行键上比v10新增1300行，无丢失命中；
ResolveQueue为4190→5477/9535（新增1287），Ftq为6615→6620/7086
（新增5），其余8行分布在BPU、SC及包装顶层。相对v6累计新增3648行。
全部真实训练metadata同时与先前BPU输入捕获逐项独立复核，并拒绝四类
离线审查故障。v11的监视器回调递归失败保留，修复只在新v12候选中进行。
见[全环绕独立资格](../results/line-gap-probes/ftq-memory-direct-v5/probe-v12/qualification.json)。

v14真实IFU纠正又比v12新增604行、无丢失命中，其中PHR 308、CommonHR 92、
Ftq 60、MicroBTB 40、ResolveQueue 18，其余86分布在真实预测器及包装逻辑。
同一87298分母，相对v6累计4252新增行。未直接写BPU train/redirect，驱动真实
io.fromIfu.wbRedirect，比较一次实际flush、实际目标fetch及真实训练payload。
见[IFU独立资格](../results/line-gap-probes/ftq-memory-direct-v5/probe-v14/qualification.json)。

v15随后完成三个不同FTQ项各自连续八拍的真实反馈，串行与并行、正反位置
顺序共四个原生场景。新只读Monitor采样committed外部输入，明确核对并行
每拍三个不同身份、各组八拍无断拍、串行／并行接受跨度，以及完整输出与
先前输入metadata；七种离线计数／身份／时序／payload故障均被拒绝。
实际49 PASS、0 SKIP，相同87298源行键较v14新增158行，全部属于
ResolveQueue，无命中损失；相对v6累计新增4410。见
[并行八拍独立资格](../results/line-gap-probes/ftq-memory-direct-v5/probe-v15/qualification.json)。
这仍不证明full-drop、backend redirect或call-ret，不能混入正式十DUT分母。

生产完整pytest的BPU实测40039/46541（比原已发布增加4305），十模块无退步，
该版正式指标现已刷新；这些增益与全256候选相对旧基线的4561
有集合重叠，不相加。逐行比较最新全量40039与later-taken候选34009后，
候选相对最新全量新增256行，均属于BypassShadowBuffer_1；潜在联合为
40295/46541，尚未作为正式增益发布。恢复对238份旧累计导出已证明全部计数／首条provenance
被末态包含，已用原xreactor严格门禁完成1477独立导出合并与独立逐计数审计；
原失败与七个strict XFAIL不更改。新的源码冻结属于11794项后续全量，
不把旧1628文件ledger说成仍对应已迁入新场景的生产源码。见
[恢复与新回归进展](pytest-parallel-migration-20261009.md)。

这轮发现并修复picker的trace dtype helper作用域缺陷：helper形参
`__VdtypeVar`及局部槽号被误当作原生存储／全局槽号，污染67个别名。
现已在`xreactor-coverage-v2`源码分支落地调用offset展开和跨文件回归测试；
候选逐字段验证60352份物理offset／stride，发现集合37842个信号不减少，
原生二进制不变。不是为xcomm补方括号就能解决的问题；dtype数组声明展开
和原生数组索引表达式仍未据此声称完成。系统安装仍冻结，失败v7／v8／v9
及修复v10均保留，不能用通过结果抹掉绑定、Monitor契约或复位观察边界错误。
下一步场景依据见[FTQ剩余缺口](../results/line-gap-probes/ftq-memory-direct-v5/probe-v10/coverage-next-scenarios.md)。

SC full-dirty修正的是前一DriveStable请求与紧接post-edge响应的精确关联，
不是改成falling-write，也不向测试暴露边沿。不同SRAM行值揭示了旧检查晚
一拍的问题，五表响应故障均在目标拍失败。资格保留原80分母、完整四槽、
十PLRU和reset重放；见
[完整80-bin资格](../results/line-gap-probes/sc-full-dirty-matrix-v7/qualification.json)。

正式刷新按旧报告功能点数量检查的问题已经修入当前生产代码：门禁按
当前计划ID精确对齐、保留旧功能点，并核对每个点的实际JUnit身份与状态，
允许真实新增而不允许漏点或同数量偷换。已发布测量为289点、282 PASS、
7 XFAIL；当前生产新增BPU-INT-058后为290点，等待新全量，不能据此代表
尚未登记的SC-used/full-dirty等新需求完成。
十模块构建provenance的旧flags问题已于09:29 UTC修正，安装写入器及原始
日志核对契约也已修复。此次重新检查十份metadata SHA与资格回执全部一致，
60份包文件未改变，无VPI/public-flat，TRACE_FST开启；不重复重建DUT。
见[已完成的构建记录修正](../results/production-build-provenance-correction-v1/qualification.json)。

下方小节按原时间戳保留为历史，不据其中旧PID认定当前任务仍在运行。
原完整物理路径、reset优先级、deep SC、dirty overwrite、FTQ与RTL问题
范围不缩减；当前目标仍未完成。

## 用户授权切换诊断策略：2026-10-10 11:00 北京时间

旧矩阵、laterTaken 和行等待队列已按授权终止，不记为审计完成。生产源码
切换到 1221 文件版本：22 个逐周期轨迹入口默认不落盘，显式加
`--dump-trace` 才导出压缩轨迹；功能覆盖、断言和原生覆盖率不关闭。
2269 项回归、4 个默认关闭的真实 DUT 场景、1 个显式开启的 SC 对照全部
实际退出0。SC原生覆盖逐字节一致，功能快照完整性及去运行身份后的
schema/bin/计数一致。见[策略说明](artifact-policy.md)及
[验证报告](../results/coverage-artifact-policy-v1-readonly.json)。

以下原有全量数字属于1218历史版本，不冒充新版本全量刷新。原始物理路径、
reset优先级、deepSC、dirty overwrite、FTQ与RTL问题等完整目标不缩减；
取消的审计仍待重新取得对应证据。续跑检查点为v99。

## 独立审计推进与无损存储资格：2026-10-10 10:09 北京时间

当次966份raw独立重合并与728份FC核对已实际退出0，200组功能覆盖、
全部十模块LCOV/JSON/HTML一致；metrics完成于09:46。随后串行动态审计
于10:01实际退出0：200个SC history、96个SC masked、144个ABTB、17个
集成场景，共457次完整reset重放及882个集成故障检查；没有复用旧completed
前缀代替重放。根报告与qualified逐字节SHA一致。见
[本轮完整串行动态审计](../results/coverage-current-hybrid-serial457-dynamic-v1-readonly.json)。

修复sequence2713471也已实际terminal0，不能继续标live或重跑。既有矩阵
owner2767544已自动接续，2960296/2960299—2960305八个真实CPU-active工作
进程正在完整case审计。261个完整reset/raw/claim、263个counter及wholeFC
仍未完成，因此formalcurrent/goalcomplete继续false；不以两次pilot代替。

冷分配触发负反馈新场景资格实际2275契约PASS（1149旧+1126新），其中10个
使用真实MemoryBackend/native XClock调度器验证触发至Driver/XTransfer的
周期边界。finalNT保留四节点，laterTaken使用单独验证的两节点递归；观察
首个真实合格冷条件分配后再延迟0—4周期提交。完整525-direct和原非零同cell
重叠门禁保留。尚未运行BPU DUT，新增物理bin仍0，原两次FAIL保留。见
[冷分配场景资格](../results/coverage-bpu-allocation-pulse-readiness-v1-readonly.json)。

新有界存储模块57契约实际0：在独立真实tmpfs中复用已有24002939字节原生
覆盖文件，持久归档777882字节，再恢复后原SHA完全相同。完整文件树逐文件
核验，拒绝缺失、篡改、重复、注入、链接及不完整归档；不删旧证据，不接受
仅RAM中的证据。首次55PASS/2FAIL记录保留，其中磁盘不足确实触发门禁；
第二项等长篡改测试修正了其自身异常预期，未降低代码门禁。见
[无损存储资格](../results/coverage-bounded-evidence-archive-v1-readonly.json)。

此模块尚未接入native owner，也没有启动额外DUT。正常80.5GiB安全线不变；
新方案固定512MiB tmpfs与80MiB持久预算，实际持久余量86507929600低于准入
86520102912，仍拒绝新任务。旧later2944971完整审计及line2951541队列继续
持有原512MiB预留，不能重复使用。40份冻结账本严格实际0；生产1218源码、
350RTL及runtime未修改。当前35734/46541、281/288功能点、200组均值和
物理路径2046/12288、优先级836/12288均未因资格测试增加，原范围不缩减。

## 新报告发布与完整物理缺口：2026-10-10 09:24 北京时间

既有report repair已实际退出0，native_merge与HTML均实际0；根目录summary、
feature-points、rtl-line-coverage与verification-report已发布，四者逐文件
SHA与本轮combined一致。当前10370个测试=10363PASS/7strict XFAIL/0SKIP；
288登记功能点=281PASS/7XFAIL，全数执行，含12个框架点。BPU源代码行
35734/46541=76.78%，比旧32264新增3470、旧命中丢失0，其他九模块不变。
既有sequence2713471已启动metrics2956340，serial457/882和matrix261/263
完整独立审计尚未完成，formalcurrent/goalcomplete仍false。见
[统一报告刷新终态](../results/coverage-current-hybrid-full-1218-v2.json)。

本轮功能覆盖为200组、190全覆盖、10未闭合，组等权98.334987%。它低于
旧197组99.2058%，不代表测试退步：新增完整物理分母暴露此前未统计的缺口。
严格核对1024cell×12路径完整schema后，实际counter路径2046/12288=16.6504%，
仅1/1024cell的12路径全部命中；inc2_3覆盖1024cell，inc3_3覆盖928cell，
inc0_1/inc1_2各15cell，finalNT四路径各14cell，laterTaken四路径各2cell。
reset优先级836/12288=6.8034%，只含same-position before2(440cell)/before3
(396cell)，两负向原因所有原值均0，before0/1也0。不能把遍历所有bank/set
等同于完整四way×所有转换闭合。见
[本轮完整物理缺口](../results/coverage-current-published-functional-physical-gap-v1-readonly.json)。

fresh与历史隔离候选逐行独立Python/AWK对账实际0/7契约：旧候选仍有469个
行键未进入fresh，fresh另有137个旧候选未命中的行键，两者并集36203。
不是直接36066-35734=332；未注入任何隔离raw。见
[逐行对账](../results/coverage-current-fresh-native-line-reconcile-v1-readonly.json)。

later分配顺序v4的真实DUT已实际0/1PASS，30082帧、所选cell四way32条路径
原生门禁全部通过；owner2944971仍在完整独立重放/故障检查，linequeue2951541
仍等待同一完整parent0，不能以native1PASS替代审计或提前扩展到全256。

新负重叠写入来源诊断28契约与完整16918帧实际0，reset模型独立生成并核对
132次写响应，不以观测write/ready初始化预期状态。finalNT选定set仅1次分配
reset；laterTaken为11次分配reset与5次多命中清理reset。五次清理全来自
position7/branchType3 fallback重复，条件条目重复清理为0；最后一次reset在
way1，负反馈命中way0，故不能计作同cell重叠。下一版必须改变真实驻留/分配
和重复条目时序，不是继续冷流延迟扫描。该诊断不声称完整独立PHR/SRAM预测/
parent/故障审计，也不把原2FAIL变PASS。冻结前未签名index_model副本导入被
拒绝，记录保留，显式选用已签名副本后原身份校验保持。见
[写入来源诊断](../results/coverage-bpu-negative-write-origin-v1-readonly.json)。

38份冻结账本严格实际0；生产1218源码、350RTL与runtime未改，未删证据，
未额外启动DUT。80.5GiB正常安全线与既有512MiB预留不变。完整原范围继续保留。


## 全量执行终态与报告修复：2026-10-10 08:59 北京时间

原串行10109项已实际退出0：10102PASS/7strict XFAIL；parallel261已退出0。
独立核对合并证据为10370个唯一node、10363PASS/7XFAIL/0SKIP，功能点全部
288项关联、281PASS/7XFAIL。原owner的exit1确认为预先定位的外部模块空
node前缀报告关联错误，不是pytest/DUT失败。既有repair2713471已自动通过
严格恢复门禁，复用原产物运行postprocess2951851/native_merge2951940：966
份当次原生raw、728份FC已关联。统一HTML/JSON/LCOV/summary尚未发布完成，
完整独立serial457/882和matrix261/263审计也未完成，formalcurrent仍false。
根feature-points暂时是串行结束的286/288中间态；不要据此把并行两点误记
NOT_RUN，也不能把合并关联281/288当完整覆盖需求闭合。见
[本轮精确执行终态](../results/coverage-current-full-shards-terminal-v1-readonly.json)。

新增later原生行测量队列2951541/session3823实际187契约PASS，14份历史LCOV
已签名复制；pidfd等待同一later完整审计owner2944971成功，严格拒绝任意32
物理路径缺失/零值/错误cause、缺完整parent/direct/fault或无prefill读回。
此队列不运行DUT；64MiB子预算包含在现有512MiB预留内，不额外占用native
预算。新增行尚未测量，36份冻结账本严格实际0。见
[原生测量队列](../results/coverage-bpu-later-allocation-native-line-readiness-v1-readonly.json)。

## 真实失败诊断与分配顺序修复：2026-10-10 08:49 北京时间

原full/serial2655665/2655922实际推进到99%，仍未终结；parallel261已经实际0，
repair/matrix仍等待同一原链，未重跑DUT。正式32264/46541和隔离候选并集
36066/46541保持分开，尚未刷新正式通过数或宣布完整目标完成。

later-taken失败轨迹的29288帧只读诊断实际0：reset推导的counter/PLRU逐拍
一致，选定set十次完整T1分配请求与下一拍注册请求一致。条件条目依次分配
way0/3/0/3/0，fallback依次分配2/1/2/1/2；原32路径门禁失败不是物理way
不存在，而是两次分配形成固定角色节奏。此诊断使用观测write输入，不代替
完整独立write生成/parent故障审计，也不把原FAIL改为PASS。见
[物理角色诊断](../results/coverage-bpu-later-way-diagnosis-v1-readonly.json)。

新隔离分配顺序v4只对alias3先执行公开negative预测流，确认真实fallback
接受和完整SRAM读回后，保留原三阶段和所有比较。全部8种初始PLRU的模型
穷举、旧真实失败回归和false-claim门禁等34项新增契约，加旧497项，共531
实际PASS。九个旧helper字节一致，旧场景仅增一处分配顺序分支。真实DUT
2947563/2947564正在运行；计划way0/3/0/1/2不是实际硬件覆盖。仍要求真实
32路径及完整parent/525-direct/reset/fault审计。原v3复制多末尾空行导致两项
字节契约失败的529PASS/2FAIL记录保留，未弱化契约。见
[新公开驱动资格与运行状态](../results/coverage-bpu-later-allocation-order-readiness-v4-readonly.json)。

负向重叠v4的231项契约实际PASS，但两次DUT均实际FAIL：8126+8792帧都没有
真实同cell负向反馈/write-reset重叠，严格非零门禁保持。只读16918帧诊断
实际0：前四alias负向T1没有条件命中，末alias两原因各21次命中但reset不
同拍。必须先形成真实驻留条目，再安排分配/drain/反馈相遇时序，不能把冷
stream延迟扫描或模型通过计作覆盖。新增目标重叠bin仍0，完整动态故障审计
未启动，原失败和所有产物保留。见
[实际DUT失败](../results/coverage-bpu-negative-overlap-native-failure-v4-readonly.json)
与[完整时序诊断](../results/coverage-bpu-negative-overlap-diagnosis-v1-readonly.json)。

35份旧新冻结账本已严格检查实际0；生产1218源码、350RTL和runtime未修改。
新laterDUT独占既有512MiB预留，80.5GiB正常安全线不变，不并发再派其他
native任务。全256/four-way/双负向原因/各原值重叠、SC、FTQ等原始范围不缩减。

## SC 功能覆盖与真实 used 分流：2026-10-10 08:14 北京时间

满dirty覆盖的完整物理cross已独立导出：两bank×五表×四victim×有/无同拍
drain，共80bins。190契约实际PASS；从已审计1950帧的原始preedge和下一
checked rising独立核对完整四槽、旧PLRU victim、旧drain payload及写优先，
确认9事件=9个不同bin，9/80=11.25%，仍缺71。九个真实victim数据扰动均
被拒绝。不是按事件数缩减分母，也未合入旧197组均值。见
[满dirty功能覆盖](../results/coverage-bpu-sc-full-functional-v1-readonly.json)。

两个新SC-used真实DUT由xdist双进程隔离，19意图契约/2DUT实际PASS：
各自6笔真实训练后，用新鲜公开metadata自然达到useScPred=1，未伪造metadata
或写内部状态。939+1110=2049帧；bank1/way1观察到used正确且TAGE同意
不读/不更新、used正确但不同意读/不更新、used错误读/更新三个分流。两个
场景最后阈值均1130/1125/1130/1130。见
[原生SC-used](../results/coverage-bpu-sc-used-native-v1-readonly.json)。

独立审计v1因自己把T1 gated qualifier查晚一周期而实际失败；完整失败和
冻结源码保留。v2用两份真实轨迹重现旧错误并修正关联：T0在接受tick-1
的controls、T1在tick+1有效，不能拿tick+3已清零门控当T1。13契约通过；
四进程完成全部2049帧reset重放和74原始故障检查，精确失败拍/context/status
均核对。基础used cross为两bank×四way×三分流，实际3/24=12.5%，不是整项
deep SC-used闭合；两方向、provider置信度、有效非零历史等仍须扩展。见
[完整SC-used审计与FC](../results/coverage-bpu-sc-used-complete-audit-v2-readonly.json)。

SC-used原生行增量的29契约通过，13份签名历史快照与两次新coverage重合并，
Python/独立AWK一致额外0行，累计候选仍3802、并集36066/46541，正式仍
32264/46541。这再次说明旧行命中不能代替功能检查证据。见
[SC-used行测量](../results/coverage-bpu-sc-used-native-line-v1-readonly.json)。

上述新SC所有owner实际terminal0且句柄关闭；没有重跑DUT或删除证据。
30份冻结账本已检查0；生产1218源码、350RTL和runtime未修改。原full/serial
2655665/2655922仍实际存活96%，parallel261已0，repair/matrix等待同一链。
288登记点和旧279/286正式通过数分开；formalcurrent=false，完整目标不缩减。


2026-10-10 07:54：SC两份真实轨迹的1950帧完整reset重放和69个原始反例
已实际0；原生行增量v2的29契约及Python/AWK交叉测量也实际0，新增0行。
累计候选仍3802、正式BPU仍32264/46541。新增9次合法满dirty覆盖的行为
检查不能由“相关行以前已命中”替代；这是行覆盖充分性之外必须补的功能点。
详见[SC原生测量](../results/coverage-bpu-sc-full-native-line-v2-readonly.json)。

2026-10-10 07:46 北京时间：四way完整parent及原生行测量均实际退出0，新增
19行（ABTB4、UTAGE shadow8、replacer7），候选并集36066/46541、相对正式
额外3802；正式32264/46541未变。SC旧参考模型缺失合法的满dirty victim覆盖，
现已扩展完整PLRU/mask/data/drain-write转换，2960契约与真实457帧phase通过；
五key修正TAGE别名选址后2063契约、1493帧DUT通过，确认9次真实满dirty覆盖
及五key读回。SC独立reset/raw-fault审计正在执行，原生增益尚未测量，不能
计入正式行覆盖率。later-taken真实DUT只有way0/3，严格32路径门禁失败；后续
负向审计因前置失败未派发，不能继续标live或宣称四way/重叠矩阵完成。
详见[最新实际进展](coverage-integrated-abtb-progress-20261009.md)。

2026-10-10 06:52 北京时间：负向审计运行器的真实35反例循环发现累计
Scoreboard状态误用，旧自建等待器在无DUT/子进程时退出143，冻结证据
保留。v2每故障独立board，新增四项直接执行旧/新owner循环的回归，
共205契约实际PASS、251项helper冻结，继续等待同一later-taken原链。
新DUT尚未派发，行数/功能点/功能bin无提前增益，完整需求不缩减。
见 [修正版资格](../results/coverage-bpu-negative-overlap-full-audit-readiness-v2-readonly.json)。

2026-10-10 06:40 北京时间：负向重叠完整独立审计/调度已实现，新增
201契约实际PASS、250项helper冻结。完整parent逐帧循环AST保持，
525-direct及标准库priority算法字节保持；新增真实metadata/接收拍/
预测不暂停/后续S3因果关联和每原因35反例。两类32768帧真实DUT按
pidfd等待现有later-taken链终态，避免重复使用512MiB预留，不降低
80.5GiB正常安全线。尚未派发DUT，新增负向重叠bin仍0；原full/serial
及四way完整parent仍运行，正式覆盖率不变、候选3783未准入。
原值3的负向递减与reset都得到2，见证记录“无数值差异”而不删除该
物理重叠需求。见 [审计资格](../results/coverage-bpu-negative-overlap-full-audit-readiness-v1-readonly.json)
和 [完整进展](coverage-integrated-abtb-progress-20261009.md)。

2026-10-10 06:18 北京时间：四way第一层独立审计已整体0，29184帧及
9counter原始/8导出/76direct故障通过，32物理正向/final-NT路径均为正。
完整parent现已实际运行，原生/AWK测量仍等待它成功；正式行数尚未改变。
另新增不暂停预测的真实异步driver/XTransfer负向反馈场景，1149契约
实际PASS，验证全256坐标/双原因/五alias的完整条目容量与52位历史旧索引，
并拒绝错原因/坐标/零命中的覆盖导出。其两个DUT入口尚未派发，独立完整
审计调度仍待补齐，因此负向重叠新增覆盖=0，不把输入模型通过算RTL可达。
见 [四way第一层审计](../results/coverage-bpu-long-cycle-four-way-pilot-v1-readonly.json)
和 [负向重叠刺激资格](../results/coverage-bpu-negative-overlap-stimulus-v1-readonly.json)。

2026-10-10 05:54 北京时间：四物理way长循环DUT已实际1 PASS，选定
bank1/set0共32条正向/final-NT路径均已命中；全局schema仍12288，
不是全bank/set闭合。完整独立probe审计仍在运行，parent/原生测量待它
成功，正式行数未更新。只读五轨迹重叠盘点59契约PASS、整体0，确认65
次真实reset优先见证，但仅same-position-taken原值2/3；两类负向与0/1
依然缺失。later-taken适配新发现真实steer协程引用未定义taken，旧未派发
DUT的等待器已退出143且证据保留；修正版只改该判断并新增22个协程回归，
全497项PASS，重新等待同一parent。原全量仍运行，正式current=false，
候选3783不准入；原始完整需求不变。详见
[实际运行与修复证据](coverage-integrated-abtb-progress-20261009.md)。

2026-10-10 05:19 北京时间：十节点五alias四物理way探针已实际388模型PASS
并启动真实DUT，强制四way各八条正向/final-NT路径共32个实际bin，不按
alias数推断way。70契约PASS的完整parent（15窗口/53原始/135关联故障）
与32契约PASS的原生/AWK测量已按真实pidfd依次等待。后者保存11份签名
历史LCOV，包含既有9行增益且不读变化中的root LCOV；初版AWK转换错误
的1 FAIL/21 PASS版本完整保留，新版补了十个数字正例。真实DUT、完整
重放和新增行尚无终态，不计新PASS或行数。原full/serial仍live，正式BPU
仍旧32264/46541、候选3783未入账，完整目标不变。详见
[本轮运行链](coverage-integrated-abtb-progress-20261009.md)。

2026-10-10 04:52 北京时间：低way完整parent及独立原生/AWK全链实际0，
新增9个行键，旧隔离候选潜在并集3774→3783，分母46541保持。三行是
AheadBtb.sv:7564/7565/7566处bank1/set0/way0的递减路径，另六行来自
BypassShadowBuffer完整运行。完整8704帧从reset审计、97原始故障、
27读回关联故障、9counter原始/8导出故障全部通过。这9行未写入正式
manifest，正式BPU仍是上一纪元32264/46541；不声称全四way/双递减原因
或deep SC闭合。原矩阵261 PASS完成，串行仍live，全量及独立审计未
终结，正式current仍false。
见 [逐行原生测量](../results/coverage-bpu-long-cycle-low-way-native-v1-readonly.json)。

2026-10-10 04:49 北京时间：原八进程矩阵已实际261 PASS/整体0，全部八
worker正常退出；783份raw/FC与261份trace的只读全身份预检也实际0。
串行10109项仍live，原full尚无终态，正式行数与功能统计仍未刷新。
低way第一层独立审计已整体0，bank1/set0/way0八路径实际出现，9counter
原始/8导出/76direct故障全部拒绝；完整parent仍运行，原生行测量仍待它0。
新增later-taken纯规划291模型PASS，全部256坐标保留五alias和双MainBTB
条目容量，完整非零历史与旧索引验证通过；没有运行DUT，不计覆盖或way
可达。旧容量失败版本保留，未缩减需求。完整目标与旧3774候选不准入
约束不变。见 [最新进展](coverage-integrated-abtb-progress-20261009.md)。

2026-10-10 04:32 北京时间：原10370项回归仍 live，当前计划288点。
下面是上一轮 memory-direct（VPI关闭）完整指标/457重放审计已通过的
正式基线，不是新1218源码纪元的刷新结果；不把 v_line 点数当映射行数。

| DUT | 原生命中/映射行 | 功能点 PASS/总数 |
| --- | ---: | ---: |
| AheadBTB | 17854/17854 | 52/52 |
| 集成 BPU | 32264/46541 | 52/54 |
| ITTAGE | 1398/1398 | 18/18 |
| MainBTB | 1056/1056 | 26/26 |
| RAS | 565/585 | 14/15 |
| SC | 3145/3481 | 22/22 |
| TAGE | 4467/4587 | 34/35 |
| MicroBTB | 794/794 | 17/17 |
| MicroRAS | 91/91 | 15/15 |
| MicroTAGE | 9901/11053 | 19/22 |

加10个框架功能点为279/286 PASS、7 strict XFAIL、0 SKIP；197个功能
covergroup中189个全命中，组等权均值99.2058%，不是功能点通过率。
指标来自 [原生重合并审计](../results/coverage-memory-direct-normal-metrics-audit-v1-readonly.json)
及上一轮正式HTML。summary.json的141 PASS/82点已标为历史快照，不能
作为最新统计。以下各历史表格保留原数字，以此表及全量终态为准。

修正版261审计资格已实际0（547契约、两个完整生产pilot），queue2767544
已通过pidfd等待repair2713471。新十节点单alias DUT实际1 PASS、300模型
PASS，首次在bank1/set0/way0命中四种递增和四种final-NT递减/保持；
完整8704帧的独立重放及parent故障审计仍待完成。独立行测量另已19契约
PASS并保存十份签名LCOV，等完整parent成功后才运行原生/AWK对照。
这不是四way/所有bank-set或later-taken闭合；3774旧候选行仍未准入。
生产源码冻结未改变，正式覆盖时效false，原始完整目标active。
见 [最新进展](coverage-integrated-abtb-progress-20261009.md)。

2026-10-10 03:55 北京时间：新增 261 的完整独立审计及全局功能聚合入口已
实现，修正版实际 547 契约 PASS、0 SKIP，两个真实 pilot 全重放正在执行。
复核纠正了新审计自身的 CoverageDatabase 组顺序假设；原九份文件保留，
新副本七份字节相同、两处单行替换，不改原重放算法。只停止了尚未启动
审计的自建等待器，DUT 与 pilot 没有终止。当前 chain2741663/session58477
只有在两份完整 pilot 成功后才排队，并等待 repair2713471/指标/serial457
全部实际0。全量 matrix261／counter263 以及 whole728-FC/HTML 尚无终态。
原 full／八 DUT worker 仍 live，冻结身份核对通过，正式覆盖率未刷新。
见 [本轮进展](coverage-integrated-abtb-progress-20261009.md)。

2026-10-10 03:27 北京时间：相同参数的只读 collect-only（实际 261 节点）
及真实 worker 目录 SHA 确认了外部模块空前缀与原合并器假设不符。
原 full 和八 worker 仍实际存活，未改冻结文件。严格 carrier/完整用例/
worker/产物绑定修复已实际 38 PASS，算法不变的复制审计另 133 PASS。
新 pidfd 等待器2713471 仅接受原 pytest 两片均成功、仅此精确后处理错误
的终态，保留旧失败，只重新归并／审计，不重启 DUT。
新增 261 的完整动态审计仍待补齐，不提前标 current 或准入潜在行增益。
见 [节点修复资格](../results/coverage-current-node-prefix-repair-qualification-v1-readonly.json)。

2026-10-10 03:09 北京时间：10370 项 full 及八 worker 仍实际存活。
当前纪元的 133 项审计契约通过，原 457 次完整重放／882 个故障算法保留，
pidfd 等待器已排队在原 full 实际退出 0 后执行；没有重启 DUT。
标准库独立物理 counter 模型另通过 51 契约和六份真实生产观测、67160 帧，
拒绝 54 个原始观测／48 个导出故障。六例路径 bin 为 8/8/8/6/32/18，
分母保留 12288，低 way 缺口仍在。新增 261 矩阵的完整独立审计与全局 FC
聚合仍待实现，不拿六例或旧范围代替，不提前刷新正式覆盖率。
见 [本轮独立实际观测资格](../results/coverage-current-independent-counter-pilot-v1-readonly.json)。

2026-10-10 场景生产迁移更新：14 模块迁移 AST/await 门禁、3263 项模型
回归和六个真实迁移 DUT（6 PASS）已经通过。当前完整收集 10370 项，
计划登记为 288 点；新源码纪元 1218 项。旧正式 279/286 功能点及各模块
行数不因登记/pilot 而改变。全量刷新前完整旧 results 的 3950 个归档成员
均完成内容 SHA 校验，无原文件删除。完整刷新将要求串行 10109 项与
八 worker 新矩阵 261 项的并集恰好匹配全量收集；15 项合并门禁通过，
迁移资格与六份完整重放已整体退出 0，独立导出审查拒绝 48 个故障。
全量控制器 owner2655665/serial2655922/parallel2655921 已实际启动，尚无终态；
1218 项源码冻结，检查点 v83。新总数以全量和合并终态为准。见
[生产迁移与刷新说明](integrated-abtb-scenario-migration.md)。

当前不是完整四 way 负向/保持、deep SC-used、完整 dirty overwrite、
真实 overlap 或完整 FTQ 闭合；3774 个隔离候选行键仍未准入正式报告。
以下均为各历史时点的结果。

2026-10-09 17:44 UTC 更新：物理 counter 功能覆盖已进入生产并接入正常
集成自然循环，完整路径分母 12288，write-reset 1024，reset 优先级 12288。
相关 1389 项模型回归、两个新实际 DUT、完整新观测重放全部通过；独立
导出审查退出 0 并拒绝 16 个故障。两个自然循环实际各只命中 10 个路径
bin，说明旧功能覆盖定义确实没有描述该完整物理需求。两个已审计的
final-NT 归档只读重放分别为 32、18 个 bin，低 way 缺口仍在。
见 [生产组件说明](integrated-abtb-counter-coverage.md)。

当前完整 collect-only 8254 项，正常全量尚未刷新；正式功能点仍 286，
正式 BPU 仍属旧纪元的 32264/46541，3774 个隔离潜在行键没有混入。
先前生产报告归因修复的 35 回归/364 raw 重合并也已实际退出 0。
所有本轮句柄已 terminal，新 1194 项源码账本及检查点 v82 已保存。
以下记录中的 running/current/pending 按各记录当时口径理解。

2026-10-09 17:13 UTC 更新：新 221 份合格 raw 的原生测量和独立 AWK
复核均实际退出 0，新增 2364 个行键，候选并集相对旧正式基线的潜在
增益为 3774；完整分母仍为 46541。1651 个 AheadBtb 新行包括 861 个
递增赋值和 790 个初始化赋值，不代表 inc0_1/inc1_2 等全部迁移已覆盖。
见 [独立复核](../results/coverage-bpu-native-whole221-positive-line-review-v1-readonly.json)。

five final-NT 完整审计已整体退出 0（485 原始故障、675 关联故障）。
新重复分段节奏三 DUT 整体 3 PASS，但完整 way 诊断仍未补齐非零
bank 的 way0/1，不扩展此激励、不将这三份 probe raw 入账。旧纪元的
所有依赖任务退出后，已将 counter 行归因修复应用到生产代码，35 项
原有/新增回归通过；native 算法函数 AST 不变。新源码纪元的生产后
364 raw 隔离重合并正在运行，旧四份报告和旧 raw/FC 保留，正式覆盖
状态标为待刷新。旧 8197 用例/286 功能点的审计结论仅属于旧纪元。
下面按时间保留此前 current/pending 等历史结论。

2026-10-09 17:00 UTC 更新：原 remaining221 正向审计已于 16:51:57
整体退出 0，221 例、28 cohort、19006 原始故障及 1989 关联故障
全部完成。结合此前 35 例，全 256 bank/set 的正向 DUT 与独立审计
已完成，见 [整批审计](../results/coverage-bpu-native-five-alias-remaining221-audit-v1-readonly.json)。
新 221 raw 的原生行增益测量已启动，22 项门禁通过、1931 项输入
身份核对通过；独立 AWK 复核器 9 项合同通过，结果仍待测量终态。
正式 BPU 仍为 32264/46541，隔离已复核增益仍为 1410，尚未提前更新。
five final-NT 完整审计及 sliced-cadence 三 DUT 继续运行，源冻结仍在。

2026-10-09 16:49 UTC（北京时间 10 月 10 日 00:49）更新：正式基线仍为
8190 PASS／7 strict XFAIL／0 SKIP、279/286 功能点 PASS、BPU
32264/46541，隔离潜在 1410 行未提前入账。新增已完成证据如下。

- 集成 counter 归因补丁的隔离修正版 41 项回归通过；真实 364 份 BPU
  raw 重合并实际退出 0。新旧 LCOV 逐字节相同，原有所有覆盖率及
  provenance 字段相同。新矩阵补全 5042 个未覆盖源代码行的物理
  counter 归因，独立 AWK 验证通过；2024 个 v_line 点另列不混算。
  [重合并验证](../results/coverage-bpu-integrated-counter-reporting-draft-remerge-v1-readonly.json)
- 四节点 final-NT 五 DUT 整体 5 PASS。完整轨迹物理 way 复核退出 0，
  两个 bank0 坐标四 way 全八迁移；三个非零 bank 坐标 way0/1 仅 inc2_3。
  真实重复分配后 multi-hit 清理低 way 的时序已保留，不能把五 alias
  当四 way。[完整诊断](../results/coverage-bpu-native-final-NT-physical-way-review-v1-readonly.json)
- 新完整审计的 266 项契约通过，五个只读重放 worker 正在执行全部
  reset 重放、485 原始故障与 675 读回关联故障；尚未整体通过。
- 基于重复分配证据的新重复分段周期节奏实验 47 项契约通过，三个
  非零 bank DUT 已启动。地址、模型、全部比较和 525 direct 观测不变。
- 原剩余 221 正向审计已有 219 个成功回执、0 失败，原 owner2543026
  仍 live；整批未终结，不提前准入。生产源码与正常四份报告仍冻结。

功能需求草案已明确集成重复分配/清理需求，但未新增正式功能点或
覆盖率 bin。见 [待登记功能需求](coverage-integrated-abtb-functional-draft.md)。
以下时间记录为历史状态。

2026-10-09 16:09 UTC（北京时间 10 月 10 日 00:09）更新：正式基线
仍为 8190 PASS／7 strict XFAIL／0 SKIP、279/286 功能点 PASS，
BPU 32264/46541；四正式产物 SHA256 未变，隔离潜在 1410 行未入账。

4/8/12 周期节奏实验的三个 DUT 实际退出 0，但完整 gzip 逐 way 复查
也实际退出 0，证明三者仍只有 way2/3 完整八种迁移，way0 仅部分递增，
way1 缺全部迁移，不继续扩展该激励。见
[完整物理 way 诊断](../results/coverage-bpu-native-negative-pair-commit-cadence-way-review-v1-readonly.json)。

真正 final-not-taken 的三节点初版五 DUT 全部在输入资格处失败，已保留
版本、日志、完整轨迹和 raw，且不入账。完整轨迹中的 40 个稳态 A 事件
确认：当前 A 的 ABTB 元数据来自两拍前 B→C token，而非规划误用的
当前 A→B token；此前两节点周期掩盖了这个相位差。见
[独立相位诊断](../results/coverage-bpu-native-final-NT-index-phase-review-v1-readonly.json)。
四节点修正版 563 项纯模型、50 项真实探针契约全部通过，新的五坐标
DUT 在三个原生 worker 中执行；未宣称 DUT PASS 或四 way 闭合。
原正向剩余 221 审计已有 170 个成功回执、0 失败，整轮仍 live。

从行缺口提取的计数器路径矩阵、final-NT 副作用及真实写响应优先级
需求，已写入 [待登记功能需求](coverage-integrated-abtb-functional-draft.md)。
其中 12288 个候选迁移 bin 是草案分母，不是现有覆盖率；正式功能点仍
为 286。生产源码与正常报告继续冻结，待相关审计退出后再准入、修复
集成 counter_gap 映射并执行正常全量刷新。下方旧状态按时间保留。

2026-10-09 15:30 UTC 正式时效确认：dynamic-v2 于 15:26:16 UTC 实际
退出 0，全部 457 条 reset 重放、882 个故障、逐案／聚合功能覆盖以及
1189 份源码、115 个 helper、1378 个输入身份最终检查通过。见
[完整原生动态审计](../results/coverage-memory-direct-normal-dynamic-audit-v2-readonly.json)。
结合已通过的原生指标重新合并，唯一正常全量 8190 PASS／7 strict XFAIL
／0 SKIP、286 功能点、197 covergroup 的正式基线现可标记 current。
该时效仅指当前冻结源码和正常测试计划；BPU 仍为 32264/46541，隔离
候选并集的 1410 个潜在新增行尚未入账，不代表全部验证目标完成。
原剩余 221 正向独立审计和三路初次提交节奏 DUT 仍 live，生产源码
继续冻结。下方按时间记录的旧 pending／失败状态均保留为历史证据。

2026-10-09 15:24 UTC 新增已复核的隔离原生证据：五个完整负向运行在
此前候选之外新增 413 个行键，原生处理器及第二种 AWK 读取器结果一致，
全 DA 分母仍为 46541。累计候选并集相对正式表潜在增量为 1410，尚未
并入正式 32264/46541，也未新增正式功能点。见
[独立复核](../results/coverage-bpu-native-negative-pair-line-review-v1-readonly.json)。
三个预填充 DUT 全通过，但实测仍未闭合物理 way0/1 的双向迁移；新
driver 级初次 pending 写提交节奏实验正在运行。功能点草案还需区分
最终 not-taken 与 later-taken 两条条件项递减路径，不能混为同一证明。
修正版完整动态审计已完成 456/457 重放、866/882 故障，aging-1 仍在
运行；不是整轮通过，生产源码与四正式报告继续冻结。

2026-10-09 15:15 UTC 审计状态修正：原 dynamic-v1 于 15:05:05 UTC
实际退出 1。200 SC history、96 SC masked、144 ABTB 已重放，前 11 个
集成案例完成；下一条 nested RAS 的轨迹迁移检查错误地强求 `program`
字段，而新旧 nested 轨迹都没有该字段。原日志／快照完整保留，不标记
正式 current。新 dynamic-v2 保留 nested 固定程序来源检查、deep/repeat
强制 `program`、全部 457 条 reset 重放和 882 个故障，66 项契约通过，
8 个只读 spawn worker 已实际运行；全部轨迹重新重放，不把旧失败轮的
部分输出当作整轮通过。生产源码、DUT、正常覆盖产物和四正式报告仍冻结。

负向 native-v3 的五个 DUT 已全部 PASS，完整独立审计也已实际退出 0，
拒绝 470 个原始观测故障和 675 个 SRAM 读回关联错误，见
[负向完整审计](../results/coverage-bpu-native-negative-pair-full-audit-v1-readonly.json)。
但逐物理 way 复查发现 way2/3 有全部八种迁移，way0 只有部分递增，
way1 没有目标窗口内迁移；五 alias 通过不等于四 way 覆盖完成，见
[物理 way 缺口](../results/coverage-bpu-native-negative-pair-physical-way-gap-v1-readonly.json)。
真实 1/2/3 alias 预填充实验的 57 项完整契约通过，三 DUT 正在运行；
五份已审计负向 raw 的原生行增量测量另行进行。两者均未计入正式行表。

2026-10-09 13:28 UTC 更新：memory-direct 全量实际完成 8190 PASS、7 XFAIL、
0 SKIP，286/286 功能点执行、279 PASS。BPU 当前原生行覆盖为 32264/46541
（69.32%）；其余九模块与下文历史表一致。197 个功能 covergroup 的等权
汇总为 99.205805%，189 个完全覆盖、8 个未闭合，不是功能点通过率。
705 份当次 raw、204 份 FC、十模块 JSON/HTML/LCOV 独立重新合并及 8197
项正常收集保护均已实际通过。见
[原生指标审计](../results/coverage-memory-direct-normal-metrics-audit-v1-readonly.json)。
原 457 条完整动态重放／882 个故障审计仍在运行，尚不标记正式 current。
下文 2026-10-08 的 29205 行及 5967 PASS 等数字是历史已审计基线，不是
刚完成的原生全量现状；新增隔离场景的行键并集也尚未并入当前正式表。

2026-10-09 14:20 UTC 补充只读定位：集成 `rtl/bpu/AheadBtb.sv` 当前
5042 个未命中 SF+DA 行键全部落在精确的计数器更新块中，涉及 1014 个
物理 cell。递减选择、非零判断、递减赋值各缺 1014 行，递增赋值缺
1010 行，弱正复位赋值缺 990 行。新解析器核对全部 4×64×4=1024
个 cell 的块边界、真实寄存器名及语句角色，12 项契约通过；第二种
AWK 读取器从生成 RTL 和原生 LCOV 独立计算，得到相同 5042 行，并拒绝
8 个错误身份／损坏记录反例。见
[集成计数器缺口清单](../results/coverage-bpu-integrated-abtb-counter-gap-native-inventory-v2-readonly.json)。
现有生产报表仅对 `dut == "abtb"` 附加 `counter_gap`／矩阵，漏了集成
BPU；旧选择器识别还漏掉不带数字后缀的第一个 cell。此处先提供已复核
清单，生产报表生成器留待所有相关审计退出、源码纪元可解冻后修正。
这些是行键，不是新功能点；已命中非零 guard 也不能证明低饱和保持。
负向输入规划已通过全部 256 个 bank/set 的 532 项纯模型检查，真实
五坐标探针仍在运行，未登记功能 PASS 或正式行增益。

原生全量完成前的续跑背景：集成 AheadBTB 的自然流、未生效的 fallback
分配及外部 xcomm 源码变化的独立资格，见
[集成 AheadBTB 进展](coverage-integrated-abtb-progress-20261009.md)。
隔离失败批次没有并入覆盖率，SC 新批次仍需完整刷新审计后才能正式入账。

记录日期：2026-10-08。数值来自完整 pytest 运行生成的
`results/rtl-coverage-manifest.json`，再由 `python3 -m suites.frontend.bpu.rtl_coverage`
合并到 `results/rtl-line-coverage.json`。只合并本次运行登记的 `.dat`，不读取遗留的
`verilator-coverage.dat`。`results/feature-points.json` 是 pytest 的功能点判定，
`results/*/functional-coverage*.json` 是显式定义的 coverpoint/bin（TAGE 的
useful-reset 状态使用独立 covergroup）；三者回答不同问题。
RTL 报告中的 `uncovered_rtl_line_points` 逐项列出未命中的生成 RTL
`v_line` arm；即使同一源码行的另一 arm 已命中，仍保留这条缺口。
`source_lines` 与 `uncovered_rtl_source_lines` 则使用原生 LCOV 的源码行口径：
保留 `v_line` 和 `v_branch`，展开 `S` 的行段，不混入 toggle。
`results/rtl-lines/<dut>.info` 保存同一口径的原生导出，`SF` 已重定位到当前
安装的源码路径；JSON 的逐行缺口同时携带 RTL 内容和 Scala 来源。
AheadBTB 的复制计数器点还附有 `counter_gap`（bank/set/way 与更新类别）；
`abtb_counter_matrix` 给出逐格和逐 bank 汇总，并保留未能映射的数量。
映射依据生成 RTL 的 `takenCounter_<bank>_<set>_<way>_value` 命名和邻近
语句块；若无法确定则不猜测物理格子。
`uncovered_rtl_toggles` 另外列出未翻转的生成 `.v/.sv` 信号位，并排除 picker
包装层；它帮助定位剩余输入/状态活动，但不直接代表未验证的功能点。
每个 DUT 实例传入固定的 `+verilator+seed+1`，并在首个时钟前置位 reset。
picker 的 Verilator 模板调用 `randReset(2)`；未固定种子时，同样的用例会因
随机初值和测试顺序产生不同覆盖计数。下文历史增量仅记录当时的探索过程，
不与本节固定种子的当前数字直接比较。

## 口径与现状

以下统计 Chisel 生成的 RTL `.v` 和 `.sv`，不把 picker 生成的
`*Dut_top.v/.sv` getter/setter 包装层算作预测器 RTL。此前按扩展名把所有
`.sv` 归为包装层，导致 TAGE/SC 等模块的 RTL 分母被严重低估；报告版本 2
只修正了分类，还错误地把 `v_line` 的 `l` 锚点去重称为“唯一源码行”。
版本 3 修正这一统计错误：原生行覆盖必须同时使用 `v_line`、`v_branch`
及其 `S` 行段。`v_line` 本身只是计数器点数，一个计数器可以映射数千行。
旧 `unique_lines` 字段已改名为 `anchor_lines`，仅作诊断，不能作为行覆盖率。
顶层 `line_points` 现在仅统计 RTL，picker 的 `.v/.sv` 包装均另行归类。
命中阈值为一次；同一行多个点的合并沿用各 DUT 记录的 Verilator 原生处理器
`--write-info` 行为，不自行用“任意一个点命中”替换。工具版本记录在
`line_coverage.tool_version` 中，因此升级后必须重新校验基线。
物理行数、已映射源码行数、计数器点数、分支数和功能覆盖率分别报告。

下表为当前已完成独立审计的固定种子正式基线，涵盖既有模块级状态／反馈／恢复场景、
集成 PHR 恢复与方向修正，以及新增 AheadBTB counter／replacer／pending
状态矩阵，以及集成 SC 相邻 mask 合并／clean 重新激活。全仓实际执行 5967 PASS、
7 strict XFAIL、0 SKIP；272/272 功能点执行，265 PASS、7 XFAIL。
189 个功能 covergroup 的组聚合覆盖率见正式 HTML，
不是 RTL 行覆盖率。统一 HTML 现在包含本次运行的十份原生 RTL 行报告。
本表使用 Verilator 5.052 插桩与原生处理器，关闭新增 expression/FSM 项。
原样 WriteBuffer 的五种逐笔对照确认 5.026 优化插桩存在漏计／错拍；
十个 DUT 均已用未改动的 RTL 重建并完成正式回归。
新旧工具的 branch/行段映射不同，分母会变化，不能直接把百分比差当作功能覆盖提升。
详细四格对照见 [coverage-phase-audit.md](coverage-phase-audit.md)，
首次工具链刷新审计见 `results/coverage-toolchain-refresh-audit.json`；
当前正式时效、同工具链增量及 HTML／JSON／LCOV 一致性见
`results/coverage-bpu-sc-state-production-refresh-audit.json`；正常收集保护见
`results/coverage-bpu-sc-state-production-collection-protection.json`。

| DUT | 原生 RTL 源码行 | 行覆盖率 | RTL `v_line` 点 | RTL 分支 | 主要剩余原因 |
| --- | ---: | ---: | ---: | ---: | --- |
| AheadBTB | 17854/17854 | 100.00% | 3405/3405 | 4810/4876 | 正式四类状态矩阵关闭 5120 行；剩余 66 个分支、full dirty overwrite／PLRU 意图及完整 FTQ 资格仍须审查 |
| 集成 BPU | 29205/46541 | 62.75% | 1996/8236 | 6086/13756 | SC 相邻 mask 正式新增 125 行；剩余 17336 行缺口，按模块及有效分支资格审查 |
| ITTAGE | 1398/1398 | 100.00% | 36/36 | 651/658 | 满表 tree-PLRU 替换的两个行缺口已由真实分配／流水线回读关闭；七个分支点及其他功能组合仍需审查 |
| MainBTB | 1056/1056 | 100.00% | 38/38 | 434/442 | dirty/clean 清理与训练重叠关闭最后 40 个映射行；八个分支按实际父模块连接分类但保留分母。零 key 错 owner／更早启动的邻项更新丢失仍为隔离诊断，完整 FTQ 资格未证明 |
| RAS | 565/585 | 96.58% | 22/22 | 198/216 | 三类正式状态场景精确关闭 45 行；剩余 16 个赋值按优先级/action 互斥分类且保留分母，另四个 bos 行仍待 FTQ 系统资格；disable metadata 仍 strict XFAIL |
| SC | 3145/3481 | 90.35% | 33/33 | 875/1038 | 三个 threshold 行已由正式边界／整笔拒绝场景关闭；剩余 336 行均为已复核局部矛盾赋值，保留原生分母；其他分支和功能组合仍需审查 |
| TAGE | 4467/4587 | 97.38% | 116/132 | 1513/1598 | 同拍独立双写正式场景再关闭 70 个 WriteBuffer 行；剩余 120 行为 112 个局部矛盾赋值和八个块头，仅分类不扣分母；captured useful 误关联仍 strict XFAIL |
| MicroBTB | 794/794 | 100.00% | 8/8 | 187/192 | resolve 完整训练向量及连续 useful 恢复／重初始化转发关闭 34 行；五个分支点和其他功能组合仍需审查 |
| MicroRAS | 91/91 | 100.00% | 21/21 | 21/24 | 中性 S2/S3 修正、主 RAS 回退及 redirect 恢复关闭两行；三个分支点及其他功能组合仍需审查 |
| MicroTAGE | 9901/11053 | 89.58% | 2329/3097 | 3238/3746 | 全地址真实训练与 partial shadow 回绕精确关闭 3604 行；剩余 1152 行受既有 lower tag-width 缺陷阻塞，保留分母；回绕后 SRAM 持久化缺陷仍 strict XFAIL |

例如 `rtl/tage/Tage.sv`（picker 重命名编译为 `dut/tage/TageDut.v`）有 10431
个物理行，新版原生顶层映射 3021 行、命中 3021 行；顶层 LCOV 的 `SF` 指向后者。
旧 5.026 曾映射 4194 行且全部命中，其中 `Tage.sv:4786` 的一个
`v_branch` 点通过 `S` 映射 2755 行；这类宽行段映射不是逐行执行证明。
因此，132 个 TAGE `v_line` 既不是源码总行数，也不是原生行覆盖率分母。
当前全部 TAGE RTL 的 4587 个映射行中命中 4467 个：顶层 3021/3021、
WriteBuffer 918/1038，其余子模块 528/528。这里的分母只包含插桩映射行，
并非全部文本行，也不是原始 Chisel/Scala 的执行行覆盖率；局部矛盾行不扣除。

### 集成 BPU 的共享 WriteBuffer 缺口复核

2026-10-08 对正式 BPU 的 17461 个缺口做了独立只读复核。以下三份 RTL 与
独立 DUT 对应文件逐行完全一致，唯一差异都是第 46 行模块声明；复核重新检查
实际 guard 定义、词法嵌套、赋值体及两态真值表，没有借用独立 DUT 的覆盖命中。

| 集成 BPU 源码 | 独立 DUT 对应源码 | 原生未命中行 | 局部矛盾行 | 尚未分类行 |
| --- | --- | ---: | ---: | ---: |
| `rtl/bpu/WriteBuffer_30.sv` | `rtl/sc/WriteBuffer.sv` | 233 | 72 | 161 |
| `rtl/bpu/WriteBuffer_38.sv` | `rtl/sc/WriteBuffer_8.sv` | 843 | 264 | 579 |
| `rtl/bpu/WriteBuffer_8.sv` | `rtl/tage/WriteBuffer.sv` | 451 | 120 | 331 |

SC 部分是外层 `hit` 与内层 `~hit` 的矛盾；TAGE 部分还包含同一 hit 的
内层 else 和后续路径的优先级排除。48 项源码条件变异均被复核器拒绝，
优先级证明移除排除条件后存在反例。456 个已分类行全部仍在正式 BPU
原生缺口和分母中；三份 WriteBuffer 尚有 1071 行待集成场景验证，不能把
“尚未分类”当作“已证明可达”。该结论也不把两个 BypassShadowBuffer 的
6998 个缺口全部归因于独立 MicroTAGE 的 tag-width 缺陷。
逐行证据见 `results/coverage-bpu-shared-logic-gap-review-readonly.json`；
四份正式报告保持字节不变，没有新增功能 PASS 或原生行命中。

下一批集成候选优先关注 pending/clean 生命周期，而非复制独立 DUT 的点名：
SC 两份文件尚未分类的缺口包含 356 个 `wayData` 行和 340 个 `wayMask` 行，
例如 `WriteBuffer_30.sv:342`、`WriteBuffer_38.sv:810` 都处于 dirty-hit 合并体；
TAGE 的 331 行中有 83 行涉及 `takenCtr`，另包含双端口优先级及 dirty 更新。
现有集成 `test_sc_batch_feedback.py` 使用 read-free 窗口、串行逐笔训练；
`BpuAgent.train_batch` 每笔额外等待 24 周期。这些检查能证明最终学习，
不能替代“预测占用 SRAM 时，同 bank 多索引反馈保持 pending、不同 mask 合并、
排空后重新激活”的实际时序见证。后续候选必须从真实捕获的 resolve metadata
生成输入，由 monitor 确认命中目标路径，再用完整公开预测回读检查未选字段，
并区分 TAGE 的训练读与预测读仲裁；不能仅因 burst API 名称就计为流水线覆盖。

### 集成 SC 相邻 mask 反馈：正式刷新与独立审计已通过

新增 BPU-INT-039／040 分别检查相邻不同 mask 的 dirty 合并，以及排空后的
clean 重新激活。两 bank × 两实际索引 × 位置 4..7 的六种配对 × 两种顺序，
每种生命周期 48 个场景。实际仓库的 96 个 DUT 用例全部通过；独立从 reset
重放了 48144 个 rising 状态和 48144 个 preedge 控制帧，完成 5111952 次
比较、288 次真实反馈接收及 864 次完整 SRAM 读响应核对。
1379 项纯模型检查和 24 项实际观测故障对照也已通过准入；故障数据不参与合并。
证据见 `results/coverage-bpu-sc-state-production-admission.json`。

只合并这 96 份通过的 raw 与封存 BPU 基线，候选精确关闭 125 行：
`WriteBuffer_30.sv` 24 行、`WriteBuffer_38.sv` 63 行、`Sc.sv` 33 行、
`Tage.sv` 三行及 `FoldedSRAMTemplate_37.sv` 两行。
正式结果为 29205/46541，未增加缺口，也未删除 456 个已分类行；125 行增量
已经计入上表。场景仅证明 commonHR-invalid、捕获 bias、单 key 的上述
生命周期，不证明 global/BW 表有效历史、多 key 深度、完整 dirty 覆盖或 FTQ 资格。

普通全仓收集还发现并修复了纯测试对临时 `test_pure` 模块的遗留导入。
修复后在无临时别名的环境重新实际执行 1379 项纯模型检查，再正常收集
5974 个用例／272 个功能点，保持四份上一轮正式报告字节不变；见
`results/coverage-bpu-sc-pure-import-fix-readonly.json` 和
`results/coverage-bpu-sc-state-production-registered-admission.json`。
真实全仓刷新于 2026-10-08 11:54:18 UTC 启动，原进程已于 14:34:06 UTC
实际以 0 退出：5967 PASS、7 strict XFAIL、0 SKIP，272/272 功能点执行。
生成的原生 BPU 报告为 29205/46541，其余九 DUT 的行数与上表一致。独立刷新
审计已于 14:41:49 UTC 实际以 0 退出，重新核对 96 份 SC 与 144 份 AheadBTB
轨迹、476 份 raw，以及 JSON／LCOV／HTML 来源、时效和精确 125 行增量。
随后的正常收集保护也实际通过，5974 个用例／272 个功能点与本轮运行一致，
四份正式报告保持字节不变。证据见上述正式刷新审计及收集保护报告。
外部 xcomm 源码的并行编辑单独记录；本轮仍使用身份一致的既有 DUT 和运行库，
不代表新 xcomm 源码已重新构建或通过验证。

### 集成 SC 四 key 深度：新增隔离证据，尚未正式入账

继续分析共享 WriteBuffer 的深槽位缺口，发现单 key 的相邻 mask 场景不能
替代四个实际索引同时驻留时的 dirty 合并与 clean 重新激活。新的两 bank
诊断使用四个不同 SC key、位置 4/6，每阶段连续接收八笔反馈；逐拍检查三个
启用表的完整四槽状态、实际 preedge 控制、训练读响应和排空后的公开预测。
两用例实际通过，独立从真实 reset 重放了 2762 个 rising 帧及 2762 个
preedge 帧，核对 32 次反馈接收、96 次完整训练读响应；三个表的槽位 0..3
均实际见证 dirty 合并和 clean 重新激活。

刺激使用真实冷启动捕获的 redirect checkpoint，以及 path hash 为零的目标，
并非把观测状态重新装进参考模型。独立 PHR 参考逐拍验证全部 52 个物理
history cell、76 个 fold register 保持零，且每次实际 taken 的 path hash 为零；
公开回读同时检查八个原 provider 的身份、counter 和两位置的 SC 决策。
这解决了此前仅恢复低 13 位却误以为完整历史相同的刺激问题，不是 RTL 修复。

只合并这两份通过的 raw 与上一批已准入的 125 行候选，额外精确关闭
516 行：`WriteBuffer_30.sv` 113 行、`WriteBuffer_38.sv` 401 行、
`ReplacerState_4.sv` 两行；候选为 29721/46541，没有新增缺口，456 个已分类
行仍全部保留。失败 epoch 的 raw 没有参与合并。独立证据见
`results/coverage-bpu-sc-four-key-zero-history-readonly.json`。

另对已独立准入的两 bank 反序、位置 6/7 跟踪执行了 16 个观测故障重放：
分别在 dirty/clean 阶段扰动深槽位 selected T2 payload、未选 lane 保留值、
preedge drain ready，以及高位 physical history cell／fold register。
全部实际触发带观测时刻、差异字段、expected/actual 和首错状态的普通
`ScoreboardMismatch`。这是观测负对照，不是 16 个实际 DUT 负向运行，
不创建 DUT、不产生 raw，也不增加行覆盖命中；证据见
`results/coverage-bpu-sc-four-key-deep-observation-controls-readonly.json`。

随后补查正向 provider 的 bias selector：正常单分支反馈将真实捕获的
counter 从 2/3 准备到 4/5，分别核对同 provider 的增量或 mispredict 后
较长表弱正向分配，并检查未选 provider 不变；SC 两阶段检查期间才要求
已资格化的 provider 身份保持不变。普通 ready/valid monitor 的稳定相位
取样、下一 rising 确认，与 coherent rising 取样不能按相同 tick 直接等同；
最终场景使用现有 `BpuPhrObservation` 统一 transaction 与 PHR 的观测来源，
没有使用时间容差。两 bank 实际通过，独立重放还严格核对了每一笔准备
反馈的真实公开接收，以及所有 checkpoint、准备／读回 transaction 与
同 tick 的完整流水线关联结果。

只合并最终这两份通过的 raw，在 29721 行候选上再精确关闭 54 行：
`WriteBuffer_38.sv` 13 行、`WriteBuffer_8.sv` 24 行、`Tage.sv` 九行、
`Sc.sv` 三行和 `CommonHR.sv` 五行，候选为 29775/46541。
全部失败或未准入的准备 epoch 均封存且不参与合并，456 个已分类行仍保留。
证据见 `results/coverage-bpu-sc-positive-bias-readonly.json`。这仅证明位置 4/6
的上述正向 provider 场景，不代表全部位置／弱强角色的 bias selector 矩阵，
额外命中的 CommonHR 行也不能代替 global/BW 有效历史场景的功能检查。

两 bank × 六种位置配对 × 两种 key 顺序 × 两种 mask 顺序的 48 场景矩阵
随后已实际全部通过，并完成独立重放：66288 个 rising 帧和同数 preedge 帧，
768 次真实反馈接收、2304 次完整训练读响应，1152/1152 个定义 cross bin 命中。
只合并这 48 份通过的 raw 与 29205 行封存候选，精确关闭 576 行至
29781/46541：`WriteBuffer_30.sv` 137 行、`WriteBuffer_38.sv` 437 行和
`ReplacerState_4.sv` 两行；没有新缺口，456 个已分类行仍保留。证据见
`results/coverage-bpu-sc-four-key-depth-matrix-readonly.json`。
这里的 576 不是在前述 516 或 54 上继续增加：不同实验使用的输入集合不同，
不能把候选增量简单相加。

进一步检查发现，固定 counter 2/3、按升序列出的两位置，只给部分物理 way
安排了 weak／mid 角色。全位置矩阵不等于完整 bias selector 矩阵。因此新增
2/3、3/2、4/5、5/4 四种真实 provider counter 配方，分别交换强弱角色和方向；
准备阶段只使用合法的公开反馈，独立检查实际 provider 增量／较长表分配，
不伪造 metadata 或参考模型初态。8 个代表场景与 321 项纯规则检查已实际通过；
独立重放严格核对同 coherent tick 的完整 transaction 来源、52 个 history cell
及 76 个 fold register。定义矩阵目前命中 192/4608 个 bin，直接从实际 bias
写 mask／命中槽位采样的物理矩阵命中 64/256 个 bin，不能宣称全部闭合。

只合并这 8 份已准入 raw 与 29775 行封存候选，额外精确关闭 74 行至
29849/46541：`WriteBuffer_30.sv` 12 行、`WriteBuffer_38.sv` 30 行、
`Tage.sv` 17 行、`Sc.sv` 15 行。没有新缺口，456 个已分类行仍保留；证据见
`results/coverage-bpu-sc-provider-role-smoke-readonly.json`。
另在已准入的两 bank 正向角色跟踪上实际执行了 16 项故障重放：缺失真实
mispredict、修改未选 provider、错误历史表分配、错误 counter 增量、篡改实际
公开准备反馈、相同 tick 的读回／checkpoint metadata 错配，以及实际 bias mask
错误。两份未修改跟踪先重新通过独立重放；16 项扰动均在预定检查处抛出普通
`AssertionError` 或带字段／时刻的 `ScoreboardMismatch`。这是证据检查器负对照，
不是 16 个 DUT 负向用例，也不产生 raw 或覆盖率增量；见
`results/coverage-bpu-sc-provider-role-lineage-controls-readonly.json`。

四种配方 × 两 bank × 六种位置配对 × 两种 key 顺序 × 两种 mask 顺序的
完整 192 场景已于 2026-10-08 13:15:13 UTC 启动，按配方分成四个隔离 pytest
进程，各自保存 raw 和功能覆盖来源。四个分片实际各通过 48 项，父进程以 0
退出，共 192 PASS；四份独立完整轨迹回放也已全部以 0 退出，完整矩阵合并
准入随后实际通过。4608/4608 个定义 cross bin 各命中一次，256/256 个物理
bias lane／槽位／生命周期 bin 各命中六次，四份来源合并没有重复计数。
独立核对 360264 个 SC rising 帧及同数 preedge 帧、同数 PHR 帧，完成
38508888 次 SC 比较、18723744 个 physical history cell 和 27365472 个 fold
register 比较，以及 9096 次真实 checkpoint 恢复和 1800 笔 provider 准备反馈。

只合并这 192 份通过 raw 与 29775 行封存候选，精确关闭 167 行至
29942/46541：`WriteBuffer_38.sv` 102 行、`WriteBuffer_30.sv` 24 行、
`Tage.sv` 17 行和 `Sc.sv` 24 行。没有新缺口，456 个已分类行仍全部保留；见
`results/coverage-bpu-sc-four-key-complete-role-matrix-readonly.json`。
该完整矩阵仍是隔离准入，不是正式功能点或原生覆盖率入账。

上述候选仍不改变上表的正式覆盖率，也不覆盖 commonHR-valid global/BW 表、
full dirty overwrite、预测重叠或完整 FTQ 资格，不能据此宣称这些功能已完成验证。

有效公共历史的资格实验进一步确认了下一步刺激入口：目标前的连续预测流，
可以在不伪造 metadata 的情况下取得 `commonHR.valid=1` 且保留真实 2/3 provider
的完整 transaction。顺序取指不是每个半块地址都遍历；奇数 bank 目标另用正常
训练的跳转到达，并选择实际 path hash 为零的地址，保持完整零 PHR 参考。
最终两 bank 实际通过；独立从 reset 重放 937 个 PHR 帧和同数 SC 预测路由帧，
比较 48620 个 physical history cell 和 71060 个 fold register，严格核对 40 份
完整同拍 transaction 来源及 31 次真实 checkpoint 恢复。
global/BW 各自观察到 94 个有效预测读周期，并按真实 PC、history 和 bank
重新计算地址。证据见 `results/coverage-bpu-sc-real-valid-common-history-flow-readonly.json`。
这份资格证据只证明有效历史的捕获与预测读路由：ghr/bw 均为零，本身不证明
非零历史、global/BW 训练写回或 dirty/clean 生命周期。失败 epoch 已封存；包括最终通过
资格实验在内的全部 raw 均未参与候选或正式原生覆盖合并。

随后在独立目录扩展 SC 参考模型，保留从 reset 推导 SRAM／shadow 的既有
状态转移，另按真实 PC 和捕获 GHR/BW 计算公共表地址、核对预测索引，并按
commonHR-valid 门控请求。1068 项纯模型检查实际通过，覆盖全部 GHR/BW 位、
完整六位有符号饱和、未选 lane 保留及无效历史与原有请求模型的一致性。
两 bank × 真实 valid/invalid 的四个 DUT 对照也全部通过，再独立重放了
2048 个 rising 帧、2048 个 preedge 帧及同数完整 PHR 帧，完成 217460 次 SC
比较、八次真实反馈接收和 32 次完整训练读响应核对。有效历史每笔检查五类表，
无效历史只启用 path/imli/bias；两种模式均核对 provider 保持和公开 SC 回读。
40/40 个定义 cross bin 命中；完整输入／输出及 checkpoint 均核对真实同拍来源。

只合并这四份通过的 raw 与 29849 行封存候选，额外精确关闭六行至
29855/46541：`CommonHR.sv:945–946,1049–1050` 四行，以及
`Sc_Anon_1.sv:133`／`Sc_Anon_2.sv:133` 各一行，后两项为实际训练读 bank mask
寄存器更新。没有新缺口，456 个已分类行仍保留；见
`results/coverage-bpu-sc-valid-common-history-training-readonly.json`。
16 项实际观测故障重放同时验证了 global/BW 的 T2 payload、完整 SRAM 响应、
无效历史下的意外写入和未选 shadow lane 检查。全部抛出包含字段、时刻、差异
及首错锁存状态的普通 `ScoreboardMismatch`；没有 DUT/raw/覆盖信用，见
`results/coverage-bpu-sc-valid-common-history-controls-readonly.json`。

这批仍是隔离准入证据，未登记新功能点、未改变正式报告。实际刺激的 ghr/bw
仍为零，只验证一个 key 的两笔相邻反馈，不等于非零公共历史、全部索引、完整
dirty/clean 深槽位或 full overwrite／FTQ 资格。仓库原有零历史参考的范围没有
偷偷放宽；后续正式化需要迁移经过准入的扩展组件及对应准确范围的 pytest 场景。

非零公共历史随后也已取得真实集成证据：两 bank × 前向／后向条件分支的四个
场景实际全部通过。条件前缀和最终无条件跳转使用正常公开训练及真实冷启动
checkpoint，实际 path hash 为零；完整 PHR 仍由独立参考逐拍检查，而目标处
真实取得 GHR=1、BW=0/1。另增加 CommonHR 边界 Bundle／monitor 和从 reset
开始的 GHR/BW 状态参考，核对条件位置去重、流水线候选、移位截断及真实恢复；
288 项独立算术／场景规则检查实际通过，没有将观测旧状态装入参考模型。

独立从 reset 重放全部四份轨迹，核对 3059 个 SC rising 帧及同数 preedge 帧、
3059 个 PHR 帧及同数 CommonHR 帧、8 次公开反馈接收和 40 次完整 SRAM 读响应。
44 份完整 transaction 来源与 54 次真实 checkpoint 恢复严格对齐；两次目标捕获
各自检查实际条件分支与最终跳转路径，再比较预测索引、五表训练及公开 SC 回读。
定义的 40 个 bank／方向／表／反馈 cross bin 均由实际通过轨迹命中一次。

只合并这四份已准入 raw 与前述 29855 行封存候选，额外精确关闭六行至
29861/46541：`CommonHR.sv:1153`／1154、1205／1206、1257／1258，分别是
S2 override 路径下 histQueue 槽位 4、5、6 的 GHR/BW 写入。没有新增缺口，
456 个已分类行均保留；见 `results/coverage-bpu-sc-real-nonzero-common-history-readonly.json`。
这仍是隔离候选，未改正式报告或登记功能点；实际 GHR 范围仅为 1，BW 为 0/1，
不证明全部历史位／索引、深槽位 dirty/clean、full overwrite 或完整 FTQ 资格。
不同实验候选仍不能把行增量直接相加，正式化前须按来源重新合并审计。

24 项实际观测负对照随后全部按预期抛出带字段、观测时刻、差异及首错锁存状态
的普通 `ScoreboardMismatch`：四场景分别扰动 GHR、BW、路径中的虚假条件命中、
前缀分支类型和 global/BW 的实际 T0 读索引。检查的是既有轨迹的错误观测，
没有创建 DUT 或产生 raw，不增加覆盖率；见
`results/coverage-bpu-sc-real-nonzero-common-history-controls-readonly.json`。

最后按实际 raw 来源重新合并完整角色矩阵 192 场景、valid 门控四场景和非零
历史四场景，共 200 个已准入 positive 场景，并保留其已封存的先前准入基线。
联合候选为 29954/46541，比完整角色矩阵再关闭 12 行；这是重新执行原生合并
得到的去重结果，不是把各候选的增量相加。456 个已分类行、原生 46541 行分母
全部保留；失败／探针／负对照／资格实验 raw 均未混入。见
`results/coverage-bpu-sc-role-valid-nonzero-union-readonly.json`。
该联合证据仍不改上表的正式基线；下一步须将可复用组件和准确范围的场景迁入
仓库，再执行正常完整 pytest 和同源 JSON／LCOV／HTML 刷新审计。

2026-10-08 retained-owner 隔离诊断随后已正式化。单纯四索引
pending 转发及饱和保持虽然逐拍正确，但临时原生行数不变；真正的缺口是
请求 physical way 与 retained shadow owner 分离后的 depth 0–3 counter 更新。
四 bank × 双向 owner × 四 depth × pending/clean 共 64 组合全部通过；真实
旧 way metadata 的请求 counter 固定为 6，retained counter 却依次为 5→6、
6→7、7→7，证明不能复制请求 counter，也不能把请求端口当作写回 owner。
每组检查完整目标及其他居民状态；192 项逐拍路由/计数器见证通过。
只在临时目录合并这些通过诊断的数据及四个新 API 代表场景，候选为
4397/4587（95.86%），v_line 105/132、分支 1472/1598，恰关闭 53 个
WriteBuffer 行且没有新缺口。112 个局部分类行均保留，候选剩余未分类为
78 行（当时仅分类 112 个赋值）。见 `results/coverage-tage-retained-owner-readonly.json`。
仓库新封装的四个 depth-3 代表场景已独立检查完整输入、216 个 shadow 周期
及正反流水线完整 profile；后续 117 项纯模型/能力/失败清理/异常上下文
检查通过。已登记 BPU-TAGE-034，其正式测试代码的隔离 64 组合已全部通过，
检查 3360 个 shadow 周期并闭合 192 个 cross bin，八个负对照均按预期产生
带 transfer/时刻的普通 FAIL；只合并该测试 raw 也精确关闭同样的 53 行。
见 `results/coverage-progress-tage-retained-owner.json`。全仓刷新已完成并审计：
1401 PASS、6 strict XFAIL、0 SKIP，254/254 功能点执行；333 份 raw、146 份
功能 JSON、147 组及十份 LCOV/JSON/HTML 同源/时效一致。TAGE 正式关闭同样
53 行，其余九 DUT 的指标和缺口集合不变；额外块头分类后剩余 120 个局部
分类行、70 行未分类，不扣原始分母。见
`results/coverage-tage-retained-owner-refresh-audit.json`；刷新后的 1407-item 收集
保护见 `results/coverage-tage-retained-owner-collection-protection.json`。
taken base 隔离 useful 更新，不代表原 useful 缺陷
已修复；未证明完整 FTQ 资格、lower saturation、full miss/PLRU overwrite。

随后双写分析仍是只读诊断，不属于已完成的 BPU-TAGE-034 正式增量。
同一批真实 NT→T 预测 metadata，经正常弱/强 counter 替换令两个 way 交换，
再同时反馈：四 bank × 四 depth × pending/clean 的 32 组合全部通过，
192 个双写见证、1760 个 shadow 周期及正反完整 profile 检查通过；288 组
手算组合检查独立双命中模型。相对于 4397 行正式基线，临时再关闭 21 行至 4418/4587，
见 `results/coverage-tage-dual-cross-owner-readonly.json`。
普通 owner 的 bank0/depth1–3/pending-clean 六个代表场景又关闭 24 行，
候选为 4442/4587（96.84%）、v_line 113/132、分支 1497/1598；330 个
shadow 周期、48 个双写见证和 320 组手算 hit/miss 组合检查通过，见
`results/coverage-tage-own-port-retained-readonly.json`。这不是四 bank 正式覆盖。
这些探针均不修改正式覆盖 manifest，也没有登记新的功能 PASS/XFAIL。

此前局部证明只计 112 个赋值行，另有八个同路径 `else begin` 块头也满足
精确的优先级矛盾；16 种布尔赋值和八个源条件变异对照通过，见
`results/coverage-tage-clean-copy-headers-readonly.json`。这是分类，不是新增
命中或扣分母。上述双写候选仍缺 145 个原生行，其中 120 个局部分类行，
25 行待验证。源码复核将这 25 行归入四类：depth0 饱和/companion clean-hit
（1 行），深层 port0 miss × companion dirty-hit（6 行），深层 port0 miss ×
companion clean-hit（3 行），深层 port0 hit × companion miss（15 行）。
正常驱动构造建议及逐行位置见
`results/coverage-tage-dual-write-gap-review-readonly.json`。随后十个代表场景
通过，339 个 shadow 周期和 62 项双写见证精确关闭其中 22 行，候选到
4464/4587；剩余三行 983/1078/1173 需要 port0 已饱和时 companion 首次 miss，
不能把第二拍的 companion hit 当作替代。见
`results/coverage-tage-mixed-companion-representatives-readonly.json`。随后扩展的
四 bank × 四 depth × 四 companion 状态加 depth0-clean 对照，共 68 组合通过；
2148 个 shadow 周期、416 项双写见证与完整正反 profile 检查精确关闭全部
25 行，临时候选 4467/4587（97.38%）、v_line 116/132、分支 1513/1598。
剩余 120 行与已证明的 112 个局部矛盾赋值加八个块头逐项一致，不扣分母。
见 `results/coverage-tage-mixed-companion-full-readonly.json`。这仍是隔离证据，
不能直接合并进正式 manifest，也不能据此声称其他分支或全 TAGE 验证完成。

双写需求 BPU-TAGE-035 已正式通过，当时已审计完整报告为 255 点；随后 RAS 刷新到上表的 258 点。
新 bounded reference 从同一 prestate 同时解析两写，drain
仅执行一次，显式拒绝 slot 碰撞、重复 key、跨 bank/跨 set 和 full-row PLRU。
509 项纯模型/scope/coverage 门禁检查及八模式 depth3 硬件代表通过；1917-item
正常收集保持四份正式报告字节一致。十项负对照均产生有上下文的普通 FAIL，
无超时、teardown 或悬挂任务错误，见 `results/coverage-tage-dual-shadow-negative-controls.json`。
正式 pytest 代码的隔离 128 组合矩阵已通过，独立重放核对 5336 个 shadow 周期、
832 项双写见证、完整输入/正反 profile 及 384 个 bin；仅合并该测试 raw 与冻结
基线，精确关闭同样的 70 行且无新缺口，见
`results/coverage-progress-tage-dual-shadow.json`。完整全仓刷新及独立审计随后完成：
1911 PASS/6 strict XFAIL/0 SKIP，255 点执行、249 PASS；334 raw、147 功能 JSON、
148 组及十份 LCOV/JSON/HTML 一致。恰关闭 70 行，无新缺口，其他九 DUT、
源码/工具/分母及六项缺陷不变；1917-item 正常收集不改新版四份报告。见
`results/coverage-tage-dual-shadow-refresh-audit.json` 与
`results/coverage-tage-dual-shadow-collection-protection.json`。

RAS 的 65 个缺口另已按实际源码复核：八个 `if (same_slot) ... else if
(pop && nonzero && same_slot)` 赋值局部矛盾，另八个在
push 分支内的 pop 更新由父模块 `rasAction==2/1` 互斥；九项源条件变异
对照均拒绝。仅分类这 16 个赋值行，原生 520/585 和全部分母原样保留。
此前把条件头 515 也归入不可达的说法已更正：该行 true-arm 为零，但可达
false-arm 的原生 counter 为 63，LCOV 如实导出 `DA:515,63`；赋值 516 仍未命中。
不可达语句体不意味着整个条件行不可达。其余 49 行分为提交栈索引/repeat/
wrap（34 行）、非 push 有效提交的 bos 回收（4 行）及 redirect-call/return、
真正相邻 push-pop bypass（11 行），不是 49 个功能点。
现有 repeated-commit 只在固定 CALL_A/CALL_B 形状验证，尚未交叉八个真实
pre-operation SSP。redirect-call 还缺公开 `cfiPc` 驱动封装；`Ras.scala` 从
`redirect.bits.cfiPc.signGuard + 2` 生成恢复返回地址，不用 speculative
`startPc/cfiPosition`。应先补驱动/被动 monitor，再按真实捕获的 metadata
检查，不在用例里写内部 IO。逐行及源码哈希证据见
`results/coverage-ras-commit-gap-review-readonly.json`；目前未登记新增 RAS PASS/XFAIL。

八 SSP × 普通/饱和共 16 组正常驱动诊断随后通过。独立有界 compressed-call
模型和另一个八物理格重放器核对 1063 次公开操作、5715 项比较；24 次队列
复用后再退栈，检查 committed counter 回读及仍驻留邻项。达到八格容量时的
底部淘汰显式计入，不要求无限调用栈。临时 raw 恰关闭上述 34 行至候选
554/585（94.70%）、v_line 22/22、分支 167/216，无新缺口；剩余 31 行为
16 个分类赋值及 15 行待验证。见 `results/coverage-ras-indexed-commit-readonly.json`。
首轮严格 33 行门禁的失败及更正前分类已归档，不能把它当作 DUT 缺陷。
该首轮诊断只覆盖 top/SSP/SCTR 投影，不直接计功能 PASS 或正式行覆盖，
也不证明完整 FTQ 资格。随后在临时目录实现静态 Bundle/@on 被动 monitor，
同拍采集公开输入、提交流水级及八个 committed 槽的地址/counter；独立
compressed-call 模型还保留已弹出槽的存储值，检查完整邻项而非仅 top。
真实隔离 pytest 的 56 项纯检查和 16 组合硬件测试通过，检查 1063 次操作、
5315 个周期、33353 项比较；另一个物理表重放器逐拍独立复核通过。
八项观察错误负对照均产生有请求/观测时刻/状态的普通 FAIL，包括漏提交，
没有额外清理错误。见 `results/coverage-ras-committed-cells-prototype-readonly.json`。
993 份当前回归运行源码未改；该原型仍未登记正式功能点。全仓刷新结束并审计
前不使用其运行中的 RAS raw 作基线，不宣称新原型已关闭 34 行；其临时原生
增量审计另受完成的正式基线门禁保护，不能复用首轮投影诊断的数字充数。

随后沿 CommitQueue → FTQ → RAS 的实际源码复核提交资格，纠正旧分组名称
`neutral_commit_bos_reclamation` 的误导：CommitQueue 只入队 valid 且
`rasAction != None` 的指令，不能用任意 speculative push 后伪造 action=0
提交来声称系统可达。非 push 的有效候选是 action=1（Pop）和 action=3
（PopAndPush），但还必须证明真实退休顺序、捕获 metadata 与 distance>2
条件同时成立；这四行既未验证可达，也不能分类为不可达。源码逐项及八个
源条件变异对照见 `results/coverage-ras-commit-qualification-source-readonly.json`。
另发现 action=3 能通过 FTQ，RAS 父级却用 `== Push`／`== Pop` 而非按位判断，
两者均为 false；已有 UBTB 属性回传／ITTAGE 资格检查不覆盖 RAS coroutine
的栈效果。此项仍是待动态验证的预测行为，不直接判为架构功能缺陷或新增 XFAIL。

相邻 push→pop 的缺口另已实测：逐次 `act()` 会排空，不能产生这一拍间关系，
而已有 `PulseDriver.send_many()` 能连续发送，不需要用例知道边沿或 asyncio
并发细节。复用公共 driver、静态 Bundle/@on monitor 和 Scoreboard 的隔离
真实 pytest 完成 27 组 nested/alternate/turnaround 及重复 9/10/12 次的饱和
场景；198 次操作、225 周期、1431 项比较通过独立展开调用栈重放。公开
top/SSP/SCTR 每拍与冻结期望一致，输入完整 payload/相邻节拍及全部 committed
邻项保持也检查通过；不声称完整 speculative queue/recovery metadata 模型。
47 次相邻 push→pop 对应 `RasStack.sv:801` 原生计数 47，八项观察错误负对照
均产生带 request/tick/status 的普通 pytest FAIL。证据见
`results/coverage-ras-adjacent-bypass-prototype-readonly.json`。该原型不修改冻结
源码、不登记正式功能点、不把临时 raw 混入正式报告；正式 RAS 仍为 520/585，
增量合并同样等待当前完整刷新及审计通过。

redirect 的公开 cfiPc 驱动也已在隔离 agent 原型补齐，而非在 testcase 写信号。
24 组真实 pytest 交叉 inflight/committed checkpoint、SCTR=0/3/7，以及同地址
调用重做、不同正/负地址调用重做和返回重做；先制造两个真实 wrong-path call，
再用此前捕获的 checkpoint metadata 恢复，最后逐步退栈验证旧链仍正确。
独立展开调用栈/物理 committed 表重放通过 524 次操作、1160 周期、1528 项
比较及 24 次恢复；核对完整输入、metadata 的实际来源、parent commit 延迟、
redirect 三拍响应、cfiPc 裁剪/signGuard 及完整 committed 邻项保持。
八项负对照均普通 pytest FAIL，包括错 cfiPc、漏 redirect、错 checkpoint、
邻项破坏及晚恢复。原生 raw 实际命中全部十个原缺失 redirect 行
325/330/748/749/752/755/756/827/831/832。见
`results/coverage-ras-redirect-redo-prototype-readonly.json`；未登记正式功能点，
尚未合并原生增量，不声称 full queue recovery reference 或 FTQ 系统资格。

三类场景随后收敛成独立正式化候选包：公共 `RasOperation`/`act_many()` 处理
批量发送与逐笔结果对齐，`observe_committed()` 管理被动 monitor 生命周期，
`restore(cfi_pc=...)` 保持旧调用形状并封装地址裁剪和恢复延迟。167 项纯模型/
能力/缺格检查及三项硬件 pytest 共 170 PASS；硬件为 16 committed、27 相邻、
24 redirect 组合。功能覆盖为 16/24 个多轴 cross bin 与 27 个单轴场景 bin，
共 67 格，均在检查通过后采样；单轴不伪造额外维度凑 cross。首次错误的单轴
CrossDef 失败记录保留，修正版已全量重跑通过，不当成 RTL 缺陷。
25 项针对新 API 的负对照均普通 FAIL，包括破坏 `act_many()` 返回数组。
6700 个周期、36339 项比较的完整输入/metadata/观测/相对 tick 与独立重放记录
一致，三个实际 pytest raw 命中 45 个原始缺口，尚不合并正式行增量。见
`results/coverage-ras-integration-candidate-readonly.json`。
另外用新 agent 运行字节相同的全部旧 RAS 测试，只将输出目录隔离：15 PASS、
1 原有 BPU-RAS-008 strict XFAIL、0 SKIP，12 个旧测试源文件哈希一致。见
`results/coverage-ras-candidate-legacy-readonly.json`。候选仍在临时目录，未改变
当次 993 份运行源码或正式计划。TAGE-035 全仓刷新审计完成后，候选已用
16 份新鲜正式 RAS raw 加三份实际正向 pytest raw 通过原生增量门禁：精确
关闭45行至565/585，无新缺口，剩余16个分类赋值和4个待FTQ资格的bos行。
上述为候选阶段的门禁。随后实现已迁入仓库并登记 BPU-RAS-013/014/015，
实际仓库 fixture／测试完成 170 PASS、旧场景 15 PASS 加一个原有 strict XFAIL、
25 项普通 FAIL 负对照及正常收集保护。完整回归于 2026-10-08 03:20 UTC
结束：2081 PASS、6 strict XFAIL、0 SKIP；258 点执行、252 PASS。
独立审计核对 1004 份运行源码未改、337 份本轮新鲜 raw、150 份功能 JSON、
151 个 covergroup 和十份 LCOV／JSON／HTML 一致。RAS 正式精确关闭同样
45 行至 565/585，无新缺口；其余九 DUT 的指标、缺口集合、RTL／工具和分母
不变。六项原有缺陷仍在，四个 bos 行没有凭端口诊断计入正式覆盖。见
`results/coverage-ras-state-scenarios-refresh-audit.json`。审计初版错误地假定单
coverpoint 与 cross 都将 bin 定义放在同一字段；失败版本保留，修正版按
实际 schema 逐项检查完整 bin 集与次数，没有减少门禁或修改报告数据。
随后 2087-item 正常收集确认四份新正式报告字节不变，见
`results/coverage-ras-state-scenarios-collection-protection.json`。

5.026 基线中 AheadBTB 的 1506 个未命中行点只有 1264 个可映射到已有
bank/set/way counter 矩阵，另有 242 个来自 `.sv` helper；不能再写
“1264/1264 全部映射”。TAGE 的 132 个 `v_line` 也远少于生成 RTL 的
物理行数，因为一个覆盖点关联多个源码行，且普通双臂分支使用 `v_branch`；
旧基线的 48 个点缺口集中在写缓冲模块；新版点数与分支分布见上表，
不能将任一基线的点缺口直接等同于相同数量的不同功能。
旧的 2/2、5/5、6/6 等数字只表示
顶层 `.v` 子集，不能再当成整个 DUT 的行覆盖率。以下按时间记录的这些
旧数字均为历史 `.v`-only 口径，不能与上表直接比较。

在旧口径下，AheadBTB 的 1264 个未命中点对应 445 条静态 `.v` 行。
许多 set/bank/way 的同类语句被分别计数，不能把约半数行点未命中直接
解读成“缺失相同比例的功能点”。反过来，MainBTB 顶层 `.v` 的 2/2
也不能证明逻辑充分覆盖：先前没有针对页边界和 fetch 起点的预测过滤用例。
此前 `BPU-INT-031` 又补上“同 bank 读冲突 × 两笔不同历史反馈排队”的行为交叉，
完整回归由 206 增至 207 个执行功能点，但集成 BPU 仍为 6/6、独立 TAGE
仍为 5/5 RTL `v_line`；新增六个功能 bin 均命中。这是行覆盖已满仍遗漏
任务关联／背压组合需求的实证，不应以复制行点是否增加评价该用例。
`BPU-INT-032` 再用真实 FTQ 反馈分别让 ITTAGE 与 MainBTB 持有不同的
间接目标，并要求同一上下文的 S2 MainBTB 目标被 S3 ITTAGE 目标覆盖。
该场景四个功能 bin 全部命中，而集成 BPU 的 `v_line` 仍为 6/6、
ITTAGE 为 5/5；这补的是顶层目标来源优先级，不是新的 RTL 行点。
不再把同一分支的“RAS 与 ITTAGE 同时有效”列为可构造优先级场景：
`Bundles.scala` 定义 `isReturn` 为 `rasAction == Pop`，而 `needIttage`
要求 `isIndirect && !hasPop`。合法 return 天然不具备 ITTAGE 资格，
故 BPU S3 的两项选择条件对同一 first-taken 分支互斥。
`BPU-INT-033` 则补齐有意义的 RAS 集成交叉：独立 RAS 的多层 LIFO
通过不能证明 BPU 按两笔 return 的各自 MainBTB 结果逐笔产生 S3 修正。
新场景让两层 call／return 经过顶层预测路径，分别断言错误静态 S2 目标
和两个不同的 LIFO S3 目标；六格覆盖在断言后命中。它不以 RAS 2/2 或
集成 BPU 6/6 的 RTL 行覆盖代替逐笔目标选择证据。
`BPU-RAS-010` 是另一例：近溢出保护期间连续 push/pop 都不改动栈顶或完整
redirect metadata，回滚至较早调用帧后又可继续 push/pop；五个阶段的功能
bin 全部命中，而 RAS RTL 行/分支仍为 2/2、6/6。原有 RAS-006 只检查
被拒绝的 push 是否改变栈顶，不能代替 guard→rollback→恢复这条状态序列。
RAS 汇总 covergroup 原先还把已知缺陷下的 `disabled` 激励直接计为覆盖，
且该用例的其他采样没有逐项断言。现改为断言后只记录
`disabled_top_held`；完整 enable 契约在独立组中明确分为栈顶和元数据
两格，后者随 `BPU-RAS-008` strict XFAIL 保持未命中。故功能覆盖率下降
是修正证据口径，不是回归退化。
picker 包装层另有大量未调用 accessor，例如当前集成 BPU 包装层为
694/1041 个 `v_line` 点；不应为刷这部分分母构造无意义的 DUT 测试。

按 Scala 来源分类，AheadBTB 在旧 `.v` 子集剩余的 1264 个行点中，819 个是
`SaturateCounter.scala:41` 的正向加一 `else` arm，445 个是
`AheadBtb.scala:241` 对应的 `needDecrease` 选择 arm；后者的生成条件是
`_needIncrease_T & (~taken | _needDecrease_T)`，不是另一种源码功能。
旧 `.v` 子集剩余的 2050 个分支按首个 Scala 归因分别是饱和计数器减向判断
（1273）、replacement reset（509）和 way 比较（268）的复制；未见第四类
未分类的独立控制路径。`AheadBtb.scala:325` 的 multi-hit 清理已由
`BPU-ABTB-028` 命中。
当前生成 RTL 的 4 bank × 64 set × 4 way 计数器矩阵中，报告将全部
**1506 个缺口中的 1264 个**定位到具体格子；其余 **242 个**是新纳入的
`.sv` helper 行点，并未映射到该计数器矩阵。各 bank 的 counter 缺口如下：

| bank | 未命中正向臂 | 未命中减向选择臂 |
| ---: | ---: | ---: |
| 0 | 208 | 99 |
| 1 | 199 | 115 |
| 2 | 208 | 110 |
| 3 | 204 | 121 |

按物理格子去重，445 格同时缺两类行点，374 格仅缺正向臂，**0 格仅缺
减向臂**；故剩余的减向点没有构成独立于正向缺口之外的另一批物理格子。
这只是生成 RTL 覆盖结构的结论，不代表这些格子对应的行为全部等价。
`BPU-ABTB-034/035` 已证明此前确实遗漏过位置优先级与替换的交叉需求，
并在四个 victim way 上完成行为对照；`BPU-ABTB-036/037` 进一步发现同 PC
多路 not-taken、混合类型过滤与位置选择性 taken 的行为交叉，且关闭 bank 0/set 0
五个行点、命中 bank 3/set 0 两个条件 way 的四个行点。`BPU-ABTB-038`
继续交叉混合类型与替换，把该 cell 剩余两个 way 的四个行点也命中；
`BPU-ABTB-039` 又关闭 bank 3/set 1 四个 way 的正向更新臂；
`BPU-ABTB-041` 将历史选 bank 与四路恢复交叉，关闭 bank 0/1/2 的
set 1 共 20 个行点；`BPU-ABTB-042` 再交叉四个历史 bank 的满组替换、
位置抑制和逐 way 恢复，关闭 set 2 共 23 个行点。`BPU-ABTB-027`
随后扩到 set 31/32 的 bank 1/3，再关闭 25 个行点。`BPU-ABTB-033`
又把 set 63→0 回绕扩到 bank 1，关闭该 set 0 cell 的 7 个行点。
`BPU-ABTB-043` 让 set 3 四路在 set 2/4 双侧哨兵与四 bank 共存的状态下
逐路变化，关闭 set 3 的 27 个计数器行点；这些仍是复制实例而非 27 个功能点。
`BPU-ABTB-044` 将老化满组替换与 set 3/5 双侧哨兵再交叉，set 4
新命中 10 个减向选择行点；`BPU-ABTB-045` 随后让替换新项再次老化，
再逐路恢复新项与幸存旧项，补齐 set 4 的 16 个正向更新臂。
`BPU-ABTB-046` 用同一 PC 的 16 种折叠历史访问高物理 set 48–51 × 四 bank：
先给每格不同目标，再逐格老化和恢复，转换后回读全网格的路由、way、目标与
方向。固定种子完整回归新增 24 个 `v_line` 点（16 个正向、8 个减向）和
39 个分支；当时这 16 格只有 way 0 无计数器行点缺口。`BPU-ABTB-047`
接着让每格四个位置同时驻留，在一次负向反馈后按位置逐路恢复并回读全部
16 格；高 set 48–51 × 四 bank × 四 way 的计数器行点缺口现在全部关闭，
但这不代表这些 set 的所有替换／比较分支都已命中。
`BPU-ABTB-048` 再逐格训练第五个更后位置，确认恰有一个 victim 被替换、
三个幸存项按位置优先级转负，且其他 15 格完整保留。16 个路由的断言后
功能 bin 闭合，但固定种子全量 AheadBTB 行／分支计数不变；这项新的
状态交叉不应被误读为“没有增加 RTL 点所以没有验证价值”。
后续应先识别不同状态交叉，再从矩阵选代表格子，而不是逐个为复制点建功能 ID。
这些点跨 bank/set/way 复制，下一轮要按几何和状态交叉挑选代表样本，
但不能把每个实例当作独立功能点，也不能仅凭 100% 已定义 bin 宣称闭环。

## 已由缺口驱动补上的场景

### MainBTB depth-one 与清理/训练重叠

BPU-MBTB-025 用正常双 key 反馈和 24 笔同 bank 预测真实填充 depth 0/1。
静态只读 Bundle/@on Monitor 证明第二个 key 驻留 depth 1，独立预期检查
两阶段完整输入、请求、owner 写回与节拍；counter 初始化按 request way，
entry 按 retained owner，两种路由不混淆。32 组合、23 项手算纯检查、
六个普通 FAIL 负对照及正反异步完整 profile 回读通过，96 个 cross bin 闭合。
正式 MainBTB 974→1016/1056（96.21%），v_line 36→38/38、分支 418→426/442，
恰关闭 42 行；其他九 DUT 指标/缺口集合、源码/工具/原生分母不变。
1261 PASS、6 strict XFAIL、0 SKIP；331 raw、144 功能 JSON、145 功能组和
十份 LCOV/JSON/HTML 同源/时效审计见 `results/coverage-mbtb-depth-one-refresh-audit.json`。
1267-item 收集保持四报告字节不变。这不是完整 FTQ、任意饱和邻项、overflow 或 flush 模型。

025 阶段正式剩余 40 个双写复制行，不扣分母，也不划为不可达。独立清理诊断有
256 组合、192 PASS、64 个零 tag/位置零清理错 owner 的普通 Scoreboard FAIL，
四物理 bank 均复现；64 例真实同拍双写。排空后另一 set 的完整状态保持，
首次旧值来自 pending 写回，不是更新丢失。只合并通过诊断的数据可再命中
20 行至 1036/1056，但不计正式覆盖；剩余 20 行仍需审查。见
`results/coverage-mbtb-flush-key-expanded-readonly.json`；复现命令为
`python3 tests/mbtb/diagnostics/run_flush_key_probe.py`，默认不被 pytest 收集。
完整 FTQ pointer/epoch/resolve/redirect 资格仍未证明，未登记新 PASS/XFAIL，目标未完成。

### MainBTB dirty/clean 清理与训练双写（026 正式闭合映射行）

剩余 40 行不是不可达，而是四组双端口复制：`WriteBuffer.sv:443–452` 和
`467–476` 分别为 dirty 清理下 training depth 0/1；`482–491` 和 `508–517`
分别为 clean 清理下 depth 0/1。持续 S2 multi-hit 会重复清理并保持 dirty，
普通串行训练或只观察第一次清理 miss 不能覆盖 clean 路径。agent 在 clean
模式发单拍清理，暂停并排空后恢复 S2 并训练；用例不涉及边沿细节。

BPU-MBTB-026 用三种非联合零 key 交叉四 bank、双 depth 和 dirty/clean，
48 组合均真实出现同拍训练/flush 两端口写有效。独立预期冻结完整输入、
端口 payload/read 资格、所有 shadow 前后状态与四周期延迟，再比较两 set
完整 profile 的正反异步回读；144 个 cross bin 在比较后闭合。21 项纯检查
通过，八项负对照均为带 request/tick/status 的普通 ScoreboardMismatch。

正式完整回归 1283 PASS、6 strict XFAIL、0 SKIP；MainBTB 1016→1056/1056，
v_line 38/38、分支 426→434/442，恰关闭上述 40 行，无新行缺口。332 raw、
145 功能 JSON、146 组与十份 LCOV/JSON/HTML 同源/时效一致，其他九 DUT 的
指标和未命中行集合不变，工具/源码/原生分母未变。审计见
`results/coverage-mbtb-cleanup-overlap-refresh-audit.json`；1289-item 收集保护见
`results/coverage-mbtb-cleanup-overlap-collection-protection.json`。

剩余八个分支由实际父模块常量连接分类：清理 mask 的 bit 0 恒零，令七个
entry payload 的选择器 else arm 不可达；counter queue RAM 的读使能恒一，
令 read-disabled arm 不可达。四项源码变异负对照均检出，见
`results/coverage-mbtb-branch-unreachable.json`。保留原生 442 分支分母，不把
这项局部连接证明推广为全功能完成。

新隔离诊断还发现：更早启动训练的联合零 key 情况下，另一 set 的新项与
清理项竞争同一 shadow slot，清理优先导致更新丢失；fresh lookup 排空后仍
为旧值。这不是旧 delay 0/1 诊断中的 pending 首读，只在一个 bank 验证这一
新偏移。见 `results/coverage-mbtb-cleanup-routing-readonly.json`；其 raw 不进入
正式 manifest，未登记新 PASS/XFAIL，完整 FTQ 资格和整体目标仍未完成。

### SC threshold 的合法上下界诊断与正式场景

三个原生缺口 `dut/sc/ScDut.v:1686,1726,1806` 是 threshold way 0/1/3
更新候选超出 `[640,5040]` 后保留旧值。不能从 way 2 的旧行已命中反推
其他 way 的边界功能已验证，也不能把激励不足自动归为不可达。

独立 `tests/sc/diagnostics/threshold_probe.py` 只使用正常 ScAgent 预测和反馈，
每笔训练携带刚捕获的完整 metadata。Bundle／CycleMonitor 只读 VPI 阈值，
独立预期更新在反馈结果返回前计算，Scoreboard 比较各拍排空后的四-way 状态。
没有修改内部寄存器或伪造 `sumAboveThres`／`scPred`，也没有登记新的正式 PASS。

初次下界激励只到 810：PC 步长 0x10 始终保留 bank 位，有限 SRAM 行的
高置信度抑制了后续正确反馈。生成 RTL 明确使用 `addr[0]` 选 bank；ScAgent
目前直接保留 picker GuardedPc.addr 单位，不能把这个 bit 当成架构字节 bit 0。
改成两 bank 的 128 个实际 bank/bias-row 后，四-way 在第 490 笔合格反馈
同时到 640，再四笔减向候选都保持 640。新复位的真实 wrong-SC 反馈在第
3910 笔同时到 5040，继续四笔增向候选也保持。整个比较使用同一份可复现
脚本，两个阶段都已终态成功，而不是仅根据控制流推测。

严格合并该诊断阶段 manifest 的 31 份 SC 数据可复现正式 3142/3481；仅在临时
目录加入诊断 .dat 后为 3145/3481，恰关闭上述三行，分支 866/1038→869/1038。
剩余 336 行与已保留的局部矛盾证明一致，分母未剔除。四份正式 JSON／manifest／
HTML 的 SHA-256 逐字保持，该诊断阶段主表依然是 3142/3481，不能把诊断提升当作正式
pytest 功能完成。证据见 `results/coverage-sc-threshold-readonly.json`。

随后 BPU-SC-021/022 已正式覆盖这些需求。ScThresholdModel 在驱动前消费
真实 metadata，独立计算资格、位置 hash 和净增减；ScThresholdMonitor 用
静态 Bundle／CycleMonitor 的 @on 只读采样，ScAgent 封装短期订阅及直接
Scoreboard 比较，testcase 无 VPI/get-set/边沿。每笔反馈排空后比较完整
四-way 状态；连续四笔反馈另核对真实 beat 数和两 tick 的相邻节拍。

单分支到 640/5040 后各检查四次拒绝和向内恢复。每个 way 再用四个不同
条件位置到 642/5038，越界候选 638/5042 必须整体保留旧值，而不是写最近
边界；其他三-way 保持初值。另有四-way × 十种资格／聚合原因矩阵：
合格 wrong-SC、MBTB miss、非条件、provider invalid、关闭、真实高置信度
且与 TAGE 一致、净零／净正／净负、相邻反馈。每格要求资格及净贡献正确，
不能仅凭预测方向采样。两组边界各 24 个 cross bin，资格组 40 个，均闭合。

40 项纯模型测试和三项 VPI 能力错误测试通过，隔离 SC 全域为 77 PASS。
错误饱和、漏 way3、漏后续分支三负对照均抛出普通 ScoreboardMismatch，
保留事务、实际／预期、accepted/observed tick 和失败状态。完整 476 PASS
回归将正式 SC 更新为 3145/3481、分支 875/1038；其余九 DUT 及六项
strict XFAIL 不变。318 份 raw 文件均来自本次正式运行，无 probe/mutation；
十份 LCOV／JSON／HTML 一致且新鲜。336 个剩余原生行与局部矛盾赋值
完全一致，逐块守卫已复核，分母未剔除；这不证明 SC 全部功能或分支闭环。
见 `results/coverage-sc-threshold-refresh-audit.json` 和
`results/coverage-sc-threshold-negative-controls.json`。

### TAGE 后部 resolve 槽位诊断与正式矩阵

在 476 PASS 的正式基线中，TAGE 剩余 276 行中，88 行由局部矛盾证明分类；另 188 行是
WriteBuffer 164 行及顶层 24 行，尚不能默认其可达或不可达。四项既有
selector／provider 断言场景保持分支内容、顺序及真实 metadata，仅在临时
encoder 中把单／双有效分支放到 resolve slot 7／6、7。四项均 PASS；
临时合并为 4313/4587，分支 1332/1598，关闭 `TageDut.v:7818,7855`：
slot 7 的 provider useful 加向值和 alternate counter 加向值。这说明这两处
不能仅以旧零计数归为不可达，但不是对 alternate 写入结果或全 FTQ 调度的
完整证明。未改 RTL 或强制写内部状态，数据不在正式 manifest，该诊断阶段
主表仍为 4311/4587。证据见
`results/coverage-tage-late-resolve-readonly.json`。

随后 BPU-TAGE-027/028 进入正式 pytest。provider 矩阵交叉八 resolve slot、
双向、四深度和五个阶段，检查弱初值到饱和及饱和保持的精确 taken/useful
counter、provider 身份和全部 protected resident。资格矩阵交叉八槽与七原因：
MBTB miss、direct、indirect、inactive、disabled，以及与 unmatched／非条件邻项
同拍的合格更新。期待在驱动前独立冻结；被动 Bundle/CycleMonitor 比较真实
输入的槽位、类型、结果、base counter 和原样 metadata，不能复用 encoder。
resolve index 与扁平预测 metadata index 独立。输出继续由异步 Scoreboard
流水线回读，检查接受间距和完成延迟；测试不暴露边沿、VPI 或 asyncio.gather。
320+56 个 cross bin 均在检查后闭合，21 项纯语义测试通过。漏 slot7、压缩槽位、
交换 metadata、错 provider 参考四负对照均为带事务／周期／差异／状态的普通
ScoreboardMismatch，而非超时或 setup/teardown 错误。

完整 499 PASS 回归关闭 20 个顶层原生行，4311/4587→4331/4587，
分支 1319/1598→1411/1598，`v_line` 仍为 95/132。未改 RTL、编译器、
处理器或 4587 行分母，其他九 DUT 与六项 XFAIL 不变；320 份本次 raw、
十份 LCOV／JSON／HTML 的时效及一致性已审计。88 个局部矛盾赋值守卫
及真值表仍成立，不扣分母。该 sparse 阶段剩余 WriteBuffer 252 行（其中 164 未分类）
和顶层四行，总计 256 行、168 未分类。alternate counter 算术行命中不能替代
对实际写回对象和值的精确断言，也不证明完整 FTQ 程序轨迹可达。证据见
`results/coverage-tage-sparse-refresh-audit.json` 与
`results/coverage-tage-sparse-negative-controls.json`。实际全仓 505-item
collect-only 保持四份正式报告字节一致，见
`results/coverage-tage-sparse-collection-protection.json`。

再对顶层剩余 `TageDut.v:777,779,852,854` 做只读诊断：正常分配并保护前项，
让 table2 饱和后一次反向结果在 table3 分配新 provider，从而建立真实 table2
alternate；把同一状态路由到四个 MainBTB 预测槽，双向 × 两个 baseConf 共
16 项状态比较通过。被动内部观测验证槽 1/2 确实选择 table2，以及 alternate
counter 为 1/6。临时合并恰关闭四个 mux 行，4331→4335，分母不变，未新增缺口。
该诊断原始数据不在正式 manifest，当时主表仍为 4331/4587；证明这四行可达，
不能再默认为不可达。随后正式化结果见下段，诊断历史证据仍为
`results/coverage-tage-alternate-slots-readonly.json`。
可重复的诊断入口为 `tests/tage/diagnostics/alternate_slots_probe.py`，例如：

```sh
PYTHONPATH=.:/home/xyl/xreactor/src:/usr/local/share/picker/python \
  python3 tests/tage/diagnostics/alternate_slots_probe.py \
  --report /tmp/tage-alternate-slot-probe.json
```

该脚本将原始 dat 输出为同目录 `probe-` 前缀文件，并验证四份正式报告的
字节摘要不变；它不是 pytest item，不能自动把探测结果提升为正式 PASS。

随后 BPU-TAGE-029/030 正式化这组缺口。正常分配准备 table2 alternate 和
table3 provider，独立配对模型只用真实分配的 way 身份作初始定位，预期
counter、useful、selector 演进不由 actual 回灌。原 prediction monitor 的
静态 Bundle 增加只读 table hit mask、table counter/useful 和 selected alternate，
在同一输出事件解码；不另起错拍的关联任务，也不在 testcase 暴露 VPI／边沿。
十四个阶段覆盖选中 alternate 的更新、provider-only、饱和保持、弱区、selector
再进入、跨方向以及 direct／MBTB miss／disable 门控；双向 × 四预测槽 ×
两 baseConf × 十四阶段共 224 格。另用相反方向 resident 和配对目标混合
于槽 0 与后部槽 1/2/3，双向 × 三槽 × 正反顺序共 12 格；先提交十二笔
再 drain，核对精确 counter/useful/table-way 身份、完整 metadata 和节拍。
全部 236 个 cross bin 均在完整断言后采样。

27 项纯模型／能力／任务清理测试通过，缺少或歧义内部信号明确报错、不 skip。
保持错误 alternate、交换 way、上一事件 native 状态、漏 slot7 四个隔离
负对照均被普通 ScoreboardMismatch 检出，无额外 teardown、超时或任务
异常遗漏。辅助 base 驱动任务在关闭时全部回收，仅抑制 Scoreboard 已拥有并
报告的同一 failure；独立辅助异常仍抛出。退出 state 观测恢复原基本 binding。
完整回归为 528 PASS、6 原有 strict XFAIL、0 SKIP。正式 322 份 raw 使 TAGE
4331→4335/4587、分支 1411→1421/1598，顶层 3021/3021；恰关闭
`TageDut.v:777,779,852,854`，v_line 仍 95/132，其他九 DUT、分母及来源不变。
十份 LCOV／JSON／HTML 一致、时间新鲜，四个原未闭合功能组不变，局部证明
守卫复核通过。最新审计为 `results/coverage-tage-alternate-refresh-audit.json`，
负对照为 `results/coverage-tage-alternate-negative-controls.json`；全仓 534-item
collect-only 逐字保持见 `results/coverage-tage-alternate-collection-protection.json`。
剩余 252 行均为 WriteBuffer，88 行局部矛盾、164 行未分类，原始分母不扣除。
配对模型不是完整 allocation／hash／aging／陈旧 metadata 或 FTQ 参考，顶层
满行也不证明所有 selector、历史及其他功能组合闭环。

随后单独审查 `WriteBuffer.sv:1535-1637` 的四 entry × dirty/clean key-copy：
此前 88 行只分类了 counter 复制块，没有自动扩张到独立生成的 set/valid/tag
块。每块重新核对 `if (hit && selected)` 优先级、后续 `else if (hit)`、
clean 条件、目标 row1／entry 身份、源 port0 和完整块边界。16 个二态取值
对 dirty/clean 条件均无解；删除优先级前提后必须出现 witness。八块共
24 个原生未覆盖赋值与旧集合无重叠，累计分类 112 行、剩余 140 行未分类。
改变优先级、弱化 clean 条件、错写目标 row、错用源 port 四个仅内存源码
负对照均被拒绝，实际 RTL 及四份正式报告字节不变。
证据为 `results/coverage-tage-key-copy-unreachable.json`，重复入口为
`python3 tests/tage/diagnostics/key_copy_audit.py --report /tmp/tage-key-copy-audit.json`。
这只是有界局部证明，不是新增功能点 PASS；原始 252 行缺口及 94.51% 覆盖率
保持不变，也不能把其余 140 行自动认定可达或不可达。

继续检查一个真实 provider 更新与一个新 tag allocation 的同笔反馈。最初让
既有 counter=0、actual=NT，虽然最终 payload 保持且新 tag 成功分配，临时合并
没有增量；`Tage.scala:421` 的 `!provider.takenCtr.shouldHold(actualTaken)` 会
直接省掉这个饱和 counter 写端口，不能把保持正确称为双端口并发成功。
随后正常训练把目标准备为最高表 way0 的 counter=1/useful=3，仅 way1
useful=0 可被替换。较早目标实际 NT、较晚冷条目实际 taken 是合法双分支
反馈；被动 monitor 核对完整同笔输入，目标必须 1→0，新项必须 table3/way1
counter=4/useful=0、旧 victim 消失，其他六项的完整状态保持。
这项隔离诊断通过，临时合并 4335→4339/4587，关闭
`WriteBuffer.sv:885,886,887,890`，v_line 95→96/132、分支 1421→1423/1598，
局部分类集合不变、无新增缺口。四份正式报告字节不变，其 probe raw 不计
正式 manifest，当时主表仍为 4335/4587；不能把该诊断提升当作正式 PASS。
证据为 `results/coverage-tage-mixed-hit-miss-readonly.json`，可重复入口为
`python3 tests/tage/diagnostics/mixed_hit_miss_probe.py --report /tmp/tage-mixed-hit-miss.json`。
随后 BPU-TAGE-031/032 正式化四上下文 × 双最高表 way × counter 1/2 的同拍
双写矩阵（48 cross bins），以及饱和／无 MainBTB 命中／无效 slot／全局关闭
的单写或零写矩阵（96 cross bins）。独立模型在提交前冻结全 bank 两端口
valid、set、tag、counter、entry-valid、taken 及四周期延迟；被动只读 Bundle/
CycleMonitor 必须在同一个事件看到两个有效写入，不能用两拍单写代替。
输入语义与真实 metadata 由既有 feedback monitor 核对，旧 victim 消失、
新分配与六邻项完整保持再经正反顺序重叠 prediction Scoreboard 回读。
正常反馈准备和恢复状态，不写内部寄存器；23 项纯模型／能力／清理测试通过。
漏目标、漏后槽、观察端将双写改成单写、错 set 参考四负对照均为带状态的
普通 ScoreboardMismatch，无额外 teardown 或悬空任务错误。

完整 553 PASS、6 strict XFAIL、0 SKIP 回归确认 4335→4341/4587，恰关闭
`WriteBuffer.sv:867,868,885,886,887,890`；v_line 95→96/132、分支 1421→1424/1598。
没有新行缺口、分母不变；其余九 DUT、六项 XFAIL 与 RTL/工具来源均不变。
324 份当次 raw、137 份功能 JSON、138 组功能覆盖及十份 LCOV/HTML/JSON
时效与一致性审计通过；559-item collect-only 保留四份正式报告字节不变。
证据见 `results/coverage-tage-mixed-writes-refresh-audit.json` 和
`results/coverage-tage-mixed-writes-collection-protection.json`。剩余 246 个
原生行中仍保留 112 个局部矛盾赋值、134 个未分类行；矩阵只针对已准备的
最高表、零折叠历史，不宣称所有 shadow 槽位、完整 allocator 或 FTQ 轨迹。

### 两笔相邻反馈的饱和转发：先导诊断与正式对照矩阵

剩余 `WriteBuffer.sv:888` 是混合 hit/allocation 分支中的计数器饱和保持，
仅用新鲜饱和 metadata 不会触达：上层 `shouldHold` 会省掉 provider 写入。
因此正常预测两次捕获相同的 counter=1、cold newcomer metadata，再按相邻
反馈提交两个不同 newcomer。两笔真实输入相隔一周期、各在四周期后写入；
写端口都请求目标 counter=0，buffer 从已有命中状态更新，第二次须在 0 保持。
完整输入、两事件双端口 payload、target/useful、最终 newcomer、两个旧 victim
消失及六邻项保持都经独立参考／流水线回读检查，隔离诊断通过。
与冻结的 4341 行基线临时合并为 4342/4587，恰关闭该行、增加一个 branch hit，
v_line 不变；四份正式报告字节不变，其 raw 不进正式 manifest。
证据见 `results/coverage-tage-overlapped-saturation-readonly.json`。
这项先导诊断只覆盖一个 bank/way、减向相邻反馈，当时尚需矩阵／对照／负对照；
其 raw 始终不计主表，也不宣称完整 FTQ 时序可达。

随后 BPU-TAGE-033 补上四上下文 × 双最高表 way × 初始 counter 1/2 ×
相邻／间隔反馈的对照矩阵，96 个阶段 cross bin 均在完整检查后闭合。
两次预测均在反馈前捕获；cold mispredict 强制读 SRAM，因此间隔反馈要
使用当前读值：第一次已到 0 时第二次 provider 写入应省掉，初始 2 时
第二次请求应为 0，不能把捕获 metadata 的旧 counter 直接当写请求参考。
相邻反馈则两次读取旧值，依赖 buffer resident 转发，两次写后目标都必须为 0。
恢复阶段也与最初冻结的六邻项 baseline 比较，不采用可能受损的新 baseline。
26 项纯模型／输入范围检查及硬件矩阵合计 27 PASS；漏第二分配、错误串行化、
错最终 counter、漏第二写观察四负对照均普通 ScoreboardMismatch，无额外清理错误。
隔离合并为 4344/4587，关闭 `WriteBuffer.sv:844,845,888`，分支 1424→1426/1598、
v_line 不变；证据见 `results/coverage-progress-tage-overlapped-saturation.json` 和
`results/coverage-tage-overlapped-saturation-negative-controls.json`。
随后完整回归为 580 PASS、6 strict XFAIL、0 SKIP，确认同样三行增量，
其余九 DUT、六项 XFAIL、RTL/工具来源及分母不变。325 份当次 raw、
138 份功能 JSON、139 个 covergroup 与十份原生 LCOV/JSON/HTML 时效和
一致性审计通过；586-item collect-only 保留四份当前正式报告字节不变。
最新审计见 `results/coverage-tage-overlapped-saturation-refresh-audit.json` 与
`results/coverage-tage-overlapped-saturation-collection-protection.json`。
剩余 243 行中 112 行仍局部分类、131 行未分类；不扣原始分母，其他
shadow 槽位／容量、完整 allocator、FTQ 时序与其他预测器缺口仍须审查。

### MainBTB counter 写回在持续预测读下排队（诊断到正式矩阵）

诊断时 MainBTB 216 个原生行缺口分为 entry WriteBuffer 152、ReplacerState 60、
counter Queue 3、queue RAM 1。Replacer 的 predictWrite 在上层恒为无效，
不能把此模块的通用“双端口优先级”直接当作本 DUT 的有效功能场景。
而 queue 的三条零计数是实际 `do_enq`、`do_deq` 和 `maybe_full` 更新，
不是常量 flush；RAM 零计数是对应的写入赋值。原 counter 测试训练后等待
写回，再单独查询，flow queue 可以全程直通，未证明 pending 更新的保留。
`MainBtbInternalBank.scala:157-160` 明确让 SRAM 预测读优先、阻止 counter deq。

隔离诊断正常分配同 bank 的两个不同 set 条件项与第三 set 哨兵，全部 counter=2。
先提交 24 笔哨兵预测、再用已有训练 driver 相邻提交两个目标的真实反馈，
让预测与训练重叠而不在测试里拼任务集合。两个目标在预测排空后 counter
都为 1，哨兵仍为 2；三个完整 entry/metadata snapshot、24 笔哨兵结果、
接受间距与完成延迟均检查。仅两个 pending key，不要求超过队列容量。
该诊断通过；旧 26 份正式 raw 复现 840/1056，加诊断临时为 846/1056：
关闭 `Queue2_MainBtbCounterSramWriteReq.sv:81,83,85`、`ram_2x12.sv:74` 及
`ReplacerState.sv:258,266`。v_line 仍 29/38，分支 317→323/442，没有新缺口。
四份正式报告字节不变，probe raw 不进正式 manifest；当时主表仍 840/1056。
证据见 `results/coverage-mbtb-counter-pending-readonly.json`。这次单 bank 诊断
还缺独立输入／活动 monitor、几何／方向／对照矩阵及负对照，不能直接登记 PASS。

后续 `BPU-MBTB-020` 正式交叉两个 align bank、两个 internal bank、两个目标 way、
双向更新、同 bank 阻塞／跨 bank 直通，以及 set 1/2、31/32 两个索引上下文，
共 64 个硬件组合。每组正常分配四个 PC 的两路 resident：两个 counter=2
目标、一个同 bank 和一个跨 bank 读哨兵。真实 metadata 与独立输入／活动预期
均在驱动之前冻结，不调用 encoder 生成预期。输入 CycleMonitor 检查完整八槽
payload、PC、metadata、ready 和相邻接受间距；四 bank 的静态只读 Bundle/Monitor
检查精确 set/way-mask/counter 请求、写回和占用。阻塞时实际入队两项、峰值 2，
读结束后有序排空；直通对照实际入队为零、峰值为零。24 笔并行预测及正反顺序
全 resident 回读由既有异步 prediction Scoreboard 配对，接受间距一周期、完成
延迟两周期；相反 way、其他 set 和两个哨兵的完整 entry/metadata 均须保持。
192 个 phase cross bin 在检查之后命中。同步 pulse 源不发布 XTransfer，故输入
和队列活动用核心 Scoreboard 直接比较，不冒充异步驱动映射；边沿/VPI 封在组件内。

51 项纯模型／能力／清理检查和硬件矩阵合计 52 个新增 PASS；漏第二反馈、
训练串行化到读结束后、漏第二写回观察、错误最终 counter 四负对照均触发
带 request/status 的普通 ScoreboardMismatch，无超时或额外 teardown 错误。
完整回归 632 PASS、6 strict XFAIL、0 SKIP，MainBTB 840→851/1056：关闭上述
queue/RAM 四行和 `ReplacerState.sv:256,258,260,264,266,268,380`，v_line 仍
29/38，分支 317→332/442。其他九 DUT、源码/工具来源、分母和六项 XFAIL 不变。
326 份本次 raw、139 功能 JSON、140 组及十份 LCOV/JSON/HTML 一致，638-item
收集保护通过。证据见 `results/coverage-mbtb-counter-pending-refresh-audit.json`、
`results/coverage-mbtb-counter-pending-negative-controls.json` 和
`results/coverage-mbtb-counter-pending-collection-protection.json`。
剩余 205 行为 entry WriteBuffer 152、ReplacerState 53；不由此宣称 overflow、
同 set 覆写、entry-buffer 参考或完整 FTQ 验证。

### MainBTB pending entry 连续目标改写（诊断及正式覆盖）

counter queue 和 entry WriteBuffer 是独立路径。`MainBtbAlignBank.scala:224-232`
允许命中的间接跳转在误预测时重写目标，entry SRAM 也让预测读优先。现有串行
target 更新不能证明 pending 时再次改写同一 key 会保留最新目标，或排空和重写
同拍时不会清掉新 dirty。隔离探针覆盖四 bank × 两 way × 阻塞/直通 16 个组合，
两笔真实 hit metadata 在反馈前独立捕获。公开输入和所有 bank/way entry 写端口
的静态只读 Bundle/Monitor 比较两次不同目标的请求：阻塞时只写回最新目标，
直通则两笔均写回。全部组合的请求延迟两周期、直通写回延迟三周期，阻塞写回
在最后一次读之后一周期；24 笔哨兵预测及正反顺序完整回读检查所有邻项保持。
16 组检查通过。只在冻结的 counter 矩阵数据外追加此探针，临时 851→857/1056，
关闭 `WriteBuffer.sv:581,582,626,627,681,682`，v_line 29→31/38、分支 332→348/442。
四份正式报告逐字保持，probe raw 不进正式 manifest；当时主表仍为 851/1056。
证据见 `results/coverage-mbtb-entry-retarget-readonly.json`。当时尚无正式功能 bin、
负对照及完整回归，未登记 PASS；也不证明跨 way 陈旧 metadata、满 dirty miss
覆写、属性/flush 碰撞或其他剩余 WriteBuffer 路径。

随后 BPU-MBTB-021 在此基础上加入低/高 set 上下文及三种 carry 变化：
Fit→Overflow、Overflow→Underflow、Underflow→Fit，与四 bank、双 way 和
阻塞/直通交叉为 96 组合。两笔真实 counter-2 hit metadata 在反馈前捕获；
独立参考冻结完整输入、tag/position/attribute/target carry/lower、写回次序及节拍。
目标只允许相对 PC 的同区间或相邻区间，不以两笔目标间的差值代替 carry。
请求相对公开反馈延迟两周期；阻塞只在最后哨兵读后一周期写回最新项，
直通两笔均各自三周期写回，第二次请求与第一次 drain 同拍。静态只读 Bundle
和被动 Monitor 覆盖所有 bank/way；预测回读仍用既有异步 Scoreboard。
全目标、counter/metadata、相反 way 与三个哨兵/邻 set 完整回读后采样，
288 个 phase cross bin 全命中。93 项纯检查与硬件矩阵共 94 个新增 PASS；
漏第二反馈、训练串行化、错 carry、漏写回观测、错误最终目标五负对照均
触发带身份/tick/status 的普通 ScoreboardMismatch，无超时或清理错误。
完整回归 726 PASS、6 strict XFAIL、0 SKIP，正式 851→857/1056（81.16%），
恰关闭上述六行；v_line 29→31/38、分支 332→348/442，其他九 DUT 不变。
327 份本次 raw、140 功能 JSON、141 组与十份 LCOV/JSON/HTML 时效/一致性通过，
732-item collect-only 保持正式报告。证据见
`results/coverage-mbtb-entry-retarget-refresh-audit.json`、
`results/coverage-mbtb-entry-retarget-negative-controls.json` 和
`results/coverage-mbtb-entry-retarget-collection-protection.json`。
剩余 199 行为 WriteBuffer 146、ReplacerState 53；本次关闭的条件行不等于
其内部跨 way 复制赋值已执行，不宣称 overflow/flush/完整 FTQ 验证。

### MainBTB 两个不同 key 的 pending entry（诊断及正式覆盖）

同 key 覆写只占一个缓冲槽，不能证明第二个槽可实际保留不同 key。
继续以正常分配的两个不同 set 间接分支、真实 counter-2 hit metadata，在
24 笔同 bank 哨兵读期间相邻改写两项目标。四 bank、双 way、低/高 set 及
阻塞/直通共 32 组合，独立完整输入/端口/节拍和正反顺序全状态回读全部通过。
阻塞时保留两 key 并在读结束后一、二周期依次写回；跨 bank 对照正常直通。
在已验证的 857 行数据外临时追加该探针，857→877/1056，关闭第二槽的
`WriteBuffer.sv:549–557,609,614–623` 共 20 行，v_line 31→32/38、分支
348→351/442，没有新缺口。证据见 `results/coverage-mbtb-entry-two-keys-readonly.json`。
该探针 raw 不在正式 manifest，当时未登记功能 PASS，主表仍为 857/1056。

随后 BPU-MBTB-022 将其扩为 192 个上下文/align/bank/way/mode/输入顺序/
目标 region 配对组合。正常分配使用不同 set 和不同 tag，两个 counter-2
间接 hit 的真实 metadata 在反馈前捕获。独立有界模型分别冻结两 key 的
完整 payload 和状态：目标按 PC 归属而非提交顺序排列，三个 region 配对
不是同 key 的时间转换；即使两个目标相同，不同 key 也不能合并写回。
全八端口请求/写回、相邻反馈、24 笔哨兵读的间距和完成延迟均直接比较，
阻塞解除后一、二周期写回两 key，直通各自相对反馈三周期写回。
完整 resident/metadata 正反顺序流水线回读检查 counter、相反 way 和两个
哨兵保持，576 个 phase cross bin 在断言后闭合。145 项纯检查及硬件矩阵
共 146 个新增 PASS；漏第二反馈、强制串行训练、错 carry、漏第二写回、
写回错 key 和错误最终目标六负对照均触发带上下文的普通 ScoreboardMismatch，
无超时、teardown 或未取回 task 错误。
完整回归 872 PASS、6 strict XFAIL、0 SKIP，正式 857→877/1056（83.05%），
恰关闭上述 20 行，无新缺口，v_line 31→32/38、分支 348→351/442。
其他九 DUT 的指标和未覆盖集合、源码/编译器/处理器和分母不变。
328 份本次 raw、141 功能 JSON、142 组与十份 LCOV/JSON/HTML 时效/一致性
通过；878-item collect-only 保留四份报告字节一致。完整证据见
`results/coverage-mbtb-entry-keys-refresh-audit.json`、
`results/coverage-mbtb-entry-keys-negative-controls.json` 和
`results/coverage-mbtb-entry-keys-collection-protection.json`。
剩余 179 行为 WriteBuffer 126、ReplacerState 53；不要求满 miss 时无损，
也不由两个不同 key 场景推断跨 way shadow、flush 或完整 FTQ 正确。

### MainBTB 跨 way shadow（诊断及有界正式覆盖）

`MainBtbAlignBank.scala:279-281` 的真实正确 taken 反馈可触碰 LRU 而不重写
entry。保存分配前的真实 cold metadata、不跨 reset 重放，再结合这种触碰，
能使请求选中与 shadow 持有者不同的 way。32 组探针覆盖四 bank、双 owner way、
clean-first/pending-second 两种交接及阻塞/直通；请求 way 与 SRAM 写回 owner
way 分别比较，不假定二者相同。初始 counter-2 居民的全部公开输入、端口/
时序与完整目标/meta/邻项正反回读通过。独立在 877 行基线上追加 raw，临时为 921/1056，
关闭 `WriteBuffer.sv:430–440,494–504,583–592,595,597–606,640` 共 44 行，
v_line 32→36/38、分支 351→365/442。证据见
`results/coverage-mbtb-crossway-shadow-readonly.json`。

随后 BPU-MBTB-023 将此局部契约扩为 192 个上下文/align/bank/owner/
clean-first-pending-second/mode/carry 组合。独立两-way LRU 消费预先指定的
正确 taken touch 和两次分配，选择请求 victim；写回 payload 的物理 owner
由 retained key 决定，不随请求 way 改写。活动请求端口的 read_valid 与全
缓冲占用不同：pending-second 的第二个请求可在非 owner 端口看见 read_valid=0，
即使另一端口仍有 dirty 数据。三种 carry 转换、完整全八端口/公开反馈、
两周期请求/三周期 flow 写回、24 笔哨兵读、正反顺序完整 resident/meta 回读
均比较独立冻结的预期。576 个 phase/status cross bin 在断言后闭合。
251 项纯检查及硬件矩阵共 252 个新增 PASS；提炼后的正常 pair 分配保持
原有 318 项 MainBTB 测试，隔离全区 570 PASS。漏正确 touch、误用 fresh
metadata、将写回误归请求 way、漏写回、错 carry 和错误最终目标六负对照
均普通失败，有 identity/tick/status，无超时或额外清理错误。
完整回归 1124 PASS、6 strict XFAIL、0 SKIP，正式 877→921/1056（87.22%），
恰关闭上述 44 行，v_line 32→36/38、分支 351→365/442，无新缺口。
其他九 DUT 的指标和未覆盖集合、源码/工具/分母不变；329 份本次 raw、
142 功能 JSON、143 组与十份 LCOV/JSON/HTML 时效/一致性通过，1130-item
collect-only 保留四份报告。证据见 `results/coverage-mbtb-shadow-refresh-audit.json`、
`results/coverage-mbtb-shadow-negative-controls.json` 与
`results/coverage-mbtb-shadow-collection-protection.json`。
该 PASS 只承诺初始 counter-2 居民，不声称任意邻项或完整 FTQ 安全。

### MainBTB 替换索引（从隔离扫描到正常 conditional 反馈的正式矩阵）

另一个探针核实当前 RTL `MainBtbAlignBank.sv:702,708` 的替换索引为 PC[9:4]，
不是 entry SRAM 的 PC[10:5]。64 个索引 × 两 align 共 128 组正常分配，
要求初始分配落 way 1/0，第三项替换 way 1；两个重叠 prediction 比较完整
状态和 metadata，保持相反 way/未活动 align。独立在同一 877 行基线上追加
raw，临时为 930/1056、分支 404/442，恰关闭全部 53 个剩余 ReplacerState 行，
不增加 WriteBuffer 命中，说明这些索引行可达。证据见
`results/coverage-mbtb-replacer-index-readonly.json`。此探针逐格复位，尚不证明
跨索引邻项隔离或 SRAM set 32-63 的替换索引别名交互。

这份索引 raw 仍不进正式 manifest、未登记功能 PASS；它的 930/1056 是
旧 877 行基线上的独立候选，不是当前正式 1056/1056。它已由以下新测试
替代，而不是把原探针 raw 直接纳入正式 manifest。

BPU-MBTB-024 使用 `mbtb_replacement_model.MbtbReplacementState`，每个
alignment/index 单独维护两路 LRU，只由预期分配和真实 taken hit 推进，
不从实际 DUT victim 回填。先正常分配目标、set+32 alias、相邻索引及另一
alignment 的两个 conditional 居民，在同一次复位后测试共享和隔离。
64 索引 × 两 align × 两 SRAM set 高位 × taken-way0/taken-way1/NT/read-only
共 1024 组合。正确 taken counter 2→3 且 touch；实际 NT 是 mispredict，
counter 2→1 但不 touch；读取不 touch；新分配 reset counter 到 2。目标与
alias 的后续分配必须共享 LRU，邻接索引/另一 alignment 的 victim 不能受影响。
每一步都比较完整 target/position/attribute/direction/counter/metadata，
四笔异步 Scoreboard 预测保持两 tick 接受间隔、四 tick 完成延迟，末尾反向
回读再验证；6144 个 phase cross bin 在比较后采样。

112 项纯检查及硬件矩阵共 113 个新增 PASS。漏 taken touch、把 NT 强制
为 taken、错误 victim/target、邻项 counter、拆开 alias state、合并邻接
state 七个负对照均带 request/tick/status 普通 FAIL，没有超时或清理错误。
源码资格检查发现后端过滤正确 direct resolve，因此主动停止原 direct
试验刷新，改用上述 conditional 反馈后重新完整运行；中断证据单独保留。
完整回归 1237 PASS、6 strict XFAIL、0 SKIP；251 点执行、245 PASS。
正式 921→974/1056（92.23%）、分支 365→418/442、v_line 仍 36/38，
恰关闭旧基线全部 53 个 ReplacerState 行，只有 82 个 WriteBuffer 行仍缺。
源码、处理器、分母、其他九 DUT 指标/缺口集合及六项 XFAIL 不变；330 份
本次 raw、143 功能 JSON、144 组和十份 LCOV/JSON/HTML 时效/一致性通过。
证据见 `results/coverage-mbtb-replacement-refresh-audit.json`、
`results/coverage-mbtb-replacement-negative-controls.json` 与
`results/coverage-mbtb-replacement-collection-protection.json`。

### MainBTB 非弱条件邻项的 counter 副作用（未计正式分的异常诊断）

初始 counter 都为 2 会掩盖 wrong-way reset。另一 tag 的条件邻项先正常
饱和到 3，再捕获三个真实 all-miss A0/A1/A2 预测，随后按相同次序反馈：
A0 正常分配 retained owner，A1/A2 相邻改写目标，没有在 A0 后插入其他
训练或 reset。四 bank × 双 owner × 阻塞/直通共 16 组，native entry 的
请求/owner/完整目标/节拍全部正确，但邻项 counter 3→2，只有 A/B 两次
公开 lookup 的 `meta_entries[align][1-owner].counter_value` 不同；只检查
taken 会漏掉这个变化。所有失败都是带上下文的普通 ScoreboardMismatch，
无超时或清理错误。此前同 tag 邻项的八组诊断也观察到 3→2，但有序不同
tag 对照进一步排除了必须乱序反馈的前提。
源码 `MainBtbAlignBank.scala:264-267` 以 cold-feedback victim 的
`t1_entryWayMask` 重置 counter；`WriteBuffer.scala:209-212` 的 entry key 命中
却更新原 shadow owner，两种身份没有在 counter 路径重新对齐。证据见
`results/coverage-mbtb-shadow-counter-side-effect-readonly.json`。
模块内捕获/反馈顺序已核对，不等于完整 FTQ 的 epoch、redirect/flush 和
训练资格已证明；失败 raw 不进正式 manifest，未登记 PASS 或 blanket XFAIL。
不能由 023 的弱 counter PASS 推断此功能也已通过，后续必须审查前提并形成
精确的失败回归，而不是用覆盖率高低判断正误。

追加资格源码审查确认：S3 metadata 按 FTQ pointer 保存，MainBTB 从
ResolveQueue/trainCache 的 resolve 路径训练，不是等待 commit；后端正确
direct resolve 被过滤（不把 IFU 路径一概视作过滤），年轻训练受到当前/延迟
redirect 保护。三个在 A0 分配前捕获的 cold snapshot，即使随后反馈按序，
也不能仅凭顺序证明三次 mispredict 都能通过真实过滤。还需记录 pointer、
epoch、redirect 和 train.fire；“重定向后、迟到的分配训练前捕获新 cold”
只是后续候选，不是已证明见证。见 `results/coverage-mbtb-ftq-qualification-source-readonly.json`。

### MainBTB 双写复制路径发现（拒绝不充分的不可达分类）

024 阶段剩余 82 个 WriteBuffer 行；025 关闭 42 个 depth-one 跨 owner 行后，
该阶段正式剩余 40 行，全部为以下双写复制赋值：
`WriteBuffer.sv:443–452,467–476,482–491,508–517` 共 40 个复制赋值需要
`_GEN_46` 和 `_GEN_24/_GEN_25`，故要求两个 write valid 同时成立。
训练 entry wayMask 的 one-hot 不能传播成整个缓冲 one-hot：
`MainBtbInternalBank.scala:170-173` 将 training 与非冲突 flush 的 valid 做 OR
再寄存。训练 way 0 与另一 set 的 flush way 1 就能同时使两路接口 valid。
上述源码反证本身只否定“按 one-hot 排除”的推理，不证明全部内部赋值可达。证据见
`results/coverage-mbtb-flush-overlap-source-readonly.json`；保留全部原生缺口和
分母。后续 256 个真实清理/训练诊断已经捕获 64 例同拍双写；192 例完整
状态通过的数据额外命中其中 20 行，另 20 行仍需审查。全部诊断保持隔离，
不计正式功能 PASS 或行增量，见 `results/coverage-mbtb-flush-key-expanded-readonly.json`。

`MainBtbEntry.valid` 由 `!attribute.isNone` 决定，并不排除 tag=0；缓冲
key 是 tag/position 与 set，而 flush payload 全零。因而正常 tag=0、
position=0 key 与 flush key 的边界不能被忽略。候选 PC `0x40000020`
映射 tag=0/set=1/bank=0，同 set、zero-tag 的训练又会触发 flush conflict
门控。源码证据见 `results/coverage-mbtb-zero-tag-source-readonly.json`。
现在四 bank 的 64 个零 key 模块诊断均观察到请求 upper way 却清掉 retained
lower owner、新目标消失而旧目标保留的普通 Scoreboard FAIL；排空后其他
set 的完整状态仍保持。不将该模块见证推广成完整 FTQ pointer/epoch/
resolve/redirect 可达性证明，不新增正式 PASS/XFAIL 或不可达分类，不扣分母。

### MicroRAS 中性修正与主 RAS 返回地址

两个旧源码行缺口 `dut/uras/UrasDut.v:460,477` 分别是中性 S3 override
直接选主 RAS 地址，以及中性 S2 override 在无较老 S3 push/pop 时回退
主 RAS／redirectDelay1 的路径。原 S2/S3 override 用例只单独检查 push/pop，
并未证明“不做 RAS 操作”的有效修正仍能取消年轻的错误 call。

`BPU-URAS-015` 交叉两个 stage 与五个 phase：静态主栈回退、取消 pending
call、redirect 优先、阶段专属恢复、撤回修正后保持。使用不同的新主 RAS
地址而不是之前的 top，并同时送入会冲突的较年轻 call；逐次断言完整
`UrasResult`，而不是仅检查 usable。redirect 当前拍只要求 invalid，不为
不具备意义的地址添加通用假设；之后中性 S2 必须保留一拍 invalid/zero，
中性 S3 按明确的源码路径直接返回主 RAS。十个 cross bin 均在断言后采样。
测试仅提交 UrasCycle，驱动和 CycleMonitor 隐藏边沿及 Rise-write 细节。

19 份旧域场景数据复现 89/91（另一个全仓 factory 初始化 item 不改变指标），
加一份新场景为 91/91，分母、RTL 和工具链不变；恰好关闭上述两行。
隔离 MicroRAS 为 20 PASS；加入报告保护测试后为 23 PASS。丢弃 S2 中性
修正、丢弃 S3 中性修正、使用旧主 RAS 地址三个 encoder 负对照均普通 FAIL，
不进入正式数据。完整回归为 430 PASS、6 原有 strict XFAIL、0 SKIP，
其他九个 DUT 指标不变。原生分支仅 20/24→21/24，剩余三个点涉及
S2 修正随 fire 传递及 pending S2/S3 配对，不能以满行替代功能审查。
见 `results/coverage-progress-uras-neutral.json`、
`results/coverage-uras-neutral-negative-controls.json` 与
`results/coverage-uras-neutral-refresh-audit.json`。

此次还修复了证据完整性问题：只收集测试会写空 coverage manifest 并把
功能点全部标为 NOT_RUN。已恢复受影响的已审计快照；pytest 插件对
collect-only 不再写正式报告。三项框架测试验证早返回、终端提示与真实
pytest 执行→收集后的逐字保持，实际全仓 436-item 收集也未改动两份报告。

### ITTAGE 满表替换与旧指针重新解码

5.052 基线的两个源码行缺口 `rtl/ittage/RegionWays.sv:227,229` 对应
16-region 满表后使用 tree-PLRU 选择 victim。原 `BPU-ITTAGE-015` 只填满
16 个非 PC region，再复用已有 region，没有分配第 17 个不同 region。
这是真实容量边界场景遗漏，不是两个独立功能点，也不是 LFSR 路径。

`BPU-ITTAGE-018` 使用独立的 heap-node PLRU 模型，在真实分配结果进入
比较前计算 region 指针。各自从复位填满表后，经新 predictor entry 复用
region 0／15 改变替换历史，再连续插入两个不同的新 region。只合格的
非 PC region allocation write 改变策略，预测读不 touch。反序流水线回读
通过现有 driver／monitor／Scoreboard 检查全部 resident：victim 指针所指
高地址会重新解码成新 region，但旧 offset 保持；其他指针的完整 target、
provider 和置信状态保持。不假设第 17 个 region 仍能无损保存。
两个 touch × 两次替换 × victim／survivor 观察的八个 cross bin 在断言后采样。

16 个纯模型 pytest 检查独立 victim 序列、复用 touch、重新解码和非法参数；
ITTAGE 隔离套件为 43 PASS。旧 26 份原始数据复现 1396/1398，加上新场景
为 1398/1398，恰好关闭上述两行，映射分母、RTL 哈希、编译器和处理器不变。
完整回归为 426 PASS、6 原有 strict XFAIL、0 SKIP；其他九个 DUT 的
行／点／分支指标不变。忽略复用 touch、保留 victim 旧 region、破坏 survivor
offset 的三项独立参考负对照都触发异步 ScoreboardMismatch，并显示请求、
接受／观察 tick、transfer 状态及检查进度；不进入正式数据。
正式时效及十份 LCOV／JSON／HTML 一致性见
`results/coverage-ittage-region-refresh-audit.json`，负对照见
`results/coverage-ittage-region-negative-controls.json`。
分支仅 650/658→651/658；满行不代替七个剩余分支和其他状态组合审查。

### 新版原生行缺口揭示 MicroBTB resolve 通道与转发遗漏

5.052 固定工具链的 MicroBTB 原生基线为 760/794 行。34 个缺口中，
30 个是 resolve 的 target／position／type／RAS action／taken 向量选择，
另四个是连续反馈时 useful-counter 的恢复与零值重初始化转发。
原 `UbtbAgent` 只驱动 `fastTrain`，没有封装 `io.train`；这是实际激励与功能点
遗漏，不能用标量训练通过代替完整 resolve 验证，也不是 30 个独立功能点。

`UbtbBatchTraining` 和 `UbtbBranchFeedback` 承载八个 slot，静态 PulseBinding
配合 xreactor 的异步单周期 driver；编码器验证有效 misprediction 至多一项、
字段宽度，并补齐空 slot。monitor 补上 `ras_action`。MicroBTB 保持原 byte-address
单位，不套用 ITTAGE 的 halfword codec。领域测试不写 IO、不等待边沿、不调用 gather。

- `BPU-UBTB-016` 在八个 slot 中选择唯一有效误预测，较早 branch 为正确
  not-taken，逐项检查完整 payload 和其他 resident 保持。每个 slot 的独立
  条件项再经三笔选中 not-taken 反馈从 useful=3 老化为 miss。流水线回读使用
  driver/monitor/scoreboard；八 slot × 两场景的 16 个 cross bin 断言后闭合。
- `BPU-UBTB-017` 让 resolve 与 fastTrain 真正同拍提交，agent 核对接受事件
  tick 相同。有效 resolve 在不同 PC 及同 PC 冲突 payload 下均优先；正确反馈、
  无效 misprediction、t0 被门控则由 fastTrain 更新。无资格 resolve 不改 resident；
  disable 同时阻止两源，重新 enable 后可分配且旧项保持。八格在架构断言后闭合。
- 新连续反馈场景扩充 `BPU-UBTB-010/011/012`：恢复和零值重初始化后还要把
  更新值前递给下一拍。逐拍检查接受间隔，再以“两次老化仍命中、第三次 miss”
  推断持久 useful=3，不以内存读写代替行为检查。四格断言后闭合。

隔离旧 24 份场景数据复现 760/794，加入三份新场景达到 794/794。
正式回归为 409 PASS、6 原有 strict XFAIL、0 SKIP，235/235 功能点执行。
在 RTL 哈希、编译器、处理器和映射分母不变的前提下，34 个旧行缺口实际命中，
没有新行缺口；`v_line` 7/8→8/8，分支 180/192→187/192，其他九个 DUT
的行／点／分支总指标不变。丢弃后续 slot、丢弃 RAS 属性、关闭 resolve 源
三项 codec 负对照分别被 slot／payload／优先级断言检出；不进入正式清单。
证据见 `results/coverage-ubtb-resolve-refresh-audit.json` 和
`results/coverage-ubtb-resolve-negative-controls.json`。
五个原生分支点仍未命中；满行覆盖不代替分支及其他组合的功能审查。

### 原生源码行口径下的 RAS 提交缺口

版本 3 的逐行报告发现，RAS 原基线 106 个未覆盖行包含
`RasStack.scala:328-390` 的 committed push/pop、重复计数更新和退休边界维护。
原 agent 没有绑定 `io.commit`，原测试的 speculative LIFO 通过不能证明
committed stack 有效。补充的 `commit` PulseDriver、commit metadata monitor
及内部延迟封装，使测试只提交操作和 pre-operation metadata，不处理边沿。

- `BPU-RAS-011` 提交三层不同地址的调用，再执行超过一轮推测队列容量的
  临时 call/return 提交对，检查回绕和驻留帧 SSP/SCTR 保持，最后逐层返回。
  这迫使旧推测记录被覆盖，不能仅靠 spec queue 的残留值假通过。
- `BPU-RAS-012` 分别提交 3 次、9 次同返回地址调用；9 次超过三位重复计数
  上限，必须分帧而不是回绕丢失调用。经过相同队列复用后，逐次检查返回地址
  与剩余 SCTR，直到不同地址的底层帧和初始空栈都恢复。
- 保持两周期延迟而禁用全部提交的负对照被 RAS-011 检出；仅跳过重复 call
  提交的负对照被 RAS-012 的 SSP/SCTR 保持断言检出。没有修改 RTL。
- 当前生成 DUT 的 MinimalConfig 使用 8 项 committed stack、16 项 spec queue；
  原测试把 Scala 默认的 32 项当作当前队列容量，已据生成位宽及
  `top/Configs.scala:162-164` 修正。

完整回归使 RAS 原生源码行从 **457/563（81.17%）** 增至
**503/563（89.34%）**，逐行对比确认原来的 106 个缺口关闭 46 个、没有新增
未覆盖行；`v_line` 点从 6/22 增至 12/22，分支从 83/134 增至 107/134。
该次 RAS 回归中其余九个 DUT 的原生源码行计数保持不变。新增两个组的 7+6 个功能 bin
均在输出／metadata 断言之后采样并闭合。
剩余的 60 个 RAS 源码行全部在 `RasStack.sv`，仍包含复制栈槽更新、提交
指针恢复及退休边界推进等路径；新场景不证明这些缺口都是等价复制，也不
证明全部 committed 行为已验证。其他 DUT 的 WriteBuffer、BypassShadowBuffer、
replacer 与 PHR 行缺口仍须按原生行映射继续追踪功能状态交叉。

### 原生源码行口径下的 TAGE/SC 多索引 pending 交叉

原基线 TAGE 有 445 个未覆盖源码行，其中 WriteBuffer 占 440 行；SC 的
1016 行全部在两个 WriteBuffer 变体。已有 TAGE-022 反复更新一个 provider，
SC-016 交替更新同一 SRAM 行的两个 way，不能证明不同索引同时等待写回时
仍各自保留正确更新。源码 `WriteBuffer.scala:184-237` 区分 miss、dirty hit、
clean shadow hit，并允许 full miss 覆盖 pending victim；因此新测试选择
四个不同索引，不提出超容量无损要求，也不把每个复制槽位定义成新功能点。

- `BPU-TAGE-023` 准备同 bank、同最高 table/way 的四个索引，provider 强方向
  与各自实际结果相反。32 拍相邻反馈持续请求训练 SRAM 读、推迟写缓冲排空；
  最高 table 不再分配更长 provider。排空后逐项检查原 provider、counter 0/7
  与方向，再只重训第一项，确认 counter 变成 1 而其他三项保持。复位后重复
  串行反馈作对照。六阶段 × 四上下文的 24 个 cross bin 均在断言后命中。
- TAGE 正确的 provider-only 反馈不请求 SRAM 读，见 `Tage.scala:224-242`。
  因而 TAGE-022 证明的是同项写缓冲转发，不能称为多行 pending 的证据。
  新用例的 `mispredict=1` 与记录的预测方向一致，不用伪造误预测来刷读端口。
- `BPU-SC-017` 用四个 PC 和同一条件 way，每轮发送 16 拍相邻反馈，逐 PC
  使用真实 metadata，最终须分别学成交替的 not-taken/taken 校正。
  公开 `meta.debug.pred*Idx` 确认五类表均使用四个不同索引，学习后仍与原 PC
  关联。复位串行对照核对冷态、输出与有界收敛；不要求旧 SRAM 读值造成的
  连续反馈与串行逐拍等效。三阶段 × 四上下文的 12 个 cross bin 均命中。
- 分别丢弃第一 PC 的 burst 反馈的负对照会被两用例检出：TAGE 保持 counter 5
  而非 0；SC 在 64 轮后仍未使用该上下文的 not-taken 校正，异常附带全部状态。
  负对照与 probe `.dat` 不在完整回归的 292 文件清单中，未修改 RTL。

完整回归使 SC 从 **2052/3068（66.88%）** 增至
**2568/3068（83.70%）**，关闭 516 行（`WriteBuffer.sv` 114 行，
`WriteBuffer_8.sv` 402 行），分支从 182/494 增至 326/494。
TAGE 从 **5208/5653（92.13%）** 增至 **5224/5653（92.41%）**，
关闭 `WriteBuffer.sv` 的 16 行，分支从 223/442 增至 236/442。
逐行集合比较确认两者均无新增缺口；其余八个 DUT 的行与分支计数不变。
可复核的前后计数与闭合行段保存为
`results/coverage-progress-multirow.json`。

SC-017 这一轮后为 33/33 行点，但仍有 500 个源码行缺口（两个 buffer 分别剩 106/394）；
TAGE 在该轮仍有 429 行（WriteBuffer 424、useful queue 4、RAM 1）。剩余的 way-mask、
跨 write-port 命中、clean/pending 转换和 useful 队列排队需继续按合法行为审查，
不能仅凭新测试的 cross bin 满覆盖宣称闭环。其他模块的行缺口也未被本轮覆盖。

`tests/run_all.py` 现在从新生成的 RTL JSON 逐 DUT 读取 `lcov_file`，通过
xreactor 已有 `--line-coverage` 接入统一 HTML，不扫描旧 `.info` 文件。
四个入口单测检查本次清单选择、pytest/合并失败时不发布旧报告，以及报告失败
向调用者传播。完整回归后的十份 LCOV、JSON 与 HTML 命中数一致，所有源码路径
存在且不含 picker 包装；旧 HTML 的原生行报告数是 0，现在为 10。

### TAGE 双写端口 pending、useful 队列和未选 tag 保持

TAGE-023 只在最高表的一个 way 中交错四个索引，不能证明两写端口同拍更新
和 useful 写入排队。`TageTable.scala:95-116` 每 bank 的 entry WriteBuffer
有两个端口，每 bank/way 另有四项 useful 队列；`Tage.scala:411-422` 只在
provider 正确且与 alt/base 不同时增加 useful，错误 provider 不会因此减 useful。

新增 `BPU-TAGE-024` 先在四个同 bank 索引分别用真实分配和反馈占满四表两 way，
并保留所有八个分支的真实 metadata。最高表两个不同 way 的分支位置有序，
反馈为较早实际不跳、较晚实际跳，base 仍为预测时的 0；一拍只有一个真实
误预测，但同时更新两个端口。32 拍反馈只重复每端口四个不同 key，不超过
entry-buffer 容量；误预测训练读暂缓 SRAM 写回，后分支的 useful 更新也须排队。
不提出 useful 队列保留全部重复 beat 或 useful 每拍累加的额外契约。

三个阶段均先同时提交四笔双分支预测，再由原 driver/monitor scoreboard 配对
回读；接受拍相邻且输出在各自接受后的两周期完成。饱和阶段要求原最高表／way
不变，counter 分别为 0/7，后分支 useful 在四个索引中都增加，前分支 useful
保持。每阶段另检查所有未选的六个分支 tag，要求各自方向、counter 和完整
有效 metadata 不变；不能比较 scalar 请求中其他无效输出槽的伴随值。
只重训第一索引的前分支后，其 counter 变为 1，其他 selected 状态和所有未选
tag 保持。复位串行对照比较相同 counter／方向，useful 只要求串行不低于连续
反馈，不错误要求两种读写排队方式逐拍等效。48 个 mode × phase × row × role
cross bin 均在这些断言之后采样并闭合。

三项验证适配层负对照分别省略后分支 MBTB hit、省略第四索引的两个 hit，以及
把后分支 base 反馈损坏为 taken/strong-taken。前两项分别检出仍为 5 的后分支
counter 和第四索引前分支 counter；第三项的 counter 0/7 与方向均正确，却因
useful 仍为 1 而失败。异常附带 PC、position、role、阶段和完整预测状态。
未修改 RTL，probe/mutation `.dat` 未进入本次 298 文件的完整清单。

完整回归为 348 PASS、4 strict XFAIL、0 SKIP，224/224 功能点执行，新增组
使统一报告共 115 个功能 covergroup。TAGE 原生行从 **5224/5653（92.41%）**
升至 **5336/5653（94.39%）**，关闭 112 行：WriteBuffer 107 行、useful
queue 4 行、RAM 1 行；逐行集合比较没有新增缺口。行点从 58/132 到 84/132，
分支从 236/442 到 301/442；其他九个 DUT 行／分支计数不变。独立用例的
5244/5653 不能用于计算正式增量，因为它没有重复其他场景的所有命中。
精确闭合行段与控制结果见 `results/coverage-progress-tage-dual.json`。

剩余 317 个源码行全部在 `rtl/tage/WriteBuffer.sv`（684/1001）。其中 32 个
生成 counter-copy `else` 分支的 40 个赋值行可作局部组合条件矛盾证明：例如
546 行定义 `_GEN_58 = hit & ~rowIdx & _GEN_25`，1376 行外层要求该 guard，
1377 行内层再次判断 `hit`，1384 行却属于其 `else`，要求 `hit && ~hit`。
另一端口的对应分支同理要求 `hit_1 && ~hit_1`。每块 guard 定义、内外条件
和赋值范围均在 `results/coverage-tage-unreachable.json` 中逐项列出并与当前
缺口集合核对。这只是这些赋值体的局部证明，不是全 RTL 形式可达性结论。
该阶段另外 277 行仍需审查跨端口 key/way 关联和 dirty／clean 状态交叉，不能视为
已证明可达或不可达；上述分类不剔除原始分母，也不证明全模块功能闭环。

以下两轮 reset 的隔离探索是历史候选记录，后续已由下述短序列正式测试替代，
不再代表当前计划／判定状态。探索发现反馈路由不能只按“双 way”分类：`Tage.scala:226-236`
在误预测或需要 alternate 时重新读 SRAM，其余 provider-only 路径采用捕获
metadata。用合法分配／两轮 useful reset，将原 position-7 tag 从最高表
way 1 迁到 way 0；各次 reset 在 set 0 开放后仍须等全 128-set 清理完成，
否则强化准备会被 reset-in-flight 门控。之后重放原来实际预测 taken 的
真实 metadata，actual=1、mispredict=0：原 tag counter 4→5，但它的 useful
仍为 0，另一个 position-9 tag（way 1）的 useful 却 3→2。相同准备使用
迁移后的新鲜 metadata，原 tag counter 同为 4→5、useful 0→1，邻 tag
useful 保持 3；其余六个邻项在两组均保持。旧 metadata 组在邻项保持处
普通 FAIL，新鲜组 PASS。当时尚未登记正式功能点，也未证明跨两轮 reset 的
长反馈寿命在集成 BPU 的 FTQ／resolve 约束下可达。
两组隔离原生行均为 5163/5653，**未关闭当前任何行缺口**，不能从 counter
正确推断 `WriteBuffer.sv:804-812` 的跨行分支已命中；这些行仍为零。
探测 `.dat` 以 `probe-` 前缀隔离，不写正式报告。
公开 snapshot、对照结果和源码归因假说见
`results/coverage-tage-way-migration-diagnostic.json`。

正式 `BPU-TAGE-025/026` 缩短上述序列，并扩展到四个同 bank 索引和两种
迁移方向。useful reset 全部发生在 capture 之前；六个低表邻项强化到
useful=3，最高表两 way 保留 useful=0、counter=5/7。捕获原 tag 的真实
strong/taken metadata 后，用另一笔真实错误反馈把原 counter 弱化至 4；
分配优先选择 weak/notUseful，将 C 放到原 way 并强化，再将原 tag 分配到
另一 way。捕获后不再 reset，最后正确反馈总共是第七个实际接受的 beat。
agent 的 opt-in feedback monitor 验证每个 valid／ready、PC／分支身份和
原始 metadata，不能只用同一个 encoder 的自洽结果代替独立核验。

新鲜 metadata 的完整八例均通过，120/120 cross bin 闭合。捕获 metadata
仍使原 tag counter 4→5，却把原 way 上无关 C 的 useful 3→1；C counter
仍为 7，另外六个 tag 的完整状态不变。八例在普通及正反顺序重叠回读均
复现，共 16 个 useful 保持失败，104/120 cross bin 通过，失败 bin 不采样
但保留。迟到 useful 更新允许丢弃或重定向，检查不强加其中一种策略。
只有专门的 useful 误关联异常触发第六个 strict XFAIL；准备、关联、counter、
反馈拍数等前提错误仍普通 FAIL。最后反馈错 way、丢反馈和串行化读回三种
负对照均检出。七拍不超当前 FTQ 容量并不证明 resolve／redirect 的集成
执行顺序可达，因此正式功能点只声明单模块反馈契约。

该轮全回归 372 PASS／6 XFAIL；原生 TAGE 仍为 5336/5653，十个 DUT 的
行／分支／点汇总均不变，不记覆盖率增量，也不把 counter 正确当成跨端口
WriteBuffer 分支已命中的证据。317 行仍保留原分母；40 行局部分类不变，
其他路径继续审查。精确实际 metadata 和八例状态见
`results/tage/way-migration-known-fail.json`，新增场景与三负对照结果见
`results/coverage-progress-tage-way-migration.json`，310 份正式数据与
LCOV／JSON／HTML 的时效／隔离审计见
`results/coverage-tage-way-migration-refresh-audit.json`。

继续沿实际生成优先级发现：804 行先判 `_GEN_129 = hit_1 & _GEN_97`，
817 行的 `else if (hit_1)` 已要求 `!_GEN_129 && hit_1`，所以 `_GEN_97`
必为假。819 行再次要求 `_GEN_97` 的 820–823 四个赋值因此不可达；
871 行 clean-copy 的 else 也要求它为真，其 872–875 四个赋值同样矛盾。
另外三个 row-0 entry 和两种上下文下四个 row-1 entry 都有对应优先级排除。
共 **24 个分支、48 个此前未分类赋值行**。这里只分类赋值体，不把仍可能
执行的 guard/anchor 行一并宣布不可达，也不把整个跨端口路径宣布死掉。

`suites/frontend/bpu/tage_coverage_audit.py` 先核对精确源码守卫、定义、局部位置和
赋值目标，再穷举 H（hit）、S（selected）、W（written）、C（compare equal）
的 16 个取值。dirty-copy 的 `!(H && S) && H && S` 与 clean-copy 的
`!(H && S) && H && !(!W || C || !S)` 均无满足项；去掉第一个优先级前提后
二者必须出现满足项。把 conjunction 改为 disjunction、改 copy 选中项、
改赋值物理 row 的三种内存源码负对照均被拒绝，实际 RTL 文件没有改动。
结合此前 40 行，当前 **88/317 行局部分类，229 行未分类**。证据见
`results/coverage-tage-priority-unreachable.json`；原生 5336/5653 分母／命中数
均不改变，也不宣称完整 RTL 形式可达性或功能验证闭环。

### SC 多索引 masked-way 隔离与生成不可达代码分类

`ScTable.scala:68-124` 在每个 bank 的四槽 WriteBuffer 中按 way-mask 合并；
`WriteBuffer.scala:75-82` 保留未选择 way，209-221 区分 dirty 合并和 clean
shadow 重写。已有 SC-016 是同一行两个 way，SC-017 是四行的单一 way，
两者均不能证明不同索引 pending 时修改一个 way 不破坏其他 way。

新增 `BPU-SC-018` 用四个同 bank 索引和 positions 4/5/6/7（四个不同 base
way）。每个 PC 使用 counter 0/7/3/4 中一种，公开 `scBiasLowerBits` 必须
分别为 0/1/2/3；`Sc.scala:245-252` 以 `{weak, taken}` 选择四种 bias 子 way。
五类表的公开索引必须四项不同且不随训练改变。每个阶段只反馈一个 branch
way：16 拍连续反馈只访问四个索引，使用当前真实 metadata，不超容量。
每轮经 scoreboard 流水线回读后，此前已学会的 way 保持 use／方向，以后
未选 way 保持 cold use=0 和原始 SC direction=1；selected way 有界学成。
原始 SC direction 不是 use=0 时的 TAGE fallback，cold provider 的 tageCtr
与 bias bits 单独核对。最终四 way 方向为 not-taken/not-taken/not-taken/taken。
复位串行对照比较 cold 与各学习阶段，并只要求串行收敛不更慢。
48 个 phase × row × way 及 16 个 way × bias-selector cross bin 均在断言后命中。

只改验证反馈的负对照分别取消 position 6 的有效 MBTB hit、取消第四 PC 的
hit、或把 position 4 路由到 5。前两者在 64 轮界限后报告仍冷态的对应 way／row；
后者首轮就检出未选邻 way 的原始 SC direction 错变为 0，异常附带阶段和完整状态。
本轮没有修改 RTL；probe/mutation 文件未进入 297 文件的完整清单。
完整回归为 347 PASS、4 strict XFAIL、0 SKIP，功能点 223/223 执行；
SC 原生源码行从 **2568/3068（83.70%）** 到 **2642/3068（86.11%）**，
关闭 74 行（base WriteBuffer 34、bias WriteBuffer_8 40），无新增缺口；
分支从 326/494 到 388/494。其他九个 DUT 的行／分支计数不变，逐行增量见
`results/coverage-progress-sc-masked.json`。

继续检查 SC-018 后剩余的 426 行，发现 336 个赋值行属于明确的组合条件矛盾，不是尚未
找到激励。以 `rtl/sc/WriteBuffer.sv:338` 的 `if (hit)` 为外层，293-296 定义
`_GEN_15..18 = ~hit && victim...`。365 行在该 hit 分支内部又执行
`else if (_GEN_15)`，因此 366-374 的赋值体要求 `hit && ~hit`；clean shadow
分支的 481 行同样要求 `_GEN_15`，482-490 也不可达。四个 slot 的 dirty／
clean 两种 body 共 72 个赋值行。`WriteBuffer_8.sv:806` 的外层 hit 与
689-692 的 `_GEN_39..42 = ~hit && ...` 形成相同矛盾，八个 body 共 264 行。
这些 fallback 是 Chisel 默认值与后续互斥更新经 firtool 生成后留下的冗余路径。
逐块 guard 定义、外层位置和 body 行段保存在 `results/coverage-sc-unreachable.json`；
该审查只证明列出的 16 个赋值体不可执行，不是整个 RTL 的形式可达性证明。
**仍保留原始 LCOV 分母，不排除这 336 行。** 该阶段另外 90 行未分类，
包含 bias way-mask 与 slot/state 交叉；不能据此反向断言这些行一定可达，
也不能用去除不可达行后的数字代替原始行覆盖率。

### SC 同一 pending 行内的四 bias selector 合并

`BPU-SC-019` 补上 SC-018 的矩阵缺口：每个 PC 不再只使用一种 counter
profile，而是都查询 0/7/3/4，使同一 bias SRAM 行的四 selector 与四 base
way 全部可见。四 PC 的五类表索引须不同且稳定；positions 4/5/6/7 经
位置 hash 分别选取四 base way。真实冷态 metadata 的延迟反馈逐 selector
训练全部四 way 为负，每次后回读所有 selector 和邻 way。

非 bias 表共享每个 base way，故总 SC 方向可能掩盖 bias 的错写／漏写。
新断言使用 `Sc.scala:259/341` 导出的 `debug.scBiasTakenVec` 单独检查 bias
方向，再核对 provider counter、selector、五类索引及 SC decision/meta
关联。全部 64 个 bias 状态为负后捕获真实 metadata，仅将 row／selector
棋盘格的两个 way 训练为正；每轮 bounded reversal 后所有未选 way 和
selector 保持原方向。两个模式分别使用相邻／复位串行反馈，monitor
逐拍核对 PC、selector、resolved branches 和间距。流水线回读先提交全部
16 个上下文，最后正反顺序 32 笔还要求同上下文两次完整 snapshot 一致。

1280 个 cross bin 断言后闭合。取消 selector-3 的 provider-valid 训练资格，
总 SC 仍为 not-taken/used，但该 selector 的 bias 全为 1，输出状态断言
普通 FAIL；错 selector metadata 由 monitor 身份检查失败；强制串行化
使拍间距 22 而非 2 tick，也普通 FAIL。没有编辑真实训练 metadata 来
伪造正对照，也没有修改 RTL 或写内部状态。公开 bias metadata 只能证明
方向，不提供精确 signed counter 数值；相邻训练读可复用旧 SRAM 值，
本场景不承诺每拍累加等价于串行。

完整回归关闭 `rtl/sc/WriteBuffer_8.sv` 的 **82** 个赋值行，其中 dirty
shadow 合并 45 行、clean shadow 重写 37 行；无新增缺口，其他九个 DUT
汇总不变。该阶段 SC 为 **2724/3068（88.79%）**，branch **470/494**，`v_line`
仍 **33/33**。当时剩余 **344** 行中，重新核对原 guard/body 的 336 个不可达
赋值仍保留在分母；另八行 `:1356/1388/1460/1492/1596/1628/1716/1748`
都是 clean hit、entry changed 且 selector-0 way-mask 选中的数据赋值，
当时需继续检查合法状态组合与插桩相位，尚未宣布可达／不可达或功能闭环。
该阶段逐行增量、缺口分类与时效审计见
`results/coverage-progress-sc-bias-selectors.json`、
`results/coverage-sc-unreachable.json` 和
`results/coverage-sc-bias-selectors-refresh-audit.json`。

### SC 排空后的已学习 bias 行重激活

`BPU-SC-020` 证明上述八行是合法状态序列尚未驱动的缺口。使用真实冷态
metadata，将四个同 bank 行的四个选中分支训练到 taken/used 全 1，
分别以相邻和复位串行反馈完成准备；这时捕获真实正向预测，而不是手填
SC 正误字段。训练封装等待九周期更新和写回排空，并完成全部 16 个
row/selector 上下文的回读，然后间隔式逐 way 发 actual=0 的负向反馈。
公开 bias 方向检查必须观察到所有四行当前 way 反转，所有其余 way、
selector 均保持。每轮 bounded reversal 都检查邻项，不能只检查终态。
四 way 全负后捕获真实负向预测，再将每行棋盘格两 way 恢复为正；
最后正反顺序 32 笔重叠预测核对完整 snapshot、索引、provider、selector
以及 driver/monitor 接受／完成时间。1024 个 cross bin 均在断言后命中。
两模式仅准备阶段是否相邻不同，所有重激活均为间隔式反馈，不把它描述为
重激活阶段的并行／串行等效。方向 metadata 也不证明精确 signed-counter 饱和。

只取消第四行的单 way 重激活训练资格，准备仍通过，但 64 次后该行的
slot-0 bias 仍为 1、其他三行已为 0，输出状态断言普通 FAIL。把捕获的
正向 SC 预测错换成 0 且标为 above-threshold，会门控掉错误更新，四行
均仍为正，普通 FAIL。强制串行化准备使 monitor 观测 22 而非 2 tick
拍间距，也普通 FAIL。正对照不修改 metadata 字段、RTL 或内部状态。

完整回归恰好关闭 `rtl/sc/WriteBuffer_8.sv` 的
**1356、1388、1460、1492、1596、1628、1716、1748** 八个 clean-hit、
entry-changed、selector-0 选中 way 的赋值行；无新缺口，其他九个 DUT
汇总不变。这些行实际命中，不能继续将它们列为插桩相位疑点。
SC 当前 **2732/3068（89.05%）**，branch **478/494**，`v_line` **33/33**。
剩余 336 行与重新核对 guard 定义及完整 body 的 16 个局部矛盾块精确一致，
仍保留全部原始分母；不从这些局部证明推断全 SC 功能验证完成。
证据见 `results/coverage-progress-sc-clean-reactivation.json`、
`results/coverage-sc-unreachable.json` 和
`results/coverage-sc-clean-reactivation-refresh-audit.json`。

### 原生源码行口径下的 ITTAGE 容量与两 bank pending 交叉

原 69 行缺口为 `RegionWays.sv` 的 region 2..15 写入（14 行），
两种 WriteBuffer 的 slot 2/3 写状态（各 26 行），以及最高表第二 bank 的
`FoldedSRAMTemplate_5.sv:95` 和 `SRAMTemplate_5.sv:87-88`（3 行）。
36/36 行点不能说明这些分支行段已经走到。

首先发现验证 adapter 地址单位错误：`PrunedAddr.scala:23-31` 中 `addr`
省略 bit 0，`toUInt` 才补回零位；`IttageTable.sv:119-122` 用编码地址
bit 0 选 bank、bit 7:1 选 set，即字节 PC bit 1 和 bit 8:2。旧 agent 把
字节常量原样写入并原样读回，两侧错误抵消，不足以证明实际 1 MiB region
边界。现在 lookup、feedback target 和 provider/alternate metadata 均在
agent 内转换；独立 encoder/monitor 单测及拒绝非法 burst 的断言归入
`BPU-ITTAGE-017`。其他 adapter 没有随之静默改变单位，仍需逐个审查。

- `BPU-ITTAGE-015` 插入 16 个不同非 PC region、相同低位的目标；每次写入
  都回读全部已有指针。满表后在相邻 folded SRAM lane 复用已有 region，
  全部旧目标及新目标均保留，再反序交错查询，48 个 phase × region bin 闭合。
  `RegionWays.scala` 满表采用 PLRU；本用例不提出第 17 个新 region 无损要求。
- `BPU-ITTAGE-016` 分别在两个 SRAM bank 准备四个真实首表 confidence=2
  provider，或四个最高表 confidence=0 provider。16 笔读与八拍反馈重叠；
  后四拍重用同四项旧 metadata，不增加索引数量。读窗口内逐笔核对原驻留状态，
  排空后检查首表强化／最高表目标改写，再逐项重训 clean shadow 并回读所有邻项。
  各 bank/mode 都复位做串行对照，96 个 phase × mode × bank × context bin 闭合。
  根据 `IttageTable.scala:207-228`，prediction SRAM 读阻止该 bank 写回；
  ITTAGE 训练本身不读 SRAM，所以不能用只有训练的 burst 替代真实并行预测。
- 最初四拍、单 bank 版本只关闭 40 行，仍缺两个 buffer 的 slot 3 和第二
  bank 读路径，共 29 行。仅增加预测预热等待没有关闭 slot-3 缺口，该调整
  已撤回；重复访问 dirty context 的八拍版本补齐剩余路径，未改变 RTL。
- 负对照串行化反馈时 event.tick=588 已晚于最后请求接受 tick=564；
  丢第四 PC 反馈时其 counter 仍为 2 而非 3。回退 identity 地址编码/解码时
  encoder 和 monitor 两个独立断言均失败。probe/mutation 数据不进入本次清单。

完整回归使 ITTAGE 从 **1216/1285（94.63%）** 经 **1256/1285（97.74%）**
升至 **1285/1285（100.00%）**，分支从 352/372 经 368/372 升至 372/372。
逐行缺口集合关闭 69 行且没有新增缺口，另外九个 DUT 的行／分支计数不变；
精确行段与负对照记录保存于 `results/coverage-progress-ittage.json`。
源码行／分支满覆盖仍不证明所有地址、region 替换、buffer 超容量和流水线组合
正确；TAGE/SC、MicroTAGE、AheadBTB、集成 BPU 等模块的缺口还需继续分析。

### MicroTAGE 全容量 shadow 回绕与 SRAM 持久化

原基线的 5196 个未覆盖源码行全部在两份 `BypassShadowBuffer`，不是顶层
MicroTAGE 功能只有少量行。低表为 2519/5261、高表为 2295/4749 原生行；
大量缺口来自 useful entries 按 bank／索引展开的复制语句，但复制计数不能
代替数据保持、转发优先级和回绕状态交叉的行为证据。

- `BPU-UTAGE-015` 每张表、每个 bank 准备八个不同真实预测索引。两个旧 API
  编码 PC 配合低四位折叠历史选择这些索引，不重新解释为字节地址，也不隐藏
  独立的 GuardedPc tag 宽度缺陷。十二拍同项正确反馈必须通过最新项 bypass
  饱和，七个邻项保持弱态；再交错八索引的 64 拍反馈，使所有 counter 饱和
  且原 provider／position／history 关联不变。复位串行三个阶段均作对照。
- feedback 的被动 monitor 核实每拍 PC／readIndex、总拍数和相邻两 tick 的
  cadence，不把串行驱动称为相邻反馈。八笔 readback 先提交、后由已有
  driver／monitor／scoreboard 配对，检查两 tick 接受间距及完成延迟四 tick。
  384 个 cross bin 均在输出断言后命中，不比较无效的伴随输出槽。
- `BPU-UTAGE-016` 保留另一项必需契约：用邻 bank 八个新索引完全替换旧
  shadow，但不替换旧 SRAM 行。每组先硬断言全部旧项饱和、新项弱态及索引
  不混淆，再回读全部旧 provider。两表 × 四 bank × 两模式共 16 组全部检查
  后才报告，128 个旧项中的 112 项 counter 退回：低表 7→5、高表 0→2。
  只有 `LostShadowWriteback` 触发 strict XFAIL，其他前提失败仍普通 FAIL。
  该组 cross 272/384（70.83%）命中，112 个失败格保持未命中；组内 point
  和 cross 平均为 95.14%，不能将其解读为 95.14% 的旧项保持正确。
- 原 Scala `BypassShadowBuffer.scala:248-258` 先清理成功写回项，再给新
  enqueue 置 dirty，最后给 `t1_cleanId` 清 dirty；当旧命中与新入队共用同一
  槽时，最后的赋值覆盖新 dirty。低表生成 RTL `:2351-2381` 中每槽的
  dirty 更新直接含这项否定条件。隔离的原 RTL `--vpi` 构建，对两表及两模式
  每组都观测到 57 次同槽碰撞，其中 15 次 counter 真正变化而新 dirty 为 0。
  公开 bypass 仍读到新 counter，不代表该 copy 已请求 SRAM 写回。
- 串行化相邻反馈在 cadence 前提处普通失败；丢最后索引反馈在拍数前提处
  普通失败；只改该索引最终分支 position、保留相同拍数与 readIndex 时，
  其 counter 仍为 4 而非 7，功能断言失败。负对照和 VPI `.dat` 不进入清单。

完整回归使 MicroTAGE **5516/10712（51.49%）→5705/10712（53.26%）**，
关闭 189 个源码行（低 buffer 114、高 buffer 75）且没有新增缺口；`v_line`
343→446，branch 1424→1467，另外九个 DUT 的行／分支计数不变。
精确行段见 `results/coverage-progress-utage-shadow.json`，根因观测见
`results/coverage-utage-shadow-dirty.json`，完整失配矩阵见
`results/utage/shadow-persistence-known-fail.json`。没有修改 RTL 或原生分母。
该阶段剩余低／高 buffer 分别缺 2628／2379 行，共 5007 行，仍需继续审查 useful
aging、相同索引不同 tag、不同槽优先级及合法读写冲突；该轮没有宣称其全部
可达、不可达或行为等价。新缺陷需要 RTL 修复，不能靠删除失败检查刷覆盖率。

### MicroTAGE 两轮 useful aging：状态差异而不是复制行数

`BPU-UTAGE-017` 为每个 bank 准备三个不同索引，通过真实预测 metadata 和
正确／错误反馈建立低表 useful 强度 1/2/3、高表 useful 3。独立校准项必须
在两次高表错误后仍阻止新 position 分配，第三次才只开放高表；即使 taken
counter 更新正确，破坏 useful 的 baseTaken 资格也会使此硬前提失败。

| 原低表强度 | 第一轮后低表／高表 | 第二轮后旧低表／高表 | 可观察的分配行为 |
| ---: | --- | --- | --- |
| 1 | 0／1 | 第一轮新项／0 | 第一轮先分配低表，仍不能升级高表；第二轮允许升级 |
| 2 | 1／1 | 0／0 | 第一轮仍阻止；第二轮须先选择低表，再允许高表 |
| 3 | 2／1 | 1／0 | 第一轮仍阻止；第二轮直接分配高表，原低表 counter 6 必须保持 |

useful 数值依据反馈与老化逻辑推导，验证证据是公开分配结果、保留项与
provider/counter 读回，不把内部数值推导本身当成断言。第一轮准确计入
4 次校准失败＋12 次被阻止 alias＋112 次新鲜最高 provider 错误；第二轮
计入 8 次被阻止 alias＋4 次低表错误＋116 次最高 provider 错误。每次操作
后全部 12 个 alias 和原 position 流水线回读，检查位置、双表索引、history
关联、counter、表选择和所有邻项。hit=0 时 raw takenVec 无 base fallback
契约，只检查 miss 与独立 baseTaken metadata，避免错误的预期。

5 phase × 4 bank × 3 strength 共 60 个 cross bin 断言后全命中；少一次
失败 tick、少一次低表强化、保持 counter 更新但破坏高表 useful 资格三个
负对照均普通 FAIL。完整回归只新增 4 行：低表 `:7991,7996`、高表
`:7479,7484` 的训练回读 counter bypass 赋值。原生行升至
**5709/10712（53.30%）**，`v_line` 446→448，branch 1467/2132 不变；
无新增行缺口，另外九个 DUT 汇总不变。60 个行为 bin 不等于 60 条新增行，
大量状态组合复用既有 RTL 路径，不能以本轮小增量否定这些功能检查。
该阶段剩余 5003 行（低 2626／高 2377）仍需按索引、tag 与状态交叉分析。
原 `BPU-UTAGE-016` 仍为 112/128 失配的 strict XFAIL，没有通过删除检查闭环。
精确增量和报告时效见 `results/coverage-progress-utage-aging.json` 与
`results/coverage-utage-aging-refresh-audit.json`。

### MicroTAGE 短历史共享、长历史独立：修正激励范围

此前共享编码器只允许 recent history 0..15，把同一值写给每个 fold；低四位
确实能同时适配所有窗口，但不代表可验证长历史区别。shadow／aging 阶段
使用的两个编码 PC 配合这些 profile，只选择 index 0..15 与 64..79。
不能把这样的激励范围当成 512 个索引的全部行为证据。

当前生成 RTL `MicroTage.sv:596-598` 明确以 `hist[2]` 的六位历史产生
低表索引，以 `hist[9]` 的十二位 history 折成九位产生高表索引；tag 比较
`:932-963` 还分别使用短／长窗口的两种 tag fold。`Types.scala` 的 fold
集合、MinimalConfig 参数及 `PhrAllFoldedHistories.sortBy(_.asTuple)` 定义
19 项布局；`PhrHelper.computeFoldedHist` 是截取相应窗口后逐块 XOR。
新编码器据此支持 31 位 recent PHR profile，并检查两 agent 的绑定位宽。
位宽检查无法推导任意配置的原历史长度，布局只承诺当前固定 RTL；旧四位
profile 的编码完全不变，数学单元测试另用逐 bit XOR 作独立算法对照。

`BPU-UTAGE-018` 交叉四 bank 和较老 bit 6/7/8：PC／position 与短六位
窗口相同，B 须先继承 A 的低表，再通过真实错误反馈建立自己的高表。
两个高表 provider 方向相反；正确反馈分别饱和 A 至 counter 0、B 至 7。
每次更新某 bank 后，流水线回读全网格保持邻 bank、对侧 history 和第三个
未训练高表上下文的低表 counter 4。第三上下文使用 bit 11，它应 XOR 折到
index bit 2，而不是被截掉。正反混排的重叠预测逐项检查完整 PHR metadata、
双表 index、provider、counter、位置和两 tick 接受间距／四 tick 完成延迟。

144 个 cross bin 断言后全命中。截成四位在 B 的冷高表索引前提处普通 FAIL；
A1 错用当前 A0 history 在首笔混排 A 的 metadata／provider 关联处普通 FAIL。
完整回归新增 14 个源码行，全部在高 buffer 的 inner index 32／64 useful
更新：bank 0/1/2 各两个 increment 赋值，bank 3 的两个 index 各四个 guard／
decision／赋值行。MicroTAGE 为 **5723/10712（53.43%）**，`v_line`
448→458，branch 1467→1469；无新增缺口，其他九个 DUT 汇总不变。
该阶段剩余 **4989** 行（低 2626／高 2363），两项已知 tag-width／shadow
持久化缺陷未修复，不能靠任意改 metadata、扩大分母排除或删断言刷覆盖率。
下一步仍需区分 useful 复制索引、合法 tag／hash alias 组合与状态交叉。
证据见 `results/coverage-progress-utage-long-history.json` 和
`results/coverage-utage-long-history-refresh-audit.json`。

### MicroTAGE 同高表 hash、不同 tag 与延迟真实反馈

`BPU-UTAGE-019` 翻转 recent PHR 的 (0,9)/(1,10)/(2,11) bit 对：
十二位窗口折成九位时两次翻转抵消，A/B 高表索引相同，但 tag fold 和
低表索引不同。另一个高表索引的弱态邻项用于检查误写。四 bank 都先通过
真实预测／错误反馈建立 A 的高表 counter 3、useful 2；B 冷查必须 miss，
只分配低表。B 的错误在 useful=2 和一次 A 错误后的 useful=1 均不得替换；
第二次 A 错误使 useful=0 后，B 才可重分配高表 tag，A 回退未改变的低表。

`BypassShadowBuffer.scala:170-204` 的更新在当前 resident tag 不匹配时
使用训练 metadata 的捕获 counter，而不是另一个 tag 的 counter：B 饱和
到 7 后，旧 A counter-3 反馈重建 A=4；再让旧 B counter-7 反馈重建 B=6。
这不是“丢弃旧反馈”的契约，也没有为命中分支捏造 metadata。每个阶段
先提交 A/B/邻项的全部 transfer 再 drain，检查完整 PHR、索引、位置、
provider、counter、方向及两 tick 接受间距／四 tick 完成延迟，最后 24 笔
混排重叠预测。两模式的反馈 monitor 检查实际拍数、身份和间距。

720 个 cross bin 在断言后闭合。错 snapshot counter 使 B 读回 3 而非 6；
错 snapshot tag 恢复 A 的高表而非 B；串行化 burst 使实际反馈间距为 26
而非 2 tick，三者均普通 FAIL。完整回归只新增 **5** 个高 buffer 源码行：
`BypassShadowBuffer_1.sv:3589/4613/5637/6661` 是四 bank 的 inner row 34
useful increment 赋值，`:6657` 是 bank 3 的 guard；不把这些行误称为新的
tag 比较或 counter 重建分支。当前 **5728/10712（53.47%）**，`v_line`
458→462，branch 1469→1470；无新增缺口，其他九个 DUT 汇总不变。
剩余 **4984** 行（低 2626／高 2358）保留在原始分母中。八次低表写入
没有超过 resident shadow 容量，不能据此宣称持久化缺陷已关闭。
证据见 `results/coverage-progress-utage-history-collision.json` 和
`results/coverage-utage-history-collision-refresh-audit.json`。

### 历史覆盖点口径的场景发现记录

本节列出的中途覆盖增量来自当时未固定 Verilator 随机种子的运行，只能作为
场景发现史；涉及绝对覆盖率或“全部命中”的旧结论不代表当前基线。

- SC 的 2/2 RTL 行和 16/16 分支未揭示 MBTB 资格门控缺口。agent 原先把
  `mbtbResult[0]` 固定为有效条件分支，只有 provider-invalid 被测。
  `BPU-SC-007/008` 先训练至 `scUsed=1`，再分别送入 MBTB miss、非条件
  hit，断言 `scUsed=0`；恢复有效条件 hit 后再次使用已训练的校正。
  功能覆盖率新增 qualification 四类 bin，并将无训练的查询记为
  `training=none`；所有采样均在相应输出断言之后。完整回归的 SC RTL
  行/分支保持 2/2、16/16。当前固定种子完整回归的 SC RTL `v_toggle`
  为 3052/4700；历史非固定种子的近满值不可与此基线比较，也不能替代
  资格门控的逐笔判断。
- `BPU-SC-011` 补上与上述预测资格独立的训练资格矩阵。`ScTraining` 现在
  显式携带 MBTB raw hit 和分支类型，测试无需写裸端口。先学得 not-taken
  校正，再分别送入 MBTB miss、非条件 taken 分支，以及预测 metadata
  已断言 `tagePredValid=0` 的 provider-invalid 反馈；各反向训练 32 次后，
  合格查询仍须得到原 not-taken 校正。最后合格条件 taken 反馈可学成 taken，
  排除训练端被整体关掉的假阳性。五个 bin 均在断言后采样。SC 行/分支仍为
  2/2、16/16；固定种子 RTL toggle 从 2961/4700 增至 2968/4700。
- `BPU-SC-012` 发现原 agent 在预测输入和输出都只覆盖 slot 0，虽
  RTL `Sc.scala` 对四路 MainBTB 结果逐路计算方向和 `scUsed`。扩展
  xreactor 多阶段 driver 的 S2 Bundle 与 monitor 向量后，先在 slot 1/2/3
  逐路检查已学成条件分支的 use 和方向、较早直接分支及空槽不使用；
  再交错四笔有效／无效 TAGE provider 向量，核对 S2 决定与次周期
  `useScPred`、`tagePredValid` metadata 的逐笔关联。五格覆盖均在断言后
  命中；全量 RTL 仍为 2/2 行、16/16 分支，证明满行覆盖此前未表达
  多路预测的功能需求。
- `BPU-SC-013` 再检查 SC 训练侧：原 agent 仅绑定 `io.train.branches(0)`，
  不能表达 RTL 对完整 resolved-branch 向量的遍历和 `mbtb.entries.flatten`
  的逐位置匹配。新 batch 事务将 resolved slot 0/2 的两个有效条件分支
  分别关联预测 slot 1/3，中间保留空槽；一次反馈让较早分支 not-taken、
  较晚分支 taken，反复以当次预测 metadata 训练直至两路同时学成相反的
  校正方向。两路输出与注册 metadata 断言后才采样独立的槽位及方向 bin。
  SC 本来已满的 RTL 行/分支因此仍不能替代此多分支语义证据；固定种子
  RTL toggle 从 2968/4700 增至 3036/4700。
- `BPU-SC-014` 检查与 SC-013 正交的同 way 冲突：RTL `Helpers.updateEntry`
  按 way 对同拍分支分别计数 inc/dec，`Sc.scala` 的 threshold 与 bias
  路径也分别聚合。位置 1 和 4 经两位分块 XOR 映射到同一 way；两路
  MainBTB/provider metadata 均有效且初始不在阈值上方，较早 not-taken、
  较晚 taken 的 64 笔同拍反馈后两个预测槽仍保持冷态。随后仅训练较早
  分支即可学成 not-taken，两个槽都观察到共享校正，排除“训练整体无效”
  的假阳性。四格覆盖只在断言后采样；SC 原本已满的 RTL 行/分支无法
  单独证明这一聚合语义。固定种子 RTL toggle 从 3036/4700 增至
  3048/4700，行/分支仍为 2/2、16/16。
- `BPU-SC-015` 补上同 way 双分支同向反馈的另一半：两个位置都
  not-taken，RTL `PopCount` 应对该 way 给出两次减向更新。用同一
  SC agent 两次复位，先核对冷态方向、provider 与阈值签名一致，再
  分别以单分支和双分支事务训练至两个预测槽共同使用 not-taken 校正；
  双分支所需训练拍数必须更少；第三次复位重复单分支学习拍数，排除
  残留状态造成的伪加速。这个差异会让只处理 slot 0 的训练实现
  失败，四格功能覆盖在对照断言后采样。SC 的满行/满分支覆盖无法
  单独区分 `PopCount=1` 与 `PopCount=2` 的行为。固定种子 RTL toggle
  从 3048/4700 增至 3052/4700，行/分支仍为 2/2、16/16。
- `BPU-SC-016` 是修正 `.sv` 分类后从真正的行缺口发现的跨拍场景。
  SC agent 新增 `train_batches`，复用结构化 PulseDriver 在八个相邻周期
  交替发送同 fetch block、不同 SC way 的合格反馈，期间 SRAM 训练读会
  暂缓 write-buffer 排空。两路预测都须最终学成 not-taken；复位后用相同
  事务的串行反馈作正对照。连续读取可能看到旧 SRAM 值，因此不要求
  两种时序的收敛拍数相同。完整回归使 SC RTL `v_line` 从 **25/33**
  增到 **27/33**，命中新纳入统计的 `WriteBuffer.sv:342` 和
  `WriteBuffer_8.sv:810`；剩余六点是其他槽位的同类生成路径，不把
  每个复制槽位当作一个新功能点。
- `BPU-TAGE-022` 针对更正后 TAGE 的 WriteBuffer 缺口：先通过真实反馈
  建立 tagged provider 并把计数器强化至 5，再用 agent 在相邻八拍发送
  同一 provider 的合格 taken 反馈，训练期间不穿插预测读。排空后公开
  metadata 必须显示原 table/way 未变、计数器饱和到 7，输出仍 taken。
  完整回归的 TAGE 全 RTL `v_line` 由 **38/132** 增为 **55/132**，
  旧锚点去重由 37/111 增为 54/111，分支由 204/442 增为 223/442；
  新命中的 17 个行点位于 WriteBuffer counter 更新路径；正确 provider-only
  反馈不读 SRAM，这一用例不能证明不同索引同时 pending。
  仍余 77 个行点，不把生成槽位复制当作 77 个不同功能点。
- MainBTB 的 2/2 原始 RTL 行和 4/4 分支在新增用例前已命中，但功能清单
  仍遗漏两个 fetch-window 规则。`BPU-MBTB-008` 在页末 fetch 中检查下一页
  entry 的 `rawHit=1` 却不返回有效预测，再从下一页起点检查同一 entry
  命中、position 由 9 重映射为 1。`BPU-MBTB-009` 从已越过分支位置的
  PC 查询，检查 `rawHit=1` 但预测被屏蔽；从原 block 起点仍命中。
  两者均先断言行为再采样独立的 `cross_page_filter`／`prefix_filter` bin。
  全量回归后 MainBTB 仍为 2/2 RTL `v_line`、4/4 分支，表明这是功能模型
  扩充，不是原始覆盖率刷点。
- MainBTB 原 lookup driver 把 `enable` 固定为 1，无法验证独立的全局门控。
  现将 enable 交给独立控制 driver；`BPU-MBTB-010` 先让输出处于已知
  miss，disable 后对训练过的 PC 发起查询，检查流水级仍保持旧 snapshot，
  再 enable 才读到 hit。RTL 在 disable 时停止 S1/S2 推进，输出可能保留
  旧 valid，不能把“disable 后必须全 miss”当作无条件规格。
  `BPU-MBTB-011` 则用 indirect target 更新作对照：disable 期间训练不改变
  旧 target，重新 enable 后同一更新能生效。两项独立功能 bin 均在断言后
  命中；完整回归的 MainBTB 原始 2/2 行、4/4 分支数字仍不变。
- `BPU-MBTB-014` 根据 `MainBtbAlignBank.scala` 的 `t1_entryNeedWrite` 属性变化
  arm 补上另一项原清单遗漏的需求。先让同 align bank 的两个 way 驻留，
  将条件 entry 老化至计数器 0，再按条件→直接→间接→条件三次改写同一位置。
  每次用新查询 metadata 训练，检查只占原 way、旧类型消失、新 target 和弱正
  计数器可见，同 bank 邻项的 way/target/direction 保持；改回条件后一次
  not-taken 训练使计数器从 2 变 1。六个功能 bin 均在逐项断言后命中，
  MainBTB 行/分支仍为 2/2、4/4。这说明已满的低分母 RTL 覆盖并未列举完
  设计行为，不能用“满行”替代功能点审查。
- `BPU-MBTB-015` 区分 `mispredictBranch.valid` 所选 entry 写入与普通有效
  branch 反馈的计数器更新。原测试辅助函数把 `mispredict` 固定为 1，故仅
  检查了误预测训练。新用例让同一 align bank 的条件与直接 entry 共存：
  正确 taken 反馈用 `mispredict=0` 将条件计数器从弱正 2 推到正饱和 3；
  两次真实 not-taken 误预测使其从 3 经 2 转为负值 1；之后正确 not-taken
  反馈用 `mispredict=0` 将其降至 0 并维持饱和。每步断言两项的方向、
  counter、target、way；五个功能 bin 均在断言后采样。MainBTB 行/分支
  仍是 2/2、4/4，再次表明满行覆盖不能替代训练语义的功能审查。
- `BPU-MBTB-016` 发现原 MainBTB agent 只绑定 `branches[0]`，因而此前所有
  测试都是逐笔反馈，未覆盖 RTL 对完整分支向量的计数器更新。扩展为批量
  事务后，在同一 align bank 的两个条件位置用单笔反馈让较早正确 not-taken
  和较晚唯一误预测 not-taken 分别使计数器 1→0、2→1；重新布置到 1／2
  后，再以零误预测的单笔双分支反馈让较早分支 not-taken、较晚分支 taken，
  两计数器同时变为 0／3。较晚分支只在前者落空时执行，符合 FTQ 控制流。
  各阶段检查方向、target、way 及饱和，六个 bin 在断言后采样。原始 2/2 行、4/4
  分支无法反映这一输入组合是否经过验证。
- `BPU-MBTB-017` 对准 `MainBtbReplacer.scala:59-65` 的同 set 训练状态前递：
  原 agent 每笔反馈后都等待 6 周期，无法验证相邻 FTQ 反馈。现由训练 driver
  连续两拍保持 valid，分别写入同物理 set／align bank 的不同 tag；正反两种
  顺序都从真实 cold metadata 出发，断言两项最终占不同 way 并回读精确 target，
  两个功能 bin 在断言后采样并于完整回归达到 100%。MainBTB 原始 RTL 仍为
  2/2 行、4/4 分支。它不证明下面的双命中清理路径。
- `BPU-MBTB-018` 针对 `MainBtb.scala:73-84` 的 S0 per-bank startPc／position
  轮转。此前同一起点多 entry、页末过滤、单项起点后移分别有用例，但没有
  在普通页内用两个相邻对齐起点检查共享预测窗口。新用例从两个真实 cold
  metadata 分别训练，断言前一起点同时返回位置 5／13 的不同 bank entry，
  后一起点只返回后者且位置映射为 5，再回到前一起点检查两项均保留。
  三个功能 bin 均在对应输出断言后采样并于完整回归闭合；MainBTB 原始
  2/2 行、4/4 分支不变，无法区分这种地址轮转和位置重映射组合。
- `BPU-MBTB-019` 已为 `MainBtbAlignBank.scala:294` 的同位置双命中清理
  找到合法可观察时序。只连续重放真实 cold metadata 时，entry write buffer
  对同 set/tag 的 shadow 合并，公开输出仍只有一个 way；持续运行的 S2 也会
  立即清理短暂重复。新用例先把原 entry 写入 SRAM，再用另一物理 set 的
  合法训练替换原 shadow，但保留原 SRAM entry；随后使用原 cold metadata
  和不同 target 重放，agent 暂缓 S2 flush。公开预测和 metadata 均出现
  两个同位置有效 way、两个不同 target；恢复 S2 后只保留低 way，另一 set
  的 entry 仍命中。四个功能 bin 只在对应输出断言后采样。write-buffer
  shadow 替换是结合 RTL 合并/替换逻辑与该输出序列作出的解释，不是把内部
  buffer 状态伪装成公开观测。MainBTB 仍为 2/2 行、4/4 分支，这些
  分母本身并不能证明此路径。
- 集成 BPU 在 prediction 背压时收到 redirect，agent 先观察未被接受的旧
  s1 payload，再在 ready 仍为低时观察 redirect PC 替换该 payload，最后
  按 monitor 接受时间戳检查恢复 ready 后的首个新 transfer。这一交叉场景
  对应 `BPU-INT-010`；它补的是原功能矩阵遗漏的控制交互，并非为了追
  `BpuDut.v:1882` 已证不可达的分支。完整回归后集成 BPU RTL 仍为
  6/6 `v_line`、13/14 分支，原始覆盖数字如实保留。功能覆盖率增加
  `redirect_stalled` bin，仅在检查新 PC 的背压期 payload 和首次接受的
  transfer 后采样；原 cold/disabled bins 也改用实际断言过的结果。
- MicroBTB useful counter 的 not-taken 老化、失效、taken 重分配和正饱和，
  使 RTL 分支从 80/84 提升到 82/84；对应 `BPU-UBTB-009/010`。
- MicroBTB 汇总 covergroup 原把 `trained`×`miss` 采样于未训练的冷 PC，
  虽然 `BPU-UBTB-004` 独立用例已有真实 not-taken 训练。现两处共用
  `train_not_taken` 事务辅助函数，汇总采样前也发送训练并断言仍 miss。
  固定种子全量回归的 4/4 行、82/84 分支与功能点总数均不变；修正的是
  功能覆盖 bin 的证据前提。
- MicroBTB 改由 xreactor 的异步单周期 driver 连续提交训练。相邻的 taken
  分配与 not-taken 老化接受事件间隔一周期，后续 hit→miss 行为验证了
  t0/t1 更新旁路；该用例的 RTL 记录中 `t0_hitT1Update` 有 6 次切换，
  `UbtbDut.v:1785` 的 `if` arm 命中 4 次。剩余两个分支没有因此闭环；
  对应 `BPU-UBTB-011`。
- 再用五笔相邻训练把 useful counter 从 3 降到 0，紧接不同 target 的
  taken 训练；新 payload 和后续三次 not-taken 才失效的行为证明重新初始化。
  `UbtbDut.v:1788` 从未命中变为命中，MicroBTB RTL 行达到 4/4；
  对应 `BPU-UBTB-012`。
- MicroRAS 正常 S1→S2→S3 推进与清除，使 8 个 RTL 分支全部命中；
  对应 `BPU-URAS-008`。
- MicroRAS 中性 S2 override 下保留较老的 S3 push，补上 `.v:472`；
  另用有／无 S3 pending push 的对照检查 S2 override pop，而非依赖旧输出
  判断配对行为；对应 `BPU-URAS-009/010`。
- MicroRAS 相邻周期送入普通 S1 pop 与中性 S1，在较老 S3 push 尚在时，
  中性 S1 输出 main RAS top；pending pop 消退后又回到 S3 CALL 的 return
  address。两个地址不同，可从输出区分路径；agent 的 `stream()` 把连续驱动
  封装起来，功能覆盖率新增 `s1_pop_s3_push` bin，对应 `BPU-URAS-011`。
  该用例的 `.dat` 中 `.v:493` 仍为 0，因此不能把 RTL 行覆盖数字写成已命中。
- RAS 的 2/2 RTL 行和 6/6 分支在新增 `BPU-RAS-009` 前已命中，但既有
  `BPU-RAS-003/007` 分别只覆盖两级 LIFO 与单次回滚。新用例构造 A→B→C
  三个不同返回地址，保存 B 的真实 redirect metadata，回滚后检查 top=B，
  再连续 pop 得到 A 和初始空栈 top。push 三次／restore／pop 两次六个
  功能 bin 均在断言后采样；完整回归 RTL 原始 2/2、6/6 不变。这是功能点
  矩阵补缺，不是为刷已满的行分母重复调用单条路径。
- MicroTAGE S2/S3 override 的提前恢复周期和 overrideStartPc 重新算 tag，
  使 RTL `v_line` 从 4/6 到 6/6、分支从 12/16 到 16/16；
  对应 `BPU-UTAGE-008/009`。普通 lookup 含驱动 launch 的三周期结果不能
  代替 override 后一周期的恢复结果，因此由 agent 单独封装这个观测点。
- ITTAGE 在 primary counter 降至 0 且 alternate 有效后继续训练，
  关闭最后一个 alternate-provider RTL 分支；对应 `BPU-ITTAGE-007`。
- AheadBTB 条件方向计数器双向饱和、相邻 set 隔离，以及同一 bank/set
  的四个 way 逐一更新，补上最后 5 个未命中的唯一 `.v` 行；对应
  `BPU-ABTB-010/011`。其中最后一个 bank 3/set 30/way 2 行此前不可达，
  是因为 lookup agent 未驱动 RTL 所需的 `normalPathHist` 折叠字段；
  agent 现将该 4 位索引 hash 作为 transaction 字段绑定。
- 相同 PC 搭配四种折叠路径历史后，实际选中四个 bank，分别训练不同目标并
  回读验证互不混淆；对应 `BPU-ABTB-012`。AheadBTB 功能覆盖率新增 bank
  和零／非零历史 bins，关闭新增 bins 后仍不意味着所有 set/way 组合已测。
- 相同 PC 的较早／较晚两个条件分支可占不同 way。训练较晚位置的 taken
  分支使较早分支从 taken 变为 not-taken，但保留双方的 target；反向训练
  较早位置只恢复它自己的方向，较晚分支保持 taken。该位置顺序交互对应
  `BPU-ABTB-013`，独立 covergroup 的 suppression/recovery 两个 bin 均
  命中。完整回归的 AheadBTB RTL 分支从 3682/4112 提升到 3710/4112：
  `SaturateCounter.scala:42` 关联的未命中点少 21 个，
  `AheadBtb.scala:269` 少 7 个；唯一 RTL 行仍为 2050/2050。
- 同一 bank 2/set 0 的四个条件 entry 分别老化到 not-taken，再分配第五个
  taken entry。用例检查新 entry 的方向计数器已重置为 taken、被替换项确实
  消失、三名幸存者仍为 not-taken 且 target 未变，对应 `BPU-ABTB-014`。
  完整回归的 AheadBTB 分支继续从 3710/4112 提升到 3738/4112；其中
  `SaturateCounter.scala:42` 关联的未命中点少 25 个，
  `AheadBtb.scala:269` 少 3 个。静态唯一行和 `v_line` 点数未变，说明这里
  补的是复制实例上的真实状态转换，不是新的源码语句。
- 持续向同一 bank/set 分配八个 entry，检查四个 way 都成为过 replacement
  victim，每次仅驱逐一项且最终四个最新 entry 保持正确 target/方向；对应
  `BPU-ABTB-015`。随后绑定此前未被 agent 驱动的 `bpuS2Override`、
  `bpuS3Override`、`overrideStartPc`：分别检查 S2/S3 恢复已保存预测在原 PC
  命中、改用另一 override PC 后重新匹配为 miss，且 metadata 有效；对应
  `BPU-ABTB-016/017`。独立恢复 covergroup 的四个 stage/result bin 均在
  断言后命中。完整回归相对上轮 3763/4112 增加 116 个 RTL 分支，达到
  3879/4112；唯一 RTL 行及 `v_line` 点数没有改变。
- 针对最高物理 setIdx=63，先以同一 PC 的四种路径 hash 分别训练四个 bank，
  检查 metadata、target 和跨 bank 隔离；再在每个 bank 连续分配八个不同 tag，
  断言四个 victim way 都被访问、每次只驱逐一项、最终驻留项不互相干扰；对应
  `BPU-ABTB-018/019`。最高 set 的普通分配与持续 replacement 使完整回归的
  AheadBTB `v_line` 从 2480/3074 到 2548/3074、分支从 3879/4112 到
  3896/4112。两个独立 covergroup 各自验证四个 bank 的相关 bin 均命中。
  但生成 RTL 中四个 `setIdx` 全 1 且末 way 的 `needReset` 分支仍报 0；
  即使覆盖了这些可观察的 replacement 行为，也不能直接宣称该内部条件已命中。
- 最高 set 的四 bank × 四 way 条件计数器分别从 taken 训练至 not-taken
  饱和、再恢复至 taken 饱和。每轮检查目标 entry 的方向/target 和其他
  15 个 entry 的方向/target，断言后采样 32 个 bank/way/转换 bins；对应
  `BPU-ABTB-020`。完整回归的 `v_line` 由 2548/3074 升到 2681/3074，
  分支由 3896/4112 升到 3901/4112。增强后的机器可读报告把剩余 393 个
  `v_line` 点全部定位为生成的 `else if` 条件之 `else` arm，即条件方向计数器
  尚未在相应复制实例执行的正向加一；其 Scala 来源均映射到
  `SaturateCounter.scala:41`。这是一种已在多个 set/bank/way 验证过的转换，
  不能据此虚构 393 个不同功能点；仍可按风险选择更多实例组合。
- 对 setIdx=63 的每个 bank，先把四个 resident 条件计数器训练至 not-taken
  饱和，再持续替换直至四个 way 都成为 victim；每次断言新 entry 立即 taken、
  旧 tag 消失，其他三个 entry 保持 not-taken 和 target，然后才采样相应的
  bank/way reset bin；对应 `BPU-ABTB-021`，16 个 bin 全部命中。完整回归
  的 AheadBTB 分支从 3901/4112 升到 3923/4112，`v_line` 点数保持
  2681/3074。四个最高 set/末 way 分支的逐用例 `.dat` 仍为 0，保留原值。
- ITTAGE 使用每次预测返回的 metadata 逐次真实误预测，直至进入
  `allocate.valid=0`，再连续 260 次无分配误预测；用例每次检查该前提，
  最终检查 provider 与最新 target 保持。该用例自身的 `.dat` 中
  `IttageDut.v:945` 命中 1 次，使 ITTAGE 唯一 RTL 行达到 4/4；对应
  `BPU-ITTAGE-008`。功能覆盖模型新增 allocation 可用／阻塞／不适用 bins。
  交错历史场景纠正了原先晚一周期的 scoreboard 采样点；因此候选耗尽的
  训练次数改由每次真实返回的 `allocate.valid` 决定，不再写死为三次。
- ITTAGE 的 `s1_foldedPhr` 同时参与表索引与 tag，旧 agent 从未提供非零历史。
  `BPU-ITTAGE-009` 使用相同 PC、两种历史分别训练不同 target，并按 A/B/A/B
  连续提交查询，确认命中与 target 不串扰。agent 将历史与上一拍 S0 PC 对齐，
  scoreboard 在接受事件后三周期采样；历史 coverpoint 的零／非零 bin 均在
  断言后命中。原先零命中的 `io_s1_foldedPhr_hist_12_foldedHist[2]` 已翻转。
  折叠历史与训练 slot 场景合并后，ITTAGE RTL toggle 达到 3309/3309；
  这是活动度信息，不等价于所有输入组合均已验证。
- ITTAGE RTL 从 `t1_train.branches` 中选择唯一有效的 taken 间接跳转，
  旧 agent 只能驱动 `branches[0]`。`BPU-ITTAGE-010` 将分支放在 slot 4，
  使用跨目标 region 的地址并在训练后回读 target；agent 负责填充其余无效
  slot，测试用例不接触裸 IO。功能覆盖率新增训练 slot 的 none／first／later
  bins，均在断言后命中。该场景触及了原先零翻转的 slot 4 target 位；
  ITTAGE 行/分支仍为 5/5、34/34，说明覆盖数字原先没有表达这一遗漏。
- MicroTAGE 的 `normalPathHist` 决定 A0 readIndex、`s1PathHist` 决定 A1 tag。
  `BPU-UTAGE-010` 为相同 PC/position 的两种历史分别分配，再把一侧 counter
  训练至 not-taken，检查另一侧仍 taken，并交错提交 A/B/A/B 请求。原先同拍
  驱动 A0/A1 上下文、在接受事件后三周期采样的 agent 会把不同请求对错位；
  分级对齐并改为接受事件后两周期采样后，用例和独立 driver 契约测试通过。
  历史 coverpoint 的零／非零 bin 均命中，原先零命中的
  `io_s1PathHist_hist_18_foldedHist[3]` 已翻转，MicroTAGE RTL toggle 为
  3495/3495。两项场景均未改变已满的行／分支计数，说明原始 100% 也可能
  遮蔽历史隔离和流水线对齐的功能缺口。
- AheadBTB 原背靠背用例只检查有有效 entry，不检查该 entry 属于哪笔 PC。
  `BPU-ABTB-022` 用条件／直接／间接三种不同 PC 的前向与反向连续流，逐笔
  断言 position、type、target；`BPU-ABTB-023` 用相同 PC、四种路径历史的
  前向与反向流，逐笔断言 bank mask 和 target。两个场景暴露了原 agent 将
  S0 的 `startPc` 与 S1 的 `newStartPc` 同拍发送，以及 scoreboard 晚一周期
  采样的问题。分级对齐后用例、独立 encoder 契约和 AheadBTB 全套测试通过。
  加入内部 set 16 场景前的完整回归中，AheadBTB `v_line` 为 2669/3074、
  分支为 3943/4112；
  相比修正前，复制计数器行点少 12 个命中、分支多 20 个命中。修正改变了
  查询／训练 metadata 的实际时序和激励轨迹，覆盖计数不保证单调；
  当时的 405 个剩余行点全部映射到 `SaturateCounter.scala:41` 的正饱和判断／
  计数更新复制路径。
- `BPU-ABTB-024` 根据该复制矩阵选中 bank 3／内部 set 16：此前四个 way
  的正向加一 `v_line` arm 全部未命中。用例逐 way 将条件计数器训至负饱和，
  再恢复到正饱和，每次检查其他三个 way 的方向和 target；逐用例 `.dat`
  的 `AbtbDut.v:16576/16591/16606/16621` 四个目标 arm 均记录 2 次命中。
  当时未固定种子的完整回归中，AheadBTB 行点由 2669/3074 变为
  2673/3074，分支由 3943/4112 变为 3966/4112；功能覆盖率新增八个
  way／转换 bin，均在行为断言后命中。这个历史绝对数字不可与当前种子基线
  相减；四个目标 arm 在当前固定种子的完整回归中仍已命中。
  固定种子下又将同一功能点扩展到 bank 1／物理 set 34 四路。逐用例与此前
  完整回归的未命中点比对，新增命中 `AbtbDut.v:9970/9974/9985/9989/
  10000/10004/10015/10019` 八个行点；每路均先断言负饱和，再断言正向
  恢复，最后回读两组 bank/set resident 的方向、target 和路由元数据。
  完整回归由 1544/3074 行点、1722/4112 分支增至 1552/3074、1731/4112；
  这只是两个代表性几何的行为对照，不把其他复制点误算为独立功能要求。
- `BPU-ABTB-030` 在已做计数双向训练的 bank 1／set 34 进一步补上替换
  状态交叉：四路条件 entry 分别老化到 not-taken 后逐一成为 victim；每笔都
  检查新 entry 立即 taken、旧 tag 消失、其余 resident 保持 not-taken 与
  原 target，另有 bank 3／set 16 的 taken 哨兵保持不变。四个 victim-way
  bin 和跨 cell 哨兵 bin 均在断言后采样。逐用例与上轮全回归的未命中点
  比对没有新增原始行／分支，完整回归 AheadBTB 仍为 1552/3074 行点、
  1731/4112 分支。该轮 Verilator 5.026、`--coverage -O3` 以 picker wrapper
  顶层独立生成的 C++ 中，`AbtbDut.v:10010` 的 `__Vcoverage[9103]` 检查位于
  `nba_sequent TOP__1`，而同一 bank/set/way 的 `_needReset_T_2044`、
  `_needReset_T_1581` 计算和 `takenCounter_1_34_3_value = 2` 更新位于
  较晚执行的 `TOP__14`；逐用例 `.dat` 的 `:10010 if` 仍为 0。与最高 set
  的同类情形一致，这是原始分支的相位归因限制，不应反推可观察替换行为缺失。
- `BPU-ABTB-024` 又增加一个**不新增功能点 ID**的相邻 set 场景：同一
  bank 1 的 set 34 与 set 35 各填满四路条件 entry，先将 set 34 四路保持
  not-taken，再逐路将 set 35 老化至 not-taken 并恢复 taken。每次转换后
  回读八个 resident 的方向、target、setIdx 与 bankMask，避免只刷生成
  计数器而没有跨 set/way 隔离断言。逐用例 `.dat` 中原先零命中的
  `AbtbDut.v:10030/10034/10045/10049/10060/10064/10075/10079`
  分别命中；八个 set35 way×方向 bin 与相邻 set 保持 bin 均闭合。
  固定种子完整回归由 1552/3074 行点、1511/2050 唯一行、1731/4112
  分支增至 **1560/3074、1515/2050、1742/4112**。这八个行点仍是
  既有计数转换在新物理实例上的复制，不代表新增八项设计功能。
- `BPU-ABTB-033` 将相邻索引场景延伸到物理 setIdx **63→0 回绕**，
  同 bank 2 的两个起始 PC 仅相差 2 字节。set 63 的条件 entry 先老化并
  保持 not-taken；set 0 四路逐路老化、恢复，每次都回读五个 entry 的
  方向、target、setIdx 与 bankMask。逐用例覆盖文件命中原先缺失的
  `AbtbDut.v:11775/11790/11805/11820` 四个 set-0 正向更新 arm；
  八个 way×方向 bin 与邻居保持 bin 均在断言后闭合。固定种子全量合并
  从 1560/3074 增至 **1564/3074** 行点；唯一行仍为 1515/2050、
  分支仍为 1743/4112。这四点是已插桩静态行的另一 arm，不能误写为
  四条新增唯一源码行或新的设计功能。
- 2026-10-07 固定种子回归将同一 `BPU-ABTB-033` 扩至 bank 1/2
  同时驻留：两套 set 63 哨兵保持 not-taken，set 0 共八个物理 way
  逐路老化与恢复；每次变化回读两 bank 十项的方向、target、way、
  setIdx 和 bankMask。功能覆盖现为 16 个 bank×way×方向转换 bin、
  两个跨 bank 保持 bin 和一个 set 63 保持 bin，完整回归全部命中。
  相对扩展前全量回归，AheadBTB `v_line` **1653→1660/3074**、
  唯一行 **1548→1551/2050**、分支 **1847→1856/4112**；净增的
  7 个行点恰为 bank 1/set 0 四个正向臂与三个减向选择臂，该物理
  cell 的四个 way 已无计数器行点缺口。bank 0/3 的 set 0 此前已
  闭合，因此没有机械扩展到那两个 bank。
- `BPU-ABTB-043` 同时填充四个历史 bank 的物理 set 2/3/4；每个 bank
  的 set 3 保留四路条件项，set 2/4 各留一个 not-taken 哨兵。逐个
  bank/物理 way 老化并恢复 set 3，所有转换后回读 24 项的方向、唯一
  target、way 和 bank/set 路由；32 个 cell×方向 bin 与哨兵保持 bin
  在断言后命中。固定种子全量回归使 AheadBTB `v_line`
  **1660→1687/3074**、唯一行 **1551→1562/2050**、分支
  **1856→1899/4112**。新增的 27 个行点正是 set 3 的 16 个正向更新
  arm 与 11 个减向选择 arm；set 3 目前没有计数器行点缺口，但这不
  代表所有 set 或所有行为都已验证。
- `BPU-ABTB-044` 在四个历史 bank 的物理 set 4 各填满四路条件项并
  老化为 not-taken；set 3/5 各留一个同样老化的哨兵。逐 bank 训练
  第五个不同 tag，断言恰好一个旧物理 way 消失，新项从 taken 起步，
  全部 24 项的 target、方向、way 与 bank/set 路由在每步回读；四 bank
  与双侧保持的功能 bin 均在断言后闭合。固定种子完整回归使 AheadBTB
  `v_line` **1687→1697/3074**、唯一行 **1562→1572/2050**、分支
  **1899→1933/4112**。新增 10 个行点全是 set 4 的减向选择臂；
  四 bank 的 set 4 仍有 16 个正向更新臂缺口，不能声称该 set 已全覆盖。
- `BPU-ABTB-045` 对照上述满组替换后的同一双侧老化邻域：旧项在负饱和
  状态逐路恢复，新项也先老化为 not-taken 再恢复，避免仅凭其初始 taken
  误判已执行正向更新。每步回读 set 4 的 16 项及 set 3/5 的 8 项，检查
  物理 way、目标、方向和 bank/set 路由；16 个 bank×way bin 与替换／幸存
  类型 bin 均在断言后闭合。固定种子完整回归使 AheadBTB `v_line`
  **1697→1713/3074**，新增点恰为 set 4 的 16 个正向更新臂；矩阵已无
  set 4 缺口。唯一行仍为 1572/2050，分支仍为 1933/4112；不能把
  16 个复制实例称为 16 项独立功能。
- `BPU-ABTB-046` 以同一 PC 的 16 个折叠历史值路由到物理 set 48–51 ×
  四 bank，分别安装不同条件目标，逐格老化／恢复后回读整个网格的目标、
  物理 way、方向和路由。16 个 route bin 与 32 个方向转换 bin 在断言后
  闭合。固定种子全量回归使 AheadBTB `v_line` **1713→1737/3074**、
  唯一行 **1572→1580/2050**、分支 **1933→1972/4112**；新增 24 个
  行点均属高 set 的计数器复制实例，而非 24 个新功能点。
- `BPU-ABTB-047` 在上述全部 16 个路由格中各驻留四个位置和不同目标。
  每格先用一次 not-taken 反馈使四路转负，再按位置逐路恢复 taken；每次
  都回读 16 格完整配置，要求其他路由的 target、way、方向不变。64 个
  route×way 功能 bin 在断言后闭合。固定种子全量回归使 AheadBTB
  `v_line` **1737→1810/3074**、唯一行 **1580→1605/2050**、分支
  **1972→2062/4112**。新增 73 个行点是 48 个正向臂和 25 个减向选择臂；
  高 set 48–51 的 64 个计数器格子现在无行点缺口，但功能点只新增一个。
- `BPU-ABTB-048` 复用上述高 set 全路由四路配置，逐格以第五个更后位置
  触发满组替换。每次确认唯一 victim 消失、新项 taken、三个幸存旧项
  not-taken，回读其余 15 格所有位置、目标、way 与方向；16 个路由 bin
  和隔离 bin 均在断言后闭合。固定种子完整回归 AheadBTB 仍为
  1810/3074 `v_line`、1605/2050 唯一行、2062/4112 分支；这是
  已插桩点不变但新增高 set bank×set×替换行为证据的实例。
- `BPU-ABTB-034` 针对 `BPU-ABTB-013` 的两位置优先级与
  `BPU-ABTB-014` 的满组替换尚未交叉这一功能缺口：在 bank 1/set 36
  的同一 PC，以位置从后到前填满四路条件分支，确保四项最初都 taken；
  再训练第五个更后位置的 taken 分支。断言恰好一项被替换、新项立即 taken，
  三个幸存旧项因位置优先级变为 not-taken、target 和 way 不变；再训练最早
  幸存项，仅它恢复 taken。四格功能覆盖在对应断言后命中。逐用例命中
  `AbtbDut.v:10090/10105/10120/10135` 四个 set-36 减向选择臂；
  其中前三个在原全量基线尚未命中。固定种子全量合并从 1564/3074
  到 **1568/3074** 行点，1515/2050 到 **1518/2050** 唯一行，
  1743/4112 到 **1748/4112** 分支；净增的另一行点是同 set 一路的
  正向恢复。这个结果证明原功能清单确实遗漏了位置优先级×替换交互，
  但不意味着其他数百个物理计数器实例各代表一个新功能。
- `BPU-ABTB-035` 进一步检验上述交叉并非只对同一个 replacement victim
  成立。预置 0–3 个同 bank/set 的不同 tag 改变替换历史，再分别填满同 PC 的
  四个条件位置并训练第五个更后位置的 taken 分支；四次选出的 victim way
  恰为 0、2、1、3。每次断言新项方向和 target、恰好一项旧位置被驱逐、
  三个幸存项方向均被抑制而 target/way 不变，旧 tag 不再命中，最后采样
  `victim_way` 四格。当时完整固定种子回归为 241 PASS、4 strict XFAIL，
  AheadBTB 仍是 1568/3074 行点、1518/2050 唯一行及 1748/4112 分支；
  故这是有独立行为价值但不增加原始 RTL 覆盖数字的用例。
- `BPU-ABTB-036` 从 RTL 的 `needDecrease = updateThisSet && isCond &&
  (!taken || taken && posBefore)` 与 `needIncrease = updateThisSet && isCond &&
  taken && posEqual` 发现未列入原功能清单的交叉：同 PC 四路同时命中时，
  一次 not-taken 反馈会降低全部四路，而 taken 反馈仅增加位置相同项、降低
  更早项、保持更晚项。新场景在 bank 0/set 0 逐步断言四路方向、target、way，
  用更早项需两次 taken 才恢复、更晚项一次就恢复证明隐藏计数状态，并依次
  训练全部四个位置。五个功能 bin 均在输出断言后命中。固定种子全量合并
  从 1568/3074 到 **1573/3074** 行点，1518/2050 到 **1520/2050**
  唯一行，1748/4112 到 **1753/4112** 分支；新增三个正向臂与两个减向选择
  臂，bank 0/set 0 的剩余计数器行点由五个降为零。这是行为需求与物理覆盖
  缺口一致的实例，不能外推为其余未命中点都是独立功能缺口。
- `BPU-ABTB-037` 把 `t1_condMask` 的条件类型过滤与同 PC 多位置训练相交：
  bank 3/set 0 四路中分别放置条件、直接、条件、间接分支，按位置逆序训练以
  避免建表过程老化较早项。重复 not-taken 后，只有两个条件项变为不跳转，
  直接与间接项保持 taken；再逐步恢复条件项，第一笔 taken 仍为 not-taken，
  第二笔转为 taken，从输出证实已达强负状态。最后修正间接目标，断言其
  target 独自改变，而两项更早条件分支按位置规则被抑制，全部四项的
  type/way/target 始终对齐。五格功能覆盖在断言后闭合。固定种子全量合并
  从 1573/3074 到 **1577/3074** 行点、1520/2050 到 **1522/2050**
  唯一行、1753/4112 到 **1757/4112** 分支；两个条件 way 各命中一个正向臂
  与一个减向选择臂，两个非条件 way 在本场景下不应触发计数器更新。
- `BPU-ABTB-038` 接着验证这些非条件 way 在替换为条件分支后，计数器必须
  重新以弱正状态工作。四种替换历史遍历四个 victim way，并让条件、直接、
  间接三种旧类型均成为 victim；新项一次 not-taken 后不再预测 taken，
  一次 taken 后恢复，幸存项的 type/position/target/way 始终不变。
  十个功能 bin 在断言后闭合。固定种子全量回归从 1577/3074 到
  **1581/3074** 行点、1522/2050 到 **1524/2050** 唯一行、
  1757/4112 到 **1759/4112** 分支；bank 3/set 0 原先两个非条件 way
  的正向及减向选择臂共四点全部命中。当时剩余 1493 行点仍可映射到其他
  bank/set/way 复制格子，这个增量有明确的“类型×替换×计数重置”功能对应。
- `BPU-ABTB-039` 从固定种子矩阵中选择 bank 3/set 1：四个 way 都已
  命中减向选择臂，唯独正向计数更新臂未命中。此前 hash-set 用例只给
  不同 set 各放一个 entry，set 1 替换用例只逐路老化／替换；同 PC
  多位置反馈则只在 set 0 验证。新场景把同 PC 的混合类型四路放在
  hash 3 选中的 set 0，四个条件位置放在 hash 7 选中的 set 1；后者
  一次 not-taken 变为全负，再逐路 taken 恢复，持续回读两个 set 的
  全部方向、类型、target、way 和路由。七格功能覆盖在断言后闭合。
  固定种子全量回归将这四个正向臂全部命中，AheadBTB 行点从
  1581/3074 到 **1585/3074**；它们所在静态 `.v` 行的另一臂此前已命中，
  故唯一行仍为 1524/2050，分支仍为 1759/4112。当时剩余 1489 行点全部
  继续映射到其他物理格子，不能把它们逐个当成新功能需求。
- `BPU-ABTB-040` 区分 AheadBTB→MicroTAGE 旁路中的实时 S1
  `fastPositions` 与 S2 `result`。此前单路稳定 PC 用例只检查过一项
  sideband，在多路交错时不足以证明 `result` 与每笔 S2 预测关联。
  新用例用 hash 3/7 在同一 PC 上分别布置弱正混合类型与饱和强负条件
  四路配置，连续六笔交错查询；逐路核对旁路的 valid、position、type、
  RAS action、taken、strong bias 和主预测／way，五个功能 bin 均在断言
  后命中。当时固定种子全量回归仍为 1585/3074 行点、1524/2050 唯一行、
  1759/4112 分支；这是新的旁路事务关联证据，而非复制计数器刷点。
- `BPU-ABTB-041` 从矩阵选择 bank 0/1/2 的物理 set 1：各有四个正向更新臂
  尚未命中，且分别有 3/3/2 个减向选择臂缺口；bank 3/set 1 则作为已
  覆盖的对照。新场景在同一 PC 用四种 path hash 选中四个 bank，各 bank
  放四个条件位置与不同目标；逐 bank 一次 not-taken 老化所有位置，再按
  位置逐路 taken 恢复四个物理 way，每次回读四个 bank 的方向、target、way
  与路由。20 格功能覆盖全部在输出断言后闭合。固定种子全量回归命中
  12 个正向臂、8 个减向选择臂，行点 **1585→1605/3074**、唯一行
  **1524→1532/2050**、分支 **1759→1781/4112**；四个 bank 的 set 1
  现无映射计数器缺口。当时剩余的 1469 行点仍按物理格子登记，不能逐格等同
  新功能点。
- `BPU-ABTB-042` 从尚有缺口的物理 set 2 选取四个历史 bank，而非沿用
  set 1 的单纯方向翻转。各 bank 同一 PC 先填满四个不同条件位置，再用
  第五个更后位置触发一次满组替换；只允许选中 bank 的一个 victim 消失，
  三个幸存条件项受位置优先级抑制，其他 bank 的路由、way、方向与 target
  不变。再次 not-taken 老化后逐位置恢复四个物理 way：旧幸存项需要两次
  taken 反馈，新项只需一次，每拍都回读所有 bank。24 格功能 bin 在输出
  断言后闭合。固定种子全量回归使 set 2 的 16 个正向臂与 7 个减向选择臂
  命中，AheadBTB 行点 **1605→1628/3074**、唯一行 **1532→1539/2050**、
  分支 **1781→1812/4112**；set 2 四个 bank 均已无计数器行点缺口。
  其余 1446 个行点仍全部映射到物理格子，不等于 1446 个独立功能需求。
- `BPU-ABTB-032` 从未翻转的目标高位和 `EnableTargetFix=false` 设计选项
  发现原功能点清单缺少早级局部目标区域契约。生成 RTL 明确拼接
  `s2_state_startPc_addr[49:22]` 与 entry 低 22 位，边界是 **4 MiB**；
  先前仅凭 Scala 参数注释推测 8 MiB 不正确。新用例用真实 fastTrain
  metadata 分别断言同区域目标完整返回、上溢时返回 `0x40400100`、
  下溢时返回 `0x40bfff00`，三个功能 bin 在输出断言后采样。这个
  局部 wrap 是配置行为，不等于集成 BPU 已对错误高位作后级修正。
  新用例合并后 AheadBTB 行点不变，分支增 1，归于某个复制的 reset
  实例；不能把它误写成目标高位修正分支已命中。
- `BPU-ABTB-025` 验证同 PC、同 bank 下，折叠路径 hash 的高两位选中四个
  不同 set，训练的四个 target 互不混淆；`BPU-ABTB-026` 在 hash 选中的内部
  set 1 中，将四路条件 entry 老化至 not-taken 后逐路替换，并检查新 entry
  立即 taken、旧 tag 消失、幸存 entry 的方向/target 不变。两组功能 bin
  均在断言后达到 100%。固定种子控制运行（排除这两个新用例）为
  1518/3074 行点、1674/4112 分支；加入后为 1520/3074、1685/4112。
  未固定种子运行曾显示更大的行点差值；逐用例 `.dat` 并不支持将其全归于
  两个新场景，因此不采用那个差值。
- `BPU-ABTB-027` 针对固定种子下仍未触发的中段计数器复制点，选中物理
  set 31/32 的索引位边界以及 bank 0/2。四个 cell 各填满四路条件分支，
  逐项老化至 not-taken、恢复 taken，并在每次状态变化后回读所有 16 个
  resident 的方向、target、set/bank 元数据；32 个 cell×方向 bin 均在
  断言后采样。新增场景后的完整回归相对 1520/3074、1685/4112 的固定种子
  基线，达到 1544/3074 行点、1721/4112 分支、1507/2050 唯一行；
  净增 24 个行点分别落在 16 个正向更新 arm 和 8 个减向选择 arm。
  这说明其余大量零计数主要是尚未访问的 bank/set/way 状态复制，
  不应为每个副本建立单独需求。
- 2026-10-07 的固定种子回归把同一 `BPU-ABTB-027` 扩展到 bank 1/3，
  使物理 set 31/32 的四个 bank × 四个 way 共 32 项同时驻留。逐项老化、
  恢复并在每次转换后回读全部 resident；功能覆盖由 32 扩至 64 格且
  64/64 命中。相对扩展前的完整回归，AheadBTB 原始 `v_line`
  **1628→1653/3074**、唯一行 **1539→1548/2050**、分支
  **1812→1847/4112**。新增 25 个行点恰为 bank 1/3、set 31/32
  的 16 个正向臂和 9 个减向选择臂；该 16 个物理格子已无计数器
  行点缺口。剩余 1421 个行点仍按格子登记，不新增逐格功能 ID。
- `BPU-ABTB-028` 复用同一次真实 cold 查询得到的 metadata 训练相同
  PC/position 两次，第二次因旧 metadata 尚不含新 way 而在另一 way 分配；
  bank 0/2 都先从输出观察到两个同位置有效项。S2 的 multi-hit 检测命中
  `AbtbDut.v:21639`，但单端口 SRAM 读优先，持续查询会暂时阻塞清理写回。
  agent 停止读请求并给四项写缓冲留出排空窗口后，输出只剩一个正确的
  方向/target。四个 bank×阶段功能 bin 均在断言后采样；固定种子完整回归
  从 1721/4112 增至 1722/4112 分支，行点仍为 1544/3074。
- `BPU-ABTB-029` 在不停止 bank 3 连续读取的情况下，向同一 bank 的
  set 0/1 各送入一笔真实 fastTrain。两处在持续读压下仍 miss；排空四项
  写缓冲后分别命中自己的 target/set。四个 set×待写/已写 bin 均在输出
  断言后采样。当时完整回归的 AheadBTB 行点与分支仍为 1544/3074、1722/4112：
  已命中的读/写仲裁 RTL 点不等于“两笔待写不丢失”已被旧用例验证。
- `BPU-URAS-012/013` 将较老 S3 pop 分别与中性 S1、中性 S2 override
  相遇，再将较新的 S2 push 压在 S3 pop 上方。用不同于 CALL return address
  的 main RAS top 检查优先级，S2 push 消退后预测无效，S3 fire 后恢复；
  对应三个新功能 bin 均在输出断言后采样。固定种子下 MicroRAS 行点从
  15/21 到 17/21；新增用例的 `.dat` 命中 `UrasDut.v:474/495`，另四点仍为零。
- `BPU-URAS-014` 用相邻周期的 S1 pop／中性与 S2 pending push／pop
  建立 2×2 矩阵，逐格比较有效位、返回地址及下一周期状态。S2 push+S1 pop
  得到 main RAS top，S2 push+中性 S1 得到 CALL return address；S2 pop
  与两种 S1 操作均无可用预测，且中性 S1 的下一周期恢复 main top。
  四个组合 bin 均在断言后采样。该逐用例 `.dat` 的 `:482/:485 else/:491/:493`
  仍为 0，不将行为通过误写成原始 RTL 行覆盖命中。
- `BPU-TAGE-012` 让 TAGE agent 分别驱动预测侧的 MainBTB `baseConf` 和
  训练侧的两位 MainBTB counter。用例对比低／高置信度时的 `altConf`，再在
  正确 base 结果后检查弱 provider counter 与 fallback 状态；两个置信度 bin
  在断言后命中。该用例自身的奇数 selector 更新 arm 仍为 0，不能仅凭
  预测 metadata 宣称内部训练发生。
- `BPU-TAGE-013` 在同一 selector 桶保留一个未经训练的弱 provider，
  只训练另一分支的正确 taken 结果。原分支 counter、table 和 way 均未变，
  高置信度 base 查询却从 fallback 切换为 provider，直接检验选择器的
  跨 tag 反馈效果。`BPU-TAGE-014` 再用同 set 的真实分支流覆盖四张
  tagged table 的弱 provider：每次核对 `altConf=1`、counter 4→3→2、
  provider 未丢失及 fallback→provider。其逐用例 `.dat` 对原缺口
  `TageDut.v:3696/3716/3736` 分别计 7/5/1 次，功能覆盖率的
  table 0/1/2/3 bins 均在断言后采样。完整回归 TAGE 分支由 27/30 到
  30/30；这不代表所有选择器状态组合已穷尽。
- `BPU-INT-011` 在集成 BPU 中只关闭 MicroBTB/AheadBTB，保持已训练的
  MainBTB 有效；同一 PC 先得到 S1 not-taken，再由 S2 override 修正为
  taken 和训练目标。专用 covergroup 在两次输出断言后采样；逐用例 `.dat`
  的 `BpuDut.v:1880` 命中 1 次，首拍复位后集成 BPU 回到 6/6 行点。
- `BPU-MBTB-013` 在 MainBTB 的 TargetWidth=20 部分目标边界，分别断言
  同区域、向相邻区域上溢和下溢的完整目标回读；三格功能覆盖均在回读后
  采样。`BPU-INT-012` 再在集成 BPU 中禁用早级 MicroBTB/AheadBTB，
  证明 MainBTB 对跨早级目标区域的上下两个方向都能在 S2 修正并输出完整
  target。`BPU-INT-013` 则只保留 MicroBTB 早级：输入地址字段 `0x407fffe0` 训练
  目标 `0x40800100` 后，S1 输出 `0x40400100`，后续不产生正确目标。
  `MicroBtbParameters` 默认关闭 `EnableTargetFix`；
  `Bpu.scala:374` 的 S2 比较不含目标，`:396-404` 的 S3 MainBTB 比较只看
  `MaxBtbTargetWidth` 低位，无法发现高位差异。关闭 xfail 标记单独运行该
  用例，失败落在“未收到正确目标”的断言；正式回归保留 strict XFAIL。
  新增这些行为对照后 MainBTB 仍是 2/2、集成 BPU 仍是 6/6 RTL 行点，
  因而两者的行覆盖率不能代替跨级目标一致性检查。
- `BPU-INT-014` 给上述缺陷增加可通过的低位对照：先训练间接目标
  `0x40002340`，关闭 MicroBTB 后仅将 MainBTB 更新为同一高位区域的
  `0x40002540`，再重新开启 MicroBTB。S1 返回旧目标，S3 明确产生
  override 并返回新目标，功能覆盖的 S1-old/S3-new 两格均在断言后采样。
  它证明已有 S3 比较路径在低位差异下能工作，故高位跨界 XFAIL 不是
  “未建立纠错场景”，而是比较宽度不足；BPU 原始行点仍为 6/6。
- `BPU-INT-015` 补上集成 AheadBTB 的实际学习路径，而非只依赖 AheadBTB
  单模块测试。MicroBTB 全程关闭；自循环分支先由 MainBTB 在 S2 修正，
  启用 AheadBTB 后让 S3 fastTrain 多次产生并暂停预测读流排空写回，同一
  PC 随后在无 override 的 S1 返回目标；重新关闭 AheadBTB 后又由 S2 修正。
  S2／S1／关闭后 S2 三格功能 bin 均在输出断言后采样。完整回归 BPU 仍为
  6/6 行点、13/14 分支，说明这些计数本身也不能证明早级表已学到数据。
  两个早级表同时保持不同预测时的来源优先级另由 `BPU-INT-017` 给出
  同一背压 S1 的行为证据；fastTrain 会使 MicroBTB 目标收敛，因此用例
  限制短恢复窗口并在关闭 AheadBTB 后回读原目标 A。
- `BPU-INT-016` 在集成路径先让 MicroBTB 学到间接目标 A，再关闭它，
  更新 MainBTB 并由 S3 fastTrain 让 AheadBTB 学到自循环目标 B；两者
  分别启用时均在 S1 返回各自目标。关闭 AheadBTB/MainBTB 后重新开启
  MicroBTB，目标 A 仍在，说明禁用期间的 B 向训练没有覆盖它。
  三阶段还分别核对 S3 perf echo 的 S1 来源为 UBTB／ABTB／UBTB；
  功能 bin 均在输出和来源断言后采样。BPU 原始行/分支仍是 6/6、13/14。
  这项隔离本身不证明双有效仲裁：此前离开自循环再重定向改变折叠历史，
  当笔 AheadBTB metadata valid=0；在 S1 背压后才开启 MicroBTB 也不
  会给旧请求补做 S0 读。`BPU-INT-017` 改为不重定向，让两个来源在新
  S0 请求前均启用，并对该笔 S1 背压：AheadBTB 仍选目标 B；关闭
  AheadBTB/MainBTB 后同一 S1 露出 MicroBTB 的不同目标 A。三格功能
  bin 在 AheadBTB 有效、双使能选择、同 S1 源切换断言后采样。
- `BPU-INT-019` 在集成 BPU 的边界 PC `0x407fffe0` 先建立并核对真实
  ABTB 来源的 S1 自循环目标。暂停预测读取以让 MainBTB 写入跨 4 MiB
  区域的新间接目标 `0x40800100`，恢复后同一接受周期的 S3 override
  输出完整新目标，metadata 仍回显 ABTB 来源及旧 S1 目标。旧／新目标
  低位也不同，因此这是后级低位差异修正和流水线配对的行为对照；三格
  功能 bin 在输出和来源断言后采样，不能代替 `BPU-INT-018` 要求的
  “仅高位错误”的 ABTB 局部 wrap 修正。
- `BPU-INT-018` 现以 `0x407fffe0 → 0x40800100 → 0x407fffe0` 两笔
  间接分支形成自然循环，先在关闭 ABTB 时分别断言 MainBTB 的双向 S2
  完整目标。启用 ABTB、运行并暂停 S0 读取以提交 fastTrain 写回后，返回
  分支的 S1 输出 `0x40bfffe0` 而非 `0x407fffe0`，同笔 S3 perf 来源确认为
  ABTB。两目标低 22 位相同，后级没有完整目标修正；仅这一末端判定是
  strict XFAIL，前提失效是普通失败。功能覆盖 5 格中前提 4 格命中，
  `later_full_target` 为 0。BPU 原始 RTL 行/分支仍为 6/6、13/14，
  因而满行覆盖和近满分支覆盖掩盖了这项真实功能缺陷。
- `BPU-ITTAGE-011` 将 `io.enable` 从逐笔 lookup 字段移到持久控制驱动。
  复用同一份 cold 预测 metadata：关闭期间训练后仍 miss，开启后相同
  事务能分配并返回目标 A；再次关闭查询时 hit=0，恢复后同一目标重现。
  四个阶段 bin 在输出断言后写入 `results/ittage/functional-coverage-enable.json`。
  ITTAGE 的 5/5 行、34/34 分支此前已经满，不能从满覆盖推断训练门控
  或恢复后状态保留均正确。
- `BPU-ITTAGE-012` 对照 RTL 的 `valid && needIttage && taken` 训练条件，
  将 valid、taken、branch type、RAS action 从 agent 的硬编码改为事务字段。
  invalid、未 taken 间接、条件、直接、return 和 return-and-call 六类反馈在 cold
  metadata 下均保持 miss，在已有 target provider 下也保持 target 和
  confidence；普通间接与仅 push 的间接调用分别成功分配。八格功能 bin
  仅在输出断言后采样，ITTAGE 仍是 5/5 RTL 行点、34/34 分支，证实
  已满的插桩点没有表达这个训练资格矩阵。
- `BPU-ITTAGE-013` 再补齐单一有效 slot 无法验证的向量选择：同一拍先有
  四个有效且 not-taken 的条件分支、再有 taken 的间接跳转，或先有两个
  not-taken 条件分支、后有 taken 间接调用，均须选择后者目标。向量若以 return taken
  结束而没有合格分支，cold 查询仍 miss；后续合格向量可分配。四个 bin
  在输出断言后采样。agent 显式限制最多一个误预测和一个 ITTAGE 候选，
  符合 FTQ 训练契约；已有 5/5 行、34/34 分支无法证明多有效 slot 的筛选正确。
- `BPU-ITTAGE-014` 不重复 `BPU-ITTAGE-010` 已有的单个跨 region 目标：
  固定同一 PC，让三种折叠历史分别学习同区、上邻区和下邻区三个目标，
  三者低 20 位均为 `0x120`。每个 context 先确认 cold 且可分配，训练后
  精确比较完整 target 和 provider metadata；随后六笔交错查询再次逐笔
  对照完整目标。四格覆盖在断言后采样，验证 region pointer 与历史 tag
  同时存在时互不串扰。ITTAGE 原始行/分支此前已满，这一组合不能由
  单目标跨区或两种同区历史用例推出。
  注意：这是早期覆盖点子口径的记录；直到 ITTAGE-017 修正 Pc.addr 编解码，
  该用例的同区／相邻 1 MiB 字节地址边界才真正被验证，不能倒推早期已有该证据。
- `BPU-UTAGE-011` 先用正确的低表 provider 训练提高 useful，再以相反结果
  分配高表 provider。相同 readIndex、不同 position 的新分支此时训练后仍 miss，
  证明两个表均不可分配；随后用真实预测 metadata 交替送入 130 次高表误预测，
  每次检查原 provider 仍在高表。低表 tick 高位触发 useful aging 后，新分支
  训练可进入低表，而原高表 provider 仍命中。逐用例 `.dat` 中
  `UtageDut.v:1054` 命中 1 次，使当前 MicroTAGE 行点从 5/6 到 6/6；
  blocked／reopened／preserved 三种输出及 none／lower／higher provider bins
  都在断言后采样并命中。这既补上原始行缺口，也有前后行为对照。
- `BPU-UTAGE-012` 将全局 `io.enable` 从每笔查询的硬编码拆出，单独驱动
  预测及延迟一拍的 fastTrain。相同 cold metadata 在关闭期间训练后仍
  miss，启用时训练则命中；已训练后关闭并查询另一折叠历史，输出保持
  之前的 hit/taken（RTL 不直接用 enable 清零 hit），恢复后该历史实际 miss，
  原历史仍 hit。四格功能 bin 在断言后写入
  `results/utage/functional-coverage-enable.json`。原始 RTL 行/分支仍是
  6/6、16/16；不能凭其满覆盖把“关闭输出应为 0”当作正确规范。
- `BPU-UTAGE-013` 对应 `MicroTage.scala` 中按最终分支类型与位置计算的
  `t0_missHitMisPredVec`：agent 原来把最终分支固定写成条件，无法区分
  同位置直接／间接跳转与较早条件分支的真实方向误判。现在先以 stale
  条件 metadata 和同位置非条件跳转验证不误分配；再让更晚的直接或
  间接跳转执行：较早 base 为 not-taken 时不分配，为 taken 时必须在较早
  条件位置分配 not-taken 修正。两种类型各三格，全部在输出断言后命中。
  MicroTAGE 原有 6/6 行、16/16 分支不能替代这一跨位置／类型功能点。
- `BPU-UTAGE-014` 暴露了原 agent 只驱动 `fromAheadBtb.result(0).valid`
  且只观察 `hitVec(0)/takenVec(0)` 的结构性盲区。现在一笔查询可携带四路
  AheadBTB 状态，monitor 同时读取整组预测向量；保留旧的第 0 路标量字段。
  正确落空的早期条件分支与较晚出错条件分支分别放在不同 slot，后者依次
  为 1／2／3，中间空槽无效；检查每路 metadata 的 valid/position，训练后
  必须只有较晚有效 slot 获得 taken 校正，早期 slot 仍 miss。三格 coverpoint
  在这些断言后命中。相邻四笔异质向量／折叠历史的 transfer 又揭示旧
  agent 将 A1 `fastPositions` 和 A2 `result` 同拍驱动，造成较早预测的
  metadata valid 来自后续请求；拆分驱动阶段后，逐笔检查预测向量、
  metadata 位置和有效位，串行／重叠覆盖两格也在断言后命中。RTL 仍为
  6/6 行、16/16 分支：满行覆盖此前没有证明多路位置关联正确。
- MainBTB 先前的背靠背用例重复同一 PC；`BPU-MBTB-012` 改用两个不同 PC，
  交错检查各自的 position、branch type 和 target，揭示旧 scoreboard
  采样点晚一周期。TAGE 的 `BPU-TAGE-011` 交错查询同一 PC 的已训练与冷位置，
  暴露旧 agent 将 S1 的 MainBTB 位置与 S0 PC 同拍发送；修正对齐后，两个
  scoreboard 都在接受事件后两周期采样。两模块 RTL 行/分支原已全部命中，
  因此这些是由功能点矩阵发现的遗漏，不是为提高行覆盖率而添加的场景。
- MicroBTB 原背靠背契约也只重复直接分支 PC；`BPU-UBTB-013` 交错提交
  条件／直接／间接三种不同 PC，每周期接受一笔，并逐笔比较完整的有效位、
  方向、位置、类型与目标。该用例通过后，MicroBTB 原有 4/4 RTL 行和
  82/84 分支仍保持，说明这里补的是事务关联的证据，而非生成行刷点。
- `BPU-UBTB-014` 将 MicroBTB 的全局 `io.enable` 从逐笔 lookup 驱动中拆出，
  交给独立的持久控制驱动。禁用期间的 cold fastTrain 不分配；启用后相同
  训练可分配。对已命中 entry，禁用期间连续训练不同 target／position／type
  不改写旧 payload，禁用查询隐藏命中，恢复后旧 payload 仍在；随后启用
  状态下相同更新最终生效。六个阶段均先断言再采样于
  `results/ubtb/functional-coverage-enable.json`。原始 4/4 行和 82/84 分支
  未因此改变，不能将这些 enable 语义归因于行覆盖率已满。
- `BPU-UBTB-015` 对照 `MicroBtb.scala` 的 `s0_hitT1Victim`：旧 lookup
  的 hit mask 若与当前训练写回选中同一个 victim，就必须压制这笔预测，
  否则下一周期可能把新 entry payload 误配给旧 PC。用公开输出先标定
  32 项满组的 victim，再复位并重放相同填充／访问历史，将 victim 查询
  与替换写回重叠；仅该笔返回 miss，替换后新项命中且其余 resident 保留。
  对非 victim 再重放相同历史，重叠写回时仍返回完整原 payload，排除
  粗暴屏蔽所有查询。agent 用两个独立 driver 的接受事件封装重叠周期，
  测试不操作边沿。四格覆盖在断言后采样；原始行/分支此前近满，不能
  由替换和流水线各自通过推断这一竞态保护正确。
- `BPU-ABTB-031` 也将 AheadBTB 的 `io.enable` 从每笔查询硬编码中拆出，
  改由持久控制驱动管理。禁用时相同 cold fastTrain 不分配、已命中 entry
  的不同间接 target 不被写入，查询 entry valid 和 meta valid 均为 0；
  启用时原 entry 恢复，完全相同的分配／更新训练可以生效。六阶段功能 bin
  在结果断言后写入 `results/abtb/functional-coverage-enable.json`。这是
  现有 bank/set/way 复制行点之外的功能语义，不应为刷行数省略这一对照。
- SC 的 `BPU-SC-009` 在连续周期交错送入 MBTB 有效／无效、provider
  有效／无效和条件／非条件分支资格，逐笔断言 `scUsed`，同时检查注册
  metadata 的 `useScPred` 与 `tagePredValid` 对齐。
  `Sc.scala` 的 PC/历史查询位于 S0、`s1_fire` 推进中间结果、MBTB 与 TAGE
  资格位于 S2；旧单周期 driver 同拍驱动会让连续请求错位。现用 xreactor
  的 `AsyncMultiCycleDriver`/`DriveStage` 使三段重叠、每周期接受一笔；
  monitor 把 S2 组合判定与下一周期的寄存 metadata 配成同一响应。
  四类相邻资格切换作为独立功能覆盖 bin 写入
  `results/sc/functional-coverage-pipeline.json`，在逐笔断言通过后才采样。
  SC RTL 仍为 2/2 行、16/16 分支，说明原始 100% 掩盖了这一时序关联缺口。
- `BPU-SC-010` 将 `io.enable` 从每笔查询的硬编码中拆成独立持久控制。
  先将同一 PC 的 SC 训练至 taken/used，再关闭全局 enable，确认查询
  不使用校正；禁用期间发送 64 笔相反方向训练，重新开启后仍观察到
  taken/used。最后在启用状态重放完全相同的 64 笔训练 payload，观察到
  not-taken/used，证明之前训练未生效是 enable 门控所致。四阶段的功能 bin 在断言后
  采样于 `results/sc/functional-coverage-enable.json`。原始 RTL 行/分支
  仍为 2/2、16/16，因此该缺口不能靠行覆盖率发现。
- TAGE 当前配置是四张 tagged table，而非默认参数的八张。最高历史表
  index 3 在真实误预测训练后仍保留 provider，并允许方向计数器向两侧饱和；
  对应 `BPU-TAGE-008`。TAGE 覆盖率闭环用例改为先断言观察结果再采样，
  并新增 none／非最高／最高 provider 层级 bins。
- `BPU-TAGE-015` 将全局 `io.enable` 从每笔查询的硬编码移到独立持久
  控制驱动。cold metadata 在关闭期间训练后仍无 provider；开启后
  同一训练事务分配 provider。再次关闭时预测 valid 和给 SC 的 provider
  counter valid 均为 0；重新开启后原 provider table/way 仍在。四阶段
  功能 bin 均在行为断言后写入 `results/tage/functional-coverage-enable.json`。
  TAGE 生成 RTL 原始行/分支此前已满，保持 5/5、30/30；本用例补的是
  无法从这两个百分比得知的全局门控语义。
- `BPU-TAGE-016` 从 RTL 的 `t0_hasCond` 与 `TrainInfo.valid = isCond &&
  mbtbHit` 发现原 agent 将 branch type 固定为条件，因而无法测非条件
  训练资格。现将类型同时送到查询 MainBTB payload、训练 MBTB metadata
  和反馈分支：直接／间接跳转即使因目标错误产生误预测，也不能冷分配或
  改动已存在的条件 provider；随后预测正确的条件反馈能使 counter 加一。
  六个 bin 均在输出断言后采样。生成 RTL 已有 5/5 行、30/30 分支，
  不代表原先验证了这一类型门控。
- `BPU-TAGE-017` 再针对 RTL 的 `t0_meta` 通过 MainBTB `rawHit/position`
  选择 TAGE metadata，以及 `t3` 逐 table/way 汇总多个训练信息的路径，
  绑定完整 `branches` 和 TAGE metadata 向量。一笔反馈中较早正确
  not-taken 与较晚正确 taken 条件分支隔一个空槽，分别把两个已存在
  provider 的 counter 从 2→1、5→6；第二笔再到 0、7。encoder 另拒绝
  重复位置和双误预测。三格功能覆盖在两路结果都断言后采样；原有 5/5 行、
  30/30 分支不变，故这是行为交叉而非行覆盖率刷点。
- `BPU-TAGE-018` 检查 `TrainInfo.valid = isCond && mbtbHit` 的命中条件。
  此前 agent 对每个有效训练分支都放置匹配的 MainBTB `rawHit`，把 miss
  行为从测试输入域中排除了；现在事务显式选择是否命中。冷态 miss 不
  分配、已存在 provider 的 miss 不更新；相同冷反馈在 hit 时可分配，
  而一笔混合向量中的较早 miss 不遮蔽较晚 hit 的 provider 更新。
  四格覆盖均在行为断言后采样。TAGE 原有 5/5 行、30/30 分支虽已满，
  并没有替代这条组合资格门控的验证。
- `BPU-TAGE-019` 发现原 agent 只让 MainBTB `result(0)` 有效、只绑定
  TAGE `takenVec(0)` 和 `meta.entries(0)`，因此已有满行/满分支数据无法
  证明后续预测槽位。现在 S1 `s1_positions` 与 S2 `result/baseConf` 分别驱动，
  monitor 采集四路方向、provider metadata 和送往 SC 的 counter valid。
  对 slot 1、2、3 分别分配并强化较晚条件 provider，中间留无效空槽；
  再在相邻周期交错训练过的 slot 2 与冷 slot 3，逐笔断言 provider、方向、
  `altConf` 与 SC counter valid。五格覆盖在断言后命中；全量 TAGE 仍为
  5/5 行、4/4 唯一行、30/30 分支，故这是新增功能关联而非刷行点。
- `BPU-TAGE-020` 进一步区分同拍多路 provider 写入与共享 selector 的
  多步更新：较早不跳转、较晚跳转两路各有独立的同表 way，弱 provider
  都与高置信度 base 相反，正确 base 反馈使两路 provider counter 各跨过
  弱状态边界，且同一个 `useAltOnNa` 桶应加二。随后把 base 方向换到
  provider 的正确一侧，分拍施加两个减向反馈仍应选择 base，第三次才
  切换到 provider；这从公开预测结果区分 0/1/2/3 步，而不读取内部
  selector 寄存器。六格覆盖在断言后采样。TAGE 的原始 RTL 行/分支
  已满，此处补的是之前未证明的 PopCount 同拍聚合语义。
- `BPU-TAGE-021` 检查同一 selector 桶内相反反馈的净效应。两个条件
  分支同拍分别命中同表不同 way：较早不跳转使弱 provider 从 4→3，
  较晚跳转使另一个弱 provider 从 4→5；两者在 selector 上一增一减。
  恢复两个 provider 到弱态后，公开预测仍回退 base；再给一笔 provider
  正确的反向反馈才切换到 provider，从行为上区分仅保留一侧投票的错误。
  四格功能覆盖在输出断言后采样。原始 TAGE 行/分支此前已满，新增的是
  向量反馈的净和语义，不是重复追求行点。
- TAGE 在同一索引以 8 个不同分支位置占满四张表的两个 way，逐个把 useful
  置为正值；第 9 个位置训练后仍 miss，原 8 个 provider 保持，证明真正的
  “需要分配但无可用 way”状态，对应 `BPU-TAGE-009`。继续以真实查询 metadata
  训练，至少 255 次失败前新分支不能分配；useful-reset 后它获得 provider，
  旧 8 个 entry 中恰好 7 个保留且 useful 清零，对应 `BPU-TAGE-010`。
  该用例自身的 `.dat` 中 `TageDut.v:3673` 命中 1 次，TAGE 唯一 RTL 行
  达到 4/4。新增独立功能覆盖组记录阻塞／重新开放、useful 正值／清零和
  满组／单项替换，并由完整回归报告一起汇总。

其余零翻转 RTL 位中，RAS 的 `io_train_meta_utage_abtbResult_2_cfiPosition[0]`
来自本模块不读取的共享训练 meta；TAGE 的
`io_train_branches_5_bits_attribute_rasAction[1]` 也不参与本模块的条件分支
筛选（`isConditional` 只比较 `branchType`）。当前固定种子 SC 报告还列出
1648 个未翻转的 `.v` 位；例如共享训练结构中未被本模块行为测试使用的
`branches[6].target_addr` 位。不能把这些位逐个当作缺失的 SC 功能点，
但也不能据此宣称 SC 所有组合均已验证。
不为这些未使用的接口输入制造“功能点”；分类基于当前 Scala 逻辑和生成 RTL，
不代表相关整体功能都已穷尽。

这些用例先断言真实输出再采样功能覆盖率。定义的 bin 达到 100% 只表示
目前模型闭环，不是设计验证完成。MicroTAGE、ITTAGE 和 TAGE 的覆盖率闭环用例
已移除“还没观察 DUT 就预先 sample”或把 disabled/miss 当 hit 的写法。

## 剩余缺口与下一轮用例

本节引用的旧 `.v` 点数仅作场景发现线索；当前全 RTL 未覆盖行以本文件顶部
原生 LCOV 表和 `results/rtl-line-coverage.json` 的逐行集合为准。

| 优先级 | 证据 | 应构造的场景与判定 |
| --- | --- | --- |
| 已知缺陷／剩余路径继续审查 | TAGE 双 way pending 未检查捕获 provider-way 在 tag 迁移后的 useful 身份；counter 正确不能证明 useful 关联正确 | `BPU-TAGE-025` 四索引／双向迁移的新鲜组 120/120 bin 通过；`BPU-TAGE-026` 捕获组八例使无关 tag useful 3→1，16 个失败 bin 保留，strict XFAIL 仅针对该异常，三负对照均普通 FAIL。该场景原生行无增量；旧阶段 88 个赋值行局部分类、229 行未分类。当前 5.052 新场景及追加 key-copy 证明后共 112 个赋值行局部分类、131 行未分类；不推断集成 FTQ 调度可达。 |
| 已覆盖／其他功能组合仍待审查 | SC 的 33/33 `v_line` 未证明同行四 bias selector 的独立 masked merge，也未证明已排空行用真实错误 metadata 重激活；共享的非 bias 总方向可掩盖 bias 漏更新 | `BPU-SC-019` 检查 64 个 bias 上下文及子集保持，1280 个 cross bin 闭合，关闭 82 行；`BPU-SC-020` 用真实已学习 metadata 逐 way 反向重激活，1024 个 cross bin 闭合，再关闭 8 行；两场景各三负对照检出。剩余 336 行均为已逐块复核的局部矛盾赋值并保留原始分母，不宣称全 SC 验证完成。 |
| 已知缺陷／P1 继续审查 | MicroTAGE 两表的原生行缺口促成全容量 shadow 回绕与替换场景；即时 bypass 正确，但 16 组 SRAM 保持矩阵中 112/128 项丢最后更新，同槽 enqueue／clean dirty 冲突由只读 VPI 复核 | `BPU-UTAGE-015` 的 384 个 cross bin 通过，`BPU-UTAGE-016` 保留 strict XFAIL 和 112 个失败 bin；修复应使其 XPASS 后再解除缺陷标记。`BPU-UTAGE-017` 两轮 aging 的 60 bin、`BPU-UTAGE-018` 短／长 history 的 144 bin、`BPU-UTAGE-019` hash/tag 碰撞与捕获 counter 重建的 720 bin 通过；剩余 4984 个复制／状态行仍按合法状态交叉审查，不直接定义成 4984 个功能点。 |
| 已覆盖 | MainBTB `MainBtbAlignBank.scala:294` 的 `detectMultiHit`／flush 不能由 2/2 `v_line`、4/4 分支直接证明；连续重放真实 cold metadata 曾因 write-buffer 同 set/tag 合并及持续 S2 清理而只观察到单命中。 | `BPU-MBTB-019` 先让原 entry 入 SRAM，再用另一 set 训练替换 shadow；重放原 cold metadata 时暂缓清理，从公开预测和 metadata 断言两个同位置 way、不同 target；恢复后断言只剩低 way 且另一 set 保留。四格覆盖在输出断言后闭合。 |
| 已覆盖 | `BPU-SC-013` 验证不同 SC way 的双分支更新，`BPU-SC-014` 验证同 way 一增一减抵消；`Helpers.updateEntry` 和阈值／bias 更新还有同 way `PopCount=2` 的同向路径。SC 的 2/2 行点与 16/16 分支无法区分这些行为。 | `BPU-SC-015` 从匹配冷态出发，对照单分支与同 way 双分支 not-taken 反馈达到相同可观察校正所需的训练拍数，要求双分支更快且两个预测槽共享结果；第三次复位复现单分支拍数，排除残留状态。只处理首分支会失败；四格功能覆盖仅在对照断言后采样。 |
| 已覆盖 | 集成 BPU 原先只绑定并驱动 `io.fromFtq.train.bits.branches[0]`，但 RTL `Bpu.scala` 会将完整 FTQ 向量转发给各预测器；6/6 RTL 行不能证明向量反馈连通。 | `BPU-INT-020` 将 agent 扩展为完整训练向量。resolved slot 0/2 间留空槽，先从公开 `resolve.mbtb_entries` 证明较早计数器 2→1 与较晚条目分配为 2，并断言 S2 返回较晚分支 target；随后无误预测反馈使两路同时 1→0、2→3。三阶段均在断言后采样；尚不推断其他预测器的集成多分支路径已由此证明。 |
| 已覆盖 | `BPU-INT-020` 为了隔离 MainBTB 关闭了 TAGE/SC；独立的 `BPU-TAGE-017` 与 `BPU-SC-013` 仅证明各自模块的完整反馈向量。集成 TAGE 的初探因持续预测读与 tagged SRAM 训练读争用而没有稳定 provider；RTL `TageTable.scala:120-134` 确认两路读共用同一 bank 读端口。临时集成 SC 探针也显示只有 MainBTB 条目、没有 TAGE provider 时，公开 `sc.tagePredValid` 全为 0，不具备 SC 训练资格。 | `BPU-INT-021` 使用有界无预测读取窗口，确认同笔 FTQ 反馈将不同 TAGE provider 计数从 2/3 更新到 1/2。`BPU-INT-022` 从两个有效 provider 的相同冷态出发：第一分支单独反馈只使其 SC 输出学成 not-taken、第二路保持冷态；slot 0/2 同笔反馈使两个不同 SC way 均学成 not-taken。训练时关闭 TAGE 更新、回读时恢复并确认两个 provider 的 table/way/counter 不变；四格 SC 功能覆盖在断言后采样。此证据只覆盖不同 way 的集成反馈。 |
| 已覆盖 | 独立 `BPU-SC-015` 的同 way 双 not-taken 反馈能加速学习，但集成 BPU 的两个真实 MainBTB/TAGE 位置此前只测到不同 SC way，不能据此推断 FTQ 向量在共享 way 上正确聚合。RTL `Sc.scala` 用两条 branch 的匹配 metadata 与 `Helpers.getWayIdx` 的位置哈希选 way。 | `BPU-INT-023` 在位置 1/4 建立不同 TAGE provider、相同计数 2 与相同 SC bias 选择；从可复现的冷态比较第一分支单独反馈与 slot 0/2 同笔反馈。单分支 4 笔未越过阈值、8 笔越过；双分支 4 笔便使两槽使用 not-taken SC 校正。TAGE provider 状态保持不变，五格覆盖仅在行为断言后采样；反向抵消另由 `BPU-INT-024` 验证。 |
| 已覆盖 | 独立 `BPU-SC-014` 已证明同 way 一增一减在单模块里抵消，但 `BPU-INT-023` 的集成用例只有同向票，不能说明完整 FTQ 向量中的相反票也会经位置匹配后抵消。单看 SC 2/2 行和 BPU 6/6 行均不足以区分。 | `BPU-INT-024` 用较早 not-taken、较晚 taken 的真实可执行顺序，保持 TAGE provider 状态不变，连续 64 笔后两个 SC 槽仍是冷态；单分支 8 笔随后可使共享 way 学成 not-taken。复位重现后先做同样抵消，再仅把较晚结果改为 not-taken，同槽位双分支 4 笔即学成；因此抵消并非忽略了整笔向量。六格功能覆盖均在断言后采样。 |
| 已覆盖 / P1 开放候选 | `BPU-INT-021` 至 `024` 的 SC/TAGE 集成反馈分别使用单笔有效 metadata、重复初始 metadata 或训练时冻结 TAGE；它们不证明先后预测的不同 S3 metadata 会逐笔送回 FTQ，亦不证明多笔反馈可以重叠。BPU 和 SC/TAGE RTL 行分母过小，满行不能替代关联检查。 | `BPU-INT-025` 用新配对 metadata 证明串行 TAGE/SC 闭环；`BPU-INT-026` 用同 PC/历史两笔相邻反馈更新不同 TAGE provider；`BPU-INT-027` 用两个 PC 的相邻反馈更新各自 MainBTB counter，并观察预测与训练同窗。`BPU-INT-028` 以两条真实 redirect 路径得到不同 PHR metadata，先证明新历史 miss 原 provider，再分配独立 provider；相邻反馈后各自原 table/way 的计数分别 2→1／4→3。`BPU-INT-029` 在另一个 TAGE bank 的活跃预测同两拍继续验证该更新；`BPU-INT-030` 让同 bank 的持续预测读使单笔训练 transfer 保持 pending，暂停读取后才接受并更新 MainBTB/TAGE；`BPU-INT-031` 在同样冲突下先排入两个不同 PHR 的反馈，释放后相邻接受并分历史更新。以上行为检查不能由 6/6 BPU RTL 行登记 PASS 代替。 |
| 已覆盖 | 独立 ITTAGE 的 5/5 RTL 行与 provider 回读，不能证明它在集成 BPU 中经 FTQ 学习后会优先于不同的 MainBTB 间接目标；集成 BPU 的 6/6 行也不区分 S2 与 S3 的目标来源。 | `BPU-INT-032` 先用真实 FTQ 反馈分配 ITTAGE，关闭它期间只改 MainBTB 目标；恢复同一 redirect／历史上下文时，检查 provider metadata、S2 MainBTB 新目标和配对的 S3 ITTAGE 旧目标／override。四格功能覆盖在断言后闭合，RTL 行分子未变。 |
| 已覆盖 | 独立 RAS 的 LIFO 与顶层 `BPU-INT-008` 的单层 call／return 不能证明两个嵌套栈帧在集成 BPU 的 S2/S3 目标选择中均正确关联；RAS 2/2 和 BPU 6/6 行点同样不足。 | `BPU-INT-033` 在不相互驱逐的 MainBTB 地址预置两次 direct call、两次故意错误静态目标的 indirect return，再沿真实预测路径执行。两次 S2 静态目标与对应 S3 LIFO 返回地址逐笔断言，六格功能覆盖闭合。 |
| P1 | 当前 5.052 正式基线有 1867 个未命中 `v_line` 点：AheadBtb 的 1627 点全部映射到 counter 格子，819 个正向 arm、808 个减向选择 arm，涉及 819 格，其中 808 格两类都缺、11 格仅缺正向。其余 240 点分别来自 AheadBtbReplacer 194 点和 ReplacerState 46 点，不是未解析的 counter。旧 5.026 的 1264 点／2050 分支数字仅是历史记录 | 既有 `BPU-ABTB-021/030/036/039/045/046/047/048` 等用例覆盖最高／中间 set、同 PC 多位置、哈希路由及邻 set 保持的代表样本；不能据此证明完整 4 bank × 64 set × 4 way 的译码与状态组合。将复制 counter 地址遍历和真正的新并发功能分开：先检验命中训练与分配写回的同 set 优先级／不同 set 独立更新，再补完整方向／饱和及邻项保持矩阵；不把复制点数当功能点数。 |
| 已知缺陷 | `BPU-INT-018` 的 ABTB 返回方向 S1 已由同笔 metadata 证明来源有效，却把正确 MainBTB 目标 `0x407fffe0` 包装为 `0x40bfffe0`；两者低 22 位相同，后级未纠正 | 双向 MainBTB 完整目标、ABTB 局部 wrap 和来源回显先作为硬前提断言；缺少后级完整目标时 strict XFAIL，修正结果功能 bin 留空。修 RTL 后该用例须转为 XPASS 并据此更新缺陷处置。 |
| 已覆盖 | `BPU-INT-017` 的双源优先级曾被改变历史的重定向探针和 S3 fastTrain 目标收敛遮蔽，不能由 `BPU-INT-016` 两次独立命中推断 | 不重定向地开启两个早级表，在新 S0 读取后保持同一 S1：先选择 AheadBTB 目标 B，关闭 AheadBTB 后露出 MicroBTB 保留目标 A；条件 AheadBTB entry 的公开 metadata 预先确认有效，A/B 不同，三格覆盖在断言后采样。 |
| 已覆盖 | AheadBTB `AbtbDut.v:21639` / `AheadBtb.scala:325` 的 `s2_fire && s2_multiHit` | `BPU-ABTB-028` 仅用真实预测 metadata 使不同 way 双命中，并从输出断言清理前后；无需直接写内部 SRAM 或伪造 hitMask。 |
| 已分类 | AheadBTB 最高 set/末 way 的 4 个 `needReset` 分支：`AbtbDut.v:7909/11750/15591/19432`；bank 1/set 34 的同类 reset 分支也未因行为用例增加原始计数 | 安装的 `AbtbDut.v` 与 `rtl/abtb/AheadBtb.sv` 字节一致。以 picker wrapper 顶层、Verilator 5.026、`--coverage -O3` 独立重生成 C++ 后，覆盖检查位于 `nba_sequent TOP__1`，而本拍 `_needReset_T_*` 赋值和实际 counter reset 位于较晚的 `TOP__14`；调度器先执行前者。`BPU-ABTB-021/030` 分别在最高 set 与 bank 1/set 34 把旧 counter 老化至 not-taken，并验证新 entry 立即 taken。原始分支计数存在相位归因问题；不改写 `.dat` 或虚报命中。 |
| 已分类 | MicroRAS `UrasDut.v:482/485 else/491/493` 四个剩余 `v_line` 点 | `BPU-URAS-014` 的 S1×S2 pending 四格矩阵逐拍断言真实输出；较老 S3 push 与 S1 pop 配对另由 `BPU-URAS-011` 对照。复制当前 `dut/uras/UrasDut.v`（`cmp` 字节一致）并以 Verilator 5.026、`--coverage -O3` 直接生成的 C++ 中，四个计数器分别为 `__Vcoverage[2570/2569/2574/2573]`，均在 `nba_sequent` 的 `_GEN_0/_GEN_1/_GEN_2` 赋值之前读取这些临时条件，行为代码随后才用本拍新值执行；原始 `.dat` 对四点仍报 0。此前 `:493` 还用 picker `-w` VCD 确认 pending `s2_hasPop=1` 与中性 S1 相遇。故这是当前插桩的相位归因问题；保留 17/21 原始数字，不补造 RTL 命中或把每个点算成未测功能点。 |
| 已分类 | MicroBTB `UbtbDut.v:1785` 的 `else`、`:1790` 的 `else` | `1785 else` 在 `if (t0_hitT1Update)` 内，而 `t0_hitT1Update = t1_fire_REG && ...`，直接矛盾。`:1790 else` 要求 `t1_fire_REG && t1_hit && _GEN && !t1_hitNotUseful && usefulCnt==0`；但 stage-1 同拍把 counter 和 `t1_hitNotUseful` 分别登记为同一个旁路值 `V` 与 `V==0`，因此条件也矛盾。见下方不变量推导；不为不可达分支制造虚假功能点。 |
| 已知缺陷 | 集成 BPU 虽然已达到 6/6 RTL 行点，`BPU-INT-013` 的 MicroBTB 跨区域 target `0x40400100` 与 MainBTB 正确的 `0x40800100` 只差高位，S2/S3 都未修正 | `BPU-MBTB-013` 和 `BPU-INT-012` 分别证明 MainBTB 单模块及关闭早级后的集成输出正确；`BPU-INT-014` 证明相同高位区域内的低位差异会在 S3 被修正。跨区域的全目标一致性用例仍为 strict XFAIL；修 RTL 时需让后续阶段发现高位差异，不能靠补刷行覆盖率解决。 |
| 已分类 | 集成 BPU `BpuDut.v:1882` 的 `else if (s1_valid)` 未命中 else arm | 生成 RTL 的外层 `_s0_stall_T_2 = s1_valid \| s2_override \| s3_override \| redirect.valid`；进入外层后，若前三个优先级条件均为假，`s1_valid` 必然为真。该 else arm 不可达，不应构造虚假的功能点去追 14/14。 |

MicroBTB 的第二个不变量可直接从生成 RTL 的共同 `if (t0_fire)` 时钟使能得到。
令 `V = t0_hitT1Update ? t1_updatedEntry.usefulCnt : t0_realHitEntry.usefulCnt`。
同一条边沿分别执行 `t1_hitEntry_r_usefulCnt_value <= V` 和
`t1_hitNotUseful <= (V == 0)`；在 `t0_fire=0` 时两者都保持。复位使
`t1_fire_REG=0`，以后只要 `t1_fire_REG=1`，上一拍必有 `t0_fire=1`，
所以必有 `t1_hitNotUseful == (t1_hitEntry_r_usefulCnt_value == 0)`。
`:1790 else` 的必要条件与此相反。该证明限定于当前生成 RTL 和正常复位后的
时钟状态；未对当前覆盖工具的原始 82/84 计数做任何改写。
严格 XFAIL 的 MicroTAGE tag 宽度与 RAS disable
缺陷也仍是整体 verdict 的限制，不能被覆盖率百分比抵消。

## 复现

```sh
PYTHONPATH=/home/xyl/xreactor/src:/usr/local/share/picker/python:/home/xyl/bpu-verify-kunminghu-v3 \
  python3 tests/run_all.py
```

该入口依次运行 pytest、合并当前测试的 RTL 覆盖、生成同时包含功能与原生
RTL 源码行覆盖的 HTML。
pytest 功能点判定另见 `results/feature-points.json`；HTML 当前不包含功能点表。

## MicroTAGE 全地址 useful 与部分回绕诊断（历史原型，正式刷新待完成）

2026-10-08 的隔离增量审计见
`results/coverage-utage-useful-address-prototype-readonly.json`。它没有写入当前正式
manifest；正式 MicroTAGE 数字仍为 `6297/11053 = 56.97%`。
冻结正式原始数据加上 14 个独立正向 pytest 入口的候选结果为
`9901/11053 = 89.58%`，精确闭合 3604 行，无新增缺口，也没有缩减分母。

- 两种训练节奏（串行／相邻周期）分别验证两表所有 512 地址的分配，
  下层 128 个可命中地址与上层全部 512 地址的递增、递减和双端饱和保持。
  1282 个上下文通过独立周期重放：134912 周期、11264 笔公开输入、
  21628928 次 useful 单元比较。公开元数据来自真实预测；静态 Bundle 与
  `CycleMonitor/@on` 仅被动读取，driver 负责所有写入和时序。
- 另外 8 个 bank×节奏场景验证部分回绕后的旧优先级组 slot2 读取。
  公开训练完整载荷、三周期可见延迟、全部 shadow 单元及输出 payload
  逐拍核对，命中原先遗漏的 8223/8255/8287/8319 四行。
- 九种 trace 故障均触发带异常点和状态的普通 pytest 失败；十个 useful
  写路径源变异和五个地址／tag 前提变异均被拒绝。负向控制不是 XFAIL。

剩余 1152 行是下层 384 个高地址的三类更新源行。实际编译 RTL 的
下层 `index[8:7]` 恒等于 PC 对应位，而这两位又进入完整 tag 的 `[12:11]`；
当前存储 tag 只有 8 位，因此这些地址无法产生真实匹配的 provider 元数据。
这是既有 `BPU-UTAGE-007` 的影响范围，不是可以从分母删除的不可达豁免。
源码与反例证据见 `results/coverage-utage-useful-address-tag-scope-readonly.json`。

完整目标仍包括这些地址的更新：候选 decoder 路由矩阵要求 10240 个
table×address×operation×节奏组合，实际检查 7168 个，另 3072 个被已知缺陷阻塞。
这些是一个地址译码功能需求的覆盖组合，不是 10240 个独立功能点。
不能把候选 89.58% 行覆盖率、诊断通过或缺口分类当作功能完整性证明。
以上为原型阶段记录；随后完整 RAS 回归和审计已通过，正式基线更新为
258 个功能点，MicroTAGE 原生数字仍为 6297/11053。

### 仓库分层实现与完整地址候选

后续候选将静态 VPI Bundle／`CycleMonitor`、独立 useful 读写流水线模型、
Scoreboard 比较和完整功能矩阵分离，继续使用已有 agent／PulseDriver。
测试只提交公开训练事务和预测请求，不出现边沿等待或 `asyncio.gather`。
首个异步比较失败交给测试前台抛出，保留请求、tick、差异与统计状态，
监视器安全关闭，不重复报 teardown ERROR。

完整矩阵包含 2052 个上下文：两种节奏下分别遍历下层／上层所有 512 地址
的分配和更新目标，未提前删去高地址。独立审计核对 187648 个周期、14464
笔真实公开反馈和 26349568 次 useful 单元比较，原生候选仍精确关闭
3604 行至 9901/11053，无新缺口。分配 cross 2048/2048；更新 cross
5120/8192（62.5%），768 个下层 provider 上下文由已证明的现有 tag-width
问题阻塞，3072 个更新组合保留为零计数。该更新组按 coverpoint/cross
加权的聚合值为 92.5%，不能用它替代地址 cross 的 62.5%。四 bank × 两节奏
的部分回绕场景核对完整八槽、三周期可见写入、注册优先级 mask 和旧 slot2
payload。178 项模型检查、旧完整证据重放及硬件代表最终门禁为
181 PASS、2 个具体异常 XFAIL；十项真实 DUT 观测破坏控制均普通 FAIL。
具体 tag 异常另通过五项分类控制：现有缺陷 XFAIL、模拟修复 strict XPASS、
三个前提错误普通 FAIL。见
`results/coverage-utage-useful-address-integration-candidate-readonly.json`。

能力现已迁入 `suites/frontend/bpu/utage_{model,observation,shadow_observation,checking,
coverage,addressing,errors,partial_wrap}.py`，agent 提供 `observe_useful()`、
`observe_shadow()` 和 `observe_partial_wrap()`；具体刺激在 `tests/utage/testcase`。
旧 BPU-UTAGE-007 也改为仅捕获具体 tag-width 异常：修复后检查应通过并触发
strict XPASS，不再用“缺陷不再复现”的断言把修复吞成 XFAIL。
实际仓库旧 MicroTAGE 回归已通过 31 PASS、2 个原有 strict XFAIL、0 SKIP。
迁入后的十五项分类／异常控制也全部通过：十项真实 DUT 观测破坏和三个
tag 前提破坏均普通 FAIL，一个已知 tag 缺陷 XFAIL，一个模拟修复 strict XPASS，
没有 teardown 错误。实际仓库完整新矩阵随后通过 180 PASS、2 个具体异常
XFAIL、0 SKIP；独立重放完整 2052 个上下文、26349568 次单元比较，实际
仓库候选仍精确关闭同样 3604 行，无新缺口。见
`results/coverage-progress-utage-useful-address-promoted.json`。
020/021/022 已登记，旧 258 项描述与状态未删改；正常收集 2268 个测试，
四份正式报告逐字节不变。2026-10-08 03:56 UTC 已冻结 1018 个运行源文件并
启动完整刷新。全流水线已于 05:11:13 UTC 实际退出 0，2261 PASS、
7 strict XFAIL、0 SKIP；独立刷新审计和随后正常收集保护均已实际通过，
故本页主表现使用 261 功能点正式基线。
启动前检查发现 picker 源仓库由 e447bb8 外部推进至 03f0f44，仍为 master；
第一版入口在依赖身份门禁处退出，未运行测试。后续明确记录这次提交差异，
核实四个已安装 xspcomm 运行文件与十个基线 DUT 内副本的 SHA 全部一致，
才启动新回归。没有重生成 DUT 或切换分支，构建器身份仍按原有逐 DUT
provenance，不能把当前 picker 源码的 ABI2 要求当作已完成 ABI2 重建。
隔离候选 raw 未写入正式 manifest。021 表示完整地址更新需求
受既有 007 阻塞，不是发现第七种独立 RTL 缺陷；功能通过率与功能覆盖率
都应如实保留该缺口，不能为维持旧 XFAIL 数而裁掉需求。

正式刷新保持 1018 个运行文件和已限定的依赖／安装运行库身份不变。
340 份本次 raw、153 份功能 JSON、154 个功能组及十份 HTML／JSON／LCOV
报告新鲜且一致。完整 2052 上下文独立重放包含 187648 周期、14464 次实际
输入、26349568 次单元比较；MicroTAGE 原生恰关闭 3604 行，无新缺口，其他
九个 DUT 的计数和缺口集合完全不变。分配 cross 2048/2048、更新 cross
5120/8192、partial-wrap 16/16；3072 个受既有 007 阻塞的更新 bin 均保留，
不是裁掉后宣称全覆盖。剩余 1152 原生行仍在分母。七个 XFAIL 需求对应
六种既有独立 RTL 问题；本轮没有修复这些 RTL，也不宣称整体目标完成。

### 集成 PHR 缺口的下一轮刺激方向

正式 258 基线中的集成 `Phr` 为 2213/4300，缺 2087 个映射行。
只读审查逐项核对 1456 个物理历史写 arm，并用四项源码变异验证映射前提。
其中 1407 个未命中行关联奇数指针写 arm，但包含条件头，不能整体解释成
“必须实际执行奇数指针写入”。当前两位步长、52 位环长在输入历史
metadata 为偶数时保持奇偶性，但外部恢复 metadata 可提供反例，尚未证明
全系统合法 FTQ metadata 的约束，因此不称其不可达、不扣原生分母。
另有 665 个偶数指针可对应的写行仍未命中：taken 87、not-taken 578；
其余 15 行另待审查。见 `results/coverage-bpu-phr-gap-review-readonly.json`。

当前 `BpuRedirect` 只携带 pc/meta，agent 固定 taken=1、cfi_pc=target=pc，
尚不能完整表达真实分支 PC、恢复目标和不跳转恢复。下一轮应使用真实捕获的
PHR metadata，验证 taken 两位移位与 not-taken 原位恢复、回绕、全部折叠历史、
邻位保持，以及 redirect 对 pending S1/S2/S3 写入的取消；不能靠伪造奇数
metadata 刷行。构造以下候选时 MicroTAGE 完整回归仍在执行，运行源文件
保持冻结；该回归现已完成并审计，但以下 PHR 硬件证据仍为隔离候选，
尚无 PHR 正式覆盖率增量。

2026-10-08 04:27 UTC，隔离目录 `/tmp/bpu-phr-recovery-candidate-xDLxiq`
的最终 PHR 矩阵通过 311 项测试（309 项独立模型门禁、两种实际 DUT 时序），
持续运行／背压恢复各 104 次恢复。逐周期核对 52 个物理历史位、19 种折叠
历史的四级寄存器及 pending 状态；完整重放核对 106808 次历史位和 156104 次
折叠寄存器比较。全部恢复 metadata 均来自先前因果关联的真实 S3 输出，
分支 PC 与目标不同，taken／not-taken、26 个偶数指针和两个环绕标志均有
对照。十项真实观测破坏控制全部普通 FAIL，包含异常点、请求、时刻及状态，
没有重复 teardown ERROR。观察层统一采样并按 S1/S2 fire／flush 关联完整
预测与 perf 回显；不靠 PC 搜索或放宽时间差绕过背压下旧 monitor 的相位差。
其中 perf PC 按已核实的 49 位 unGuard 端口比较，预测 PC 则保留 50 位 signGuard。

该候选保留全部 416 个功能 cross bin，208 个偶数指针组合命中、208 个奇数
指针组合为零；cross 为 50%，组聚合为 75%，两者均不称为全覆盖。
38 份 BPU 基线 raw 的 SHA 与冻结的正式 258 点账本逐项一致，原生 LCOV
指标和缺口集合重现后，只加入两个正向 raw：集成 BPU 候选由 28290/46541
到 28969/46541，精确关闭 679 行且无新缺口、分母不变。其中 PHR 从
2213/4300 到 2883/4300，关闭全部 665 个偶数相关目标行及其他五行；
CommonHR 另关闭九行。见
`results/coverage-bpu-phr-recovery-candidate-readonly.json`。

这里另发现原分类必须细化：其他五个 PHR 命中中，3735/3787/3839 是
奇数相关 arm 的**条件头**，不是奇数指针写入赋值；1566/1576 是 S2/S3
**taken 指针减二时的内层回绕分支**，不是外层 not-taken 恢复选择
（外层 not-taken 行分别为 1567/1577，见后续原生门禁纠错）。故此前
“1407 行要求奇数写指针”的说法只适用于
对应 arm 的选择条件，不能整体推成这些源码行不可达。条件求值覆盖与
赋值执行覆盖须分开，三个条件头已由真实偶数指针轨迹命中。
剩余非写路由缺口共 13 行：四个 pending 局部矛盾分支，以及九个折叠保持
false-arm。后九行的外层 `_s0_foldedPhr_T` 已要求 `S1 valid && taken`，
内部再次选择 taken 的 false-arm 同样矛盾，不能仅看内部三目运算就列成
漏测的 not-taken 场景。第二版源条件审计覆盖全部祖先条件、32 种布尔赋值
及六项源码变异，13 行只分类、不扣分母。见
`results/coverage-bpu-phr-line-role-refinement-v2-readonly.json`；第一版把九行
列为可达目标的证据保留，并由第二版明确更正。

为检查真实 not-taken 行为，另在 `/tmp/bpu-phr-recovery-warmed-rMsxXO`
先等待 SRAM 初始化和第一笔 enabled 冷预测，断言其 taken=0，再关闭
预测器后运行相同恢复矩阵。最终 312 项测试与十项实际 DUT 负对照通过；
持续运行模式还检查 104 个在途 S2 token 的 redirect 冲刷。这个行为场景
有独立价值，但不会令上述九个矛盾 false-arm 命中。模型单测也已根据完整
外层条件更正为“S1 not-taken 不改变当前历史／fold”，而不是选择另一阶段
的历史；先前版本的源码快照、测试结果和 native 试验均保留。
最终冷启动版本独立 admission 精确关闭 672 行：PHR 668、CommonHR 四行，
集成 BPU 临时候选为 28962/46541，PHR 为 2881/4300；全部 665 个偶数相关
目标行仍关闭，无新缺口，原生分母不变。两种初始化场景的 native 增量不同，
不能为了取更高百分比而忽略初始化资格。见
`results/coverage-bpu-phr-warmed-candidate-readonly.json`。
该冷启动场景尚未触发 `Phr.sv:1566/1576`。此前将它们列为 S2/S3
not-taken override 的目标是嵌套三目运算归类错误：真实 not-taken 恢复有
独立验证价值，但目标行实际要求 taken 且历史指针小于 2。后续必须分别
构造方向修正与零指针 taken 回绕，并核对完整 PHR 与 metadata 关联，
不能依赖关闭前尚未初始化的预测 payload。
上述候选均未迁入当前冻结的正式测试，也未更新正式 manifest 或主表。

进一步追踪真实 FTQ：`Ftq.scala:114` 的 `metaQueueRedirect` 是未复位的
`Reg(Vec)`，`:219` 在 S3 meta.valid 时写入；`:384` 按提前一拍的 redirect
索引经 `RegNext` 读出。BPU 内部偶数指针不变量仍需“合法 redirect 读取已
写入、索引／代次正确的 metadata 槽位”这一系统级前提，独立 BPU DUT
没有覆盖 FTQ 存储及 IFU/backend 的合法读资格。六项源条件变异均拒绝，
但并未证明全系统前提，也不是已确认的 RTL 缺陷。见
`results/coverage-bpu-phr-ftq-scope-readonly.json`。奇数目标及原生分母全部保留。

### PHR 真实方向修正与 taken 零指针回绕候选

隔离候选 `/tmp/bpu-phr-override-candidate-DcONiS` 的最终 `combined-full-v3`
实际通过 320 项测试：310 项纯模型检查、两种完整外部恢复矩阵、S2/S3 ×
持续流／背压的四个 not-taken 修正场景，以及相同四格的 taken 零指针回绕。
十项恢复、二十项最终训练窗口方向修正和八项回绕负对照均为普通 contextual
FAIL，无 teardown ERROR。负对照只在最终准备完成的目标窗口触发，不能以
准备期间的其他真实修正替代新场景的检测资格。新建功能组在全部比较后采样；
方向修正与回绕各 24 个 bin 全命中，原外部恢复矩阵的 208 个奇数零 bin 仍保留。

not-taken 场景用真实 MicroBTB taken／MainBTB counter=1，及真实 TAGE
provider=4／SC not-taken 训练，分别观察有效 S2/S3 修正，检查指针从 46 恢复
为 48 而非再次减二。`prediction.ready=0` 时，已接受的旧 token 仍推进修正。
独立逐拍模型检查全部 52 格、76 个 fold 寄存器、pending、完整 metadata 及
fire/flush 关联。driver 的 DriveStable 完成时刻与统一观察时刻不混用：后续
事务边界取实际完整 payload 匹配的 redirect 接受事件，不放宽时间匹配。

首版原生 admission 因目标 1566/1576 仍为零而实际失败，失败源码、全部
LCOV/dat 和 `native-combined-v1/failure.json` 保留。这才发现它们是内层
`taken && pointer.value<2` 回绕路径，而不是外层 not-taken 行。真实 NT
场景虽已通过，但不能声称关闭这两行；当时 PHR 仍为 2881/4300，集成 BPU
候选为 29077/46541（额外 115 行来自其他 BPU 子模块，原生分母未变）。
源码审查覆盖 416 组 taken／pointer／flag 输入，六个源码变异均拒绝。见
`results/coverage-bpu-phr-pointer-wrap-review-readonly.json`，它明确更正之前
warmed 报告中的目标角色，不改写历史报告，也不扣任何分母。

新回绕场景从真实第一笔 S3 输出取得 pointer=0 的 metadata，以该块末尾
条件分支的 NT fallthrough 恢复到下一块，再用真实 MainBTB taken 或
TAGE not-taken／SC taken 触发有效中晚级修正，指针实际 0→50、flag 0→1。
两级目标原生 raw 已为非零，持续流和背压版本全部通过。完整三组原生
合并 admission 已实际通过：冻结基线 28290/46541、暖启动恢复矩阵
28962/46541、完整候选 **29080/46541**，恰关闭 **790 行**；较暖启动再
关闭 118 行，PHR 共关闭 670 行至 2883/4300，含正确的 1566/1576 回绕
目标。无新缺口、分母不变。十条实际轨迹独立重放核对 8080 周期、
420160 次物理格比较和 614080 次折叠寄存器比较。其余增量在 CommonHR、
SC、TAGE、WriteBuffer、replacer 的真实训练路径，按模块分别列出，不全归功
于 PHR。见 `results/coverage-bpu-phr-direction-repair-candidate-readonly.json`。

第二次 admission 恰与正式 261 点报表生成重叠，虽目标已闭合，仍因四份
保护报表的 SHA 变化而拒绝发布；`native-combined-v2/failure.json` 和全部
来源保留。待正式全流水线、独立审计、正常收集保护全部结束后，用同一
未改动源码在新目录 `native-combined-v3` 重跑才成功，未绕过保护门禁。
新的正式 261 点四份报告、验证计划、340 份 raw 账本及 38 份 BPU raw
副本也已保存到 `/tmp/bpu-phr-integration-candidate-kxL2GQ/baseline261`，为
下一轮真实仓库迁入准备基线。该准备时点 PHR 尚未迁入正式运行源码或清单，
不能把本段候选增量计入当前主表；全系统 FTQ 合法读资格和奇数目标仍未证明。

### PHR 正式实现迁入，完整刷新已审计（2026-10-08）

独立模型、静态 VPI Bundle、同拍 monitor、fire/flush 关联、Scoreboard
检查和功能覆盖定义现已迁入 `suites/frontend/bpu/bpu_phr_*.py`。`BpuAgent.observe_phr`
独占同拍观测时通过公开 `aclose/start` 交接普通流 monitor，退出后创建新
monitor；不再用原型代理或访问私有 `_queue`。公开 `BpuRedirect` 保留
原两参数形式，新增 keyword-only 的 cfi_pc/taken/branch_type，恢复目标
与分支 PC 可分离。用例只选择恢复、方向修正、回绕及持续流/背压意图。

迁入门禁先发现纯测试重命名遗漏，随后真实背压场景发现普通流 monitor
移除后异步交付造成前台依据旧一拍的 S1 接受记录行动。两轮失败日志均
保留；未放宽背压断言，而将比较和记录移至 `@on` 同步 capture，驱动仍
经原有公开 API。最终同版源码通过 342 项纯门禁和十个完整硬件场景；
38 项最终窗口观察故障均为带 request/observed_tick/status 的普通 FAIL，
无 teardown ERROR。原有 38 项 BPU 测试为 36 PASS、2 strict XFAIL，
另两个真实 DUT 的成功/异常退出消费权交接测试均 PASS。

仅合并实际迁入测试的十份正向 raw 与 38 份冻结 formal261 BPU raw，
再次精确得到 **29080/46541，新增 790 行**；PHR 新增 670 行，分母不变、
无新缺口。十条实际轨迹重放为 8080 周期、420160 次物理格比较、
614080 次 fold 寄存器比较和 1196 次因果关联。见
`results/coverage-bpu-phr-promoted-isolated-admission.json`。

需求 BPU-INT-034–038 已登记。登记后的 AST 对照确认只追加需求、feature
marker 和公开导出列表，没有更改通过门禁的运行行为；正常全仓收集
2622 项、266 个需求，原四份正式报告字节不变，见
`results/coverage-bpu-phr-registered-admission.json`。完整刷新于 UTC
05:39:59 启动，冻结 1030 份运行源码及依赖状态，目录为
`/tmp/bpu-phr-integration-candidate-kxL2GQ`。该任务随后真实退出 0，结果为
2615 PASS、7 strict XFAIL、0 SKIP；266 个需求全部执行，259 PASS。
352 份新鲜 raw、163 份功能 JSON／164 组，以及十份 HTML／JSON／LCOV
通过完整一致性与时效审计；正式 BPU 恰关闭同样 790 行，其他九 DUT
指标及逐行缺口集合不变。2622-item 正常收集保持四份正式报告字节一致。
上述增量现已计入主表。208 个未获全系统资格的奇数 pointer cross bin
原样保留，功能组聚合为 99.17665989159892%；新增必需未命中 bin 令聚合
下降，不扣掉奇数格或用五项需求 PASS 代替功能矩阵闭合。

审计首轮因依赖 git status 新增外部 `xreactor/design/drafts/` 被拒绝。
独立限定新增五份 class-coverage 设计草稿，确认不位于 src，也未被运行
源码引用；重新枚举的 1030 份运行文件集合及全部 SHA、分支／提交和已安装
runtime 与冻结记录一致。报告明确记录 `dependencies_unchanged=false`、
`runtime_dependencies_unchanged=true`，不伪称整个工作区无变化。第二轮
又发现 recovery cross helper 校验 instance 却不返回该摘要字段的 KeyError；
保留两轮失败记录和原脚本，第三版仅补齐已校验组名后完整审计成功。
未重跑回归、切换分支或删除用户草稿。见
`results/coverage-bpu-phr-refresh-audit.json` 和
`results/coverage-bpu-phr-collection-protection.json`。六项既有 RTL 问题、
FTQ 全系统资格及整个验证目标仍未闭合。

### AheadBTB 替换状态真实并发缺口（2026-10-08，隔离候选）

当前正式 AheadBTB 剩余 5120 个原生映射行，分布为 AheadBtb 4051、
AheadBtbReplacer 905、ReplacerState 140 和 WriteBuffer 24。不能把它们
全部解释为未遍历的 counter 地址：替换器也存在尚无明确行为对照的并发路径。
上述计数与源码分类来自当前 5.052，非历史 5.026 点数。

`AheadBtbReplacer.scala` 使用两个 PLRU 写端口，同 set 时较高物理序号
的 trainWrite 优先；两个端口各自从旧状态计算，不是先执行 read-touch
再执行 write-touch。不同 set 时两个更新都应保留。但端口名字不能代替
顶层语义：`AheadBtb.scala:373–376` 实际以 T2 taken/hit 训练触发 read 端，
以 bank 的 SRAM write-response 触发 write 端。仅同时发 predict/train
并不能证明该冲突发生。

新隔离原型复用 AbtbAgent 的真实 lookup、PulseDriver、Scoreboard 及
只读 VPI 静态 Bundle／`@on` monitor。先在真实同 bank 预测读压力下
缓存分配写入，再发送另一居民的真实命中 metadata 训练，并立即释放
读压力。监视器必须观察到同拍两个端口实际有效，且地址／way 与公开意图
完全一致。延迟一拍释放的对照没有重叠，未把这些普通 PASS 当并发覆盖。
独立三位树 PLRU 模型从真实 reset 开始，不以观测状态回填参考状态；
每拍检查四 bank 的全部 64 格及影子实现，并比较 victim。训练读选择
非幂等 touch，同 set 的错误顺序合并和不同 set 的漏读均会改变预期。
冲突后再发新的公开分配，检查实际替换 way 及完整居民／邻项 profile，
避免只用冲突前已选好的第一笔 victim 证明冲突结果。

已通过 269 项纯模型／完整地址解码检查，和四 bank × 四 victim ×
同／不同 set 的 32 个强制并发场景。这里的公开 pc 是 PrunedAddr.addr，
独立译码为 `index=((pc<<1)^path_hash)&255`，bank 为低两位、set 为高六位；
不能对已剪裁的 pc 再右移一次。32 条轨迹的完整逐拍记录另行独立重放。
八项观察故障负对照全部产生带 expected/actual/observed_tick/status 的
普通 ScoreboardMismatch FAIL，无 SKIP、XFAIL、超时或 teardown ERROR。
首轮负对照门禁的报告组装遇到重复字典键 TypeError，原日志保留，修正仅
报告组装后在新目录重跑全部八项，未更改实际比较或正在运行的冻结源码。

57 份 AheadBTB 正式 raw 均按此前已审计账本的 SHA 封存。只合并最终
32 场景的八份正向 raw，原生候选为 **12899/17854（72.25%）**，相对
正式 12734 行恰关闭 **165 行**：AheadBtb 60、AheadBtbReplacer 101、
ReplacerState 4。没有新缺口，原生分母不变，不混入负对照或相位探测 raw。
见 `results/coverage-abtb-replacer-prototype-readonly.json`。此结果仅为
隔离候选，尚未登记新 feature 或迁入正式实现，不修改主表或正式 manifest。

全部 4 bank × 64 set × 4 victim × 同／不同 set，共 2048 个强制冲突组合
已于 UTC 06:05:25 在 `/tmp/bpu-abtb-address-candidate-TryLMg` 启动。
该任务随后真实退出 0，八项硬件 pytest 全部通过；全轨迹独立重放确认
2048 个实际同拍冲突，而非仅提交了 2048 对输入。与上述 57 份冻结正式
raw 合并后，候选为 **15406/17854（86.29%）**，恰关闭 **2672 行**：
AheadBtb 1627、AheadBtbReplacer 905、ReplacerState 140。替换器及其状态
模块全部原生行缺口关闭；WriteBuffer 的 24 行不变。新增集合包含全部
165 个先导场景闭合行，没有新缺口，未更换源码／构建／处理器或扣减分母。
见 `results/coverage-abtb-replacer-full-readonly.json`。这仍是隔离候选，
须正式实现迁入、登记需求、真实全仓刷新及独立审计后才能更新主表。

另一隔离候选 `/tmp/bpu-abtb-counter-candidate-210wYR` 以独立方向计数器／
PLRU 模型、只读静态 Bundle／同拍 monitor 和带物理格定位的 Scoreboard
检查全部 1024 格。1044 项纯模型检查、四 bank 的代表硬件场景及十项
实际观察错误负对照已通过；负对照均产生有异常点／状态的普通 pytest
FAIL。完整 4 bank × 64 set × 4 way 的 8192 个方向／饱和 transition bin
和 1024 个 enable／metadata 资格 bin 已真实退出 0，四项硬件 pytest
全部通过；独立重放逐拍核对 104902656 次物理格比较、18432 个已确认
更新、7936 笔公开反馈和 1024 次独立预期分配写回，功能 JSON 的全部
cross 计数与重放一致。单独合并计数器正向 raw 得 **17697/17854**，
相对正式基线精确关闭 4963 行；再合并已审计替换器正向 raw，新增集合
严格等于两者并集，得到 **17830/17854（99.87%）**，总共关闭 5096 行，
无新缺口、分母不变。剩余 24 行全部在 WriteBuffer 的 358–369、376–387。
见 `results/coverage-abtb-counter-full-readonly.json`；不计正式 feature 或
manifest，也不把多个场景命中的同一行重复算增量。
该矩阵本身不证明同一物理格的分配 reset 与方向训练同拍优先级；该组合
另由下节专门场景验证。公开方向及强弱输出已在运行时比较，但临时轨迹尚未保存
完整实际公开输出，不能宣称这部分已获离线重放证明。

PHR 的 2622 项全仓刷新已按上节真实完成并审计；期间未修改它冻结的
1030 份运行源码、验证计划或 RTL。两个 AheadBTB 候选都未混入其正式
manifest；外部新增设计草稿的依赖状态差异另按上述明确门禁处理。

### AheadBTB 同格 reset／方向训练优先级（2026-10-08，隔离候选）

上述 99.87% 的原生行覆盖不能证明 reset 与训练相遇时的优先级。另建
隔离候选 `/tmp/bpu-abtb-counter-priority-IqN0zB`，复用静态 counter Bundle、
同拍 monitor、独立 reference 与 Scoreboard。临时 AcceptedPulseDriver
使用 xreactor AsyncDriver，立即提交返回 XTransfer，返回的接受事件来自
monitor 的真实公开输入 pulse，而非将 PulseDriver 完成时刻冒充接受时刻。
资源所有权通过 close/start 交接，退出恢复原 driver；用例不写内部信号、
不等待 FallingEdge，也不展开 asyncio.gather。

先以四种释放相位交叉增／减向，八项真实 DUT 测试通过：仅相位 0 各观察
一次同拍、同 set、同 way 的 SRAM reset 与 T1 方向训练；另外六项普通
PASS 没有碰撞，不计优先级覆盖。随后 4 bank × 4 way × 4 counter 初值
× 双方向，共 128 个组合全部通过；每个组合都要求实际碰撞恰一次，下一拍
完整 1024 格与参考状态一致，真实公开替换结果的 target／position／方向／
强弱及 metadata 也检查。128 项手算纯模型检查和六项实际窗口观察错误
负对照通过；负对照均普通 ScoreboardMismatch FAIL，带异常点／状态，
没有 teardown ERROR。

实际终态 0 后，对 128 条输入／全部物理状态／实际公开输出轨迹及四份
功能 JSON 独立重放；四个 32-bin cross 均为 100%。其中 96 个组合能
区分错误优先级，另外 32 个 inc1→2／dec3→2 本来就与 reset 值相同，
保留并明确标作非区分性结果，不宣称它们单独证明 reset 获胜。该矩阵使用
物理 set5，不宣称 64 个 set 的优先级全交叉。加入其四份正向 raw 后，
原生行数仍为 **17830/17854**，新增 **0 行**：这是新增功能组合证据，
不是刷出额外行覆盖。见 `results/coverage-abtb-reset-training-priority-readonly.json`。

剩余 WriteBuffer 24 行分别是 shadow 槽 **2／3** 的条件块尾行及完整 entry
赋值：358–369 对应 `entries_0_2_*`，376–387 对应 `entries_0_3_*`。
此前按邻接块误写成 1／2，已依据实际赋值名更正。不能按 counter 地址缺口
解释，也尚无不可达证明。下一步需在同 bank 读压力下缓存四个不同 set
的真实分配，实际证明槽 2／3 被占用并在排空后完整回读。相同 set 优先
复用 shadow 槽，所以仅训练四个不同 tag／way 不等于占用了四个 buffer
槽；进一步可更新同 set／tag 的待写 payload，交叉 dirty/clean 及邻项保持。
这与已经验证的同 set PLRU 优先级、counter 地址遍历是不同需求；仍须
实际槽命中证据、完整 payload／状态对照及原生增量审计，不能只发输入
或扣减分母。候选正式迁入、登记需求及下一轮全仓刷新也尚未完成。

### AheadBTB 四槽 WriteBuffer 容量与生命周期（2026-10-08，隔离候选）

上述缺口现已由真实公开输入证明可达，不再只是源码推断。四个 bank 各自在
ascending／descending／interleaved／boundary 四种不同 set 顺序下填满四槽，
在 bank 读压力中确认尚未写入 SRAM；随后依次核对 dirty 同 key 完整 payload
重写、公开停止读流后的逐槽排空、clean shadow 再激活，以及正反完整公开
profile 和邻项保留。256 个 bank×顺序×槽×生命周期 cross bin 均在独立状态
比较通过后命中。静态 Bundle／`@on` 被动采集所有 bank 的 16 槽 payload、
dirty、shadow-valid、PLRU 和 drain；参考状态仅来自已接受公开反馈及实际
ready 握手，不由观察到的内部状态回填。

最终源码的 311 项纯模型检查、十项实际观察变异负对照和四项完整硬件矩阵
全部通过相应门禁；负对照为带上下文的普通 ScoreboardMismatch FAIL，
不是超时／SKIP／XFAIL／teardown 错误。终态为 0 后独立重放全部输入、
完整槽状态、counter、drain 和实际公开输出，并逐笔核实使用的 cold metadata
确实来自更早的真实预测。仅合并正向 raw，与此前三项已审计候选的并集从
17830/17854 精确提升到 **17854/17854（100%）**，恰关闭槽 2／3 的 24 行，
无新缺口、分母不变；相对正式基线合计关闭 5120 行。
见 `results/coverage-abtb-writebuffer-capacity-readonly.json`。

这仍是隔离候选，不是正式报告刷新，也不等于 AheadBTB 功能验证完成。
full-row dirty overwrite 尚无硬件矩阵证明，完整 FTQ metadata 资格及其他
分支仍待核查。实际生成 RTL 的 WriteBuffer PLRU 仅在 miss 时更新；hit
touch 的设计意图需单独审查，不能把参考模型匹配当前实现当成意图正确证明。
前述首次负对照工具自身 TypeError 已保留为无效门禁，未计入十项有效负对照。

### AheadBTB 候选迁入进展（2026-10-08，正式刷新前）

四类候选已迁入 `suites/frontend/bpu/abtb_state/`：独立 model、静态 monitor、checker、
driver 与复用 scenario 分层；`tests/abtb/testcase/test_state_matrix.py` 只调用
意图级场景，没有 IO getter/setter、FallingEdge 或 asyncio.gather。临时训练
writer 的信号所有权由 `AbtbAgent.using_training_driver()` 和 StateObservation
统一接管／恢复，原有 `agent.train*` 使用相同编码 payload，不能因替换而失配。
Counter 的公开响应与 cold/disabled metadata 来源现在也落盘；replacer 另有
独立的 bank×set×victim×same/different-set cross，不把行命中冒充功能完成。

当前已实际完成：1849 项纯模型／scope／coverage／清理检查、12 项硬件代表、
八项真实接管／正常返回／body/setup 异常／pending 取消后的训练恢复、57 项
原有 AheadBTB 回归，全部 PASS；34 项观察变异均为有状态上下文的普通 FAIL，
无 teardown 错误。代表轨迹的独立公开输出／metadata 来源重放也已通过。
完整 20-item 硬件矩阵随后于 08:41:34 UTC 实际结束，20 PASS，耗时约 55 分钟。
入场审计已独立重放 144 份轨迹，确认 24 个功能组／11648 个 cross bin，
原生候选恰好从 12734/17854 到 17854/17854，关闭 5120 行且无新增缺口。
counter 的实际公开响应与 metadata 来源重放通过；replacer 的实际端口冲突、
公开居民 profile 与独立分配重放通过，但未采样公开 T0 输入，也不宣称
counter-strength 离线重放。见 `results/coverage-abtb-production-admission.json`。
离线重放工具首次遗漏 `itertools.product` 导入的失败版本已保留并更正，
不是 DUT 缺陷，也未计为有效负对照。

冻结的正式基线仍为 266 点、352 raw 及本节表格的十 DUT 原生行数字；报告、
全部 raw 账本和 57 份 AheadBTB raw 的 SHA 备份见临时迁入审计目录
`/tmp/bpu-abtb-production-Cqa2Di/`。入场审计通过后已登记 BPU-ABTB-049～052；
AST 与计划比对确认仅增加功能标记和四条需求，没有改变测试行为。
正常收集实际为 4499 项／270 点，并保持四份旧正式报告字节不变，见
`results/coverage-abtb-production-registered-admission.json`。
08:52 UTC 已启动实际 `tests/run_all.py` 全仓刷新，冻结 1059 个运行源码、
依赖分支／提交／脏状态及安装库身份。执行中根目录的 raw 和功能 JSON
属于中间态，不能与旧 manifest 混用申领时效或新增正式命中；完整进程结束
并通过同源／增量审计后才更新正式表格。集成 BPU 也不能
借用独立 DUT 的覆盖率：其正式 17461 行缺口中，AheadBtb 5115 行、两种
MicroTAGE BypassShadowBuffer 合计 6998 行，仍须独立集成场景资格与实际证据。

迁入期间还发现旧回归隔离 wrapper 第一版只重定向 DUT raw，没有重定向
旧用例固定的 REPO_ROOT，导致 34 份已有 AheadBTB 功能 JSON 的时间戳属于
这次旧回归，而非原完整正式运行。第一版证据保留；第二版只修改该 pytest
进程中的报告目的地，57 项全部通过，34 份 JSON 均写入隔离目录，逻辑 bin
与第一版相同且不再触碰仓库文件。四份正式报告与全部 352 份正式 raw 已
逐项核对原 SHA 不变，见 `results/coverage-abtb-production-interim-protection.json`。
这不恢复原功能 JSON 的时间戳，因此禁止用这些混合轮次文件申领新增正式
覆盖；后续必须通过一次完整刷新统一重建功能 JSON／LCOV／HTML。

### 集成 SC 连续反馈诊断的仲裁前提（未获得候选覆盖）

首次隔离脚本误用 `Transfer.tick`，实际应读取 `Transfer.event.tick`；
失败版本和 FAILED／teardown ERROR 日志保留，不算 RTL 负对照。
第二次脚本改正采样字段，但直接在连续预测中等待八笔同 bank 反馈，且没有
周期截止与采样上限。运行约 13 分钟后 RSS 已超过 3.2 GB，因无界等待／
持续增长的采样缓存，定点终止该诊断子进程；父运行器实际记录退出 -15。
没有通过结果、有效 candidate raw 或正式覆盖增量。

源码确认 `Bpu.sv:1288` 的训练 ready 同时依赖 TAGE／SC；`Sc.sv:1129/5208`
规定 `t0_needWrite && s0_fire && t0_bankMask == s0_bankMask` 时 SC 不接受训练，
`Tage.sv:9911` 也检查训练读与预测读冲突。此时驱动送入的 transfer 可以持续
pending；仅调用 burst API 不保证任何训练被接受。本次耗时与这个饥饿前提
一致，但未获得逐拍训练 ready 轨迹，不能据此登记 RTL 死锁缺陷或新功能 PASS。
后续候选应显式提供训练读窗口、捕获实际 ready/valid 和 payload，并以
`AnyOf(TaskComplete(...), ClockCycles(...))` 等现有 xreactor 组合提供周期上限，
将诊断截止与取消清理封装在 helper，不能暴露给意图级用例。
失败／终止配方与实际收尾记录在 `/tmp/bpu-sc-burst-diagnostic-22qJY8/`。

### 集成 SC 有界反馈对照与独立 mask 候选（尚未正式登记）

后续独立目录 `/tmp/bpu-sc-bounded-diagnostic-DyuAem/` 为每个操作增加硬件周期
截止、取消清理和最多 512 个采样帧，并实际捕获训练 valid／ready／完整 payload。
测试只调用场景 helper；静态 Bundle 和 CycleMonitor 负责相干采样，训练仍由
现有异步 driver 完成。所有输出隔离，正式回归的 1059 个冻结运行源码不变。

同一份真实捕获 metadata、同 bank/index、两个同 SC way 的 NT 分支，八笔反馈
在最密集情况下确实相邻接受，但 path/imli/bias 三表八次都写回 6-bit 的 62
（即 -2），公开 SC 回读仍未达到使用阈值。加入不同间隔后，实际接受间距为
1／2／3／4／5／25 个周期：1 周期时只保留一次减计数；2／3 周期时序列是
62,62,60,60,58,58,56,56；4／5／25 周期的序列才是完整的
62,60,58,56,54,52,50,48。六项对照实际为三项普通 FAIL、三项 PASS，
没有改成 XFAIL 或减弱累积预期。第一次对照检查器把 tuple 与 list 直接比较，
其错误版本及六 FAIL 输出已保留；更正仅统一预期容器类型，随后完整重跑。

`Sc.scala:442–467` 的旧计数来自 table 的 trainReadResp；
`ScTable.scala:94–96` 的 trainReadResp 直接选择 SRAM 响应，而 pending
WriteBuffer 只参与写回，不向训练旧值旁路。实际序列与这一缺少旁路的局部
解释一致。尤其 2／3 周期对照的公开 useScPred／sumAboveThres 已通过阈值，
若只检查“最终学会”便会遗漏未累积的反馈。因此缺少的检查需求是连续已接受
反馈的计数持久性，而不只是最终预测方向。不过本诊断重复同一 captured
metadata，尚未证明完整 FTQ 流水合法性，不能直接登记为已确认的系统 RTL
规格缺陷。独立完整输入重放与纠错审计见
`results/coverage-bpu-sc-feedback-cadence-readonly.json`；该混合正负运行的全部
raw 都排除于候选和正式覆盖合并。

另一个正向场景仅相邻发送两个不同 SC way 的独立 NT 反馈，不重复更新同一
计数器。正反两种顺序均实际 PASS；way 1/3、bias way 4/14 的 mask 在真正
dirty-hit 中合并，保留未选 way 的非零旧值。参考模型从显式全零 shadow
前提开始独立维护状态，比较十个 buffer 的全部四槽、valid／dirty／index／
mask／data，共 1420 个 buffer-frame 比较、六次 dirty 合并；同时核对实际
公开接受 payload、captured metadata 来源、所有 table 写入及公开 SC 回读，
TAGE provider 保持不变。20 项离线轨迹变异均被带上下文的断言拒绝；它们
不是实际 DUT 负对照，也不是复位阶段采样或完整 FTQ 参考模型。

在正式 BPU 模块重跑前已独立封存原 50 份 BPU raw，逐文件确认冻结 SHA，
原生重合并精确复现 29080/46541 及原缺口集合。只在临时目录加入上述两个
通过场景的 raw 后，候选为 29154/46541，精确关闭 74 行：
`WriteBuffer_30.sv` 19 行、`WriteBuffer_38.sv` 55 行；无新增缺口、分母不变，
456 个已分类局部矛盾行均未被关闭或剔除。缺口位置例如
`WriteBuffer_30.sv:342` 正是此前指出的 dirty-hit 合并体。见
`results/coverage-bpu-sc-distinct-masks-prototype-readonly.json`。
这 74 行尚未登记功能 PASS、迁入正式场景或计入本节正式表格；两 bank／
多 index／更多 mask／clean 生命周期、实际 DUT 负对照、完整 FTQ 资格及
SC 连续同计数器反馈问题仍需继续验证。ABTB 全仓正式刷新仍在运行。

### 集成 SC 的真实复位／输入派生参考资格（代表场景新增 112 行候选）

后续独立资格目录为 `/tmp/bpu-sc-masked-production-92WiV2/`。SC bank 来自
PrunedAddr 的 addr[0]，不是架构字节地址 bit 0；因此代表场景同时使用
0x40000800／0x40000801 等裁剪地址，并交叉两个实际 index 与不同 position
配对。静态 Bundle／CycleMonitor 还采样完整 drain payload，checker 使用
xreactor Scoreboard 保留逐字段差异、case／phase、observed_tick 和状态。

新参考从实际 reset 采样开始，独立维护十个 buffer 的四个完整 shadow 槽和
SRAM 内容；每个真实接受的完整反馈先与计划、captured metadata 比较，再由
参考 SRAM、真实分支位置／方向／资格派生后续完整 table 写 payload。预测
状态不以 DUT 前态重新播种。排空时比较完整 payload，再独立更新参考 SRAM。
dirty 合并后重新捕获公开 metadata，再相邻反馈，验证 clean 重激活和未选
counter 保持；不是把两次重复的初始 metadata 当作第二个生命周期输入。

四个代表场景实际 PASS，包含另一 bank、不同 index、不同 mask 及 clean
重激活。独立离线重放 2006 个硬件周期、83876 项比较和 12 笔真实接受反馈
通过；1352 项手算 mask／drain 优先级、signed saturation、scope 和 reset
纯检查通过。该纯测试有一条 pytest 参数迭代器弃用警告，尚未改动正在冻结的
配方源码，也不把警告计为硬件失败。

十项实时 DUT 观测故障负对照的首版在报告收尾调用 asdict(status)，深拷贝
含 keyword-only 构造函数的 ScoreboardMismatch，导致 TypeError 遮蔽原
比较异常。首版源码／输出保留，不算有效负对照。修正放在另一个独立目录
`/tmp/bpu-sc-masked-negative-wFZvjs/`，仅按字段序列化异常为 repr，未修改
运行中矩阵的源码或比较逻辑。重跑十项均为普通 ScoreboardMismatch FAIL，
包含完整输入、写 counter／mask、已选／未选 shadow、dirty、合并 mask、
drain payload 与另一 bank 的故障；均有字段差异／时刻／状态，无 teardown、
超时或背景异常。这些故障作用于实时采样观测，不是篡改硬件内部状态。

只将四个通过代表场景的 raw 加入之前独立封存的 50 份 BPU 正式基线，候选
为 29192/46541，精确关闭 112 行，包含先前全部 74 行并另增 38 行；无新增
缺口、分母不变，456 个局部矛盾行保留。按源码为 WriteBuffer_30 23 行、
WriteBuffer_38 58 行、Sc 26 行、Tage 三行和 FoldedSRAMTemplate_37 两行。
独立输入／状态重放、负对照纠错资格及原生合并审计见
`results/coverage-bpu-sc-masked-smoke-qualification-readonly.json`。

完整两 bank × 两 index × 六种 way 配对 × 正反顺序 × dirty/clean 生命周期
共 96 组合矩阵已启动；功能 cross 只在全部比较通过后采样，运行中的部分
bin 不能当作 96/96 完成。该矩阵及 ABTB 全仓刷新仍须实际终态、独立审计，
后续才可迁入／登记／刷新正式覆盖。参考仍不预测仲裁 ready、不独立重建
PHR 到 train-path index，也未采样实际 T0 输入；commonHR=1、全部 index／
bias low-bit、满 dirty 覆盖及完整 FTQ 合法性不在当前资格内。正式表格保持
原基线，不计任何失败／负对照／隔离候选 raw。

### 集成 SC 的 96 组合矩阵独立审计（125 行候选，仍未正式登记）

上述完整矩阵于 2026-10-08 09:47:13 UTC 实际退出成功：96 PASS、96 份独立
raw，bank × index × 六种 position 配对 × 顺序 × 生命周期的 96 个 cross bin
均恰好采样一次。独立审计重新构造参考并重放 48144 个硬件周期、2013024 项
比较及 288 笔真实接受反馈；1352 项纯检查和十项有效实时观测故障对照继续
通过资格检查。审计见 `results/coverage-bpu-sc-masked-matrix-qualification-readonly.json`。

仅合并这 96 份通过场景 raw 与封存的 50 份 BPU 正式基线，候选为
29205/46541，精确关闭 125 行：WriteBuffer_30 24 行、WriteBuffer_38 63 行、
Sc 33 行、Tage 三行、FoldedSRAMTemplate_37 两行。包含代表场景全部 112 行，
并另增 13 行；没有新缺口、分母不变，456 个已分类局部矛盾行全部保留。
新增行包括 `WriteBuffer_30.sv:349` 及 `WriteBuffer_38.sv:829/837/877` 的
其他 mask lane 保持分支，以及 `WriteBuffer_38.sv:1348/1388` 的 clean-hit
未选 counter 保持。因此不能以单一 way 配对或只核对最终方向，替代完整
不同 mask 与 dirty/clean 生命周期的逐字段检查。

训练入口仍是该版资格的缺口。picker VPI 能只读取得实际 SC T0 输入、训练
read 请求和响应，能力探测输出隔离在
`/tmp/bpu-sc-masked-production-92WiV2/port-discovery-v1/`，不计覆盖。后续独立
阶段 `/tmp/bpu-sc-masked-t0-DVBBN3/` 已用自包含静态 Bundle 去掉旧临时 monitor
依赖，并通过四个实际硬件代表场景：对照公开完整输入到 SC T0 的投影、实际
enable/fire、五表训练读 valid/index/bank，以及三表下一周期完整 SRAM 响应。
索引由实际 PC/folded-history/commonHR 输入计算，再与 captured debug index
对照；参考仍不由 DUT 前态播种，也不声称已独立重建完整 PHR/FTQ 历史。
收尾按字段安全序列化 Scoreboard 异常，不再用 asdict 深拷贝异常；纯测试参数
迭代器改为 tuple。新版本的完整矩阵、纯检查和二十项实时观测故障对照正在
资格运行，未获得实际终态及独立审计前不替代上面的已审计候选，更不计正式
功能 PASS。ABTB 全仓正式回归仍在运行，本文正式表格保持已审计基线。

### T0 完整资格与多 key 暴露的 preedge 控制采样缺口

T0 版本完整 96 场景于 2026-10-08 10:14:29 UTC 实际成功退出。独立重放
48144 个 rising 周期、3111120 项比较、288 笔接受反馈和 864 个完整训练 SRAM
响应通过；1379 项纯检查及二十项实际实时观测故障对照通过资格核对。
只合并该 96 份正向 raw 与封存 BPU 基线，仍精确关闭相同 125 行，没有额外
增量或新缺口。见 `results/coverage-bpu-sc-masked-t0-qualification-readonly.json`。
控制门禁首版把 AST 中的 dict(...) 当作 literal_eval 字面量而报错，未生成
资格报告；保留首版后，仅按 dict 关键字读取常量修正，二十个指定故障字段及
状态均核对通过，见 `results/coverage-bpu-sc-masked-t0-controls-readonly.json`。

剩余深槽缺口促成新的四真实 key／两 bank 诊断。首版两项普通 FAIL 都在
最后一笔接受后发现槽 0 dirty 比参考提前清零，失败 raw 不计覆盖。另加只读
DriveStable 探针后，同一失败边界实际为：rising tick 2440 训练 valid=1、
训练 read=1、drain.ready=0；preedge tick 2441 已撤销 valid、read=0、ready=1，
四槽仍 dirty；rising tick 2442 槽 0 已排空。使用原 rising 的 ready 做单步
推演不符，使用实际 preedge ready 后十个 buffer 的完整下一状态全部吻合。
这项单步诊断使用观测前态，仅证明控制采样假设有误，不是独立完整参考证明，
也不是已确认 RTL 缺陷。见 `results/coverage-bpu-sc-four-key-phase-diagnosis-readonly.json`。

独立修正版 `/tmp/bpu-sc-masked-phase-zwB6zg/` 将控制与状态分开：rising
比较已提交状态、公开接受和 T0/read 响应；DriveStable 再比较完整 preedge
状态、派生 write 和 drain，并用此时实际 ready 推进下一状态。两个观察流
各自有界，均记录实际 tick，不篡改原 rising 快照、不用 DUT 状态重新播种。
测试仍只调用意图 helper，不暴露边沿。四个代表场景真实 PASS，按时间合并
两条记录流的独立重放通过 2006 个 rising、2006 个 preedge 和 212998 项比较；
见 `results/coverage-bpu-sc-preedge-smoke-replay-readonly.json`。同版本 1379 项
纯检查通过，完整 96 矩阵和原二十项故障对照继续资格运行。另四项 preedge
ready／write／未选 state／drain 实时观测负对照均产生普通 ScoreboardMismatch
FAIL，仍须并入该版本完整独立门禁；全部负对照 raw 排除。

相位修正版重跑同一四 key 刺激时，首版嵌套 conftest 重复创建输出目录，
收集阶段 exit 3，属于无效运行。限制 confcutdir 后实际两项普通 FAIL 已越过
原 dirty 边界，但在首轮公开回读发现一个 position 的 TAGE provider 不存在。
该多 key／历史上下文留存前提尚未证明，不能弱化 provider 断言、将其改为
XFAIL，或据此登记四 key PASS／关闭深槽覆盖；也不能将问题直接归因为 RTL。
失败配方、收据和所有 raw 保留在修正版的 `depth-check/`，不计任何覆盖。

相位版本的故障资格审计随后完成：1379 项纯检查、20 项 rising 观测故障和
四项 preedge 观测故障全部核对通过。24 项均为预定字段上的普通
ScoreboardMismatch FAIL，含 tick、差异和状态；无 teardown、超时或背景
错误，没有写硬件内部状态，全部负对照 raw 排除。见
`results/coverage-bpu-sc-preedge-controls-readonly.json`。这证明检查器对这些
故障敏感，不替代尚在运行的完整 96 正向矩阵，也不增加正式覆盖率。

先前准备的机械迁移位于 T0 目录的 promotion/，只证明当时的 import／包
拆分等价，尚未安装。由于随后发现并修正采样缺口，正式迁入必须基于最终
相位版本重新生成并资格化，不得直接安装旧草案。正式全仓运行的源码、RTL、
DUT 和外部依赖继续保持冻结，正式表格不计这些候选或诊断。

### 四 key provider 的历史上下文诊断（不计覆盖）

新增静态 Bundle／CycleMonitor 只读记录 TAGE 的实际请求、tag 折叠历史、
两 way 表项和顶层写入。原四 key 刺激和 provider 断言完全不变，实际仍为
一项普通 FAIL；1283 个硬件周期记录及源码冻结已独立核对。第三个 key
PC 0x40004100 的原预测为 table 3／set 67，tag folds 为 7815、1280，way 1
确实含 tag 7073、counter 3；回读请求却为 set 73，tag folds 为 6811、5488，
该地址两 way 均无效。两笔公开 PHR pointer／low bits 完全相同，并不意味着
完整历史内容相同。期间没有观测到该 table 原 set 67 的顶层写入，但这不是
原 SRAM 单元持久化证明，更不能据此证明完整 PHR／FTQ 正确或有 RTL 缺陷。
见 `results/coverage-bpu-sc-four-key-provider-context-readonly.json`。

仅把公开回读改为由新到旧，第一轮四 key 的原 provider 和两位置 SC 结果
全部保持正确；第二轮仍在第三 key 的 provider 断言失败。原所有断言保留，
从真实 reset 独立按 tick 重放 rising／preedge 两流，146385 项比较、16 笔
接受反馈、48 个完整训练 SRAM 响应通过；这只是失败配方的状态证据，
不是完整场景 PASS 或深槽覆盖率增量。见
`results/coverage-bpu-sc-four-key-rollback-prefix-readonly.json`。两次诊断的
全部 raw 继续排除，尚需解决多次回滚后的完整历史留存和全局 FTQ 资格。

对原失败刺激再加现有 BpuPhrMonitor 的 52 单元／76 个 folded 寄存器只读
观测后，从真实 reset 独立重建全部 1283 周期成功，未用观测前态播种。
tick 2538 和 2548 的正常 redirect 改写物理单元 0、1、2、8；在同一
pointer 36 下，对应逻辑历史位 15、16、17、23，均不在 metadata 保存的
低 13 位中。因此相同 pointer／low bits 的恢复不能保证旧 key 的完整
查表历史仍在。独立推导的 folded 历史也与实际 TAGE table 3 输入一致。
见 `results/coverage-bpu-sc-four-key-full-phr-context-readonly.json`。这明确了
配方必须保持／重建全路径上下文的前提，不是要求修改 RTL 来复原已经被
其他回滚改写的高位，也未证明该刺激符合完整 FTQ 生命周期。

已从最终相位版本重新生成 promotion/ 草案，并通过五个核心文件、两组纯
测试、七个提取 metadata helper 及 coverage wrapper 的 AST 等价检查；
仅改变导入／包边界，意图测试仍只 await 一个 helper。旧 T0 草案已被新
草案取代，但尚未安装、登记或声称生产执行通过。配套 production-runner
已纳入全部 24 项故障和 confcutdir 隔离，编译检查通过；仍须等待两个原始
运行结束并审计后，才可安装并执行正式代码的隔离资格矩阵。

### 相位完整资格、ABTB 正式刷新与 SC 生产迁入

相位版本完整矩阵于 2026-10-08 10:55:17 UTC 实际退出成功：96 PASS、
96 raw、96 个 cross bin 恰好各一次。独立门禁重新构造参考，按实际 tick
重放 48144 个 rising 和 48144 个 preedge，5111952 项比较、288 笔接受和
864 个完整训练 SRAM 响应通过，并核对 1379 项纯检查和全部 24 项实时
观测故障。仅这 96 份正向 raw 加封存基线仍精确关闭相同 125 行，候选
29205/46541，无新缺口、456 个局部矛盾行保留。见
`results/coverage-bpu-sc-preedge-matrix-qualification-readonly.json`。这替代旧
T0-only 参考的迁入资格，但尚非正式功能登记或正式 BPU 行增量。

ABTB 全仓刷新随后实际成功完成：4492 PASS、7 strict XFAIL、0 SKIP，
270 个需求执行、263 PASS；380 raw、183 功能 JSON、188 组及十份原生
LCOV／JSON／HTML 的时效和一致性独立复核通过。ABTB 精确关闭 5120 行至
17854/17854，v_line 3405/3405、branch 4810/4876；其他九 DUT 的指标和
缺口集合不变。当时 SC 的 125 行候选尚未混入；当前上表已更新到后来
通过审计的 272 功能点基线。

首版正式门禁因 picker／xcomm dirty 状态变化拒绝，保留
`refresh_audit_v1_rejected.py`。实际差异为六项构建规则、构建模板、文档或
独立测试文本，分支和提交均未变化；精确 diff／SHA、1059 份运行文件和
40 份系统库／DUT 副本相等的独立资格见
`results/coverage-abtb-build-edit-transition-readonly.json`。新版门禁明确记录
依赖文本有变，不冒称 unchanged，也不声称新 -fno-strict-aliasing 选项或
ABI2 构建已在本次回归生效；保留外部改动，全部原生分母及完整复算不减。
最终见 `results/coverage-abtb-production-refresh-audit.json`（version 2）；
4499 项正常收集保持新版四份正式报告字节不变，见
`results/coverage-abtb-production-collection-protection.json`。

完成以上两个实际终态及审计后，已将相位修正版的八个组件和三个测试文件
迁入 `suites/frontend/bpu/bpu_sc_state/` 与 `tests/bpu/`。严格 SHA 检查先捕获复制时
多出的末尾空行，已修正为草案精确字节，没有放宽门禁。正常收集为 5974
项，原正式四报告不变；1070 份运行源码中仅既有 BPU conftest 增加输出
fixture，另增八组件／三测试，两个需求尚未登记。见
`results/coverage-bpu-sc-state-pre-formal-collection.json`。

真正仓库 fixture 和两个意图测试的隔离生产资格已启动：完整 96 DUT 场景、
1379 纯检查及 24 实时故障；其中纯检查实际通过，其余仍待真实终态和
独立完整重放。故障对照的 rising 与 preedge 输出采用不同目录前缀，
避免 write_counter／drain_payload 同名冲突。所有输出隔离在
`/tmp/bpu-sc-masked-phase-zwB6zg/production-runner/`，不覆盖正式 raw／报告。
不得以迁入或收集成功替代生产执行资格，或提前登记两个功能 PASS。

生产版纯检查与实时故障资格随后完成：1379 项纯检查 PASS，20 rising 加
四 preedge 故障均在预定字段产生带 tick／差异／状态的普通比较 FAIL，
无 teardown、超时或背景异常。目录前缀隔离正常，24 份负对照 raw 全部
排除，四份正式报告及 1070 份运行源码保持新快照身份。见
`results/coverage-bpu-sc-state-production-controls-readonly.json`。完整 96 正向
生产矩阵仍在运行，部分 bin 不计为完整资格或正式行增量。

### 四 key 角色与真实 common history：仓库迁移后的当前状态

以上探索段落保留各阶段当时的状态；当前正式基线以本文件开头的
272 功能点／29205 行及其独立刷新审计为准。新的三个功能需求已经加入
`verification_plan.json`，但尚不把它们登记为正式执行 PASS：

| 功能点 | 由行缺口发现并补充的场景 | 当前仓库版实际执行 |
| --- | --- | --- |
| BPU-INT-041 | 四真实 key 的 dirty/clean 流水线、四种真实 provider 角色、双 bank／位置／顺序和物理 bias lane | 8/192 代表场景 PASS；完整 192 原型已独立准入，仓库完整矩阵待全仓回归 |
| BPU-INT-042 | 真实 commonHR 有效／无效时，global/BW 预测读取与完整反馈写入资格 | 4/4 PASS；GHR/BW=0，不能外推为全部历史 |
| BPU-INT-043 | 真实前向／后向条件分支产生 GHR=1、BW=0/1，并训练和回读五张 SC 表 | 4/4 PASS；不包含所有历史位、完整 queue 或深流水生命周期 |

迁移保留已准入参考和状态转移算法，只调整包导入、报告名前缀、意图封装及
组合检查器的超时上下文转发；测试用例不暴露边沿、底层 get/set 或 gather。
1681 项仓库纯检查和普通全仓收集实际通过，收集为 7855 项／275 功能点，
旧 272 项需求定义不变。机械证据见
`results/coverage-bpu-sc-role-history-migration-readonly.json`。
16 个仓库 DUT 代表场景于 2026-10-08 15:06:41 UTC 实际退出 0，
16 PASS、184 deselected；随后完整状态／来源／功能 bin 的独立重放已实际
通过。只合并这 16 份 raw 与正式基线得到 29832/46541，与同一基线下
对应的 16 个已准入原型完全相同，包括全部映射行和缺口集合；不能把
代表场景的 192/4608 角色 bin、64/256 物理 bias bin 当作完整矩阵闭合。
见 `results/coverage-bpu-sc-role-history-root-smoke-readonly.json`。
正式准入记录见 `results/coverage-bpu-sc-role-history-production-registered-admission.json`；
它区分原型完整 200 个场景与仓库已实际执行的 16 个场景，不把准入登记
当作全仓执行证据。下一轮正常全仓刷新目标为 7855 项／275 功能点、
676 raw、187 功能 JSON／193 组，独立门禁必须再次核对全部新增 200 轨迹、
原有 96 SC 轨迹及 144 AheadBTB 轨迹，再重新合并十 DUT 并核对 HTML。

恰好用旧正式基线加已准入的 200 份新增正向原型 raw 重新合并，不借用
未迁入的早期实验，得到候选 29954/46541，精确增加 749 行：
`WriteBuffer_38.sv` 516、`WriteBuffer_30.sv` 137、`WriteBuffer_8.sv` 24、
`Tage.sv` 26、`Sc.sv` 27、`CommonHR.sv` 15、`ReplacerState_4.sv` 两行，
`Sc_Anon_1.sv`／`Sc_Anon_2.sv` 各一行。分母不变、没有新缺口，456 个
局部矛盾行全部保留。该候选仍须由完整正常仓库回归及独立审计复现。

下一批集成优先级仍保留：AheadBTB 5115 行、AheadBTB 替换器 1066 行、
两个 BypassShadowBuffer 合计 6998 行，以及 PHR、TAGE、RAS 等未闭合场景。
父模块 `Bpu.scala:150..173` 明确 ABTB metadata 内部从 S1 传到 S3，
由最终 S3 prediction 产生 fastTrain；`abtb/AheadBtb.scala:232` 还要求
fastTrain.valid、abtbMeta.valid 和 enable 同时成立。集成场景必须监控并
关联这条真实链路，再比较完整计数器／替换状态和公开回读，不允许直接
调用独立 ABTB 公共训练端口后宣称集成覆盖，也不能仅消费观察到的任意
fastTrain payload 而不检查其 S3 来源。既有 7 项 strict XFAIL／6 个 RTL
问题及更广历史、SC-used、full dirty overwrite、预测重叠和 FTQ 资格仍未解决。
