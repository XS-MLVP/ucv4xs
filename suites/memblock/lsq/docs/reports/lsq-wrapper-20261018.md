# 真实LsqWrapper整体UT：共享路由、Forward/RAW/RAR与覆盖闭环

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


> 本文保留截至132例的历史证据。最新253例216 PASS/37 FAIL、76/82 checked、
> 58471/59602真实闭包及全池/特殊副作用/NC RAR/共享恢复与共同reset审计见
> [20261019续报](lsq-wrapper-20261019.md)，整体仍未验收。

状态：**进行中，未验收。** 不能把原生构建、静态codec或首批定向用例当整体LSQ
完成；真实LoadQueue与StoreQueue及原有严格失败全部保留。完整目标见
[交付清单](lsq-delivery-checklist-20261018.md)与[层次计划](../ut-plan.md)。

## 用例前边界

[整体合同](../contracts/lsq-wrapper.md)已在任何整体用例前定义82项可读行为：
混合分配/不同环、真实SQ依赖与转发、RAW/RAR、全局ROB许可/连续完成前缀、共享
Uncache年龄仲裁/独立ack与resp方向、串行与NC重叠、SID归还复用、共享恢复/reset
及公平排空。它不是把端口组合列作功能点。

- 真实603输入/458输出；没有联合canAccept/enq resp、外部SQ就绪指针/位图、
  lqFull等已优化删除接口。`issuePtrExt`只观察SQ地址ready，不能伪造数据ready。
- STA的原ROB/FTQ/PA/mask现在同时进入真实PSQ与RAW，STD完整SQ身份同时进入
  PSQ与Replay；不能照独立分支的优化接口把本层多出的字段填成常量。
- 共享req无is2lq输出，只有idResp/resp各自携带is2lq输入；按原UID/命令/ROB/
  地址捕获方向，不按当前选择给旧响应路由。NC ack后的SQ完成与未回总线resp
  是不同义务。req在背压下是Decoupled而非Irrevocable，不能凭空锁定选择。

## 原样构建和静态适配

固定开源`893e1580b`，top SHA
`7833f0083df200ecdc3f4be2c0821eb91131bb415666befb65d7abe92b550b65`；原样53文件
闭包，未修改目标RTL/Chisel。Picker构建、实际实例化和走钟PASS：
`results/builds/20261018T150247307497Z-lsq_wrapper/report.json`，包含原始命令、
全部RTL及原生包SHA、ABI3/coverage5链路。

`results/static/lsq-wrapper-codec-v1/report.json`实际检查256组全输入变化的
编码/独立被动解码往返，603个输入全部变化，11个非法包及14个伪内部反馈拒绝，
同时核验82个用例前目录情形与53份源SHA。这是**静态适配检查，不是合法混合业务
流量或DUT功能覆盖**；内部child adapter占位值不出现在可驱动Wrapper Inputs。

## 首批参考/独立外部检查的实际范围

公开历史参考同时冻结旧SQ readiness和两个旧请求候选，再推进真实两分支参考，
不把SQ新ready当同拍反馈。串行Uncache采用原请求方向/mid/sid的外部事务账本，
不能被任意不相关响应脉冲清除。forward保留独立PA字节安全性质。

首批`lsq-initial-01`22例已实际全部PASS：

- 8个混合dispatch位置×STA/STD两种先后顺序；一个全局ROB排过两条普通指令，
  Load可完成而旧Store仍在真实Sbuffer背压中，随后必须原PA/字节实际消费才SQ释放。
- 两个真实store入口×地址依赖/数据依赖/同拍STD写入三条路径；真实SQ未就绪时
  Load保持阻塞，STA/STD实际写入后才有Replay握手，原slot反馈后VLQ与SQ各自完成。
- 用例另记原始分配/地址/数据、真实Sbuffer fire和两个分支实际deq，最终empty
  须建立在两笔真实完成上。独立原始历史审计为`tools/audit_lsq_initial_v2.py`，
  明确拒绝它未实现的总线/恢复/multi-flow/forward等范围，不能借其局部成功验收。

**首30例时12路Store perf（io_perf_27..38）尚未建模**，当时每个连续记录都列出该边界，
不计已比较；后续49/69例已补齐并独立审计，见下节。其余定义输出按valid/精确首次knownness比较，父级Load perf两级历史
与busy一级历史分开；活动reset不能重开startup屏蔽。模型实现与用例语法检查不
等于原生功能通过，必须以实际结果和随后逐行分析为准。

