# LSQ：内部子模块 → 分支组合 → 整体 UT

## 1. 范围与状态

验证根目录为 `memblock-hash/lsq/`。首轮面向 `LsqWrapper` 的真实子树，使用 picker+xreactor；内部子块、Load/Store 分支和整体分别建立独立 DUT 与证据。

**当前更新**：回归12完整2203例实际1982 PASS/221 FAIL，504源/2116流SHA/460700记录、
各DUT原DA和221失败主签名门禁完成，见[12报告](reports/lsq-progress-regression-12-20261019.md)。
新增精确S4实际84 PASS/515源一致，5592 UID/813 ROB头trap/942同槽新UID完成；自身
26994→49882/59602（+22888、丢失0），9720剩行逐原source/line分类，见[精确S4](reports/lsq-s4-precise-20261019.md)。
新增本地reset保留外部NC响应15 PASS/528源一致，132 UID、60旧实际回包丢弃/0外部
abort、60同槽新UID完成，自身26573→30075/59602（+3502、丢失0），见[本地reset](reports/lsq-local-reset-20261019.md)。
两批新增不追溯算入回归12；它们证明声明的producer profile/独立LSQ效应，不是native
上游或整体随机验收。旧S4-03的hyper/poison/过早trap限制和原ordinary接口事实仍保留。
按用户纠正，默认只保存小摘要，逐拍JSON/wave需显式debug且限大小。已实际79节点
重跑核验0 JSONL/0wave及全4186拍流SHA相等，1个原SID FAIL保持。删除已结束重复日志/
中间coverage，旧报告与FAIL/源保留；主基线才压缩按需复核，不把历史审计当作旧完整
原件永远驻留的承诺。完整原生/语义/缺口闭环和整体目标范围不变。

新完整八类型/原八种子`lsq-normal-mixed-source-04`实际2PASS/6FAIL、542源一致；
23个S2 TLB早返回窗口、17 TLB/14 Cache原job真实偿还，五个CBO异常WB和一个
old-Sbuffer污染zero严格失败保留。03的UID-v2曾拒绝两个原生PASS：7个取消物理槽
仅有异常释放的新UID，未满足普通同槽完成。04只补强原600随机/公平后的独立
清理段后，441UID分账闭合、95取消槽均有非fault新UID实际完成，六FAIL完整流SHA
与03相等。不删原FAIL/16B向量或早hint；首次vector上游路由仍单列未证明。
自身36925→39695/59602（+2770/丢失0），19907缺口逐原行分类；此前02→03仍如实
保留新增2061/丢失520，不能相加分子或谎称全程单调。只压缩04当前native、删除
前三份246486930字节native不归档；清理后三门禁exit0、0临时遗留，results审计点
825.9MiB。见[完整混合源关系](reports/lsq-normal-mixed-20261019.md)。

**最新实际增量（整体未验收）**：回归10已结束38DUT/1908例1708 PASS/200 FAIL，430源
与完整raw/FAIL/每DUT原DA重复门禁完成，见[10报告](reports/lsq-progress-regression-10-20261019.md)。
旧LDU S3准入撤回后，独立26例仅修size/lastBeat/update，实际17/9、762次S3/18次S4
源关系，原输出与9个失败保持，见[S3报告](reports/lsq-ldu-s3-20261019.md)。源正确联合
容量/CBO分阶段与串行缺口补例最终27例21/6，原SID六FAIL保留，自身50902→52999→
53079/59602、旧命中丢失0，见[分阶段闭环](reports/lsq-ldu-joint-phases-20261019.md)。
这些局部进展不改变完整八类型随机、S4异常/其他128与恢复、local-only旧响应和最终
全层次交付审计要求。旧317例/满池快照仅在各自接口域保留，不追溯提升正常准入。

本文为完整实施计划，不以单个试点完成代表整体验收。当前四个 FreeList、三个 CAM、年龄选择器和VirtualLoadQueue已完成原生 UT 与覆盖迭代，见 [FreeList](reports/freelist-20261018.md)、[CAM](reports/cam-20261018.md)、[AgeDetector](reports/age-20261018.md)、[VLQ](reports/vlq-20261018.md) 证据。RAR已执行完整覆盖迭代，但存在release合同失败，47通过/7失败，**尚未验收**，见 [RAR](reports/rar-20261018.md)；继续独立RAW等UT，不以缺陷存在阻止其他有意义的进展，也不降低父级通过标准。

RAW已完成32例原生UT及覆盖迭代，60/60语义、本体4005/4005、真实闭包5139/5139，另有独立公开输入历史审计，见 [RAW](reports/raw-20261018.md)。继续UncacheEntry全16个ID等剩余模块；RAR保持未验收。

全部16个UncacheEntry已完成384例，分别106/106行、ID0语义75/75、其余77/77，见 [UncacheEntry](reports/uncache-entry-20261018.md)。其真实父级LoadQueueUncache以及Replay、Store分支和组合层仍未验收。

真实LoadQueueUncache已完成逐拍参考、缺口补例和72例重跑，64 PASS/8 FAIL、40/42 checked，仍**NOT_PASS**。7个合法SID重用反例与1个仅UNIT-INTERFACE多MMIO边界分开记录；本体1120/1126、真实闭包3169/3175，剩6条guarded defaults有结构证明且保留原分母。见 [LQU](reports/load-queue-uncache-20261018.md)。继续独立Replay，不删除RAR/LQU未验收项。

Replay也已执行完整覆盖闭环：`replay-expanded-03`为131例127 PASS/4 FAIL、84 reached/82 checked，本体25806/25806、真实3文件闭包30500/30500；20954条连续记录、360个输入lane×slot×固定bank成功见证及127份启动文件SHA已审计。LRQ-STRICT-001仍NOT_PASS，见 [Replay](reports/load-queue-replay-20261018.md)。为不虚假完成Load阶段且继续有意义工作，持久化计划合并Load/Store独立业务实施阶段，保留全部任务/完成标准和三项局部验收受阻；当前推进EnterSbufferQueue，后续完整组合层不删减。

独立Store叶子EnterSbufferQueue现已验收：26 PASS、78/78 DA、34/34 checked，首轮17条可达缺口分类后补例闭合；4582条公开历史审计的4256次接受=4252消费+4 reset中止，credit只在真实Sbuffer消费上记账。见 [EnterSbufferQueue](reports/enter-sbuffer-queue-20261018.md)，后续UnalignQueue/ForwardModule和父块仍待完成。

