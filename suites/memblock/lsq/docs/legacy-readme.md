> 迁移前历史说明。当前命令与基线见仓库根 README；以下记录不代表重建版本验收。

# LSQ 独立验证工程根目录

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


**本目录 `memblock-hash/lsq/` 是 LSQ 验证工程根目录。** 后续构建、pytest/xreactor 入口、DUT 包、测试、版本锁和运行结果均相对此目录定位，不以父级 MemBlock 目录或源码仓库为工程根。

目标：像 BPU 的分层方式一样，**内部子模块独立 UT → 分支组合 UT → 整体 LsqWrapper UT**。已开始实际验证，不直接上整块 smoke 代替子模块验证。

**当前实际状态**：统一回归12完整2203例，**1982 PASS / 221 FAIL**；504启动/结束源一致，
2116完整流摘要SHA/460700记录、38DUT原DA及全部221失败主签名门禁完成，0逐拍JSON/
0wave，见[回归12](docs/reports/lsq-progress-regression-12-20261019.md)。这不是整体PASS。
新增精确S4实际**84 PASS**，5592 UID/813次ROB头trap/942同槽新UID完成；自身
26994→49882/59602（+22888、丢失0）、9720剩行逐项分类，见[精确S4报告](docs/reports/lsq-s4-precise-20261019.md)。
本地reset保留外部旧NC请求另有**15 PASS**，132 UID、60旧响应真实返回丢弃且0外部
abort、60同LQ槽新UID完成，自身26573→30075/59602（+3502、丢失0），见[本地reset报告](docs/reports/lsq-local-reset-20261019.md)。
后两批在回归12启动后新增，不能追溯算入其2203节点。旧S4/plain01的hyper/poison/
过早trap准入问题不追溯抹掉；新正条件不替代完整八种子随机、其他128/旧代和最终审计。

完整八类型源关系新尝试`lsq-normal-mixed-source-04`实际**2 PASS/6 FAIL**、542源一致；
23个TLB S2早返回窗口、17个原TLB job/14个原Load Cache job真实偿还，五CBO错误WB和
一个老Sbuffer污染zero的严格FAIL保持。03两个绿色种子的普通同槽复用门禁曾被拒绝，
仅补随机后清理段后，04的441原UID分账闭合、95取消槽均有非fault新UID实际完成。
六FAIL完整流SHA与03相等；自身36925→39695/59602（+2770/丢失0），19907剩行逐项
分类。16B首次vector路由仍未证明，不冒称完整正常producer验收。只压缩04当前native，
前三份大native实际删除不归档；清理后语义/UID/DA三门禁exit0、0临时遗留、results
审计点约825.9MiB。见[混合源关系报告](docs/reports/lsq-normal-mixed-20261019.md)。

**诊断与存储策略已纠正**：逐拍JSON与wave默认关闭，不再每轮保留全量原件。
默认79节点实际重跑78 PASS/1原SID FAIL，0 JSONL/0 waveform；完整4186拍流SHA与旧
原生原件全部相等，约438MiB逐拍JSON改为约49KiB摘要，所有运行时检查继续执行。
前次清理审计点历史`results/`约**755MiB**（此前约262GiB），当时磁盘可用约**375GiB**；
这是回归12启动前的历史快照，不是后续运行中的实时大小。新增批次仍及时收整已结束覆盖中间物。
175个旧运行删除52680个中间文件；另清理无活动runner的旧中止目录，不虚构它已完成。
仅显式选择的主基线及必需大行报告压缩按需复核，不再对所有旧全量日志归档。
历史报告中的“保留原始日志”描述的是当时审计，不承诺所有旧原件仍在磁盘；以每个
目录的`storage-index-v1.json`或`retired-intermediates-v1.json`为当前保留状态。
本轮结束后再次实际收整：`results/`唯一分配约787.6MiB，0 case JSONL/0wave；仅选
回归12/精确S4-03/本地reset-02原生基线压缩，三份被替代native.dat实际删除、不归档。
清理后五个必要门禁再次exit0且221个原FAIL保持，见[收整与按需复核](docs/reports/lsq-post-precise-retention-20261019.md)。

