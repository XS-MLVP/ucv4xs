# 真实 LsqWrapper：全池、特殊副作用与覆盖补例进展

**后续纠正/最新范围**：本篇317例是历史接口里程碑，不再将其中旧CBO/混合/联合快照
追溯视为完整正常程序。S3源关系与NoSpec/BlockBack审计拒绝保留，见
[S3纠正26例17/9](lsq-ldu-s3-20261019.md)和[合法容量转移/CBO及串行27例21/6](lsq-ldu-joint-phases-20261019.md)。
新自身53079/59602不借下文59595分子，所有旧FAIL原样保留。完整回归10已实际
1908例1708/200，见[10报告](lsq-progress-regression-10-20261019.md)；整体未验收。

**状态：进行中，NOT_PASS，整体目标仍为 active。** 最新完整目录为 **317 例：
269 PASS / 48 FAIL**，82 reached / 76 checked；真实 53 文件闭包 DA 为
**59595/59602（99.9883%）**，本体 114/114。76 个 checked bin 只表示有成功
情形，不能抵消同一功能的必需失败情形，也不能替代所有恢复边界/合法混合随机。

本报告接续 [132 例及此前历史](lsq-wrapper-20261018.md)。仍固定开源
`893e1580b705d81f113c30c7a05734e09a08050e`，原样 RTL、真实 LoadQueue/StoreQueue
及全部下级。603 输入 / 458 输出；没有外部 SQ readiness、VLQ head、RAW/RAR full
或 Uncache wake 可供测试伪造。未修改目标 RTL/Chisel、未使用私有工程。

## 1. 功能点先行与实际新增范围

[整体合同](../contracts/lsq-wrapper.md)原有 82 项可读微架构行为保持不变；本批
在写用例前补充了特殊 Store、真实 SQ strict、2048 拍窗口和全池回收的情形合同。

### Store 特殊副作用：20 例

- 4 种 CBO 经真实 VSQ 头许可、PSQ、Cache/Sbuffer、实际 WB 和 SQ 释放；年轻缓存
  Load 同时完成自己的 S3/VLQ，不能用单分支 smoke 代替组合。
- denied / corrupt / 二者同时存在，分别比较立即 WB 与三拍背压后的 **WB.fire**。
  原 ROB/former、VA、高位 VA 和 hyper 保持同一事务。
- zero 的 WB/SQ 释放必须有 **自己 PA 的真实零写片段**；有/无旧普通 Sbuffer 项
  对照。旧普通 Store 已退休但未消费，不人为加 `read==head` 限制。
- NC/IO（memory 1/2/7）完成不得越过未消费老 Store。确认、实际 WB、Sbuffer 消费、
  SQ 释放和仍欠外部 resp 分开记账；先消费老项的必要条件对照不替代背压失败域。
- 普通 split 尾段的 wline 必须属于原 owner，不能继承相邻 CBO.zero；非 zero
  邻项作为对照。原 PA、mask 和有效字节均检查。

其中 4 个干净 CBO 例使用原严格 `lsq` fixture；另 **16 例明确使用 `lsq_probe`**。
后者保存连续全引脚，但每条日志显式 `checked=false`、
`full_cycle_reference_compared=false`，只提供原 UID 协议/副作用检查，**不冒称
逐拍全输出参考通过**。其用途是把事务推进到实际错误 WB/Sbuffer fire 或错误 SQ
释放，再使原语义断言普通 FAIL；没有吞掉严格 fixture 的失配或标 skip/xfail。

### Replay、LQ 容量及真实依赖：20 例

- 地址依赖 / TLB / MSHR 三种原因 × 三个 S3 入口，各填真实 120 项并完成。
  地址依赖 SQ7 来自实际分配的 8 个老 Store，必须经真实 STA/STD 及就绪反馈解除；
  不沿用独立 LoadQueue UT 可外驱的 SQ 指针。
- 原程序头最后入 Replay 池，检查真实 VLQ head/head-near 优先于早入池年轻项，
  随后全部原 slot 反馈/VLQ 完成。
- 8 个 dispatch 来源各填 120 个多 flow 元素，合计 **960 Load**，检查全 LQ
  物理槽及两种 flag、后续实际完成，不只计写入行。
- 两个实际 Store 构成 SQ0 地址缺口和 SQ1 ready 位。严格 Load 不得因位图或
  valid=0 的反馈清除依赖；3 个有效唤醒对照完成，3 个禁用输入情形严格失败。
- 资格正/负对照、ROB/former 头变化检查 2048 拍特殊模式；先建立真实 ROB 头，
  原 Load 实际反馈完成后才能移动下一头。

### RAW/RAR 全池与真实头回收：6 例

- 三个查询入口各接受 **96 个真实缓存 RAR 记录**。年轻 Load 已 S3 完成但旧 LQ0
  未完成，真实 VLQ 头保持不动；目标 Load 的实际查询被拒绝，进入 C_RAR Replay。
  只有旧 Load 完成使 VLQ 连续头推进，才回收池并允许原 slot 反馈。
- 三个查询入口各接受 **56 个 RAW 记录**，完整 SQ8 指向真实 8 个未就绪老 Store。
  Load 自身完成不释放 RAW；不冲突的同一 STA 同时进入 PSQ/RAW，真实地址指针
  推进至 8 后回收并唤醒 C_RAW。
- 本批没有给缓存 Load 伪贴 NC，也没有外驱 head/full。它证明满池、真实回收和
  原 UID 完成，**不宣称所有 RAW 选择组的正 rollback、全部 RAR PA 元信息或 NC
  生命周期已经穷尽**。

## 2. 冻结运行与覆盖提升

| 运行 | 实际结果 | reached / checked | 真实闭包 DA |
|---|---:|---:|---:|
| `lsq-expanded-06` | 107 PASS / 25 FAIL（132 例） | 53 / 51 | 29054/59602 |
| `lsq-expanded-07` | 107 PASS / 45 FAIL（152 例，含 19 日志错误） | 不作为功能验收 | 原件保留 |
| `lsq-special-02` | 12 PASS / 8 FAIL（新增特殊 Store 20 例） | 局部范围 | 不拼入整体 |
| `lsq-replay-initial-01` | 11 PASS | 局部范围 | 不拼入整体 |
| `lsq-replay-expanded-02` | 15 PASS / 5 FAIL（含 2 计时 helper 错误） | 局部范围 | 原件保留 |
| `lsq-expanded-08` | **136 PASS / 36 FAIL（172 例）** | **66 / 63** | **48947/59602** |
| `lsq-nuke-population-01` | 6 PASS | 局部范围 | 不拼入整体 |
| `lsq-expanded-09` | **142 PASS / 36 FAIL（178 例）** | **68 / 64** | **53480/59602** |
| `lsq-expanded-10` | **157 PASS / 37 FAIL（194 例）** | **69 / 65** | **55502/59602** |
| `lsq-expanded-11` | **173 PASS / 37 FAIL（210 例）** | **72 / 68** | **57395/59602** |
| `lsq-expanded-12` | 216 PASS / 37 FAIL（253 例，另3个绿色前导刺激不合法） | 不作整批合法验收 | 58471/59602，原件保留 |
| `lsq-expanded-13` | **216 PASS / 37 FAIL（253 例，已纠正前导域）** | **80 / 76** | **58471/59602** |
| `lsq-expanded-14` | **260 PASS / 37 FAIL（297 例）** | **80 / 76** | **59595/59602** |
| `lsq-expanded-15` | **263 PASS / 48 FAIL（311 例）** | **81 / 76** | **59595/59602** |
| `lsq-expanded-16` | **269 PASS / 48 FAIL（317 例）** | **82 / 76** | **59595/59602** |