UnalignQueue也已验收：41 PASS、44/44 DA、40/40 checked，7条可达缺口逐项分类后补例闭合；5947条公开历史审计，1967分配=1726消费+237取消+4 reset中止，取消后同物理槽新UID完成证明完整，146份快照哈希核验通过。见 [UnalignQueue](reports/unalign-queue-20261018.md)，推进ForwardModule及其VA别名历史回归，父块仍未验收。

阶段回归03已核验849例/31独立DUT，830 PASS/19 FAIL，保留RAR7/LQU8/Replay4，148冻结文件和全部artifact/build SHA一致，报告[回归03](reports/lsq-progress-regression-03-20261018.md)。ForwardModule新目录初批另运行34例31 PASS/3 FAIL，24/62 checked；虽253/253 DA但FWD-ALIAS-001跨word VA别名返回旧物理字节，3lane复现，见[Forward阶段报告](reports/forward-module-20261018.md)。当前仍实施剩余Forward功能，不将缺陷或DA全满当作结束整个任务的理由。

Forward后续完整冻结回归`forward-expanded-02`为184例165 PASS/19 FAIL、64/64 reached与61/64 checked，仍253/253 DA；5599条公开历史、192个lane×slot和6条pre-edge live边界独立审计，163份启动文件结束SHA一致。新增FWD-SQID-001（裁剪后完整依赖身份）和FWD-RANGE-001（跨段mask标记未写字节）；ALIAS3/SQID6/RANGE10，17个生产者域失败与2个接口mask压力分列，仍NOT_PASS。剩余验收受这三项严格失败阻止，独立推进[VSQ用例前合同](contracts/virtual-store-queue.md)，不把局部blocked升级成整体unmet，也不改写旧849例回归证据。

VSQ现已完成42例40 PASS/2接口FAIL、1438/3125→3125/3125 DA、32/55→54/55 checked；首轮1687行逐项分类并补齐，4531条公开历史、1024个入口×虚拟槽、36条取消后同槽新UID退休和178源SHA已审计。VSQ-REDIR-IF-001仅同拍dispatch/redirect接口边界，完整真实上游路径表明正常producer互斥；严格边界未通过，不混称架构缺陷或整体验收。见[VSQ报告](reports/virtual-store-queue-20261018.md)，继续DeqModule及真实PSQ/SQ/LoadQueue/LsqWrapper。

新阶段回归04已完整执行1075例/33独立DUT，1035 PASS/40 FAIL，66功能组、180份启动源与全部产物/build SHA通过门禁；35生产者域与5接口边界失败分列，六条LQU guarded defaults重新窄证明且保留原分母，见[回归04](reports/lsq-progress-regression-04-20261018.md)。此运行不含Deq功能目录，不能将其新增失败追溯混入。

当前DeqModule已保留真实EnterSbufferQueue完成原样构建和28例定向迭代：22 PASS/6 FAIL，本体34/46→46/46、闭包101/124→124/124、17/44→25/44 checked；23条缺口逐项分类后补NC/IO/奇数尾用例。DEQ-WB-001在三个实际writeBack fire中丢失Cache denied/corrupt已独立审计；仍需完整生命周期参考/PSQ代理、19项剩余语义、合法随机和完整历史，不能因行满或首轮缺陷结束。见[Deq阶段报告](reports/deq-module-20261018.md)，后续PSQ/SQ/LoadQueue/LsqWrapper完整范围不变。

Deq后续公开分阶段参考、独立读取/释放代理和完整历史审计已完成：`deq-lifecycle-expanded-03` **89例71 PASS/18 FAIL、44/46 checked**，本体46/46、闭包124/124；9746记录、3035 UID=2835完成+4 reset中止+196失败停留、256 SQ编码、201源结束SHA审计通过。9个WB错误与9个新split尾段wline被相邻zero污染失败分列；后者另有4个实际Sbuffer fire。普通语义补齐，未通过两项保留；接续[真实PSQ用例前合同](contracts/physical-store-queue.md)，不把外部PSQ代理当真实父级或推断架构后果。

真实PSQ已完成五文件原样构建及首轮→1704条缺口分类→两长流补例：`psq-expanded-01` **23例18 PASS/5 FAIL、21/43 checked**，本体3733/5396→5387/5396、闭包4113/5817→5772/5817；2947记录/957检查、384个新普通/CBO owner全部实际完成及213源SHA独立审计。3个WB错误和2个split wline错误已通过真实PSQ公开输入复现，不扩大为实际VSQ/Backend可达。当前仍实施剩余22项语义、45条DA、完整阶段参考/恢复/UQ/合法随机；见[PSQ阶段报告](reports/physical-store-queue-20261018.md)，不以99.83%本体行覆盖或故障存在提前结束。

PSQ后续逐行补例、完整公开阶段参考/外部actor及独立审计已执行：`psq-expanded-05` **63例45 PASS/18 FAIL、45 reached/39 checked**，本体5396/5396、真实五文件闭包5817/5817，旧45条缺口全闭合。7424公开记录、1429 actor UID=1097完成+1取消+3 reset中止+328失败保留、另384长流完成、226源SHA核验；两个300 UID必要条件随机完整排空不替代三个失败的完整域种子。新DEQ-ZERO-001有实际零写0次却WB/SQ释放的父级证据；Forward三类及WB/wline严格失败保留。PSQ六项未checked均有真实失败，不虚报完成；推进真实[StoreQueue合同](contracts/store-queue.md)和VSQ/PSQ连接验证，后续LoadQueue/LsqWrapper和最终审计范围不变。

真实StoreQueue已完成首轮3464条、下一轮252条缺口分类与补例；`sq-expanded-03` **79例55 PASS/24 FAIL、51 reached/43 checked**，本体26/26、七文件闭包5504/8968→8968/8968。7114公开记录、1556 actor flow UID=1259完成+10取消+4 reset+1错误提前释放+282失败保留，另128CBO+16普通flow独立完成、全部10取消/4reset同槽新UID完成及253源SHA通过审计。七类实际故障在真实VSQ/PSQ闭环复现，包含新DEQ-FINISH-ORDER-001；剩八项严格失败保留。旧Deq代理在read!=deq时人为屏蔽特殊commit，已依据真实父级可达证据去掉该过窄限制，需新版本回归，不改旧89例/1075例结果。见[StoreQueue报告](reports/store-queue-20261018.md)，继续真实LoadQueue/LsqWrapper完整范围。

