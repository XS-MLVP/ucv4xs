# BPU Scala 交互语义审查与覆盖设计（2026-11-06）

> 2026-11-08已开始[后续验证侧实施](../verification/evidence/runs/closeout-20261108.md)，不是重开本轮已完成审查。
> owner静态债务24→0已有真实前后对账；INT041/059适配仅推进到下一层阻挡，尚不授予
> provider-role/alignment后续比较信用。本文下方11月6日的24债务及零新DUT运行是历史事实。

目标是确定**应检查的交互与场景**，不是依据 Scala 自证 RTL 正确。固定
`public-a0c2a26cb` / `a0c2a26cbe3c862175174bad03a1a23c406315ed` /
`DefaultConfig`；现场 Scala tracked worktree 干净，初始冻结117份来源哈希，核验输入
见 `/tmp/opencode/bpu-scala-interactions-20261106/initial.json`。原验证源码
`b753b48539922b5452eebc3400cfd993f4bb0117684a76115ede47eed0758cf4`，本轮不改变
RTL、工具、基线或历史判定。下文源码路径均相对 `XiangShan/`，行号属于此固定 commit。

## 证据层次

- **接口/producer合同**：字段来源、编码、单位、允许的输入与接纳关系。
- **实现观察**：Scala 实际仲裁、状态更新和时序；可用于找风险和设计区分样本，
  不能直接作为独立 golden。算法策略只有在既有合同/独立性质确认后才作为验收预期。
- **待确认**：存在语义歧义、完整 producer 前态未构造或观察字段被裁。记录缺口，
  不从 actual 选预期，不擅自修改模型得到全绿。

## 已追到的 producer 与父级交互

| 条款 | 固定 Scala 定位 | 核对结论 / 场景要求 |
|---|---|---|
| PC域与CFI末半字 | `frontend/PrunedAddr.scala:155-213`；`frontend/bpu/Helpers.scala:46-61,73-103`；`frontend/bpu/Bpu.scala:52,138-143` | resetVector是物理地址，不能直接用高virtual地址；GuardedPc保留额外位、消费点显式unGuard。FTQ offset指向末半字，非RVC的真实指令起始需减2字节；设计压缩/非压缩、跨align/页与guard/sign场景。 |
| 指令族与RAS hint | `frontend/bpu/Bundles.scala:41-146` | None/conditional只能用合法无栈动作；JAL/JALR由rd/rs链接寄存器区分push/pop/pop+push；`needIttage`是indirect且无pop，包含间接call，不只OtherIndirect。非法编码端口压力不得混入producer可达信用。 |
| NT真实target | `backend/fu/wrapper/BranchUnit.scala:26-29,73-82`；`frontend/ftq/ResolveQueue.scala:132-153` | 执行conditional NT带顺序后继及真实Conditional属性；不能把该target作为旧taken payload覆盖。属性纠正与方向学习需分开。 |
| 训练过滤与前缀 | `frontend/ftq/ResolveQueue.scala:51-66,86-98,157-177`；`frontend/ftq/Ftq.scala:405-453` | 正确direct和return的backend resolve被过滤；IFU canTrain纠正独立进入。FTQ按CFI位置屏蔽首个误预测后的分支，保留稀疏槽，不以槽号当执行顺序；训练原件被重用/年轻redirect的失效由FTQ资格约束。 |
| IFU纠正与重定向年龄 | `frontend/ifu/PredChecker.scala:128-184`；`frontend/ftq/IfuRedirectReceiver.scala:35-63`；`frontend/ftq/BackendRedirectReceiver.scala:28-52` | None假命中仍可有训练；backend压IFU，提前索引匹配走快路，不匹配延一拍读原metadata；return的IFU目标取该原件的specTopAddr。需核原FTQ索引/epoch，不能用最新Ras top补旧原件。 |
| RAS提交来源 | `frontend/ftq/CommitQueue.scala:43-65`；`frontend/ftq/Ftq.scala:504-521` | callRet队列保留动作次序并逐笔发布Valid；提交branchType是DontCare，真正资格来自rasAction及原commit meta。neutral/重复提交与真正的同返回地址多次调用不可合并；队列full丢入是FTQ域问题，不能套RAS反压。 |
| 启停传播 | `frontend/bpu/Bpu.scala:90-108` | CSR延2拍；UTAGE由ABTB使能，RAS/MicroRAS/TAGE/SC/ITTAGE还依赖MBTB。不能任意假设独立UTAGE CSR；关闭使用与在途副作用是否继续需到叶模块逐项核。 |
| fire/flush与输出 | `frontend/bpu/Bpu.scala:248-275,509-530`；`frontend/ftq/Ftq.scala:187-241` | 正常S1受prediction.ready；S2/S3继续排空、meta为每S3 valid发布，FTQ恒meta.ready。S2/S3 override在ready=0仍由FTQ特殊写入，不能当成一般必须保持到fire的普通响应；redirect清年轻，但同时有效的物理fire/Valid须按原件核对。 |
| S1选择反例 | `frontend/bpu/Bpu.scala:296-329,341-345` | 实现上ABTB只要有有效entry就遮住UBTB；ABTB全NT时走fallthrough，即使UBTB有taken。UTAGE只纠正conditional，最早taken按位置而非物理way选；需单列此控制，不简化为“ABTB有taken才优先”。 |
| S2/S3纠正 | `frontend/bpu/Bpu.scala:347-474` | S2比方向/位置/属性而**不比target**；仅目标差异留S3。S3比较first-taken身份及目标，S2已纠正时MBTB低目标比较被抑制，但ITTAGE/RAS仍比较对S2目标。覆盖target-only、方向/身份同时变化、S3压S2及无taken回退。 |
| 训练与恢复并行 | `frontend/bpu/Bpu.scala:158-198,224-229,562-613`；`frontend/ftq/Ftq.scala:410-453` | train.ready为全部predictor ready之AND；实际t0 fire才驱动学习。redirect不直接全局屏蔽train；合法旧原件可以和恢复同拍。fastTrain为s3_valid，不能先验认定所有redirect拍训练均被取消；投机取消、学习资格和提交是不同义务。 |
| PHR可见相位 | `frontend/bpu/history/phr/Phr.scala:47-108,139-198,264-346` | 普通预测/override有pending写与旁路，redirect即时物理写并控制新pending；s0逻辑fold、旧fold、s1/s2/s3祖先与训练原meta重建分别拥有。需连续redirect、override×pending、NT恢复、环回绕与训练并行，不能只读物理cell。 |
| CommonHR双拍恢复 | `frontend/bpu/history/commonhr/CommonHR.scala:88-211,255-305,315-405` | 位置去重后计算已执行conditional前缀；redirect当拍history valid=false，r1修复并补s1/s2，IMLI当拍按独立优先级更新。S2 override重用年轻S1原history，非当前S3结果。连续redirect、r1×新r0、S2×S3 fire/环指针需要区分；实现观察不关闭旧前缀FAIL。 |

