# LoadQueueReplay：等待真实依赖解除、保序重发与同槽反馈生命周期

状态：**功能点在用例前定义；当前已实现并完成覆盖迭代，但127 PASS/4 FAIL、82/84 checked，仍未验收（NOT_PASS）。** 真实top为`LoadQueueReplay`，120项分3个40项bank，保留真实`FreeList_2`和3个`AgeDetector_36`实例（文件去重3份）。依赖两类叶子已验收；不借用它们的覆盖替代本父块真实连接。最终证据见第11节。

## 1. 实际公开接口与合法输入

三路LDU反馈用同一个入口表示首次需要重放、同槽再次需要重放、或者已完成而释放；三路输出用ready/valid将调度请求发回LDU。输出握手只意味着“已调度”，**不释放槽位**，必须等待反馈明确不再重放或redirect。独立参考应以UID、槽号、入队年龄、阻塞依赖、已调度状态和反馈义务建模，不读取DUT的allocated/scheduled/age矩阵或freeList寄存器作oracle。

- 初始RTL输入ready已常量化删除；与LQU不同，Replay没有容量nack/rollback。参考必须约束首次新入队不超真实预分配可用前缀，不把溢出当合法随机。
- 首次：valid && need_rep && !isLoadReplay && 未被当前redirect取消，按输入lane前缀压紧分配。无需重放的首次输入不占槽，即使cause payload非零。
- 反馈：isLoadReplay时schedIndex宽7，必须是实际调度后仍归该UID所有的槽，120～127非法；再次need_rep在原槽更新元信息/原因并重新允许调度，不新增容量或改变原入队年龄。need_rep=false释放该槽，无重复反馈；三lane不得同拍反馈/释放同一槽。
- req.uop包括ROB160的former/latter、LQ120指针、SQ64×2的两个flag和value、FTQ/RVC/checkpoint、fuOpType12、四类写使能、pdest8、storeSetHit/waitSqIdx/loadWaitBit/Strict。50位vaddr、mask16、NC、isvec/alignedType等按真实保留端口驱动。
- replay输出保留原uop（本配置5个源异常位在保存时清零）、vaddr50、fullva64来自vaddr零扩展、size3、mask16、entrance8、instrType3、mshrId4、replayQueueIdx7和forwardDChannel/uncacheReplay/ncReplay。不比较未定义payload。
- 两个store地址/数据wakeup、两个真实storeDataWrite、两路loadWakeup、两路L2 hint、慢/快TLB hint、MMIO/NC wakeup、SQ ready指针和64位ready向量均使用实际公开输入。SQ四圈编码不能当普通64项值比较。
- **当前生成top删除**storeAddrWakeupCancel/storeDataWakeupCancel、tlbReplayDelayCycleCtrl、debugTopDown、全转发full_fwd、replayCarry/replacement/missDbUpdated和多数vector元信息、输出cause向量。不得伪造这些端口或声称动态验证了被删除的cancel/调试/计时功能；上层集成若有相关边界仍另行审查。
- 有lqFull、replayAllocate、specialMode和13个6位perf事件输出，没有公开validCount。specialMode及事件必须按实际管线相位检查，不读内部计数器。

接口以原始SV及导出signals最终核对为准；若导出有额外删除或宽度差异，先更新合同再写对应刺激。

## 2. 原因不是任意多bit组合

源码列13种原因，低编号的生产者选择优先级发生在LDU：`mem/pipeline/NewLoadUnit.scala:1566,1615`用`PriorityEncoderOH(lqWriteCause)`生成写入原因，不能在Replay中凭空发明一个多hot原因编码仲裁器。普通合法入队使用**单hot**原因；zero cause但need_rep=true和多hot作为域外刺激单列，不用它们凑覆盖。

