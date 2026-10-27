# 完整LSQ目标的请求→产物→验收检查清单

**这是进度/范围清单，不是整体完成声明。** 最终交付是固定开源配置的分层UT、
真实功能检查、原生行覆盖缺口分类和补例前后证据；不是要求修改目标RTL使其通过，
也不是将独立叶子或一条整体smoke改称LSQ验收。`LsqWrapper`仍是必需整体边界。

**最新补充（2026-10-19）**：统一回归09已实际1882例1691/191，411源一致，v10核验
1795日志/346218记录、1033逐节点、每DUT原DA集合及全部191失败签名，见[09报告](lsq-progress-regression-09-20261019.md)。
新增正常LDU定向18例15/3、自身+3335 DA丢失0，另原8种子新LDU混合2/6；两PASS完成
600/fair及148组取消同槽新UID，见[LDU路由](lsq-ldu-rar-routing-20261019.md)与
[新混合](lsq-ldu-mixed-20261019.md)。旧CBO许可不等于完整LDU准入，旧RAR误作C_NK
及缺revoke流保持接口证据。新增26例不在09冻结范围；完整八种子/STRESS、正常联合
容量/CBO分阶段、其余exact128与最终审计仍必需，下列历史里程碑不追溯改写。

## 1. 用户要求与证据入口

最新[S3/exclusive128报告](lsq-raw-exclusive-20261019.md)进一步限定正常域：旧LDU定向
默认S3字段与混合171次Replay伪更新被拒绝，原15/3或2/6不改，但不提升完整生产者。
新RAW/Replay/Wrapper端点75 PASS、452源一致；六Wrapper1110原UID和新增1440 Replay
owner完成，2732/6900/14419条各DUT自身DA增量旧命中0丢失。该75例不属于尚无结束
结果的回归10之1908范围；八类型写回修复、联合容量/CBO及最终审计仍未完成。

| 明确要求 | 现有产物/检查 | 尚需满足的最终门禁 |
|---|---|---|
| 仅开源、固定真实层次和变体 | `manifest/baseline.json`、`manifest/lsq-rtl.sha256`、`docs/ut-plan.md`真实层次；`prepare_rtl.py`逐文件SHA核验原样提取 | 最终再次核验全部53份SHA及开源树状态；不使用私有工程，不宣称重新elaborate逐文件对应 |
| 自底向上，保留真实下级 | 38个已实施独立DUT；LoadQueue45文件、StoreQueue7文件、LsqWrapper53文件闭包；`build-provenance.json`和build report | 整体独立UT仍有大量未验收范围；不得把Python组合参考当硬件父块 |
| 每块用例前定义人可读行为 | `docs/contracts/`逐层合同；LsqWrapper82情形及新增SQ端点、正常CBO/串行混合合同，先于对应新用例 | 整体模型、代理和用例须遵守实际旧状态/生命周期及NoSpec/BlockBack合同 |
| Picker + X Reactor实际运行 | `tools/build_dut.py`实例化走钟、`tools/run.py`managed runner、被动连续采样、实际native coverage | 不能只以export/build退出码、静态codec或模拟器smoke计功能通过 |
| 功能点对应实际检查 | reached/checked双目录；独立UID actor、阶段参考、字节/身份安全检查和公开历史审计 | 未checked项保留失败或缺证据状态；不得仅发送输入或填行计checked |
| 首轮逐条未覆盖行分析 | 每轮`line-audit.json`、逐行`line-audit-classified*.json`、源/行号/原文/功能映射 | LsqWrapper本体和全部真实闭包同样审查；区分已有功能缺情形与整体功能遗漏 |
| 补例后真实重跑提升 | 各模块独立initial/expanded目录；LoadQueue28841→44962→50393→50513/50520；Wrapper24174→24386→25684→28035→29054→48947→53480→55502→57395→58471→59595/59602，297例完整重跑/逐行分类/独立审计 | 原1124可达余量已补例动态命中，剩7条本层窄证明不计命中/不删分母；完整混合随机等语义缺口不能由行闭合抵消 |
| 真实失败不掩盖 | 普通pytest FAIL、固定输入/输出/源码快照、问题反例和必要条件对照 | 不改RTL、不skip/xfail、不读`known-issues.json`作答案，不以高覆盖抵消缺陷 |
| 恢复/reset与安全复用 | LQ1375旧UID同槽新UID完成；Wrapper43例的901取消/reset同槽完成，新44例另2144取消均同LQ新UID完成；1784取消Replay slot仅由相应新UID重授予/反馈完成 | 共同reset显式中止20笔外部job，不冒充返回/消费；只reset本地但旧响应迟到的不同合同未验证；完整随机组合范围不豁免 |
| 可复现、可审计 | 每轮专属目录、`source-evidence.json`、`end-source-check.json`、artifact/build/auditor SHA | 原件保持不变；工具/参考错误以新版本纠正，并保留旧失败/错误报告 |
| 不扩大或缩小边界 | 目标LsqWrapper；LsqEnqCtrl/ExceptionInfoGen为相邻专项 | 不冒充MemBlock/Backend整体验收；删除端口、常量和未定义payload单列观察边界 |