08 比 06 新增 **19893 条 DA**；09 再新增 **4533 条 DA**，本批累计增加 **24426 条**。
这些均来自各自真实 Wrapper 完整运行，不是合并独立叶子/分支覆盖。
09 的 `coverage-delta-audit-v1.json` 还逐条核验 24426 个新命中行与前轮人可读
语义缺口的对应：06→08 为 Replay15292、VLQ4267、FreeList_2 326、PSQ8；
08→09 为 RAR1615、RAW2350、两池272及三个CAM296。两次原DA集合均为59602，
此前命中行丢失数均为0；没有把行命中当成失败语义已经通过。
08 的 323、09 的 327 份启动验证源与结束 SHA 全部一致；所有 native/build/artifact
SHA、committed manifest、coverage_complete、cleanup_complete 均经独立审计。
09 的 `baseline-audit-v1.json` 再次核验原始 53 份 RTL 与真实闭包逐文件匹配，
开源树 HEAD 精确匹配且 `git status --porcelain` 为空。

### 保留的测试设施纠正，不冒充 RTL 修复

`lsq-expanded-07` 新 actor 将 `tick` 重复传给 `emit`，19 例停在日志 TypeError。
修正只改变日志包装，`helper-correction-audit-v2.json` 核验这 19 份旧原始采样
逐 bit 为新例前缀；旧 152 例/源快照不覆盖。20 个新例中另一个本来就已观察到
完成前缀错误，不归为日志错误。

`lsq-replay-expanded-02` 两个 helper 将 ROB 头移动与首次 eligible S3 触发放在同拍。
开源 `LoadQueueReplay.scala:1050-1063` 明确头移动优先清计数；原 DUT 和参考一直
一致，错误是 directed 阈值断言。纠正为先建立头再触发，**2048 阈值、原 UID 完成、
合法头移动要求不变**；独立审计记录正例恰好 2048 拍首次 high。其他 17 个 Replay
结果和原始历史不变，含 3 个 strict FAIL。

## 3. 新版独立历史审计

`results/lsq-expanded-08/population-history-audit-v1.json`：

- 独立核验 **16492 条连续全引脚记录**，旧 132 例所有输入、pre/post、tick 逐 bit
  匹配已审计 06；不导入 DUT 参考/actor，不读取 change/outcome 作正确答案。
- 新 Replay 范围 **2205 UID = 2196 完成 + 9 失败保留**；1206 次实际 Replay grant
  与 1206 次原 slot 反馈，**360 个 slot×S3 入口组合**、960 个多 flow Load 完成。
- 新特殊 Store 49 个原 UID，20 个原 Load 全部完成；实际 SQ 释放 27 个并不等于
  合法完成，独立核验的安全 Store 连续前缀只有 17 个。错误 WB、缺零写、错误
  wline 和错误 release 单列，不以队列 empty 宣称这些 owner 完成。
- 明确区分 156 个严格逐拍参考用例与 16 个协议探针用例；后者不能继承前者声明。

`results/lsq-expanded-09/nuke-population-history-audit-v1.json`：

- 独立核验 **17605 条连续记录**，旧 172 例所有原始采样逐 bit 不变，36 个 FAIL
  节点保持；新增 6 例严格 fixture 通过，**744 原 UID 全部完成**。
- 288 个 RAR 实际接受、168 个 RAW 实际接受；六次真实容量拒绝、相应 C_RAR/C_RAW
  阻塞、真实头/STA 回收、原 slot 反馈得到重新核验。
- RAR 首次公开历史回收 tick336、首次 Replay tick346；RAW 分别 tick244/246，
  各三个入口一致。池数按公开身份账本重建，不冒称观察了私有 physical slot。
- 新范围使用新门禁，未放宽只接受 132/172 例的旧审计器。

## 4. 截至09的 36 个普通 FAIL（10再增加1个全池strict失败，见第7节）

| 问题 | FAIL 数 | 本层实际证据 |
|---|---:|---|
| LSQ-BUS-OWNERSHIP-001 | 4 | 旧 NC Load 响应提前暴露仍欠自身响应的串行 Store 之后的新请求；未宣称第三笔实际 fire |
| LQU-SID-001 | 6 | 合法 SID 复用后，旧 Load 实际 s1 异常 19/5 被新响应污染 |
| FWD-ALIAS-001 | 3 | 无阻塞标志时返回旧 Store 而非最年轻原 PA 字节 |
| FWD-RANGE-001 | 6 | forwardMask 包含没有原 PA producer 的字节 |
| FWD-SQID-001 | 3 | SQ112 的真实依赖报告成 SQ176 |
| RAR-REL-001 | 3 | 前拍同 line release 漏报 |
| LRQ-STRICT-001 | 3 | 实际 SQ 指针仍为 0，禁用反馈后 Replay 在 tick50 提前有效 |
| DEQ-WB-001 | 3 | tick56 实际 WB.fire 的异常 7/19 为 0/0，而原 Cache 错误非零 |
| DEQ-ZERO-001 | 1 | 只在 tick66 消费旧普通写，tick70 zero WB、tick72 SQ 已到 2，自己零写 0 次 |
| DEQ-SPLIT-WLINE-001 | 1 | tick50 普通 split 尾段真实 fire 的 wline=1，严格应 0 |
| DEQ-FINISH-ORDER-001 | 3 | 老 Store 原片段消费 0 次，tick66/70 SQ 头已从 0 到 1，随后到 2 |

Store 四类错误已经在真实 Wrapper 边界复现，不再仅有叶子/PSQ/SQ 证据；仍不
扩大为完整 Backend 发行/仲裁可达性、ISA 后果或 fresh Chisel elaboration 证明。

## 5. 09的6122条 DA 余量（10已降至4100，见第7节）

全部原始行保留在 09 的 `line-audit.json`，逐行功能映射在
`line-audit-classified.json`；均属于已有 82 功能的缺失情形，目前没有整条新增
功能定义，也**没有**把这些行排除、宣布不可达或改分母。

| 余量 | 行数 | 需要补充的人可读行为 |
|---|---:|---|
| VSQ | 1673 | 128 个虚拟 uop（不是 8 个 16-flow uop）、8 dispatch 来源/完整 flags、已退休前缀恢复 walk |
| Replay | 815 | 其余 head-near 候选、全槽 strict/混合原因保存、真实 StoreDataWakeup 历史与依赖更新 |
| LoadQueueUncache | 745 | 全 16 entry、排序/容量/多路 bypass、真实 NC/MMIO、取消/复用和异常 |
| UncacheEntry 全家族 | 880 | 其余 ID 的真实请求/ack/响应/取消/唤醒/消费，不借独立 entry 通过 |
| 四 FreeList | 1426 | 真实父块变长回收、单/多通道积压、取消和同槽再分配完成 |
| PSQ | 386 | 各物理槽/STA 入口的 CBO 属性保存，必须由原 owner 的实际特殊完成观察 |
| RAW | 192 | 两个真实 STA 的高选择组恢复元信息正冲突，不把满池无冲突对照算作正选择验证 |
| UQ / VLQ | 4 / 1 | 共享恢复第二页/尾部取消；VLQ 普通 producer 同拍互斥须本层重新窄证明，分母保留 |

此外仍必需：真实 NC RAR 生命周期、完整两分支多圈/flags、shared redirect/reset、
已发/已缓冲总线取消且偿还响应义务、全部取消/reset 同物理槽新 UID 真正完成、
合法全域固定种子混合随机与公平排空、扩大后的全层统一回归及最终请求→证据审计。
不存在阻止继续这些工作的外部障碍；本报告不构成 complete/unmet 依据。

## 6. 复现及审计入口