**最新复核（2026-10-19，整体仍未验收）**：38DUT统一回归10已实际结束，
**1908例1708 PASS / 200 FAIL**、430源一致；1821日志/351451记录、1059逐节点映射、
各DUT独立原DA/命中及所有FAIL签名门禁完成，见[回归10](docs/reports/lsq-progress-regression-10-20261019.md)。
旧LDU默认S3字段和Replay伪地址更新被源审计拒绝，旧15/3、2/6及UID/接口效应保留，
不称完整正常域。仅修源三字段后相同26节点实际**17 PASS/9 FAIL**、458源，762次S3
和18次S4源关系核对，全部公开输出/旧9个失败终点保持，见[S3纠正](docs/reports/lsq-ldu-s3-20261019.md)。
向前exclusive128端点及满Replay共75例全PASS，见[端点闭环](docs/reports/lsq-raw-exclusive-20261019.md)。
新合法联合容量/CBO分阶段及串行补例最终**27例21 PASS/6 FAIL**、475源：六个正条件
各三代完整完成，原六SID数据失败逐bit保留；自身50902→52999→**53079/59602**、
增量2097再80且丢失0，6523剩行逐项分类，见[联合分阶段报告](docs/reports/lsq-ldu-joint-phases-20261019.md)。
这些新增范围不追溯混入回归10；完整八类型随机、S4异常分域、其他恢复/128边界、
扩大全范围回归及最终全请求审计仍必需，不能以正条件或本体行满验收。
随后新增34例为26/8，18个合法满SQ/SMF端点独立2313 UID完成，但其CBO部分经
NoSpec/BlockBack门禁仍被拒绝为完整正常程序；不要只看QB包字段或绿色。
新真正串行CBO12例**7/5**、原8串行全域种子**8 FAIL**，真实源许可及字段门禁
仅针对CBO字段/串行许可通过，不等于整段LDU正常；512正常CBO+512年轻Load完成，实际WB错误/zero无原零写等仍复现，见
[串行CBO报告](docs/reports/lsq-serialized-cbo-20261019.md)和[端点/生产者复核](docs/reports/lsq-normal-domain-20261019.md)。
原有317例和相关CBO联合/混合/全槽历史只保留其真实接口结果，不追溯升级正常域。
完整随机/公平恢复、合法联合容量与CBO分阶段、扩大全范围回归和最终审计仍必需。

**历史317例整体里程碑**：真实53文件 `LsqWrapper` 完整
317例 **269 PASS / 48 FAIL**，82 reached / 76 checked；闭包
**59595/59602 DA（99.9883%）**。Replay全120项/3入口、960多flow Load、实际WB/zero/wline/
完成前缀、真实RAW56/RAR96全池头回收，以及八来源各128虚拟uop/1024 Store完整
SQ/ROB回绕、全16 entry两代NC/MMIO/IO及真实NC RAR/实际重读/共享部分恢复已补例
并独立审计；新增共享两分支全池取消、退休前缀walk/UQ恢复及共同系统reset，
901个取消/reset UID均有同槽新UID完成见证。新44例再闭合三路MA strict、RAW高组正
冲突、512个槽×CBO×STA实际完成及真实父池变长回收/entry0精确取消；2144个取消
均有同槽新UID完成。16个明确的协议探针不冒充逐拍全输出参考；原37个普通
失败保留。新增8个固定种子严格混合尝试均中途FAIL，原UID/92次双分支恢复独立
核验；另3个干净s1后的SID复用例实际暴露s2原数据污染，3个不同SID对照完整完成。
旧311全部原始历史/48FAIL不变，不以新失败前缀声称公平排空。新6个联合定向例
实际接口同时保留SQ128/LQ120/RAR96/RAW56/Replay120/Uncache16，18段公平服务完成
4464原UID；992个取消/reset均同槽新UID完成，仍不替代完整随机或勾STRESS总项。
见[联合容量报告](docs/reports/lsq-joint-capacity-20261019.md)；这些旧快照后经源S3/revoke
与CBO许可审计拒绝正常准入，不与新的合法分阶段峰值混称。剩7原DA均有本层
窄证明，不删分母、不计命中；历史完整38DUT/1808例统一
回归为 **1649 PASS / 159 FAIL**，见[回归07](docs/reports/lsq-progress-regression-07-20261019.md)；新增20例不追溯混入该旧范围。完整混合随机验收、全域公平/恢复交错和
最终全范围审核仍必需。见[最新整体报告](docs/reports/lsq-wrapper-20261019.md)
和[完整交付清单](docs/reports/lsq-delivery-checklist-20261018.md)；下列逐块条目含历史里程碑。

