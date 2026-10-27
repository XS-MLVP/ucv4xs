# LsqWrapper：真实Load/Store共享顺序、依赖与总线合同

**后续生产者纠正优先限定历史补例合同**：旧S3默认字段/Replay伪更新、RAR nuke作
C_NK、错拍/缺revoke及提前分配CBO的旧接口流不再给完整正常准入。原82项功能不删，
旧执行/FAIL/DA保留，但联合RAR96与LRQ120长期原UID双占不能当正常稳定峰。新
[全域S3合同](lsq-ldu-s3-full-domain.md)、[容量转移/CBO合同](lsq-ldu-joint-phases.md)
与[串行缺口合同](lsq-ldu-joint-serial.md)分别定义新源正确范围；实际新26例17/9及
新27例21/6见[S3报告](../reports/lsq-ldu-s3-20261019.md)和[分阶段报告](../reports/lsq-ldu-joint-phases-20261019.md)。
正条件不替代完整八类型随机/错误/别名/split或抵消普通FAIL，后文历史计划不追溯改写。

状态：**用例前整体合同。尚无本层功能通过声明。** 本层必须保留真实LoadQueue、
StoreQueue及全部下级，不能以分支通过、独立回归汇总、两Python模型相连或smoke
替代整体DUT。开源固定`893e1580b705d81f113c30c7a05734e09a08050e`，真实连接依据
`LSQWrapper.scala:158-349`，原样`LsqWrapper.sv` SHA256：
`7833f0083df200ecdc3f4be2c0821eb91131bb415666befb65d7abe92b550b65`。
53份RTL传递闭包；不修改目标RTL/Chisel，不使用私有工程。

## 1. 实际端口与不可伪造的边界

- 原SV除clock共**603输入、458输出**，全部宽度1..128。8路dispatch含两位
  needAlloc、ROB、numLsElem、exclusive SQ end与LQ start；3路共享S3/RAR/RAW、
  2路STA/STD/S2/UQ、3路forward/bypass/replay、ROB当前/下一head、两memory
  channel与TLB hints、Cache CBO、Sbuffer、共用Uncache及独立Load/Store异常。
- 顶层**无**enq.ready/canAccept/recoverStall/resp、lqCanAccept/sqCanAccept、
  lqDeqPtr、lqFull/lq_rep_full、rarValidCount、physicalStoreQueueFull、hartId、
  WFI、debugTopDown及wakeCancel端口；这些删除字段不制造驱动/观察或动态覆盖。
  `sqFull`、`sqDeqPtr`、`issuePtrExt`、两分支实际deq/recoverStall/redirect响应、
  `sqEmpty/lqEmpty/replayAllocate/specialMode`和39路perf仍存在。
- **所有SQ就绪反馈现在是内部真实连线**：地址/数据指针和位图、sqEmpty、SQ
  deq/physicalUpper都来自真实StoreQueue，不能像独立LoadQueue UT那样外部直驱。
  `issuePtrExt`只直接观察SQ地址就绪指针，不将其当数据指针或全部依赖答案。
- STA在本层同时影响PSQ写入和RAW冲突：实际保留ROB/FTQ/RVC、PA、mask、wline、
  TLB-miss及低6位SQ。STD保留完整SQ双flag并同时进入PSQ和Replay实际写入唤醒。
  不因独立SQ曾优化删除ROB/FTQ或STD flags而在本层补成常量。
- 共用Uncache公开idResp/resp均保留`is2lq`；**req没有is2lq输出**。请求来源须
  从已知UID、ROB、PA/VA、读写命令和字节身份核对，不伪造方向端口。正常读cmd0
  来自Load，写cmd1来自Store；req.data在Load路径为DontCare，不比较未定义值。
- Store分支的Uncache child只保留响应valid/ack方向；共享resp的data/id/error/
  nderr只在Load路径有实际功能观察。不能宣称已动态检查被删除的Store错误传递。
  Cache denied/corrupt→实际store WB保持仍是独立严格义务。

原Chisel的联合canAccept等组合接口当前未保留，只可记录源码语义/删除边界，
不能计动态checked。容量测试通过外部合法账本、真实消费/恢复/rollback检查实际
保留行为，不把这种间接检查改称联合canAccept端口验证。

## 2. 合法混合生产者、完整身份与完成

1. 使用一个外部程序序ROB账本生成混合Load/Store，而不是两组互不相关的ROB头。
   ROB为160槽×flag×former/latter，SQ为64物理槽×双flag的256编码，LQ为120项
   ×flag的240编码；均用独立环形年龄，不把低index相等当相同owner。
2. dispatch Valid-only正常needAlloc为0/Load1/Store2，字段静态payload不能在
   valid=0或本分支needAlloc=0时产生分配；两位同时1作为额外UNIT-INTERFACE域
   时明确单列，不能推断普通指令会同时需要两队列。0..16 flow合法，LQ连续
   start、SQ紧凑exclusive end、稀疏八lane和0-flow均须与真实完成核对。
3. 普通producer的dispatch与当拍redirect互斥，恢复stall时不新dispatch；这一
   限制来自已核对完整开源门控/延迟路径，不是为了规避VSQ接口失败。前拍分配
   可与后拍恢复相遇，且必须测试。恢复只能采纳真实分支响应指针后再重发。
4. SQ最多128虚拟flow占用，只有当前64物理窗口可STA/STD发行；虚拟uop与flow
   UID分开跟踪。正常ROB可在执行完成后先于Sbuffer副作用退休，但CBO/NC/IO头
   必须遵循真实特殊完成许可；不能人为禁止`read!=head`来绕开完成顺序缺陷。
5. S2没有valid，必须是前拍同lane STA的属性；跨word首末与UQ第二物理页保持
   原PSQ合同。RAW的mask/wline/ROB/FTQ来自同一真实STA，不独立伪造另一笔store。
   同物理槽STA/STD必须引用外部当前代owner，不能凭6位槽号覆盖旧在途store。