在 `memblock-hash/lsq/` 使用新运行名，预期 pytest 真实非零退出码：

```sh
python3 -B tools/run.py --name <fresh-name> --workers 4 -- tests/lsq_wrapper --tb=short
python3 -B tools/capture_end_sources.py <fresh-name>
python3 -B tools/coverage_audit.py <fresh-name>
python3 -B tools/audit_lsq_gaps.py <fresh-name>
python3 -B tools/audit_lsq_baseline_v1.py <fresh-name>
```

结束 SHA 捕获前不得修改启动文件。`population-v1` / `helper-v2` 专用于冻结的
172 例范围，可对 `lsq-expanded-08` 重审；`nuke-population-v1` 专用于冻结的178例，
`wrap-history-v1` 专用于194例，`uncache-history-v2` 专用于210例。
历史253例的精确冻结证据可重审：

```sh
python3 -B tools/audit_lsq_recovery_history_v2.py lsq-expanded-13
python3 -B tools/audit_lsq_delta_v4.py lsq-expanded-13
python3 -B tools/audit_lsq_static_gaps_v1.py lsq-expanded-13
python3 -B tools/audit_lsq_reference_impact_v1.py lsq-reference-impact-01
```

当前297例与扩大38DUT统一回归的门禁见第10节；旧门禁范围不扩大。

未来增加/修改用例需新目录及对应审计版本，不能只放宽旧门禁或覆盖这些原件。
冻结的06→08→09逐行增量另可执行
`python3 -B tools/audit_lsq_delta_v1.py lsq-expanded-09` 重审；它刻意只接受这三轮。

## 7. 128个真实虚拟uop、完整多圈和Replay余量补例

09的VSQ1673/Replay815等余量再次驱动合同补充和16个新例，而不是以已有128-flow
向量例替代128个虚拟uop。`lsq-expanded-10`完整194例为 **157 PASS/37 FAIL**，
69 reached/65 checked；332份启动结束源及全部artifact/build SHA一致，开源53份
RTL和干净HEAD再次核验。所有旧178例原始input/pre/post/tick **逐bit不变**。

### 本批可读行为和实际检查

- 八个dispatch来源分别保留128个不同ROB的单flow Store uop，合计 **1024 Store**；
  只在当前64物理窗口发行，原PA/字节真实Sbuffer消费及下一拍连续SQ释放后才重用。
  另8个原缓存Load各自实际S3/VLQ完成。全 **256个SQ编码**、**ROB flag×former四
  组合**以及128逻辑虚拟槽×8来源有完成见证，不将逻辑槽账本冒称私有寄存器观察。
- 普通all-ready Store在ROB头可经真实preCommit执行（`NewStoreQueue.scala:1989-2005`），
  不人为限制必须严格早于ROB头。独立审计最初的严格小于谓词会误报，已依该公开
  合同纠正为头许可或已退休，**7次实际头预提交fire单列、不当作ROB退休证明**；
  未改变测试刺激、RTL或字节/完整身份释放检查。
- 三路同拍各带MA/TLB/MSHR不同单hot原因，三个MA入口轮换；真实SQ STA/STD、
  TLB广播、16个MSHR refill解除各自原依赖，并完成120个原slot反馈。不是多hot
  非法原因，也不是外部伪造SQ反馈。
- SQ0仍地址缺口时只实际写SQ7：非strict全池对照完成，strict全池须继续等匹配
  执行唤醒；该完整域 **普通FAIL**，未用前述对照抵消。
- 两个StoreDataWakeup入口分别命名实际Store，先以错误SQ0对照，再以SQ1 issue
  wake和下一拍真实STD写入偿还原生产者义务，随后原Load反馈/字节写出完成。
- cache-replay和way-retry各三个S3来源保存原身份并完成，未声称验证外部Cache/Way
  内部实现。另把真实VLQ头放入Replay bank1/2，消费旧持有候选后检查下一次选择
  优先取程序头，全部120个原UID随后排空。

### 新全池strict反例及helper纠正

新全池strict例在tick312：120个原Load仍需等待SQ7，真实地址ready指针为0，
只写SQ7且没有有效STA匹配wake；实际Replay0.valid=1、合同应0，输出原uop的
loadWaitStrict仍为1。**尚无实际Replay握手或架构后果声明**，8个Store和120个
Load共128 UID因失败保留。当前LRQ-STRICT-001在Wrapper为3个disabled例+此全池
例，共4 FAIL；加原其余33例合计37，旧36节点全部保留。

`lsq-replay-gaps-01`首15例为12 PASS/3 FAIL，其中两个头优先helper错误要求在
!ready时替换已选输出。原逐拍模型和DUT一直一致；真实合同应持有原候选，在其
fire后才接收下一选择（`LoadQueueReplay.scala:654-700`）。旧失败/331源保留，
`wrap-history-audit-v1.json`证明两份旧原始采样逐bit为纠正例前缀，之后确有原
候选fire和下一原VLQ头选择/完整120 UID完成；其他13个Replay结果/历史不变，
含全池strict普通FAIL。两个纠正控制独立重跑2 PASS，随后才并入完整194例。

### 新独立历史和剩余缺口

`results/lsq-expanded-10/wrap-history-audit-v1.json`独立核验 **22029条连续记录**；
新16例 **1924 UID=1796完成+128失败保留**，728次真实Replay grant及728次原slot
反馈，1024个原Store字节片段、另36个Replay对照原Store片段实际消费。
16个旧protocol-only probe边界及所有旧严格FAIL原样保留，新16例都使用严格fixture。

`coverage-delta-audit-v2.json`逐条绑定09→10的 **2022条新增DA** 与前轮语义缺口：
VSQ1666、Replay89、FreeList_2 263、PSQ4；原59602 DA集合保持，旧命中丢失0。
可用 `python3 -B tools/audit_lsq_delta_v2.py lsq-expanded-10` 重审，旧v1不扩大范围。

剩 **4100条**已再次逐项分类：VSQ7、Replay726、LQU745、entry880、四池1163、
PSQ382、RAW192、UQ4及VLQ1。VSQ余7条属于有已退休前缀的恢复walk；Replay仍有
同时两路MA/另一原因的strict保存、其余回收/依赖情形，不能因本批15例或全池
通过对照宣布穷尽。真实NC/RAR、全entry及共享恢复/reset、已发/已缓冲总线清理、
全部取消/reset同槽新UID完成、全域固定种子混合随机与公平排空及最终全层回归
审计继续保留为必需工作；未删除分母、无skip/xfail或RTL改动。

## 8. 全16个Uncache entry、真实NC RAR/重读和共享部分恢复

按上述4100条缺口先补充合同，再增加15个Uncache/NC RAR例及1个“两MA strict+
另一TLB原因”全120池例。`lsq-expanded-11`完整210例 **173 PASS/37 FAIL**，
72 reached/68 checked。336份启动/结束源SHA、全部artifact/build SHA及53份原样
RTL/开源固定干净HEAD再次核验；原37个FAIL未删除、未xfail，也未修改目标RTL。

### 新范围不是简化的单侧smoke或伪NC标签

1. **NC / 内存型MMIO / IO × 三个bypass来源，共9例**：各两代16个新Load UID，
   三路S3逆序输入后由真实队列排序，全部mid0..15均经历实际共享req/方向ack/
   resp、内部wake、Replay grant、真实bypass s1/s2数据/错误、原slot S3及VLQ完成。
   原普通Store同时保留到其原PA/字节实际Sbuffer消费/随后SQ释放。新输入保持
   fullVA与VA一致、VA/PA/GP页内偏移一致，检查原ROB/former、GP、hyper/nonleaf。
   NC有16个不同mid数据同时未消费的公开峰值；MMIO按真实ROB头串行消费，不能
   把其公开在途mid峰值1冒称私有entry并行峰值16。九例都实际消费两代mid0..15。
