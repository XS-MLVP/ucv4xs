# 真实LoadQueue首批组合验证与覆盖迭代

状态：**本层UT/覆盖闭环已执行，三项真实失败阻止严格验收，NOT_PASS**。保留真实VLQ/RAR/RAW/Replay/Uncache及其所有
下级；不是在父层连接Python替代模块。用例前合同为
[`contracts/load-queue.md`](../contracts/load-queue.md)，共63项可读行为情形。

## 原样构建和适配

- 开源固定基线`893e1580b`，45文件传递闭包，原始top SHA
  `13b06fefd522bc26b7574dcb4186db51548bcc6e0676b7e543f4fa45c6c03e7a`。
- Picker导出、原生实例化和走钟PASS：
  `results/builds/20261018T131247846766Z-load_queue/report.json`。
- 实际622输入/266输出；`results/static/load-queue-codec-v1.json`记录256组
  全输入变化、编码/独立被动解码逐字段往返，9个非法包和5个伪造内部反馈拒绝。
  静态编码随机不是合法业务流，也不产生DUT功能覆盖credit。
- 内部VLQ head、RAR/RAW full及Uncache wake只从真实业务产生。五块公开历史
  阶段参考在同拍advance前冻结旧反馈；外部UID actor不读模型内部账本决定完成。

## 首轮问题与真实业务结果

`lq-initial-01`17个fixture ERROR全部停在第一拍pre-edge：原SV resetless
response/bypass/redirect/perf尚无历史，不是17个RTL反例。按精确1/2/3/4/5拍
结构建立首次knownness后重跑；旧17 ERROR与268源结束SHA保留，不skip/xfail，
不在后续活动reset重开初始化屏蔽。

| 运行 | 结果 | 本体DA | 45文件闭包DA | checked |
|---|---:|---:|---:|---:|
| `lq-initial-02` | 17 PASS | 57/57 | 20029/50520 | 18/63 |
| `lq-expanded-01` | 29 PASS | 57/57 | 20900/50520 | 23/63 |
| `lq-expanded-03` | 33 PASS | 57/57 | 28841/50520 | 31/63 |
| `lq-expanded-04` | 136 PASS / 12 FAIL | 57/57 | 44962/50520 | 60/63 |
| `lq-expanded-05` | 186 PASS / 12 FAIL | 57/57 | 50393/50520 | 60/63 |
| `lq-expanded-06` | 187 PASS / 12 FAIL | 57/57 | 50513/50520 | 60/63 |

首17例检查8个dispatch入口、稀疏/multi-flow、年轻S3完成不能越旧头、地址无效和
Replay阻止VLQ完成、三bank输出背压及真实S3反馈释放；额外检查内部VLQ head
自动回收RAR，以及真实store冲突产生RAW恢复和MDP训练。

## 逐行缺口与第一次补例

首轮**30491条缺口**全部保留在`lq-initial-02/line-audit-classified.json`：
Replay17418、VLQ4301、RAW2722、RAR1828、LQU914、各FreeList及CAM/entry等。
按源文件、行号、原文和父层语义逐项定位；这些义务已存在于用例前合同，分类为
已有功能缺少本层情形，不把未实施的整条Uncache测试误说成合同缺了该功能。
没有删除DA分母或将泛化规则当不可达证明。

第一次补12例：NC/MMIO × 三bypass lane × 干净/错误回包。业务链为：
共享S3同时进入真实Replay和Uncache → bus接受/mid-sid绑定/真实回包 →
内部wake解除Replay阻塞 → 真实输出握手 → bypass s1原PA/s2原数据与错误 →
共享S3反馈 → VLQ真实消费完成。新29例闭包增加871条DA；剩29620条再次保存逐行
分类，仍无六条guarded default的本层排除或全覆盖声明。

## 独立公开历史审计

`tools/audit_lq_history.py`不导入任何领域参考/DUT内部状态：

- 初轮415连续记录，38实际dispatch flow UID全部完成，12实际Replay握手和12反馈；
  269启动/结束文件及artifact/build SHA一致。