6. Load S3进入真实VLQ/Replay，cause0进入真实Uncache；原因0..11单hot，cause12
   含assert不作普通流量。Replay握手只授予再执行，真实slot反馈才更新/释放；
   VLQ完成仍要求`!need_rep && updateAddrValid`。总线/bypass未结束不能假造正常
   S3完成来清空队列。重复cause0新分配须遵循Uncache真实producer规则。
7. load→store转发按load SQ依赖边界检查最年轻老store的逐PA字节。VA候选、缺地址/
   数据、完整依赖SQ身份、跨word/page、别名及负对照都保持严格；不以阶段模型
   命中代替独立PA安全性质。迟到store地址触发RAW时检查原load与store的各自
   ROB/FTQ/RVC/checkpoint和MDP训练，不能只断言valid出现。
8. 完成分三类：Load真实VLQ连续前缀消费；Store原字节/CBO/WB/NC完成与随后
   连续SQ释放；共享总线每个已接受事务唯一ack/resp。不能把ROB退休、Replay
   握手或NC ack当作所有外部义务都结束。尤其NC store可能已允许SQ完成，但
   尚欠总线resp的外部UID仍必须保留在总线账本。
9. redirect取消年轻后缀并同时影响真实两分支；幸存已退休store副作用不得撤销。
   已送入Load弹性流水的请求即使尚未在顶层握手，也可能在redirect后继续出现，
   须以原身份接受/回包安全清理。取消/reset后必须同物理槽新UID实际完成，
   不只出现新请求或恢复指针；外部UID、Replay、bus、bypass义务分别守恒。

## 3. 共享Uncache仲裁与路由

原SV`1318-1337,1497-1508,3163-3204,4011-4041`与Chisel`274-340`为依据：

- 当两分支都有可见请求，按完整ROB slot/former年龄选择老者；完全相同ROB身份
  的直接接口平局由Store获选，不能把平局当普通程序年龄。ROB回绕与former正反
  必须单独检查。选择只能来自真实队列产生的请求，不能poke内部req.valid。
- pendingstate空闲时才给获选分支ready，顶层实际req.fire才建立外部事务。
  `uncacheOutstanding && req.nc`时保持空闲允许NC重叠，否则到resp后才重新空闲。
  idResp不能提前解除串行等待；响应当拍不能从旧busy状态零拍偷发另一请求。
- pendingstate记录串行占用，**不代替响应方向**：idResp和resp分别按各自
  is2lq路由，可以独立到达。外部代理保存每笔已接受请求的正确方向/mid/sid，
  不按“当前选择”或“最新请求”给旧响应选择方向。共享SID只能在resp.fire后
  归还；旧Load未消费数据不能因合法SID复用被新响应覆盖。
- 顶层Decoupled不是Irrevocable承诺：未ready时若另一老候选到达，组合选择可
  改变。每个采样边沿比较当时合法候选和真实fire，不凭空锁定一个未来owner。
  分支内部弹性流水的原身份保持与顶层组合选择需分开检查。
- `io_rob_mmioBusy`是两分支mmioBusy的OR再寄存一拍；不能拿当前bus.valid作答案。
  它是无reset历史，初始化与活动reset不得用整块宽泛屏蔽。

## 4. 用例前语义功能目录（82情形）

reached只表示情形执行，checked必须对应完整实际比较和必需生命周期证明。
以下ID不因已知缺陷而删除；必要条件对照不能替代失败的完整合法域。

| 功能组 | 必需情形 | 人可读微架构行为与检查义务 |
|---|---|---|
| LSQ-RESET | initial / active_load / active_store / pending_load / pending_store | 复位空闲及活动两分支/共享等待；中止旧UID，无幽灵副作用，同槽新UID真正完成 |
| LSQ-ALLOC | filters / sparse / multi_flow / all_lanes / lq_wrap / sq_wrap / lq_capacity / sq_capacity | 同一混合dispatch正确过滤/压紧两队列，8入口、多flow及各自回绕/容量，旧槽不被覆盖 |
| LSQ-RETIRE | ordinary / rob_before_sbuffer / multi_flow / nc / io / cbo / zero_ownership / finish_prefix | 执行、ROB退休、真实副作用与SQ释放不能混同；多flow、特殊完成和zero必须守住原owner的连续完成前缀 |
| LSQ-FORWARD | aligned / youngest / addr_hole / data_hole / late_std / alias / range / sqid / wrap / page / kill | Store真实乱序就绪后Load取最年轻合法PA字节或重放；缺就绪不得回退旧值/假身份，跨界/别名仍安全 |
| LSQ-REPLAY | sq_address / sq_data / std_write / strict / disabled / refill / tlb / capacity / head / special | 真实SQ反馈、STD/STA及实际容量/头、hint/2048等待控制重放；未满足依赖不能重发，正常反馈才完成 |
| LSQ-RAW | conflict / mask_negative / age_negative / tlb_miss / dual / revoke / train | 老Store地址迟到触发年轻Load字节违规，两个store、撤销、负对照与训练均保持各自原始身份 |
| LSQ-RAR | current_release / previous_release / nc / revoke / head_reclaim | 真实Load完成和release相位正确标记/触发再执行，VLQ头自动回收，取消后不误报 |
| LSQ-BUS | load_only / store_only / older_load / older_store / rob_wrap / former / tie / backpressure / serial / nc_outstanding / ack_route / resp_route / sid_reuse / cancelled_return | 两分支实际请求竞争、年龄仲裁、串行/NC重叠及独立方向路由不串单；每个mid/sid和原数据/错误只回应一次 |
| LSQ-RECOVER | partial / all / concurrent / sent_load / buffered_load / retired_store / reuse | 共享恢复与分支不同流水/已发响应并发，保留已退休Store，取消旧Load安全清理，实际同槽新UID完成 |
| LSQ-EXCEPTION | load_clean / load_fault / cache_wb / shared_route | 干净/出错Load保持原ROB/VA/GP/fault；Cache错误保持至Store实际WB；两分支响应/异常互不污染，删除Store总线错误字段不伪造 |
| LSQ-STRESS | seeded / capacity / fair_drain | 固定种子合法混合压力、全域容量和公平最终排空；独立核算全部UID、Replay反馈、bus和bypass，不以固定拍数结束 |