2. NC允许年轻Load在老Store头前发行；MMIO头只越过已正常完成的老uop，第二代
   最后一笔有错误后不再越过该ROB头。LSQ数据/异常与VLQ完成不冒充Backend trap/
   退休。两代重填在旧数据全部消费后进行，但**不将它当作SID必须等消费才可归还**；
   原“resp.fire后合法复用SID而旧数据未消费”的6个严格FAIL仍逐bit保留。
3. **真实NC RAR：同line正例/不同line负对照 × 三lane，共6例**：先实际返回老NC
   响应，再接受年轻同block请求，避免伪造外部Uncache同block重叠；两个请求均
   真正回包/Replay/bypass后才查询RAR。年轻NC的真实数据标记released，旧Load
   同line查询nuke，负对照不误报，没有给普通缓存Load伪贴NC。
4. 正例按 `NewLoadUnit.scala:1111-1115` 优先以 **C_UNCACHE原slot反馈并实际重读**，
   不用C_NK或无新数据的普通S3完成掩盖NC重读。另一个独立外部branch redirect
   同拍取消年轻后缀——**不声称RAR自动产生这个redirect**。年轻Load已S3完成但
   尚未VLQ释放，仍须正确取消；两分支真实恢复后，老Load接受新响应/再bypass/
   RAR不再nuke/最终完成。年轻者同LQ1物理槽的新UID也重新完成完整总线/bypass/
   VLQ链，退休但背压的老Store原字节最终仍实际消费。
5. Replay最后追加同时两个MA strict及另一个TLB单hot原因，120个真实Load依赖
   实际Store7 STA/STD/wake与TLB广播，120次实际grant及原slot反馈后完成。

### 消费代理与审计器的错误均保留，不当成RTL修复

`lsq-uncache-population-01`首15例为12 PASS/3 FAIL。三个NC例在完成LQ0/1后，
代理固定等LQ2，而Replay合法保持LQ3/4/8候选，不会因ready一直为0而替换输出。
原逐拍模型/DUT一致，没有RTL失配；旧结果与335源保留。改为公平消费实际有效
候选后，`lsq-uncache-population-02`完整15例全部PASS，随后才并入210例全回归。

独立审计v1在解释纠正时又错误猜测“下一实际消费LQ8”，而公平策略确实选择
最小可见 **LQ3**。这不是测试或RTL失败；v1 SHA
`2e21794d6f474a1a386019cad0a1c448b0f8e753a075b1734d69a782bd858489` 连同启动源码
与拒绝原因保留。新版v2**复用完全相同的独立事务检查核心**，只纠正helper证明：
三例旧/新前84个原始采样逐bit一致，tick170原代理仍全ready0，新代理真实消费
持有集合{3,4,8}中的LQ3，随后全部32个原UID完成；其他12例原始历史完全不变。
没有放宽字节/错误/顺序/完成门禁，也没有覆盖原失败/审计器或将v1称为通过。

### 独立证据、覆盖增量与余量

`results/lsq-expanded-11/uncache-history-audit-v2.json`独立核验 **26422条连续记录**，
旧194例所有input/pre/post/tick逐bit不变；新16例 **446 UID=443完成+3取消**，
全部3取消UID有同LQ物理槽新UID完整总线/bypass/VLQ完成见证。其中：

- 306次真实Load请求fire、306方向绑定ack、306原SID响应、306实际Replay grant、
  306次原数据/错误s2消费；NC RAR正例另3次C0原slot重读反馈均有新请求/新响应。
- **144个mid×NC/内存MMIO/IO×bypass lane组合**，九例各有两代mid0..15实际消费。
- 15个原普通Store片段实际消费；三次两分支恢复和退休Store保存，15个真实NC
  数据RAR查询。额外两MA全池有120次grant/slot反馈及8个原Store片段消费。

`coverage-delta-audit-v3.json`逐条绑定10→11新增 **1893条DA**：LQU724、其余14个
entry各56共784、Replay320、FreeList_2 21、FreeList_3 44。原59602 DA集合不变，
旧命中丢失0；可用 `python3 -B tools/audit_lsq_delta_v3.py lsq-expanded-11` 重审。

剩 **2207条**再次逐项分类：四FreeList1098、Replay406、PSQ382、RAW192、entry96、
LQU21、VSQ7、UQ4及VLQ1。具体后续情形为真实父块变长回收/取消复用、全部entry
未发/已发/唤醒等取消及reset、LQU容量拒绝rollback、PSQ各槽CBO保存及实际完成、
RAW高选择组正冲突、已退休前缀VSQ恢复walk和跨页UQ取消。LQU21中六个guarded
默认值及VLQ1的普通producer互斥须本层重做窄证明，仍保留原分母，不算动态命中。
完整共享redirect/reset/已发已缓冲总线外部响应清理、全部取消/reset同槽新UID
完成、合法全域固定种子混合随机/公平排空、扩大后的全层回归和最终请求→证据
审计仍必需；本轮3个部分恢复不能替代这些完整范围，整体继续active。

## 9. 共享恢复/reset、外部义务和满池拒绝：43个新例

合同先补充取消阶段、总线清理、共同系统reset及退休前缀语义，再实现新例。
`lsq-expanded-13`完整253例 **216 PASS/37 FAIL、80 reached/76 checked**，
346启动/结束源及全部artifact/build SHA一致；原53份RTL与干净开源固定HEAD
再次核验。**原210例全部input/pre/post/tick逐bit不变**，含37FAIL和16个明确的
protocol-only probe。本批43个新例均使用严格逐拍fixture，不新增弱检查探针。

### 真实取消、回包和新UID完成，而不是删除旧账本

- **Uncache23例**：四个16项全池情形检查MMIO未到头、NC弹性包背压、已发待响应、
  回包后未消费数据的取消；另16例逐mid0..15先真实返回该mid原SID，紧接下一拍
  shared redirect，针对真实wake阶段取消，其余15笔外部响应仍全部返回。
  弹性包即使此前没在顶层fire，redirect后仍实际接受/ack/resp清理。取消返回
  的289笔数据明确标为“返回后丢弃、未消费”，不计Load完成；不能把它们从外部
  义务中静默删除。每个旧LQ槽均由新UID完整bus/Replay/bypass/S3/VLQ完成。
- **LQU14/15/16项占用**：三路逆序原S3触发真实容量拒绝，逐字段检查最老被拒者
  ROB/former、FTQ/RVC/offset/checkpoint和flush-self level。该公开rollback成为
  shared redirect，已接受老项保留并完成；被拒1/2/3项后缀同LQ槽新UID再完成。
- **两分支同时取消/全池恢复四例**：同一混合程序保留8个真实Store、120个TLB
  阻塞Load、56 RAW及96 RAR记录，按四种回收对齐取消两侧全部原owner。重填新
  UID后各有实际120个Replay slot grant/原slot反馈、VLQ完成和原Store字节消费；
  不把取消后的empty、私有full/head或仅Load后缀恢复冒称这一组合通过。
- **退休前缀walk**：14个已执行、Sbuffer仍背压的Store，仅前10个按真实ROB退休，
  下一拍redirect取消SQ11以后的后缀。实际双分支恢复返回exclusive SQ11；全部
  幸存老Store原字节及同槽替代UID随后真正完成。**跨页UQ两例**另填满两个真实
  second-page记录后取消后缀/全部，共7次真实UQ请求，幸存/替代跨页Store的两段
  原PA字节都实际消费，不能用新普通对齐Store来证明UQ数据安全。

### reset边界明确，仍检查无reset流水