| 原因 | 等待/释放的微架构含义与必需反例 |
|---|---|
| C_UNCACHE(0) | 等对应LQ的延迟MMIO或NC wakeup；按LQ flag/value完整匹配，两个类型输入都可解除该层等待。输出uncacheReplay=true，ncReplay来自保存NC属性，不捏造该层类型门控 |
| C_SMF(1) | 等阻塞SQ已不晚于sqDeqPtr，不能在老store仍占用时重复猜转发 |
| C_MA(2) | 等store地址依赖解除：readySqPtr越过、非strict且ready位/物理upper允许、sqEmpty或延迟地址wakeup；wakeup必须仍在真实物理SQ窗口 |
| C_TM(3) | 等匹配TLB ID、慢hint replay_all、fast hint；tlb_full可直接不阻塞；S4延迟的非对齐头可消费额外一拍历史hint，普通load不能 |
| C_FF(4) | 等真正store数据就绪；新入队同时遇匹配延迟STD wakeup或本拍storeDataWrite可以不阻塞。只发生产者wakeup不等同于任意dataWrite索引都可解除 |
| C_DR(5) | DCache重放/资源失败，不需等待外部wakeup即可重选 |
| C_DM(6) | 已handledByMSHR的miss等匹配loadWakeup或L2 hint；普通/S4延迟头有不同历史refill窗口。MSHR ID和last-beat元信息保持至再次重放更新 |
| C_WF(7) | way预测失败可直接重选，仍保留原load的恢复身份和size/mask |
| C_BC(8) | bank冲突可直接重选，不把输出握手误当完成 |
| C_RAR(9) | 等rarFull解除，或自身LQ已不晚于ldWbPtr，不能把另一个LQ的进展误当许可 |
| C_RAW(10) | 等rawFull解除，或阻塞SQ已不晚于store地址ready指针 |
| C_NK(11) | 违例重执行可直接重选；redirect仍可取消，不能向已取消UID重复发请求 |
| C_MF(12) | 源码含`assert(false)`/TODO保留原因，不作为普通合法事务。即使release SV保留输入bit但删除断言，也不能宣称其为架构支持的重放流程 |

非handled的C_DM不能凭印象假设自动非阻塞；按实际源码和公开行为检查并记录合法生产者域。原因可在同槽反馈改变，普通“高优先”选择组为C_DM/C_FF/C_UNCACHE，其余为低组；输出entrance高优先仅C_DM/C_UNCACHE，**C_FF的选择高优先不等于entrance编码也高**。

## 3. 三bank选择、年龄与背压

slot按`slot % 3`映射固定输出lane，每bank40项，不等于输入lane归属。一般情况下，各bank先在可调度集合中选高组，否则低组，再按首次入队年龄选最老；同拍多入队按入口顺序形成年龄，不以槽号、ROB数值或最近反馈时间作年龄。

程序头部窗口覆盖一般年龄：ldWbPtr相等者最高优先，其后+1～+3的可调度记录优先，再由该bank低索引选择窗口候选。必须比较它与高/低组、入队年龄同时存在时的真实选择；不能只测试每bank单个记录，也不能把LQ120回绕当2幂截断。

输出有一个“选择→保持发送”级：ready=false保持同一UID和所有适用payload，不能重复调度或吞掉请求；选择时即标scheduled，输出握手后等待LDU反馈。redirect可抑制当前s1以及已释放的s0旧选择，取消和同拍新入队/反馈分别按规定边界处理。

连续重放有16循环的冷却控制，阈值12：饱和段禁止接入新的选择，但**已握手的s1请求仍必须清空**，不能在无法接入新选择时把旧valid重复保留。实测准确边沿，参考按连续实际握手历史推导，不用固定sleep把比较绕开。

## 4. wake/hint相位与历史窗口

store Addr/Data wakeup、loadWakeup、慢TLB hint、MMIO/NC wakeup各一级本地延迟；fastTLB和L2 hint使用当前到达拍。不能把所有wakeup统一延迟或统一即时。

- C_MA/C_FF检查两个store lane和完整SQ多flag，地址wakeup还有`withInPhysicalQueue(sqDeqPtr)`过滤；strict、ready位、ready指针/upper、sqEmpty正反条件各自可观察证明。
- C_FF入队当拍同时匹配**延迟wakeup**或**本拍实际storeDataWrite**可直接非阻塞；错SQ、错flag或禁用payload不得触发。已驻留C_FF的其他ready路径与新入队快路径区分。
- C_DM的新分配/再重放：普通load接受当前与前一拍本地refill，rep_from_unalign_head另允许额外一拍历史；更旧的孤立refill反例必须不解除。正在保存MSHR ID的当拍、下一拍命中需分开。
- L2 hint先按mshrId匹配一次；isKeyword与dataInLastBeat决定本拍解锁第一beat还是把另一beat延后一拍。不能又用延迟hint重新CAM产生过期匹配；两channel同一个MSHR重复命中属于源断言非法域。
- 慢TLB匹配ID或replay_all，本地延迟；fastTLB仅匹配ID可在选择拍直接把阻塞C_TM纳入候选。S4非对齐头的慢hint历史只对其有效，普通load不得误捕获。