## 5. 参考、采样、独立代理与覆盖闭环

1. 先原样构建、实际603/458端口清单和全字段codec/被动decode往返；静态随机包
   不是合法业务覆盖，所有实际输入必须绑定，输出不得误当驱动。
2. 组合公开历史参考时先冻结两分支**旧状态**反馈、获选bus ready与response路由，
   再同时推进Load和Store；不能按顺序把SQ新ready指针或Load新bus状态变成零拍
   旁路。所有参考状态来自公开历史，不读DUT内部寄存器/内存作正确答案。
3. 外部混合actor与参考分离：同一ROB队列分配LQ/SQ/flow UID，真实公开握手决定
   工作；每个边沿连续保存pre/post全部引脚。forward另作PA字节性质，结束后按
   实际公开历史独立重建年龄前缀、总线方向、数据错误、取消/reset和同槽复用。
4. 无valid payload、DontCare、源码未初始化数据不比较；按各寄存路径精确建立
   首次knownness。父级额外perf两级和busy一级历史单独核对，活动reset不重新
   打开startup屏蔽；未实现的perf检查必须明列，不能将未比较字段称为已checked。
5. 初轮先实际混合分配/普通副作用/Store依赖解除Replay/真正bus竞争与路由，随后
   审查本体及53份真实闭包每条未覆盖DA。逐条标明既有功能缺情形或整体遗漏，
   再补合同/目录与用例重跑；先前叶子/分支行满不替代本层覆盖。
6. 每轮独立结果目录，启动/结束验证源SHA、RTL/包/工具/build/artifact哈希和
   种子齐全。真实RAR/strict/SID/Forward/WB/wline/zero/完成顺序失败须在可达
   整体场景保留普通FAIL和必要条件对照；接口边界与生产者域分开，不修改RTL、
   不skip/xfail、不读known-issues作oracle。
7. 最终收敛时同时审查本目录82项、逐行余量和独立生命周期；任何未实施/未检查
    项仍是必需工作。此合同/原生build/smoke不等于LSQ功能验收或整体目标完成。

### 下一轮新增情形的用例前约束

- Store 12路perf依`NewStoreQueue.scala:1546-1547,2110-2123`：物理跨度取地址/
  数据就绪中年龄较后的指针到deq距离，虚拟跨度才取分配尾到deq距离。占用恰好
  16（物理）/32（虚拟）时，源码四分位事件均为0，不擅自补齐区间。事件经过
  PSQ、StoreQueue、Wrapper各两拍无reset寄存；活动reset不能清空六拍历史。
  建模不等于所有事件都实际翻转，需独立原始历史重算并报告0/1见证。
- 真实Store请求必须由VSQ根据同一全局ROB头发出preCommit。普通竞争场景使用
  老Store和可推测执行的年轻NC Load；NC outstanding允许Load先在途，随后老
  Store才就绪，ack与resp可在同拍各向相反方向返回。NC Store已SQ释放仍保留
  未回resp的外部账本。串行模式的ack不能解除等待，resp当拍不能零拍偷发。
- 老Load仍等待总线时，年轻特殊Store不应在正常ROB退休规则下获准执行。为
  直接检查已保留年龄仲裁的Load优先、former正反或同ROB平局，可以明确标为
  **UNIT-INTERFACE**，只验证Wrapper公开边界，不能假称正常producer或架构可达；
  普通流量/边界流量及完成证明分别报告，不用该边界替代后续完整合法随机。
- 串行身份还需三笔交错情形：全局ROB头是老Store，年轻NC Load先发行且未回包，
  老Store随后就绪并接受非NC串行请求，再产生第二笔年轻NC Load候选。第一笔
  NC Load的响应只能结束自己的义务，不能解锁仍等待自身响应的Store；NC Store
  outstanding作为必要条件对照。另以不同SID对照检查：SID在旧resp.fire后可
  复用，不能等旧LDU消费才归还；旧Load的原数据/异常必须保持到真实bypass/S3。
- 下一批Forward查询必须属于真实已dispatch的Load及其完整SQ依赖边界。先保持
  一份稳定的真实STA/STD银行，再检查最年轻PA字节、缺地址/数据、迟到STD、kill、
  跨word/page、VA别名和physicalUpper截断身份；阻塞的查询补齐依赖并重查后才
  送正常S3，不能靠直接S3完成掩盖错误。正例还须原Store片段实际Sbuffer消费。
- RAW的store探测只能是同一笔真实STA：ROB/FTQ/PA/mask/TLB-miss同时进入PSQ和
  RAW。冲突返回原Load、原Store恢复字段和最老MDP训练；取真实最老rollback
  作为共享redirect，取消年轻Load后按真实恢复指针重发同LQ槽新UID并完成，
  不把rollback.valid当作原Load已经完成。mask、年龄、TLB-miss和两级revoke负
  对照保留；TLB-miss的Store必须正常重试后写出。
- RAR同/前拍release须绑定同物理cache line的真实两个Load身份，旧Load未完成
  使真实VLQ头阻塞；正常正nuke按原Load ROB产生flushAfter，保留老UID、取消年轻原UID，
  恢复后同槽新UID完成，不能误作Replay cause11。旧Replay接口流保留原件但不提升为
  正常LDU程序。撤销和无release对照不得误报。NC位不能只为激活路径而贴给普通缓存Load；NC业务另须真实总线
  /bypass完成。共享VLQ头自然回收与再次查询单列，不能外部直驱内部head。
