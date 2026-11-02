# IFU 事务适配状态（2026-11-01，本工程已移交）

本文描述当前验证环境，不重标历史覆盖结论。全仓活动目标仍覆盖十工程/132 DUT；IFU
七 DUT 已完成当前适配范围，Ifu顶层的全部原功能体、guard和自检接入同一事务agent，旧直接
引脚helper/fixture已移除。最终输入描述、性能事件、生命周期及收据审计见末节；依据是实际
比较与正反对照而非静态清零。全仓适配、保留硬件FAIL与覆盖闭环仍未完成。

## 公共资源边界

`harness.py` 只负责 Picker 装载、初始参数与原生资源；fixture 在临时目录构造 DUT，
向 Toffee 登记 native coverage，并在最后 Finish。加载器默认使用 `ucv.runtime.native_seed`
取得 `ucv run --seed` 记录的种子，显式传入 seed 时才覆盖；`rand+reset+0` 保持关闭初始
寄存器随机化，与显式功能复位不是同一件事。修前加载器将默认 seed 固定为1，不能把
修前 seed=2 的命令收据当作原生 seed=2 的证据。

## 已适配模块

| DUT | 事务/独立 oracle | 绑定/驱动/采样/比较 | 生命周期 |
|---|---|---|---|
| IfuPerfAnalysis | `model/perf.py::Inputs/PerfModel` | `perf_analysis/{ports,agent,checker}.py` | 根fixture；显式槽Driver/lossless Monitor；严格Frame/端口、粘滞失败、三拍加空拍收尾（本轮补复核） |
| PredChecker | `model/pred_checker.py::Instr/Request/predict` | `pred_checker/{types,ports,driver,agent,checker}.py` | 根 fixture；独占 Driver、两个 lossless Monitor、精确槽关联与双空拍收尾 |
| RvcExpander | `rvc_expander/types.py::DecodeRequest`、`model/rvc.py::expand` | `rvc_expander/{ports,agent,checker}.py` | 根 fixture；无硬件时钟，native XClock评估事件 + lossless Monitor；单NOP收尾 |
| InstrBoundary | `model/boundary.py::BoundaryInput/Output/predict` | `instr_boundary/{types,ports,agent,checker,stimulus}.py` | 根 fixture；无时钟评估槽；独立valid限定比较，完整有限批次及单idle收尾 |
| FrontendTrigger | `model/trigger.py::Trigger/Update/Inputs/TriggerModel` | `frontend_trigger/{types,ports,agent,checker}.py` | 根 fixture；真实沿前/后双采样；CSR与端口域分开，最终配置/disable双槽收尾 |
| IfuUncacheUnit | `model/uncache.py::Inputs/Outputs/UncacheModel`、`uncache_unit/types.py` | `uncache_unit/{ports,agent,checker,ledger,stimulus}.py` | 根fixture；沿前全部握手/沿后脉冲；输入UID/epoch、显式取消和有界收尾 |
| Ifu | `ifu/types.py`、`ifu/input_contract.py`、独立字节流/ISA/UncacheModel/PerfModel/fetch_events | `ifu/{ports,agent,checker}.py` | 同一唯一Driver/双lossless Monitor服务全部通道；逐UID/阶段/peer、carry与性能事件尾部账本，旧端口压力与显式producer类型分开 |

## PredChecker 事务与绑定合同

事务和返回值的 PC/target 均为**字节地址**；只有 ports 层转换到真实 `[50:1]` 半字端口。
Instr 限制 PC 为对齐的 51 位 GuardedPc；位移允许对齐的有符号51位值或其无符号51位
模数表示。所有标志为1位，branch/ras各2位，end_offset为5位；越界、非整数和未知键
在进入驱动前失败，不靠 XData 丢高位。旧目标算术用例中两个超宽 XLEN 常量已经显式转为
它们原先实际送达端口的 GuardedPc 值，原6组目标加法器输入不变，另有越界拒绝自检。

Request 必须完整提供36个 Instr；构造时复制调用方 list 为 tuple，Instr/Request 均冻结。
DefaultConfig 中只有 lane0..34 有指令：lane35必须是空指令，lane34 cross必须为0，否则
拒绝。lane35唯一保留的PC加法器使用独立、确定的覆盖噪声驱动，不冒充可选择的指令。
ports 显式检查三个已证明裁剪端口不存在；所有真实输入（除 clock 外422个）由一个
Driver 声明，35个组合结果和11个重定向字段严格绑定宽度/方向。新增、缺失或改宽端口
必须重新适配，不能默认为0或继续忽略。lane34常量证明及lane33合法跨块重定向对照在
`tests/framework/test_pruned_ports.py`，沿用真实 IFU producer 的窗口/对齐模型。

### 时序、身份与收尾

此接口没有 ready，不虚构握手或响应 UID。每个显式 cycle 对应一个输入槽，比较器按
以下三组观察检查（`registered_tick = combinational_tick + 1`，相邻输入槽差2 half-tick）：

1. **DriveStable**：组合 stage1 属于当前 Request，逐 lane 比较截断；不错误地用
   request.valid 门控该组合结果。