- 29例轮847连续记录，50 UID全部完成，24 Replay握手/反馈、12真实bus请求、
  12实际bypass消费及12次独立原数据/错误比较；271启动/结束文件和全部哈希一致。
- 独立审计按实际dispatch重建完整LQ身份；消费必须是至少两边沿前已完成的年龄
  前缀。Replay握手不是完成，只有同owner的真实slot反馈才释放。总线SID义务与
  bypass消费分离，未用模型的“completed”作答案。

## 后续补例（保留未完成项）

已实现并检查满120项四代/逆序S3完成、真实RAR满→Replay阻塞→VLQ回收唤醒、真实RAW满
→Replay阻塞→SQ前进回收唤醒，并以64个新UID遍历16 Uncache entry及两种类型。
`lq-expanded-02`为32 PASS/1 FAIL；唯一失败是复用测试helper误将“当前UID未完成”
写成“全历史从未完成过任何UID”，第二个事务已有旧UID完成时触发，不是RTL失败。
旧运行和273份结束源保留；修正为当前UID判断后的完整33例轮另存，不覆盖历史。

`lq-expanded-03`完整33例全部PASS，274份启动结束源码及所有artifact/build SHA
一致。`history-audit-v2.json`独立重建3112条连续记录、834个dispatch flow UID
**全部实际完成**，覆盖全部120个物理LQ槽、8个dispatch入口、3个Replay bank；
90次真实Replay握手/反馈、76个总线请求、76次bypass消费及原数据/错误比较。
16 entry×NC/MMIO的32种真实ID/类型对都已通过完整业务链，不只写入即计覆盖。

v1审计器曾将64事务长流的中途checked事件与最终done集合比较，因后续又有新UID
完成而拒绝，属于审计器时间口径错误，不是DUT/UT失败。v2保留v1，独立按实际
S3及VLQ消费重建每个tick的done集合，并核对135个检查点**当时**的真实完成集合。
不是放宽为“最后有完成即可”。两个旧轮的v1审计原件仍保留。

首轮30491条未覆盖→本轮21679条，闭包新增8812条DA；全部剩余行继续逐项保留
分类，详见`lq-expanded-03/line-audit-classified.json`。当前仍主要缺Replay
14592、VLQ1966、RAW1931、RAR1283及FreeList/恢复/异常等，不能以本体行满结束。

以上33例轮当时尚缺32项功能；不能以其行满或33 PASS验收。后续补例和失败见下，
旧结果、审计器和快照保持不变。LsqWrapper仍在完整目标内，尚未进行本层UT。

## 完整目录补例与真实父层反例

`lq-expanded-04`完整执行148例，**136 PASS / 12 FAIL，60/63 checked**。
新增补例实际检查：

- 全部0..11原因，120个真实Replay owner同时占用及三S3入口/两代复用，
  原UID调度握手后同slot再重放更新，完整scalar/vector元信息。
- SQ地址/数据指针、位图、STA/STD唤醒及实际数据写入；strict匹配/不匹配和
  disabled反馈；快/慢TLB全标签、refill历史窗口及两channel L2 first/last beat。
- 真实VLQ head和头后候选优先，三bank及跨120边界；specialMode精确2047/2048
  边沿、eligible负对照及ROB下一head的former/slot改变。
- 真实RAR全96槽、RAW全56槽/两拍revoke/PA、mask、ROB、TLB-miss负对照及双store
  恢复和MDP训练身份。RAR全槽探针让未完成头查询不同PA，明确是**UNIT-INTERFACE
  CAM压力**，不是一条固定软件load访问多个PA的架构路径。
- 真实Uncache满16后第17项拒绝rollback、共享redirect与槽位复用；已发总线取消
  后返回旧响应；部分/全取消、并行S3完成、活动/阻塞/选中/已发/总线等待reset，
  均要求同物理LQ槽新UID真实完成。活动reset的参考异步相位及resetless perf纠正
  详见合同，原`lq-recovery-initial-01`和`lq-pressure-recovery-01`失败快照保留。