源码位置：`../../../XiangShan/src/main/scala/xiangshan/`。下文源码名相对此目录；RTL top 来自 `../../../soc-split/rtl/`，大小写和生成后缀必须原样保留。

**历史297例里程碑（最新317例见下）**：
`lsq-expanded-14`完整297例 **260 PASS/37 FAIL、80 reached/76 checked**，真实
53文件闭包 **59595/59602（99.9883%）**。新44严格例先补合同再执行，补齐三MA
strict/真实第二wake、RAW高组正冲突/原rollback、512槽×CBO×STA实际完成、父池
变长回收对齐和entry0精确未入弹性请求取消；独立58963记录、7264新UID=5120完成+
2144取消，全部取消同LQ新UID真正完成。新增1124条逐行绑定原语义缺口，旧命中
丢失0、原分母不变；仅余7条本层窄证明，不计动态命中。350源结束SHA及全部
产物/build/53原RTL/干净固定开源HEAD核验，原253历史逐bit及37FAIL全部保持。

`lsq-progress-regression-07`首次完整包含 **38DUT/1808例：1649 PASS/159 FAIL**，
76功能组/350启动结束源通过新版v8门禁。1721持久原始日志/270210记录完整SHA
多重集合与各自冻结基线相等，959份另有逐节点轨迹匹配；基础87例原fixture无
持久逐拍JSON，明确不虚构该证据。每个DUT原DA集合/命中集合分别不变。v7叶子
closure字段适配错误连原器保留，v8仅改LCOV元数据核验，未改结果/刺激/RTL。
详见[Wrapper第10节](reports/lsq-wrapper-20261019.md)和[回归07](reports/lsq-progress-regression-07-20261019.md)。
当前原DA余量闭环与当前全38DUT统一回归已经实际执行，但完整合法固定种子混合
随机、联合容量/公平排空、未来新范围回归和最终请求→证据/边界审计仍必需，
不能以行接近满或新增44例全部PASS把阶段/整体虚标完成；所有失败任务保留。

**最新整体317例**：`lsq-expanded-16`为 **269 PASS/48 FAIL、82 reached/76 checked**，
364启动结束源及53原RTL/native/开源干净HEAD复核。此前311例的原始事务历史与48FAIL
不变。8个完整域固定种子仍是首失败前缀，3个新SID例实际在s2得到新owner字节，
不能给它们伪造fair完成。新增6个严格联合定向以22个不同原UID代际同时保留
SQ128/LQ120/RAR96/RAW56/Replay120/Uncache16；18段真实fair服务完成4464原UID，
496取消+496reset均同槽新UID完成；388外部接受=356实际返回+32共同reset中止。
三轮正常跨完整ROB640/SQ256/LQ240，6030grant/6030原slot反馈及2214片段/90WB/54
Cache req/resp独立核验。原LQ199参考影响重跑仍187/12，联合影响审计101738记录
核验原510全部实际历史/60失败主断言不变；参考AST仅reset拍新采集mask=0，
无reset perf流水/knownness/比较不变。原DA全集/命中仍59595/59602、50513/50520。
新联合正条件不是更保守随机替代品，三个STRESS仍未checked；完整混合随机、
恢复交错、扩大的38DUT统一回归及最终请求→证据/边界审计仍必需。详见
[联合容量报告](reports/lsq-joint-capacity-20261019.md)与[Wrapper最新报告](reports/lsq-wrapper-20261019.md)。

## 2. 已核对的真实层次

### 最新正常生产者/参考复核（不修改旧里程碑）

**后续S3/exclusive128更新**：新端点75例实际全PASS、452源一致，六真实Wrapper完成
1110 UID；再补Replay120池，1440原owner真正grant/反馈，RAW/Wrapper/Replay自身DA
分别+2732/+6900/+14419且旧命中0丢失。旧LDU-RAR定向默认S3字段和混合171次Replay
伪更新被拒绝，旧15/3、2/6及原效应不改，但非完整正常准入，见
[源关系/端点闭环](reports/lsq-raw-exclusive-20261019.md)。回归10现已实际1708/200结束、430
源一致，1908范围不含新75例。新S3 26例与分阶段27例见页首独立证据；完整混合剩余
失败、S4异常分域、其他128/恢复与最终审计仍必需。

统一回归08已完成完整38DUT/1828例1658 PASS/170 FAIL，371源、1741持久日志/
284165记录和979逐节点映射门禁；每DUT原DA/命中与失败签名都保持，见
[回归08](reports/lsq-progress-regression-08-20261019.md)。新增正常域34例26/8与
18个满127/128/SMF端点2313 UID完成，但旧12个提前ROB退休绿色仍拒绝；CBO的
包字段准入之后又发现NoSpec/BlockBack缺失，相关旧流保持接口证据，见
[复核报告](reports/lsq-normal-domain-20261019.md)。

新真正串行CBO12例7/5、原8串行全域种子8 FAIL，源许可/字段/原UID独立审计完成；
512正常CBO+512年轻Load全完成，实际WB/zero错误保留，原类型/权重/种子与老SB
背压域不删除。见[串行报告](reports/lsq-serialized-cbo-20261019.md)。合法联合容量
与CBO分阶段、公平未完UID、剩余exact128及最终审计仍必需，计划阶段和三个STRESS
不因局部进展而完成。

统一回归09现已实际**1882例1691 PASS/191 FAIL**，411源一致；v10核验1795日志/
346218记录、1033逐节点、各DUT原DA和全部失败签名，见[09报告](reports/lsq-progress-regression-09-20261019.md)。
完整LDU复核另纠正RAR nuke误作C_NK、错拍/换lane反馈和缺revoke；正常定向18例
15/3、原UID恢复及3335新DA见[LDU路由](reports/lsq-ldu-rar-routing-20261019.md)。
新LDU混合保留原8种子/八类型权重，实际2PASS/6FAIL；两PASS完成600/fair及148组
全部取消同槽新UID，六FAIL和保留接口必要合同边界见[混合报告](reports/lsq-ldu-mixed-20261019.md)。
这26例须独立扩大统一回归，不改写09，也不以两个种子或RAR行满代替完整范围。