2. **同一 DriveStable**：stage2 仍属于上一输入槽，检查其 valid 和有效 payload。
3. **接下来的 RisingEdge**：stage2 才属于本次 Request，比较完整 target/分类/坐标。
   valid=0 时 payload 无合同意义，不将残留寄存器当作错误或期望。

观察来自 Toffee SamplingMonitor 的同步 capture，使用 Bundle.sample 保存不可变快照；
返回 CheckedCycle 只含值、输入槽序号和两个 tick。槽序号由环境建立，不从输出反推身份，
也不把它叫作 DUT 的接受计数。`predict/fault_classes` 算法未改动；比较使用 Toffee
Scoreboard 的直接入口。自动一输入/一 rising 响应链不能同时表达当前组合结果和上一拍
寄存结果，所以由本 agent 明确关联两阶段，不再复制框架队列/时钟/monitor 实现。

`PredCheckerDriver` 经共享 ExplicitSlotDriver 继承框架 SyncSingleCycleDriver，保留所有权、接受沿及整帧撤销；
额外使用公开 `Execution.paused()` 在显式输入槽之间暂停**仿真时间**，而不是停 monitor。
原因是持续采样订阅也会推进时间：pytest 的 fixture/call/teardown 任务切换可能先采到
尚未供应请求的 DriveStable 空闲槽。只检查 tick 相邻不能辨别这种错误。现在每个周期
从暂停的上升稳定点开始，先写全帧，再运行两个采样阶段，最后撤销并暂停；需要空闲
时间时仍须显式 cycle(empty)，该槽同样受检。跨12次 asyncio任务让出的自检验证此边界。

正常 finish 发送两个空槽，核验上一重定向、清空及无重复，不能靠关闭 monitor 丢掉尾部。
reset 明确取消寄存重定向；随后新请求的首个阶段不应看到旧 payload 的 valid。失败或
中断的输入槽标记为未对账，禁止吞掉取消异常后再报告正常 finish；退出仍释放两个
monitor、driver所有权、Execution及 backend。运行期并发 cycle 被明确拒绝。

### 需求到检查链

| 需求 | 输入 / 独立期望 | 观察及比较 | 代表用例/控制 |
|---|---|---|---|
| PC-001/002 分类合法/全放行 | Instr类别/taken，顺序语义 oracle | stage1全35 lane及redirect.valid | legal_predictions / accept_all_taken错误模型 |
| PC-003/006 首故障截断 | 有序窗口、首故障位置 | 固定valid tuple及该lane redirect字段 | earliest_fault / fault_position_sweep；错截断快照 |
| PC-004 字节目标 | PC+位移或PC+2/+4，51位模加法 | target半字解码为字节再逐值比 | target_arithmetic / wrong_target控制 |
| PC-005 属性/坐标 | fault lane的原始属性，invalid时属性清空 | 11个redirect字段，valid限定 | fault_lane_coordinates / 全字段翻转控制 |
| PC-007 跨拍、撤销/reset | 当前/上一输入槽关系，不读取内部寄存器当答案 | 两相邻tick与两槽空闲检查 | back-to-back、identical_adjacent、inactive_payload、reset；旧tick/旧payload/重复尾部控制 |
| ENV-001/002/004 边界完整性 | 正确schema、合法域、唯一driver | 缺口即失败，关闭monitor不能通过 | `test_pred_agent.py` 的49个自检；不是RTL mutation |

原12个功能用例、原3个相关环境用例保持 nodeid 与判定；新增3个功能用例与49个自检。
随机请求仍是**端口合法域压力**，不因适配成功就宣称每个随机元数据组合均由真实 IFU
生产者可达。原始功能覆盖和未证明范围保持 `verification_plan.json` 的边界。

## RvcExpander 组合事务合同

`DecodeRequest(word, fs_is_off)` 是不可变的32位指令字与布尔FS状态，超宽、负数、非整数、
非布尔编码和未知键在进入驱动前拒绝。32位输入不等于只传16位：压缩字的上半字来自
后续字节，不参与本条展开；低两位为11的全宽字必须32位原样返回，不在此层再次判断
完整RVI是否合法。输出快照 `Decoded(bits, ill)` 和含槽序号/tick的 `CheckedDecode` 均冻结。

ports 严格检查2输入/2输出的宽度、方向及输入集合；不存在clock/reset/ready/valid，新增
引脚须重新适配。native `GetXClock()` 在无硬件时钟的Picker包中仍能推进评估时间；这里
RisingEdge(XClock) 只是框架的**评估完成采样点**，不是RTL上升沿、接受握手或一拍流水
延迟。lossless SamplingMonitor 同步 Bundle.sample，须与本次driver完成事件同tick，
相邻显式评估差2 half-tick；队列旧值、错误载荷或缺快照都不能当本次结果。

`drivers/explicit_slots.py` 现在由六个实际DUT使用，只共享框架单槽调度与调用间仿真暂停，
不包含任何编码或oracle。PredChecker保留专属Frame/driver入口，完整IFU重跑核验共享前后
判定不变。monitor在运行期间持续开启；任务切换不消耗额外未供应槽。退出送入一个定义
明确的全宽NOP并检查，纯组合无在途流水可“排空”，不虚构额外完成事务。已失败/取消的
评估保留未对账状态，吞掉断言或恢复monitor不能使finish重新成功；生命周期释放全部组件。