## 首轮实际结果、独立审计与覆盖驱动补例

| 运行 | 结果 | 功能checked | 本体DA | 真实53文件闭包DA |
|---|---:|---:|---:|---:|
| `lsq-initial-01` | 22 PASS | 8/82 | 109/114 | 24174/59602 |
| `lsq-expanded-01` | 26 PASS / 4参考FAIL | 11/82 | 保留原运行 | 保留原运行 |
| `lsq-expanded-02` | 30 PASS | 14/82 | 114/114 | 24386/59602 |
| `lsq-expanded-03` | 49 PASS | 29/82 | 114/114 | 25684/59602 |
| `lsq-expanded-04` | **59 PASS / 10 FAIL** | 30 reached / 29 checked | 114/114 | **28035/59602** |
| `lsq-expanded-05` | 104 PASS / 28 FAIL（含3定向helper错误） | 50/82 checked | 114/114 | 29043/59602 |
| `lsq-expanded-06` | **107 PASS / 25 FAIL** | **53 reached / 51 checked** | 114/114 | **29054/59602** |

首22例的`mixed-history-audit-v2.json`独立重建720条连续记录、22 Load与22 Store
原始UID全部实际完成；22次原Store字节Sbuffer fire、6次真实Store依赖解除后的
Replay握手与6次原slot反馈，8个Load/Store dispatch入口及2个STA入口有完成见证。
301份启动结束验证源和全部artifact/build SHA一致。v1审计把C_FF错写为mask32，
固定源码index4实际为mask16，原工具及`audit-v1-rejection.json`保留，v2完整
重审未跳过数据依赖、未变更测试/DUT预期。

首轮**35428条未覆盖DA**逐行保留并分类：本体5条为共享总线实际接受后的串行/
NC重叠和响应清理；主要真实下级余量为Replay18327、VLQ4416、RAW2808、RAR1933、
VSQ1807、PSQ1662及FreeList/Uncache/CAM等。全部映射到用例前82项已有功能缺少
整体情形，非偷偷遗漏整条功能；没有移除原分母、宣布不可达或把叶子覆盖并入。

基于本体5条与下级Uncache/Deq缺口新增8例：Load NC/MMIO×干净/fault、Store
NC/IO×两个STA入口，实际共享请求/方向ack/resp、Load内部wake→Replay→bypass
原数据/错误→S3→VLQ及Store确认/WB/SQ完成。**这些只是单侧生命周期，不是两候选
年龄仲裁、混合方向竞争或NC并发验收**，因此相应复杂bin仍未checked。

`lsq-expanded-01`四个Store例先停在父参考取不存在的child cmd字段，非RTL反例；
SV4393在Store分支提供literal1，纠正一处常量映射后另跑新目录，304启动结束源
和原失败保持。新的30例`lsq-expanded-02`全部PASS，305份启动结束源及全部SHA
一致。`bus-history-audit-v1.json`核验原22例的全部原始输入、pre/post与tick
**逐bit匹配**已经独立审计的初轮，不仅比较签名；新增8例另独立重建298记录、
4个原Load请求/数据/错误/Replay/最终消费、4个原Store写请求/完成、8个方向正确
ack与8个唯一响应、2个IO实际WB。合计1018记录、26 Load/26 Store原始事务完成。

第二轮新增**212条DA**，本体已114/114，但真实闭包仍仅24386/59602、功能14/82。
剩**35216条**再次逐行分类，仍主要Replay18323、VLQ4416、RAW2808、RAR1933、
VSQ1807、PSQ1662，以及各FreeList/剩15个entry/forward/UQ等。全部记录在
`lsq-expanded-02/line-audit-classified.json`，不能以本体行满或30 PASS结束。

## 后续真实竞争、完整perf与128-flow补例

`lsq-expanded-03`新增19例并完整重跑49例，全部PASS，308启动/结束源SHA及全部
artifact/build哈希一致。新范围为14个正常producer混合总线例、4个明确的
**UNIT-INTERFACE**年龄仲裁例，以及1个128-flow向量Store例：

- 先让真实年轻NC Load在总线背压中可见，再使老Store经真实STA/STD、S2和VSQ
  许可就绪；观察它在两真实候选之间取代原Load，包含ROB跨159/0及同entry的
  former/latter。未握手请求不假设Irrevocable，年龄选择随当拍候选变化。