storeWakeupCancel输入在当前top已删除，不能按Chisel中的scoreboard注释声称已测试“wakeup被生产者撤销”的真实动态路径；需明确为配置优化边界，而不是假装已经通过。

## 5. 正常反馈、取消、reset与重用

同UID可多次调度→重放反馈，始终只占一个slot，首次分配年龄保持。need_rep=false反馈才正常释放；共享redirect按ROB slot年龄取消，冷却/背压或历史hint不能让取消UID重新出现。多路正常完成和redirect同拍同槽只释放一次；域外重复反馈/同拍多写同slot另列，不能作为普通随机。

归还仍经过真实4通道FreeList积压和预分配延迟，满池释放不能假设同拍立刻可用。活动reset中断旧反馈/wakeup义务；重用必须有新UID的实际replay输出及反馈释放/容量证明，reset中断不当正常完成。

## 6. specialMode与可观察事件

aligned ROB-head eligible请求写入触发观察窗口；只要ROB头不移动，计时持续，不因同槽重放反馈或原因更新重新开始。2048边界后specialMode经真实寄存输出，ROB头移动解除；同entry former/latter变化也算头变化。头不匹配、specialModeEligible=false、当前redirect取消不能冒充触发。

specialModeRequest标记的较年轻C_TM反馈不应等待常规TLB唤醒；该标记来自上级LoadUnit被特定模式杀掉的请求，不能把任意普通C_TM都设该位以绕过等待。边界和普通反例分别检查。