## 叶模块的双向核对

下面把实现观察反查到既有行为族。算法预期仍取各模块的独立语义合同；“源码有此路径”
不等于预期已独立确认，更不等于该路径在真实DUT被检查。

| 行为族 | 固定 Scala 定位 | 观察、独立义务与必须拆开的场景 |
|---|---|---|
| `UBTB.lookup/confidence/lifecycle` | `frontend/bpu/ubtb/MicroBtb.scala:58-100,106-197` | 命中即taken，可靠性不是方向计数；resolve误预测压fastTrain，t0接纳后t1可在关闭时完成。查询与t1分配碰到原victim须当miss。另有父级直接用bits.taken而非valid的启停组合风险：静态leaf valid门控不能证明Bpu关闭资格。旧字节API/半字wire问题需按当前adapter另核，不沿用旧报告下结论。 |
| `ABTB.lookup/learn/residency/lifecycle` | `frontend/bpu/abtb/AheadBtb.scala:93-223,230-370`；`AheadBtbBank.scala:43-102` | 索引用当前S0历史、匹配用next PC；S2/S3 override分别重用两个年龄快照。fastTrain在t0要求原ABTB meta.valid；counter reset优先方向更新，训练touch与分配服务有独立年龄。NT不分配，但能惩罚原命中条件项；all-NT/后序/稀疏/类型纠正不可混成一格。多命中清理请求在普通写后服务；旧待写不同目的身份缺陷保留。 |
| `MBTB.lookup/learn/residency/service` | `frontend/bpu/mbtb/MainBtb.scala:73-188`；`MainBtbAlignBank.scala:138-218,248-399`；`MainBtbInternalBank.scala:85-272`；`VictimBtb.scala:89-224` | rawHit、窗口过滤后的valid、原第五槽暴露、现在victim驻留是四件事。conditional NT只学方向不写payload；None/NT仍能失效假命中。Main方向位置匹配路径未用rawHit的旧反例不能因新NT资格放行。Main/Victim及entry/counter服务分开，读压力与同拍snapshot/cleanup/迟到反馈须按原owner核全状态。 |
| `ITTAGE.select/region/service` | `frontend/bpu/ittage/Ittage.scala:155-168,217-307,309-416`；`IttageTable.scala:185-263`；`RegionWays.scala:51-90` | 仅唯一taken且indirect无pop可教目标，含indirect call；发布meta.valid却未见updateValid检查它，是既有未发布资格风险而非新放行。最长provider置信0可回退alternate，不能只比较selected target漏掉隐藏provider错误。非分配的零置信跨区重写及目录受害指针重新解释分开。useful维护只在无读/更新时推进，需有限公平释放，不能要求持续读下无条件完成。 |
| `UTAGE.select/learn/service` | `frontend/bpu/utage/MicroTage.scala:52-243,252-389`；`MicroTageTable.scala:70-133`；`BypassShadowBuffer.scala:99-268`；`Parameters.scala:23-35` | 仅纠正ABTB真实条件位置，index与tag来自不同相位；S2取A2、S3取A3重匹配，redirect清hit且次拍原ABTB结果不许训练。实际两表5/9历史：tick选择按table id、保护初始化按NumTables/2，不能从四表旧注释推相同维护域。连续同索引用最新版本旁路；强制写回使同bank读无效，应有明确miss/重试观察而非使用旧有效项。FastTrain局部单错误假设未获整机证明。 |
| `TAGE.select/learn/service` | `frontend/bpu/tage/Tage.scala:96-189,210-255,371-460,489-658`；`TageTable.scala:118-219` | 最长/次长与base回退分开；fastTaken是provider候选，不是最后weak-provider选择，S2/S3可能因方向而纠正。训练原MBTB身份和条件资格；meta-only与重新读表两条路径不同，同bank需读才反压。分配只在更长合法候选，随机筛选空时回退；同选择器先净票再饱和。useful扫表与entry方向存储分离，扫表清useful队列而不能清tag/方向；迁移后陈旧way的XFAIL不关闭。 |
| `SC.select/weights/threshold` | `frontend/bpu/sc/Sc.scala:151-218,241-338,375-423,487-610,615-692`；`Helpers.scala:49-94`；`ScTable.scala:79-126` | provider存在≠TAGE最终采用provider，SC bias用原provider方向/置信，非finalTaken；只合格条件Main命中可用。CommonHR无效时global/bw不读、不训练，预测改用零权重占位；`getPercsum=2w+1`使其仍有常量正票，不能说总贡献为0，策略预期待独立确认。path/imli/bias并非全部关闭。严格正负阈值；同特征净票先聚合；阈值越界整步拒绝而非夹紧。阈值t1更新与权重t2入待写/实际服务分离，须查邻居及fresh消费者。 |
| `RAS.stack/recovery/retire` | `frontend/bpu/ras/Ras.scala:63-113`；`RasStack.scala:89-171,173-325,333-422`；`frontend/bpu/Bundles.scala:56-64` | 地址是末半字后+2字节；真实checkpoint恢复重做并压年轻动作，commit和spec不同寿命。nearOverflow不是接口ready，操作被抑制不能算push完成。isCall/isReturn是排他的Push/Pop，PopAndPush不等于两者同时，保留组合动作旧FAIL。另需核spec.pushValid未直接与enable/fire合取导致的leaf启停风险；不得因fire=0假设全部child写无副作用。 |
| `URAS.stack/recovery/enable` | `frontend/bpu/ras/MicroRas.scala:81-146,153-246`；`frontend/bpu/Bpu.scala:198-222,321-329` | 用老到年轻的已知深度归约，不复制mux作golden；未知前驱只判不可用，不能断言无效target。中性S2修正须保留老CALL；S3/redirect取消年轻效果且观察撤回后不复活。leaf无enable门控，父级消费也需核；旧URAS-017的普通FAIL保留。PopAndPush资格与主RAS相同仍有旧反例，不能由普通CALL/RET替代。 |