- 同VA跨word多匹配对照允许保守`forwardInvalid`，不能要求立即无阻塞转发；
  应走真实multi-match Replay、Store原片段实际消费、SQ empty唤醒及原slot正常
  反馈。不同VA/同PA的已知失败仍必须拒绝未阻塞的旧字节，不能以扩大don't-care
  或放宽PA字节安全来换取通过。首132例中该对照helper过严的3个失败与源码冻结
  保留，纠正后必须新目录完整重跑。Forward的wait/strict/完整waitSQ元信息还应
  与同一Load的S3 uop保持一致，不将仅查询端的动态标签当作独立虚构事务。
- Store特殊完成下一批采用同一全局ROB：老普通Store可已经退休但仍在Sbuffer
  背压中，年轻ROB头的CBO/NC/IO经真实VSQ/PSQ许可执行。不得人为增加read==head
  限制。Cache denied/corrupt必须保持到真实WB.fire；CBO.zero必须有自己PA的零
  写片段才能WB/释放，普通split尾段不能继承邻项zero的wline，年轻完成不能越过
  未消费老owner。NC SQ完成与仍欠外部resp继续分开记账，Load分支同时完成原UID。
- 为捕获实际错误WB/Sbuffer消费和错误释放，可新增明确命名的公开协议probe
  fixture：保存全部输入/pre/post，但不冒称逐拍全输出参考；日志必须标明该
  边界并使用独立文件名。它不放宽现有严格fixture/模型，所有真实协议/字节/
  错误/前缀断言保持普通FAIL；只在原UID义务完成或实际反例观察后检查，不能
  skip/xfail、把阶段模型失配忽略后标全输出checked，或拿probe替代整体随机验收。
- Replay覆盖补例将真实VLQ/Replay同时填到120：每个S3入口分别保存120个不同
  原Load依赖/元信息，握手仅授予重执行，原slot反馈后VLQ才释放。地址依赖SQ7
  必须先实际分配8个老Store，等真实STA/STD推进到SQ8才解除，不借独立LQ的外部
  SQ就绪指针或虚构未分配Store。TLB/MSHR不同ID先阻塞、再以实际公开hint/refill
  解除；全120 slot×3入口及原UID排空须有独立历史见证，不能仅写满计checked。
- 真正程序头最后进入Replay时，检查真实VLQ head/head-near候选优先于更早入池的
  年轻Load，并完成所有原UID；另以8个dispatch来源分别填120个多flow Load，
  每个ROB的1..16元素区间和全部LQ圈/flag必须由后续S3/VLQ实际完成证明。
- strict对照由真实两个Store形成SQ0地址缺口、SQ1就绪位；严格Load在指针未越过
  SQ1且无匹配执行唤醒时不得仅靠位图或valid=0的反馈清除依赖。有效对照必须实际
  STA/StoreWakeup，再补齐旧缺口并完成原slot反馈与原Store字节。specialMode检查
  原ROB头TLB-miss等待2048拍及资格负对照；只有该原Load实际完成后才移动下一ROB
  头（含former变化），不能用非法越过未完成Load伪造退出事件。
- `lsq-replay-expanded-02`保留两个special计时helper失败：它将ROB头移动与首次
  eligible S3触发放在同拍。开源`LoadQueueReplay.scala:1050-1063`明确头移动优先
  清计数，逐拍模型和DUT均未启动窗口，并非RTL失配。纠正为先建立真实ROB头再
  S3触发，2048阈值/原UID反馈/合法头移动断言不变；须在新目录重跑。
- RAW/RAR全池下一批分别由三个真实Load查询入口填56/96项，使用已dispatch的
  原Load PA/ROB/SQ/LQ，不将缓存Load伪贴NC。RAR年轻Load可完成S3但旧LQ0未完成
  使真实VLQ头不动；后续Load的真实RAR查询被容量拒绝并进入C_RAR Replay，只有
  旧Load实际完成、VLQ连续头自然推进/回收后才允许原slot反馈。RAW记录指向真实
  8个未就绪老Store的exclusive SQ8，先让原Load完成而池仍满，再由不冲突的同一
  STA/STD写入推进真实SQ地址指针至8，释放池并唤醒C_RAW；不能外部直驱head/full。
  本批证明满池/三个入口/真实回收和原UID完成，不把填满或无冲突对照冒称全物理
  选择组的正rollback、全部RAR地址元信息或NC生命周期已验收。
- VSQ余量下一批使用128个不同ROB的单flow uop，而非8个16-flow uop；八个来源
  各填满一次128虚拟槽，只有当前64物理窗口可STA/STD。先完成并退休老64个ROB，
  原PA字节实际消费/释放后才发行后64；同一全局ROB随后退休剩余项及原缓存Load。
  程序序与绝对SQ代由外部历史保存，完整SQ编码回绕后不能把新owner写成旧代。
  ROB flag/former以及SQ双flag都须由真实许可、原字节消费和连续释放观察，不读
  私有VSQ槽或以写满行/删除canAccept端口代替检查。
  普通Store的allValid ROB头也可经preCommit执行（NewStoreQueue.scala:1989-2005），
  不人为要求严格早于ROB头；该副作用必须标为头许可而不是已退休证明。
- Replay余量按三路同拍的不同单hot原因覆盖严格等待保存，不制造多hot正常流量。
  120个原Load的MA/TLB/MSHR依赖分别由真实SQ、公开TLB/refill解除；MA strict
  另保留“只写SQ7、SQ0仍缺口”的全池正反对照，strict不能仅靠真实ready位提前
  重放。数据唤醒必须命名实际已dispatch Store，随后下一拍的真实STD写入偿还
  该生产者义务；无cancel端口不伪造取消历史。缓存重试/way重试各入口检查原UID
  正常slot反馈；真正VLQ头故意放到不同Replay bank，以实际完整身份/slot选择
  和120个原UID排空证明，不用内部head或只计候选组合行命中。