六例同时中止两分支：刚分配、STA→S2在途、TLB阻塞、Replay已选/已grant，以及
已退休Store的Sbuffer项背压。七例额外覆盖Load弹性包、串行NC/MMIO待响应、
16个NC在途、Store IO/NC待响应和bypass s1→reset拍s2数据/错误。旧LQ/SQ物理槽
均由新Load完整总线/bypass/VLQ和新Store原字节消费/释放证明复用。

本批采用**共同系统reset**：20笔尚未响应外部job显式单列为external-reset-
aborted，**不假造响应或计消费完成**；其中2个已经实际req.fire的Store外部写
接受是既成事实，reset不能撤销，也不把它们算作完整Store完成。未验证“只reset
LSQ但外部旧响应继续迟到”的不同系统合同，不冒称该边界已经覆盖。

Uncache弹性valid/entry控制异步清零，Wrapper busy/perf、bypass和异常历史不是
统一reset寄存。实际旧s1数据在首个reset拍仍以正确128位重复数据、derr/nderr
出现在s2，得到独立核验；不跳过reset采样、不重新打开首次unknown屏蔽。

### 设施和刺激错误保留，审计不能只相信绿色

1. `lsq-uncache-recovery-01`为18PASS/5代理FAIL：错误允许所有取消未发旧UID
   匹配后来的同ROB/PA新代，身份不唯一。仅为redirect前**实际可见**弹性包保留
   原UID迟发资格后，`lsq-uncache-recovery-02`23PASS；原失败/340源保持。
2. `lsq-shared-recovery-01`为9PASS/4参考FAIL：三个因RAW叶子单调输入域错误
   拒绝真实SQ恢复回退，一个因UQ恢复误接晚一拍PSQ寄存而非实际VSQ输出。
   原Chisel1883-1887/1623及原SV16062-16068支持修正；独立RAW默认域不变，只在
   父组合允许附近signed epoch，不复活旧记录、不屏蔽ready。原失败/342源保留。
3. `lsq-pending-reset-01`为4PASS/2参考FAIL：参考未在reset前采样反映已异步
   清除的Load弹性valid/MMIO选择。按真实reset寄存边界修正，新增s1→reset拍s2
   历史例后，`lsq-pending-reset-02`7PASS；原失败/343源保留。
4. 以上11个原失败，独立审计证明**全部原始采样是纠正例逐bit相同的完整前缀**，
   纠正后才继续原UID义务，不拿参考域修正冒称RTL修复。
5. `lsq-expanded-12`虽原生253例216PASS/37FAIL，独立事务审计又抓到三个绿色
   return_alignment前导例把ROB1..3分配在公共pending=9之后，违反合法退休域。
   **明确拒绝计合法PASS**，原run/343源及v1审计核心保留。更正仅把该前导头设
   为ROB0，执行后再正常移到9；全部active dispatch/STA/STD/S3/RAW/RAR事务完全
   保持。`lsq-shared-recovery-03`先13PASS，再运行当前完整13轮；v2重审仍以同一
   严格事务核心拒绝旧三个非法绿色历史，另250例与12轮原始历史逐bit不变。

### 独立审计、参考影响回归和覆盖闭环

`recovery-history-audit-v2.json`独立 **34920条连续记录**，新43例：

- **1897 UID＝996完成＋848取消＋53 reset中止**；全部901个取消/reset UID均有
  同物理槽新UID真实完成，其中844个Load、57个Store，不把旧owner中止当完成。
- 704次原Load请求fire、2次实际Store写请求接受、705次方向绑定ack；686次真实
  原SID响应＋20笔共同reset中止＝706个外部事务闭环。redirect没有reset豁免。
- 396次正常原数据/错误bypass消费，另1次旧s1在reset拍实际s2数据/错误；879次
  Replay grant、876次原slot反馈，差3是reset中止的已grant原Load，不伪造反馈。
- 99个原Store字节片段实际消费、30次双分支恢复响应/settle、7次两侧非空后缀
  同时取消、16个mid的“真实resp→紧接下一拍redirect”、3次完整容量rollback。

参考修改另以 **5个受影响DUT/448例**独立回归：`lsq-reference-impact-01`为
**383 PASS/65 FAIL**，RAW32/0、LQU64/8、PSQ45/21、StoreQueue55/24、LoadQueue187/12。
346源/全部产物SHA一致，`reference-impact-audit-v1.json`重审 **63887条原始记录**
与各自冻结旧基线完全一致。部分旧叶子日志无nodeid，明确采用**各family完整
原始轨迹SHA多重集合**比对，不谎称逐节点关联；全部448个pytest节点及结果也
独立相等，65FAIL未变化。这不是扩大后的全部38DUT最终统一验收回归。

`coverage-delta-audit-v4.json`逐条绑定11→13新增 **1076条DA**与旧语义缺口：
四FreeList956、entry94、LQU15、VSQ7、UQ4。原59602 DA集合不变、旧命中丢失0，
不是跨独立叶子合并。`static-gap-proof-wrapper-v1.json`另在真实53文件层次及
正常生产者连接上重做六个guarded mux默认值矛盾和一个VLQ同拍互斥窄证明；
**7条不计动态命中、不删分母**，不是借独立LoadQueue证明或任意接口不可达声明。

### 剩余1131条DA与必需完整范围

| 剩余原DA | 行数 | 已有功能中还缺的具体情形 |
|---|---:|---|
| Replay | 406 | 三路同时MA写strict的级联优先保存/不同分配对齐，第二路真实StoreAddrWakeup等完整历史；现有两MA+TLB不能冒充三MA级联闭合 |
| PSQ | 382 | 各物理槽、两个STA来源的CBO属性保存及原owner实际CBO完成，不能仅写属性后reset |
| RAW | 192 | 两个真实STA来源的高选择组正冲突和原Load恢复元信息；满池无冲突不算正选择 |
| Replay/Uncache两FreeList | 138/4 | 真实父块不同变长回收、单/多通道优先和返回位置对齐，同槽新UID完成 |
| UncacheEntry0 | 2 | 在entry0已请求但尚未进入弹性包的精确拍取消；现有buffered取消时entry0已进入待响应，不能混算 |
| LQU / VLQ | 6/1 | 已按本层重做guarded默认值/正常producer互斥的窄证明，保留原DA且不计命中 |

1131中只有上述7条已有本层窄证明，**其余1124条仍未证明不可达**。完整合法
全域固定种子混合随机、联合容量与公平排空仍未实施；late-response/local-only
reset等不同合同未验证边界单列，不能用共同reset替代。剩余6个未checked情形
为SID复用、前拍RAR release、禁用strict反馈及三个STRESS情形；前三类普通FAIL
继续保留，而已有成功bin也不抵消37FAIL。最后还须扩大后的全层统一回归、完整
请求→证据及未验证边界审计，目标继续active，无外部障碍阻止下一轮有意义工作。

## 10. 余量驱动的44个严格补例，以及当前38DUT统一回归

本节接续第9节的1131条余量；**不是用99.99%行覆盖宣称LSQ功能通过**。
先在原82项整体合同中明确缺失行为，再补三MA级联、RAW高组正恢复、各槽CBO
真实完成、父池变长回收和entry0精确请求取消。局部运行27例、15例、5例均PASS；
后两轮有3例重叠，**唯一新增为44例，不是47例**。随后完整`lsq-expanded-14`
297例为 **260 PASS/37 FAIL**，350份启动/结束源及全部native/build/artifact SHA
一致。旧253例所有实际input/pre/post/tick逐bit不变，含原37FAIL和16个明确的
protocol-only probe；44个新例全部使用严格逐拍全输出fixture。

### 可读微架构行为→实际原UID检查

