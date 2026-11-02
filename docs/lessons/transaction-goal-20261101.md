# 全仓事务/迁移适配目标（2026-11-01，进行中）

2026-11-02用户要求结束本轮连续推进、准备多人/AI协作发布。本次按
[协作检查点](../collaboration-checkpoint-20261102.md)收尾并暂停接续，**不把阶段交付改为整体
complete/unmet**；历史证据保留，目录/命名以[协作约定](../../CONTRIBUTING.md)统一。

## 目标与退出条件

用户通过 /goal 明确要求：修复目前所有验证框架事务适配/迁移适配缺口，直到没有待修复
缺口，并符合 Skill。目标 ID：ff03ca99-7d7f-4752-b8d7-3493ad1ca0a7。整体计划由目标工具
保存；本文件只保存实现证据，不替代目标状态，不将单模块完成写作整个目标完成。

适配需要满足真实合同下的端口与编码严格校验、唯一所有权、正确采样沿/有效条件、不可变
快照、适用的 UID 或固定延迟关联、接受/响应/取消/重试与有界收尾。功能测试只描述事务，
优先复用 Toffee 组件，关键修复必须有合法控制与可区分的错误控制。结构/静态零命中不
代替语义审计；真实硬件 FAIL/XFAIL/UNCERTAIN 与覆盖限制不通过修改 oracle 或豁免消除。

## 初始清单与冻结证据

[机器清单](../history/transaction-goal-inventory-20261101.json) 实际列出十工程、132 DUT
及真实 top、当前缓存身份/原生入口/构建冒烟收据，并逐 DUT 登记仍待核验的七类义务。
这是完整范围清单，不是132 DUT语义已经通过的证据。BPU/FTQ/ICache 的零静态命中仍须
复核配置与生命周期，BPU 分区 collect 中的 coverage marker 注册警告另列待修。

`results/ucv-goal-collect-before-20261101` 的十个收集任务均 exit=0，共 45883 个有序
nodeid，源码前后哈希一致；ucv 总退出码 1 保留 IFU R-13 blocking 残余，不是收集失败。
IFU 修改前完整基线 `results/ucv-goal-ifu-before-20261101` 为 144 PASS / 2 FAIL /
1 UNCERTAIN。其他工程先复用已核验的当前修复证据，首次实质修改前补取所需模块基线。

## IFU PerfAnalysis（已完成本模块，IFU 总任务仍进行中）

下述为初版模块检查点；本轮之后真实red控制发现吞错后finish假成功，已按下方“PerfAnalysis
生命周期复核”节补齐。初版18自检不能证明当时已覆盖该新义务，历史结果不重标。

原 `tests/perf_analysis/test_perf_analysis.py` 包含物理字段编码、逐端口读取、推进时钟、
维护期望状态和比较，虽已有语义 Inputs，仍把 agent/driver/monitor/checker 放在用例里。
本轮将职责移入工程 `perf_analysis/`，并使用真正的框架组件，不提供字段改名/转发外壳：

- `model/perf.py::Inputs` 为不可变事务，严格限制布尔控制及该配置可提供的 FTQ reason
  位；未知字段由构造器拒绝，不再静默丢掉 unsupported bits。
- `ports.py` 绑定全部真实输入和76个输出位，缺口立即失败；只在该层编码物理端口。
- `agent.py` 使用 SyncSingleCycleDriver 和 DriveStable lossless SamplingMonitor，
  保存不可变整数快照，再以相邻 RisingEdge 的框架 tick 确认；同一输入由唯一 Driver
  所有。此接口没有 ready/valid，按每个流水槽的固定三拍关系核验，不虚构接受信号。
- 独立 PerfModel 的理由传播/覆盖算法保持原语义；比较放在 `checker.py`。正常退出
  再送入三拍加一个空拍的 aging 控制，检查最后一笔与最终清空，不通过停止调用 cycle
  忽略流水尾部。reset 可明确取消当前流水，不假装已经正常完成。
- pytest 根引用的 fixture 拥有 DUT、框架组件和 native coverage 登记；测试只使用
  reset/cycle 的事务 API。原 checker 自检也不再动态装载功能 testcase 来复用编码。

18 个新增框架/合法域控制验证非布尔值、非法/负 reason、未知键、缺端口、不可变性、
第二 writer、停止 monitor 及最后 reason 被隐藏。后者使用真实未改动 DUT，但在观察层
注入错误，不能叫做 RTL mutation 或真实硬件功能 PASS。

定向选择为 28 PASS（原9功能例 + 原1比较器控制 + 新18自检）；由于未选择触发器反例，
报告仍为 INCOMPLETE、ucv 总 exit=1，R-13不移除。
完整 `results/ucv-goal-ifu-perf-integrated-20261101` 为 **162 PASS / 2 FAIL /
1 UNCERTAIN**：原147项逐条判定不变，新18项通过，源码哈希稳定、构建收据未变、产物
manifest committed / coverage_complete=true，R-13缺口照实保留。IFU 引脚表达式从313降至
302；仅该功能文件静态清零，不能声称另外六个 DUT 已适配完成。

本模块检查点的根回归为 **109 PASS**；结构、skill、资产、diff check 均通过，全仓事务
门禁仍如实非零。逐运行和差分哈希见
[本模块机器证据](../history/transaction-goal-perf-analysis-20261101.json)。

## IFU PredChecker（已完成本模块，IFU 总任务仍进行中）

原用例把物理端口编码、组合截断和寄存重定向一起放在 helper 内，通常在推进一拍后才
读取两者，无法作为迁移后撤销整帧的正确采样方式。现迁入 `pred_checker/`，测试仅调用
不可变 Request 的 cycle/reset；驱动独占全部422个非clock输入，严格绑定全部公开输出
的宽度/方向以及三个pruned常量。端口中半字 PC/target 只在 ports 层与语义字节地址转换。

主要修复和检查如下：

- Instr/Request 冻结，输入列表复制为tuple；标志、属性、offset、51位PC与对齐严格校验，
  不再默许超宽PC靠XData截断。旧6组目标算术用例的实际目标加法器输入保持不变，原来
  两个超宽常量显式转成其已实际送达的 GuardedPc，并新增越界拒绝控制。
- 两个 lossless SamplingMonitor 分别在 DriveStable 与下一 RisingEdge 采样；前者检查
  当前35 lane组合截断及上一槽重定向，后者检查当前槽11个重定向字段。精确half-tick
  和本地槽号关联，不虚构ready、硬件UID或“driver返回就代表响应已检查”。独立
  `predict/fault_classes` 两函数 AST 与修改前完全相同，比较复用框架 Scoreboard。
- 首次双阶段实现暴露了 fixture→test 任务切换问题：进入首个正常请求时已到tick9的
  DriveStable，队列里是lane0=0的旧空闲样本，虽然与tick10上升沿相邻，仍不是请求的
  组合结果。`driver.py` 在框架单周期Driver上使用公开 Execution.paused，在调用之间
  暂停仿真时间，绝不停monitor或跳过已有样本；空闲时间由同样受检的显式空槽推进。
  跨12次任务让出、并发拒绝、旧tick注入分别验证该问题不会静默回归。
- 原pruned证明中 `... or True` 的无效断言改为真正逐split检查lane34为0；通过合法
  IFU窗口的lane33跨块JAL重定向核验邻接非零对照。lane34非零/隐藏lane35 payload则在
  事务边界拒绝，不能因无端口而忽略。
- 正常finish检查两个空槽的清空/无重复；reset后新请求不带旧valid；失败或取消的槽
  保持未对账，不能吞掉取消异常后仍报成功。关闭任一monitor、隐藏最后重定向、旧响应
  冒充新响应及错误组合截断均在指定检查点被拒绝。
- 同时发现IFU加载器默认native seed固定为1，没有传递ucv记录的UCV_SEED。改用公共
  `ucv.runtime.native_seed`，保留显式override和rand+reset+0；三个根测试核对构造参数。
  修前名字含seed2的定向运行不能当作原生seed2，本轮另外保存了修后真实seed2的回归。

新增 **3个正常原生功能用例 + 49个框架/合法域自检**；自检包含有效重定向所有payload
字段的区分性翻转，不叫作RTL mutation。最终完整
`results/ucv-goal-ifu-pred-final-20261101` 为 **214 PASS / 2 FAIL / 1 UNCERTAIN**，
原165项逐条判定不变，新增52项通过；与初始147项对照同样不变。修后native seed2、
单worker的最终定向为 **67 PASS**。所有完整/最终定向的源码前后哈希稳定、当前源码
匹配，native构建收据未变，manifest committed / coverage_complete=true；R-13继续保留。
较早15 ERROR、15 FAIL、3个自检注入错误等探针也单列保留，不能改写为最终PASS。

根回归 **113 PASS**；结构、skill、资产、pip check和diff check通过。IFU引脚表达式由
302降至276，另外五DUT仍待适配；全仓严格事务门禁继续如实exit1。最新十工程collection
为 **45953个有序nodeid**，原45883项都保留原顺序，新70项仅来自本目标的Perf与Pred。
本模块与运行差分见
[机器证据](../history/transaction-goal-pred-checker-20261101.json)，具体字段/所有权/阶段与
需求到checker映射见 [IFU事务合同](../../suites/frontend/ifu/docs/transaction-adapters.md)。

最后复核还补齐了 reset 检查失败的粘滞状态：恢复正常 monitor、吞掉 reset 断言也不能
使 finish 报成功，与中断输入槽采用同一未对账规则。上面的最终结果包含该第49个自检；
较早 `pred-verified` 的213 PASS/66 PASS仅对应其当时源码，仍在机器证据中保留。