- `lsq-replay-gaps-01`的两个头优先directed断言错误地要求未ready时替换已选输出；
  当时逐拍模型与DUT都保持最先选中的原请求。开源Replay.scala:654-700规定S1
  持有及真实fire后接收下一选择。旧失败/源码保留；纠正为先核对并消费原候选，
  再要求下一次选择优先原VLQ头，完整120 UID/原slot反馈义务不变。全池strict的
  真实valid提前仍为普通FAIL，不与该helper错误混淆。
- Uncache全entry下一批将真实16项NC/内存型MMIO/IO分别送入三S3来源排序，再经
  真实共享req/方向ack/resp、内部wake、Replay grant、三个bypass通道、原slot S3
  和VLQ完成；原普通Store同时保留到实际Sbuffer消费。两代新UID复用16个mid，
  旧数据消费后才重填，不以此规避已保留的“旧数据未消费即合法SID复用”失败。
  MMIO头只越过已正常执行的老uop；第二代最后一个MMIO可有异常，随后不再越过它
  宣称ROB退休。NC可在老Store头前发行，异常完成也不冒充ROB trap/退休。
- 真实NC RAR查询必须来自实际回包、Replay和bypass的NC数据，不能给缓存Load贴
  NC。年轻同line读者使旧Load nuke时，按NewLoadUnit.scala:1111-1115优先反馈
  C_UNCACHE并实际再发总线，不用C_NK或无新数据的普通S3掩盖重读义务。可同时
  由独立外部branch redirect取消年轻后缀（不声称RAR自动产生该redirect），
  清理年轻RAR后旧Load用新响应再查询/完成，取消者同LQ物理槽的新UID也必须真正
  总线/bypass/VLQ完成；退休但Sbuffer未消费的老Store原字节必须保留。
- `lsq-uncache-population-01`保留三个NC代理超时：在全部回包后固定等程序序下一
  UID，但Replay正保持另一个合法有效候选。原逐拍参考与DUT一致，并非RTL失配。
  更正为公平消费实际可见候选，VLQ仍严格检查连续已完成前缀；不能把grant当退休、
  伪造顺序或放宽原PA/字节/错误/UID完成要求。旧结果/335源保留，须新目录重跑。
- Replay剩余严格保存补例同时使lane1/2携带两个独立MA strict原Load，lane0携带
  另一单hot TLB原因；填120项并由实际Store7 STA/STD/wake及TLB广播解除，再逐
  原slot反馈/完成。这与单MA轮换不同，不能用已命中的单路保存路径抵消该缺口。
- 共享恢复补例保持老普通Store的原字节至实际消费，对16个真实Uncache entry
  分别检查MMIO未到头、NC弹性请求背压、已发待响应、回包wake和已回包待bypass
  的取消。弹性请求在redirect后仍按原UID接受/ack/resp；已发请求必须全部真实
  回包，丢弃只指取消Load不再bypass/S3/VLQ完成，不等于免除外部响应。逐mid的
  wake取消先真实返回该mid的原SID，再在下一拍redirect；其他15笔照常回包。
  取消的每个LQ物理槽均由新UID完成完整总线/Replay/bypass/S3/VLQ生命周期，
  还要实际重用原mid集合；不能只写恢复指针或用另一槽新事务证明取消安全。
- LQU容量拒绝补例用真实14/15/16项占用、三路逆序原S3和原ROB/FTQ/checkpoint
  检查最老被拒者的完整rollback；该公开rollback成为真实shared flush-self。
  已接受老项不可取消或重复总线请求；被拒后缀恢复后同LQ槽的新UID再完成。
  真实请求数/响应数/数据消费数与被拒者分列，不用填池或rollback.valid代替完成。
- reset补例使用共同系统reset边界：同一reset同时撤销外部代理中尚未响应的
  已发事务和本地所有旧UID，并逐笔记录external-reset-aborted，而不是伪称回包/
  消费完成。reset后迟到旧响应不属于该共同reset合同，不冒称本批已验证；普通
  redirect绝不享有此豁免。活动reset不能重开启动unknown屏蔽，非reset历史
  busy/perf/bypass/异常寄存仍按真实时序核对，旧槽新UID必须实际完成。
- `lsq-uncache-recovery-01`保留23例中的5个代理身份歧义失败：严格逐拍检查已通过，
  代理却允许所有取消且未发者匹配后来的同ROB/PA新代，导致新请求同时匹配旧UID。
  更正为只登记redirect前真实可见弹性包的原UID可迟发；不扩大取消豁免、不改
  DUT期望/刺激，原源/失败保留后新目录重跑，原UID与同地址新UID仍严格分代。
- 两分支同时取消补例同时保留真实PSQ/VSQ旧Store和120个TLB阻塞Load，向真实
  RAW56/RAR96查询并按共享redirect取消全部，不能只测Load后缀。新UID重填相同
  LQ/SQ/RAW/RAR/Replay容量后通过实际grant/原slot反馈、VLQ、原Store字节完成。
  RAW/RAR查询地址仍来自已dispatch的原Load，不伪造内部full/head或NC属性。
- 已退休前缀恢复walk在14个已执行但Sbuffer背压的Store中，只把前10个真实ROB
  退休，下一拍取消第11个后缀；真实两分支恢复必须保留exclusive SQ11及未消费
  老字节。跨页UQ另用两个真实second-page请求填满后取消后缀/全部，并要求同SQ
  物理槽新跨页UID的两段原PA字节真正消费，不能只用普通对齐Store证明UQ复用。
