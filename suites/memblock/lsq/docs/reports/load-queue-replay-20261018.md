# LoadQueueReplay：独立重放生命周期与覆盖迭代

## 结论与范围

**尚未验收（NOT_PASS）。** 已发现严格store地址依赖提前重放问题 `LRQ-STRICT-001`，保留普通失败，不修改目标RTL、不用xfail或收窄invalid payload域。整体LSQ目标也未完成。

真实DUT为120项、3×40 bank的 `LoadQueueReplay`，保留 `FreeList_2` 与3个 `AgeDetector_36` 实例，文件去重3份。开源基线 `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e`；53份原始RTL本轮重新校验SHA全部一致，开源工作树无修改。原样导出及原生实例化走钟见 `results/builds/20261018T063105344803Z-load_queue_replay/report.json`。

当前配置删除的store wakeup cancel、TLB延迟CSR、full_fwd、输出cause、debugTopDown及多数vector字段不声称动态覆盖；合同以实际400个输入（不含clock）及公开输出为准。原因0～11为合法普通单hot重放原因；12的源码assert(false)不伪造成正常流程。

## 用例前功能点与参考

合同：[load-queue-replay.md](../contracts/load-queue-replay.md)，先于原生功能用例定义18类可读微架构行为。首轮82个情形；strict失败后补充全容量/无效反馈两种情况到84，旧运行的冻结82分母不改写。

- 所有权以首次分配UID、slot、第一次入队年龄和反馈代次记账；输出握手只表示已调度，**不释放slot**。只有真实反馈 `need_rep=false` 或redirect可释放；reset中止单列。
- 独立参考使用标量年龄、依赖身份/到达时间和选择快照，不读取DUT的allocated、scheduled、age matrix或strict寄存器作为正确答案。
- 三个bank逐拍比较完整有效payload；FF选择高优先不等于输出entrance编码高优先；scalar mask、vector mask/size、源异常清除、ROB former/latter及非2幂指针分别核对。
- 提示区分fast TLB即时选择、慢TLB历史、普通与S4历史窗口、延迟refill、L2 keyword/lastBeat；wrong ID、过期和flag不匹配均有负例。
- 检查正常反馈/同槽更新、背压、连续与中断冷却、redirect/reset、全池与4回收通道、2048周期specialMode以及13个公开perf事件的两级时序。
- 功能覆盖分开reached/checked；普通checked等真实输出握手、有效payload比较及正常反馈释放；取消checked等后续新UID真实完成，reset不冒充成功。

实现：`lsqverify/replay/{types,codec,ports,driver,model,coverage,env}.py`、`tests/replay/` 和 `tests/conftest.py`。xreactor单消费者监视器消费全部DriveStable/RisingEdge观察，包括fixture切换空拍。

## 实际运行和逐行补例

以下路径均相对工程根 `memblock-hash/lsq/`，每次运行独立目录，不覆盖历史失败、源码快照或审计器。

| 运行 | 用例结果 | 本体原始DA行 | 真实3文件闭包DA行 | 语义checked |
|---|---:|---:|---:|---:|
| `replay-initial-01` | 4 PASS | 9560/25806，37.05% | 13409/30500 | 15/82 |
| `replay-directed-01` | 42 PASS（7个全池例未选） | 10503/25806，40.70% | 见原始line-audit | 44/82 |
| `replay-expanded-01` | 52 PASS / 1 FAIL | 24665/25806，95.58% | 28742/30500 | 52/82 |
| `replay-expanded-02` | 125 PASS / 4 FAIL | 25692/25806，99.56% | 30386/30500 | 82/84 |
| **`replay-expanded-03`** | **127 PASS / 4 FAIL** | **25806/25806，100%** | **30500/30500，100%** | **82/84** |

逐行清单见各运行 `line-audit*.json`，分类都是已有功能的缺失情形，没有把可达行排除：