## IFU RvcExpander（已完成本模块，IFU 总任务仍进行中）

原组合用例的observe/check直接编码和读取物理端口；现以不可变DecodeRequest驱动32位
指令字与布尔FS，严格绑定2输入/2输出，由根fixture登记原生覆盖并管理全部资源。native
XClock只推进评估时间，框架采样事件不冒充硬件时钟或握手。输出经lossless Monitor和
Bundle.sample保存不可变快照、精确同tick关联；组合无流水，finish检查一个定义明确的
NOP评估，再释放组件。失败/取消保留未对账，不能恢复monitor或吞错后重新报成功。

为真正复用，把PredChecker已验证的显式槽调度提取为 `drivers/explicit_slots.py`，只共享
框架单周期Driver和公开Execution.paused机制，不包含任何DUT端口/编码/oracle。完整IFU
再次核验了原PredChecker全部用例，不以代码复用为由撤回原验证。RVC参考模型文件字节
未改；整数、访存、控制、Zcb、reserved/hint编码表不变。原11个功能用例经纯生成器
对账，**28331笔输入及顺序完全相同**，含原**28000次随机比较**；生成器对账不是原生
采样日志，也不当作额外硬件证据。

新增 **2个正常原生功能 + 38个自检**：前者覆盖压缩字后续半字变化、同指令当前FS；
后者覆盖域/不可变/缺端口/错宽方向/所有权、任务让出/并发、旧tick/旧payload/关monitor/
缺快照/错误末尾输出、取消或吞错后不能正常finish。ill总比较；架构允许的hint规范化和
illegal载荷不作无依据约束，正确对照仍须通过；expected override不能通过设置hint来
隐藏本应比较的合法bits。自检注入发生在Python观察/期望层，不叫RTL mutation。

原错误寄存器重映射算法的3组负对照全部保留；初次探针中发现迁移缩进曾让错误期望
只在循环末项比较，已在后续定向/完整回归前修复，初探针不能认证完整控制链。

最终 `results/ucv-goal-ifu-rvc-integrated-20261101` 为 **254 PASS / 2 FAIL /
1 UNCERTAIN**，原217项逐条判定不变，新40项通过；初始147项同样不变。
修后native seed2、单worker的RVC选择为 **53 PASS**；含共享后PredChecker的定向选择
为117 PASS。完整/seed2源码哈希稳定且与当前一致，native构建收据未变，manifest
committed / coverage_complete=true；R-13与原硬件FAIL/UNCERTAIN保留，整体目标未关闭。
根回归 **114 PASS**；结构、Skill、资产、pip/diff检查通过，IFU仍有272个引脚表达式，
全仓严格事务门禁继续exit1。最新十工程collection **45993项**，初始45883项保留原顺序，
新增110项仅来自本目标的三个IFU模块（5个正常功能、105个自检）。

本模块逐运行、生成器差分、需求到产物映射及下一模块诊断见
[机器证据](../history/transaction-goal-rvc-expander-20261101.json)；无时钟DUT事件含义与
比较有效域见[IFU事务合同](../../suites/frontend/ifu/docs/transaction-adapters.md)。

## IFU InstrBoundary（已完成本模块，IFU 总任务仍进行中）

原helper把物理字段编码/读取、settle和全字段比较放在功能测试。审计真实ICache producer
发现map按每个原始半字low2分类，而不是只标真实指令起始；合法0xAAAAAAAA先暴露16个
无效槽endOffset差异。沿consumer继续审计确认compact不选无效槽，carry首槽endOffset
被重写0；据此限定比较域，其他有效字段仍比较，不从DUT valid反推期望掩码。

新`instr_boundary/`复用框架Driver/lossless Monitor/Scoreboard及共享显式槽调度，严格
绑定40输入/257输出，slot31 cross显式验证是pruned0；输入/快照冻结并校验。无硬件时钟
的native评估事件不是接受握手，精确tick/槽关系、唯一所有权、单idle尾部与取消/失败
未对账均有控制。finite batch只累积真正的typed比较错误，不吞时序或传输故障。

同时发现并保留真实新缺陷[R-14](../../suites/frontend/ifu/docs/bugs/instr-boundary-carry-ftq-owner.md)：
旧模型和RTL均缺cross的“真正起始”前提，carry首槽高半字low2=11且块0 size=1时会误用
块1 FTQ。通过真实invalidTaken恢复、合法FTQ块大小/对齐序列复现：高半0x10正常，0x13
指令字/PC/endOffset正确但FTQ错误。原600随机样本及顺序完全不变，全部执行并比较，
其中137/254/406/477/529五个反例令原一条假PASS转为FAIL。该变化是修复漏检，不恢复旧
错误oracle、不删除样本或登记XFAIL。`build_window`改为从raw halfword数据产生map，
独立aligned_lanes/branch_info AST不变。早期未收紧FTQ大小的诊断不能单独证明生产可达。

新增**7个功能用例 + 53个自检**（58 PASS/2 FAIL），包括额外600 raw-map窗口与压缩
坐标sweep。完整 `results/ucv-goal-ifu-boundary-integrated-20261101` 为
**311 PASS / 5 FAIL / 1 UNCERTAIN**，原257项除上述一条PASS→FAIL外均不变；原始147项
同样只有该变化。native seed2单worker选择为**71 PASS / 3 FAIL**；源码前后稳定且匹配，
原生构建收据未变，manifest committed/coverage_complete=true，不等于覆盖闭环。

另修复async fixture无法自然收到pytest正文异常，导致真实call FAIL后再有假teardown
ERROR的问题。`agent_runtime`只桥接已报告非通过；PASS/无报告仍严格finish、独立cleanup
错误仍传播，吞错不变PASS。10个新增根控制通过，四个已适配agent完整回归保持判定。
根**124 PASS**；结构/Skill/资产/pip/diff通过，严格事务门禁继续exit1，IFU仍有252个引脚
表达式。十工程collection **46053项**，原45883项和相对顺序保留，新增170项仅来自四个
IFU模块。逐运行/生成器/模型变更/需求对账见
[本模块机器证据](../history/transaction-goal-instr-boundary-20261101.json)。

## IFU FrontendTrigger（已完成本模块，IFU 总任务仍进行中）

输入配置/PC编码、refresh读取、参考状态和比较均已从功能用例迁入`frontend_trigger/`。
严格冻结Trigger/Update/Inputs，校验完整64位tdata2、50位字节PC及布尔/编码/向量；50个
非clock输入和36输出由ports严格绑定，一个框架Driver拥有全部输入。真实时钟的两个
lossless Monitor分别在DriveStable/同一RisingEdge检查旧/新配置和enable，debug与权限是
当前live门控；精确tick与输入槽号关联、最终配置加disable后双槽检查、reset及失败/
取消未对账均有控制，不虚构ready/UID。

CSR只输出EQ/GE/LT、select0、action0/1，timing固定0，但tdata2是完整64位。producer
入口检查配置及无相邻chain的历史；旧保留编码、select、不支持action和任意链压力走
显式characterize入口，仍比较所有同样字段，不算CSR可达证据。原15个功能体计划的798笔
激励及顺序完全不变，含原180随机；这不是原生采样日志。R-13现在在第一笔更新沿后即
失败，不能把该FAIL之后计划中的第二笔算已执行。

补齐旧模型的真实复位缺口：全零配置action应为0，旧模型用None15。新增PC0启用未更新
配置的合法对照及冻结错误模型，compare/can_fire/lane_actions/tick AST不变；R-13两条
FAIL继续保留。最终源码审计还纠正了初版准入对末槽chain=1的过严拒绝：真实CSR仅禁止
相邻chain，并未强制末位0。新增合法末链控制通过，不靠更保守域隐藏验证范围。

新增**5功能 + 71自检**均通过。最终完整`results/ucv-goal-ifu-trigger-verified-20261101`
为**387 PASS / 5 FAIL / 1 UNCERTAIN**，原317项逐条不变；单worker native seed2选择为
**90 PASS / 2 FAIL**，两个FAIL仍为R-13。源码稳定且匹配，native构建收据未改，manifest
committed/coverage_complete=true。较早未含末槽chain合法修正的386/89结果只归当时源码，
不当最终producer域签核。根**125 PASS**，十工程collection **46129项**，初始45883项
及相对顺序保留；结构/Skill/资产/pip/diff通过，全仓严格事务门禁继续exit1，IFU仍有240
个引脚表达式。最后还同步了旧功能点JSON中“复位未编程一定不开火”的错误措辞，以及
寄存enable/live门控、未命中链伙伴的精确合同；因此另取verified收据，之前final结果保留
其旧JSON哈希，不静默视为仍匹配。该次文字同步没有修改oracle或RTL。全部差分/哈希/需求对账见
[机器证据](../history/transaction-goal-frontend-trigger-20261101.json)。

## IFU IfuUncacheUnit（已完成本模块，IFU 总任务仍进行中）

原用例的apply/observe/expected_dict、refresh/step和shadow计数已迁入`uncache_unit/`。
新增严格冻结的输入/输出、ReadRequest/BusReply与不可变UID/epoch记录，完整绑定15输入/
9输出及显式pruned ready=1；所有输入由唯一框架Driver拥有。当前47线是PrunedAddr的
半字坐标，语义地址实际48位字节；旧常量/随机值显式左移，只有ports编解码时再移位。

两个lossless Monitor分别保存沿前全部通道快照和同一沿后状态，精确tick/输入槽关联。
valid总比较、payload按独立expected valid限定；不使用DUT valid或expected override
隐藏合法载荷，也不把valid0无定义payload当错误。独立UncacheModel类的归一AST未改，
另以实际受检fire/脉冲建立UID账本，避免旧model.accepted计数冒充采样接受。

