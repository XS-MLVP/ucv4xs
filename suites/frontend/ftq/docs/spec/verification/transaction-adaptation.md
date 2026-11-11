# FTQ 事务迁移复核（当前适配范围已核验，2026-11-08）

本页适用于`public-a0c2a26cb`、完整DefaultConfig闭包的`Ftq`、`ResolveQueue`和
`CommitQueue`。当前适配范围已由新基线记录的源码/seed收据核验；以下保留分阶段
实施与历史待办，不把旧绿色或本次适配结论等同硬件全通过/覆盖闭环/全仓完成。
2026-11-02及更早章节的数值、源码哈希和结论仍归`public-893e1580b`历史，不重标。

## a0c2a26cb 新基线边界（2026-11-08）

新基线相对`893e1580b`只改动了`Ftq`顶层：`4b9f938b7`（#6691）新增8槽软件预取
队列、3个`softPrefetch`输入和`PrefetchSource`；`b716aade5`（#6751）把
`FrontendRedirect.pc`扩为51位、cfiPc半字投影扩为50位。`ResolveQueue`与
`CommitQueue`的Scala/生成RTL逐字节不变，其槽位、容量、合并、过滤、取消和身份
合同继续按本页后文执行；两个容量XFAIL仍是真实RTL缺陷。

顶层固定ABI现为**439个非clock输入、470个输出**（metadata仍329项）。新增：
3个`io_softPrefetch_*`（`valid`+50位`vaddr`）、两个prefetch `source_value`；
redirect pc 51位、cfiPc 50位。`FtqInput`的`soft_prefetch`三槽和
`PrefetchStore`按以下合同检查：

- 队列8槽保留1槽，实际最多7项；3个LDU端口按序入队，`ready`不回压，超容量
  或超端口静默丢弃；同拍出队不能把已被沿前容量拒绝的输入追认为接受。
- 选择顺序为FDIP双发 > FDIP+队列混合双发 > 队列（FDIP不可用或`pfPtr-fetchPtr>2`）
  > FDIP单发；队列单发不推进`pfPtr`，混合推进1，FDIP双发推进2。
- 队列请求`source=Sw`、`startVAddr=PcInit(vaddr).signGuard`的半字坐标，
  `nextLineVAddr/isCrossLine/vSetIdx[1]`为0；输出`ftqIdx`是当前`pfPtr`标签，
  不是软件预取输入UID。队列项身份在入队时由输入建立。
- `reset`异步清空队列；reset有效沿上的新软件预取不建立offer。完整两阶段采样、
  取消/收尾和粘滞错误规则不变。

当前完整回归为**931 PASS/2 XFAIL**（933 nodeid，seed2/seed1、2 workers，源码
`4462a4b8…`）。旧907 nodeid删除0、判定变化0，新增26项全部PASS。逐DUT行覆盖
均100%；分支剩余**6个计数 / 4个distinct初始化reset else**（leaf与Ftq闭包重复计）；
原先的3个顶层IFU合并mux臂已由`test_ftq_ifu_backend_merge.py`用合法序列覆盖，
旧“结构不可达”结论撤回；toggle ftq 128620/152622。RQ-011经只读追踪判定
**可达**（每拍3 backend + 1 IFU，入口可背压保持），两个strict XFAIL与
`--runxfail`真实FAIL保留。详细RTL差分、逐nodeid对账、覆盖归因和`--runxfail`证据见
[新基线适配记录](reports/baseline-adaptation-a0c2a26cb.md)、
[RQ-011缺陷记录](../../bugs/open/resolve-queue-branch-overflow.md)与
[机器记录](../../../../../../docs/history/ftq-closeout-a0c2a26cb-20261108.json)。

## 已核验并修复的输入边界

- `CallRet`的`ptr`是6-bit FTQ pointer value，`ras`是完整2-bit action域（包括NONE和
  POP_PUSH）。只接受精确Python整数，不把bool/float/字符串转成原生整数。全部64×4
  组合是合法控制；非法数据和duck-typed对象须在编码前拒绝，不能先推进FIFO oracle。
- prediction override pointer、metadata身份、redirect身份、resolve字段与consumer
  controls使用显式整数域。拒绝未知字段和不合类型的数据，不根据truthiness接受。
- `Meta.fields`在事务建立时复制并只读化；调用方后续改原字典不能改变已提交请求。
  这不意味着任意metadata值都已证明完整生产可达；旧全位存储压力仍是端口域测试。
- `Pins.set`先核验**整个**beat的逻辑键、输入方向、精确整数和实际宽度，再写任何一个
  信号。不能先拉高valid，遇到后面的未知键/越界后才抛错。合法全宽边界不被收窄。
  实际宽度检查还不等于按需求独立认证完整schema，后者继续保留为逐DUT义务。
- 引脚claim整组预检后才登记；两个driver标签相同不能被当作同一个物理owner，重复
  物理别名及与已占引脚冲突都拒绝，且失败不留下前面空闲引脚的半组claim。该registry
  修复不等于已经把手动driver迁为SDK Driver，生命周期/重绑还须随运行环境一起审计。