```text
MemBlock
├── LsqWrapper                         ← 当前整体 DUT
│   ├── LoadQueue
│   │   ├── VirtualLoadQueue
│   │   ├── LoadQueueRAR
│   │   │   ├── FreeList
│   │   │   └── LqPAddrModule
│   │   ├── LoadQueueRAW
│   │   │   ├── FreeList_1
│   │   │   ├── LqPAddrModule_1
│   │   │   └── LqMaskModule
│   │   ├── LoadQueueReplay
│   │   │   ├── FreeList_2
│   │   │   └── AgeDetector_36 × 3
│   │   └── LoadQueueUncache
│   │       ├── UncacheEntry / UncacheEntry_1 … _15
│   │       ├── FreeList_3
│   │       └── 仲裁与流水寄存器
│   └── StoreQueue
│       ├── VirtualStoreQueue
│       └── PhysicalStoreQueue
│           ├── ForwardModule
│           ├── DeqModule
│           │   └── EnterSbufferQueue
│           └── UnalignQueue
└── ExceptionInfoGen                    ← 相邻 MemBlock 子块，不在 LSQ 内

Backend / CtrlBlock
└── LsqEnqCtrl                          ← 相邻分配控制，不在 LsqWrapper 内
```

省略了 DelayN、通用 arbiter 等辅助实例。`ExceptionInfoGen`、`LsqEnqCtrl` 虽在 `mem/lsqueue/` 源目录定义，却不是 LsqWrapper 的子模块；前者留给 MemBlock 异常汇聚专项，后者作为 LSQ 完成后的分配/恢复联调对象。

依据：`mem/lsqueue/LoadQueue.scala:229-233`、`LSQWrapper.scala:158-159`；`NewStoreQueue.scala:1569-1571,2137-2138`；`mem/MemBlock.scala:549,587`；`backend/CtrlBlock.scala:119`。

## 3. 基线配置与变体映射

源码 `Parameters.scala:102-113` 和当前实例对应的主要配置：VLQ=120、RAR=96、RAW=56、Replay=120、Uncache entries=16、物理 SQ=64、SQ Multiple=2、SnapshotInterval=1、UnalignQueue=2。当前有 3 路 load、2 路 store，默认 DCache 是双通道。

| 家族 | 真实 RTL top | 当前归属/区别 |
|---|---|---|
| FreeList | `FreeList` | RAR，96 entries，非预分配 |
| FreeList | `FreeList_1` | RAW，56 entries，预分配 |
| FreeList | `FreeList_2` | Replay，120 entries，预分配 |
| FreeList | `FreeList_3` | Uncache，16 entries，预分配 |
| 地址 CAM | `LqPAddrModule` / `LqPAddrModule_1` | 分属 RAR/RAW，地址编码、比较规则、写入延迟不同 |
| mask CAM | `LqMaskModule` | RAW 字节 mask 相交 |
| age selector | `AgeDetector_36` | LSQ 本地实现；40 entries、3 路 enq；Replay 的 3 个 bank 各实例化一个 |
| Uncache entry | `UncacheEntry` … `UncacheEntry_15` | entry index 特化，共用语义模型但逐 ID 检查路由 |

后缀不可随意替换，也不能使用别的模块里同名的 FreeList/AgeDetector。先覆盖此实际配置，不承诺任意参数 sweep。SnapshotInterval 当前源码要求为 1；RAW=56、VLQ/Replay=120 不是 2 的幂，指针不可按简单二进制截断模拟。

FreeList 源码的 `allocateReq`、`empty` 等端口可能在现成 SV 中被常量传播删除；合同以实际公开端口为准，不绑定不存在的信号，也不把缺失观察点标成已测。

## 4. DUT 清单、层级与实施顺序

闭包是当前生成 RTL 的文件去重统计，含注释/空行；非编译通过证据，不可跨行相加。

| 层 | DUT | 闭包文件 / 行数 | 先完成的主要依赖 |
|---|---|---:|---|
| L0 | FreeList 四变体 | 各 1 / 2,281、1,537、2,784、618 | 各自公开接口与合法分配域 |
| L0 | PAddr 两变体、Mask CAM | 4 / 2,491；4 / 1,975；4 / 1,749 | bank 写入、读延迟、地址/mask 编码合同 |
| L0 | AgeDetector_36 | 1 / 12,371 | 旧/新状态与端口年龄优先级合同 |
| L0 | UncacheEntry 家族 | 首个 1 / 485，其余各 1 / 488 | ID、ROB 头、响应和取消合同 |
| L0 | EnterSbufferQueue / UnalignQueue / ForwardModule | 各 1 / 298、259、11,476 | 输入顺序、指针和协议合法域 |
| L1 | **VirtualLoadQueue** | 1 / 23,251 | numLsElem/区间、完成与恢复合同；不依赖 FreeList |
| L1 | VirtualStoreQueue | 1 / 17,648 | 虚拟/物理指针、退休/preCommit/恢复合同 |
| L1 | LoadQueueRAR | 6 / 19,059 | RAR FreeList、地址 CAM |
| L1 | LoadQueueRAW | 12 / 26,497 | RAW FreeList、地址/mask CAM |
| L1 | LoadQueueReplay | 3 / 85,650 | Replay FreeList、AgeDetector_36 |
| L1 | LoadQueueUncache | 22 / 17,572 | UncacheEntry、Uncache FreeList、仲裁适配 |
| L1 | DeqModule | 2 / 1,006 | EnterSbufferQueue；外部 Cache/Uncache/Sbuffer 代理 |
| L2 | PhysicalStoreQueue | 5 / 29,020 | ForwardModule、DeqModule、UnalignQueue |
| L2 | StoreQueue | 7 / 48,452 | VirtualStoreQueue、PhysicalStoreQueue |
| L2 | LoadQueue | 45 / 174,829 | VLQ、RAR、RAW、Replay、Uncache |
| L3 | **LsqWrapper** | **53 / 227,749** | LoadQueue、StoreQueue，保留真实 RTL |

首批建议：**FreeList → FreeList_1 → VirtualLoadQueue**。前两块确认原生初始化、采样和 checker 链路，VLQ 作为第一个业务 DUT；之后按依赖完成其余基础块和两条业务分支。此为工程顺序，不是把 FreeList 虚构成 VLQ 子模块。