独立ISA模型 `model/rvc.py` **字节未改**。check_decoding 用 Scoreboard 比较ill，只有
架构规定的非hint合法指令才比较bits；hint允许规范化、illegal的bits无合同意义。该有效
域来自独立oracle，不来自DUT值，也不允许expected override通过设置hint来隐藏应比较的
指令字。定向编码表仍由独立ISA编码器给出期望；原错误寄存器重映射算法的3组负对照保留。

| 需求 | 驱动 / oracle | 观察 / 检查 | 控制与边界 |
|---|---|---|---|
| RVC-001/002/003/004/008 全宽/整数/访存/控制/Zcb | 32位字，独立 `isa/cenc` 编码表与 `expand` | ill + 有定义bits | 原表逐项不变；错寄存器重映射/错bits被拒绝 |
| RVC-005 FS门控 | 同一FP字、逐次FS状态 | 当前ill与合法时bits | 新增同字FS 0/1/1/0功能例；不能用前一次结果 |
| RVC-006/007 保留/hint | 架构分类，不读取DUT建立合法域 | ill总比较；bits按合同限定 | 合法任意未规定bits仍通过，错ill必须失败；override不能扩大豁免 |
| RVC-009 组合无状态 | 当前完整word+FS，历史只作控制 | 不可变快照和精确槽tick | 原stateless序列、新增压缩字上半字变化；旧tick/旧payload/任务让出控制 |
| ENV-001/002/004 完整边界 | 严格输入、2+2绑定、唯一driver | 缺口/错宽/错方向立即报错 | 38个自检，含关monitor、缺快照、错误末尾输出、取消/吞错；不是RTL mutation |

原11个功能用例的**28331笔输入及顺序**经纯生成器对账完全不变（不是原生采样日志），
包括12000×2压缩样本与2000×2全宽样本；所有编码表原值保留。新增2个正常功能用例和
38个自检。完整受管原生IFU回归、seed2单worker和根测试证据见活动目标记录，不把纯
生成器对账或manifest完整性当作RTL正确性/覆盖闭环证明。

## InstrBoundary 半字流事务合同

真实ICache生产者的maybeRvcMap是**每个半字低两位是否不是11**，并非“只标真实指令起始”
的压缩格点。16条 `addi x1,x0,0` 就能合法产生0xAAAAAAAA，不能禁止续半槽的map位。
`BoundaryInput`冻结并校验块大小1..32、布尔标志、5位offset/index、32位map/块选择、
taken位置和块选择与split关系；index list复制为tuple，空向量不默认补齐。随机index是
leaf端口域压力，不宣称任意排列均能来自真实ICache。`model/fetch.py::build_window`改按
实际raw_slots逐半字产生map，数据/metadata保持一致；payload oracle的aligned_lanes和
branch_info AST不变。

严格绑定40输入/257输出，唯独slot31 cross为已证明裁剪常量：ports要求其不存在，模型
对所有split证明0，并保留slot30及真实跨块非零对照。所有输入由一个框架Driver独占；
使用共享显式槽调度、lossless SamplingMonitor和不可变BoundaryOutput。native XClock
仍仅代表组合评估完成，非硬件时钟或握手；每次sample与driver同tick，相邻槽严格差2。

### 字段有效域与独立oracle

- valid、instrEndMask、first/totalEndIsHalfRvi全槽/标志比较，不依DUT valid缩小范围。
- Helpers.compact只选择有效槽；isRvc/cross/坐标/blockSel/index按**独立期望valid**比较。
- Ifu重建carry首槽时会把endOffset重写0，故只有该字段不约束leaf原值。carry的cross
  **没有被消费者重写**，必须比较；不能把首槽其余metadata一起豁免。
- cross的独立语义要求本窗口真正的指令起始；carry上半槽不是新起始。旧模型与RTL均
  漏掉该条件，导致数据相关的FTQ归属错误，登记为[R-14](bugs/instr-boundary-carry-ftq-owner.md)。
  正常高半字0x10与错误高半字0x13的leaf/真实invalidTaken恢复均保留，不改oracle取绿。

| 需求 | 驱动/独立期望 | 观察/比较 | 控制与边界 |
|---|---|---|---|
| IB-001/003/004 格点/结束/半指令 | 原始半字流、carry、end位置 | 全valid/endMask/half标志 | 原600窗口、额外600 raw maps；错误valid/endMask/half被拒绝 |
| IB-002/006 坐标/归属 | split、独立起始格点和index | 有效槽metadata，carry仅endOffset例外 | 原全宽sweep、新全压缩sweep；无效槽metadata可变，合法槽同字段错误必失败 |
| IB-005 跨块 | 真正起始跨当前split才是cross，carry不跨 | 有效cross与顶层FTQ身份 | 冻结旧错误模型、正常/低11高半字对照，原五个随机反例保留FAIL |
| ENV-001/002/004 完整边界 | 严格输入、40+257绑定、唯一driver | 精确tick、完整样本、有限尾部 | 53自检：缺端口/宽度/方向/所有权、跨任务/旧值/缺样本、batch/取消/吞错控制 |