- 两个完整原因域固定种子`88`、`20261018`各180 UID，随机总线、Replay/bypass、
  共享S3和query交错，最后公平排空所有UID、bus、未反馈slot及未消费数据。没有
  延长SID生存期规避缺陷；这两个种子未碰到定向SID反例，不代表该语义通过。

| 未checked语义 | 父层真实FAIL | 必要条件对照 |
|---|---:|---|
| `LQ-RAR.previous_release` | 3，`RAR-REL-001` | 同拍release三lane通过；前拍完整line应命中而实际nuke=0 |
| `LQ-STORE.disabled` | 3，`LRQ-STRICT-001` | 有效匹配STA才解strict的正常路径通过；无效S3反馈后却提前replay |
| `LQ-UNCACHE.sid_reuse` | 6，`LQU-SID-001` | 三lane×两种旧fault极性的不同SID对照6例通过；SID归还复用后旧异常被新回包覆盖 |

这些是12个失败case，不是12个独立新缺陷；不能xfail或用问题清单更改参考。

## 新版公开历史审计与后续行覆盖闭环

`lq-expanded-04/history-audit-v3.json`不读取DUT内部寄存器或领域参考答案，独立核验：

- 16603条连续pre/post、3069 UID = **3017实际完成 + 26取消 + 5 reset中止 +
  21失败停留**；全部31个取消/reset UID都有同物理槽新UID实际完成证明。
- 1292次真实Replay握手、1279次真实反馈；360个slot×输入lane成功见证，全部
  0..11原因、120物理LQ槽、16 entry×NC/MMIO的32种请求。
- 141次实际bus请求、133次bypass消费、127次已到期s2原数据/错误比较；6个SID失败
  停在消费当拍异常比较，尚未发生s2，不能把133写成133次s2通过。
- 独立重建792次RAR查询、171次RAW恢复身份和170次MDP训练；逐个失败都有公开
  时序/身份反例。282份启动结束源、artifact和build SHA一致。

注意：v3报告的`peak_simultaneous_*`全局字段错误地累加了各case峰值（432/251），
**不是单次真实池占用峰值，也不可当容量证明**。UID/输出和失败证明未用该统计。
旧报告不覆盖；新增审计版本须按max汇总并列出每case峰值。

本轮闭包增加16121条DA，剩余5558条全部逐行保留并映射到已有功能的缺失情形。
基于这些行补充`test_line_gaps.py`的13例已实际全部PASS：八dispatch入口各满120
并完成；每个S3入口各120个地址/TLB/MSHR依赖；末年龄槽头优先；两store全组恢复；
三lane Uncache排序和并行bypass。`lq-line-gaps-01`的284份启动结束源一致，独立
审计2936条记录、2232 UID全部完成、1216次握手/反馈、112次RAW恢复与16次数据/错误
比较。该13例定向运行不替代完整148例或最终LSQ。

## 全池批量恢复、全entry取消与最后127条缺口

`lq-expanded-05`为198例，**186 PASS / 12 FAIL**，失败集合仍是上述3+3+6，
没有skip/xfail；60/63 checked不变。新增补例在真实父块内完成：

- RAR96/RAW56/Replay120满池的四种回收尾对齐、两代批量取消，取消后的整个120
  物理LQ区间重填为新UID并真实完成；不把独立FreeList结果转计为父块覆盖。
- 三lane同时地址等待、三种池起始偏移和strict正反，填满120 Replay owner；
  匹配真实STA后原slot/UID完成。另一STD唤醒入口也实际检查。
- 全16 entry在等待MMIO头、NC请求背压及每个实际mid回包后wakeup阶段共享取消；
  等原总线义务安全返回，再重填全16 entry、实际bus→Replay→bypass→S3→VLQ完成。
- 全16 entry×NC/MMIO×三bypass lane的**96种组合**均有真实s2原数据与错误比较。

`lq-pool-recovery-01`的23 PASS/1 FAIL原件保留。唯一helper失败错误地要求
顶层ready=0的请求在redirect后立即消失；真实entry此前已向弹性流水发送，而
该流水没有redirect。修正为保持请求原mid/PA直到实际接受，返回唯一响应，检查
不再产生Replay义务后再重填。该更正没有变更逐拍参考或RTL，详见合同第6节。