完整 LSQ 验收前须覆盖四个 FreeList 变体和 Uncache 的实际 ID 特化。DelayN/通用仲裁先在业务父块中验证连接影响，除非有独立风险，不先扩成通用组件项目。`LqRawDataModule` 是抽象类；Bundle/Ptr 是类型；未在本子树实例化的 `LqVAddrModule` 不列为本轮 DUT。

## 5. 子块最少功能集合

下列 ID 为计划功能组，**不是已实现的可执行 coverage schema**。

### 基础块

| 功能组 | DUT | 必查项 |
|---|---|---|
| LSQ-FL | FreeList 家族 | 复位槽位集合、合法多路分配、耗尽、回收、同拍分配/回收、回绕、无重复活跃分配；预分配延迟与分 bank 回收批次 |
| LSQ-CAM | PAddr/Mask CAM | 写生效延迟、同步读/read-enable 保持、比较结果、RAR/RAW 编码、mask 相交、wline/cacheline 选择 |
| LSQ-AGE | AgeDetector_36 | ready 子集内最老选择、同拍多 enq 的年龄、deq/重用冲突、空结果；确认使用旧状态而非误作零延迟 next-state |
| LSQ-UE | UncacheEntry 家族 | MMIO 等 ROB 头与 NC 发起规则、请求背压、mid/sid、响应、wakeup、bypass 消费、错误、各阶段 redirect |
| LSQ-ESB | EnterSbufferQueue | 多路顺序约束、背压、满空、同拍出入复用、deqPtrMove 与真实消费关联 |
| LSQ-UQ | UnalignQueue | 第二物理页地址、SQ 索引、addrReadyPtr 门控、redirect、回绕、合法 one-hot 入队 |
| LSQ-FWD | ForwardModule | 年龄域/回绕、年轻匹配 store、字节范围、跨 16B/跨页、数据未就绪、虚实地址不一致、CBO、无效槽排除 |

FreeList 的 `validCount` 是已分配/占用数，不是空闲数；回收 mask 到再次可分配有流水延迟，不假设同拍 free 立即可用。CAM 同地址多写等非法输入单列负向测试，不作为普通功能随机。

### LoadQueue 分支

| 功能组 | DUT | 必查项 |
|---|---|---|
| LSQ-VLQ | VirtualLoadQueue | numLsElem 连续区间、稀疏 lane、非 2 幂回绕、乱序完成/连续头释放、replay 不完成、redirect 多拍恢复、SQ 可接收约束 |
| LSQ-RAR | LoadQueueRAR | 何时分配、ldWbPtr 释放、release 前后拍窗口、NC/released、年轻 load 命中、partial-address/hash、1/2 拍 revoke、full 的容量预留 |
| LSQ-RAW | LoadQueueRAW | 未决老 store 分配域、地址与 mask、最老违规 load、wline、tlbMiss 屏蔽、选择流水中的 redirect/revoke、回绕 |
| LSQ-LRQ | LoadQueueReplay | 原因优先级、分配/重用、分 bank 年龄选择、ready/背压、各类 hint/wakeup、store 唤醒取消和实际 data 写入、再 replay/完成、redirect、specialMode |
| LSQ-LQU | LoadQueueUncache | 输入排序/过滤、容量不足 rollback、entry 分配/释放、mid→sid、MMIO/NC 仲裁、唤醒/数据 bypass、异常/取消 |

VLQ 的 `committed` 是 load 完成状态，**不是 ROB 架构退休**；ldin.ready 常真也不等于每次 ldin 都完成，还要检查 need_rep/updateAddrValid。RAR 的 lqFull 不是“零空槽”，存在双请求重放相关预留。RAW 选择延迟与配置相关，不凭印象写周期常数。

Replay 当前有 13 类 cause，含提前/延迟 hint、store 取消和长驻留 specialMode，复杂度较高，不先从它起步。源码统计/调试位在 release SV 未必保留，功能合同逐项审查。

### StoreQueue 分支

| 功能组 | DUT | 必查项 |
|---|---|---|
| LSQ-VSQ | VirtualStoreQueue | numLsElem→物理区间快照、虚拟/物理容量、ROB head/退休/preCommit 差异、idle/release/walk、连续 redirect、多圈 flag |
| LSQ-DEQ | DeqModule | committed/retired 边界、cacheable→Sbuffer、MMIO/NC→Uncache、idResp/resp/writeback、CBO、跨页第二地址、drain、异常/WFI |
| LSQ-PSQ | PhysicalStoreQueue | STA/STD 先后、ready 指针/位图、issuePtr/physicalUpper、转发与出队并发、取消、旧写入不得污染复用槽 |
| LSQ-SQ | StoreQueue | VSQ/PSQ 区间、退休/preCommit/恢复/释放反馈；empty/full、forward、写出与异常一致 |

ForwardModule 必须包含历史回归 `88fb444c5`（2026-10-13）：老 store 经 VA1、较新但仍早于 load 的 store 经 VA2，二者映射同一物理地址，load 经 VA1。应按合同识别虚实 CAM 不一致并要求重放，不能把老 store 旧值当作安全完成；还需反例，晚于 load、无效槽或无字节重叠的物理命中不能错误参与判断。

## 6. 组合层验收

### L2：LoadQueue / StoreQueue

- LoadQueue：真实 VLQ 的 ldWbPtr 与 RAR/Replay 对接；RAR/RAW 容量与 replay；Uncache 唤醒、数据返回与 replay；共享 ldin/redirect 的不同流水延迟。
- StoreQueue：真实 VSQ→PSQ 的区间、preCommit、retired、redirect；PSQ→VSQ 释放反馈；转发、写出和非对齐队列并行。
- 保留子块回归，再增加独立组合不变量；不简单汇总子块覆盖率或把真实子块替换为 Python 模型。

### L3：整体 LsqWrapper