`analyze_many`只接受预校验后的非空有限list/tuple。仅已完成快照的ScoreboardMismatch
可以累计，时序/monitor/类型错误立刻中止。原600样本全部比较，报告五个失败索引
137/254/406/477/529后明确FAIL；不会为了保留后续样本而吞掉基础设施故障。正常finish
再检查一个IDLE组合槽；取消或吞掉失败仍为未对账，不能恢复monitor后重新报正常完成。

### pytest正文与收尾

async fixture的yield不会收到正文异常，曾使已记录FAIL的用例再被严格finish重标为ERROR。
`fixtures.py::agent_runtime`将已存在的pytest setup/call非通过报告传给agent退出，原FAIL/
SKIP等判定不变；无报告或正文PASS仍严格finish，因此吞错不能伪通过。独立清理异常仍
传播。10个新增根控制覆盖setup/call、原异常身份、吞错、缺报告和独立cleanup；真实
R-14失败也不再附带虚假的teardown ERROR。六个已适配agent复用该资源机制。

## FrontendTrigger 配置与live比较合同

`Trigger/Update/Inputs`全部冻结，嵌套输入列表复制为tuple。输入严格校验match2位、action4位、
完整64位tdata2、布尔select/chain/timing及live控制、四个enable、36个对齐50位字节PC；
timing必须0（CSR固定before-execution，接口无timing端口），valid update必须有明确payload。
PC只在ports转换为49位半字端口，不在测试内右移，也不把完整PC向量强制收窄成密集序列。
严格绑定50个非clock输入和36个4位action输出，检查clock宽度/方向；未知输入、缺失或改宽
立即失败，唯一Driver拥有全帧，capture只保存不可变Actions值。

### producer与端口域压力不能混为一谈

公开`Bundle.scala::GenTdataDistribute`与CSR `DebugLevel.scala/Debug.scala`确认：
select=0、timing=0、MATCH只EQ/GE/LT、ACTION只0/1，tdata2全部64位可写，不能用本地
比较器的50位截断定义合法输入。CSR链检查只禁止相邻chain位均为1，**没有强制最后一个
chain位为0**；初次准入误加了该约束，最终已移除并加入真实合法末槽chain控制，不能用
看起来“更干净”的子集替代producer域。

`cycle(inputs)`检查当前/更新后配置表符合上述CSR编码和链约束；这证明叶子入口的配置
编码/历史约束，不替代整个CSR权限/分发流水验证。`characterize_cycle(inputs)`显式保留旧
保留match=1、select=1、action2/3/15与任意链的端口压力，仍受同样的严格schema、所有权、
采样、oracle和收尾约束，不增加宽泛豁免。相关原功能点可说明叶子端口行为，但不算这些
配置的CSR生产可达证据。原15个用例的798笔**计划激励**及顺序完全相同，含原180步随机；
纯生成器对账不是原生采样日志。两个R-13用例现已在更新沿后立即失败，不能称失败后计划
中的第二笔输入也已实际执行。

### 两阶段、复位与有界收尾

每个输入槽使用显式槽Driver及两个lossless SamplingMonitor：

1. DriveStable检查当前live PCs/debug/permission与**旧**配置/enable产生的36 lane动作。
2. 同一RisingEdge检查相同live输入与**新**配置/enable产生的动作。

两个快照严格差1 half-tick、相邻输入槽差2，以本地sequence关联；不存在ready或硬件UID，
不虚构接受握手。物理沿发生后独立模型必须前进，不能因比较失败倒退影子状态；失败、
取消和reset检查错误均粘滞为未对账，吞掉异常/恢复capture不能使finish成功。

复位答案是配置和enable**全零**。旧TriggerModel把action错误初始化为None15，仅因从未
在启用但未更新的PC0上检查而漏检；现改为action0，以固定零答案和冻结旧错误模型作
区分性对照。compare/can_fire/lane_actions/tick核心算法AST不变，全64位tdata2仍保留R-13。
正常finish在最后PC向量上检查一次最终配置，然后检查已寄存disable后的安静槽；不能
关闭monitor把最后一次配置或旧动作丢掉。reset另检查每次沿后全None，再发正常空槽。

| 需求 | 输入/独立答案 | 观察/比较 | 控制与边界 |
|---|---|---|---|
| TR-001/003 配置/enable时机 | 旧表→更新后表；当前live门控 | 沿前/后全部36 lane | 新配置/enable双阶段、debug/permission不延后；旧tick/旧payload分别拒绝 |
| TR-002 比较宽度/坐标 | 50位PC零扩展与64位tdata2 | 每lane当前PC，EQ/GE/LT | 原128字节carry扫描、原180随机、新非密集64字节跨度；R-13两条FAIL保留 |
| TR-004/005/006 链/动作 | CSR无相邻chain；debug>允许的bp>none | 每trigger配置及每lane动作 | 原链/优先级/36lane扫描、末槽chain合法对照、错lane逐项拒绝 |
| TR-007 复位 | 全零配置与enable，不是action=None | reset沿后/启用PC0后动作 | 零答案及冻结旧错模型对照，reset错误被吞仍不能finish |
| ENV-001/002/004 边界/生命周期 | 严格值/端口/唯一driver | 两相邻阶段、两尾槽 | 71自检含缺端口/错宽方向/额外输入、writer冲突、任务切换/并发、关monitor/缺样本/吞错/取消；不是RTL mutation |