### 地址坐标必须按通道区分

当前leaf API保留原计划激励的实际数值，不在迁移时暗改输入：

| 输入 | 实际字段合同 | 当前事务含义 |
|---|---|---|
| BPU prediction.startPc | `GuardedPc.addr`，50-bit | 带guard/overflow位的半字坐标；不是未经转换的50-bit字节PC |
| Backend/IFU resolve.pc/target | `Pc.addr`，49-bit | 半字坐标，构造器拒绝第50位，驱动不截断 |
| Backend/IFU redirect.pc | 50-bit `VAddrBits` UInt | 字节地址 |
| Backend/IFU redirect.target | 51-bit `GuardedVAddrBits` UInt | 带guard/overflow位的字节目标；转成公开BPU恢复的50-bit GuardedPc.addr时才去掉低位 |
| Commit pointer value | 6-bit | 队列身份，不是地址 |

`frontend/PrunedAddr.scala::Pc/GuardedPc`、`frontend/ftq/Bundles.scala`和实际三个DUT的
`signals.json`共同限定此投影。旧文档统称“50位地址”的表述不能充当逐字段编码合同。
目前仍须继续完整producer关联、FTQ epoch/年龄及最高位组合审计，不能把这份ABI说明
当作完整程序可达性证明。byte/halfword不同的字段不能通过返回数据猜单位或补身份。

DefaultConfig ICache的cache line实际为64**字节**，fetch block为64字节、32字节
half-align；旧责任边界文档把半字坐标差`+0x20`误写成32B cache line，现纠正。
`GuardedPc.addr + 0x20`对应64字节的next line，而不是32字节；position对齐仍是
32字节half-align的低4位半字偏移。依据`icache/Parameters.scala`及
`ICacheCacheLineHelper::useHalfAlignFastPath/isCrossLine`，不能因旧低位样本正常
就混用原生半字数值和字节几何。原功能激励与断言数值未更改。
后续比较器可用区分性固定向量：`startPc.addr=0x10/endPosition=31`的字节起点是0x20，
nextLine.addr应为0x30；以32字节half-align算末半字在0x5e，因此跨64字节line，8字节
bank的两个mask应为`0xf0/0x0f`。这是独立字节区间推导，不是读取DUT得到expected，
最初只作为后续请求比较器的依据；现已接入`checker/requests.py`，原生case矩阵也经
双阶段自动比较。纯固定向量仍不单独计为原生功能credit。

后续顶层全ABI复核纠正了本页初版把redirect.pc/target都称50-bit的错误：
`FrontendRedirect`明确pc为`VAddrBits`、target为`GuardedVAddrBits`。旧构造器错误拒绝
合法target第51位，现按真实51位范围验收并保留pc越界与target第52位拒绝控制；不能
因为旧样本只用了低位目标，就把它误列成合法域收紧。高位对照是端口/投影控制，不
据此声称所有guard overflow组合均有真实producer历史。

## Ftq 顶层固定ABI复核（协议迁移仍进行中）

`testbenches/ftq/env/bundle/abi.py`按DefaultConfig与明确类型/向量形状建立439个非clock输入、470个输出
及clock的固定宽度/方向集合。其中329个BPU metadata输入由PHR、RAS、HR、ITTAGE、
MainBTB两bank×(4way+victim)、10路SC/TAGE等明确字段模板构造，不从live端口扫描
生成expected。未知/缺失字段、增加一个metadata输入也失败，不能静默解释为新DCE。

`TwoPrefetchCase`是允许零Conflict的4-bit one-hot（值1/2/4/8），不是2-bit二进制；
`bankSel`是8-bit DataBanks掩码，不是1-bit选择。对照`frontend/TwoFetch.scala`、
`frontend/ftq/Bundles.scala`和ICache `Parameters::DataBanks`，不能只按名字猜宽度。
单bit在signals.json有High/Low简写，物理SDK仍是1-bit；expected使用显式1而非零位。

固定ABI只证明传输形状，不证明metadata已在自动checker中完整比较。该版本完整回归
322 PASS/2 XFAIL，前287项无删除/判定变化，新增37项均selftest；修前8条输入控制
FAIL与修后同源码ABI结果见[机器证据](../../../../../../docs/history/transaction-goal-ftq-top-abi-20261102.json)。
后续SDK/完整协议迁移不能冒用这批较早源码的证据。

### 顶层整槽输入迁移（当时的输入边界检查点，不是完整协议完成）

`FtqInput`冻结全部producer、consumer及reset。`FtqInputPorts`按固定ABI一次编码
完整439输入；SDK `FtqInputDriver`唯一拥有所有输入，消除各旧Pulse/LevelDriver分别
写共享s3 pointer的机制。匹配的s3 override/meta可同拍组合，不匹配身份必须在任何
写入前整组拒绝；不能通过静默覆盖pointer把其中一笔改名。多lane/多组stream也先整组
验证，避免先执行合法前缀再因末尾非法报错。