| 场景组 | 必查结果 |
|---|---|
| INT-ALLOC | 混合分配，needAlloc/numLsElem/start/end 一致；一边受限时联合 canAccept |
| INT-FWD | STA/STD 乱序就绪下正确转发或重放；别名、字节/跨页、回绕、槽位复用 |
| INT-REPLAY | SQ readiness、storeDataWrite、wake/cancel 的真实连接；满足实际释放条件才重发 |
| INT-VIOLATION | Store 地址迟到触发 RAW rollback；RAR/release 参与重执行；取消条目不误触发 |
| INT-UNCACHE | Load/Store 共用请求仲裁，pendingstate/uncacheOutstanding，idResp/resp 的 is2lq 路由不串单 |
| INT-REDIRECT | redirect 与写入/完成/请求/响应/回收同拍；恢复阻塞、恢复指针一致，旧事务不污染新条目 |
| INT-COMMIT | ROB 提交/退休、Sbuffer/Uncache 写出、dequeue 计数，路径不重复完成 |
| INT-EXCEPTION | MMIO/NC 错误、load/store 异常有效信息透传；不冒充独立 ExceptionInfoGen 的选择覆盖 |
| INT-STRESS | 合法并发、容量边界、非 2 幂多次回绕、背压、scalar/vector 元信息；活性注明公平性/超时假设 |

L3 保留 LsqWrapper 全部真实子块。外部代理模拟 dispatch/ROB、LDU/STA/STD、Cache release/refill/hint、Uncache、Sbuffer 边界，不接入 Python LoadQueue/StoreQueue 来替代硬件。

LsqEnqCtrl 在 L3 后做相邻专项：先独立 UT，再验证真实端口上的 rename/dispatch 预分配与 LSQ 恢复反馈。多 DUT 连接或新 wrapper 单独评审，本轮不生成；此专项通过不等于 Backend 已验收。

## 7. 开始用例前的合同门禁

每个 DUT 需明确：

1. 唯一 key、精确 top、导出类名、父实例/参数、闭包/哈希；不模糊匹配第一个同名后缀。
2. 真实端口方向/宽度、分组、常量/优化删除字段；初始化所有真实输入，不驱动输出。
3. 分配、完成、redirect、forward、wake/hint、uncache request/idResp/response、retire/writeout 等领域事务到信号的映射。
4. valid/ready 与 Valid-only 的区别、允许的 lane 顺序、取消规则、公平性；不把随机 bit 组合当合法事务。
5. 发送/采样/检查的周期和相位；事务语义与时序适配分离，不用散落 Step(n) 修补 checker。
6. 独立环形年龄模型：LQ 非 2 幂、SQ multi-flag、ROB slot/必要的 uopIdx；不以普通整数比较替代。
7. don't-care：无 valid 的 payload、未初始化/已取消数据、源码 DontCare、当前未保留功能；不比较未定义值，不把它们标成已通过。
8. 每个功能点绑定实际观察和结果检查，具备最小定向向量、合法随机种子及产物位置。

参考语义不要复刻 RTL 位矩阵：FreeList 用独立槽位与延迟回收账本，AgeDetector 用序列年龄，业务队列用事务生命周期和字节/顺序关系。内部 memory-direct 信号只辅助定位，不能作为模型正确答案。

## 8. 分层通过标准

- 运行门禁：补齐本工程工具/ABI/coverage 锁；原生 DUT 真正可导入、实例化、初始化、走时钟，不只看导出退出码。
- 子块：每个必需功能点既 reached 又 checked；定向和合法随机通过，日志/种子可复现；原生行/分支分母与缺口有说明，无点不算 100%。
- 变体：四个 FreeList 不能只测一个；UncacheEntry 共用模型但需检查全部实际 ID 的路由特化和关键边界。
- 组合：进入父块验收前完成必需下级的合同与单测；保留回归，增加真实连接检查与并发。
- 整体：INT 场景有独立证据，所有必需子块/分支通过；缺失端口或未实现能力列未覆盖，不以高行覆盖抵消。
- 产物：每次运行独立 results 目录，记录测试/功能点、种子、波形策略、RTL/导出包/工具版本和覆盖分母。

当前顺序见目标持久化计划：四个 FreeList 完成后先做地址/mask CAM、AgeDetector，再交付 VirtualLoadQueue 独立 UT；不要直接把 53 文件交给 picker 后以整体 smoke 替代分层验证。
## 最新阶段进展：回归06及真实LoadQueue启动

[回归06](reports/lsq-progress-regression-06-20261018.md)已审计1312例/36DUT：
1202 PASS/110 FAIL、72功能组、256启动结束源SHA一致。Deq扩大真实父级许可域
后为92例67/25、43/47 checked，新增独立UID审计；PSQ66例45/21、39/46 checked，
63旧例全引脚历史逐bit重核及3个新完成顺序证明。回归05的参考相位误报和v5
分类错误均保留旧证据，以新参考/新版审计纠正，不缩小刺激或修改目标RTL。

真实LoadQueue用例前合同见[load-queue](contracts/load-queue.md)；45文件原样
Picker构建、实例化走钟和622/266适配已完成。五个真实下级的旧状态阶段参考、
独立外部UID actor已运行并迭代：`lq-expanded-03`33 PASS，闭包20029/50520→
28841/50520、18/63→31/63 checked，首轮30491条和本轮21679条缺口均逐行分类。
独立新版历史审计核验3112记录、834 UID全部完成、120槽/8入口/3bank和16 entry×
NC/MMIO的32种真实完成链，274源结束SHA一致。见[LoadQueue报告](reports/load-queue-20261018.md)。
以上为33例轮当时进展，不是当前验收结论。后续`lq-expanded-04`完整148例136 PASS/
12 FAIL，60/63 checked、44962/50520真实闭包；3个release、3个disabled strict和
6个合法SID复用失败已独立在父层复现。16603连续记录、3069 UID=3017完成+26取消+
5reset+21失败保留，全部31取消/reset同槽新UID完成、360 Replay slot×入口、全部
原因和32 entry×类型见证及282源SHA已审计。v3的全局峰值统计误加各case峰值，
不作为容量证据，旧报告保留并用新版审计纠正。5558行缺口逐项分类后新增13例已
实际通过，2232 UID全部完成；批量回收/全entry恢复及剩余逐行收敛继续进行。
后续`lq-expanded-06`完整199例为187 PASS/12 FAIL、60/63 checked，闭包50513/50520；
剩7条逐行窄证明保留原分母。v4独立核验28820记录、8873 UID=7477完成+1370取消+
5reset+21失败保留、1375同槽新UID完成、96 entry×类型×lane，288源SHA一致。
LoadQueue三项严格失败不验收；阶段门禁再次阻止未验收业务之后启动整体，故仅把
原pending的lsq-contract/lsq-tests/lsq-coverage三任务合并到当前实施阶段，不将
任何失败任务/阶段标complete。LsqWrapper[用例前合同](contracts/lsq-wrapper.md)
已定义82项可读语义，真实603输入/458输出，256全字段静态往返/11非法包/14伪内部
反馈拒绝已核验；53文件原样Picker构建/实例化走钟已PASS。整体首22例→35428行
缺口分类→单侧总线8补例→完整30例PASS，8/82→14/82 checked、闭包24174/59602→
24386/59602，本体109/114→114/114不能替代整体语义。新审计核验原22例全部实际
输入/pre/post/tick逐bit匹配已独立审计初轮，新8例298记录/8 bus事务独立路由和
原数据/错误完成证明，305源SHA一致。当前剩35216条DA已逐行分类、68项功能未
checked、12路Store perf当时未建模。后续`lsq-expanded-03`完整49例PASS，14正常
混合总线+4明确UNIT-INTERFACE仲裁+128-flow补例，12路Store perf已建模且各有
0/1实际见证；独立2474记录/52908 perf比较、全部原30例输入/pre/post/tick逐bit
复核，308源SHA一致。闭包25684/59602、29/82有成功checked见证，剩33918条
逐行分类。进一步补三笔交错与合法SID复用后，`lsq-expanded-04`完整69例59 PASS/
10 FAIL、30 reached/29 checked、28035/59602；新LSQ-BUS-OWNERSHIP-001四例为旧NC
Load响应提前解锁后来的串行IO Store，SID异常污染六例在真实Wrapper复现。
v3独立3444记录、原49例全部原始采样逐bit匹配、新48 UID=24完成+24失败保留、
73548 perf比较和312源/产物SHA一致。31567条剩余DA再次逐行分类；串行/路由
bin已有成功见证不抵消其新增必需子情形失败。公开producer窄审计与boot空拍
误报拒绝记录保存，未声称Backend/架构后果。完整Forward/RAW/RAR、其他子块
缺陷整体复现、Load容量/两分支多圈、共享恢复/reset及完整合法随机仍须推进；见
[整体报告](reports/lsq-wrapper-20261018.md)。所有范围保持，整体目标active。