新增5个功能用例和71自检通过，最终完整IFU及单worker native seed2的原判定不变。
真实顶层taken-branch前史的shift0..3有限诊断也均命中目标lane；它是保留诊断，不额外
计入受管功能数或全组合生产可达证明。

## IfuUncacheUnit 请求/回复/完成合同

### 类型、单位与完整绑定

Inputs/Outputs、ReadRequest/BusReply、CheckedCycle/Events/Status/RequestRecord全部冻结。
构造时校验布尔位、PBMT2位、32位回复数据和**48位对齐字节地址**，valid denied必须同时
corrupt；未知键/缺字段、负数、超宽或隐式浮点/字符串转换均拒绝。当前PrunedAddr的47根
线代表物理地址`[47:1]`，不等于“47位字节地址”；只有ports右移输入/左移输出。

ports严格绑定15个非clock输入（含reset）和9个输出，检查clock及所有端口宽度/方向和
输入集合。fromUncache.ready由本基线固定true且已裁剪，明确登记为常量1；若该端口以后
出现必须重新适配，不默认为0或悄悄忽略。一个框架Driver拥有整帧输入，两个lossless
SamplingMonitor各自保存全部通道不可变快照，不为等待某一通道漏采其他通道。
单一ready/valid响应绑定不能同时表达req fire、bus issue、沿后完成和flush优先级；本agent
仅增加领域关联/账本，复用框架Driver/Execution/Monitor/Scoreboard，不另建时钟或采样队列。

### 沿前握手、沿后脉冲与独立比较

DriveStable快照属于当前输入/沿前状态，用于req fire、总线issue及之前完成脉冲；同一
RisingEdge快照用于本槽状态改变后的完成/取消结果。两个tick差1、相邻输入槽差2；每槽
有本地sequence，不把Driver完成事件当成DUT接受或响应。

ready/valid三个字段始终比较；bus/response payload分别按**独立oracle的valid**比较。
不可用DUT valid或expected override隐藏本应比较的字段；valid0的未消费payload不额外
约束，复位另按固定零状态严格比较全部寄存输出。ifuStall可撤销toUncache.valid，不能
把Decoupled擅自当Irrevocable；恢复valid后仍须是捕获的同一地址/属性。

独立UncacheModel四阶段算法的归一AST与修前完全相同；坐标变成字节值不改变其协议
算法。它负责expected阶段；ledger另外用实际受检快照的fire/脉冲记录事实，不再把模型
计数冒充已观测接受。Status.phase只是独立协议进度，不是读取RTL内部FSM的证明。

### UID/epoch与peer来源

UID由环境在提供输入前分配，不能从返回地址/数据反推；同一地址/数据的新请求仍有新
UID。RequestRecord冻结保存原始请求、epoch、scope、fire/issue/terminal tick和取消原因：

- `offered_cycles`计输入槽上的offer，不机械要求所有可撤销offer最终被接受。
- `req_fires`是沿前req valid/ready；flush不门控ready，因此必须分开同拍fire与生效。
- 非flush fire才计`accepted`并产生唯一active UID；flush-on-fire保留事实但不新增live义务。
- bus valid/ready只在真实沿计一次`issued`；held多拍不重复，地址/两属性另与原输入记录比较。
- 完成在沿后resp_valid真正通过比较后，按active已issue UID计一次；下一沿前旧脉冲不重复
  完成，新请求可同槽接受，两个UID明确区分。
- flush/reset将active义务转为cancelled，复位提升epoch但不清历史；恒满足
  `req_fires=accepted+flushed_on_accept`、`accepted=completed+cancelled+active`。

正常`cycle`要求MMIO/NC/IO，回复必须显式提供已issue UID，通常通过`reply(uid, BusReply)`
或`read(ReadRequest, BusReply)`；未知、未issue、重复、布尔别名UID及端口压力请求的
“正常回复”均在推进前拒绝。真实InstrUncache只在干净非RVC且起始地址为页末半字时给
needResend，normal路径校验这一来源关系；read在发起前即拒绝不合法的请求/回复组合。

**UID不是硬件tag。** 对已issue后取消的UID，若当前不在新WaitResp，允许显式关联迟到
回复并验证无完成；若新请求已进入WaitResp，线路无法区别同值新/旧回复，normal入口
必须拒绝注入这种歧义，而不能声称DUT有隐藏身份检查。真实peer的needFlush负责过滤旧
代际，叶子测试不替代完整InstrUncache/TileLink/全局flush系统验证。任意无来源回复、
reserved PBMT、PMA非MMIO或不合法resend组合仍可作显式端口characterization；它不豁免
schema/所有权/采样/比较，也不获得生产可达credit。

### 有界收尾与原用例保留

`read`只用调用方明确提供的peer数据，在观测到bus issue后才发回复，并必须在预算内
观测到对应UID完成。`finish`再检查两个空槽及无重复脉冲，仍有active请求必须失败；
**它不自动发回复、flush或reset来清债**。部分状态场景要显式cancel_pending(reason)，
中途reset在有在途请求时必须有取消原因，失败或取消的输入槽不能吞错后恢复为正常finish。