1. 首轮16246条本体缺口：头窗口240、各slot原因/NC/beat保存1309、strict更新1200、MSHR/TLB标签1193、原uop/vector/vaddr及脉冲历史12299、special5；另真实FreeList缺845条回收路径。补全部slot/入口、各依赖、元信息、全池回收和长驻留。
2. expanded-01剩1141条本体：头窗口196、strict并发360、TLB依赖571、脉冲9、special5，另FreeList617条。补120项MA/TM三入口同槽反馈轮换、4回收通道在4种FIFO尾对齐下的复用和长驻留。
3. expanded-02剩114条全部是bank-local索引3～39的程序头窗口优先编码。补120项不可缓存load按原LQ依赖逐组唤醒，上一组实际反馈完成才推进ldWbPtr，下一组才解锁；含119起点的跨120回绕。两例 `replay-head-gap-01` 及完整 `replay-expanded-03` 均确认这些缺口全部命中；原始分母不变，但两项strict语义继续失败。

单独长驻留/合法随机专项 `replay-long-directed-01` 为7 PASS；历史窗口/redirect/reset专项 `replay-timing-directed-02` 为42 PASS；第二轮补缺口专项 `replay-gap-directed-01` 为9 PASS。专项选择运行不替代完整回归。

## 开放缺陷 LRQ-STRICT-001

### 可观察反例

- 全池：120个C_MA都带 `loadWaitStrict=true`，阻塞SQ7；`addressReadyPtr=0`、`sqEmpty=false`、无地址wakeup，仅置地址ready位，slot0便提前输出 `valid=1`，严格参考期望0。
- 最小边界：单个strict owner等待SQ7，地址ready位已置1但无实际pointer/wakeup解除。三个入口分别驱动 `valid=false, isLoadReplay=true, schedIndex=0` 的禁用反馈payload，随后均提前输出slot0。
- 公开输出仍保留该uop的 `loadWaitStrict=1`。定位不依赖读取内部strict寄存器。

四个普通失败完整nodeid在 `manifest/known-issues.json` 及JUnit。`replay-timing-directed-01` 为15 PASS/3 FAIL；expanded-02完整重现4例失败。无效payload指向别slot、非feedback编码、地址位未就绪、普通non-strict等必要条件对照通过，不能通过禁止合法invalid payload规避。

### 源码依据

`XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala:825-828` 不论valid都计算反馈slot或预分配slot；861～865的 `otherwise { strict(enqIndex) := false.B }` 未受真实入队valid保护。原SV33683～35965保留该更新结构。全池时不可用预分配输出与活动slot0别名；无效反馈也可显式指向活动slot。这里只定位当前配置缺陷，不声称任意配置的形式化证明。

## 独立证据审计

`tools/audit_replay_trace.py replay-expanded-03` 已通过证据一致性检查，结论仍 **NOT_PASS**。expanded-02的审计和审计器另保留不改写；最终 `trace-audit.json` 与冻结 `evidence-auditors/` 保留：

- 131个完整用例，无skip/xfail/缩小选择；127 PASS/4 FAIL；84 reached/82 checked，恰缺两项严格依赖语义。
- 127份冻结验证文件、原生包/产物/build文件哈希已核验；`source-consistency.json`确认这127份启动文件结束时仍全部SHA一致，新建Store合同未用于本次运行。
- 20954条连续观察；20140条非reset完整比较、810条reset、4条真实失败。
- 所有权守恒：**4748分配 = 4081反馈完成 + 540取消 + 4 reset中止 + 123失败结束保留**；127个成功例均排空。
- 独立重算FIFO预分配/4通道延迟回收、UID及反馈代次、完整payload、13个perf历史、冷却及2048周期模式历史；不导入领域模型或用内部寄存器作oracle。
- 全部360个“首次输入lane×120 slot×固定输出bank”组合各有真实输出并反馈完成的UID、tick、journal/SHA正向见证，不用4个失败输出凑覆盖。
- 一般依赖/仲裁仍由运行时独立参考比较，审计器检查其完整pre/post记录；不宣称审计器是第二套独立仲裁模型、第二次RTL执行或形式化证明。

## 后续范围

最后114条选择情形的完整冻结重跑和审计已经完成；Replay仍因缺陷保持未验收。继续独立Store子模块，不把本轮局部问题视为整体无法推进。RAR、LoadQueueUncache原有问题不被Replay结果消除；真实LoadQueue、StoreQueue和LsqWrapper组合均仍需后续验证。