| 新例 | 实际行为和不可替代的检查 |
|---|---|
| 三路MA strict，3例 | 每拍三路各携带独立单hot MA且strict=1，120项全池；0/1/2个已真正完成的Replay前导移动真实分配对齐。错误SQ0 wake不能解除SQ7，第二路匹配SQ7 wake和原Store实际STA/STD后才grant，原slot反馈后120个Load完成。不是两MA+TLB，也不抵消原4个strict FAIL。 |
| Replay变长回收，18例 | 原120个slot全部实际grant但未反馈；取消不同长度年轻后缀，保持老slot占用。新UID实际grant的集合恰好等于原取消slot集合，再完成幸存/新owner反馈。1/2/3个真实前导推进返回尾，不直接修改指针。 |
| Uncache变长回收，8例 | 16项全池实际发出；保留1/2/3个老Load，取消年轻后缀后仍偿还全部原响应、消费幸存原数据，再同LQ新UID完整完成。0/1/2/3/9/13笔已消费前导推进真实返回尾，覆盖靠近队列尾的批量归还落点。 |
| entry0精确取消，1例 | 原S3 tick34，tick40 redirect；公开固定流水将entry推进到request，但顶层弹性包尚无valid、原外部job为0。随后16个新UID真正bus/bypass/VLQ完成，原LQ0与mid0都实际复用，不借buffered取消例。 |
| RAW高组正恢复，12例 | 真实56个Load查询记录、56个老Store；高选择组1..6×两个实际STA来源分别产生原Load/Store完整rollback和MDP训练。实际rollback作为shared redirect，取消后缀同LQ新UID经原Store逐PA字节forward/S3/VLQ完成；幸存原Load也解除MA、反馈原slot。 |
| 各槽CBO完成，2长例 | 两个STA来源各执行256个原CBO owner，覆盖64槽×4种CBO×2来源全部512组合、各自完整SQ256编码。384个非zero Cache请求/响应、128个自己的零字节Sbuffer写、512次原ROB/VA/hyper WB.fire及随后SQ释放；另512个年轻原缓存Load各自完成。不是仅保存属性后reset，干净响应也不冒称错误背压/zero/顺序FAIL已修复。 |

### 新版独立历史审计及审计器负对照

`remaining-history-audit-v1.json`独立核验 **58963条连续记录**，其中新范围24043条：

- **7264 UID＝5120完成＋2144取消**；全部2144取消均有同LQ物理槽新UID真正完成
  （普通/Replay2036＋Uncache108）。本批无reset豁免或外部job中止。
- **4923实际Replay grant、3139原slot反馈**；差1784恰好为被取消原slot，全部1784
  slot均只给相应新UID重授予并真正反馈/完成，没有把grant当作VLQ完成。
- 279个原Load总线请求＝279方向ack＝279原SID响应；172次原字节/错误实际消费，
  107个取消原请求真实返回后丢弃，不计Load完成。另一个未发取消entry0没有job。
- 672个原RAW查询实际接受、432个完整原rollback payload、252次替代Load原PA字节
  检查、39次实际shared redirect；主Memory范围696个原Store片段、Uncache伴随
  老Store另9个片段均真实消费。上述CBO Cache/zero/WB完成另单列，不能重复混算。
- 原slot、CBO opcode、zero实际字节的三个**仅内存副本**破坏性负对照均被语义
  审计拒绝。输出的相应expected也同步污染，故不是靠参考预期不一致才拒绝；
  原始证据文件完全未改。`remaining-negative-audit-v1.json`还保存entry0精确
  tick34→40、无顶层请求/外部job的公开时序证据。这三项负对照不保证所有审计器
  正确性，不将有限校验器测试冒称形式证明。

### 同一Wrapper完整运行的1124条DA增量和最后7条

`coverage-delta-audit-v5.json`逐条将13→14新增 **1124条**绑定到旧可读语义缺口：
Replay406、PSQ382、RAW192、Replay FreeList138、Uncache FreeList4、entry0请求
取消2。**原59602 DA集合保持，旧命中丢失0**；不是拼接上述局部运行或独立叶子。
当前剩余仅LQU六guarded默认值和VLQ一普通producer同拍互斥写，本层窄证明再次
按真实53文件/实际连接执行，`remaining_not_proven=0`；**7条仍保留原分母，不计
动态命中，不扩大为任意接口、任意参数或fresh elaboration不可达声明**。

### 已扩大到全部当前DUT的统一回归，不等于补齐未来随机范围

`lsq-progress-regression-07`运行完整`tests`、无`-k`/deselect/skip/xfail：
**1808例/38原生DUT，1649 PASS/159 FAIL、76功能组、350启动/结束源SHA一致**。
`evidence-check-v8.json`核验所有节点/结果与冻结的36DUT1312＋LoadQueue199＋当前
Wrapper297精确相等，所有159失败原主断言也保持（仅Python对象进程地址归一化，
不归一化实际hex payload）；每个DUT的原LCOV DA集合/命中集合分别相等，不跨DUT
拼覆盖。详见[统一回归07报告](lsq-progress-regression-07-20261019.md)。

1721份持久原始日志共 **270210条记录**与各自旧基线的完整SHA多重集合相等，其中
959份日志含nodeid，另核验逐节点轨迹。基础87例（FreeList52/CAM24/Age11）旧fixture
没有持久逐拍JSON，只有运行时连续采样/检查、节点结果、native/functional/source
证据，**不为它们虚构原始历史或逐节点轨迹关联**。

首版v7已通过原始历史/节点/失败签名门禁，但错误假设叶子line-audit也有父块才
保存的`closure_line_hit`，以KeyError退出。原器SHA/失败原因保留；v8复用同一
严格历史核心，改为逐源/逐行核验实际LCOV全DA集合和命中集合，未改任何测试、
刺激、RTL、结果或语义域。这是审计元数据适配修正，不是RTL修复。

可重审当前冻结范围：

```sh
python3 -B tools/audit_lsq_remaining_history_v1.py lsq-expanded-14
python3 -B tools/audit_lsq_remaining_negative_v1.py lsq-expanded-14
python3 -B tools/audit_lsq_delta_v5.py lsq-expanded-14
python3 -B tools/audit_lsq_static_gaps_v1.py lsq-expanded-14
python3 -B tools/audit_progress_run_v8.py lsq-progress-regression-07
```

### 仍未完成的整体义务

本轮关闭的是**当前逐行可达缺口清单**，不是完整功能目标。仍76/82 checked：SID
复用、前拍RAR release、disabled strict有真实FAIL；三个STRESS尚无完整验收。
必须继续实现**一个绝对ROB环的完整合法固定种子混合代理**，覆盖真实两分支、
共享总线/Cache/Sbuffer/Replay义务及联合容量，公平最终排空和全部取消/reset同
槽新UID完成。不能直接放大只支持两个NC Load的BusOwners，或沿用MemoryOwners
的raw ROB排序/最大值退休；也不能以更保守流量/协议probe/已定向全池替代失败域。
随机扩大后的请求→证据和未验证边界审计、对应全层重跑仍必需。目标保持active，
不以37FAIL或困难/未完成调用整体unmet，也不修改目标RTL来迎合参考。

## 11. 单一ROB环的首批混合尝试，以及实际s2 SID数据反例

本批按第10节剩余整体义务开发新`mixed_owners.py`，不是放大旧两Load总线代理。
普通/NC/MMIO/IO Load、普通/NC/IO/CBO Store共用一个绝对ROB顺序，映射完整640
编码；SQ/LQ独立绝对代及UID，正常dispatch/redirect互斥、128虚拟/64物理Store
窗口、旧STA→下一拍S2属性、真实Forward/RAW/RAR、Replay grant/原slot反馈、
共享总线方向/mid/SID、Cache/Sbuffer/WB和实际队列释放分别记账。原普通Store
可在ROB头获真实preCommit，旧响应返回后SID即可复用，不人为等数据消费。
随机包含别名、split、strict、错误响应/背压、两分支恢复，没有按known-issues
筛去失败域；所有新增用例均为严格全输出fixture，未新增protocol-only probe。