原11个功能体的767笔主激励（含700随机）经`tools/audit_uncache_stimulus.py`逐笔对账，
**物理端口值与顺序完全不变**。旧raw47位地址常量显式左移为字节值，未删掉原raw奇数
样本/高位；新增显式取消/reset控制另列，不伪装成原有主输入。此证明是纯生成器对账，
不是RTL采样日志。原700帧真实受管运行核验fire94/生效89/完成75/取消13/同拍flush5，
末尾1笔Send由场景明确取消；旧shadow的89不再被叫作全部物理fire。

新增19个合法完整历史和72个自检。前者覆盖五种合法内存类型、干净/HWE/AF、跨页/最高
地址、相同数据不同UID、同拍flush、新旧完成/接受、合法取消后迟到及真实背压/IFU stall。
后者覆盖非法域/缺端口/宽度/方向/新输入、第二writer、错UID/重复/歧义回复、合法mask
对照、零接受、丢最后完成/重复尾部、三个阶段欠债、两monitor故障/旧tick/旧payload、
并发/任务切换/reset/取消/吞错。注入在Python观察/期望层，不是RTL mutation或额外硬件PASS。

| 需求 | 驱动/独立期望 | 观察/检查 | 控制与边界 |
|---|---|---|---|
| UC-001/004 捕获/类型 | 输入字节地址、MMIO/PBMT及UID | 沿前fire和issue，三项bus载荷与输入记录比 | 最高地址、五类正常read、busy压力、同拍flush |
| UC-002/003 排空/背压 | 非幂等需release，NC不需 | 全通道两阶段及一次issue | MMIO真历史、原700压力、冻结wait-all错误oracle |
| UC-005/006 响应/脉冲 | 显式已issue UID/peer数据与异常规则 | 沿后全部有效payload、一次完成、下一沿清零 | 错ready/数据、丢完成/重复尾部、同值不同UID |
| UC-007/008 取消/单槽 | epoch/UID/cancel理由与peer过滤假设 | 旧脉冲/新接受分开；账本等式、完成/取消互斥 | 合法迟到、歧义旧UID拒绝、reset历史、欠债finish失败 |
| ENV-001/002/004 完整环境 | 严格类型、15+9绑定、pruned1、唯一driver | lossless快照、精确tick、有界尾部 | 72自检，非硬件mutation；原11主输入767笔保留 |

最终完整IFU为478 PASS/5 FAIL/1 UNCERTAIN，原393项逐条不变；真实native seed2单worker
选择104 PASS。源码/构建/manifest与门禁的核验见活动记录，不将coverage_complete当覆盖闭环。

## PerfAnalysis生命周期复核（后续证据纠正）

初版18自检覆盖丢末尾理由和monitor停止，却未覆盖调用方吞掉比较错误后恢复capture。
新red受管探针`perf-revisit-red`为1 FAIL/1 PASS：错误比较确实被拒绝，但旧finish没有
保持未对账状态，`test_swallowed_comparison_cannot_become_a_clean_finish`因DID NOT RAISE
失败。跨12次任务让出的合法对照本来PASS，不能夸称已复现时序故障；旧通过结果保留
其原范围，不能当作这个新义务早已完成。

现补齐整个cycle/reset/finish的粘滞失败、取消状态，原子busy保护、一次finish与禁止
重启；Frame严格校验Inputs/reset，ports检查全部one-bit宽度/方向、clock和完整输入集。
reason快照严格为完整76位非负整数，比较复用框架Scoreboard，不默许0.0==0或缺样本。
采样仍为DriveStable，使用共享显式槽Driver保持monitor持续开启，并追加相邻输入槽
精确+2tick检查；当前沿确认仍为sample tick+1。原3+1空槽收尾不缩短。

新增15自检通过，涵盖上述red反例、取消/reset吞错、旧tick、并发reset、Frame/端口和
快照域及严格finish/restart；独立PerfModel和原功能文件**字节未改**，原484项判定不变。
最新完整`perf-revisit-integrated`为493 PASS/5 FAIL/1 UNCERTAIN，真实native seed2定向
43 PASS；实际7native文件/收据未改，collection46235、根126 PASS，严格事务门禁仍exit1。
这不是修改RTL或关闭R-13/R-14；本模块后续证据见
[机器记录](../../../../docs/history/transaction-goal-perf-revisit-20261101.json)。

<a id="ifu顶层缓存链已实施整体尚未签核"></a>

## Ifu顶层缓存链：缓存阶段检查点，整体尚未签核

`ifu/{types,ports,checker,agent}.py` 已接入原49个取指功能体中的40个缓存功能体，另迁移
缓存guard、pruned与比较器控制。当时9个uncache功能体及其guard保留旧fixture；后续已
按下一节迁移，未把helper挪为自检或从门禁豁免。下列为当时的缓存阶段范围，最终审计见末节。

- `FetchRequest`、`Frame`、`Enqueue`、`Redirect`、`Snapshot`为严格不可变类型；`Window`
  与嵌套`Inst`冻结，列表复制为tuple。物理地址是48位字节地址，PC51位、GPA56位；
  编码仅在ports中去隐含bit0。旧raw `Window.paddr0`不能被新入口静默忽略，必须显式归一。