normal入口只接受MMIO/NC/IO与显式已issue UID的peer回复，校验denied→corrupt及真实
needResend来源；旧reserved PBMT、PMA非MMIO、任意响应组合通过显式characterize保留，
仍受全部schema/驱动/采样/比较检查，不算生产可达。tagless线上没有UID，不能从相同
数据反推身份；已issue取消UID在新请求未WaitResp时可作关联迟到控制，新WaitResp时的
歧义旧回复在准入拒绝，实际过滤依赖外部InstrUncache flush，不冒称DUT有硬件tag。

真实事件分开offered、req_fire、生效accepted、flush-on-fire、issued、completed、
cancelled和active。reset提升epoch但不清历史；场景显式取消/复位必须有可追踪原因。
read有预算且只在实际issue后用调用方明确提供的数据回复；finish检查空槽/无重复，
有在途请求则失败，不能自动回复/flush/reset来清债。72个自检验证错字段/错UID、同值
不同历史、缺端口/错宽方向、writer冲突、零接受、三个阶段欠债、丢完成/重复尾部、
关闭monitor/旧tick/旧payload、任务切换/并发、reset/取消/吞错；注入不是RTL mutation。

新增**19个功能 + 72个自检**全部通过。原11个功能体**767笔主激励**及物理端口值/
顺序经纯生成器对账不变（不是原生采样日志），包括原700帧全部执行。真实受管700帧
记录94 fire、89生效、75完成、13取消、5同拍flush，最后一笔Send由场景明确取消；
账本恒等式与端口压力/合法完整历史都被检查，未删除随机反例或静默停止采样。

最终`results/ucv-goal-ifu-uncache-integrated-20261101`为**478 PASS/5 FAIL/1 UNCERTAIN**，
原393项逐条不变，新增91项通过；native seed2单worker选择**104 PASS**。源码稳定且逐
文件匹配，七DUT实际native文件/build_id与前一完整manifest一致，build.json哈希也逐项
匹配最初inventory，未重建RTL/native。manifest committed/coverage_complete=true只证明
产物完整，不等于功能/覆盖闭环。R-13/R-14和carry UNCERTAIN继续保留。