- `lsq-shared-recovery-01`保留13例9PASS/4FAIL及342源：三个失败是参考RAW沿用
  独立叶子“地址就绪只前进”的输入域，拒绝真实SQ恢复后的指针回退，并非DUT
  不匹配；`NewStoreQueue.scala:1883-1887`明确恢复可回退。仅在父级组合允许附近
  signed环形epoch，仍逐拍比较真实SQ反馈且不复活已释放记录；独立RAW原默认域
  不变。另一个失败是参考把UQ恢复误接到晚一拍的PSQ保存寄存，实际原样SV
  `PhysicalStoreQueue.sv:16062-16068`与Chisel1623直接接入VSQ公开恢复输出。
  更正精确连接，不屏蔽ready、缩小刺激或改RTL；旧37FAIL及旧210原始采样须重审。
- 共享pending reset另单列Load弹性包、串行NC/MMIO等响应、16个NC在途和Store
  IO/NC等响应。Store已实际req.fire的外部写接受是既成事实，reset不能撤销；
  只中止其本地UID及外部未响应义务，不标为“未产生副作用”或完整Store完成。
  reset后新Load使用真实总线/Replay/bypass数据、新Store原字节实际消费，旧SID
  可由共同reset释放，不能以不重用ID掩盖残留。reset与bypass流水相遇时，实际
  无reset历史的旧s1/s2输出仍要精确核对，不能笼统要求reset后立刻所有valid0。
- `lsq-pending-reset-01`保留6例4PASS/2参考FAIL与343源：Load弹性valid和entry
  MMIO选择是异步reset，参考却在首个reset前采样保留旧值，造成req.valid与
  下一拍Wrapper busy错误。依据`PipelineRegModule.sv`和UncacheEntry.sv236-247
  仅更正异步控制的reset视图；`LoadQueueUncache.sv:2749,3558-3562`的bypass和
  entry异常仍是无reset历史，新增实际s1数据→reset拍s2数据/错误例验证保留。
  原失配/来源保存，不改RTL，不跳过reset边沿，也不重开首次unknown屏蔽。
- `lsq-expanded-12`的253例216PASS/37FAIL原生回归不能直接作整批合法验收：独立
  审计抓到三个return_alignment前导例把ROB1..3分配在公共pending=9之后，违反
  正常生产者退休域，虽未发生模型/DUT失配仍拒绝计合法业务。更正仅把该前导
  pending设为ROB0，原事务执行完成后仍正常推进到9；不改变被取消的128个原
  owner、96RAR/56RAW/120Replay容量、同槽新UID完成或原37个真实FAIL。原12轮与
  首审拒绝保留，须新目录重跑并验证旧210全部原始历史不变。
- 剩余路径补例先定义：三路S3同拍各携带独立单hot MA且strict=1，真实填120项；
  先完成0/1/2个真实Replay前导以移动分配对齐，错误SQ0 wake不得解除SQ7，第二
  路匹配SQ7 wake与同一Store实际STA/STD后才允许grant/原slot反馈。不是多hot
  刺激，也不拿两MA+TLB例代替三MA级联写入优先。
- Replay变长回收先真实grant全部120个原UID但不假造完成，然后按程序序取消
  不同长度年轻后缀；在幸存原slot仍被占用时分配相同数量新UID，实际新grant的
  slot集合必须恰好等于被取消原UID的slot集合，再反馈幸存/新owner并完成。
  Uncache变长恢复另保留1/2/3个老Load，其余真实已发后缀取消，先偿还所有原
  响应并完成幸存数据消费，再同LQ槽重发新UID完整完成；没有reset豁免。
- RAW高选择组正例必须来自真实56项原Load记录与真实56个老Store依赖，保持
  SQ地址缺口到目标组的真实STA。每个高组和两个STA来源分别产生完整最老恢复
  元信息/MDP训练，随即按该公开rollback作共享redirect，取消后缀同LQ新UID
  必须经实际Store逐PA字节forward及S3/VLQ完成。幸存旧Load以实际SQ就绪解除MA
  并反馈原slot；不得把56项无冲突容量对照或未完成旧UID当作正选择检查。
- PSQ每槽CBO下一批由真实VSQ ROB头许可，两个STA来源分别运行全部64物理槽、
  CBO0..3和完整SQ256编码。非zero实际Cache req/resp、zero自己的零字节Sbuffer
  消费、原ROB/VA/hyper WB.fire及随后SQ释放均须完成，同时年轻原缓存Load完成；
  每个owner都完成后才重用同槽，不仅写属性再reset。干净响应只证明保存/完成
  的本情形，原错误响应背压WB/zero/完成顺序FAIL仍保留，不冒称已修复。
- entry0精确取消例在原S3两拍后、尚无顶层弹性请求时发redirect，以公开流水
  合同定位entry的request阶段；断言无外部req.fire/ack/resp义务，再将16个新UID
  真正送总线/bypass/VLQ完成，原LQ0与mid0都须有实际复用，不能借buffered例。
- 第一批27例后仍缺两个真实父池的53条返回写入情形。下一补例先完成1/2/3个
  原Replay或Uncache前导UID以移动**真实**返回尾对齐，再重复全池/变长后缀取消
  和同槽新UID完成。前导与主事务都守住ROB退休域，不改私有free指针/人为指定
  分配slot，不把多个独立DUT覆盖合并成Wrapper覆盖。
- Uncache返回落点的剩余情形再用9/13笔完整NC前导推进真实返回尾，然后16项
  中保留3个老Load、取消13个年轻后缀并偿还全部响应，重发同LQ新UID至实际消费。
  这是父池批量归还落在队列尾附近时的身份保存，不用私有返回尾或单独FreeList
  刺激伪造本层可达性；前导、幸存及新owner都须实际完成。