13个perf输出是事件，不是常驻累计值；当前生成件保留两级事件寄存。0/1/2分别新输入握手/实际replay握手/输出阻塞数，3为full事件，4～12为RAR/RAW/NK/MA/TM/BC/DR/FF/**DM**入队事件。该映射在功能用例前已逐项核对原始SV 61622～61727；此前合同将最后一项误记为SMF，现修正文档，不改DUT。需逐一核对真实条件和相位：new输入计数不自动等于实际新分配，不能靠perf代替生命周期。未保留的SMF事件输出、驻留时间直方图、每原因统计、scoreboard/cancel统计和debugTopDown不能动态声称覆盖。

## 7. 用例前语义功能点和公开证明

| ID | 微架构行为 | 必需情况 / 完成证明 |
|---|---|---|
| LRQ-RESET | 清空全部所有权、已调度和输出义务 | 初始、阻塞、选择保持、反馈、冷却、special窗口；新UID完成 |
| LRQ-ADMIT | 首次入队只给真实需要重放的load分配 | 3lane稀疏/连续、need_rep与cause分离、当前redirect、完整池不隐藏分配 |
| LRQ-OWNER | 已调度记录等待反馈而不是输出即释放 | 正常反馈、同槽再重放、原因/元信息更新、无重复输出、反馈lane变化 |
| LRQ-BANK | 真实slot映射到固定输出bank | 全120项/3入口、3bank并行、40项bank内年龄、回收后重用 |
| LRQ-ORDER | 头窗口/高低组/首次年龄共同决定候选 | 4个LQ窗口位置、same ROB slot和回绕、反馈不改年龄、bank内反序 |
| LRQ-HOLD | 输出阻塞保持身份和完整payload | 三lane独立ready、取消/空拍、同拍发送与换入，无重复调度 |
| LRQ-COOLDOWN | 连续重放受控冷却但已发请求必须离开 | 12/16边界、持续3bank压力、ready打断和redirect恢复、实际握手唯一性 |
| LRQ-CAUSE | 每种合法原因等待正确依赖或直接重选 | 表中0～11各自正反例；12和非法原因域不冒充普通支持 |
| LRQ-STORE | store指针/ready/真实写入解除依赖 | Addr/Data两lane、strict、SQ四圈与物理窗口、FF同拍快路径、错误SQ反例 |
| LRQ-TLB | 快慢TLB hint按身份和规定相位唤醒 | ID0～15、replay_all/tlb_full、S4额外历史和过期负例 |
| LRQ-REFILL | refill/L2 hint按MSHR和beat解锁miss | 两channel、lastBeat×keyword、入队历史窗口、乱序和高位ID |
| LRQ-UNCACHE | 返回的LQ wakeup解除不可缓存重放 | MMIO/NC、flag/value正反、延迟和旧UID隔离、派生entrance/NC属性 |
| LRQ-PAYLOAD | 重放请求保留原load语义与访问范围 | ROB/FTQ/RVC/checkpoint/写使能/pdest，scalar size/跨16B mask、vector保留字段、fullva来源、异常清零 |
| LRQ-FLUSH | 取消阻塞/选择/背压/已发未反馈的所有者 | flushSelf/After、former/latter、ROB回绕、反馈/释放重叠及幸存者 |
| LRQ-RECYCLE | 回收延迟和多bank积压后无旧身份污染 | 120项非2幂、多池循环、同拍回收/入队、全部输出槽身份/容量证明 |
| LRQ-SPECIAL | ROB头等待2048周期后模式进入及头移动退出 | 阈值前后、eligible/取消反例、再反馈不重启、年轻C_TM模式请求与正常TLB反例 |
| LRQ-PERF | 公开事件计数和相位与实际事务一致 | 13输出逐项0～3、重叠事件/阻塞/full，不能冒充已删除统计 |
| LRQ-IDLE | 无效输入/非匹配提示不制造有效重放 | 空/占用、禁用payload、旧提示/反馈重用隔离 |

## 8. 首轮与覆盖迭代顺序

先核验原样3文件闭包、导出/初始化/时钟和优化后接口。再以独立所有权参考执行空闲、直接重选C_BC、阻塞C_TM匹配hint、不可缓存LQ唤醒、反馈正常释放，确认N拍分配/选择/输出/反馈及perf相位；逐一分析真实未覆盖行，不把原生smoke当功能通过。

按首轮缺口将每条可达行映射到上述既有功能缺情形或新增整体功能点；补全池、原因、提示前后拍、3bank、背压/冷却、恢复/重用和specialMode长等待，再跑完整定向和合法随机。功能checked等待真实输出及反馈完成/明确容量证明；报告真实失败与配置删除边界，保留每轮结果、快照和审计器，不以行满替代语义。

RAR-REL-001、LQU-SID-001和域受限LQU-MMIO-IF-001仍开放，不能因独立Replay进展将LoadQueue或整体LSQ标通过。

## 9. 用例实施前的适配证据（历史节点，不是功能验收）

已建立`suites/memblock/lsq/replay/types.py`领域事务和`codec.py`纯公开引脚适配：`tools/audit_replay_codec.py`按固定原始SV逐项核对**除clock外全部400个实际输入**，25个有效编码样本的名称/位宽完全匹配，并拒绝5个域/宽度错误样本，记录在`results/replay-codec-static-01/static-audit.json`及4份冻结源文件中。

该历史节点只证明输入适配没有伪造或漏掉端口，不代表DUT走钟、独立参考、输出检查、功能点checked或RTL覆盖。当时尚无Replay fixture、一般参考或原生功能用例；后续导出和功能证据另见下节，不能将适配静态检查追溯计作功能通过。

## 10. 首轮原生实测与补例前缺口

原生完整导出和实例化走钟已PASS，`results/builds/20261018T063105344803Z-load_queue_replay/report.json`校验3份原样RTL及包哈希，优化后400输入已由实际fixture绑定。独立参考以UID/依赖/选择快照和提示到达历史建模，所有DriveStable/RisingEdge观察（包括fixture切换空拍）都逐拍比较。

`replay-initial-01` **4/4 PASS**：空闲、C_BC直接重选且握手后仍占槽、C_TM错ID负例/正确慢hint、NC原LQ唤醒及正常反馈释放。实测即时可选记录在分配边沿后仍无s1输出，下一选择边沿后有效；握手不释放、反馈才使replayAllocate清空，perf逐拍按两级事件历史比较。

首轮本体**9560/25806=37.05%**，真实3文件闭包**13409/30500**，语义**15/82 checked**。原始needs_review清单保留；补例前对16246条本体缺口逐项映射：头窗口选择240条、各slot原因/NC/beat保存1309条、strict更新1200条、MSHR/TLB标签1193条、原uop/vector/vaddr及脉冲历史12299条、特殊模式5条。真实FreeList另缺845条回收路径；AgeDetector原生DA已满但父级顺序语义仍需验证。全部属于既有功能点缺少情况，不排除可达行、不把Age的行满当父块通过。

补例顺序：先全部合法原因、3lane/3bank及payload、store依赖快慢路径、TLB/refill/L2 beat正反窗口；再120项全池/回收/同槽更新、头窗口/高低组、背压/冷却、恢复和2048周期specialMode，最后合法随机与独立逐拍历史审计。每个普通checked须实际输出握手并正常反馈释放；取消checked须后续新UID完整完成。

首批`replay-directed-01` 42 PASS（7个全池例未选），覆盖12个合法原因、payload/store/TLB/L2和同槽更新。本体10503/25806=40.70%、44/82语义。`replay-expanded-01`完整53例为**52 PASS/1 FAIL**：120个C_MA都strict=true，addressReadyPtr仍0、sqEmpty=false时，仅地址ready位变1使slot0提前输出；公开uop.loadWaitStrict仍是1。记录开放LRQ-STRICT-001，保留原失败，不改模型或RTL。

根据该失败补充既有strict功能的两种情况枚举，而非删减原功能：`LRQ-STORE.strict_capacity`（全池不可用预分配输出不能影响旧owner）和`LRQ-STORE.strict_valid_only`（无效反馈payload不能清除活动owner的依赖属性），语义分母82→84，旧运行保持82的冻结定义。源861～865的strict清除并未被入队valid保护；对禁用payload切换isLoadReplay/schedIndex、三个入口和正常非strict/真正ready指针对照继续动态核验，尚未运行前不记作通过。

`replay-timing-directed-01` 15 PASS/3 FAIL：三个入口各自valid=false/isLoadReplay=true/schedIndex=活动slot时，都使strict load仅凭地址ready位提前重放；头窗口、cause优先、首次年龄及冷却定向通过。普通非strict等待者的禁用payload用例通过。将必要条件控制继续分为无效payload指向其他slot、无效非feedback编码、地址位未就绪，以及正常非strict依赖；不缩小合法invalid payload域来规避失败。

第二次逐行缺口审查：`replay-expanded-01`本体24665/25806=95.58%，闭包28742/30500，52/82语义；剩本体1141条分为头窗口196、strict并发分支360、各slot TLB依赖571、脉冲历史9、special5，FreeList另617条。补充120项发出后的3lane同槽反馈轮换（MA/TM各三轮）覆盖三个入口的strict/TLB更新；回收用先真实反馈0～3项改变FIFO尾对齐、再redirect剩余项、等待真实回收并整池新UID完成，覆盖4通道到各池写位置的组合。所有都归为既有功能缺少情形，不排除可达行、不借叶子结果。

`replay-expanded-02` **125 PASS/4 FAIL**，84 reached/82 checked，失败仅strict_capacity和strict_valid_only；本体25692/25806、闭包30386/30500。剩114条均为三个bank的程序头窗口优先编码器在bank-local索引3～39的选择（原SV10354～10592），属于既有LRQ-ORDER.head/near_head的高槽位情形缺失。继续补120个C_UNCACHE按真实LQ依赖逐组唤醒：只有前一组实际输出、反馈完成后才推进ldWbPtr，下一组才唤醒；不让指针跳过未完成load、不凭内部矩阵挑选，用原LQ唤醒及公开输出逐项证明所有slot在head/near窗口被选中，另以119起点跨120回绕。此项补例前已完成缺口分类，不删除原始分母。

## 11. 最终冻结重跑与未验收项

`replay-expanded-03` **127 PASS/4 FAIL**，84 reached/82 checked；本体**25806/25806**、真实3文件闭包**30500/30500**，最后114条全部由原始DA命中。两项strict语义仍失败，绝不因行满验收。

`trace-audit.json` 独立核验20954连续观察（20140非reset完整比较、810 reset、4失败），4748分配=4081反馈完成+540取消+4 reset中止+123失败结束保留，127成功例全部排空。全部360个首次输入lane×slot×固定bank组合各有真实输出及正常反馈完成见证；127份启动快照文件在结束时全部SHA一致。详见[报告](../reports/load-queue-replay-20261018.md)。继续独立Store模块，RAR/LQU/Replay缺陷及真实父级验收标准完整保留。