### 执行结果与合法域审计，而不是仅相信staged参考

| 新范围 | 结果 | 本轮真实达到的边界 |
|---|---:|---|
| 种子0x7100..0x7107，8例 | **8 FAIL** | 实际前缀；全部在600随机拍结束前被第一失败停止，未运行fair阶段 |
| 两干净NC响应×三bypass来源，SID复用/不同SID，6例 | **3 PASS/3 FAIL** | 对照两原Load真正完成；复用例先通过s1，后在实际s2字节失败 |
| **完整`lsq-expanded-15`311例** | **263 PASS/48 FAIL** | 旧297全部input/pre/post/tick逐bit不变，含原37FAIL/16明确协议探针 |

361份启动/结束源SHA一致，全部native/build/artifact SHA、53份原RTL和干净固定
开源HEAD重新核验。`mixed-history-audit-v3.json`独立核验 **61152条记录**；新
14例2189条，原始事务与各自最后有效局部运行完全相同，不以工具/代理修正冒称
RTL修复。`coverage-semantic-audit-v6.json`验证原53文件DA集合及命中集合均与14
相同，**新增DA=0、旧命中丢失=0**；最后7条本层窄证明再次执行、分母保持。
这批新增功能失败说明“当前可达行闭合”不等于语义全部验收。

### 原UID及未完成义务明确保留

八个随机实际前缀的公开历史独立核验：

- **2988 UID＝248完成＋2133取消＋607失败停留**；取消者尚未全部完成同槽新UID
  复用，不计恢复验收，不把它们静默删除。实际最大单例LQ89、SQ虚拟81、外部
  未回包8，**未达到120/128/16联合满容量**，不把跨case累加当池峰值。
- 219个Load和22个Store真实总线接受，231次方向ack、223次原SID响应，仍欠18笔
  外部响应（241＝223＋18）；另88笔Load已回包但尚未消费，分别保留账本。
- 509次实际Replay grant、420次原slot反馈；差额包含取消和失败在途，不伪造
  反馈或当成最终完成。1106个原RAR查询/1002对Forward+RAW查询、92次shared
  redirect及92次两分支实际恢复settle，93个原Store片段、9次Cache req/resp、
  13次WB.fire均按原UID记账，但不冒称所有owner/全部副作用已完成。

六个SID定向例另12 UID：6个对照原Load真正完成，6个失败原Load保留。因此新14
例合计 **3000＝254完成＋2133取消＋613失败停留**。它们不是完整随机通过，
不能把248个已完成或队列局部empty换成整个种子通过。

### 已观察到的新s2边界，而非推测未到达的数据

旧SID例先在s1错误字段停机。本批让两原响应均error=nderr=0、字节不同，保持
同一正常ROB和fullVA=VA，三个bypass来源都先完成原s1元信息比较，再实际进入s2：

- 老响应 **tick38**：`0x1122334455667788`，SID4归还但数据尚未消费；
- 新原Load **tick60** 合法重用SID4，**tick62** 返回 `0xaabbccddeeff0011`；
- 老Load s1在tick78干净通过，**tick80实际s2却返回新Load字节**（64位重复为
  128位），而非原老响应；lane0/1/2分别普通FAIL。尚无老S3反馈/VLQ完成或ISA
  错误声明。不同SID三个对照全部完成两原UID、原响应/数据/反馈/VLQ排空。

两个混合种子也实际到达s2：28934原mid9/SID11，tick202旧响应后tick210同SID
新响应，tick214旧消费错成新字节；28935原mid15/SID8，tick540旧响应后tick552
新响应，tick556旧消费错成新字节。另28931在s1异常污染停止；28929/28930在
tick1166/706的背压WB有效期间丢失原Cache错误，均有独立原响应身份见证。
其余三个混合首失败为PA来源安全检查、zero相关flush相位及串行req.valid失配；
完整原始历史保留，仍需进一步缩减/核对具体根因，**不将它们草率算作三个新
独立RTL/架构缺陷**，不声明未发生的第三笔请求fire或后续副作用。

### 代理/审计拒绝与纠正均保留

1. `lsq-seeded-mixed-01`产生了Sbuffer逆前缀ready，违背真实Sbuffer.scala380-381
   与NewStoreQueue.scala1407；另有Store旧代和CBO地址歧义。保留356源/8FAIL，
   仅修正常生产者ready前缀及完整身份，不改参考FIFO或RTL。
2. `lsq-seeded-mixed-02`纠正上述问题后，独立v1仍拒绝size4 Load被标为scalar、
   原mask65535与实际Replay mask1不一致。保留16字节宽度，补真实vector/
   aligned_type及写回元信息；旧356源/失败/审计器保持，不删该流量。
3. `lsq-seeded-mixed-03`元信息正确后，v1审计自己误将无当前grant的已取消
   Replay lease留下，导致合法新授予假碰撞。v2按原UID取消释放lease，不以
   grant!=None作为释放条件；活跃slot/feedback检查保持，原v1源码保留。
4. 03曾在run入口提前标fair reached；04把mark移到真正drain入口，**八个原始
   事务历史逐bit不变**。本批没有执行fair，最终reached不包含它，也无STRESS
   checked，不能把mark调用当实际到达。
5. `lsq-mixed-data-04`新SID6例复用旧BusOwners的独立接口fullVA标签，原生虽3/3，
   v3独立Replay元信息门禁仍拒绝其正常producer一致性。05仅在新6例分配前绑定
   同一Load fullVA=VA。`mixed-correction-audit-v4.json`逐字段证明**只有fullVA
   输入及对应异常VA输出改变**，原SID/ROB/PA/data/时序及所有其他引脚不变。
   不改旧297刺激、不放宽原v3语义核心，旧接口元信息刺激也不提升成正常Backend
   数据流证明。05仍以同一核心得到3个真实s2反例和3个完整完成对照。

当前仍 **81 reached/76 checked**：seeded已有实际执行，但三个STRESS均未checked，
fair甚至尚未执行；只把前缀合法性审计通过称为前缀审计，不称完整混合通过。
下一步须继续联合满容量、能够实际进入的公平阶段、混合活动reset、完整ROB
多圈及取消后同槽新UID完成；保留本8个失败域/种子，不以短流或更保守对照替换。
旧38DUT/1808例统一回归07不追溯加入本14例，未来扩大的完整范围须新目录重跑
及最终请求→证据/边界审计，整体继续active。

可重审：

```sh
python3 -B tools/audit_lsq_mixed_history_v3.py lsq-expanded-15
python3 -B tools/audit_lsq_mixed_corrections_v4.py lsq-mixed-data-05
python3 -B tools/audit_lsq_mixed_coverage_v6.py lsq-expanded-15
python3 -B tools/audit_lsq_static_gaps_v1.py lsq-expanded-15
```

## 12. 联合同场满池、真正公平阶段及全容量恢复

新增6例先按原合同定义“64个老Store→120个Load→64个年轻Store”的同一ROB程序。
在同一真实Wrapper实际保留 **SQ虚拟128/64物理窗口、LQ120、RAR96、RAW56、
Replay120、Uncache16和16个尚欠响应的原job**，不是独立池峰值相加。三个查询
入口/两个STA来源分别轮转，真实SQ0缺口钉住RAW、真实VLQ头钉住RAR，容量拒绝
仍来自实际ready。年轻Store含NC/IO/CBO0..3；完整ROB640/SQ256/LQ240原UID分代。