## 2. 层次覆盖产物索引

以下每行均指本工程内的真实硬件UT；“已实施”不等于DUT严格通过。

| 必需块/实际变体 | 用例前合同 | 结果、覆盖迭代和问题报告 |
|---|---|---|
| 四FreeList | `contracts/freelist.md` | [FreeList](freelist-20261018.md)，四变体分别运行 |
| 两PAddr与Mask CAM | `contracts/cam.md` | [CAM](cam-20261018.md)，真实延迟/编码分别检查 |
| AgeDetector_36 | `contracts/age.md` | [Age](age-20261018.md)，真实Replay三个实例仍由父块保留 |
| VirtualLoadQueue | `contracts/virtual-load-queue.md` | [VLQ](vlq-20261018.md) |
| LoadQueueRAR | `contracts/load-queue-rar.md` | [RAR](rar-20261018.md)，release严格失败保留 |
| LoadQueueRAW | `contracts/load-queue-raw.md` | [RAW](raw-20261018.md) |
| UncacheEntry全部16 ID | `contracts/uncache-entry.md` | [Entry](uncache-entry-20261018.md)，不能只测ID0 |
| LoadQueueUncache | `contracts/load-queue-uncache.md` | [LQU](load-queue-uncache-20261018.md)，合法SID与接口MMIO失败分开 |
| LoadQueueReplay | `contracts/load-queue-replay.md` | [Replay](load-queue-replay-20261018.md)，strict失败保留 |
| EnterSbufferQueue | `contracts/enter-sbuffer-queue.md` | [ESB](enter-sbuffer-queue-20261018.md) |
| UnalignQueue | `contracts/unalign-queue.md` | [UQ](unalign-queue-20261018.md) |
| ForwardModule | `contracts/forward-module.md` | [Forward](forward-module-20261018.md)，PA字节安全与历史别名回归 |
| VirtualStoreQueue | `contracts/virtual-store-queue.md` | [VSQ](virtual-store-queue-20261018.md)，同拍接口域失败单列 |
| DeqModule | `contracts/deq-module.md` | [Deq](deq-module-20261018.md)，完整身份完成前缀、0..128合法占用 |
| PhysicalStoreQueue | `contracts/physical-store-queue.md` | [PSQ](physical-store-queue-20261018.md)，真实四个下级 |
| StoreQueue | `contracts/store-queue.md` | [SQ](store-queue-20261018.md)，真实VSQ/PSQ许可反馈 |
| LoadQueue | `contracts/load-queue.md` | [LQ](load-queue-20261018.md)，五个真实队列反馈、60/63 checked、三项失败 |
| **LsqWrapper** | `contracts/lsq-wrapper.md`，82项整体语义及本批情形先于用例 | [最新整体报告](lsq-wrapper-20261019.md)：53文件真实整体317例269 PASS/48 FAIL；82 reached/76 checked、闭包59595/59602；原44例闭环、8混合失败前缀/3实际s2 SID反例保留。新6联合例5456UID/18公平段/992同槽完成，不能抵消原全域失败。严格逐拍参考与16个明确protocol-only probe分列，整体仍未验收 |

`contracts/`路径相对`docs/`，上述报告相对本文件目录。通用Delay/arbiter/流水
实例在真实父块闭包中覆盖，不擅自扩成通用IP验证项目。

## 3. 冻结运行和审计命令合同

1. `python3 -B tools/run.py --name <fresh-name> --workers 4 -- <tests> --tb=short`
   必须使用新目录；测试跑完立即
   `python3 -B tools/capture_end_sources.py <fresh-name>`，捕获结束源前不改启动文件。