保留显式`offer/drive_*`组合预览，不在预览返回时记接受；`step(N)`的每个沿分别以
真实SDK event核验沿前/沿后全部输入，记录`epoch/slot/tick`及原不可变计划。相同
payload的三个有效沿是三个input slot，不能折成一次；这些收据**不是**逐通道accepted
或completed账本。`Execution.paused()`及双阶段lossless观察保持不变。

自建`SyncDriver._drive_one`而非直接SingleCycle模板的原因：原协议API允许多通道在
下一沿前组合、保持Valid-only源到显式release，并在不走沿的阶段观察redirect/override。
SDK仍负责独占与活动send，工程只补整槽时序；不建立另一套ownership/clock scheduler。
取消后撤销payload只作物理清理，可能已发生的edge不能据此标完成或合法取消。

训练与redirect快照扩为完整公开metadata，训练保留真实branch valid mask；prefetch/
fetch两lane完整公开字段、IFU s3 flush identity及BPU指针/ready一并进入既有双阶段
观察。valid=0的未定义payload仍不授予功能credit，metadata值不用于猜输入UID。

本整槽检查点的`finish`当时仅审计输入已解除、无活动send、无粘滞失败；后续正在按
下节接入commit自主消费的有界尾部，但**尚不证明训练/取消/重试等其余协议义务已偿还**。
该函数的存在与原功能回归通过不能签核顶层；完整自动比较和逐通道生命周期继续是
下列必需任务。

该整槽检查点完整354 PASS/2 XFAIL、同源码seed1定向145 PASS、根242 PASS，原324项
判定不变，新32项selftest。7/5个完整/seed1覆盖产物与182/94个原生输入构建凭据核验，
仅表示产物完整，不是覆盖闭环；47874项collection的初始/前序集合均无删除/顺序变化，
见[整槽收据](../../../../../../docs/history/transaction-goal-ftq-top-slots-20261102.json)。

后续6条独立red又证实`PredictionSpec`仍引用可变metadata、没有严格构造检查，
`allocate`也未在改变消费者/执行第一笔前验证后面的完整plan。现补Spec冻结、固定metadata
域、全plan预检和显式wrap identity；沿原各笔prediction→meta时序执行，不删除旧激励。
另外2条red揭露直接构造的metadata记录仍可变：正常SamplingMonitor路径已freeze，但
ahead匹配时`drive_backend_redirect`组合预览绕过该层，必须把记录本身只读化并复用decoder
view。独立8条控制修后PASS，完整最终回归另记，不能重标前一整槽源码。

### 顶层 callret → BPU commit 协议（当前子链已核验）

新的三条真实原生负控制在完整输出采样之上分别隐藏commit、翻转RAS action或SSP，
原顶层均未自动报错；修前3 FAIL留在`results/ucv-goal-ftq-commit-lifecycle-red-20261102`。
这不是缺少decoder，而是缺少**从输入到输出的自动比较与完成账本**。

现`testbenches/ftq/checker/commit.py::FtqCommits`复用既有独立`CallRetFifo`算法与SDK Scoreboard，
旁置环境`(epoch,slot,lane)`UID。每次顶层受检slot都比较沿前旧队首与沿后新队首，
两阶段输出不再由功能体是否读取决定。equal payload保持独立输入祖先；FIFO顺序决定
当前UID，输出无FTQ tag，不从SSP/TOSW/RAS或返回值猜身份。完整commit metadata期望
来自已核验物理输入的meta写入历史，不从内部metaQueue读数反推。

- NONE过滤、沿前56项guard整组拒绝、正常完成、reset取消及pending分别对账。沿后
  新队首只是预览，下一沿前的旧队首在该沿完成；同拍出队不能追溯降低准入门限。
- reset有效时的callret lane不建立新的FIFO offer（reset优先），但物理input slot仍完整
  保存。不能把这个resettable通道的规则套到后述无复位metadata store。
- 当前FIFO没有响应ready，队首自主消费。因此finish可仅送有界idle等待它排空，再
  核验两个空尾槽；不能补callret、ROB commit、meta、ready、redirect、response或reset。
  原明确consumer levels保持不变；整个Ftq的其他队列仍未获完整收尾信用。
- metaQueueCommit是`Reg`而非RegInit，实际`FtqDut.v`在独立`always @(posedge clock)`
  中按meta.valid写，不随异步reset清零。未知初始image绝不能填0：只核验valid/action，
  把该UID列在`unknown_metadata`；写过完整meta槽后其三个commit字段都应完整比较。
  这类未初始化来源是明确端口压力，不声称完成producer来源证明。
- 已知metadata的环境UID和输入flag/value随image保留；完成账本记录当时对应的meta
  祖先。reset只取消FIFO旧epoch，不抹掉无复位存储历史。行号/UID不是硬件tag。
- 同拍metadata写只能影响沿后队首读数；当沿已消费的旧队首绑定沿前旧image。公开
  checker的错误、自动比较错误、预算耗尽及账本删改/吞错均粘滞，reset不能洗掉失败。