v4审计纠正v3全局峰值加总错误，并完整复核旧148例和新198例。新轮独立结果：

- **28787连续记录，8867 UID = 7471完成 + 1370取消 + 5 reset + 21失败保留**。
  所有1375个取消/reset UID均有同物理槽新UID实际完成见证。
- 3767 Replay握手/3754反馈，941实际bus请求，673次bypass消费，667次已到期
  s2原数据/错误比较；245个已取消外部响应安全返回。4个已缓冲请求在redirect
  后才被顶层bus接受，均独立核验原身份及唯一回包。
- 单case真实RAR/RAW记录峰值为96/56（max，不是跨case求和）；360个Replay
  slot×入口、全部0..11原因、96种entry×类型×lane成功见证。
- 1566次独立RAR查询、283次RAW恢复身份、226次MDP训练及5325595个原始身份
  引脚绑定；285份启动结束文件和全部artifact/build SHA一致。

本轮闭包**50393/50520**，比148例轮新增5431条；原始127条DA全部保留：

| 源/缺口 | 分类与处理 |
|---|---|
| Replay120条strict保存赋值 | 已有功能缺混合原因情形：lane1/2地址等待而lane0非地址原因。新增定向例`lq-mixed-priority-gap-01`已PASS，33记录/6 UID实际完成；需纳入最终完整目录重跑。 |
| LQU6条mux默认值 | 本层真实闭包重新验证相同NC/MMIO向量的guard与选择结构，默认写要求`(N∨M)∧¬N∧¬M`，任意输入下矛盾。保持raw分母，不计动态命中。 |
| VLQ14881 | 完整开源上游路径中dispatch valid经`!redirect`门控后寄存，同源redirect在MemBlock延迟一拍，LSQ侧互斥；lastEnqCancel归零后不变。只证明正常producer下排除，不声称任意直接接口不可达。 |

`static-gap-proof.json`保留源SHA、精确结构/真值表和CtrlBlock→Backend→XSCore→
MemBlock→LSQ全链源码片段；`line-audit-classified-v2.json`逐行区分120个缺情形、
6个结构默认值和1个producer排除。不能以覆盖缺口收敛或新96组合抵消三项严格失败。

## 199例完整回归的最终本层审计

`lq-expanded-06`完整199例为**187 PASS / 12 FAIL，63 reached / 60 checked**。
最后混合原因例新增120条DA命中，原始真实闭包为**50513/50520（99.9861%）**。
剩7条正是上述6个guarded defaults与1个正常producer排除，全部有本层精确
`static-gap-proof.json`及`line-audit-classified-v2.json`，没有删除raw分母、改写
RTL或计成动态命中；这也不代表分支/表达式或任意参数形式穷尽。

v4重新逐case独立重建**28820条连续记录，8873 UID = 7477完成 + 1370取消 +
5 reset + 21失败停留**。全部1375取消/reset旧UID均有同物理槽新UID实际完成；
3773 Replay握手/3760反馈、941总线请求、673 bypass消费/667已到期s2原数据错误
比较、245取消响应安全返回、4个redirect后才接受的已缓冲请求均有原身份审计。
保留96个entry×类型×lane、360个Replay slot×入口及全部原因见证；RAR/RAW单case
峰值96/56、1566次RAR查询、283次RAW恢复和226次MDP训练复核通过。
288份启动结束验证源和全部artifact/build SHA一致；53份原始RTL再次全部一致，
开源XiangShan树干净。

12个普通失败仍为RAR前拍release3、disabled strict3、合法SID复用6，三个语义
未checked，**不验收LoadQueue**。当前没有阻止真实上级验证的外部障碍，整体目标
保持active并推进LsqWrapper；为避免阶段门禁要求虚假完成，将原pending整体三个
任务合并到当前未完成实施阶段，全部原任务/验收项和最终审计范围保留。
