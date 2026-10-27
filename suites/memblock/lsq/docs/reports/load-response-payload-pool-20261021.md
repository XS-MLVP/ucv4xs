# Load响应池：真实三层响应数据、错误与S3闭环

结论：**本补例完成真实运行和八build专项审计；完整LSQ仍ACTIVE_NOT_ACCEPTED。**
不修改固定开源893e1580b目标RTL/Chisel，不以串行正例替代SID、混合流量、跨页
或其他原失败。38-DUT统一regression15的2330节点/227 FAIL及原缺口库存不回填。

## 请求到证据

| 请求 | 具体证据 |
|---|---|
| 先定义可读微架构功能点 | `docs/contracts/load-response-payload-pool.md`，先于新增用例建立，明确原UID数据、独立error/nderr、首次Uncache不可完成、Replay/bypass及最终S3/异常恢复。 |
| 实际层次逐层UT | `tests/{load_uncache,load_queue,lsq_wrapper}/test_response_payload_pool.py`；真实LQU→LQ→Wrapper，下级保持原连接。 |
| 独立刺激与实际功能检查 | `lsqverify/load_response_payload.py`只按公开bus/Replay/指针推进外部台账；固定参考、逐周期全检查不改。 |
| 真实完成而非刷数 | 每层128原Load，16真实mid×NC/MMIO×4轮；ack/response/wake/bypass比较后消费。父级额外128原slot授权/反馈、源正确S3和实际LQ释放。 |
| 三类覆盖率前后集合 | 三份`load-response-payload-evidence-v1.json`及八build `load-response-payload-contributor-evidence-v1.json`。原始dat/LCOV、source/build、全部点键集合与旧命中保持。 |
| 失败不屏蔽 | 八build基线1454节点1262 PASS/192 FAIL；after1457节点1265 PASS/192 FAIL，全部旧节点/失败全文全等。 |
| 中断恢复 | `results/load-response-contributor-regression-01/interruption-audit-v1.json`；缺gw2/gw7完成回执且无最终JUnit，不补写完成、不合并dat。基线不重跑，只另建after-02。 |

## 1. 生命周期及适用域

每层四轮响应为0/all1/0/all1；error/nderr分别00/10/01/11，两种NC/MMIO都执行，
每轮实际mid覆盖0..15。低canonical VA、对齐PA、GPA0、无源输入异常，不用
无效高地址或源异常激活本来会被过滤的Uncache请求。

父级实际驱动/检查：

1. 首次S0/S1/S2/S3，C_UNCACHE且updateAddrValid=0，不能提前释放VLQ。
2. 原请求实际bus fire、mid→sid ack、64位response，唤醒原Replay项。
3. 取得公开replayQueueIdx，bypass s1原PA/异常元数据、s2原64位复制为128位
   以及derr/nderr逐位比较。NC replay走RAR/RAW，MMIO replay不走该查询。
4. 最终S3携带原slot、原size/PA lastBeat、bit19(error)/bit5(nderr)，uop和
   Load异常字段相等；实际LQ连续前缀释放后才计本地完成。
5. 32个clean UID正常完成；96个fault UID仅声明LSQ本地写回/释放，随后外部
   ROB头异常flushSelf并等待真实恢复。**fault写回不是架构提交，不声称验证了
   Backend trap实现**。无reset捷径，无读取DUT/model私有状态决定刺激。

Compact witness逐UID保留mid/sid/数据/错误/lane、父级实际s1/s2字段、实际首次和
最终S3字段及LQ释放。它不是逐拍trace，也不证明所有上游资源历史。

## 2. 同选择的正式定向比较

| native DUT | PASS节点 | toggle hit/total前→后 | branch前→后 | raw line前→后 |
|---|---:|---:|---:|---:|
| LoadQueueUncache | 12→13 | 34615→42910 /63328 | 1817→1824 /1932 | 139→139 /223 |
| LoadQueue | 15→16 | 78129→96988 /204148 | 8026→9062 /16440 | 236→440 /3426 |
| LsqWrapper | 19→20 | 92861→135886 /322010 | 7358→10262 /18670 | 168→478 /3654 |

以上是各层**定向子集**，不是完整回归分子。三类分母与源/build一致，旧命中不丢。
LCOV原始源码闭包行另列在JSON，不能把raw line点当作源码行。

## 3. 八build完整贡献范围fresh前后运行

基线`load-response-contributor-baseline-01`；after实际为
`load-response-contributor-regression-02`，不要误用中断的01。

完整范围为原六build1182节点，加完整LQU/LQ既有272节点（252 PASS/20 FAIL），
然后增加三新节点。八build的既有贡献者由primary journal与manifest input_files
双重核对，Wrapper原744→745项；没有遗漏主目录外local_reset、normal_mixed或
sq_endpoint贡献节点。

| DUT | 完整toggle前→后 /total | 新toggle | 新branch | 新raw line |
|---|---:|---:|---:|---:|
| LoadQueueUncache | 49353→51159 /63328 | 1806 | 0 | 0 |
| LoadQueue | 139898→143270 /204148 | 3372 | 44 | 0 |
| LsqWrapper | 278078→278352 /322010 | 274 | 0 | 0 |
| 其余5个build | dat字节SHA全等 | 0 | 0 | 0 |

16个entry的`uncacheData`、`io_ncOut_bits_data`、`io_mmioRawData_lqData`，每个64位
双方向，共6144点。完整LQ **4371→6144**；LQU和Wrapper完整基线已经6144，
所以它们此域的完整新增益为0，不能用定向小子集的增益冒充完整新增益。

所有旧hit保留，所有build三类点全集相等，固定Verilator分析器与独立解析一致；
原Wrapper2232份public/check/actor摘要全等。三层完整witness与定向witness全等。

## 4. 失败保持与精确源码迁移

基线与after-02的192个FAIL全文SHA均为
`c70dfc1912d01b60a2455df0c819adeed520727bfbb42969d9580e9a1100c8f7`。
原六build172 FAIL、SQ头许可旧UID失败和旧SID未消费重用失败全部保持。

从历史regression15新增纳入Load节点时，8个旧LQU失败仅因`SCENARIOS`插入单行，
导致consume栈帧255→256或266→267。专项审计核对固定旧/当前源SHA、唯一单行
diff、删除该新字典项后完整旧AST相等，并限定8节点、该一个帧比较；断言、实际
数据和全部其他文本逐字相同。不是宽泛行号归一化，不改历史JUnit/失败原文。

## 5. 耗时及后续工作

after-02 24 worker实际2274.17秒（37分54秒）。没有重跑已完成基线；保留中断01。
38-DUT统一回归和剩余缺口、SID、release-wait、disabled反馈、跨页/S4、完整核
容量producer与所有父级真实失败仍开放。后续性能工作遵守
`docs/contracts/lsq-runtime-summary-performance.md`，不能用减少检查提速。

### 复现与审计

- 原运行精确命令：各运行的`command.json`；after02 24 worker，命令完整范围相同。
- 专项只读审计：`python3 -B tools/audit_load_response_payload_v1.py --full`。
- 全链：`python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15`。
- 默认无逐拍JSON、波形、新完整源码副本；raw dat、JUnit、manifest、失败全文及
  compact witness保留。重建派生报告通过`write_report`按旧字节SHA归档。