- 唯一`ExplicitSlotDriver`占用80个非clock输入，ports逐项验证宽度/方向及完整集合；
  405个输出全采样。lane35 predTaken仍为有独立证明、明确核验不存在的常量0。
- 两个lossless `SamplingMonitor`从运行开始到严格finish结束持续开启：DriveStable核验
  即将被接受的事件，RisingEdge核验同一输入沿后的流水可见值。每槽校验相邻tick，不把
  driver完成的输入槽当成DUT请求接受，也不在首个beat后停止读valid。
- UID在输入提供时建立，记录未接受offer、物理fire、同拍flush取消与有效进入流水；
  缓存阶段历史将s1、s2和writeback关联到同一UID。payload由独立指令流模型决定，不从
  DUT输出反推。重定向取消年轻stage，不取消同FTQ的自身held beat；指针按独立计数推进
  并在redirect更正，reset保留历史且取消活动义务必须给原因。
- IBuffer的offer/held/fire分开；ready0不算完成，GPA `wen`却按valid生效，所以合法同址
  幂等重复写可出现多次。cached valid/enq、异常、有效lane的payload/FTQ/endOffset/
  foldedPC/predTaken/triggeraction与GPA完整比较，padding常量总比较。无效lane metadata
  不进入消费者，因此不从DUT valid构造比较mask。`prevInstrCount`是下一槽容量预告：有
  s1推进时比较下一窗口spec count，否则比较当前count，不机械当成当前beat长度。
- Trigger配置复用严格CSR合同及独立模型；debug/permission与FS为live门控。ECC只在
  接受后的下一槽脉冲一次，不延长到整段等待。topdown reasons用独立`PerfModel`逐阶段
  核验；当时13个performance输出仅冻结采样、不给比较credit，末节另记之后补齐的事件链。
- carry在输入历史中保存原PC、低半字和源UID；可跨一次fetch存续，但finish不能自动
  flush/reset清债。最终半指令须完成或由场景给原因显式取消。比较、reset或Python取消
  被吞后状态仍为未对账，不能通过恢复capture得到正常finish。

旧顶层原生包装的scalar宽度元数据为0（逻辑1位），竟能把FTQ flag2/3写入并读回2/3。
这不是合法RTL位编码。6个功能体中的34个计划窗口已显式将这些非法值改成其低位0/1，
新增flag2/3拒绝控制；不宣称这部分原物理激励保持。其余计划窗口字段、指令数据及
顺序不变：纯生成器对账40功能体/41参数变体/373窗口，包括5个完整32随机窗口；四个
手工时序体只比较首个已构造窗口，不假冒原生输入trace。证据工具
`tools/audit_cached_stimulus.py --before <冻结文件>`明确输出该边界。

缓存checker另补两个先前未统一比较的投影合同：invalidTaken的低半字不在完整指令
valid/enq中；memory-predictor folded PC只包含虚拟地址、不是GuardedPc的溢出位。
独立`aligned_lanes`/`branch_info`/`build_window`算法未复制或改写成RTL，投影有原功能
及guard/invalidTaken/carry正常对照，R-14仍在端口场景的FTQ归属处FAIL；生产可达结论
按下节的新反证收紧，不能因用的是真实native就称输入来自真实FTQ。

自检的注入都在Python快照/期望层，不是RTL mutation或额外硬件功能PASS。原先
“首结果后额外两拍valid仍PASS”的诊断见[顶层前置审计](../../../../docs/history/transaction-goal-ifu-top-review-20261101.json)；
当前相同`fetch`实际调用链在沿前和沿后重复/隐藏beat、重复redirect、错载荷和错误oracle
控制下都拒绝，正常控制通过。

### 缓存阶段移交清单（历史）

当时必须继续迁移9个uncache功能体及其guard、raw PA转换、真实peer issue/reply/UID、
needResend/carry组合和严格收尾，并移除仍被这些场景使用的旧helper。旧非页末resend
保留为显式端口压力，另补真实peer历史；不能用cached入口拒绝uncache来称顶层完成。
完整FTQ生产者尺寸/年龄/不重用身份和所有保留端口压力的来源分类仍待总审计，当前缓存
入口只证明严格端口编码和所执行历史，不宣称全部窗口可由真实FTQ产生。之后仍须完成
BPU/FTQ/ICache、MemBlock/VAGQ及最终全仓验收，不用静态计数清零代替必需语义工作。

## Ifu顶层uncache与生产者复核

9个旧uncache功能体及uncached guard已接入同一`ifu_agent`，所有49个旧取指体/两个guard
不再直接读写引脚。旧`apply_window/read_beat/read_redirect/fetch/uncache_collect`等helper
和最后的raw fixture已删除，原用例没有被移动、豁免或删选。原raw PA显式左移为字节地址，
ports才右移编码；原非页末resend作为`characterize_reply`保留，正常`reply/read_uncached`
执行真实InstrUncache的页末/clean/非RVC关系。两者都必须提供已经实际issue的UID，不可
按返回数据或当前地址猜身份。旧已取消回复仅在没有另一个WaitResp时代际可证明无歧义；
有新WaitResp时，无tag接口无法辨别旧数据，要求peer过滤，不能冒称DUT检查了UID。