2. `python3 -B tools/coverage_audit.py <fresh-name>`保留本体及闭包DA原始分母。
3. LoadQueue当前使用`audit_lq_history_v4.py`、`audit_lq_static_gaps.py`和
   `audit_lq_gaps_v2.py`：分别检查公开UID/总线/字节/失败、精确7条窄证明及逐行
   分类；旧v1/v2/v3与旧报告不覆盖。v4峰值采用每case和max，不能再累计为池峰值。
4. 独立审计需对照实际pytest节点和失败输出；不能先信manifest绿色或测试目录名。
   历史阶段回归06为36独立DUT/1312例，**不含LoadQueue或LsqWrapper**。
   最新回归07已在新目录扩大到全部当前38DUT/1808例，1649 PASS/159 FAIL，包含
   LoadQueue199/Wrapper297；用新版v8门禁，不改写1312例旧范围/结果，见第14项。
5. Wrapper69例使用`audit_lsq_bus_v3.py`：旧49例全部实际输入/pre/post/tick逐bit
   复核、新20例UID/总线路由/SID合法复用和4+6严格失败独立重建；v2保存49例混合
   及128flow完整证明。`audit_lsq_bus_producer_v1.py`只提供公开源码准入窄核对，
   boot空拍条件误报的旧工具/拒绝记录保留，不能当完整Backend或Uncache联合仿真。
   `coverage_audit.py`与`audit_lsq_gaps.py`记录53文件全部DA和逐项映射，不拼叶子。
6. 历史132例用`audit_lsq_memory_v1.py`：原69例全量原始采样逐bit门禁、新63例PA
   字节/完整SQ/共享STA RAW恢复/RAR release/907UID独立核验；4取消均有同LQ槽新
   UID完成。`audit_lsq_control_v1.py`保留并解释旧3个过严helper断言，证明原采样
   是新对照前缀，随后Replay/SQ empty/S3和全部UID真实完成；其他25失败节点不变。
    新容量/reset/CBO/随机范围不能复用旧审计或放宽范围门禁。
7. 新172例使用`audit_lsq_population_v1.py`，原132全部原始采样逐bit门禁，新40例
   真实Replay120池/strict/special/960多flow和特殊Store实际WB/Sbuffer fire/释放
   另独立重建，16492记录/323源核验。16个protocol-only probe明确不计全输出
   逐拍参考；`audit_lsq_helper_v2.py`保留19日志及2头移动计时helper错误，未改RTL
   或2048阈值，其他17 Replay原始历史不变、含strict3 FAIL。
8. 历史178例使用`audit_lsq_nuke_population_v1.py`，旧172全部原始采样逐bit不变，
   新6例RAW56/RAR96由三个真实查询入口填池，容量拒绝仅经实际STA/VLQ自然回收
   解除，744原UID全部完成，17605记录/327源及全部artifact/build SHA核验。
   `audit_lsq_baseline_v1.py`再次核验原53份RTL/真实闭包及开源固定HEAD、干净树。
   `audit_lsq_delta_v1.py lsq-expanded-09`逐条绑定24426个新DA命中与前轮语义缺口，
   原DA集合59602保持，两轮均无旧命中丢失，不把失败语义换算成覆盖PASS。
   这些门禁不接受未来NC/完整恢复/reset/随机新范围，必须新增审计版本。
9. 历史194例使用`audit_lsq_wrap_history_v1.py`，旧178全部原始input/pre/post/tick
   逐bit不变，新1024 Store/8 Load及15 Replay例独立重建；22029记录、332源、
   新1924 UID=1796完成+128全池strict失败保留、728grant/slot反馈得到核验。
   全128虚拟uop×8来源、256 SQ编码与ROB flag/former四组合均有真实完成见证；
   7个普通ROB头preCommit fire不当作已退休证明。两个头优先helper过严的旧采样
   为纠正例前缀，先消费旧候选后优先选头并完整完成，其他13 Replay历史不变。
   DA增量v2逐条绑定新增2022与前轮语义缺口；原59602集合保持且旧命中丢失0。
   仍不接受未来NC/完整恢复/reset/随机新范围，不放宽旧178/172/132审计门禁。