- NC/IO Store×串行/outstanding：ack不代替串行resp；忙态resp当拍没有零拍
  新握手。两种反向同拍路由都检查：ack→Load/resp→Store，以及ack→Store/
  resp→Load，不能按当前仲裁方向返回旧响应。原Load的PA/字节/不同错误位到真实
  Replay、bypass s1/s2、S3、VLQ；Store到自己的ack或实际WB/SQ释放分别完成。
- 老Load待总线而年轻特殊Store得到头许可、或同ROB平局的4例只作公开接口仲裁
  检查，明确不当作正常ROB退休、Backend或架构可达性证明。
- 8个16-flow uop形成128虚拟flow，只在64物理窗口内发行。地址先行而数据未就绪，
  实际检查物理ready跨度15/16/17/32/33/48/49/64与虚拟128不同；真实消费/释放
  前64后，同64物理槽的新SQ代完成余64，不只是写满后断言empty。

12路Store perf参考已实现：物理跨度用较后addr/data ready指针，虚拟跨度用
分配尾；恰好16/32的源码区间空洞按原行为检查，事件经PSQ/StoreQueue/Wrapper
各两拍，无reset流水不清空历史。全39路perf均有模型，未实现输出列表现为空，
但这不等于活动reset或所有未来流量已经验收。

`bus-history-audit-v2.json`独立重算2474条连续记录：原30例全部输入/pre/post/
tick逐bit匹配前审计；新增18 Load/18 Store原始事务完成、128原始flow实际字节
消费及释放、64个同物理槽新SQ代完成、8次NC SQ先释放而外部响应仍欠。两种反向
ack/resp同拍分别有3/2个原始见证。Store perf独立比较52908个引脚样本，**12路
均有0/1见证**；其中event0在Load只含NC、或无Store总线时用公开寄存OR-busy
作跨接口一致性核验，不称作第二套任意Deq状态机。覆盖增加1298条DA，剩33918
条全部逐项分类，未删除分母。

## 三笔交错与SID复用的严格失败

再补20例后，完整`lsq-expanded-04`实际为**69例59 PASS/10 FAIL，NOT_PASS**；
312启动/结束源SHA及全部artifact/build SHA一致，没有把失败转成skip/xfail。

1. **新`LSQ-BUS-OWNERSHIP-001`，4 FAIL**：一个全局ROB始终停在老Store0，
   年轻NC Load1先总线接受/确认但未响应；老IO Store随后经真实VSQ/PSQ请求并
   接受/确认，年轻NC Load2也成为真实候选。旧Load1回包后，tick74/80顶层
   `io_uncache_req_valid`实际变1，合同应仍为0，因为串行Store自身响应仍欠。
   当前证据是**提前可见请求**；严格参考立即停止，没有第三笔实际fire、下游
   接受或架构后果证明。NC Store必要条件对照4例均将3个原UID真正排空。
2. **原`LQU-SID-001`在真实Wrapper复现，6 FAIL**：旧resp.fire后合法归还SID，
   不等旧Load的bypass；新Load复用同SID并返回相反error/nderr。旧Load实际
   s1消费时，原PA/ROB仍在，但异常19/5变成新Load的错误。严格检查先停在s1，
   不宣称本批又观察到了尚未到达的s2字节。不同SID的6个必要条件对照均完成
   两个Load原数据、错误、S3和VLQ释放。

`bus-history-audit-v3.json`不导入子参考或change作答案，独立重建3444条连续记录，
原49例全部原始采样逐bit复核；新增48 UID=24真实完成+24失败保留，44原请求、
44方向ack、40原响应及20原Load数据/错误实际消费。独立识别上述4+6失败和实际
SID归还/复用时间，所有历史（含失败）再核验73548个Store perf样本。

`producer-domain-audit-v1.json`保留固定开源commit、干净树及5份源码快照，核对
NC entry可在ROB头前发行，Uncache准入没有“所有NC返回前禁止nonNC”的额外
互斥；本例3个地址不同block、最多2笔外部在途。它**不是**完整Backend可达性、
精确Uncache SID优先级/流水时延的原生联合仿真或Chisel重elaborate。初次审计
误把fixture boot空拍也要求outstanding=true，原拒绝记录/审计器已保留，修正
只限定实际分配后的事务窗口，未改刺激、严格预期或RTL。