新增纯/原生控制验证上述阶段、相同payload、整lane重复offer、容量、取消后重用、
错误字段/错metadata来源、最后输出隐藏、吞错和有界finish；Python观察/expected注入
只计selftest，不冒充RTL mutation。初版模型的额外纯red发现reset槽有效meta写被遗漏，
当时待修：无复位store在reset有效沿仍写入，不能把“reset清FIFO”扩大成“丢弃meta输入”。
该边界有源码与真实闭包依据，不以seed碰巧为0建立答案。后续源码已将有效meta写从FIFO
reset分支移出，同一个纯探针修后PASS，并补原生reset有效沿写入及后续来源对照；最终
完整回归为410 PASS/2 XFAIL，同源码seed1定向146 PASS、根242 PASS；原356项判定不变，
新增20个allocation/快照与36个commit协议控制均为selftest。全仓47930项收集保留初始
45883和前47874的集合/相对顺序，十任务exit0。构建与7/3个覆盖产物、218/111个原生输入
凭据已核验，raw覆盖输入未保留，合并产物完整不等于覆盖闭环。

首版commit接线完整404 PASS/2 XFAIL、同源码seed1 140 PASS，只属于此前源码检查点。
额外五条native控制分别改错backend write、prefetch/fetch owner、training PC或redirect
target，全部因“未自动抛错”FAIL，证明其他通道还缺逐输入自动比较；不是setup偶然
失败。它们是明确下一必需项，不能把commit绿色外推给全部Ftq；证据见
[顶层commit机器记录](../../../../../../docs/history/transaction-goal-ftq-top-commit-20261102.json)。

### 组合协议的阶段/身份边界