- 完整混合随机的后续用例前门禁：使用**一个绝对ROB时间线**生成正常混合程序，
  映射到完整640编码并保持活动半环合法；SQ/LQ按绝对代记账，不能沿用
  MemoryOwners的raw ROB排序/最大值退休或直接放大只支持两个NC Load的BusOwners。
  外部ROB只能越过真正执行完成的连续前缀；普通Store可以在头preCommit，已
  退休但未Sbuffer消费的老Store仍保留，不能增加read==head限制规避完成顺序。
- 随机生产者须支持实际0..128 SQ虚拟占用/64物理发行窗口、120 LQ与父池容量，
  不能为方便参考把合法容量压成64或只做单侧压力。三个Load查询/S3/Replay与
  两STA/STD/S2、真实Cache/Sbuffer/Uncache响应共同调度；每一请求仍绑定同一
  原UID/PA/uop，前拍STA属性与当前S2对齐，原slot反馈可再次重放但不能伪造完成。
  RAW/RAR拒绝和公开rollback必须依实际容量/原字段处理，不外驱内部full/head。
- 固定种子全域不得按known-issues筛掉别名、split、strict、SID合法立即复用、
  error/WB背压或年轻特殊Store越过未消费老Store的真实许可情形。必要条件对照
  可单列，但不能代替完整域；失败普通保留并继续其他种子/有意义范围。Cache和
  bus接受、方向/mid/SID ack、resp、Load数据消费、Replay grant/反馈及队列释放
  分别记账；SID响应后即可复用，不能延长到旧Load消费。异常完成不是正常ROB
  退休，须明确trap/redirect边界；普通redirect不豁免任何已接受外部响应。
- 公平排空须在停止新随机分配后保证外部ready、原job ack/resp、Cache/refill/
  TLB和实际候选消费最终服务，仍须所有未取消原UID真正完成及全部取消/reset
  同物理槽新UID完成。reset使用已定义共同系统边界并显式记录中止，不静默删
  外部账本。只达到固定拍数/队列empty、定向全池、协议probe或当前DA清单闭合
  均不能勾选LSQ-STRESS的三个checked情形；扩大后仍需新目录/对应独立历史门禁。
- `lsq-seeded-mixed-01`首8种子全部停止，不能直接作合法RTL缺陷证据：新代理
  将Sbuffer两ready独立随机，产生逆前缀，违背真实`Sbuffer.scala:380-381`的
  ready1受ready0门控及`NewStoreQueue.scala:1407`的fire前缀。按既有ESB合同
  更正为前缀ready（仍随机单/双消费和背压），不改参考FIFO或目标RTL。首轮另
  有Store总线UID误匹配已取消的同ROB/PA旧代、CBO仅凭PA/opcode匹配多个活动
  owner；分别保留当前有效Store代及真实ROB头许可/未请求身份。Load弹性旧请求
  的迟发/偿还义务不因此删除。原356源/8FAIL及全部采样保留，须新目录重跑；
  合法固定种子全域、SID立即复用、真实CBO/零写/背压域不因代理修正而删减。
- `lsq-seeded-mixed-02`已纠正ready/身份代理并保留8FAIL，但独立v1审计进一步
  拒绝16字节Load的原mask与实际Replay mask不一致：size=4仍被代理标为scalar、
  原mask=0xffff而实际Replay scalar byte-count取低两位后为1。不能只相信严格
  staged参考一致就宣布正常producer合法。更正保留原16字节宽度，设置真实
  vector/aligned_type及integer/vector写回元信息；不删该流量、不放宽独立mask
  检查、不改目标RTL。前两轮356源/8FAIL及原v1审计器均保留，须新目录重跑并
  重新审计所有公开身份/生命周期；此前的data/WB/req失配暂不作整批合法验收。
- 第三轮8种子修正vector后，独立混合v2审计核验实际前缀1901记录/2988UID、
  92次真实shared恢复；未到达的fair/reset/完整容量/同槽恢复不计通过。v1审计
  另在03误将“已need_rep反馈、无当前grant但仍有slot lease”的取消者留在slot
  表，造成新UID合法重授予的假碰撞；保留原v1，v2按取消原UID释放lease而非只
  看grant!=None，活跃身份/反馈检查不放宽。第三轮未执行fair却在run入口先mark
  reached，不能凭该bin计到达；下一轮仅将fair reached移到真正drain入口，须
  逐bit证明全部实际事务历史不变，仍不设checked。
- 混合种子28934/28935在s1干净错误字段下推进到真正s2，暴露旧返回SID数据被新
  SID响应污染。下一定向例用两个真实NC Load、共同正常ROB，旧resp后才复用SID，
  两笔均error=nderr=0但原字节不同，三个bypass来源分别核对原s1及s2；不同SID
  作为必要条件对照并须两Load完整VLQ完成。同SID失败不因s1 metadata碰巧相等
  被放过，不延长SID占用到数据消费，也不以新数据/旁路参考或probe替代原s2。
- `lsq-mixed-data-04`的8混合原始历史与03完全相同（只将未到达fair的错误mark
  移走）；新6个SID例原生3PASS/3FAIL，但独立v3拒绝其Replay.fullva一致性，因
  直接复用旧BusOwners的独立接口fullVA=0xABC...与q.vaddr=0x4000标签。新正常
  producer复现应在分配前将同一Load.fullva绑定到该Load.execution.vaddr；只改
  新6例，不改旧297冻结历史、原SID复用时机/数据/ROB/PA或任何参考期望，不把
  旧接口元信息保存刺激提升为正常Backend数据流证明。04/原v3拒绝保留，下一轮
  还须核验只有fullVA输入和对应异常VA输出改变，实际SID数据反例不得变化。
