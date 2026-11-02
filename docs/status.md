# 结构整合阶段状态

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


仓库名称为 `ucv4xs`，定位是基于 UnityChip 的香山单元测试；命令与 Python 导入名保持 `ucv`。

**后续默认基线更新（2026-11-02）**：按用户要求，将九个公开工程的根默认改为
`public-a0c2a26cb`，固定上游`kunminghu-v3`当次最新
`a0c2a26cbe3c862175174bad03a1a23c406315ed`；76条递归gitlink已核对，只有
`difftest`/`XSCache`相对旧基线变化。DefaultConfig与工具/生成参数保持，VAGQ internal
覆盖及旧`public-893e1580b`完整清单不变。本次未生成新RTL或构建/冒烟/功能回归，
下文协作检查点及所有旧PASS/FAIL仍归其原基线与源码，**不代表新默认已验证**。
配置继承/缓存分离检查通过，公共路径API默认已改为跟随根配置；新增两个反证修前FAIL、
修后随完整根测试 **268 PASS**。这些根自检不计新RTL构建或功能验收。
新缓存身份与旧版不同，旧native链接保持原状且会被运行前校验拒绝；后续需先
`ucv prepare public --require-unified-baseline`和`ucv build public --require-unified-baseline`。
已暂停的事务适配整体目标未恢复；见[基线记录](history/baseline-kunminghu-v3-20261102.json)。

**协作发布收尾（2026-11-02，按用户要求结束本轮连续推进）**：本阶段交付目录和接续
规则，不标全仓适配完成；整体未完成范围保留，收尾后暂停。统一协作入口为
[CONTRIBUTING.md](../CONTRIBUTING.md)，按工程/DUT分工、沿用既有命名空间/fixture/布局，
不为各AI新建外壳或批量搬目录。完整交接见[协作检查点](collaboration-checkpoint-20261102.md)。

当前根 **266 PASS**；ICache source`b48dc54b...`完整seed2 **567 PASS/3 XFAIL**，同源码
DataBank+MetaBank seed1/2各 **305 PASS**，原412项保留且判定不变、158新项均PASS。
新增MetaBank严格ABI/事务、SDK所有权、双相持续采样、tag/valid双来源与checked finish；
两SRAM DUT共享严格非零控制，修正释放预览相位、逐row reset清扫和停止consumer假收尾。
当前ICache owner访问351→327，其他DUT仍需适配；模拟宏不适用控制不冒称硅片DFT验收。

MainBTB source`606640...`完整 **2854 PASS/9 FAIL**、同源码seed1定向 **136 PASS/9 FAIL**，
源码/构建/产物已审计；九条FAIL实际恢复原semantic/shared-service比较，不再被次生缺
sample错误遮盖。十工程结构门禁和Skill能力检查通过，严格事务门禁仍真实exit1。
最新十工程collection **49078项**，source`602ea9a6...`前后稳定且4159文件逐hash匹配，
十任务exit0；初始45883及上一48809项无删除、逐工程相对顺序保持。collect-only不算
硬件PASS，CLI1仍保留IFU登记残余；不重标旧collection数字。
捕获本检查点时尚未创建新commit/tag/推送，HEAD当时为`0017350...`；该旧提交不包含上述
后续内容。用户随后已授权将阶段检查点、协作约定及新基线更新一并提交并推送；实际共享
版本以Git历史/远端main为准，不能只把旧HEAD交给协作者。以下历史检查点数值保留原义。

**最新检查点（2026-11-02，整体仍进行中）**：新owner基础设施门禁揭露的Sbuffer模型
驱动排空已修：保持原四笔入队/响应并加强无额外请求尾部，同源码seed1/2完整均
**66 PASS**，原66项判定保持。根从原257 PASS随DataBank报告桥接控制扩展，当前完整
**266 PASS**，含9条真正的fixture/report边界控制，没有改门禁断言或加豁免。Skill20篇/
锁定框架能力、资产10工程132 DUT/4820拟发布路径及diff检查通过；资产数字含cached与
untracked，不冒充纯tracked文件数。
FTQ四处运行时checker耦合已改为既有UID审计收据和独立场景oracle，当前完整已审计
**905 PASS/2 XFAIL**、同源码seed1定向**57 PASS**；原907项及顺序/判定保持，见
[收据边界证据](history/transaction-goal-ftq-receipt-boundary-20261102.json)。
当前严格静态报告FTQ/Sbuffer均0 owner访问，BPU24、ICache351和MemBlock/VAGQ其他
债务仍在，不能据局部清零签核。

MainBTB reset/disable typed终态、实际SDK比较交付及按UID/时窗索引已生产接入。定向
**2737 PASS/5既有FAIL**（native75/5、pure2662），sourceff41f...稳定且源码/产物/build
核验，所选旧项无删除/判定变化，新73自检PASS。旧完整08a1a...最后shadow矩阵因每沿
全历史扫描持续变慢而定向SIGINT中断，nativeexit130/manifest仍running，没有完整信用。
旧1000/16000历史、同200空沿访问40万/640万行；新索引均0，不删除历史。同源码完整
**2853 PASS/9 FAIL**（native159/9、pure2694）、seed1选测124 PASS已审计，但七处原始
语义错误被后续缺sample见证的次生错误遮盖；新red确认后已修原错误优先传播，纯11控制
PASS。新source606640...完整BPU回归已启动，继续审计诊断而非只比较FAIL数；只冻结BPU
范围，不用全仓待锁collection阻止独立工程推进。见
[终态/索引证据](history/transaction-goal-mbtb-disposition-index-20261102.json)和
[Sbuffer来源修复](history/transaction-goal-sbuffer-timeout-source-20261102.json)。

最新**已审计**十工程collection为**48809项**，source0078a318...稳定且逐文件匹配，十
收集任务exit0；初始45883及上一48673均无删除/相对顺序变化。该总数早于本次终态/
索引/closed-send/reset控制，不能外推新总数或当硬件PASS。ICache closed-send已生产修复，
完整**327 PASS/3 XFAIL**、同源码seed1选测**103 PASS/1 XFAIL**，原项判定保持、新1
native自检PASS；随后DataBank reset接入SDK唯一所有权/严格预拒绝，同源码seed1/2各
**58 PASS**（31native输入/27纯控制），新增9自检PASS、原reset相关5red同探针修后PASS。
之后DataBank持续lossless双相frame/逐输入UID/raw66存储来源/默认自动读检查和严格fixture
finish已生产接入，不再由功能体手改model或直接driver。v4完整ICache **401 PASS/3 XFAIL**、
同源码seed1选测 **177 PASS/1 XFAIL**，source6a5d865...稳定且源码/构建/产物审计，旧330项
及相对顺序/判定保持、新74 selftest PASS；原8条runtime red同探针修后8 PASS。v5另补6条
跨MBIST/功能/reset控制，定向22 native PASS，当前source4003a071...完整已审计
**407 PASS/3 XFAIL**、同源码seed1 DataBank **129 PASS**（53 native用例/76纯控制、55
native实例），旧项/判定保持。非零DFT控制语义、进一步
组合生命周期和其他DUT/所有其余工程仍必需。详见
[DataBank持续账本](history/transaction-goal-icache-databank-continuous-20261102.json)。
v5后又补首沿前read/reset取消控制，证实旧finish会先推进4/2tick执行取消计划才失败；
现生产在任何drain tick前拒绝未发射计划/reset日程，定向24 native PASS，当前完整v6
source11cbc636...已审计 **409 PASS/3 XFAIL**、同源码seed1 DataBank **131 PASS**，旧
330/410项及顺序/判定保持；55 native用例/76纯控制、57 native实例，全部产物/build hash
核验，native未重建。前述407/3保留前一源码含义，不与当前结果拼接。
以下按先后保留此前检查点的各自源码和结论边界。