随后新增真实Forward/共享STA→RAW/缓存Load RAR63例，首132例expanded-05为
104 PASS/28 FAIL，三个同VA对照helper过严已连原317源快照保留；修正为真实
multi-match Replay/SQ empty/原slot反馈后，expanded-06完整132例**107 PASS/
25 FAIL、53 reached/51 checked、29054/59602**。新独立memory-v1审计6526连续
记录、原69例全部原始采样逐bit重核、新907 UID=669完成+4取消+234失败保留，
603 Store/615片段/66 Load实际完成，所有4取消Load均同LQ槽新UID完成。RAW两路
实际恢复字段/最老MDP及共享两分支真实恢复，RAR实际VIOLATION Replay均有见证；
Forward三类3+6+3和前拍release3已在Wrapper复现，加旧bus/SID10共25普通FAIL。
control-v1证明三个旧失败采样逐bit为新对照前缀，未放宽PA字节性质。Forward
DA满仍不验收；补例新增1019条DA后余30548条逐行分类，317结束源及全部产物SHA
一致、53原RTL SHA匹配且开源树干净。Store特殊完成/错误/zero、Replay全池/严格/
禁用/特殊模式、RAR/RAW全池/NC/头回收、完整恢复/reset/多圈/合法随机及最终
全范围审计仍未完成，不能用本层132例代替完整目标。

### 2026-10-19：真实全池、Store特殊副作用及178例完整重跑

按上述30548条缺口补40例后，`lsq-expanded-08`完整172例 **136 PASS/36 FAIL**，
66 reached/63 checked，闭包 **48947/59602**，较06新增19893 DA。独立population-v1
核验16492连续记录、旧132例原始采样逐bit不变；新Replay2205 UID=2196完成+9失败
保留、1206次grant/原slot反馈、360 slot×S3入口、960多flow/8dispatch/全LQ flags
实际完成。Store20含4严格逐拍例及16明确protocol-only probe，后者不冒充458输出
比较；独立在实际WB/Sbuffer fire与SQ release复现WB3、zero1、split-wline1、完成
顺序3，加disabled strict3共11新增普通FAIL，原25不变。19个重复tick日志错误和
2个头移动/触发同拍helper错误原件保留，helper-v2独立核验纠正，不改RTL或阈值。

再按10655条余量补真实RAW/RAR容量6例，`lsq-expanded-09`完整178例 **142 PASS/
36 FAIL、68 reached/64 checked、53480/59602**，再增4533 DA。nuke-population-v1
独立重建17605记录、旧172全部input/pre/post/tick逐bit不变，新增744原UID全部
完成；三查询入口各实际接受RAW56/RAR96，真实容量拒绝和C_RAW/C_RAR阻塞仅经
实际STA指针/VLQ头自然回收后解除，未伪造NC标签或内部反馈。327启动结束源、
全部artifact/build SHA一致；原53RTL再次匹配，开源树干净且HEAD固定。

剩6122条逐项分类：VSQ1673、Replay815、LQU745、entry880、四FreeList1426、PSQ386、
RAW192、UQ4及VLQ1。不把满池或DA满冒称每项元信息/正选择已穷尽；真实NC RAR、
完整多圈/flags、共享redirect/reset/已发及已缓冲响应清理、取消/reset同槽新UID
完成、合法全域混合随机与公平排空、扩大全范围回归及最终审计仍必需。见
[最新整体报告](reports/lsq-wrapper-20261019.md)，完整目标active，未验收。

继续按6122条余量补16例，`lsq-expanded-10`完整194例 **157 PASS/37 FAIL、
69 reached/65 checked、55502/59602**。新1024个不同ROB的单flow Store uop在八个
dispatch来源各填128虚拟槽，8个原Load独立完成；全256 SQ编码和ROB flag/former
四组合由原PA字节实际消费/连续释放证明，不把旧8×16-flow向量例当成128uop覆盖。
真实ROB头普通allValid项允许preCommit，不人为要求严格早于头；独立审计的7次
头许可fire单列，不混同退休。Replay另补三路MA/TLB/MSHR不同单hot原因、STD issue
唤醒/次拍实际写入、Cache/Way retry各S3来源、真实VLQ头在bank1/2的后续优先选择。
新全池strict仍在真实SQ指针0且仅SQ7就绪时tick312提前valid，成为第37个普通FAIL。
两个初始!ready头选择helper过严已连旧失败/331源保留，新审计证明旧采样为纠正
例前缀、先原候选fire再选真实头及120 UID完成，其他13 Replay历史/结果不变。