## 基线

| 项目 | 值 |
|---|---|
| 源码 | `../../XiangShan/`，开源版 |
| 分支/提交 | `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` |
| 现成 RTL | `../../soc-split/rtl/` |
| RTL 标注配置 | `DefaultConfig`、单核、`top.TopMain` |
| 整体 DUT | `LsqWrapper` |
| 独立子树 | LoadQueue 与 StoreQueue 及其实际内部模块 |
| 排除 | XiangShan-internal；将其他工程通过记录当作本工程证据 |

现成 RTL 的生成来源由已有元数据声明，本轮做了静态层次检查，没有重新生成证明逐文件对应关系。详见 [baseline.json](manifest/baseline.json)。

## 计划与首批路线

- [详细 UT 计划](docs/ut-plan.md)：层次、DUT/变体、检查点、组合场景、合同和验收。
- [MemBlock 总体拆分](../docs/memblock-ut-split.md)
- [LSQ RTL 哈希清单](manifest/lsq-rtl.sha256)：LsqWrapper 静态闭包，53 个文件。

```text
基线/公开信号合同/工具链校验
  → FreeList → FreeList_1：非预分配与预分配的工具链/基础语义试点
  → FreeList_2 / FreeList_3 → 地址/mask CAM → AgeDetector
  → VirtualLoadQueue：第一个业务子模块 → Load/Store 内部业务模块
  → PhysicalStoreQueue → StoreQueue；LoadQueue
  → 整体 LsqWrapper
  → LsqEnqCtrl 相邻接口联调；后续 MemBlock 系统集成
```

这是工程顺序，不表示 VirtualLoadQueue 实例化 FreeList。每个子块使用独立真实 DUT 和 checker；父块测试保留真实子块，检查跨块交互。

## 工程结构

以下目录已创建，按模块逐步填充；目录存在不代表其中所有规划模块已验收：

```text
lsq/                           ← 当前目录
  docs/                        每块合同、已知限制、证据索引
  manifest/                    版本锁、配置、DUT 映射、RTL 哈希
  rtl/<dut-key>/               原样 RTL 与最小 filelist
  dut/<dut-key>/               picker 导出的原生 DUT
  lsqverify/<block>/           transaction / ports / driver / monitor
                               model / checker / case / coverage / env
  tests/<block>/               独立 DUT 与集成 DUT 用例
  tools/                      原样提取、Picker 构建、xreactor 运行、覆盖审计
  pytest.ini                  本工程自己的配置入口
  results/<unique-run>/        种子、结果摘要、FAIL与覆盖；逐拍/wave仅显式调试
```

原生模型、输出路径、pytest fixture 的 root 都应解析到本目录；不得隐式借用 BPU/ICache 的 DUT、model、测试 fixture 或 results。公共设施有实际多模块需求后再抽取，避免空框架。

## 状态与基线检查