**此前检查点（2026-11-02）**：IFU七DUT当前适配保持完成；BPU共享
pipeline/PHR/short/positive检查点686 PASS及seed2 12 PASS。FTQ两个leaf现已完成当前
事务迁移；Ftq顶层callret/commit子链检查点完整**410 PASS/2 XFAIL**，同源码seed1
定向146 PASS、根**242 PASS**；之后其余五通道已接自动比较、输入UID/仲裁/重试和本地
有界收尾，最终v4完整**905 PASS/2 XFAIL**，前412项判定保持，新495项均selftest。v3的
903 PASS/1 FAIL/2 XFAIL唯一FAIL是旧自检固定通道数9，现改为完整固定10通道集合；
最终同源码seed1定向**122 PASS**、Ftq收集907项，当前三个FTQ DUT的事务适配范围已核验。
整体前端/全仓目标继续，不能由此关闭；
MBTB/其他BPU、ICache及MemBlock/VAGQ和最终验收仍必需。全仓最新完整collection
**48673项**（MBTB事务v5检查点；后续训练账本新增项尚未计入），初始45883及前48424无
删除/相对顺序保持，十任务exit0；CLI1仍是IFU残余登记，见
[收集对账](history/transaction-goal-collect-mbtb-transactions-20261102.json)。详细
证据见[ResolveQueue检查点](history/transaction-goal-ftq-resolve-transactions-20261102.json)与
[Ftq整槽检查点](history/transaction-goal-ftq-top-slots-20261102.json)。随后新red控制确认
PredictionSpec/allocate计划和直接预览metadata不可变性仍有缺口，继续修复，不重标旧结果。
这些输入/快照问题已在后续源码修复，原8条red探针修后PASS；新完整373 PASS/1 FAIL/2 XFAIL
和seed1 138 PASS/1 FAIL的唯一错误来自新增控制在redirect后未重新分配就写meta，现补
合法前置而不放宽PNR不变量。额外三个native commit观察注入均证实仍缺自动比较，正接入
输入UID/FIFO与metadata来源、完成/取消账本及有界自主消费尾部。meta无复位store在reset
有效沿仍可写的边界也已由red/green及原生控制核验，commit子链410/2与seed1 146保持原
356项判定、新56项均selftest；其余五通道auto-compare red均保留为真实未完成项，见
[顶层commit实施证据](history/transaction-goal-ftq-top-commit-20261102.json)；不据此签核整个Ftq。
后续首版五通道完整418 PASS/4 FAIL/11 ERROR/2 XFAIL保留原记录，差异为same-flag位宽
回绕、旧IFU字节/半字PC混用及原功能体未消费训练。现保留first-owner oracle，显式转换
三个IFU PC并在5个原功能体末尾追加排空；7个原文件AST除此保持。完整字段/元数据来源、
receiver分义务、request重试及禁止自动清债的边界见
[当前组合合同](../suites/frontend/ftq/docs/transaction-adaptation.md#五通道组合检查当前实现)。
7个覆盖产物/235个原生输入/18个构建文件哈希核验，构建未变；额外5条严格
ScoreboardMismatch原生探针通过，排除了训练收尾的通用AssertionError假救活。中间判定、
源码及最终待办见[五通道机器记录](history/transaction-goal-ftq-top-frontend-20261102.json)。
MBTB当前基线为2257 PASS/229 FAIL（native101/24、pure2156/205）。两条纯red证实旧
cleanup仅2-way预期且漏掉4-way中只有两路有效的观察；现四路输入LRU计划、完整4×4
shadow、真正zero-tag输入、clear属性及三组纯适配已修。v2的544纯检查通过；后续guard
改为完整4路且恰2路有效后，完整v3为**2539 PASS/12 FAIL**，12个cleanup原生场景通过。
shared-service/owner和严格域、嵌套快照、固定ABI、有界finish继续适配：seed2定向
**2599 PASS/5 FAIL**，后续seed1定向**88 PASS/5 FAIL**；来源/产物/构建逐项核验，真实
反例不豁免。两次定向源码因新增高guard消费者不同，不冒称同源码双seed。随后完整MBTB
事务v5已审计为**2723 PASS/11 FAIL**（native121/11、pure2602），其中两条是排空时多走
一沿引入的适配回归，不当作硬件缺陷；其余九条真实功能反例保留。后续生产训练账本按
发射前UID核对完整wire，区分实际接受/disabled过滤/reset取消/未发射取消和精确终态；
实际RisingEdge采样代替可撤回的DriveStable预览，修复取消后的幻影接受。定向v2为
**2643 PASS/5 FAIL**，44项新增自检PASS、两条排空FAIL→PASS，所选原项无删除。
根回归再次**242 PASS**；当前训练账本源码完整v4已核验**2780 PASS/9 FAIL**
（native137/9、pure2643），原2734项无删除、两条排空适配FAIL→PASS，新55自检PASS，
源码9f6825...稳定且审计匹配、146native输入/产物/构建hash核验。同源码seed1定向已审计
90 PASS；前一个完整尝试因外层600秒超时而中止，不给完整结果信用。后续lookup输入UID/
S0/S1/S2/SDKlaunch与实际tick/响应frame owner和metadata祖先已接入：来源定向v2为
2686 PASS/5既有FAIL，后续修复replacement场景把改写expected当source的刺激漏洞。
当前08a1a...源码seed1定向**105 PASS**（51native/54pure），来源/产物/构建已核验；
完整MBTB及新十工程collection仍待通知/审计，不拼造最新总数。中途disable和已接受响应
句柄的reset终态已有两条native red，仍需修复，不将正确拒绝stale frame误当该合法控制
场景已完整适配。其余API/生命周期仍必需；不将静态零命中或旧0 setup ERROR当迁移完成，见
[事务证据](history/transaction-goal-mbtb-transactions-20261102.json)及
[训练输入证据](history/transaction-goal-mbtb-training-inputs-20261102.json)。
最新lookup/来源与剩余reset/filter反证见
[机器记录](history/transaction-goal-mbtb-lookup-source-20261102.json)。

ICache同时补DataBank严格域/完整深只读快照及首响应取样，不再按expected payload选择
后来的响应；同源码seed1/2各43 PASS。共享LevelDriver的71处构造位置接入SDK输入claim，
完整ICache**326 PASS/3 XFAIL**、同源码seed1选测**102 PASS/1 XFAIL**；原294项无删除/
判定变化，新35项selftest PASS，全部11DUT的66个构建文件与覆盖产物hash核验。零沿set
不是接受；新发现已close后的send会先重新claim再抛closed，保留native red待补，其他
reset/MBIST所有权、持续采样、UID和finish仍必需。见
[DataBank证据](history/transaction-goal-icache-databank-domains-20261102.json)及
[level所有权证据](history/transaction-goal-icache-level-ownership-20261102.json)。

后续严格门禁补查owner的driver/ports/model/monitor和私有编码/边沿访问；旧pin/signal
计数未改。10个修前错误清零控制已在预期断言red，修后拒绝与合法对照通过，但新报告仍有
BPU24、FTQ4、ICache370、LSQ121、MMU53、Sbuffer1、VAGQ32处基础设施访问。当前根
回归真实为**256 PASS/1 FAIL**：Sbuffer旧功能用例用`env.model.lines`决定排空，必须修
功能来源，不能删除该门禁断言；不能继续引用此前242 PASS作为新门禁源码全绿证据。
工程源码在完整MBTB/十工程collection期间仍冻结；reset/filter原生15控制及原20生命周期
用例已在外部原型通过，closed-level guard原型1 PASS，DataBank连续输入/响应原型10
PASS，但均未合入生产，不给迁移完成信用。新增八条DataBank原生反证与实际MBIST
ack/完整66-bit响应相位同列待修合同，详见
[新门禁/原型机器记录](history/transaction-goal-component-boundary-20261102.json)。
以下旧检查点的数值及源码哈希按各自运行保留，不冒称对应当前完整源码。

**2026-11-01 新全仓适配目标（进行中）**：按用户 /goal 创建独立活动目标，覆盖十工程
132 DUT 的全部框架事务/迁移适配，不继承旧目标的过强 complete 结论。初始收集45883项；
已完成 IFU 七个DUT（包括Ifu顶层）的当前框架事务适配、严格合法域、
分阶段采样/身份和有界收尾；修复fixture切换时组合旧样本及native seed固定为1的问题。
最新完整 IFU 为 **719 PASS / 5 FAIL / 1 UNCERTAIN**：保留R-13两条FAIL及R-14的三条端口
合同反例。R-14原生产可达论证因短non-taken窗口不符合真实FTQ规则而撤回；严格生产者
对照均正常，不能把真实native端口FAIL自动称生产缺陷。相对上一uncache检查点的643项，
新增82项全部PASS、原判定逐条不变；新增内容补齐raw字节与派生描述对账、13个性能事件
两级延迟比较、同拍/年龄/取消/尾部控制。真实seed2定向为278 PASS/1 FAIL/1 UNCERTAIN；
根126 PASS，IFU静态事务泄漏为0。最新十工程collection46495项，初始45883项及上一46379项
均无删除、相对顺序保持；十任务exit0，CLI仍因IFU残余登记exit1，不当作硬件通过。
RVC原28331笔输入及顺序不变（含28000次随机比较），InstrBoundary原600样本及顺序不变，
补真实raw半字map并按消费者有效域比较。FrontendTrigger原798笔计划激励（含180随机）
及顺序不变，CSR合法域与端口域压力分开，补零复位action和双阶段检查。Uncache原767笔
主激励（含700随机）的实际端口值/顺序不变，补48位字节地址、真实fire/UID/完成/取消与
禁止自动清债的收尾。Ifu顶层全部49个原功能体及两个guard已接入同一事务链，补逐UID
uncache issue/reply/resend/取消与全通道尾部检查，旧raw helper和fixture已移除；IFU静态
引脚/信号表达式现为0。ProducerFetchRequest按真实extent/页/FTQ后继/翻译偏移准入，
原端口压力不晋升producer credit；carry模型按完整ISA与完成槽taken修正，旧错误答案对照
被拒绝。旧flag2/3显式改为合法低位编码，不冒称全部物理激励保持；纯计划对账缓存373窗口、
uncache53请求/18回复。顶层最终语义审计已完成当前适配范围（包括派生指令metadata与实际
raw字节一致性、性能事件和生命周期）；其他前端工程及最终全仓验收继续，不能据静态清零
称全部适配完成。见
[活动目标实现记录](lessons/transaction-goal-20261101.md)。
PerfAnalysis另以真实red控制复核并补齐吞错后finish假成功：新增15自检、严格端口/Frame、
共享显式槽和粘滞失败，旧模型/功能文件字节不变；此前“已适配”不等于该新控制当时已覆盖。

前端复核继续：PHR的532-cell/33-fold/value-only适配已由同一源码真实seed1/2各16 PASS、
纯检查2128 PASS核验，补输入UID/fire/flush和精确终态账本、显式收尾、RAS输出字段投影
及真实训练PC`(1,1,2)`几何。内部PHR输入target不算已DCE的公开BPU target证据。
FTQ未传seed和ICache固定seed1也已修复：真实seed2完整FTQ109 PASS/2 XFAIL、ICache相同
生命周期选测44 PASS/1 XFAIL。MemBlock共51个加载入口的83个构造器控制修前全FAIL、
修后全PASS；另15个legacy直接运行provenance控制通过，根现230 PASS。修后真实seed2完整Sbuffer66 PASS、DCache229 PASS/3 XFAIL、
MMU417 PASS、LSU536 PASS/7 FAIL，逐nodeid判定均保持。独立pipeline的两个原生功能和
四个entry保护功能也已通过当前投影；其他短/长来源和positive程序仍未完成。
最新十工程collection47627项，初始45883及
前47592项无删除、相对顺序保持。BPU其他DCE消费者、短/长来源原生程序、MBTB
四路写回及前端逐DUT语义义务仍未完成，不能借PHR局部通过签核整体；见
[PHR与seed证据](history/transaction-goal-phr-adapter-20261101.json)及
[前端早期复核记录](history/transaction-goal-frontend-review-20261101.json)。

**2026-11-01 后续事务修复**：Sbuffer/SbufferData 两个 DUT 已接入框架单周期 Driver 与
lossless SamplingMonitor，修复零接受/排空超时的假成功、写回 UID/尝试与响应关联、
offered/accepted 区别和相同数据不同历史的 retry。此前两次CLI seed运行均 **66 PASS**，原 31
项判定不变；新增 7 个正常原生功能用例和 28 个自检。最新根测试 **108 PASS**；Sbuffer
严格事务边界审计通过，全仓仍有六工程待适配，不据此签核全部语义/覆盖。LSQ 已将
路径依赖的 fixture 模型选择改为显式合同，定向前后均为 324 PASS / 16 FAIL，逐条判定
不变。LSU StoreDelay 接入框架并补字段/尾拍检查，定向为 28 PASS；最新 LSU 完整回归为
536 PASS / 7 FAIL，原 529 项与历史完整集逐条判定不变，新 14 个自检通过。
所有后续修复仍未再次提交/推送，
最终差分与限制见[事务边界修复](lessons/transaction-boundary-repair-20261101.md)。
后续核验发现MemBlock原生默认入口未转发`UCV_SEED`；旧66项功能判定不改写成真实
双seed证据。四工程当前已逐次转发并补真正seed2回归，详见
[原生seed证据](history/transaction-goal-memblock-native-seed-20261101.json)。这些配置项的
修复不关闭各工程事务迁移；直接运行的legacy provenance writer现已同步同一seed解析、
启动前冻结和子进程参数，13/14/7项新原生选测判定保持，见
[seed收据修复](history/transaction-goal-memblock-seed-provenance-20261101.json)。

**2026-11-02 前端继续复核**：FTQ三个DUT补严格输入域、只读metadata、整组写入与claim
的原子拒绝，同名driver不能重占同一物理输入。修后真实seed2完整**166 PASS/2 XFAIL**，
原111项nodeid及判定保持，新增57项均为自检、不是新增硬件点，根**230 PASS**。其手动
driver、只在`edge(cycles)`返回时观察一次以及`aclose`清记录等仍是真实待迁移项；不据
绿色或静态零泄漏签核三个DUT。见[FTQ当前证据](history/transaction-goal-ftq-input-ownership-20261102.json)。

BPU短表/positive准备流与真实恢复读祖先修复后，合并共享调用链为**686 PASS**
（33 native/653纯检查），真实seed2的entry/short/positive共**12 PASS**；两批源码相同且
稳定、构建未改、产物哈希核验。保留原NT1/长T4/同owner和positive T4/protection1要求，
不是按live表状态挑期望。仍不关闭其他BPU、MBTB、FTQ/ICache及全仓范围，见
[源码/生命周期证据](history/transaction-goal-source-lifecycle-20261102.json)。
相同检查点十工程collection为**47686项**，原45883及前47627均无删除、相对顺序保持；
十任务exit0，CLI exit1仍是IFU残余登记。后续CommitQueue迁移不沿用这份源码身份，见
[收集对账](history/transaction-goal-collect-source-lifecycle-20261102.json)。

CommitQueue现已完成当前事务迁移：SDK Driver、双阶段lossless采样、输入UID终态账本、
真实异步reset及有界idle尾部。该源码下完整FTQ为**210 PASS/2 XFAIL**，旧168项判定不变；
同源码seed1定向**53 PASS**，根**240 PASS**。新增44项均为自检，不计新硬件功能点。
ResolveQueue/Ftq顶层的同类采样/身份/收尾仍继续迁移，详见
[CommitQueue证据](history/transaction-goal-ftq-commit-transactions-20261102.json)。

随后补齐ResolveQueue/Ftq的框架持续双阶段全通道观察与嵌套只读快照、逐拍tick及早关/
取消守卫。当前完整FTQ为**228 PASS/2 XFAIL**，前212项判定保持，新18项自检；同源码
seed1生命周期选测**71 PASS**、根**242 PASS**。十工程collection**47748项**，初始45883
和前47686无删除/顺序保持，十任务exit0。两DUT的driver/完整schema/协议UID与事务收尾
仍继续迁移，不以采样帧数代替事务完成，见
[持续采样证据](history/transaction-goal-ftq-cycle-sampling-20261102.json)。

**2026-11-01 检查点与后续语义修复**：先提交并推送 `0017350` 到 origin/main，远端
哈希已核对。随后修复 DCache 默认多 worker 的零收集、L2 沿前握手/完整双 beat、
随机流的无来源 ReleaseAck 和 golden store 数据泄漏，以及 MMU PTW 的接受/完成身份。
最终 DCache 为 **229 PASS / 3 XFAIL**，MMU **417 PASS**；原 213/408 项逐条判定不变，
新增 19/9 项通过。根测试 **102 PASS**。扩展审计揭露 Sbuffer 等信号操作盲区，当前七
工程仍有事务边界技术债，不能据此宣称全部语义或架构迁移完成。后续修复目前尚未再次
提交/推送；过程中的 FAIL/INCOMPLETE 与最终证据分别保留，见
[提交后语义修复](lessons/semantic-boundary-repair-20261101.md)。

**2026-10-31 工程根命名空间更新**：十工程实现已直接迁入 suites.<group>.<suite>，
移除重复 *verify/common 包装；runner、插件、ROOT、工具、安装元数据、文档和 skill
一起调整。45806 个有序收集 nodeid 与迁移前完全一致，根测试 96 PASS，结构与资产/skill
审计通过；FTQ/ICache/IFU 的本轮全量判定分别为 109 PASS+2 XFAIL、291 PASS+3 XFAIL、
144 PASS+2 FAIL+1 UNCERTAIN，其他工程按明确子集回归。此次不是全部事务迁移或全部
硬件验收完成；范围、证据及产物隔离复跑见
[工程根重构记录](lessons/suite-namespace-refactor-20261031.md)。下文历史运行仍归原日期与源码。

**2026-10-31 复核更正**：下文“全工程布局迁移完成”只证明 fixture 接线与部分句柄
收口。P.p_* / P.io(...) 是端口别名，不是事务抽象；IFU/LSQ/LSU/MMU/DCache/VAGQ
仍有引脚级耦合，不能宣称全部事务架构迁移完成。历史构建/回归原数和真实失败不改写。
目录取舍、skill 修正和 22 个散落仿真产物的清理见
[结构与 skill 复核](lessons/structure-skill-review-20261031.md)。

本阶段按当前优先级交付可维护的仓库结构，不以全部硬件用例通过为门槛。十个工程、132 个 DUT 已进入同一独立 Git 仓库；唯一公共命令为 `ucv`，公共 Python 包为 `src/ucv/`，验证框架统一使用 toffee。

## 已完成的结构范围

- `frontend`、`memblock`、`vector` 分组及十个独立验证包、pytest 根目录。
- 根 → 分组 → 工程的完整命名基线继承，未知/不完整引用报错，禁止 DUT 单独覆盖源码或配置。
- 公开九工程统一 commit `893e1580b705d81f113c30c7a05734e09a08050e`；VAGQ 通过本地来源接入 internal `d4566d58a5ace1f6a5df4409b37a84b971f48e43`。所有工程使用 DefaultConfig。
- `list`、`doctor`、`setup`、`prepare`、`build`、`run`、`report` 入口，锁定依赖、独立源码检出、Chisel 生成和闭包提取、构建及冒烟、worker 预算和来源记录。
- 基线、DUT、工具链及选项参与缓存身份；运行使用新结果目录；工程进程隔离、BPU 原生 DUT 进一步隔离。
- 生成文件、本地配置、工具安装、internal 实现和大结果不进入 Git；134685 份历史证据由按工程拆分的哈希索引记录。

## 结构检查与已取得的执行证据

此前结构验收时根 `tests/` 共 29 PASS，包含继承优先级、错误引用、混合基线、缓存隔离、真实 pytest 用例选择、RTL 闭包、失败分类及两个锁定工具补丁的检查；新增整芯片生成跨工程复用、override 隔离及拒绝旧 BPU 独立生成配置的检查。资产审计通过，未发现公开源文件依赖旧框架导入或工作区符号链接。2026-10-30 UNCERTAIN 本地适配后的根测试为开发环境 54 PASS，旧 `.venv` 50 PASS / 4 SKIP（4 项需要新 Toffee）；资产审计仍通过。

统一入口已验证公开环境检查、混合基线拒绝、Sbuffer 显式单用例执行和 BPU 显式单用例分区收集。标签 `v0.1.0-structure` 的 122 个 DUT 已使用锁定工具链构建并通过独立进程冒烟，其中 BPU 当时使用独立生成入口；该证据不代表当前整芯片 BPU 的重建验收。全新源码检出、独立 Python 3.12 虚拟环境且没有工具/构建缓存时，23 项结构测试通过，4 项依赖原生 SDK 的测试明确跳过；基线与资产检查通过，缺少工具或 internal 来源会明确报错。此检查不声称完成空缓存的全工程硬件重建。

本次 `ucv4xs` 更名后已在新路径重建虚拟环境、原生工具和全部 122 个 DUT，并全部通过独立进程冒烟；其中 BPU 十个 DUT 均来自与其他公开工程共享的完整香山 RTL。生成阶段复用经过哈希核验的整芯片 RTL 缓存，本次没有重新执行空缓存 Chisel 生成。Sbuffer 显式单用例为 1 PASS，BPU 指定用例恰好收集 1 项，两次运行均无产物完整性缺口。记录见 [本轮结构调整证据](history/structure-update-20261027.json)。

旧虚拟环境、工具构建目录和原生 DUT 凭据保存在本地 `.history/`，具体映射记录在本轮证据中。原 `v0.1.0-structure` 标签及其历史记录保持不变。

## 硬件与适配状态

锁定工具链下既有六个公开非 BPU 工程的完整回归已结束，逐用例判定与迁移前一致，报告无产物完整性缺口。下表另附 IFU 的最新本地开发环境结果；不表示其他工程也已切换该环境重跑：

| 工程 | PASS | FAIL | XFAIL | SKIP | UNCERTAIN |
|---|---:|---:|---:|---:|---:|
| ICache | 290 | 0 | 3 | 0 | 0 |
| LSQ | 2325 | 250 | 0 | 0 | 0 |
| DCache | 210 | 0 | 3 | 0 | 0 |
| MMU | 408 | 0 | 0 | 0 | 0 |
| Sbuffer | 31 | 0 | 0 | 0 | 0 |
| LSU | 522 | 7 | 0 | 0 | 0 |
| IFU（本地开发运行） | 144 | 2 | 0 | 0 | 1 |
| VAGQ（internal） | 433 | 1 | 0 | 33 | 0 |

2026-10-29 新增 frontend/FTQ 工程，按 `Ftq → {ResolveQueue, CommitQueue}` 真实实例化层次提取三个 DUT。2026-10-30 将验证包重组为每 DUT 一个 agent（agent / driver / monitor / checker / transaction 分层），测试只提交事务，引脚所有权在 fixture 边界检查；同一轮补齐顶层物理槽 × 分支槽 × 来源矩阵。实际运行 `results/ftq-final-20261030b` 为 109 PASS、2 XFAIL（strict）、0 FAIL、0 SKIP；原生覆盖为 `resolve_queue` 100.0% 行 / 99.9% 分支 / 89.2% toggle、`commit_queue` 100.0% / 99.8% / 100.0%、`ftq` 100.0% 行 / 99.6% 分支 / 84.4% toggle。`ftq` 闭包行覆盖达到 100%，上一轮记录的顶层 IFU 命中 fallback 枚举缺口（R-02）关闭；剩余分支只有三个初始化 reset else 和三个顶层结构不可达的同拍 IFU 合并臂。2 个 XFAIL 不是通过：ResolveQueue 在第 9 条分支解析（或同拍超量组）时越过 8 槽容量，回绕覆盖已有分支；合法依据是 DefaultConfig 的 BPU meta 有 10 个位置。缺陷复现、根因行和建议修复见 [ResolveQueue 分支槽溢出](../suites/frontend/ftq/docs/bugs/resolve-queue-branch-overflow.md)，案例见 [覆盖率下容量缺陷](lessons/ftq-resolve-capacity-20261029.md)。责任边界、等价类、追溯、残余和运行证据见 [FTQ 工程 README](../suites/frontend/ftq/README.md) 与 [验证包结构](../suites/frontend/ftq/docs/architecture.md)。此结论只适用于 `public-893e1580b` + DefaultConfig 和本次原生包，不改变其他工程历史判定。

2026-10-29 新增 frontend/IFU 工程，按 `Ifu → {RvcExpander, InstrBoundary, PredChecker, IfuUncacheUnit, FrontendTrigger, IfuPerfAnalysis}` 的真实实例化层次提取七个 DUT，并按自底向上顺序验证：六个内部子模块逐一闭环后，再用组合模型验证顶层。第三轮按“观察点精度”重扫生产者/消费者宽度，发现并保留一个真实 RTL 偏差：`FrontendTrigger` 的 `tdata2` 比较只用低 50 位，而 CSR 暴露 `RW(63,0)`，`tdata2 ≥ 2^50` 时 EQ/GE 会在真实 PC 上误命中、LT 全不命中。实际运行 `results/20261030T022604Z-107cb685` 为 144 PASS、**2 FAIL**、**1 INCOMPLETE**（硬件用例 114 + 环境门禁 30），硬件 53/55 PASS + 1 FAIL（`IFU-TR-002`）+ 1 INCOMPLETE（`IFU-TOP-011`，只覆盖一种 carry 位置）、验证环境 5/5。两条反例保留为 FAIL，未登记 XFAIL；未证明范围（R-01..R-12）以机器可读残余登记在 `verification_plan.json`，插件在“有 blocking 残余却全 PASS”或“有 FAIL 却无 blocking 残余”时报一致性错误；`ucv run`/`ucv report` 会把残余写入 `run.json`、`summary.json` 和 `summary.md` 的 Residual register（本轮 13 条、blocking+open 1 条），并规定“全 PASS 但仍有阻塞残余”时判定降为 INCOMPLETE；残余 R-13 记录复现、根因与修复方向（全宽比较，或把 CSR 高位 WARL 化并改合同），见 [FrontendTrigger tdata2 宽度](../suites/frontend/ifu/docs/bugs/frontend-trigger-tdata2-width.md)。此前一轮 `results/20261029T133533Z-d193f454` 的 142 PASS 只覆盖 `tdata2` 高位为 0 的配置。第二轮按执行/复核方法补充了独立 oracle 区分力、负对照、pruned 端口审计、双向追溯、激励合法性与 guard 交接探测；等价类矩阵、观察点/比较器对账、退出标准与残余 R-01..R-13 分别在 [行为矩阵](../suites/frontend/ifu/docs/behavior-matrix.md)、[观察点对账](../suites/frontend/ifu/docs/observation-coverage.md)、[退出与残余](../suites/frontend/ifu/docs/exit-criteria.md) 中。基线之后的上游变更复核发现 `b716aade`（基线后第 57 个提交）修复了重定向 PC 的 guard 位截断，本地基线是其 pre-image；该交接面限制以 `IFU-ENV-005` 探测并登记为出域残余，不计入硬件 PASS，详见 [上游复核](../suites/frontend/ifu/docs/upstream-review-20261029.md)。原生覆盖（行/分支/toggle）：`rvc_expander` 100.0/100.0/95.9%、`instr_boundary` 100.0/99.4/91.8%、`pred_checker` 100.0/95.8/99.8%、`uncache_unit` 100.0/93.8/100.0%、`frontend_trigger` 100.0/99.4/95.2%、`perf_analysis` 100.0/95.5/17.4%、`ifu` 顶层 100.0/99.8/87.6%。七个 DUT 的生成 RTL 行覆盖均为 100%，剩余分支臂全部定位为结构不可达（`ENABLE_INITIAL_REG_` 一次性初始化块的复位 else 臂、槽 0 必属第一块、第 36 lane 被置 0）；`perf_analysis` 的 toggle 上限由端口裁剪决定（76 个理由位只暴露 10 个，可达位已 100% 覆盖）。功能点语义、逐轮缺口分类、观察点精度扫描与残余处置见 [IFU 功能点](../suites/frontend/ifu/docs/functional-points.md)、[覆盖率闭环](../suites/frontend/ifu/docs/coverage-loop.md) 和 [退出与残余](../suites/frontend/ifu/docs/exit-criteria.md)。此结论只适用于 `public-893e1580b` + DefaultConfig 与本次原生包。

BPU 已切换为从与其他公开工程共享的完整 DefaultConfig 香山 RTL 提取十个 DUT，删除 `recipes/` 独立生成入口及相关分支。模型、激励和源代码审计继续适配整芯片实际端口。此前独立生成 DUT 的构建和回归记录仅作历史对照。2026-10-29 迁移适配修复后的全量纯模型诊断（显式排除 2600 个原生 DUT 用例，24 worker，结果目录 `results/pytest-pure-final-20261029`）为 38353 PASS、74 FAIL、0 ERROR、7 SKIP；此前 1222 FAIL、9 ERROR 已收敛到该结果。修复覆盖整芯片 8 槽反馈载荷、5/9 TAGE 选择器与 16 个寄存器、矩阵分母、五 way MBTB 深度、整芯片生成文件名及 PHR/RAS 静态审计锚点。剩余 74 FAIL 集中在 `test_short_revisit`、`test_entry_protection` 和 `test_early_positive_protection`：这些程序仍按 MinimalConfig 的“短表 table0、长表 table1”身份写预期，DefaultConfig 的实际 5/9 历史会把同名原件选到 table1，随后长项训练覆盖该短身份。该组需按新表映射重新设计场景，不能用放宽断言或登记 XFAIL 代替。尚未执行完成当前最终源码的 BPU 全量原生回归。

BPU 同一历史 RTL 上的框架比较保存在 `history/bpu-framework-verdict-comparison.json`：大部分原生 DUT 判定一致，MicroTAGE 有一个 strict XFAIL 变为 FAIL，覆盖率打包完整性亦未认证。历史产物是 MinimalConfig，不能证明新 DefaultConfig 的硬件正确性。

### BPU 模块级自底向上闭环进展（2026-10-29）

开始按实际模块层次推进模块级 UT 闭环，先完成两个叶子模块：

- **MicroBTB（UBTB）**：`results/ut-ubtb-gap2-20261029` 为 49 原生 PASS、168 纯模型 PASS；`MicroBtb.sv` 行 805/806（99.88%）、分支臂 102/104、toggle 完整位 2019/2020。未覆盖的 1 行和 4 个分支臂均已给出局部守卫证明（hit 蕴含 useful≠0；初始时间复位 else；内层互斥 else），toggle 剩余位为公共 API 恒零的半字地址最高位。整芯片裁剪的 `prediction.valid`、常量 `sramResetDone/trainReady`、FastTrain 无 mispredict 叶均由适配层按语义重建。报告：`suites/frontend/bpu/docs/ubtb-module-review-20261029.md`。
- **MicroRAS（URAS）**：`results/ut-uras-gap3-20261029` 为 29 原生 PASS、4 已归档真实 RTL FAIL（BPU-BUG-05 禁用门控 1 项、BPU-BUG-10 返回并调用 3 项）、137 纯模型 PASS。`MicroRas.sv` 行 73/73（100%）、分支臂 30/31、toggle 完整位 439/440（99.8%）；剩余 arm 为初始时间复位 else，剩余位为 GuardedPc 地址 bit0。迁移适配修复了无 enable 引脚、属性叶展平、常量状态端口和跨 reset 的边界对齐；新增全 50 位地址/位置 16/31/S2→S3 存储路径用例。报告：`suites/frontend/bpu/docs/uras-module-review-20261029.md`。

两个模块的 FAIL 均原样保留，未添加 XFAIL 或删除用例。其余叶子/中层模块（ABTB、TAGE、ITTAGE、SC、UTAGE、MBTB、RAS、Bpu）继续进行同样的闭环。

### BPU 模块级闭环补充：AheadBTB 与 MicroTAGE（2026-10-30）

- **AheadBTB**：`results/ut-abtb-gap3-20261030` 为 **93 原生 PASS / 1 FAIL**、1896 纯模型 PASS / 7 SKIP。唯一 FAIL 是已归档 `BPU-BUG-09`（同 set 两条间接分支的目标修正选错 way），迁移前即存在。设计行覆盖 **11621/11621（100%）**，写缓冲/替换器子模块行覆盖均 100%；toggle 完整双向位 **7601/9261（82.1%）**。已适配整芯片稀疏 PHR（仅索引 2）、根级 `result_entries`、被删的 `s3_fire`/`trainReady`/`fastTrain.mispredict` 与 `toMicroTage` 被裁 sideband 叶；新增写缓冲四槽全宽身份与极端 set 清理用例。报告：`suites/frontend/bpu/docs/abtb-module-review-20261030.md`。
- **MicroTAGE**：整芯片端口适配已完成（稀疏 PHR 索引 2/7 与 1/2/5/6、4 行训练元数据、被删 `meta.valid`、仅 taken/kind 的 ABTB sideband），初始 **269 个 setup ERROR 全部消除**。`results/ut-utage-probe9-20261030` 为 **229 原生 PASS / 39 FAIL / 1 XFAIL**（迁移前 232/35/3），其中 35 个 FAIL 与迁移前逐条一致，仅新增 4 个（useful 地址矩阵 2 项、历史碰撞 1 项、功能覆盖门禁）。纯模型负对照仍有按旧 33 折稠密 metadata 构造的夹具待迁移。功能点闭环尚未完成，未写成通过。报告：`suites/frontend/bpu/docs/utage-module-review-20261030.md`。

### IFU / Toffee UNCERTAIN 本地迁移（2026-10-30）

按用户确认，直接修改本地 Toffee Git 检出，未提交、打 tag、推送或制作 Toffee patch。
从源码构建并安装 `uc-toffee 2.0.1.dev1+uncertain.a886d1c12444` 到独立
`.venv-uc-toffee`（已有 `uc-xcomm 1.1.1`，pip check 通过），原 `.venv` 与原生 DUT
不替换。实际源码/安装哈希由本机配置与开发凭据校验，公共原生构建锁保持原义。

`@pytest.mark.uncertain(reason=..., reference=...)` 的声明、`U`/详细状态、session 摘要、
失败优先和 manifest 计数均由 Toffee 负责；ucv 与 IFU 功能点报告复用其分类。
UNCERTAIN 不计入 PASS，但本身不导致非零退出；执行/产物未完成仍为 INCOMPLETE。
完整复验 `results/20261030T-uncertain-uc-toffee` 为 **144 PASS / 2 FAIL / 1 UNCERTAIN**，
硬件 53 PASS / 1 FAIL / 1 UNCERTAIN，环境 5/5，整体 FAIL / exit 1。
与第三轮用例集合及原生构建相同，仅 carry 用例从旧声明式 INCOMPLETE 迁移为 UNCERTAIN；
line/branch/toggle 命中数和分母均不变，R-09/R-13 不关闭。另有真实 carry 用例 2-worker
运行为 1 UNCERTAIN / exit 0，覆盖正常提交。Toffee 全量 1165 PASS + 3 subtest PASS，
ucv 开发环境根测试 54 PASS。版本、完整哈希和边界见
[UNCERTAIN 迁移核验](../suites/frontend/ifu/docs/uncertain-migration-20261030.md)。
上方第三轮的 1 INCOMPLETE 为历史状态，原收据未改写。


### 全工程布局迁移完成（2026-10-31）

> 保留原轮次结果；“pin fields=0”是旧扫描遗漏别名和 keyword 的结果，不是实际零
> 耦合。现审计已修正，六工程标为 needs-adapter；fixture 条目数也不能称作 DUT owner 数。

本轮把剩余七个工程的 pytest 接线、pin 访问与自检分类全部收敛到同一契约，并完成新工具链
下 132 个 DUT 的重建。

**布局契约**：`scripts/audit-suite-layout.py` 检查四项——根 owner fixture 可达、
无嵌套 conftest / `env/pytest.py`、功能 testcase 无原生 DUT 访问、`selftest` 已注册。
审计同时区分“原生访问”（`.dut`/`.pins` 属性链）与“pin 字段字面量”（`"io_*"`）；
迁移后十工程两者均为 0。

| 工程 | 根 owner fixture | 功能用例 | 迁移内容 |
|---|---:|---:|---|
| BPU | 13 | 397 | 复用上一轮；selftest 插件改共享 `ucv.pytest_selftest` |
| FTQ | 4 | 20 | 同上 |
| ICache | 13 | 44 | 同上 |
| IFU | 7 | 8 | 新增 `ifuverify/common/pins.py`；根 conftest 暴露 7 个 harness fixture |
| DCache | 2 | 15 | 工程根 conftest 删除，fixture 集中在 `tests/conftest.py`；step/refresh/reset 收回 runtime；Queue env 移出 testcase |
| LSQ | 31 | 165 | 11 个嵌套 conftest 合并到根；`common/pins.py`；按目录分派的同名 fixture |
| LSU | 2 | 23 | 工程根 conftest 删除，fixture 到 `tests/conftest.py`；`perf_value()` 替代直接读端口 |
| MMU | 52 | 22 | 工程根 conftest 删除；387 处 `execution(env.dut)` 改为 `execution(env)`；bit sweep 移入 runtime |
| Sbuffer | 7 | 2 | 工程根 conftest 删除；31 处 `execution(env.dut)` 改为 `execution(env)` |
| VAGQ | 14 | 54 | 根 fixture 到 `tests/conftest.py`；`NativeSplit` 移入 `vagqverify/split/native.py` |

`tests/test_suite_layout.py` 把审计固化为根测试；`ucv.pytest_selftest` 统一注册
`selftest` marker，替换 BPU/ICache 各自的插件副本。

**pin schema**：六个工程的 `common/pins.py` 成为唯一写 `io_*` 的地方
（IFU 51 个、LSQ 199 个、LSU 75 个、MMU 21 个、VAGQ 49 个、DCache 1 个常量）。
功能测试改用 `P.p_*` 与 `P.io(...)`，f-string 按 Python 3.12 token 边界替换。

**构建**：`ucv build public --require-unified-baseline --jobs 64` 完成 118 个公开 DUT；
BPU `tage` 与 `bpu` 顶层随后同样 `BUILT + SMOKE PASS`。`ucv build vagq` 完成 12 个
internal DUT。`ucv build sbuffer` 另行完成 2 个。**132/132 DUT 均有本次冒烟收据**（按当前 `cache_key` 逐个核对 DUT 链接与 `build.json.smoke`）。

**实际回归**（真实判定，未改写）：

| 工程 | 结果 | 说明 |
|---|---|---|
| 根 `tests/` | 67 PASS | 含新增布局门禁 9 项 |
| IFU | 144 PASS / 2 FAIL / 1 UNCERTAIN | 2 FAIL 为已归档 `FrontendTrigger tdata2` 宽度缺陷 |
| LSU | 522 PASS / 7 FAIL | 与迁移前同一失败集合 |
| DCache | 210 PASS / 3 XFAIL | 3 个 strict XFAIL 保留；布局迁移后重跑 |
| MMU | 408 PASS | 全通过；迁移后复跑 `tests/l2 tests/tlbn` 331 PASS、`tests/tlb tests/tlbfa tests/wrapper` 64 PASS |
| Sbuffer | 31 PASS | 全通过 |
| ICache | 291 PASS / 3 XFAIL | 与迁移前一致 |
| FTQ | 109 PASS / 2 XFAIL | ResolveQueue 容量缺陷未修 |
| LSQ | 2325 PASS / 250 FAIL | `results/ucv-lsq-final-20261031`：manifest `committed`、`coverage_complete=true`、`ucv report` 无产物缺口；计数与迁移前逐项一致 |
| VAGQ | 433 PASS / 1 FAIL / 33 SKIP | 统一入口 `results/ucv-vagq-20261031`；1 FAIL 与迁移前同一用例 |

**覆盖率与产物完整性**：三个通过统一入口执行并生成 manifest 的工程均为
`state=committed`、`coverage_complete=true`、`ucv report` 无缺口——Sbuffer 5 个原生
覆盖率产物、LSQ 77 个、VAGQ 25 个，三者都生成 `coverage.html`。其余工程的判定来自
直接 pytest 运行，没有本次统一合并的原生覆盖报告，因此不引用旧覆盖率数字。

VAGQ 的 1 FAIL 是 `tests/maskgen/testcase/test_element_windows.py::test_segment_element_windows_and_policies`
（56/9024 个 native policy mismatch，`elemActiveMask` 与独立窗口模型不一致）。该失败在
迁移前已存在，本轮保留为 FAIL，未登记 XFAIL。

## 文档与本地空间整理

已补齐 README、仓库协作约定 `AGENTS.md`、项目工作流 skill、历史验证经验和编译构建经验入口。2026-10-28 按用户要求回收一轮异常 BPU 调试留下的 224 个覆盖率文件，约 25.8 GiB；日志和原状态保留，删除文件清单见 [回收记录](history/storage-reclamation-20261028.json)。该清理不产生新的硬件验收结论；覆盖率按字节控制与异常自动回收仍待实现。

## 后续工作

FTQ 的 ResolveQueue 分支槽溢出缺陷需单独修复并复验（当前 2 个 strict XFAIL）；顶层闭包行覆盖已在 2026-10-30 达到 100%，R-02 关闭，但剩余分支/toggle 缺口与 R-01 仍需分开陈述。当前保留这些缺口，不以 XFAIL 或放宽检查替代修复。BPU 剩余短/长表场景重设计、其完整生产回归、全新环境空构建缓存下的全工程链路，以及最终硬件失败和覆盖缺口分析继续单独推进。现有失败、XFAIL 和 SKIP 均保留，未以删除用例或扩大豁免替代验证。

`v0.1.0-structure` 标记结构阶段交付。完整“迁移与重建验收”仍为 NOT_CERTIFIED；硬件判定以各次实际运行报告为准。证据路径与哈希见 `history/structure-evidence.json`，不将结构通过改写为硬件通过。

### BPU 模块级闭环补充：TAGE / ITTAGE / SC / RAS / UTAGE（2026-10-30）

本轮在整芯片 DefaultConfig 生成 RTL 上完成五个模块的端口迁移与验证；所有运行目录、覆盖率 JSON 和模块报告均保存在 `suites/frontend/bpu/docs/` 与对应 `results/` 目录。

| 模块 | 原生判定 | 纯模型 | 行覆盖 | 分支臂 | toggle | 证据 |
|---|---|---:|---:|---:|---:|---|
| TAGE | 247 PASS / 1 XFAIL（既有） | 867 PASS | 4978/5308 = 93.78% | 2841/3154 = 90.08% | 27837/66424 = 41.91% | `results/ut-tage-probe4-20261030`、`docs/tage-module-review-20261030.md` |
| ITTAGE | 42 PASS / 3 FAIL（迁移前同判定） | 122 PASS | 2126/2190 = 97.08% | 1218/1670 = 72.93% | 18955/212758 = 8.91% | `results/ut-ittage-final-20261030`、`docs/ittage-module-review-20261030.md` |
| SC | 61 PASS / 0 FAIL | 403 PASS | 4556/5245 = 86.86% | 1878/2256 = 83.24% | 29135/41226 = 70.67% | `results/ut-sc-final-20261030`、`docs/sc-module-review-20261030.md` |
| RAS | 23 PASS / 5 FAIL / 1 XFAIL（与迁移前逐条一致） | 565 PASS | 804/838 = 95.94% | 282/316 = 89.24% | 3911/7218 = 54.18% | `results/ut-ras-final-20261030`、`docs/ras-module-review-20261030.md` |
| UTAGE | 234 PASS / 35 FAIL / 1 XFAIL（35 FAIL 与迁移前逐条一致） | 4050 PASS | 11279/11286 = 99.94% | 3725/3734 = 99.76% | 8758/11384 = 76.93% | `results/ut-utage-final-20261030`、`docs/utage-module-review-20261030.md` |

- UTAGE 新增功能点 `BPU-UTAGE-028`（整表 useful aging）与用例：先用真实分配把表 0 全部 512 个 useful 单元置 1，再用 126 次失败分配跨越低 tick bit7，证明一次 aging 对 4 bank × 128 set 的全部非零单元各减一。`BypassShadowBuffer` 的 512 个 aging 行由未覆盖变为全命中，模块行覆盖从 95.53% 提高到 99.94%。剩余 7 行是各模块初始化复位 else 臂。
- UTAGE 的 35 个 FAIL 与迁移前 FAIL 集合**逐条一致**（new=0、fixed=0），两个 strict XFAIL（useful address matrix、tag width）因真实修复转为 PASS；保留的 XFAIL 是 shadow 满替换。
- TAGE 未覆盖集中在“多槽 alternate 选择”和“同拍双路写合并/满队列强制写回”，归类为已有功能点的**情况枚举缺失**；BIST/DFT toggle 不计入功能判定。
- ITTAGE 的 383 个未覆盖分支臂全部在 `MbistPipeIttage`（扫描/DFT 域）；3 个原生 FAIL 与迁移前一致，属未发布快照/region 目录语义的待归因项。
- SC 原生全部通过；剩余缺口是全局计数器双向饱和与写缓冲合并/满队列的情况枚举。
- RAS 恢复了独立的 `io.enable` 驱动并修复 `meta_ras` 回灌投影和复位边界；`RasStack` 提交队列的 33 行未覆盖，对应尚未补的重复提交/回绕语义，且与 4 个 return-and-call 真实 FAIL 同域。

### MBTB 与 Bpu 顶层：尚未闭环

- **MainBTB（MBTB）**：整芯片适配已完成（0 setup ERROR），当前 `results/ut-mbtb-probe7-20261030` 为 **99 PASS / 26 FAIL**（迁移前 116/10）。26 FAIL 集中在 shadow owner/depth、cleanup overlap、full-capacity 与 shared-service 场景：这些场景仍按旧 2-way/旧坐标假设读取写缓冲 shadow，需要按 DefaultConfig 的 4-way LRU 与 `AddrField` 几何重写独立模型。行覆盖 3664/12114（30.25%）不代表通过，而是多处场景在准备阶段失败导致深层写缓冲/VictimBTB 未执行。报告：`docs/mbtb-module-review-20261030.md`。
- **Bpu 顶层**：整芯片生成的 `Bpu` DUT **不含** `toFtq.prediction.bits.target_addr`（生成 RTL 只导出 startPc/taken/endPosition/s2Override/s3Override），而现有 adapter 按旧接口绑定 target，导致 setup ERROR。该端口差异需要单独决定：把预测目标作为不可观测域并在 DUT 内部观察点取证，或重建包含 target 输出的生成入口；在决定前不把 Bpu 顶层写成通过。`ahead/abtb/ubtb` 等组合用例尚未重新运行。

### 依赖升级与验证包布局重构（2026-10-30）

- **环境升级**：`.venv` 已从 `pytoffee 2.0.1.dev1` / `xspcomm 0.3.0.dev3` 升级到
  `uc-toffee 2.1.0` / `uc-xcomm 1.1.1`，ABI 3、coverage protocol 5 不变；
  `pytest 9.2.0`、`pytest-asyncio 1.4.1`、`pip 26.2.2` 等基础依赖同步到当前最高兼容版本。
  锁文件、`.tools/sources` 和 `.tools/receipt.json` 一致；xcomm 宽 trace 补丁在新 tag
  上仍可应用并保留哈希。
- **能力核对**：正式版 `uc-toffee 2.1.0` 已提供 `toffee.outcomes`、
  `toffee._pytest_outcomes` 和 UNCERTAIN，不再依赖本地开发版；根测试由旧环境
  `50 PASS / 4 SKIP` 变为 **58 PASS / 0 SKIP**。`ucv.runtime` 按锁定的 `distribution`
  读取版本，并保留旧分发名回退；`ucv setup` 使用新分发名和 CMake 版本。
- **布局重构**：BPU 10 个 DUT、ICache 11 个 DUT 的 agent fixture 已集中到各自 pytest
  根，删除 `bpuverify/*/env/pytest.py`、`icacheverify/*/env/pytest.py` 和所有子目录
  转发 conftest；`tests/framework` 自动标 `selftest`。新增 `wait_cycles` /
  `write_with_flush` agent API，功能 testcase 不再直接访问 `.dut`/`.pins`。
- **审计**：`scripts/audit-suite-layout.py` 报告 BPU/FTQ/ICache 为 `ok`；IFU、DCache、
  LSQ、LSU、MMU、Sbuffer、VAGQ 仍为 backlog（旧扁平 harness、物理端口名或嵌套
  conftest）。backlog 不是通过项，迁移方案与验收见
  [布局审计案例](lessons/suite-layout-audit-20261030.md)。
- **实际验证**：根 `pytest -q tests` **58 PASS**；BPU `tests/ubtb/testcase`
  **45 PASS**、`tests/ubtb/scoreboard` **132 PASS**、`tests/ras/testcase/test_push_pop.py`
  **5 PASS**、`tests/sc/testcase/test_directions.py` **2 PASS**；ICache
  `tests/waylookup/testcase/test_flush.py` **7 PASS / 1 XFAIL**（既有 strict XFAIL
  保留），全工程收集 293 项。BPU 8 个 DUT（abtb/ittage/mbtb/ras/sc/ubtb/uras/utage）、
  `icache/waylookup` 和 Sbuffer 两个 DUT 均为新工具链 `BUILT + SMOKE PASS`。
  统一入口 `ucv run sbuffer --workers 1` 为 **31 PASS**，manifest `committed`、
  `coverage_complete=true`，`ucv report` 判定 PASS 且无产物缺口。
- **边界**：工具锁变化已改变构建缓存身份。BPU 的 `tage` 与 `bpu` 顶层在 20/30 分钟
  构建窗口内未完成，保持旧缓存、未写成 PASS；其余 121 个 DUT 的构建/冒烟、全工程
  原生回归和覆盖率合并**未执行**。旧 DUT 收据不再作为新工具链证据，本轮不产生新的
  全量硬件通过结论。