wrap-history-v1独立核验22029记录、旧178全部input/pre/post/tick逐bit不变；新增
1924UID=1796完成+128全池strict失败保留，728grant/slot反馈和1024+36原字节片段。
332启动结束源、全部产物/build SHA及原53 RTL/干净开源树一致。DA增量v2逐条核验
新增2022（VSQ1666/Replay89/池263/PSQ4），原59602集合不变、旧命中丢失0。
剩4100逐条分类：VSQ7/Replay726/LQU745/entry880/四池1163/PSQ382/RAW192/UQ4/VLQ1。
仍须两MA混合严格保存/回收、全entry/真实NC、共享恢复/reset/已发已缓冲总线清理、
取消/reset同槽新UID完成、全域随机公平排空和最终全层回归审计，目标继续active。

继续按4100条缺口补15个真实Uncache/NC RAR例和1个同时两MA+TLB全120池例，
`lsq-expanded-11`完整210例 **173 PASS/37 FAIL、72 reached/68 checked、
57395/59602（96.2971%）**。新336启动结束源、全部artifact/build SHA及原53RTL/
开源固定干净HEAD核验。uncache-history-v2独立26422记录、旧194全部原始采样逐bit
不变；新446UID=443完成+3取消，306原请求/方向ack/响应/Replay/bypass数据消费、
144个mid×NC/内存MMIO/IO×bypass lane组合，九例各两代mid0..15实际完成。NC公开
未消费mid峰值16，MMIO串行峰值1单列；不冒称私有entry并行状态，也不将SID归还
延长到消费来规避原6个SID失败。MMIO不越过最后错误ROB头宣称退休。

真实NC RAR来自实际回包/Replay/bypass的NC数据，3个同line正例实际C0原slot重读
取得新响应，再经独立branch共享部分恢复清理年轻后缀；不声称RAR自动产生该
redirect。3个已S3完成但未VLQ释放的取消Load均同LQ物理槽新UID实际bus/bypass/
VLQ完成，退休但Sbuffer背压的老Store原字节仍消费。3个不同line负对照不误报，
无给缓存Load伪贴NC。新两MA strict+TLB仍为单hot各自原因，由真实Store7/wake及
TLB广播解除，120原slot反馈和8个Store片段完成。

旧uncache-population-01有3个消费代理固定等LQ2超时，原335源/失败保留，公平
消费实际候选后15例PASS再完整重跑；v1审计又误猜下一候选8，原器与拒绝SHA保留。
v2复用相同独立事务核心，证明前三个失败各前84原始采样相同、tick170实际合法
消费持有集合{3,4,8}中的LQ3，其他12例历史不变，不修改DUT/测试或放宽字节检查。
DA增量v3逐条核验新增1893：LQU724/entry784/Replay320/两池65，原59602集合保持、
旧命中丢失0。剩2207全部逐行分类：四池1098/Replay406/PSQ382/RAW192/entry96/
LQU21/VSQ7/UQ4/VLQ1。仍需完整shared恢复/reset、全entry取消/复用、已发已缓冲
总线外部义务清理、原分母内窄证明、全域合法随机/公平排空及最终全层回归审计。

继续补共享恢复/reset及LQU满池拒绝43个严格例，纠正非法前导后的
`lsq-expanded-13`完整253例 **216 PASS/37 FAIL、80 reached/76 checked、
58471/59602（98.1024%）**。346启动结束源/全部产物SHA及原53RTL/干净开源固定
HEAD核验，旧210全部原始input/pre/post/tick逐bit不变；16个旧protocol-only
probe继续显式单列，新43例无弱参考探针。

recovery-history-v2独立34920记录，新1897UID=996完成+848取消+53reset中止，全部
901取消/reset均同物理LQ/SQ槽新UID真正完成（844Load、57Store）。704Load请求+
2实际Store写接受=686原SID真实响应+20共同系统reset显式中止；不伪造消费或
撤销已接受外部Store写。396正常bypass原字节/错误消费另加1个s1→reset拍s2
无reset历史，879Replay grant/876原slot反馈差3为reset中止的已grant原Load，
99个原Store片段真正消费。30双分支恢复/13共同reset、16个mid各resp紧接下一
拍取消、3次LQU14/15/16占用的完整最老拒绝rollback；两分支全取消重填120Replay/
56RAW/96RAR四对齐、退休10个Store前缀的SQ11恢复walk和跨页UQ同槽新PA片段
均有实证。只reset LSQ而外部旧响应继续迟到的不同合同仍未验证，不被共同
reset成功豁免，也不计Backend/ISA后果。

旧uncache-recovery-01的5个代理新旧UID匹配歧义、shared-recovery-01的4个RAW
单调域/UQ恢复接线错误、pending-reset-01的2个异步控制参考错误均保留，11个
原始采样完整逐bit为纠正例前缀。原生12轮253例虽216PASS/37FAIL，独立审计另
拒绝3个把ROB1..3分配在pending9后的绿色前导刺激；仅改为前导pending0，全部
active事务不变后独立重跑13例再完整13轮，v2同一事务核心仍拒绝旧3个绿色
历史，另外250例与12轮原始采样完全一致，不放宽正常退休域或原37FAIL。

对受修改参考影响的5DUT另运行448例383PASS/65FAIL，63887原始记录与各自旧
冻结基线SHA多重集合一致，全部448节点及结果不变；旧无nodeid叶子不伪称逐
节点关联。这是影响回归，不是最后扩大全部38DUT统一验收。
DA增量v4逐条绑定1076新增（四池956/entry94/LQU15/VSQ7/UQ4），原59602集合不变、
旧命中丢失0。剩1131全部逐行分类：Replay406、PSQ382、RAW192、Replay池138、
Uncache池4、entry0请求但尚未入弹性精确取消2、LQU6、VLQ1。后7条已在实际
Wrapper53文件及正常producer连接本层重做窄证明，仍不计动态命中/不删分母；
其余1124未证明不可达。下一批补三MA级联及第二地址wake、RAW高组正冲突、各槽
CBO实际完成/变长返回对齐和entry0精确拍；全域合法固定种子混合随机/联合容量/
公平排空与最后全层回归/请求→证据审计保持必需，整体继续active。