### 仍需独立确认的需求与准入边界

1. **启停切点**：各模块采样enable相位不同；在途已接纳服务与关闭后新学必须分开。
   UBTB、RAS、MicroRAS的上述接线是风险定位，不是本轮新原生缺陷判定。
2. **FastTrain可达域**：一个S3选择并不自动保证早级ABTB/MicroTAGE只有一个相对错误。
   真实多早级错误、全NT指导及相邻redirect的完整前史先记录待确认，不删场景。
3. **资源公平性**：WriteBuffer无通用ready；有界dirty范围内的保留服务与超容量政策分别核。
   持续读阻挡的活性只有在合同声明有限释放后才可要求，不能用无限队列模型误杀有界硬件。
4. **真实生产者身份**：对外原件寿命由FTQ队列资格保证，不因端口容许陈旧数值就自动合法。
   快照发布、训练资格、redirect checkpoint及commit metadata分别追踪；完整IFU/FTQ组合未证。
5. **地址与配置**：新DefaultConfig有两表MicroTAGE、八表TAGE/SC、四way Main及第五槽；
   旧MinimalConfig的物理维度、tick/保护关系或字节API结论均需从当前适配器单独验证。

## 有界覆盖设计与实际检查

[覆盖设计](../verification/coverage/behavior-coverage-design.json)是本轮场景要求的权威记录，
[原场景证据记录](../verification/functional/behavior-scenarios.json)只保存真正已映射的3条MainBTB样例，
不重复维护另一份PASS表。设计以行为分组继承共同的准入/观察/完成义务，每条case再
明确前态、事件、结果域、预期/待确认、禁止副作用、合法/错误规则对照和下一实验。