- 已完成：源码版本/实际层次复核、分层建议、首批检查点、53 文件的静态闭包与 SHA-256 记录。
- 已完成：实际工具链/ABI/coverage 门禁、四个 FreeList 独立原生 DUT、xreactor 端到端检查与覆盖合并。
- 四个 FreeList 已完成首轮→逐行缺口分析→补例→重跑：52/52 PASS，原始 DUT 行覆盖均为 100%，可读语义情形全部 checked。见 [FreeList 报告](docs/reports/freelist-20261018.md) 与 [功能合同](docs/contracts/freelist.md)。
- 三个地址/字节 CAM 也完成覆盖闭环：24/24 PASS，本体原生行覆盖均为 100%，真实辅助流水的插桩行完整；语义情形 21/21、25/25、24/24 checked。见 [CAM 报告](docs/reports/cam-20261018.md) 与 [功能合同](docs/contracts/cam.md)，其中明确记录零延迟直连子块无 DA 的工具边界。
- 实际40项的 AgeDetector_36：11/11 PASS，语义从9/26提升为26/26；本体行覆盖首轮即100%，补例后维持3285/3285。见 [年龄选择报告](docs/reports/age-20261018.md)，不以高行覆盖跳过功能缺口。
- 已有8个叶子 DUT 同进程完整回归 **87/87 PASS**，全部适用语义与原生插桩行门禁通过。见 [完整叶子回归](docs/reports/leaves-regression-20261018.md)。
- VirtualLoadQueue 也完成闭环：**22/22 PASS**，原生行覆盖30.40%→100%，语义11/43→43/43；4881条逐拍记录另核验指针/计数守恒和恢复输入历史。见 [VLQ报告](docs/reports/vlq-20261018.md) 和 [合同](docs/contracts/virtual-load-queue.md)。现有9个DUT通过不代表整个LSQ通过，继续RAR/RAW等业务子块。
- 上述9个DUT统一回归 **109/109 PASS**，9构建/18功能组的行、语义和哈希门禁通过，见 [基础阶段回归](docs/reports/foundation-regression-20261018.md)。
- LoadQueueRAR已实现独立参考并执行首轮→逐行分类→补例→完整重跑，最终 **47 PASS / 7 FAIL**，本体3898/3898、真实闭包5320/5320插桩行，语义52/55；发现孤立release时序错位 **RAR-REL-001**，**尚未通过**。见 [RAR报告](docs/reports/rar-20261018.md)、[合同](docs/contracts/load-queue-rar.md) 和 [开放问题](manifest/known-issues.json)。失败没有xfail或跳过，不因行覆盖满而验收。
- LoadQueueRAW完成闭环：**32/32 PASS**，本体32.41%→4005/4005、真实12文件闭包5139/5139，60/60语义；11301条逐拍记录另以不导入领域模型的公开输入历史审计，全部336个load入口/账本slot/store入口组合有唯一恢复证明。见 [RAW报告](docs/reports/raw-20261018.md) 和 [合同](docs/contracts/load-queue-raw.md)。
- 当前已实现的11个DUT统一回归 **188 PASS / 7 FAIL**，195例中仅RAR-REL-001重复失败；11构建/22功能组及83份冻结源码的证据审计通过，回归结论仍为 **NOT_PASS**，见 [当前范围回归报告](docs/reports/lsq-progress-regression-20261018.md)。
- 全部16个UncacheEntry ID完成闭环：**384/384 PASS**，各ID100/106→106/106行，语义ID0从17/75→75/75，其余各17/77→77/77。86129条逐拍独立审计核验完整mid/sid、64位data、mask、错误和所有权守恒；80次reset中断单列，不冒充完成。见 [UncacheEntry报告](docs/reports/uncache-entry-20261018.md) 和 [合同](docs/contracts/uncache-entry.md)。ID0无wakeup ready端口、其余有背压的差异如实保留，不能替代父级LoadQueueUncache的独立验证。
- 真实LoadQueueUncache已执行完整逐拍迭代但 **NOT_PASS**：72例64通过/8失败，语义40/42，本体364/1126→1120/1126、真实闭包3169/3175，剩6条guarded default有窄范围结构证明且不改原分母。9163条连续记录/110冻结文件哈希审计通过；7个合法SID重用数据/错误失败，另1个仅多MMIO接口边界（不声称合法ROB流量可达）。见 [父块报告](docs/reports/load-queue-uncache-20261018.md)。
- LoadQueueReplay已完成原生逐拍参考与覆盖迭代，`replay-expanded-03` **127 PASS/4 FAIL、82/84 checked**，本体9560/25806→25806/25806，真实闭包30500/30500；20954条记录及127份快照哈希审计保持 **NOT_PASS**。新缺陷LRQ-STRICT-001：全池或3个禁用feedback入口清除活动strict，导致仅地址ready位便提前重放。见 [Replay报告](docs/reports/load-queue-replay-20261018.md)；不以DA全满或已通过子块冒充父块验收。
- 已进入独立Store分支，先定义 [EnterSbufferQueue合同](docs/contracts/enter-sbuffer-queue.md)，再做真实两项缓冲的原生UT。输入/输出前缀协议有真实生产者与Sbuffer依据；SQ释放credit必须等待实际Sbuffer消费。RAR/LQU/Replay的局部验收受阻项完整保留，不代表整体无法继续。
- EnterSbufferQueue已完成独立闭环：**26/26 PASS、61/78→78/78行、7/34→34/34语义**；4582条公开记录独立审计，4256次接受=4252次实际消费+4次reset中止，消费中3295次SQ credit与957次无credit正确区分。136份启动快照与结束SHA一致。见 [EnterSbufferQueue报告](docs/reports/enter-sbuffer-queue-20261018.md)，接续UnalignQueue。
- UnalignQueue完成独立闭环：**41/41 PASS、37/44→44/44行、11/40→40/40语义**；5947条公开历史/146份快照哈希审计，1967分配=1726消费+237取消+4 reset中止，所有取消均有同槽新UID完成证明。完整SQ四圈/256编码、36位页号和恢复边界通过。见 [UnalignQueue报告](docs/reports/unalign-queue-20261018.md)，下一模块ForwardModule。
- ForwardModule已建立695实际输入适配、逐拍分阶段参考及独立PA字节来源安全检查，当前初批34例 **31 PASS/3 FAIL、24/62 checked**；250/253→253/253行但尚未验收。普通同word历史别名回归通过，跨16B的年轻VA别名会返回老值且重放/依赖标志全0，三个lane均复现 **FWD-ALIAS-001**。15个必要条件对照及64slot×3lane正向检查通过；剩余38个语义情形与随机等继续实施，见 [ForwardModule阶段报告](docs/reports/forward-module-20261018.md)。
- 历史范围回归02为 **651例 / 28个独立DUT：636 PASS、15 FAIL，NOT_PASS**；15例分为RAR7、合法SID重用7和域受限多MMIO接口边界1。旧门禁/证据保留，详见 [回归02报告](docs/reports/lsq-progress-regression-02-20261018.md)。
- 最新阶段回归03为 **849例 / 31个独立DUT：830 PASS、19 FAIL，NOT_PASS**；新增Replay4例真实失败，已有EnterSbufferQueue/UnalignQueue完整通过。31构建、62功能组、148份冻结文件/运行后源一致性及全部哈希审计通过，见 [回归03报告](docs/reports/lsq-progress-regression-03-20261018.md)。ForwardModule初批功能在独立新目录/本地fixture实施，不在该849例冻结范围内；它们都不代表真实LoadQueue/StoreQueue/LsqWrapper组合通过。
- **整体目标仍未完成**：各层已实施但仍有真实FAIL；LsqWrapper本轮可达DA余量已补例闭合，仍须全域合法混合随机、联合容量/公平排空和最终完整审计。当前全部38DUT已统一重跑，但新增随机范围后仍需对应回归/审计；共同系统reset不冒充只reset本地但外部旧响应迟到的不同合同。不能用FreeList或本体DA满推断LSQ通过。最新数据见页首报告，以下保留历史进展。
- DeqModule现已完成公开生命周期参考/PSQ代理、首轮缺口补例及独立UID审计：`deq-lifecycle-expanded-03` **89例71 PASS/18 FAIL、44/46 checked、本体46/46/闭包124/124**；9746公开记录、3035 UID=2835完成+4 reset中止+196失败停留、全部256 SQ编码及201源SHA核验。WB错误9例与新split尾段wline相邻zero污染9例保留，含4个真实Sbuffer fire，仍NOT_PASS。见[Deq报告](docs/reports/deq-module-20261018.md)；接续[真实PSQ合同](docs/contracts/physical-store-queue.md)，不把Python代理当真实父级。1075例旧回归04不追溯增加Deq范围。
- 真实PSQ已构建并执行首轮覆盖闭环：`psq-expanded-01` **23例18 PASS/5 FAIL、21/43 checked**；本体3733/5396→5387/5396、五文件闭包4113/5817→5772/5817。384个普通/CBO新owner全部实际完成、768个真实forward响应及213源SHA独立审计。两类Deq错误经真实PSQ公开输入复现，实际VSQ/Backend约束仍待验证；22项语义/45条DA和完整父级参考、恢复/UQ/随机继续，见[PSQ报告](docs/reports/physical-store-queue-20261018.md)。
- 之前 FTQ/InstrUncache 的 lint 不属于本 LSQ 工程证据。