本轮再新增2351条DA，当前真实闭包为28035/59602，**剩31567条**逐项保留分类：
Replay16107、VLQ4398、RAW2808、RAR1933、VSQ1709、PSQ492及其他池/entry/Forward/
UQ等，仍均属于用例前82项已有功能缺少情形，不是不可达证明。目录29个checked
仅表示有成功检查见证；串行/响应路由现在仍有必需子情形FAIL，不能按bin命中
宣称该功能完整验收，SID复用仅reached未checked。

## 真实Forward、共享STA→RAW及缓存Load RAR闭环

新增63例后，`lsq-expanded-05`完整132例为104 PASS/28 FAIL，其中3个同VA多匹配
对照helper错误要求立即无阻塞转发。阶段参考和RTL均给出合法保守重放，不能把
它归为RTL缺陷。修正对照为实际multi-match Replay、原Store三片段消费、真实
SQ empty唤醒、原slot反馈和3原UID完成；同时将地址依赖查询的wait/完整waitSQ
与原Load S3 uop保持一致。**未改PA字节安全预期、未改RTL、未移除任何失败节点。**

新目录`lsq-expanded-06`完整重跑132例：**107 PASS/25 FAIL，NOT_PASS**。两轮各
317启动/结束源SHA一致，原132例/28失败及源快照全部保留。
`control-helper-correction-audit-v1.json`证明3个原失败的全部原始采样逐bit为
修正例前缀，只有旧directed断言的forwardInvalid=0不成立；修正后的延长历史
各有一次真实Replay握手、三次原Store片段消费和全部UID完成。其余25个失败
node ID完全保持，不将必要条件对照替代失败的完整合法域。

### 新增用例的实际语义

- Forward查询属于真实已dispatch Load，完整SQ边界指向真实Store银行。3lane
  检查对齐/最年轻PA字节、缺STA、缺STD不得回退旧值、迟到STD解除依赖、kill、
  跨word范围、不同VA同PA别名、非零SQ头/裁剪后的完整依赖身份和实际UQ第二页。
  阻塞查询先解决依赖/真实重放再完成，不发送正常S3绕过失败。
- 对非零头，先实际写出60个flow，再分配64/68个新flow；每个within-window
  对照完成124原Store和1 Load。clip失败仍使用合法68虚拟flow，不缩到物理窗口。
- 跨页Store的实际UQ接受、首末STA和两个不同物理片段真实消费得到检查；释放后
  原Load再查无旧forward，再由外部缓存S3完成。保留接口没有Load最终结果data
  输出，未把外部给定缓存读值冒称本层观察。
- RAW不能另造一组store探测输入：同一真实STA携原ROB/FTQ/PA/mask/TLB-miss
  同时进入PSQ和RAW。双port正例核对全部Load/Store恢复字段、checkpoint/RVC
  及最老MDP训练；采用真实最老rollback作为共享redirect，两分支实际恢复响应
  后，取消的4个Load均由同LQ槽新UID完成，旧Store原字节仍必须实际消费。
  mask、年龄、miss及一/两拍revoke负例保留；miss必须正常重试并触发真正冲突。
  年龄负例的Load真实SQ边界为0，不分配RAW记录是合法行为，不冒称强写了年龄
  不合法的记录来覆盖比较器。
- RAR用两个同物理line、不同VA的真实缓存Load身份。当前release触发旧Load的
  VIOLATION Replay、原slot反馈和VLQ连续前缀完成；无release和两级revoke不得
  误报。前拍release继续严格失败；未用虚假NC位给普通缓存Load激活路径。

### 整体新增严格失败

| 问题 | 新增FAIL | 本层独立观察 |
|---|---:|---|
| FWD-ALIAS-001 | 3 | 无任何重放/依赖标志时，原PA字节应来自年轻Store的0x22，却输出旧0x11 |
| FWD-RANGE-001 | 6 | 两个word×3lane的有效forward mask包含没有原PA producer的字节 |
| FWD-SQID-001 | 3 | 真实head60、source SQ112、Load SQ128时，dataInvalid依赖错误报告SQ176 |
| RAR-REL-001 | 3 | 前拍同line release的年轻读者未标released，旧Load实际nuke0、合同1 |