| 范围 | 本轮交付 | 不能推出的结论 |
|---|---|---|
| 逐族源码对照 | 十DUT、33个已登记行为族均有具体Scala范围/锚点及独立合同入口 | 不等于33族所有策略已获独立规格确认 |
| 代表分区 | 78条，58条引用既有模块合同性质、20条明确待确认 | 全部继承`unmapped/none`，没有新运行或自动继承旧用例PASS |
| 维度反查 | 每DUT对source/state/identity/address/capacity/timing/lifecycle/outcome给具体case入口 | 不是八维全组合或状态空间穷尽，也不以位置/seed复制增加语义类 |
| 联合交互 | 11条高风险交互，分别声明联合前态/事件、预期或待核、禁止副作用、观察、控制和下一实验 | 单模块旧结果不能相加变成交叉通过；全部仍待确认/实验 |
| 无旧ID候选 | 父子派生enable在途边界、SC无效历史的常量占位票 | 不为清单整齐删需求，不先给旧ID/新PASS或称新RTL缺陷 |

实际执行：

- `tests/framework/test_module_behavior_taxonomy.py`：**46 PASS / 0.79s**，包括现场Scala
  行范围/锚点以及漏行为/维度/交互、假绑定/假运行/静态PASS、候选无ID等正负控制。
- 上述门禁加IO矩阵、新基线合同、DefaultConfig尺寸、观察边界、点域与计划审计：
  **127 PASS / 50.26s**。这是纯自检选择，没有新DUT仿真。
- 根测试 `.venv/bin/python -m pytest -q tests`：**268 PASS / 64.06s**。
- 资产、skill/framework、常规布局及Markdown本地链接/锚点、`git diff --check`通过；
  严格事务边界仍**exit1**，BPU仍有**24项owner基础设施债务**，未放宽门禁。
- 重新打开两个v4历史`io-matrix-audit.json`，核原nodeid、源码、seed、reached/checked及
  NT期望事实；历史源码仍为`f22dc87a…`，不能合并为当前新自检源码的全量验收。

具体来源哈希、审计输入/产物与范围边界见
[本轮证据索引](../../../../../../docs/history/bpu-scala-interactions-20261106.json)。工作期间
检测到共享经验索引及LSQ清单的并行变化，均保持，不将其算作本轮BPU修改或验证证据。

## 下一轮实验顺序与未关闭事项

1. 独立确认20条待核分区涉及的策略/切点，尤其动态enable、FastTrain多相对错误、
   SC无效历史常量票和同拍恢复/目录/Victim线性化；源码观察不能直接抄进golden。
2. 优先清除`INT-041`旧PHR形状、`INT-059`旧观察绑定阻挡；保留原失败并检查目标行为
   真正到达和后续比较。公开target/perfMeta被裁的义务继续blocked。
3. 映射现有合法程序及控制；缺项才补新DUT用例。优先MainBTB NT×读/reset/满待写、
   第五槽迟到×同拍替换、活跃预测器guard×恢复/训练、主微RAS接管与动态启停。
4. 映射后接入同轮reached/checked/完成证据，再按影响选择定向/完整回归与真实seed。
   本轮没有改模型、驱动、RTL、工具锁、配置或旧nodeid，也没有新构建/新DUT回归、
   提交/发布/推送；不能把场景设计完成写成覆盖闭环完成。

旧完整非PASS、21个IO矩阵gap、未确认根因、完整IFU/FTQ可达性及事务边界债务均保留。
**NOT_CERTIFIED**不变；本轮完成的是源码辅助的交互审查和有界覆盖设计。