## 运行与证据

在本目录运行，已有 DUT 不重复覆盖导出，run 名必须是新目录：

```sh
python3 -B tools/prepare_rtl.py freelist_rar freelist_raw freelist_replay freelist_uncache
python3 -B tools/build_dut.py freelist_rar freelist_raw freelist_replay freelist_uncache --jobs 8
python3 -B tools/run.py --name <新的运行名> --workers 1 -- tests/freelist
python3 -B tools/coverage_audit.py <新的运行名>
python3 -B tools/verify_run.py <新的运行名> --require-semantic-complete --require-line-complete
```

`tools/run.py` 调用 `python -m xreactor run`，默认保存console/JUnit、verification-source
快照/哈希、原生覆盖、功能覆盖、每例小摘要和committed manifest，**不生成逐拍JSON或波形**。
这是历史入口的源保留行为，**不用于本轮及后续摘要执行**。统一回归13改用
`python3 -B tools/run_summary.py --name <新运行名> --workers 4`：只保留源码文件数与
启动/结束聚合指纹，不生成新的全量源码副本、逐文件路径/哈希清单或
`verification-source/`；实际xreactor/native/全部运行时检查、FAIL和覆盖仍保留。
聚合相等不冒充完整新源码快照或逐文件变更审计，复现依赖工作区与选定旧基线源。
需要定位具体失败时才使用`--trace --trace-max-mb 16`，wave另显式`--waves`；上限按每个
journal计，达到后停止写trace但继续所有检查，摘要标明截断，不能冒充完整离线历史。
例如`python3 -B tools/run.py --name debug-one --trace --trace-max-mb 1 -- '<具体nodeid>'`。
不要为了普通回归或保存证据默认对全套开启trace。摘要SHA可用于重跑等价检查，不能
假称未保存的轨迹可离线重放。原生构建与coverage processor使用`/opt/verilator-5.052/bin/`。
共享通用Picker/xreactor/xcomm，不使用其他验证工程的领域模型或fixture。

仅对有`storage-index-v1.json`的选定主基线，需要离线审计时按需临时展开，命令结束后
删除展开副本：`python3 -B tools/lsq_evidence_archive_v1.py audit <run名> -- <原审计命令>`。
有`retired-intermediates-v1.json`的旧中间目录只留报告/源/复现信息，完整旧逐拍原件已
按用户要求删除，不再自动归档；可按冻结源/种子复现，或查看已核验的统一主基线。

在工作区的 `soc-split/rtl/` 中可检查原始 RTL 基线：

```sh
sha256sum -c ../../memblock-hash/lsq/manifest/lsq-rtl.sha256
```

该检查只证明文件内容未偏离清单，不证明功能正确。