10. 历史210例用`audit_lsq_uncache_history_v2.py`：旧194原始采样逐bit不变，26422
    连续记录、336启动结束源及全部artifact/build SHA核验；新446UID=443完成+3
    取消，全部3取消有同LQ物理槽新UID完整bus/bypass/VLQ完成。306原请求/ack/
    响应/grant/数据消费，144个mid×NC/内存MMIO/IO×bypass lane见证；真实NC RAR
    经实际C0重读及独立branch部分恢复完成，不冒充RAR自动产生redirect。两MA+
    TLB全120池另有真实原slot反馈完成。原NC消费代理固定等LQ2的3失败保留，改
    公平消费有效候选；v1审计又把合法下一候选误猜为8，原器/拒绝SHA保留，v2
    复用同一事务核心，仅证明前84采样相同、tick170真实消费持有集合中的LQ3。
    DA增量v3逐条绑定新增1893，原59602集合不变、旧命中丢失0；37FAIL不变。
    全16entry取消/reset、完整shared恢复/已发已缓冲响应清理及全域随机仍需新
    版本覆盖，不能复用此局部通过或扩大旧门禁。
11. 历史253例用`audit_lsq_recovery_history_v2.py lsq-expanded-13`：独立34920记录，
    旧210全部原始采样逐bit不变，346源和全部artifact/build SHA一致。新43例
    1897UID=996完成+848取消+53reset中止，全部901个同物理槽新UID实际完成；
    704 Load请求/2实际Store写接受=686真实响应+20共同reset中止，取消不免外部
    回包。879grant/876原slot反馈，差3是reset中止的已grant者；99个原Store
    片段、30双分支恢复、16mid逐一resp下一拍取消、3次完整LQU容量rollback。
    共同reset不撤销已经接受的Store外部写、不伪造旧job响应，local-only reset
    后旧响应迟到未验证。11个代理/参考首失败完整原始采样为新例逐bit前缀；
    12轮虽绿色但3个前导刺激ROB1..3已在pending9后，独立核心明确拒绝。新13轮
    仅纠正前导pending0，全部active原事务保持、另外250例与12轮原始历史相同，
    v2保留同一严格核心且仍拒绝旧三个绿色历史，不拿参考变更冒称RTL修复。
12. `audit_lsq_delta_v4.py lsq-expanded-13`逐条核验1076新增DA与旧语义缺口，
    原59602集合/旧命中保留；`audit_lsq_static_gaps_v1.py`在实际Wrapper53文件及
    正常producer连接上重做六默认值/一互斥写窄证明，7条不计命中、不删分母。
    `audit_lsq_reference_impact_v1.py lsq-reference-impact-01`另外审计受参考修改
    影响5DUT/448例383PASS/65FAIL、63887原始记录与各自旧基线SHA多重集合不变；
    所有448节点结果也不变。无nodeid的旧叶子日志不伪称逐节点轨迹关联，不把
     此影响范围回归冒充扩大后的38DUT最终统一回归或整体完成。
13. 最新297例用`audit_lsq_remaining_history_v1.py lsq-expanded-14`：旧253全部实际
    input/pre/post/tick逐bit不变；新44严格例独立24043记录、7264UID=5120完成+
    2144取消，全58963记录/350启动结束源及全部artifact/build SHA一致。512个
    槽×CBO×STA组合真实Cache/zero/WB/SQ完成、4923grant/3139原slot反馈（差1784
    为取消且独占同slot重发完成）、279原总线请求/ack/响应与172消费+107取消丢弃
    分列。`audit_lsq_delta_v5.py`逐条绑定新增1124到旧语义缺口，原59602集合不变、
    旧命中丢失0；剩7条本层窄证明再次核验、不计命中。负对照v1拒绝三类内存副本
    身份/副作用污染，并核对entry0精确S3 tick34→取消tick40且外部job0；旧记录不改。
14. `audit_progress_run_v8.py lsq-progress-regression-07`核验当时全部38DUT/1808节点
    结果与冻结旧36DUT1312＋LoadQueue199＋Wrapper297精确并集相等，159失败原主
    断言也保持。1721持久原始日志/270210记录的完整SHA多重集合相同，其中959份
    有nodeid另逐节点匹配；基础87例没有持久逐拍JSON，不虚构对应轨迹证据。
    每个DUT自己的逐行DA集合/命中集合相同，不跨DUT合并。76功能组、350启动结束
    源及全部artifact/build SHA一致；当前完整范围统一回归已经实际完成。
    首版v7因误读叶子不存在的冗余closure字段KeyError退出，原器/失败原因保留；
    v8复用其严格历史核心、按实际LCOV逐源/逐行检查，没有改变测试/输入/RTL。
     未来随机范围扩大后仍须新目录/新版门禁，不能以本批代替未实施的三个STRESS。