根**126 PASS**；十工程collection **46220项**，初始45883项/相对顺序保留；结构/Skill/
资产/pip/diff通过，严格事务门禁仍exit1，IFU仍有217个引脚表达式。当前合同已同步到
verification_plan.json、功能点表和观察/账本对账；详见
[本模块机器证据](../history/transaction-goal-uncache-unit-20261101.json)及
[事务合同](../../suites/frontend/ifu/docs/transaction-adapters.md#ifuuncacheunit-请求回复完成合同)。

## PerfAnalysis生命周期复核（已修复新证实缺口）

交叉复核时以真实原生DUT/Python观察注入新增两项控制，`perf-revisit-red`为1 FAIL/1 PASS：
调用方捕获比较断言、恢复monitor后，旧finish正常成功，未保留未对账；跨任务让出合法
对照原本通过，未误报为时序缺陷。依据该具体证据重新打开生命周期义务，而非推翻已有
独立oracle/原功能工作。

补齐Frame/port严格宽度方向/完整输入集、Scoreboard整数快照、共享显式槽Driver、
精确相邻tick、整个cycle/reset/finish粘滞失败/取消与并发保护、一次finish/禁止重启。
原三阶段+空槽尾部、独立PerfModel与原功能测试字节均保持；新增15自检包括原red反例、
吞掉reset失败、取消、旧tick、并发reset、Frame/端口/快照域和严格生命周期。

最新完整`results/ucv-goal-ifu-perf-revisit-integrated-20261101`为
**493 PASS/5 FAIL/1 UNCERTAIN**，原484项逐条不变，新15项通过；native seed2定向
**43 PASS**。源码前后稳定且逐文件匹配，实际7native文件/build_id/最初build收据均未改，
manifest committed/coverage_complete=true。根126 PASS，十工程collection **46235项**，
初始45883及相对顺序保留；结构/Skill/资产/pip/diff通过，事务门禁仍exit1、IFU217引脚
表达式。R-13/R-14和carry UNCERTAIN保留，整体目标继续执行。复核依据/差分/需求对账见
[机器证据](../history/transaction-goal-perf-revisit-20261101.json)。

## 下一未完成工作

继续 IFU 剩余Ifu顶层的多通道事务/身份/完成适配，再依整体计划复核/修复
BPU、FTQ、ICache、DCache、LSQ、LSU、MMU、Sbuffer、VAGQ；所有待审/待修义务保持在
计划中。BPU DefaultConfig 旧场景映射、原生全生产运行与 VAGQ 穷举边界不能用静态门禁
或代表性选择代替。既有未提交修改与所有受管结果保留，本目标尚未完成。

InstrBoundary已完成本模块适配，但R-14仍为真实开放硬件缺陷，不能以此宣称IFU硬件通过。

### Ifu顶层前置审计（尚未实施）

已冻结最新499项IFU收据与顶层49个功能体/52个实际nodeid；真实接口含80个非clock输入、
405输出。现有217个功能引脚表达式仍集中在旧顶层调用链，不能只搬helper或加raw转发
外壳来声称迁移完成。见[顶层审计记录](../history/transaction-goal-ifu-top-review-20261101.json)。

实际成对诊断还确认一处漏检：未改RTL只发出一拍beat，但Python观察层注入三拍
valid/ready机会时，旧fetch在拿到首beat后不再读取valid，最后仍PASS；无注入的正常对照
也PASS。这是checker/runtime缺口，不是新RTL缺陷或额外硬件功能PASS，完整诊断保留在
results/ucv-goal-ifu-top-review-20261101/duplicate-valid-diagnostic.json。迁移需持续采全通道，
held-valid/backpressure与真实重复fire区分，不能靠“第一个结果正确”忽略末尾事件。

其他必须处理项：top ready在s0_flush时仍高，但有效进入pipeline的s0_fire被flush阻断；
需要分开物理fire和取消的生效。旧paddr0同样是47位raw坐标，语义应48位字节；虚拟PC/
GPA分别51/56位字节，redirect.pc50位限制仍单列R-08。旧cross-page resend样本中存在
非真实页末地址的端口压力，必须保留并分类，另补真实peer序列。GPA写wen不由IBuffer.ready
门控，合法重复幂等写不能错算成重复beat。carry可跨fetch存续，但整个场景须完成或明确
取消，不能机械要求每个fetch末尾都无carry。当时仅审计/冻结，没有实施顶层agent；
后续缓存链的实施证据见下方检查点，uncache组合仍未完成。

### IfuUncacheUnit前置审计（实施前历史快照）

以下保留实施前审计边界；本模块现已按上节实现验证，不能把这份旧审计当作仍未实施。
当时冻结393项完整IFU及Uncache源码，复用trigger-verified收据，不重跑旧基线。
[审计机器记录](../history/transaction-goal-uncache-review-20261101.json)保留真实producer/
consumer指纹与原700帧纯生成器统计（不是原生采样日志/新硬件结论）：

- 当前47根paddr_addr线是PrunedAddr去掉bit0后的半字坐标，语义物理地址实际48位字节。
  旧测试/模型把raw坐标直接叫address；迁移须显式转换并保留原始端口输入，不能丢最高位
  或把原raw奇数样本当成非法字节地址删掉。
- 正常IFU只将MMIO/NC/IO且无异常的请求送入；旧PMA非MMIO、reserved PBMT及任意响应
  元数据不能都称真实生产可达。InstrUncache的needResend只在干净、非RVC、跨页高半缺失
  时产生。旧端口压力要全部保留并显式分类，另补合法完整历史。
- ready不被flush门控。纯生成器/旧shadow分析有94个ready-valid事件，但旧accepted计数89，
  差值是5个同拍flush重叠；必须拆分物理fire与被取消的生效请求，不能拿shadow计数冒充
  原生接受。末尾是Send、仍有一笔在途，fixture Finish当前未对账。
- 需落实逐UID/epoch、实际bus issue、响应/完成脉冲与flush/reset取消账本；tagless响应的
  身份依赖外部InstrUncache历史和flush过滤，不能虚构硬件标签，也不能把所有非WaitResp
  响应（包括可能合法的取消后迟到）一概当非法。
- 比较掩码须来自独立expected valid，pruned fromUncache.ready为显式常量1；沿前握手、
  沿后脉冲、连续采样和有界收尾当时仍待实现，审计时未修改Uncache模型/功能测试/原生构建。

## Ifu顶层缓存链（已实施的中间检查点，顶层未完成）

原`test_ifu_fetch.py`的49个功能体中，40个缓存体（41个参数变体）现实际使用
`ifu_agent`，另迁移缓存guard、pruned及比较器控制。`ifu/{types,ports,checker,agent}.py`
严格绑定80非clock输入/405输出，冻结嵌套窗口/指令与全部通道快照；复用共享显式槽Driver、
持续lossless DriveStable/RisingEdge Monitor及Scoreboard。UID在输入建立，物理fire、
同拍flush取消、有效进入、stage1/stage2/writeback、held offer、enqueue fire和redirect
分别对账。GPA `wen`按valid允许背压期间合法幂等重复写，不能错计成重复入队。

新的实际`fetch`调用链不会在首结果后短路：沿前/沿后重复beat、隐藏必须beat、重复
redirect、旧tick/错误payload和错误expected注入都在承诺检查点拒绝，正常控制通过。
新增4个真实功能历史覆盖双窗口重叠、held GPA、多阶段/同拍flush和redirect保留自身
held beat；新增72个自检覆盖严格schema/端口/ownership、两monitor、任务切换/并发、
零接受/watchdog、carry身份、完成/显式取消/reset及吞错后的粘滞未对账。这些Python注入
不是RTL mutation，不能算额外硬件功能通过。

还发现旧顶层FTQ flag2/3的真实准入缺口：逻辑1位的native scalar元数据为0，旧包装竟
能读回2/3且旧checker通过。新入口拒绝非法编码；6个旧功能体、34个计划窗口明确改为
低位0/1，不冒称该部分原物理输入保持。纯生成器工具对账40体/41变体/373窗口，除上述
flag及其指令身份归一外，其余字段、数据和顺序一致，三个纯生成helper AST不变；四个
手工时序体只比较首个已构造窗口，不把该工具叫作真实native trace。`build_window`、
`aligned_lanes`、`branch_info`算法AST不变。新checker明确invalidTaken半字的独立有效域、
folded虚拟PC不包含guard，以及`prevInstrCount`的下一槽容量预告语义，未改oracle迎合RTL。

最新完整`results/ucv-goal-ifu-top-cached-integrated-20261101`为
**569 PASS / 5 FAIL / 1 UNCERTAIN**：原499项逐条不变，新增76项通过。真实native seed2
单worker顶层定向为**128 PASS / 1 FAIL / 1 UNCERTAIN**，唯一FAIL仍为R-14。两个运行
源码前后稳定且与当前逐文件匹配；七DUT的build收据、manifest build_id及42个实际native
输入文件与前检查点一致，未重建RTL/native。manifest committed/coverage_complete=true
只代表产物完整，不是功能/覆盖闭环。

十工程收集现**46311项**，初始45883及此前46235项的顺序均保留，十个collection任务
exit0；根126 PASS，结构/Skill/资产/pip/diff检查通过。严格事务门禁继续exit1，IFU
仍有184个引脚表达式，源码无散落仿真产物。9个uncache功能体及其guard仍实际用旧helper，
必须继续迁移raw PA、issue/reply UID、peer resend/carry、取消与收尾，并完成真实FTQ
可达域/端口压力分类。不能用cached入口拒绝uncache来宣布顶层无缺口，也不以静态计数
降低代替最终语义验收；其他所有工程与最终全仓任务继续保留。

详细需求—产物—正反对照映射、运行哈希和剩余义务见
[本检查点机器记录](../history/transaction-goal-ifu-top-cached-20261101.json)及
[顶层合同](../../suites/frontend/ifu/docs/transaction-adapters.md#ifu顶层缓存链已实施整体尚未签核)。

## Ifu顶层uncache组合与生产者证据纠正（当前检查点）

此前缓存阶段列出的9个uncache功能体和uncached guard现已接入同一`ifu_agent`，没有
复制新的引脚转发层。全部49个旧取指体与两个guard保留原nodeid；移除旧raw fixture和
`apply_window/read_beat/read_redirect/fetch/uncache_collect`等helper后，IFU功能文件
引脚、信号与原生访问静态命中均为0。但顶层总语义审计尚未结束，不据此关闭`ifu-adapters`。

uncache使用输入建立的UID：物理fetch fire、生效/同拍取消、child接受、实际bus issue、
显式peer reply、一次入队/redirect和resend分开。两phase lossless采样服务全部通道，
未拿到首结果就停止；正常peer遵守clean/full-width/page-final的needResend规则，旧
0xC000/rawPA0x4000 fake resend仍通过显式`characterize_reply`驱动并严格检查，绝不
晋升生产credit。raw PA只显式转成字节，原9体的计划序列对账为53请求（含缓存前史）/
18回复，数据、其他metadata及顺序一致；此工具是纯生成器，不是native pin/timing trace。

新增13个uncache功能参数用例覆盖五种内存类型、最高字节地址、异常优先级、真实页末
重发到不连续物理页、背压、真实前史的非幂等排空、取消/迟到/新代际和cached→uncached
carry；另有6个严格producer功能对照。49个新增自检验证未知/提前/重复/错代UID、同值
不同历史、两phase漏采/重复/错载荷、错误ISA expected、无issue/无reply watchdog、
三个欠债阶段、未完成resend、reset和吞错粘滞，以及producer准入/来源继承。所有这些
新用例通过；Python注入只证明检查链，不叫RTL mutation或新增硬件功能信用。

### 纠正R-14的过强生产可达结论，保留原FAIL

新增源码证据：`Bpu.scala`无taken时选择`FallThroughPredictor`，后者要求窗口完整取到
`min(align32(start)+64,nextPage)`；只检查size上界不够。旧R-14的首请求第二块和恢复
请求第一块均是任意短non-taken块，因此先前“真实FTQ size受约束、已证明生产可达”的
表述不充分。本节与当前缺陷文档**纠正该结论，不改写旧运行或删除反例**。

实际native诊断把first改为sizes1/17 taken1/0、resume改为1/3 taken1/1后，高半字0x10
和0x13均使用正确FTQ(0,32)，恢复时出现正确notCfiTaken redirect。正式producer agent
上的两个等价对照也通过。原leaf、600随机批次和顶层端口场景中的R-14三条FAIL继续保留，
但目前只证明端口合同域偏差，不能自动叫作已复现的生产缺陷。

此次合法历史还暴露了独立模型的另一个缺口：carry硬编码pred_taken0/NONE，遗漏完成
槽的预测和完整指令的ISA类别。`build_window`已按完整保存字解码，并在块0只有carry且
taken时归属该预测；冻结旧missing-prediction答案在相同真实snapshot上被拒绝，合法
对照通过。`build_window`的AST因此确实改变，不能继续沿用上个检查点“未改”的说法；
`aligned_lanes`、`branch_info`算法仍未改，原575项判定逐条保持。

`ProducerFetchRequest`额外检查真实DefaultConfig的extent/页末、双fetch同页/后继FTQ、
flag回绕、backend/satp限制、PBMT与PA页内偏移，仍允许合法false prediction。
`FetchRequest`明确为严格端口域，不隐含producer证明；输入和peer来源分别沿carry传播，
不能通过换成producer类型把旧端口低半或fake resend晋升。该准入不是整合BPU训练、
PNR、翻译或提交历史的整机验证，所有权/采样/oracle检查对两种来源相同。

### 最终源码收据与剩余必需工作

`results/ucv-goal-ifu-top-uncache-integrated-20261101`为
**637 PASS / 5 FAIL / 1 UNCERTAIN**；原575项逐条不变，新68项（19功能/49自检）均PASS。
真实native seed2单worker顶层定向为**196 PASS / 1 FAIL / 1 UNCERTAIN**。源码前后稳定
且与当前逐文件匹配；七DUT缓存build.json、manifest build_id及42个实际native输入文件
与前检查点匹配，未重建RTL/native。manifest committed/coverage_complete仅代表产物
完整，不能替代功能或覆盖闭环。

十工程collection为**46379项**，原45883和前46311的有序nodeid均保留，十个collection
任务exit0；根126 PASS，Skill与资产检查通过。严格全仓事务门禁继续exit1（其他五工程
仍有真实泄漏），不是本工程静态0就全仓通过。

下一必需项是顶层最终语义审计，包括输入中派生的instruction metadata与实际驱动raw
字节的一致性，不能只信builder恰好提供正确值。13个performance输出仅严格绑定/冻结
采样，不给未比较的逐事件功能credit。其他前端、MemBlock/VAGQ及最终全仓门禁/回归/
当前包/资产与文档验收均继续保留。详细需求映射、源码/运行哈希和差分见
[本检查点机器记录](../history/transaction-goal-ifu-top-uncache-20261101.json)；
[R-14当前范围](../../suites/frontend/ifu/docs/bugs/instr-boundary-carry-ftq-owner.md)明确区分
实际native端口复现与生产可达证据，活动目标不关闭。

## IFU顶层最终语义审计补充（当前检查点）

恢复后没有重跑已稳定的缓存/uncache基线；先核对当前源码与前检查点，再执行新控制。
`FetchRequest`此前只检查派生字段的各自宽度，未验证它们与实际驱动半字流一致：同一
raw数据可以伪造word、PC、slot、FTQ、预测、ISA分类、截断和计数。这是环境准入缺口，
不是RTL判定。新增`ifu/input_contract.py`从line/offset/size原始半字独立步进，拒绝
不一致描述；carry仍由agent按前一实际UID/低半/PC校验。1200个随机窗口、手写byte
stream、19字段/4计数/序列错误对照及实际agent零驱动控制通过。

同时核对公开`Ifu.scala:773-788`、`ICachePerfInfo`和`HardwarePerfMonitor.scala:27-38`：
13个`perfEvents`是布尔分类，经两个`RegNext`公开，不是累计计数。此前agent只把13个
输出采样进snapshot，未给功能比较credit。新增独立`fetch_events.py`真值表和事件管道，
按接受UID保存hits/double-line，按IBuffer fire计数，在DriveStable/RisingEdge各比较全部
13字段。8种hit/double组合在held beat期间切换live元数据仍保持旧UID答案；每字段两阶段
26个错误注入均被真实链路拒绝，redirect/尾部和一拍finish控制也通过。

追加同拍bus fire+backend cancel、reply+cancel、uncache完成取消年轻stage/offer、FTQ
producer半环年龄、carry reset/cancel原因等生命周期对照。完整IFU结果从643项的
637/5/1变为725项的719/5/1，无旧nodeid删除或判定变化，新82项全部PASS；seed2选择
结果278/1/1，唯一FAIL仍R-14。源文件哈希为
`47242ca8fa03b360e5639d70016bc5034f4bc97ca268930ffca29fc47cfdc281`且两次运行逐文件
匹配。旧R-13/R-14 FAIL、R-09 UNCERTAIN保留；本检查点不声称RTL/Native重建或功能
覆盖闭环，完整证据见[IFU semantic history](../history/transaction-goal-ifu-top-semantic-20261101.json)。

IFU适配任务据此移交完成，下一阶段审计BPU/FTQ/ICache；整体目标继续active。

## 前端迁移复核：DCE不是可写常量输入

FTQ当前选测108 PASS/2 XFAIL，ICache生命周期选测44 PASS/1 XFAIL；它们不是完整逐DUT
语义签核。BPU完整DefaultConfig导出确实没有prediction target、perfMeta和metadata ready。
初版修复删除强绑定后，却为让旧绑定自检通过，引入可写`InputConstantLeaf`并虚构
`IsInIO()`。这仍是错误的物理所有权：已删除的input不能声称被driver实际驱动。

后续把metadata常量仅保留在valid-only协议适配器，移出control driver payload；逐项核验
真实公开投影的字段/位宽/方向。decoder也不能用`hasattr`把漏采字段重新解释为DCE，是否
存在必须由已审计绑定决定。无retirement PC的`redirect_and_settle`还须在发redirect前拒绝。
五条修复前反例FAIL，修后38项受管检查PASS（含原生绑定/控制/解码），不修改RTL/native。

这只修好观察边界，不能签核仍依赖旧perf/target的PHR/组合场景；当前继续迁移真实身份链。
旧短表场景在独立DefaultConfig模型里先得到table1，不能把“original short必须table0”的
断言放松成任意provider来取绿。合法初始化/历史构造与MBTB四路写回仍是必需适配工作。
参数常量自检和公开schema检查也不等于内部八张表都已验证；README已纠正该过强描述。
当前证据与未完成义务见[前端复核记录](../history/transaction-goal-frontend-review-20261101.json)。

继续实际PHR选测得到42 PASS/1 FAIL，首错是旧monitor强绑已裁掉的pointer flag；当前schema
只有`phrPtr_value`，native trace为532个cell/33个fold。不能从golden补回flag，或把尚未迁移
的perf echo/target关联说成只读诊断已经通过。该FAIL保留为迁移缺口，不登记新RTL缺陷。
此时完整收集46495项，十任务exit0，原45883和上一46379项无删除、相对顺序保持；整体
CLI因原R-13/R-14残余仍exit1。根126 PASS，Skill/framework、资产、diff和57个当前链接
核验通过；全仓事务门禁仍因DCache/LSQ/LSU/MMU/VAGQ真实待办exit1，目标不关闭。

## PHR物理投影、训练几何和真实seed转发（后续检查点）

PHR当前适配范围已验证：同一源码的原生seed1/seed2各**16 PASS**（10个原功能参数、
2个handoff及4个真实native框架控制），纯合同/编码/反馈检查**2128 PASS**。独立fold、
path hash、physical read、logical bypass和advance算法的归一AST相对HEAD未改；reset/
subtract显式选择value-only物理合同，旧flag纯算术仍单列。UID在PHR输入fire建立，沿
S2/S3 fire与flush推进，同PC/同payload也不合并；完成与取消保存精确终态UID，收尾禁止
用关闭monitor、reset或补回复清债。当前环532cell/33fold×4，覆盖lap是输入程序圈次而非
硬件flag。内部PHR输入target不能冒充已裁公开BPU target或完整预测选择oracle。

value-only首轮原生10 FAIL又揭露了输出/输入metadata不对称：公开RAS的`topRetAddr_addr`
不在恢复输入，现只投影这一已核验字段，不过滤未知键。投影后的8 FAIL则定位训练PC
副本实际为`(1,1,2)`，不是旧`(2,2,2)`；必须保留MainBTB的第三副本真实后继，不能把
整个输入截成一格。全部784对齐域及错误几何/指针拒绝控制通过，原十个PHR功能参数均通过。
中途两个框架自检FAIL属于误写冻结tuple和误把reset调用前全部pending当作取消，已按
真实复位沿前可能正常完成的双终态义务修正；没有把这些失败登记为RTL缺陷。

另外原生构造器反证5 FAIL/1 PASS确认FTQ未传seed、ICache固定seed1。现两者逐次解析
`ucv.runtime.native_seed()`；根132 PASS，FTQ完整真实seed2为**109 PASS/2 XFAIL**，
ICache相同生命周期选择为**44 PASS/1 XFAIL**，旧所选判定无变化。历史CLI seed2字样
不自动升级为原生双seed证据；MemBlock同类入口缺口已加入各自未完成任务，Sbuffer旧
两轮66 PASS的功能判定保留，但其native双seed结论仍待实际参数复核/修复。

最新十工程收集**47592项**，初始45883及前46495有序nodeid全部保留，新增1097均为BPU
控制；十collection任务exit0，IFU残余导致的CLI exit1不当收集失败。BPU既有128份RTL
输入、5份native输出重算哈希一致，没有重建。PHR收据在移交时逐文件匹配，后续自主
pipeline源码变化不能静默重标这份旧哈希；见[PHR机器证据](../history/transaction-goal-phr-adapter-20261101.json)
和[当前收集对账](../history/transaction-goal-collect-phr-current-20261101.json)。

整体仍active：自主pipeline的6项原生红基线先失败于另一路已DCE flag；原始短/长来源
与positive保护程序为227 PASS/74 FAIL，仍需合法初始化、真实consumer与收尾适配。
一个独立程序探针用Main-only稳定历史、逐笔排空及显式恢复分隔bubble/有效查询，在
PC0/1/2都得到table0 counter3→0且未分配table1；这只是可行性，不是已落地/DUT验收。
不能放宽原table0/1身份断言或用已完成PHR代替自主BPU、MBTB及全仓剩余工作。

## 自主流水与原短表程序（继续中的检查点）

已把另一路自主pipeline接到当前真实ABI：20组lookup fold、Main四way+victim（victim
属性确实DCE）、Micro训练4fold和DCE的baseStrong。S2属性从真实CommonHR/MicroRAS
消费者取actual，不误绑S2保存的旧S1 prediction。完整自主模型仍从reset/环境事件维护
选择、target、历史及所有表状态；内部target持续比较，公开缺失的target/perf/flag不合成。
外部训练在DriveStable冻结完整beat，在下一rising关联原owner，不能按沿后valid清理
误算接受。所有恢复和反馈先登记精确发布来源，有界窗口复用现有Driver/AdmissionWindow。

`pipeline-entry-integrated`的native分区**25 PASS**：原PHR10、entry保护4、自主流水2及
9个handoff/真实native框架控制。这不是25个硬件功能点，更不是BPU-INT-066的全部义务
已经关闭。投影和15个旧flag重定向自检迁移后，相关纯检查**336 PASS**；生产入口仍拒绝
假flag，纯抽象flag算术域单列，不以兼容分支偷偷放宽硬件驱动。

原entry的26个纯FAIL已由合法短表初始化修复，109项纯检查及4个真实参数全部通过；旧
连续初始化作为冻结错误程序仍被未改的table0断言拒绝。顺序等完redirect清理后再开ready
会改变原read ancestor，native首轮不通过；复用RecoveryDriver并发启动，并按实际S1
接受future立即关年轻输入后通过。不是改provider身份、改RTL或缩短学习来取绿。

继续short-revisit时发现两项旧程序/检查前提：错误NT0原件必须同时拥有其罚减及T4长分配，
不能等到S3才选到一个更年轻的同key原件；5/9配置下旧长suffix又抹掉了要保留的older
区别。根据输入hash首个差异bit4/shift2重新构造，保留NT1/T4、long priority和所有原
counter/身份错误控制。另外S0索引读祖先与当前S1/tag checkpoint不是同一个对象；新
检查从预声明path endpoint和精确redirect owner独立计算索引及5/9性质，不按actual数据
猜来源，也不把当前tag checkpoint的数值别名算成不同读历史。

修后原159个short纯控制与109个entry均通过；再加12个读祖先合法/错误控制后short为
**171 PASS**。但四个真实short参数**仍FAIL**，卡在named wrong原件的接受window，
不能据纯程序通过关闭迁移或叫新RTL缺陷。正在核验NT0前置和第一批/尾部真实比较候选，
后续positive保护6项、MBTB及其他工程任务完整保留。

四个MemBlock工程也已补真正seed2完整回归：Sbuffer66 PASS、DCache229 PASS/3 XFAIL、
MMU417 PASS、LSU536 PASS/7 FAIL，逐nodeid均与各自旧验收集合完全相同。根215 PASS，
83个全入口seed控制修前全FAIL、修后全PASS；legacy直接工具的seed provenance仍需同步。
新完整收集**47627项**，初始45883及前47592有序nodeid保留，十任务exit0；IFU残余导致
的CLI exit1保持。没有修改RTL/native、提交或推送。详见
[pipeline机器记录](../history/transaction-goal-pipeline-entry-20261101.json)、
[seed机器记录](../history/transaction-goal-memblock-native-seed-20261101.json)与
[收集对账](../history/transaction-goal-collect-pipeline-entry-20261101.json)。

## 后续实测：有界短表原件与seed收据（2026-11-02）

继续审计时，单把初始化由两轮延长到完整NT0仍不足以修复四个真实short超时。
有界分配日志证明长表提前分配来自返回opposition的owner133，而不是错误窗口中待选的
原件。原生driver在S3搜索返回时还会接受年轻输入；将返回opposition也按每笔接受/学习
完整排空后，第一笔reward只改变一次Ahead，不能继续假设它已自动饱和到NT0。因此又
显式用合法新原件建立所需NT base，才禁用早级学习、正常resolve将Main转向T。

`results/ucv-goal-bpu-short-nt-base-v5-20261101`（路径标签沿用启动时日期）的实际结果为
**316 PASS/4 FAIL**：原entry四参数、short-revisit四参数、short171、entry109及positive
28个纯检查通过；仅四个positive原生参数FAIL，且没有新的自主RTL比较偏差。short原
table0 NT0错误→NT1、同一原件分配table1 T4、long优先和独立新路径上的short再消费
全部保留，未按来源数据/当前PC猜UID。源码稳定，收据仍归其实际哈希；后续共享helper
修改不自动重标这份结果为最新源码。

positive六个纯失败的旧单fallback路径读到了已保护的长row352；根据输入hash的独立
5/9性质改为160/96两种读祖先，并保留旧合法程序“不能称已分配新长”的错误信用对照。
四个实际positive参数则在arm_seed处发现短T4已被准备流中的年轻NT输入降强，不满足
原T4/protection1种子。正复用原有Driver/AdmissionWindow的逐笔原件机制约束该准备
阶段，不放宽种子强度或改成从actual选择任意命中。

另一个独立缺口已闭合：DCache/LSU/MMU直接运行工具实际使用`UCV_SEED=7`时，仍会把
legacy环境19写进收据。新resolver与native argv共用，启动前冻结/校验并显式传给
子进程，运行后环境变化也不能改写seed身份。12项修前writer控制失败，修后15项writer
和83项loader控制全部通过，根**230 PASS**；当前原生seed2选测DCache13、StoreDelay14、
PTWRepeater7均PASS且判定保持。之前的四工程完整回归保留原哈希，没有无依据重跑或
静默改标。细节见[seed收据机器记录](../history/transaction-goal-memblock-seed-provenance-20261101.json)。

FTQ逐DUT继续复核又证实CallRet此前无合法域校验，bool/float及越界会被原生整数驱动
接受，duck-typed payload也绕过事务。已补严格6-bit pointer/2-bit完整RAS action域及
编码前拒绝（包括不允许先改变oracle），合法全域256对照保留。持续采样和完成性仍待
迁移：当前`Dut.edge(cycles)`返回时才调用一次`EdgeMonitor.observe`，aclose会清空
记录；这不是每拍lossless观察或接受/完成账本，已有绿色不能代替该义务。

## CommitQueue 实际迁移与两类漏检（2026-11-02）

先前“FTQ三DUT静态零泄漏、完整绿色”不够。新的真实native控制在四笔call/ret之后
连续等六拍，旧观察只保留40，漏掉41/42/43；把sample_fn改成始终无输出，旧step也不
报错。修前两条FAIL分别证实丢中间事件和根本没有逐拍比较，不是setup偶然失败。

CommitQueue已单独迁到SDK SyncSingleCycleDriver、DriveStable/RisingEdge两个lossless
SamplingMonitor与Scoreboard。复用已在IFU证实的显式输入槽原则：暂停槽间仿真时间，
monitor始终订阅；不是停止monitor躲开任务切换。严格绑定25个非clock输入/3输出及
clock，输入slot与实际沿前payload/tick对账；环境(epoch,slot,lane)UID按输入建立。
线路没有tag，重复payload仍分别接受/消费。沿后队头仅是预览，下一沿才完成；NONE
过滤和沿前guard容量拒绝都不是“接受后丢失”。有界finish只发idle、等待自主消费和
两个空尾槽；不补call/ret、flush/reset清债。

迁移初版另有一条FAIL是**错误的同步reset假设**：完整导出RTL实际为
`always @(posedge clock or posedge reset)`，因此reset后的第一DriveStable就应全空。
按真实异步reset合同修正，原受检UID作为reset取消，不误计正常完成；取消tick只表示
首次受检reset边界。之后的公开checker吞错控制又证实旧裸assert能绕开agent._failed，
现将公开checker也接入同一Scoreboard并在finish/receipt检查粘滞失败，修前1FAIL保留。

最终同源码完整FTQ为**210 PASS/2 XFAIL**，原168项nodeid和判定保持、新44自检通过；
seed1单worker定向**53 PASS**、根**240 PASS**。两seed原生输入/构建/覆盖产物哈希均已
核验，合并覆盖可用但原始输入不保留；这些Python观察/expected控制不是RTL mutation
coverage，构建/功能/覆盖闭环不混称。原八个CommitQueue功能体、240轮随机及lane×slot
矩阵不缩短。正文已FAIL/skip不通过normal finish虚增teardown ERROR，但正文PASS/缺报告
必须严格finish，独立cleanup异常仍传播，10个新增根控制验证此策略。

详见[CommitQueue机器证据](../history/transaction-goal-ftq-commit-transactions-20261102.json)。
此模块完成不能关闭整个FTQ或前端；ResolveQueue/Ftq顶层仍需真实多通道采样及输入身份、
取消/重试/收尾迁移，BPU其他调用链、MBTB、ICache、MemBlock及VAGQ均保持必需范围。

后续对ResolveQueue/Ftq的三个修前控制也全部FAIL：ready连续消费时中间两个队头完全
没有记录，prefetch/fetch同拍多周期也漏中间请求，Topdown历史中的嵌套reasons字典还可
被调用方修改。现改由共享harness的DriveStable/RisingEdge两个框架lossless monitor
冻结全通道，再统一交付decoder view；输入槽间只暂停时间、不关闭订阅。phase event、
完整通道、150拍分批交付、任务切换、早关/删除observer、replay和取消控制均已通过。
完整FTQ为**228 PASS/2 XFAIL**，之前212项判定保持，新18项自检；根**242 PASS**。
一轮因旧`monitors/__init__.py`还导出已删除Monitor名称而发生的collection ERROR保留，
已同步真实导出名，不误算硬件FAIL。此批只完成持续观察链；两DUT仍需driver、完整
schema、协议UID及有界事务收尾，不能用逐拍帧数取代checked/完成事务信用。

随后ResolveQueue按原RQ-001..011功能合同完成当前事务迁移：47个非clock输入/60输出
和clock的独立ABI，SDK整槽Driver，完整同时来源/控制的严格事务，真实DriveStable输入
计划对账，branch实际valid-mask及双阶段payload比较，独立FIFO/合并/取消和逐report
UID终态。返回identity只作比较，原owner由输入建立；同payload、pointer flag变化及
取消后相同value重建都有独立UID。后端过滤、全局guard拒绝和branch超量拒绝不冒充
接受后完成，IFU“不受后端语义过滤”也不被错误外推为无限容量。

在新oracle评审时还显式固定原RQ-001/003的first-owner startPc，不让后续报告的PC
改名；该纯错误producer对照不声称真实程序会为同FTQ身份改变PC。独立半字对齐答案
`15+16=31`拒绝旧raw offset答案。完整branch valid-mask防止压缩后数目/顺序相同却
物理槽已错的漏检；公开旧参考checker也接SDK Scoreboard，吞错后reset/finish不能
把失败状态洗掉。正常ready消费、同entry合并抑制、不同entry新分配、redirect同拍
完成/取消分别对账，不由一个if分支串行漏掉另一通道。

原七个用例停在accepted+ready0；没有在finish里暗升ready，而只在这些正文全部原
断言之后追加显式`drain_all`消费者计划。git-show/AST证明原功能主体除该尾部调用外
一致，其余报告流、随机180轮、512组slot/来源及XFAIL反例没有删减。最终源码完整
FTQ为**285 PASS/2 XFAIL**，之前230项判定保持、新57项自检；同源码seed1定向
**105 PASS/2 XFAIL**，根**242 PASS**，全仓collection**47805**、初始45883与前47748
无删除/顺序保持。十个collection任务exit0，full CLI1仍为IFU残余而非收集失败。

额外用`--runxfail`运行两条旧容量反例，得到**2 FAIL/0 ERROR**：第一条仍把slot7的
position8/原target改成9/0xa0000000，第二条仍把slot0的position1改成9。首因是完整
自动Scoreboard比较，setup/teardown都正常；原安全8槽oracle与两个strict XFAIL声明
未放宽。自动比较先失败，之后的原assert不再冒称执行过。构建、源码、native/LCOV/HTML
哈希核验仍只证明身份/产物，不等于覆盖闭环。

[机器证据](../history/transaction-goal-ftq-resolve-transactions-20261102.json)保存实际收据。
两个leaf的当前适配完成不关闭Ftq顶层、其他前端或整个目标；下一必需项仍是顶层完整
SDK producer与prediction/meta/override、resolve/train、commit及取消/重试/收尾关联。

## Ftq 顶层完整ABI与SDK整槽输入（2026-11-02，协议仍待闭合）

实际复核确认433个非clock输入、468个输出及329个metadata输入。旧前缀扫描只能保证
“找到端口”，不能独立证明方向/宽度/集合；现按DefaultConfig及明确向量/类型模板建立
全叶expected，新增/删除metadata也必须失败，不能静默当作新的DCE。TwoPrefetchCase
真实为4-bit one-hot/zero Conflict，mainpipe bankSel为8-bit掩码；名字相似不代表1-bit。

还纠正了旧合同文档与构造器把redirect.pc/target都写成50-bit的问题。真实pc是50-bit
字节VAddrBits，target是51-bit字节GuardedVAddrBits，输出GuardedPc.addr才去掉最低位。
两个合法高位边界控制修前失败；四个duck-typed编码及两个override缺pointer控制同样
失败。修后完整FTQ为**322 PASS/2 XFAIL**，前287项判定不变，新37项均selftest。
该批机器证据见[顶层ABI收据](../history/transaction-goal-ftq-top-abi-20261102.json)，
是较早源码检查点，不冒领后续SDK或协议完成信用。

随后源码将顶层全部旧Pulse/Level/Reset调用改为SDK SyncDriver唯一整槽输入。
`FtqInput`冻结producer/control，统一编码整拍433输入；共享s3 override/meta身份不匹配
时整组拒绝，不能靠后写覆盖前写。`offer/drive_*`只staging不算接受，`step(N)`每个沿
核验真实输入/tick并保存不可变原plan。相同payload多有效沿仍独立slot。全部公开输出
进入原有双阶段快照，包括metadata、实际branch mask、两lane全部字段及指针/ready；
完整采样与输入收据不等于自动比较或accepted/completed事务账本。

首轮新并发控制发现正常inflight被`_require_clean`先判成未对账，导致预期concurrent
异常不匹配；控制自身又没在finally解除等待，产生独立active-driver cleanup ERROR。
保留首轮353 PASS/2 XFAIL及这条FAIL/ERROR，而不是改写全绿。修正busy优先检查、测试
等待任务finally放行，并使driver.close先由SDK拒绝active work再改变输入，避免cleanup
扰动仍在执行的slot。根242 PASS；修后完整/seed1及收集证据另按实际新源码核验。

同轮又用独立6条red控制证实`PredictionSpec`未冻结metadata、没有严格构造器，且
`allocate`会在后面未验证spec暴露之前推进前面合法部分。该输入计划问题必须继续修复，
不能只依赖最终driver的单槽校验。当前顶层finish仅防吞错/held producer，尚无完整
有界协议收尾；完整prediction/metadata/override、resolve/cache/train、commit/取消/重试
关联仍为真实必需任务，不能以本节的局部绿色关闭顶层、前端或整体目标。

整槽最终检查点随后核验为354 PASS/2 XFAIL、同源码seed1 145 PASS、根242 PASS；
初始/前序集合保留，十工程collection47874项。对应源码951c5101...与
[机器收据](../history/transaction-goal-ftq-top-slots-20261102.json)保持绑定。

输入计划/直接记录修复后，完整回归373 PASS/1 FAIL/2 XFAIL、seed1 138 PASS/1 FAIL，
共同源码0a3b3c81...、前356项判定不变。唯一失败不是metadata不可变性仍失败，而是新
控制的后置序列非法：redirect把BPU回卷到1之后，直接写meta1令PNR变2，越过BPU1。
现控制先用新prediction重新分配slot1，再写新meta；PNR不变量、模型、原功能体均未
放宽。不能通过把guard关闭或删除后置写来让immutable记录测试变绿。

三个额外native控制随后又证明完整采样并不等于自动比较：隐藏顶层commit、翻RAS或
翻SSP都不会报错，修前3 FAIL保留。现正将TOP-014接到`FtqCommits`：复用原独立FIFO
算法，输入(epoch,slot,lane)UID选择响应祖先，完整已知metadata来源于真实输入plan，
沿前完成与沿后预览分开；NONE/guard拒绝、完成/取消/待偿还精确对账，公开checker
和账本错误粘滞，finish只发送idle等待无ready的commit自主消费并检查空尾部。

原生无复位metaQueueCommit不能因reset而填0。已写image应携输入UID保留，未初始化
来源单列unknown_metadata、不冒称producer合法或metadata已检查。实际闭包还有独立
`always @(posedge clock)`写meta，reset有效沿的meta.valid仍会写store；初版组合模型把
此输入错放reset过滤分支，新增纯red1 FAIL保留并继续修复，不把reset清FIFO扩成丢meta。
完整自动commit/有界尾部的新原生与seed对照尚在运行；其他顶层协议仍继续，不签核全顶层。

上述commit子链最终以同源码fad6d9eb...核验为410 PASS/2 XFAIL、seed1 146 PASS、根
242 PASS；原356项判定保持，新增56项均selftest。无复位store的reset槽写入、同沿前后
不同metadata祖先、相同SSP但不同TOSW的错owner，以及第二个空尾槽伪造输出控制均通过。
十工程collection47930项，初始45883及前47874无删除/相对顺序保持，十任务exit0。
源码/构建/合并覆盖产物核验见[最终commit收据](../history/transaction-goal-ftq-top-commit-20261102.json)。
不能据此签核全部Ftq：另外五条native red仍因未自动比较而FAIL，必须继续修复。

## Ftq五通道自动比较与多义务账本（2026-11-02，最终验收进行中）

五条red对应路径已接到输入建立的`FtqFrontend`及SDK双阶段采样/Scoreboard，原生观察
注入均被拒绝。receiver的backend/IFU仲裁、IFU resolve转发、queue→cache→BPU消费不是
同一个完成事件；prefetch/fetch每次交接与override回卷重试分别有attempt，重试root来自
输入allocation，不按公开PC、索引或相同payload猜身份。metadata保持完整输入image与
UID，同步读/目标捕获/cache抓取各绑定实际祖先，未初始化值不能补0。

首版完整418 PASS/4 FAIL/11 ERROR/2 XFAIL的四个正文差异中，两条是反向端口压力的
same-flag6-bit减法被首版误作mod128，两条是旧IFU/Backend合并输入混用字节/半字PC。
位宽刻画与producer合法年龄分开，不缩窄原端口压力；三个IFU构造位置作显式`2*pc`，
first-owner oracle不改成last-writer。原11个teardown ERROR来自5个旧功能体仍留训练
报告，现仅在原断言后显式排空，fixture不补ready、不用reset消债。原7个顶层功能/
support文件经AST对账，差异恰为5个附加drain与3个PC坐标适配；不声称物理激励字节不变。

修后定向73 PASS，新增447个纯字段控制与输入UID/重试/仲裁/meta来源/尾部等组合控制
合计494 PASS，源码188ac50c...稳定并匹配。根242 PASS；最终完整、多seed与全仓收集
仍在执行。详见[工程合同](../../suites/frontend/ftq/docs/transaction-adaptation.md#五通道组合检查当前实现)。
纯字段翻转证明比较路径，不是RTL mutation；本地handoff完成不表示ICache回复或全机
退休。未接受、无消费许可的backpressured offer明确列在收据，不能虚报接受/完成；
已接受训练、receiver子义务及已给ROB target则必须有界完成或合法取消。

MBTB当前基线复核同时启动；其DefaultConfig四路owner/写回/cleanup、其他BPU/ICache、
MemBlock/VAGQ和最终全仓验收仍是必需工作。整体活动目标保持进行中，不作局部完成外推。

后续Ftq最终v4已核验为905 PASS/2 XFAIL、同源码seed1 122 PASS，源码0964e566...均
稳定/当前匹配，前412项判定保持、新495项全部selftest。最后补的是旧通道数自检9→
完整固定10通道集合，以及限定负控制必须是ScoreboardMismatch，防止训练收尾通用错误
假救活。全部覆盖/构建凭据核验，Ftq收集907项；全仓v3收集48424项仍属于当时源码，
随后BPU修改不能重标该哈希。三个FTQ DUT当前适配范围闭合，整体目标仍进行中；见
[最终组合机器记录](../history/transaction-goal-ftq-top-frontend-20261102.json)。

MBTB基线2257 PASS/229 FAIL已冻结。cleanup已改为独立输入LRU owner与完整4way×4rank
shadow/写回观察，真正zero-tag以raw半字tag周期构造；12个原生场景逐步越过beats0及
旧clear属性误期望，v2最后只因coverage仍固定2个物理端口失败。该guard正适配为完整
4路/恰2路有效，不能删掉来取绿；另205个纯迁移失败已在选测中修复，新增四way及错误
收据控制。完整新MBTB回归尚待核验，其他shared-service/full-capacity/semantic/depth
场景继续必需，不能借cleanup副作用通过关闭MBTB/BPU。

## MainBTB输入意图、metadata祖先与ICache首响应（2026-11-02，仍进行中）

后续完整训练账本检查点为2780 PASS/9 FAIL，同源码seed1定向90 PASS；原九条功能反例
保留。新的真实native控制又证实：只靠wire自洽的独立模型和SDK固定延迟关联，会漏掉
自定义expected/input-only lookup的错PC，以及同payload下的S0/S1/S2丢失；合法pending
取消也被旧tail当作失败。现输入计划先保存UID/epoch，独立核对真实沿、阶段token和
frame owner，SDK继续负责响应句柄匹配。原六条red与相位对照修后生产7 PASS。

再向训练来源追一层，metadata的显式deepcopy也必须保留实际lookup祖先；否则“内容相同”
会让source0冒充source1，或让修改expected counter后的profile冒充原始真实快照。
`MetadataOrigin`与只读来源catalog现核对UID/epoch/PC/时窗和完整metadata，整个burst在
分配训练UID前准入；刻意端口重放用非空reason明确声明，不晋升FTQ producer credit。
这实际揭露replacement场景将expected counter3归到原实际counter2的错误来源，现改成
在每次touch前读真实source，再用独立expected检查；未改oracle、删除反例或缩小分支激励。
该修复增加真实lookup，不能声称原全部物理波形字节不变。

当前来源定向2686 PASS/5既有FAIL；随后来源刺激修复定向23 PASS，当前源码seed1定向
105 PASS。新完整MainBTB和十工程collection已启动但待审计，不能拼造全仓新总数。
新原生控制还证实normal响应句柄在接受后reset、S0/S1之间disable的终态尚未适配：旧
SDK被错误的missing-frame封死，或新UID错误借旧frame；不把这两个框架缺口当RTL缺陷。
其余BPU及全仓目标继续。需求映射、逐运行哈希与真实待办见
[lookup/来源记录](../history/transaction-goal-mbtb-lookup-source-20261102.json)。

ICache DataBank的旧read循环用expected数据选择“正确的返回拍”，注入第一次错误后会
继续等待并以第二次正常值假通过。真实不同set相位探针确认latency-one边界后，现只在
该响应点采样一次；data/code首错与禁止读取oracle来选择采样点的控制通过，同源码双
seed各43 PASS。共享level源也不能以“set不走时钟”为由绕过SDK唯一输入claim：71处
构造位置已复用SDK所有权，三条native竞争red修后PASS，完整ICache326 PASS/3 XFAIL，
同源码seed1选测102 PASS/1 XFAIL，原294项判定保持、新35项均selftest。

这仍不等于11个DUT完成事务迁移：reset/MBIST/控制所有权、持续全通道采样、输入UID和
finish等继续必需，且close后send先重claim再报closed已有新native red待补。见
[DataBank证据](../history/transaction-goal-icache-databank-domains-20261102.json)与
[level来源所有权记录](../history/transaction-goal-icache-level-ownership-20261102.json)。

## 逻辑字典和owner模型也不能绕过事务边界（2026-11-02，修复中）

先前静态门禁只看physical names/信号操作，漏掉了`agent.read_driver.set({...})`、
`agent.model.write(...)`、`agent.ports`和私有边沿/编码helper。十条同功能体控制在
修前均以`no-static-leak-found`错误清零，现加入独立`owner infrastructure`列及
简单owner别名/常量getattr检查；普通事务字段和独立oracle保留合法。旧pin/signal
数字未改，基础设施/selftest目录也未扩大豁免。

新门禁真实揭露BPU24、FTQ4、ICache370等访问，Sbuffer原用例用`env.model.lines`
决定排空，因此根回归现为**256 PASS/1 FAIL**。应从四个显式入队输入建立响应承诺、
有界等待并验证无额外输出/最终empty，而不是改掉“transaction-only”断言或把正常功能
用例改标自检。工程源码当前仍冻结以等待完整MBTB/十工程collection的来源审计。

在冻结范围外已用原生反证与可执行原型验证下一步方案，但不冒充生产实现：MBTB
取消/过滤终态15控制PASS，终态与有效硬件响应、实际SDK比较交付分开；协议错误发生时
长reset等待应立即醒来并通过公开drain传播同一失败，不在后台继续运行到monitor溢出。
DataBank八条新原生red证实default read漏检、错原write无readback漏检、reset/MBIST
所有权及reset参数副作用；持续输入/响应原型含并发同payload UID和未计划读控制10 PASS。
MBIST的ack不等于完整66位响应，正常同地址控制看到req540/542、ack542/544、首完整字546。
第一版只填write addr未填addr_rd的相位探针失败属于合同假设待厘清，不能立即登记RTL
缺陷或通过缩小编码域掩盖。生产合入、MBIST独立来源/存储oracle、reset/cancel及严格
fixture finish仍必需。详见[门禁/原型机器记录](../history/transaction-goal-component-boundary-20261102.json)。

## 终态、历史索引与四工程生产修复（2026-11-02，整体仍未完成）

恢复时核验发现旧完整MBTB实际仍在最后shadow长矩阵运行40分钟，十工程collect阻塞于
suite-run锁，不是已经通过但通知遗漏。新账本每沿扫描全部已完成历史，1000/16000历史
在200空闲沿访问40万/640万行；必须按当前时窗/未产结果UID索引，而非删历史取快。
已核对独立进程组和源码后仅SIGINT该回归，nativeexit130、manifest未提交；根finally
保留了稳定source_after，但无完整summary，不能把存在source_after当完整功能证据。
放行后的十工程收集真实为48809项，原45883/48673及相对顺序保持；总数早于后续新控制。

生产已接入typed reset/filter终态及sample/真正比较delivery的分离；SDKcompleted既可为
有效响应也可为终态交付。自定义expected不能豁免错UID/reason、掉终态或损坏的SDK样本；
长reset在协议错时立即经公开drain报告同一失败，不继续到monitor溢出。保留所有历史行/
来源索引后空闲沿旧行访问均为0；定向2737 PASS/5既有FAIL、native75/5、pure2662，源码/
产物/构建核验，新73自检相对所选训练检查点PASS。新完整MBTB仍在跑，不给未出结果信用。
其中探针绿色重跑曾误覆写原red JSON，已从保留的原始stdout实录恢复并保存hash/事故
边界；原文件不再当red原件，辅助审计脚本改用独占创建拒绝覆盖，不能静默拼造旧收据。
见[生产终态/索引记录](../history/transaction-goal-mbtb-disposition-index-20261102.json)。

Sbuffer把模型驱动的排空循环改为原四笔Enq输入决定四笔有界响应，保留accept/hit检查并
加强原三沿尾部无额外请求；同源码双seed完整各66 PASS、原项判定保持，原门禁断言未改。
FTQ三个empty断言改用既有严格UID收据，随机场景独立实例化原oracle不再借agent状态；
当前完整905 PASS/2 XFAIL、同源码seed1定向57 PASS，原907项和顺序/判定保持，未扩大
自检分类或XFAIL。两工程新owner门禁均0仍不是全仓语义证明，见
[Sbuffer来源](../history/transaction-goal-sbuffer-timeout-source-20261102.json)与
[FTQ收据边界](../history/transaction-goal-ftq-receipt-boundary-20261102.json)。

ICache closed-send在重新claim前拒绝，完整327 PASS/3 XFAIL、同源码seed1选测103 PASS/
1 XFAIL；随后DataBank reset由SDK唯一驱动、非法参数无副作用、关闭后不重启，同源码
双seed DataBank各58 PASS，新9原生自检通过，原reset相关5条red同探针修后PASS。其余
default read、错输入无readback、MBIST所有权三个原生red仍未修；持续monitor/输入UID/
MBIST来源和严格finish继续必需，不把reset检查点当整DUT完成。根当前257 PASS，严格
全仓事务门禁仍exit1；BPU24/ICache370及MemBlock/VAGQ真实债务保持。资产工具的
source_files含Gitcached与拟发布untracked，并不是纯tracked数；另核对实际cached4610
路径无生成/内部资产，避免用错统计口径冒领发布完成。

## DataBank连续生产链及错误优先级（2026-11-02，整体仍未完成）

默认`read()`原来只有返回，`check_read()`才比较；原始write即使驱动错且没有readback也
可成功。现在由两个SDK lossless SamplingMonitor逐沿冻结全通道，原生发射t与物理消费/
功能响应t+2分开，输入UID在驱动前建立，不靠相同数据认人。输入的沿前getter能看到本次
排队意图，并非前一拍RTL消费，不能拿两拍输入直接相等当不变量。该错误guard的真实
12 FAIL/35 ERROR/27 PASS保留，修正后正常/错误控制都从真实相位得到区分。

MBIST的ack仅是注册req（t+2），宏操作t+4、完整66位读回t+6；同level保持两个有效沿
仍是两个UID。独立存储保存66位和每cell输入祖先，不再由功能体手改model补BIST答案。
明确singlePort源码和256-row几何说明共享地址为addr_rd的低8位，两个地址不必相等；
通用注释不能覆盖专用分支或成为缩窄合法域的借口。一way宏没有byte mask，be为0的
whole-word写仍合法。连续选择变更导致旧结果不再被mux选择、功能fire被注册MBIST覆盖
及ack后reset均按输入历史独立记终态，不把ack或相同word冒充响应/有效存储祖先。

当前source4003a071...完整ICache407 PASS/3 XFAIL、同源码seed1 DataBank129 PASS，
原节点/顺序/判定保持，来源/所有产物及66/6构建文件核验且native构建未改。原8native
runtime red同探针现在8 PASS；普通存储输入所有49个非clock叶均唯一claim，19个功能
owner耦合被真正移除而ICache其他DUT仍351。非零DFT控制语义和进一步生命周期仍必需，
不能把这次普通存储检查点说成所有模式或整个工程闭合。fixture在PASS/缺报告时严格
finish，已报告FAIL/SKIP仅cleanup；真正pytest async-yield/report-hook的子进程控制确认
吞错变teardownERROR、原正文FAIL不重复加ERROR、独立cleanupERROR仍保留。根266 PASS。
详见[持续生产机器记录](../history/transaction-goal-icache-databank-continuous-20261102.json)。

MainBTB完整ff41f...为2853 PASS/9 FAIL，seed1选测124 PASS且源码/产物核验，仍不能
仅凭9条FAIL的nodeid/判定不变就说归因正确：七个原semantic错误使账本停止更新后，被
SDK比较入口次生缺sample错误替代。新纯red明确验证错误对象身份而失败；现在先传播
公开reference.raise_failure，无先错时仍完整核对UID/终态/真实比较交付，纯11控制PASS，
新606640...完整正在冻结范围执行。不将这些未审计新结果重标为旧完整已验。

读取Sbuffer双DUT还发现正常退出只核对ledger或pipeline/tick，吞掉中途直接比较错误的
情况尚需真实native反证及粘滞首错收尾修复。当前仅登记源码审计，不冒称已执行新red；
整体计划保持唯一frontend当前阶段，该后续memblock必需项未被删除或偷记完成。

还须区分“finish最终报错”与“finish没有执行禁止的补救动作”：DataBank首沿前取消
read/reset后，旧finish虽会失败，却已多走4/2tick执行了未发射计划。两个真实native
red在无tick断言失败，不能只看已抛异常就判收尾安全。现在先拒绝输入计划/reset日程，
再考虑纯自主尾部；原22加新2控制24 native PASS，随后当前v6完整409 PASS/3 XFAIL、
同源码seed1 DataBank131 PASS，源码/产物/构建/旧项顺序及判定已核验。v5的407/3与
同源码seed1 129结果仍只属于前一源码，不合并冒领。