组合时复用已经验证的独立`UncacheModel`，没有另写RTL状态机oracle或读取内部寄存器。
沿前/沿后均核验全部bus/IBuffer/redirect/GPA/topdown通道；发送期间持续响应其他通道。
`send_uncached`返回的是已观察到bus fire的输入UID，不是driver返回就算完成。
非幂等访问用真实前史进入wait/drain；bus保持不重复计issue；reply后的完成脉冲只消费
一次。resend不入队，保存低半/PC/来源并要求后续完成或显式取消；不能把首次resend
当作整个场景完成。backend/reset取消记录保留，finish不补回复、flush或reset来清债。

逐UID审计核对物理fire/同拍取消/生效，以及issued/reply/enqueue/redirect计数与记录。
未退休s1/s2/writeback的FTQ身份不得被另一个请求重用；这不是对真实FTQ提交/释放流程的
整机验证，只是顶层环境所需的不混代约束。原生响应无tag，环境UID与epoch不虚构硬件标签。

### 严格编码与生产可达必须分开

`FetchRequest`明确为严格端口合同事务，`input_source=port-characterization`，不能单凭
opcode/数据正确获得生产可达credit。`ProducerFetchRequest`额外检查当前DefaultConfig
的FTQ32字节对齐/64字节窗口、5位endPosition、non-taken完整fall-through、页末截断、
双fetch同页/后继flag-value、backend/satp标记互斥、保留PBMT和翻译前后页内偏移。
false prediction仍然合法，不要求预测必须命中真正CFI。两种事务走同一驱动/采样/oracle，
不存在“端口域允许不比较”。producer类型也不证明实际BPU训练、PNR、iTLB/PMP或整机
活性；这些仍是caller/更高层合同。输入来源与peer来源分开保存，并沿carry传播，不能
用一个producer类型的后续请求把旧port-only低半或fake-resend晋升为完整生产历史。

生产者复核证伪了旧R-14的“已受真实FTQ约束”论证：原序列的短non-taken块不满足完整
fall-through长度。旧五条FAIL（其中R-14三条）全部保留，不扩大XFAIL；R-14目前只证明
端口合同域偏差，尚未证明同一错误生产可达。严格size/taken对照在两种高半字下都使用
正确FTQ(0,32)。此次合法对照还发现独立carry模型忽略完成槽taken与ISA类别，已按完整
指令语义修正，并保留冻结旧pred_taken=0答案在同一native观测上失败的控制；不能继续
声称本次`build_window` AST未改。`aligned_lanes`、`branch_info`和独立ISA/UncacheModel
算法未改，原刺激和判定的实际差分另行核验。详细反证见
[R-14当前证据边界](bugs/instr-boundary-carry-ftq-owner.md#后续生产者复核原可达性论证不充分)。

### 顶层最终语义审计与交付

`FetchRequest`不仅限制各字段位宽，还由`ifu/input_contract.py`从实际raw半字流独立重建
指令起始、宽度、PC/FTQ、预测和完整ISA属性，核验`Inst`数量/顺序、word/expanded、half/
count/截断等冗余描述。重建不调用`build_window`、`Boundary.predict`或读取DUT；carry
高半的声明低半仍须由agent绑定真实前序UID/PC。39个输入自检含1200窗口、手写固定答案
及19字段/4计数/序列错误控制；修复前28 FAIL保留为环境准入反例。

13个`Ifu.perfEvents`按公开`HasPerfEvents`的两个`RegNext`延迟比较，不是累计计数器。
`model/fetch_events.py`从接受时的hit/double-line元数据和实际IBuffer fire独立分类；两个
采样阶段全部字段均比较。8种固定hit/double组合、held期间改变live元数据、checker
redirect，以及26个字段/阶段错误注入区分通过。事件寄存器无reset，短reset不能把历史
管道归零或把旧held UID算成新enqueue；finish也必须排完已知事件尾部，一拍预算不足
明确失败。原“仅采样”检查点保留其当时边界，不据新结果改写旧收据。

追加同拍bus fire/reply与取消、uncache完成取消年轻stage/offer、producer活跃身份半环
年龄/回绕及carry取消原因历史。完整725项为719 PASS/5 FAIL/1 UNCERTAIN，原643项无
移除/判定变化，新增82项全部PASS。seed2定向278 PASS/1 FAIL/1 UNCERTAIN；两个运行的
源码逐文件匹配，七个build收据及42个native构建输入逐文件核验不变，完整产物各15/3个
均匹配manifest哈希。481/202个覆盖输入已按收据合并后清理，不能冒称原始输入仍可用。
这些完整性检查不等于硬件通过或覆盖闭环，证据见
[最终语义记录](../../../../docs/history/transaction-goal-ifu-top-semantic-20261101.json)。

`ifu-adapters`已移交；其他前端、MemBlock/VAGQ及最终全仓门禁/回归/当前包与资产审计
继续保持必需，不据本工程静态清零关闭整体目标。

最新运行、差分和源文件哈希登记在仓库
[活动目标记录](../../../../docs/lessons/transaction-goal-20261101.md)；真实R-13/R-14 FAIL
及carry UNCERTAIN不通过修改模型或扩大豁免消除。