`lsq-expanded-16`完整 **317例269 PASS/48 FAIL**，364份启动/结束源一致，全部
artifact/build/原53RTL及固定干净开源树再次核验。`joint-impact-audit-v1.json`
核验全部**72918条Wrapper记录**：旧311全部input/pre/post/tick逐bit不变、48个
失败主断言不变；6个新例与已冻结04局部运行11766记录相同。原16个明确probe
保持原边界，6个新增均严格全输出fixture。

`joint-history-audit-v3.json`仅从公开原始历史独立重建：

- **22代同场满池快照、18段停止dispatch后的实际公平服务**，每个fair段的原UID
  集合恰等自己的满池代，而不是恢复前同指针的旧UID。
- **5456 UID＝4464完成＋496取消＋496共同reset中止**；全部992取消/reset有同
  SQ/LQ物理槽新UID真正完成。三个正常容量轮/每例744UID完整执行跨所有ROB640
  编码及SQ256/LQ240，不用reset冒充回绕。
- **6030实际Replay grant＝6030原slot反馈**（可多次重放，非6030新Load），各
  完成代120个不同原slot均实际授予/反馈；2214个原Store片段、90次WB、54次
  Cache req/resp真正完成。
- **388总线接受＝352 Load＋36 Store＝356实际返回＋32共同reset中止**；388方向
  ack，288次原Load数据消费，另32次取消后的真实原返回丢弃。普通redirect不
  免除旧响应，reset绝不冒称返回或消费，已接受Store写不可撤销边界不变。

两个共同reset首轮在perf17/24失配。原FreeList占用异步复位后full_mask已000，
无reset perf流水却保留旧事件；父参考此前错误把reset前111再采入。只更正新
采集mask，AST审计确认无其他语义变化，流水/knownness/掩码不动。原错误03与
新04两个reset的实际raw前缀完全相同，四个原PASS全部raw保持。另完整LQ199的
`lq-joint-impact-02`仍**187 PASS/12 FAIL**，28820记录逐bit等于06；合计516例
**456 PASS/60 FAIL**、101738记录门禁通过，原510实际历史/60失败主断言均不变。

原53文件DA全集及命中集合与15完全相同，**59595/59602，新增0/丢失0**；LQ
仍50513/50520。剩7条Wrapper窄证明重做，不删分母、不算动态命中。独立审计
四个内存变异（原slot、CBO opcode、zero字节、删取消原响应）即使污染对应
expected/raw pins仍被原UID语义拒绝，原证据SHA保持。

首两轮helper错误、03参考相位、history-v1原因编号误写、v2遗漏同尾新UID代标签、
negative-v1找错输入名均保留原器/失败及版本解释，见[联合容量完整报告](lsq-joint-capacity-20261019.md)。

**本批是干净、不重叠地址的补充定向，不是完整随机验收**。原8个全域种子
首FAIL及其未完成义务仍保留；82 reached仅因fair现在真实执行，76 checked和
三个STRESS未checked保持。全域混合随机/恢复交错、未来扩大统一回归及最终
请求→证据/未验证边界审计仍必需，不关闭整体目标。

```sh
python3 -B tools/audit_lsq_joint_history_v3.py lsq-expanded-16
python3 -B tools/audit_lsq_joint_negative_v2.py lsq-expanded-16
python3 -B tools/audit_lsq_joint_impact_v1.py
```

## 13. 正常生产者复核、满SQ参考端点与真正串行CBO补证

第11/12节的实际结果和原件均保留，**但其中CBO全正常程序可达的声明须受本节
纠正**：旧CBO为size3/mask255/wline0；即使新QB包修正，真实Decode/Dispatch/ROB
还要求NoSpec/BlockBack，不能在ROB非空时分配CBO或提前发年轻指令。

完整回归08实际38DUT/1828例1658/170、371源，1741日志/284165记录、979逐节点
映射与每DUT原DA/命中/失败签名保持，见[回归08](lsq-progress-regression-08-20261019.md)。
其38DUT完整范围不等于CBO源合法性，旧原件不追溯改写。

新34例实际26/8。18个127/128/SMF无CBO端点4701记录、2313原UID全部完成，保留
旧Forward/Replay参考异常；只窄修anchored128和SMF exclusive guard，不改expected/
选择/knownness/比较掩码或通用半环拒绝。12个ROB过早前进的绿色历史仍逐例拒绝。
该34例自身raw覆盖56989→57394/59602、新增405逐行映射/丢失0；CBO相关命中仍
是接口域，不能借旧317覆盖变成正常域验收，见[复核报告](lsq-normal-domain-20261019.md)。

新真正串行CBO12例**7 PASS/5 FAIL**、404源，原8串行全域种子仍**8 FAIL**、408源。
定向522个CBO owner和混合33个owner的NoSpec/BlockBack违例均0，字段与603实驱
pin一致。512正常CBO+512年轻Load真正完成；独立正常CBO原Cache tick44错误在
tick52真实WB.fire丢失，3例；老Store已ROB退休但仍SB背压时，zero tick84 WB、
tick86 SQ释放却无自己zero16，1例；strict tick80 phase-only另1例，不给该前缀
捏造后续WB。

新混合7677记录/430UID=214完成+166取消+50失败保留，39次shared恢复、69总线
接受/真实响应；6个有效保持WB的Cache错误、1个SID s1错误和1个600+5000 fair
超时仍普通FAIL。类型/权重/种子不删，CBO意图sticky等真实许可，不要求老SB空。
详见[串行完整报告](lsq-serialized-cbo-20261019.md)。新增54例未追溯混入旧317；
当前全新1882例范围待统一重跑/审计，完整合法容量/CBO分阶段、随机公平/恢复和
最终请求→证据/边界仍必需，目标active。

## 14. 1882范围统一回归完成，完整LDU生产者纠正后推进原8种子

第13节“待统一重跑”现由回归09实际完成：**38DUT/1882例1691 PASS/191 FAIL**，
411启动/结束源一致；v10核验1795持久日志/346218记录、1033逐节点映射、全部191
失败主签名和每DUT原DA集合，见[09报告](lsq-progress-regression-09-20261019.md)。
这不提升旧接口流的正常程序域：CBO包/NoSpec/BlockBack门禁不证明整个LDU流水。

原UID-bound source-v3确认旧混合把RAR nuke误作C_NK，并错拍/换lane S3和缺revoke；
28928的UID97/LQ22与UID101/LQ26构成驱动循环等待，不认新RTL死锁。正常LDU定向
18例实际15/3，3335条自身DA增量/丢失0与原UID flushAfter/同槽完成见
[路由纠正](lsq-ldu-rar-routing-20261019.md)；RAR本体3898/3898仍保留三个前拍release FAIL。

新固定LDU阶段/NC-MMIO/head-tail-S4驱动保持原八种子和八类型权重，实际**2 PASS/
6 FAIL**、424源一致。两个PASS完成600随机/fair及148组全部取消同槽新UID完成；
3397原记录、746UID=359完成+374取消+13失败保留，111接受/真实响应。六FAIL分别
三WB错误保持、两flush相位和一非法SQ释放，错误credit未计语义完成。必要生产者
检查不冒称原生LDU/DCache/Backend仿真，详见[新混合报告](lsq-ldu-mixed-20261019.md)。

新增26例不在09冻结范围，须扩大统一回归；两个种子不抵消其余必需FAIL，STRESS
仍未checked。正常联合容量/CBO分阶段、RAW等其余exclusive128合同及最小例、剩余
恢复/fair和最终全请求审计仍必需，不缩小整体目标或以局部成功关闭。