15. 311例`lsq-expanded-15`：263PASS/48FAIL，361源。mixed-history-v3核验61152
    原始记录，旧297/37FAIL逐bit保持。8个原全域固定种子只执行到首FAIL，另3个
    干净s1后的真实s2 SID字节反例和3个完整完成对照。前两轮非法ready/scalar16、
    04 fullVA标签和原审计器lease错误均保留，05纠正fullVA只改变该输入/对应
    异常VA输出，其余实际引脚不变；不把失败前缀或行覆盖当完整随机完成。
16. 当前317例`lsq-expanded-16`为269PASS/48FAIL、364源，新增6个严格联合定向。
    `audit_lsq_joint_history_v3.py`核验11766新记录、22代实际同场满池、18个真实
    公平段，5456UID=4464完成+496取消+496reset中止、全部992同物理槽新UID完成。
    388原接受=356真实响应+32共同reset中止；6030grant/slot反馈、2214片段/90WB/
    54Cache req/resp实际完成。`audit_lsq_joint_impact_v1.py`联同原LQ199重跑核验
    **516例456PASS/60FAIL、101738记录**，旧510实际历史/60失败原签名不变、
    新6例与04冻结相同；参考AST只改reset新采集full_mask，流水/knownness/掩码
    未放宽。两DUT原DA集合/命中不变，剩7条本层窄证明重做。负对照v2四个内存
    变异均被拒绝，包括删取消原响应；原证据不改。详见[联合报告](lsq-joint-capacity-20261019.md)。
    仅干净/地址不重叠联合正条件，三个STRESS仍未checked，不能替换8个原随机FAIL。

## 4. 当前不能关闭目标的原因

### 最新必须同时满足的门禁与限制

- 回归08已经实际完成38DUT/1828例1658 PASS/170 FAIL，371源、1741日志/284165记录、
  979逐节点映射、每DUT原DA/命中和全部原失败签名保持；见[回归08](lsq-progress-regression-08-20261019.md)。
  不再称新增20例尚未统一，但后续54例须新1882范围重跑，不追溯改旧范围。
- 正常包34例26/8中，18无CBO端点2313 UID真正完成；12个旧绿色提前ROB退休历史
  仍拒绝。CBO包正确后又发现NoSpec/BlockBack遗漏，相关旧CBO流只能保留接口域。
  2613逐行缺口→+405 raw命中/剩2208不等于正常全功能通过，见[复核](lsq-normal-domain-20261019.md)。
- 新真正串行CBO12例7/5、8原串行随机种子8 FAIL，所有实际CBO owner源许可零
  违例，512 CBO+512年轻Load完成；3实际错误WB fire、1无自身零写的zero WB/SQ
  release、1 strict phase错误保留。7677混合记录仍166取消/50失败停留，不能用
  214完成或600+5000实际服务当公平通过，见[串行报告](lsq-serialized-cbo-20261019.md)。
- 合法联合容量与CBO串行分阶段、随机fair未完成UID及同槽恢复、其余exact128域、
  参考影响统一回归与最终请求→证据/边界审计尚未完成。以下保留原317历史边界。

- LsqWrapper已实际317例269 PASS/48 FAIL、82 reached/76 checked；旧1124条可达
  DA已由三MA级联/第二地址wake、RAW高组正冲突、各槽CBO实际完成、变长回收对齐
  等新44例动态命中，剩LQU6/VLQ1有本层窄证明且保留原分母、不算命中。
  **当前行缺口闭合、6个补充联合正例不等于完整合法固定种子混合域验收**；
  新例已实际同场满池/公平服务，但8个原随机仍首FAIL、三个STRESS仍未checked。
  历史38DUT回归07已完成，新增20例范围须另完整重跑/审计，不追溯混入旧1808。
  Store实际WB/zero/wline/完成顺序及disabled strict已在真实Wrapper复现，连同
  原bus/SID、Forward三类和前拍RAR release均保持普通FAIL；新全池strict失败也
  保留128原UID，不用其非strict对照或DA/bin抵消未验收。
- 各层release、strict、SID、Forward、Store完成顺序/字节/错误保持等真实FAIL
  仍需在整体层保留复现和作用边界，不得删除或转成PASS。
- LoadQueue199例完整回归及其覆盖/独立历史审计已完成，仍187 PASS/12 FAIL；
  整体最终证据审核和未验证边界汇总尚未完成。没有外部原因阻止继续有意义验证。

因此目标保持active；本清单不是complete/unmet依据，也不将本轮工作量替代完整目标。