再加原有4个串行owner和6个SID失败，共25个普通FAIL。**Forward本体253/253 DA
已在Wrapper真实闭包命中，但三类语义仍失败，不能验收。** alias/range/sqid等bin
有对照成功见证只表示局部情形checked，不代表该功能完整通过。

### 独立历史、生命周期与覆盖提升

`memory-history-audit-v1.json`不导入DUT参考/actor，不读取change/physical字段作
答案。独立重建6526连续记录、原69例全部input/pre/post/tick逐bit复核，以及
新增**907 UID=669完成+4取消+234失败保留**。其中：

- 603原Store flow完成、615个原PA/字节片段实际Sbuffer消费、66原Load完成。
- 212个实际未阻塞forward原PA字节、34个安全响应、61个绑定原Load UID的查询；
  被阻塞响应不计字节成功。3次实际UQ第二页接受和3次kill抑制独立核验。
- 4个原RAW rollback、2个最老MDP训练、2次两分支实际恢复，全部4个取消Load的
  同LQ槽新UID实际完成；6次原Replay握手及6次原slot反馈。
- 独立从原始PA/字节/完整SQ和release窗口识别新增3+6+3+3失败，未靠known-issues
  表或参考输出推断失败类型。实际artifact/build SHA及317冻结源核验一致。

原31567条缺口补例后，首轮新增1008条DA，修正完成路径又新增11条真实ESB DA；
当前**29054/59602**，剩**30548条**逐项分类，未删分母或合并叶子覆盖。主要缺口
Replay16107、VLQ4268、RAW2542、RAR1615、VSQ1673、PSQ394及其他池/entry/UQ；
全部属于用例前已有功能的缺失情形，不等于不可达证明，也不因51/82 checked
或53 reached宣称整体完整。

### 实现与复现入口

- `lsqverify/lsq_wrapper/store_perf.py`：公开Store历史的12路事件/六拍流水；
  `model.py`仍先冻结两分支旧反馈/候选，不读DUT内部寄存器。
- `tests/lsq_wrapper/test_mixed_bus.py`、`test_store_span.py`：新增19个成功用例；
  `test_bus_ownership.py`与独立`bus_owners.py`：三笔交错、SID复用及必要条件
  对照20例，保留10个普通FAIL。
- `tests/lsq_wrapper/memory_owners.py`、`test_forward_memory.py`、`test_nuke_memory.py`：
  独立混合内存actor、新63例、实际PA字节/共享STA恢复和取消后同槽新UID完成。
- `results/lsq-expanded-04/`保留69例bus审计与producer窄证明；最新
  `results/lsq-expanded-06/`保留132节点的命令/pytest/连续引脚/native覆盖、317源
  冻结/结束SHA、`memory-history-audit-v1.json`、
  `control-helper-correction-audit-v1.json`和逐行`line-audit-classified.json`。

以下是当时132例的历史审计命令；当前目录已扩至253例，最新门禁见续报。使用
独立验证根`memblock-hash/lsq/`与**新目录名**；预期真实非零
pytest退出码，不能为了绿色而排除失败：

```sh
python3 -B tools/run.py --name <fresh-name> --workers 4 -- tests/lsq_wrapper --tb=short
python3 -B tools/capture_end_sources.py <fresh-name>
python3 -B tools/coverage_audit.py <fresh-name>
python3 -B tools/audit_lsq_gaps.py <fresh-name>
python3 -B tools/audit_lsq_memory_v1.py <fresh-name>
python3 -B tools/audit_lsq_control_v1.py <fresh-name>
```

捕获结束源码前不能修改启动文件。旧bus-v3只接受69例，新memory-v1只接受当前
132例及69例原始历史逐bit门禁，不擅自接受未来新增容量/完整恢复/reset/CBO/随机
用例；届时必须新增审计版本，不能直接放宽断言或复用局部PASS冒称新范围已审计。

## 仍需完成

已复现的总线/SID/Forward/RAR严格失败、Store特殊完成等其余缺陷整体复现、RAW/
RAR全池及NC/真实VLQ头回收、Replay全部容量/原因/严格依赖/特殊模式、Load容量和
两分支完整多圈/全槽、完整shared redirect/reset同槽新UID完成、82目录全部实际
执行/检查、后续53文件闭包逐行缺口分类与补例重跑、全历史混合UID/总线/字节审计
及最终全范围审核仍为必需工作。无skip/xfail、问题清单oracle或RTL修改。