下面是已核对producer与顶层合同的实施约束。后续实际接线与验证边界见
[五通道组合检查](#五通道组合检查当前实现)，不能仅据此表取得checker信用：

| 通道 | 输入建立的身份及阶段 | 必须保留的区分 |
|---|---|---|
| prediction → backend PC write/entry | 规划offer UID与本地owner序列；公开bpuPtr只作比较 | `ready && valid`物理fire与redirect门控后的有效写分开；override可在ready=0写入，s3优先 |
| metadata → 三组存储 | 同一输入plan的s3 flag/value及metadata UID | meta端口valid即写，公开ready已DCE；共享s3不能被两个producer分别改写；未初始化meta不能补为已知0 |
| prefetch/fetch | 从已分配entry的本地owner/代次取得UID | 两lane预览与实际fire分开，prefetch case和consumer realTwoFetch不同；override造成重发不能冒充新分配 |
| backend redirect | 本拍input和上一拍ahead plan | ahead匹配允许组合生效，否则延一拍；同拍真实redirect压过ahead预告，不能仅按返回PC选祖先 |
| IFU redirect/resolve | 原IFU输入UID注册到下一槽 | backend优先，IFU return target来自已存输入RAS metadata，canTrain只控制resolve；redirect和resolve是同一输入的不同义务 |
| resolve → train cache → BPU | 原report UID及entry的first-owner/合并序列 | 队列接受、交付cache、公开ready消费是三阶段；完整mask按首误预测的位置裁剪，不能按压缩后数目猜槽 |
| callret → BPU commit | 原lane UID及FIFO顺序，meta由输入ptr指定 | valid-only每沿分别offer，NONE/guard拒绝不算accepted；沿后可见不算当沿完成 |
| ROB commit | 明确commit输入的flag/value与本地年龄 | 同指针可反复报告，第一次后逐项追赶；重复报告不能重复退休同owner |

依据为现有TOP-002..017功能合同，以及当前`Bpu.scala`的s1 ready/fire、s3 valid/meta和
共同s3 pointer；顶层两个redirect receiver说明ahead/一拍注册的transport边界。
生产者历史与端口域压力仍需分开：原metadata全位写和部分只分配不发meta的序列不能
自动声称完整BPU流水可达。默认未初始化的存储无复位保证，不能用seed碰巧为0填oracle。
后续完成审计必须把该表每一行连接到实际checker和正反控制，只有文档表不算修复。

后续receiver阶段核对还发现：不能把“导出异步reset”扩成“所有transport寄存器都复位”。
`BackendRedirectReceiver`的ahead/redirect、`IfuRedirectReceiver`的redirect以及redirect
metadata read都是无init的RegNext；真实`FtqDut.v`的`ftqIdxAheadNext_valid`、
`redirectReg_valid`、`ifuRedirect_valid`在无reset的clock块更新。相反IFU resolve是
`RegNext(resolve, init=0...)`。新reset epoch的第一个沿前可能仍看到旧redirect transport
预览，不能据此判正常完成，也不能在model里凭空补成0；有效输入经过真实边界后才归零。

还须分开IFU两个义务：本拍新backend输入没有ahead时延一拍，IFU输入可能在当拍获准
注册；下一拍backend在redirect仲裁中赢，并不自动抹掉已经注册的IFU resolve。
`/tmp/opencode/ftq_redirect_schedule.py`及六个纯控制已验证这一输入日程原型（包括ahead
匹配立即生效、非匹配延迟、相同backend beat不合并身份、resettable/非resettable分离），
在当时尚未接入agent。现接入`checker/redirect.py`，原生ahead/非ahead及元数据
转发在73项定向中通过，逐UID取消/resolve子链的新控制仍须以各自最终收据核验。

### 五通道组合检查（当前实现）

`FtqFrontend`现将本地BPU/PNR/PF/FETCH/ROB owner、预测存储、metadata输入image、
redirect receiver、ResolveQueue和trainCache组合。所有输入先与完整439字段快照核对，
然后比较同一slot的DriveStable旧状态；统一推进模型后比较RisingEdge新状态。
`ftq.owners`另外比较全部内部pointer投影，内部读数只作actual，不用来发现expected owner。
显式组合预览也调用同一比较入口，但不产生输入接受或输出消费。

| 合同/通道 | 当前检查入口 | 身份、有效域及终态 |
|---|---|---|
| TOP-002/003/007/008，prediction/backend write | `frontend.py::controls/check_phase/advance_slot` | staging revision建立offer UID；ready=0保持同UID，多拍retry分别登记；每个真实接受沿后的继续valid形成下一笔。物理ready/fire、redirect抑制、override写入分开记录。override保留原allocation root并建立revision/parent，不把同PC等同同输入 |
| TOP-004..009/012，prefetch/fetch | `requests.py`、`handoffs.py::RequestHandoffs` | 用已安装输入和本地pointer生成两lane全部payload/owner，64B line与8B bank按独立字节区间求解；case/second eligibility、异常/satp、实际realTwoFetch消费子集分别检查。每次offer/保持/交接/回卷重试有独立attempt，retry_of由输入allocation root确定 |
| TOP-010/011，redirect | `redirect.py::RedirectSchedule` | ahead匹配当拍生效，其他backend延一拍；每个有效输入沿有独立UID。接收时backend门控与下一拍仲裁分别处理，记录applied、backend-blocked、backend-arbitration-cancelled及reset-suppressed-application |
| IFU redirect→resolve | receiver `resolve_done/resolve_children`及`TrainingPath` | redirect与canTrain后的resolve是两个义务。已注册的IFU resolve不会因下一拍backend仲裁优先而消失；child UID必须出现在训练输入账本中。return target绑定接收时RAS输入image，不用后来meta写入或公开target反推 |
| TOP-015/016，resolve→cache→BPU | `training.py::TrainingPath` | 过滤/沿前容量/8槽安全前缀/first-owner/三slot grace沿用已核验leaf合同；队列交付cache和公开ready消费分开。完整branch mask由最早mispredict的**位置**裁剪，不是压缩后lane序；每个原report保留完成、mask过滤、reset/redirect/overwrite取消或pending |
| TOP-013，ROB commit | `handoffs.py::RobTargets`及`ftq.owners` | 每个输入沿记录target UID；逐项追赶与重复旧target分别对账；每个退休沿绑定当时held target及已知输入allocation。pointer value/flag绕回不是新的硬件tag；跨完整两圈仍保留不同输入祖先 |
| TOP-017/018，metadata/topdown | `frontend.py::check_phase`、receiver/cache metadata UID | 训练与redirect完整公开meta逐字段比较，已知image绑定meta输入UID；同步读、cache抓取和同拍写次序分别保留，跨reset不抹无复位存储。未知初值列入unknown，不因seed碰巧为0而补零。topdown只比较合同有效的backend分类及所有保留reason位 |

框架仍使用SDK Driver、lossless SamplingMonitor和Scoreboard；没有另外运行一个时钟或
替换框架的资源所有权。非消费式decoder view、组合预览、跨通道UID账本和特定协议的
cancel/merge规则是工程侧补充，SDK的通用一对一响应匹配不能代替这些多义务转换。

#### 收尾信用限于真实协议

`finish`只发送解除后的idle输入，保持原消费者levels，不添加ready、meta、ROB commit、
callret、resolve、redirect或reset。它有界等待无ready的commit自主消费、已给train ready
的训练报告、receiver transport和已给ROB target的逐项追赶，并检查两个完整安静尾槽。
train ready=0而尚有已接受report或已注册IFU resolve时立即要求用例显式`drain_training()`；
不能在fixture内偷偷升ready或以reset清债。预算耗尽、错误被吞或账本被删改均粘滞。

没有消费许可的prefetch/fetch **unaccepted offer**可以仍然有效，收据明确列在
`requests.pending_offers`，不能冒称已接受/完成，也不强加“全机必须退休所有预测”的
虚构保证。消费者交接的完成只表示Ftq职责边界，不表示ICache响应、指令执行或ROB退休。
已接受训练、已生效receiver或已给出的ROB target则不能凭关闭monitor或清空view算完成。

#### 首轮差异及修正依据

首版完整`ucv-goal-ftq-frontend-composition-v1-20261102`为418 PASS/4 FAIL/11 ERROR/
2 XFAIL，源码685256e...稳定；5条原生错误观察均已被自动路径区分。该记录不改写：

- 两条commit压力用例在没有fetch消费时推进commit，属于端口刻画，不能说是真实ROB
  生产可达。`CircularQueuePtr::distanceBetween`的同flag分支先用6-bit减法再扩成7-bit，
  `0-1=63`、`0-2=62`；首版错误用统一mod128。现按明确位宽保留旧压力，合法队列年龄
  仍是非负距离；不缩窄输入或把这种反向顺序晋升成整机合同。
- 两个原IFU合并用例把backend半字PC与IFU字节PC填成同一个数，实际对应不同起点。
  现在仅将其中三个IFU构造位置作`pc=2*pc`，所有报告/lane/slot、目标和原断言保留。
  未改first-owner oracle为last-writer迎合RTL；旧物理激励变化明确记录，不声称字节不变。
- 11个teardown ERROR来自5个原功能体末尾仍有未消费训练。仅在全部原断言之后追加
  显式`drain_training()`，不改变其主激励/判定，不能由fixture自动补ready。

修正后的定向`ucv-goal-ftq-frontend-composition-directed-v2-20261102`为73 PASS，源码
dbb8d7c...稳定且当时逐文件匹配。随后新增447个逐字段纯比较控制（包括2个固定合法向量）
及UID/重试/metadata来源/尾部控制，后续最终完整、多seed与差分见下节。纯字段翻转仅
证明比较路径，原生Python观察注入也不是RTL mutation；不能据此宣称覆盖闭环或整个
前端、全仓目标完成。

#### 最终源码验收与剩余边界

最后完整`ucv-goal-ftq-frontend-integrated-v4-20261102`为**905 PASS/2 XFAIL**，同源码
seed1定向`ucv-goal-ftq-frontend-seed1-v4-20261102`为**122 PASS**；两者源码均为
0964e566...，前后稳定并逐文件匹配。前412项判定保持，新增495项均selftest。v3的
903 PASS/1 FAIL/2 XFAIL唯一失败是旧自检仍固定通道数9；现比较完整固定10通道集合，
含新的owner通道，而不是放宽计数。五个collected错误注入改为指定ScoreboardMismatch，
避免被训练未排空的通用finish AssertionError假救活；新增原生控制核验reset时旧非复位
redirect transport仍被检查，但其应用记reset-suppressed，已注册IFU resolve精确取消。

完整/seed1的7/5个覆盖产物、236/91个原生输入及全部构建文件哈希已核验，native未重建；
manifest committed/coverage_complete/cleanup_complete均真。原始覆盖输入未保留，产物
完整不等于覆盖闭环。十工程v3收集48424项保留初始45883及前47930的集合/相对顺序、
十任务exit0；最后Ftq单工程收集907项与v4源码相符。随后BPU继续修改，不能拼造一个
未执行的新全仓收集哈希。collect-only的CLI exit1还来自NOT_RUN硬件判定，不是收集错误。

当前三个DUT的事务迁移范围闭合；ResolveQueue两条安全容量XFAIL仍是真实硬件缺陷，
未删除或扩大豁免。完整BPU/ICache、MemBlock/VAGQ及全仓最终验收仍必需。逐项机器
证据见[顶层组合记录](../../../../../../docs/history/transaction-goal-ftq-top-frontend-20261102.json)。

## 实施前真实待迁移项（历史义务，不能借输入修复签核）

以下是当时主要适用于**Ftq顶层**的必需义务，现已由前述组合检查与最后源码收据逐项
实现/验证；两个leaf的单独完成曾不足以证明顶层，不能抹掉这些实施前反证。

1. 旧`harness.Dut.edge(cycles)`只在等待结束后调用一次自建observe，已由本轮的框架
   双阶段全通道采样链替换（见末节）；但逐协议fire/UID关联和完整比较仍未完成，不能
   把已采样的帧数当成完成/checked事务数。
2. Ftq顶层旧手动驱动（原`runtime/drivers/signal.py`，已在 schema2 迁移中按哈希清单移除）
   的引脚/edge路径现已在源码中改为SDK整槽driver，正在用唯一所有权/共享s3/取消/错误收据等
   控制核验；源代码接线不等于完整协议完成。
3. `aclose()`清空monitor记录不等于接受义务完成。需分别核验offered、accepted、训练/
   commit完成、重定向/复位取消及重试；无tag通道的环境UID在输入建立，不伪造硬件tag。
4. Ftq顶层还需在原用例承诺范围内显式有界排空、粘滞失败和检查链负控制。不得自动
   补commit/训练、flush或reset清债；也不能凭空要求合同允许过滤/拒绝的输入全部完成。
5. ResolveQueue两条容量XFAIL继续保留；新观察若揭露漏检，必须保存合法对照和真实失败，
   不扩大豁免。原有硬件结论、代码哈希和收集顺序分开对账。

## CommitQueue 逐沿事务链

### 真实协议与模型边界

- DefaultConfig为8条Valid-only commit lane、64个存储槽、8槽guard。没有请求ready，
  每个有效沿都是新offer；`ras=NONE`过滤，沿前深度达到56时本拍所有新call/ret合法拒绝。
  同拍出队释放的空间不能让已被沿前guard拒绝的输入被事后算接受。
- input slot建立`(epoch, slot, lane)`环境UID。线路没有此tag，payload相同的输入也不能
  合并。FIFO lane顺序和输入计划决定身份，不从返回ptr/ras或内部存储反推身份。
- 沿后新队头是**可见预览**，下一有效沿前的队头才在该沿被消费。分别比较沿前/沿后，
  避免把一次可见输出算两次完成。独立`CallRetFifo`保留原公开payload合同；旁置UID账本
  记录offered、eligible accepted、NONE过滤、容量拒绝、完成、reset取消和pending。
- 源码的隐式Reset在完整导出闭包中是**异步reset**，实际`CommitQueueDut.v`为
  `always @(posedge clock or posedge reset)`。因此reset驱动后第一DriveStable已须为空，
  不能按“同步reset沿前仍保留旧队头”建错oracle。取消终态的tick标记第一次受检reset
  边界，不冒称它是电气reset刚上升的精确时刻；完成与取消的UID集合严格分开。

### 输入、采样及收尾

| 层 | 实现/合同 |
|---|---|
| schema | `testbenches/commit_queue/env/bundle/ports.py`独立固定25个非clock输入、3个输出及clock的宽度/方向；缺项、额外输入/输出、几何不符立即拒绝 |
| driver | `CommitInputDriver`继承SDK `SyncSingleCycleDriver`，唯一拥有完整lane及reset；完整payload撤销、接受事件和取消清理沿用SDK |
| idle-time | `Execution.paused()`只约束显式输入槽之间的仿真时间；monitor一直订阅，不能靠关掉观察避开任务切换 |
| monitor | 两个SDK lossless `SamplingMonitor`分别在DriveStable和RisingEdge冻结完整输入/队头；逐拍取出、校验tick/相邻槽并统一推进参考 |
| checker | SDK `Scoreboard`比较真实输入、沿前旧队头、沿后新队头；UID模型对账独立于公开输出tag。自动及公开checker错误均粘滞 |
| finish | 只允许已解除的producer，有限预算内送idle并被动观察自主消费，再比较两个空尾槽。不能补call/ret、reset或任何功能响应清债 |
| close | 只释放SDK资源，保留账本；不是完成性证明。正文PASS/缺报告必须先finish，既有正文FAIL不重复虚增teardown ERROR，独立清理错误仍传播 |

`drive()`是准备下一显式输入槽；`step(N)`让其每个沿成为一个新Valid-only offer。
`release()`显式解除重复供给；`submit()`只提供一个输入槽并完整撤销。原八个功能用例的
主体、240轮随机流、lane×slot和全宽toggle程序均未删除或缩短；旧自检额外显式release。
`training()`返回最近受检的不可变沿后预览，不绕过monitor重新读live引脚。

`history/latest`仅为**已被逐拍检查后**的有界非消费式观察缓存，不替代lossless交付队列。
监视器消失/关闭、错payload、漏事件、重放tick、取消、未偿还完成或吞掉比较错误均不能
正常finish。注入位于Python观察/期望层，不计RTL mutation coverage。

## ResolveQueue/Ftq 持续观察链（不替代协议迁移）

共享harness现使用两个SDK lossless `SamplingMonitor`，分别冻结DriveStable和RisingEdge
的**全部输入、全部已注册通道**。采样回调不推进协议模型；成对快照交付后校验真实event、
相邻tick和完整通道名，再统一更新各decoder view。旧名`EdgeMonitor`现在只是明确的
非消费式decoder/cache，不拥有订阅或独立时钟循环。`InvariantMonitor`仍只在沿后运行
已说明的指针安全网，不给予功能credit。

等待N拍不再只采末拍；大等待按有界交付批次取出每拍快照，不增加覆盖输入容量来
掩盖丢帧。`Execution.paused()`在请求槽之间保持所有订阅开启，避免pytest任务切换
凭空产生ready/fire。`CycleSnapshot`嵌套字段、Topdown映射也复制并只读化；不接受
mutable dataclass/native view。canonical stream与有界history分开，后者只用于诊断。

早关phase monitor、删除/替换已注册channel、重放event或取消已发生的edge后未交付
都必须失败并粘滞；正常正文的环境退出检查sampling状态，不能由live组合读数回退成
通过。组合预览仍保留为显式阶段API，用于不走edge的offer/redirect检查；它不是接受
或完成证据。两DUT的driver/完整schema、输入UID、重试、合并/年龄、合法取消和有界
事务收尾原为两DUT的待办；ResolveQueue现按后文闭合此范围，Ftq顶层仍须实现，不能
据输入快照或持续采样签核顶层。

## ResolveQueue 协议迁移（当前实现）

当前实现接入一个SDK `SyncDriver`，独占全部resolve/reset/ready/redirect/enqueue
输入。每个`ResolveInput`冻结三条backend及一条IFU来源、控制和许可；混合来源整组
编码前校验，不能驱动完IFU后才因backend坏字段失败。原两拍pulse的计划次序保留，
统一SDK驱动整拍输入，已有共享双阶段采样在同一slot返回真实event。

旁置事务检查器以输入`(epoch,slot,source)`UID记录报告，不从Training.index/PC挑选
身份。条目序列按独立FIFO/合并合同维护；原`ResolveChecker`的公开纯参考仍供旧组合
用例使用，自动采样不靠用例主动调用它才触发。要核验的完成/取消语义包括：

- 后端correct direct/return过滤，IFU不受该过滤；16槽/4guard的**沿前**capacity拒绝
  仍适用于IFU。IFU“always accepted”仅指不被backend语义过滤，不意味无限容量。
- 同拍按backend0/1/2/IFU来源顺序追加，最多8个有效branch槽，`flag,value`是完整条目
  身份；旧八报告保持、超量丢弃的FTQ-RQ-011合同继续保留，不按当前RTL覆盖行为修改。
- 当前report更新同一队首时抑制本拍training，不能把尚在合并的分支集合提前完成；
  Ready仅消费沿前有效队首一次，长时间背压不是重复接受/完成。
- 后端redirect三slot grace窗口按环形年龄撤销旧entry，BPU overwrite只比较pointer
  value；取消后同value/flag的新entry有新的输入祖先。标flush与物理自动跳过分开。
- reset按当前异步导出边界取消准确旧epoch，不能抹除错误；输入出错或已发生edge后
  取消必须保留未对账状态，关闭driver不表示完成。
- `finish`不自动升ready。以前停在背压队首的七个旧功能体只在全部原断言之后追加
  显式`drain_all()`消费者计划，原主体、报告数量、随机种子、512组slot×来源扫描及
  XFAIL反例不删除或缩短。其余调用链仍须显式许可或取消，不能在fixture里自动清债。

完整源码的seed2当前回归为285 PASS/2 XFAIL，原230项判定保持，新57项均自检；
同源码seed1为105 PASS/2 XFAIL（含原CommitQueue与cycle控制），根242 PASS。额外
`--runxfail`得到2条真实FAIL，首因仍为slot7/slot0覆盖，不是setup或清理错误。源码/
构建/覆盖产物和47805项全仓收集已核验，见
[机器证据](../../../../../../docs/history/transaction-goal-ftq-resolve-transactions-20261102.json)。
本节不授予Ftq顶层通过，也不把完整采样本身当作协议信用，整体工程目标仍进行中。

### ResolveQueue 独立依据与检查映射

| 合同 | 输入/观察 | 自动checker与区分控制 |
|---|---|---|
| RQ-001/003：初始owner及startPc不被后续报告重新命名 | 输入flag/value/pc，完整Training身份/PC | `ResolveTransactions`按首次输入建entry；纯first-PC控制拒绝last-source改名，非法producer变体不冒称真实生产序列 |
| RQ-002：来源顺序、8槽前缀 | 0/1/2/IFU的offset/target/方向/属性，实际8-bit valid mask | 原lane/slot矩阵及独立UID序列，native指针/branch/mask错误注入；不只比较压缩后的branch数 |
| RQ-004/005/009：过滤与沿前容量 | source、branchType/mispredict/rasAction，ready前后的队首 | backend-filtered、capacity-rejected独立终态；IFU bypass过滤合法对照，满门限不被同拍出队事后降低 |
| RQ-006：允许合并、单次fire | 真实沿前Training、输入ready、同时报告 | 同entry合并抑制完成、不同entry入队与老队首完成同拍分别对账；重复held预览不计新完成 |
| RQ-007/008/010：取消边界 | 输入redirect/enqueue/reset、每拍完整队首 | 环形年龄独立顺序、旧报告取消、新相同payload/flag/value新UID；同拍已fire不能改标取消 |
| RQ-011：超8槽保留原8条 | 真实超量输入和完整branch前缀 | 安全合同不改变；两条旧strict XFAIL继续拒绝RTL覆盖。失败可提前到自动比较，不声称失败之后原断言已执行 |
| PC/branch坐标 | 输入49-bit半字Pc与5-bit offset | 32B块内半字偏移加offset，固定答案`pc.addr低4位15 + offset16 = position31`区分旧直接offset答案；不是运行时读RTL自证 |

基础合同来自本工程原`docs/spec/design/functional-points.md`的RQ-001..011以及已确认DefaultConfig
几何；49-bit Pc/32B align投影同时核对`frontend/PrunedAddr.scala`与BPU Helpers接口
定义，不引用实时DUT寄存器作payload期望。三slot redirect grace及相同entry更新时
暂不发training属于本leaf明确时序合同，不推广成整机issued分支都能被立即取消。
纯序列oracle、SDK采样检查和观察层注入各有信用边界；Python错误控制不计RTL mutation。

输入控制位于`testbenches/ftq/tests/checkers/test_commit_input_contract.py`和`test_input_atomicity.py`，
标为selftest，不计新增硬件功能点。当前完整回归与中间red按根`results/`新目录保存；
最终源码与机器记录核验后才能使用相应数值。结构/静态零命中不是以上语义任务的替代。