- 联合容量/公平阶段下一补例先使用同一程序序分配“64个老Store、120个Load、64个
  年轻Store”，共248个不同ROB身份，活动跨度小于320；Load的真实exclusive SQ
  边界是64，而不是将128虚拟占用误当128物理发行窗口。老SQ0保留地址缺口，其余
  老63项真实STA/STD；104个缓存Load进行同UID Forward/RAW/RAR查询，分别实际填
  RAW56/RAR96并观察后续容量拒绝，16个NC Load真实cause0请求填Uncache16，所有
  120个Load各以真实单hot原因进入Replay，均未反馈完成。只有实际同时保留这些
  原UID、SQ128/LQ120及未消费/未响应义务，才记联合峰值，不累加独立case容量。
- 此联合定向是原8个全域混合FAIL之外的补充，不修改/替换种子、不删除已知失败
  域。联合正例用不重叠且对齐的原地址，Cache/bus干净响应，年轻Store仍含NC/IO
  与全部CBO类型；这是显式必要情形，不冒称完整随机域已验收。新公平阶段真正
  停止dispatch，按轮转原UID及实际可见Replay候选服务，提供原STA/STD、匹配唤醒、
  TLB/refill、总线方向ack/resp、Cache应答及前缀Sbuffer ready/WB ready；结束
  条件是所有原UID/原slot反馈/外部job/片段和ROB合法前缀均完成，不是固定拍数或
  empty。超时仅为失败保护，不能当排空成功。三个STRESS总bin仍不因本定向勾选。
- 联合全满后另测共享redirect/共同系统reset。redirect后偿还每笔已接受旧job，
  不给取消者制造bypass/S3完成；reset逐笔显式中止尚未响应的外部job、不伪造回包。
  接着同SQ/LQ物理槽新UID必须实际完成；不能用同地址新请求冒充复用证明。正常
  执行至少三轮全容量，实际跨完整ROB640、SQ256、LQ240编码并分别分代；仅reset
  不能作为跨圈证明。活动reset继续用同一严格fixture/参考，不重启unknown掩码。
- `lsq-joint-capacity-01`六例保留364源/六个helper FAIL。公开历史已实际接受RAW56/
  RAR96，但新actor假设“旋转后的前56个UID”对应RAW分配前缀，最后两个credit实际
  按输入lane优先，第三个UID可能被接受、而另一个仍因真实SQ0缺口重放。将前19组
  （57个UID）都绑定同一真实SQ0等待，仍只实际分配56条RAW；其余原查询继续容量
  拒绝，不增池、不伪造失败原因、不改RTL/参考。旧首轮产物保持，须新目录重跑。
- `lsq-joint-capacity-02`修正lane假设后实际保留所有联合容量，六例却停在新helper
  错误的`io_sqFull==1`断言。该端口不是VSQ的128边界full：开源NewStoreQueue.scala
  2150接PSQ.full，实际PhysicalStoreQueue.sv16123为寄存计数`>128`而非`==128`；
  本工程既有严格参考也逐拍取`>128`，故正常128时真实值0并非新RTL失配。更正
  helper检查该保留信号为0，仍以128原虚拟UID/64物理发行、原释放credit验证满
  边界，不制造删除的canAccept、不增占用至129，不改RTL或参考。02/364源保留。
- `lsq-joint-capacity-03`为4PASS/2FAIL，普通/redirect已实际经过三轮联合容量及
  公平完成，两个共同reset在tick324停于perf17/24参考。FreeList.sv1217/2279、
  FreeList_1.sv728/1535、FreeList_2.sv1293/2782均异步清占用，因此reset拍
  LoadQueue.sv1023-1024的full_mask已为0；1060-1075的无reset perf流水应采集
  新事件0，但继续传递旧流水历史。父参考只更正reset拍新采集mask=0，不清流水、
  不开startup屏蔽、不改任何比较/目标RTL。原364源/两个失配保留，新目录重跑
  联合6例及受影响的原LoadQueue199/Wrapper311逐bit历史门禁后才采信修正。

## 6. 首轮适配/审计纠正的证据保留

首22例`lsq-initial-01`全部通过；独立审计v1错误把C_FF写成mask32，实际固定
源码`LoadQueueReplay.scala:55`为index4、mask16。保留原v1与显式拒绝记录，用
v2逐行重审全部720记录/44个完成UID，不跳过数据依赖、不更改DUT期望。

下一轮30例`lsq-expanded-01`为26 PASS/4 FAIL，四个Store NC/IO先停在参考
`KeyError: io_toUncacheBuffer_req_bits_cmd`，不是RTL输出反例。实际StoreQueue
该常量端口被删除，原SV`LsqWrapper.sv:4393`在Store分支直接提供literal1。
父参考据此取常量M_XWR，其余真实ROB/PA/data/mask/id/nc字段仍逐项检查；不制造
缺失child端口，也不放宽Store请求数据或完成。原304启动/结束源及失败保留，
必须新目录重跑全部30例确认。

## 7. 完整LDU生产者纠正与实际新增证据

CBO包及NoSpec/BlockBack只证明该许可，不代表整段LDU流水合法。旧RAR-nuke→C_NK、
任意延迟/换lane S3、缺revoke、MMIO replay查询由原UID-bound source-v3拒绝，旧8FAIL
不改、不认新RTL死锁。用例前新增[正常LDU路由](lsq-ldu-rar-routing.md)与
[全类型LDU混合](lsq-ldu-mixed.md)合同。

正常定向三轮15例12/3→16例13/3→18例15/3，自身26902→29161→30237/59602，
3335新增丢失0，前拍release普通FAIL保留。原8种子新混合实际2PASS/6FAIL，两PASS有
600随机/fair及148组全部取消同槽新UID完成，其他停止前缀不虚构完成。动态检查
固定S0/S1/S2/S3、18次head/tail/S4、25次MMIO禁查、原slot和真实STA-nuke；外部
DCache/TLB事件位未保留，不冒称原生LoadUnit UT。完整随机/STRESS、正常联合容量/
CBO分阶段、其余exact128和最终审核仍必需。
