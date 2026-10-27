# 正常Load的RAW全池原UID、checkpoint与真实父级恢复

当前结论：**源投影补强后的两层定向运行和完整八build after专项审计完成，
1569节点1377 PASS/192 FAIL；证据索引接入实际exit0。整体LSQ仍ACTIVE_NOT_ACCEPTED。** 固定开源893e1580b原样
RTL/Chisel，Picker原生DUT、完整X Reactor参考与逐拍检查均不修改。

## 请求到证据

| 要求 | 实际证据 |
|---|---|
| 先定义人类可读功能点 | `docs/contracts/load-raw-checkpoint-owners.md`，populate/full/original/recover/retry/payload六项微架构行为。 |
| 从实际子块推进真实父级 | 已有RAW叶子`raw-toggle-gap-after-05`复核7168/7168存储方向点，不重复叶子运行；本轮真实LQ→Wrapper，各自保留真实RAW/RAR/Replay及上层连接。 |
| 独立功能检查 | `lsqverify/load_raw_owners.py`；公开输入建立不可变程序/UID，实际输出比较rollback/MDP、恢复指针、源正确S3、本地LQ释放；不读取DUT或model私有状态决定刺激。 |
| 具体用例 | `tests/{load_queue,lsq_wrapper}/test_raw_checkpoint_owners.py`，每层target0..55、每例四连续池生命周期。 |
| 正式定向证据 | `results/{lq,lsq}-RAW-owners-after-02/load-RAW-owners-evidence-v1.json`及各目录原始dat/LCOV/JUnit/manifest/witness。 |
| 历史失败与域纠正保留 | probe01的两个过早empty断言失败、formal01接口域限制、CLI拒绝日志和ROB源补强diff均保留，不冒称RTL修复或删除原运行。 |
| 完整贡献范围 | 实际1457节点旧基线不重复；`load-raw-owners-contributor-regression-02`实际纳入原八build全部贡献者及112新例，共1569节点，旧1457结果和192失败全文精确相等。 |

## 1. 为什么不是仅翻转checkpoint

每个程序只有一个未执行STA的老普通Store和57个年轻Load，总58个ROB程序项。
Load逐个派发并执行，前56个源正确S0/S1/S2/S3完成，RAW因老Store地址未知仍保存
它们。第57个Load真实S2查询时RAW ready=0、RAR ready=1，S3为C_RAW、update0并
正确revoke；不用空闲valid=0时恒为1的ready伪称容量检查。

原Store只发送一次、不可变地址的真实STA，与target选择的原Load同址。N+2输出
rollback逐字段核对原Load ROB/FTQ/RVC/64位checkpoint和Store FTQ身份、MDP训练。
实际原UID驱动外部flushSelf，检查真实LQ/SQ恢复尾和停顿，老Store幸存；已本地
释放的Load仍未架构提交，ROB取消它们与仍占LQ的溢出Load是不同义务。

取消后缀全部以新UID重新派发；LQ使用真实恢复尾（原溢出Load位置），不是虚构
回到已经释放的target槽。正常S0/S1/S2/S3后实际释放；Wrapper还检查同址新Load
获得原Store的8个真实转发字节，最终原Store真实Sbuffer消费、出队且combined SQ
empty。没有中途reset或将ROB许可视为Store消费。

四轮checkpoint为0/all1/按原序号图样/互补。每个target固定target%2 STA通道，
四轮读回同一通道已知写入的64位payload，避免依赖随机启动方向。RAW没有公开
物理slot号，功能证据为完整56项分配及逐target回读；native dat另核验物理存储
方向，**不声称隐藏slot指导了刺激**。

## 2. 上游投影与诚实修正

- 只有1个未执行STA，不使用56条未执行STA突破固定STA0/STA1各16项发行队列。
  Load逐条执行，不把56条未执行Load宣称同时占IQ。4B非压缩指令流生成单调FTQ
  块与0/2/4/6半字offset，不为翻转任意跳flag/RVC。
- 首次probe01为LQ2 PASS/Wrapper2 FAIL。Wrapper原Store已实际消费和出队，失败
  是在deq同拍立即要求combined empty。固定RTL中empty取VSQ与物理队列交集；
  新producer等待两者实际成立，原两个检查都保留，probe02为4 PASS。
- formal01曾在程序末把pending一拍前移58项。其59/65 PASS及原dat仍是实际
  **接口域证据**，但不验收为正常ROB提交历史；旧报告已通过`write_report`
  按原字节SHA归档，并标记`UNIT_INTERFACE_PENDING_JUMP_UNPROVEN_NORMAL_ROB`。
- 固定`RobDeqPtrWrapper.scala:59..96`与`Rob.scala:1248..1258`要求8项提交行及
  pending/pendingNext寄存关系。formal02逐拍先给pendingNext，再pending跟随，
  允许提交停顿，检查delta≤8、不跨行、pending等于上一拍pendingNext。compact
  witness保存该推进对；probe03四例及正式112新例全部验证。
- 修正diff通过内存重建原producer字节、精确恢复formal01整个验证库聚合SHA来
  审计，未保存一份完整新源码副本，未改旧测试/参考/共享actor。
- DCache、TLB、ROB和NewLoadUnit不在本DUT；这里是固定源约束下的接口生产者，
  不声称已做上游原生DUT或全核可达性验收。LQ无StoreQueue/Forward，不能借用
  Wrapper的Store转发/消费结果。

## 3. formal02同源定向比较

| 实际DUT | PASS节点前→后 | toggle命中前→后 /总数 | 新branch /总数 | 新raw line /总数 |
|---|---:|---:|---:|---:|
| LoadQueue | 3→59 | 55940→71090 /204148 | +2015 /16440 | +14 /3426 |
| LsqWrapper | 9→65 | 100832→120615 /322010 | +1069 /18670 | +18 /3654 |

每层56目标×4轮，12544次原RAW接受、224次真实容量nack、224次原UID rollback，
Wrapper另224次原Store真实消费。两层RAW checkpoint存储均7168/7168方向点，
rollback输出均256/256。baseline/after三类点全集及build相同、旧hit不丢、旧节点
结果和public stream保持。LCOV原始源码闭包另列JSON，raw line不是源码行。

**这些增益属于定向子集，不能冒充完整八build增益或回填38-DUT统一分子。**

## 4. 完整after及框架限制

已完成1457节点的`load-response-contributor-regression-02`作为真实基线。排除
明确列出的三个新增验证库文件和三份新增测试后，原159份库/195份测试完整聚合
SHA精确恢复；不因“看似没改”就复用旧基线，也不重复该基线DUT运行。

完整01尝试透传`--dist=worksteal`，锁定X Reactor CLI直接拒绝，exit2/0.268秒、
无DUT执行、无manifest/JUnit。`runner-limitation-v1.json`保留限制和原命令。
完整02使用24 worker与runner默认load调度，不修改/绕过工具、不拆长例、不减
5000周期排空预算，codec缓存仍默认关闭；不声称work-stealing或线性加速。

完整02实际2223.485秒（37分03秒），source launch/end聚合精确相等，原1457节点
结果及192份失败全文SHA均保持`c70dfc1912d01b60a2455df0c819adeed520727bfbb42969d9580e9a1100c8f7`，
新增112 PASS，0 ERROR/SKIP。完整范围以primary journal/manifest input_files核对，
Wrapper745→801、LQ201→257；旧2235份Wrapper public/check/actor stream精确保持。
112份完整witness与定向全等，冻结共享actor/参考源SHA不变。

| DUT | 完整toggle前→后 /总数 | 实际新增toggle | 新branch | 新raw line |
|---|---:|---:|---:|---:|
| LoadQueue | 143270→149506 /204148 | 6236 | 0 | 0 |
| LsqWrapper | 278352→282950 /322010 | 4598 | 0 | 0 |
| 其余6个build | 原dat字节SHA全等 | 0 | 0 | 0 |

完整RAW checkpoint存储LQ3870→7168、Wrapper4392→7168；rollback输出
LQ195→256、Wrapper192→256。全部三类点全集保持、旧命中无丢失，固定5.052
分析器与独立解析一致。LCOV原始闭包LQ50513/50520、Wrapper59595/59602均未变；
这些line分母不是rawline点分母。索引实际保留44补例、53源检查及原38-DUT矩阵，
不回填统一回归覆盖分子。

统一regression15仍2330节点、
2103 PASS/227 FAIL，缺口和分母不回填；SID、strict、disabled、release-wait、
头许可、混合排空、异常/跨页、全核容量资源历史及最终38-DUT扩大回归仍开放。

## 5. 复现入口

- 每次实际原命令：各运行目录的`command.json`，fresh目录不能覆盖旧运行。
- 专项审计：`python3 -B tools/audit_load_raw_owners_v1.py --full`。
- 新证据索引接入：`python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15 --raw-owners-index-only`。
- 幂等/原件保护：`python3 -B tools/audit_load_raw_owners_post_round_v1.py --capture`，随后同脚本不加参数。
- 默认仅摘要、compact witness、失败、覆盖、命令；无逐拍JSON、波形或完整新源码副本。

## 6. 下一缺口的精确源边界，不冒充覆盖增益

`tools/audit_replay_exception_payload_boundary_v1.py`核对RAW叶子之外的Replay
叶子及两个父级，精确限定`uop_0..119_exceptionVec_{23,19,15,7,6}`，每个DUT
600寄存器、1800个clocked写入和600个受`ENABLE_INITIAL_REG_`保护的initial
随机payload写入。固定Chisel在分配时`exceptionVec.zeroInit()`；生成RTL的每个
三路优先模板经全部1024组两状态取值核对，下一状态等价于
`old & !(need0&slot0 | need1&slot1 | need2&slot2)`。

因此**选中有效写入后为0，此后clocked公开输入不能把该存储位重新置1**。
不是“reset把它清零”，也不把任意未复位payload都归为不可达。对应方向点仍是
每DUT1200，叶子缺564、完整LQ缺622、Wrapper缺596，原始hit/missing点集合均
不变。所有分母保留，不为覆盖强塞源异常、改随机种子、force私有寄存器或删点。

该证明不覆盖上游初始随机化/四状态/故障注入，也不替代公开S3异常功能UT；不能
声称“异常功能不存在”或native动态覆盖新增。独立报告是本轮附加源级分类依据，
统一regression15原分类JSON未重写。下一正常Load Replay地址/指令类型/原因/
MSHR/TLB producer场景仍需先立语义合同再补例。

## 7. 故障后续审与幂等终点（2026-10-22）

会话因临时服务故障恢复时，先检查真实落盘：完整1569节点与专项审计均已完成，
原后台索引审计仍存活，因此未重复启动DUT或索引任务。原索引进程随后实际
exit0（162.682秒），接入44份定向补例、53份源检查和38-DUT矩阵。

`load-RAW-owner-round-post-audit-v1.json`实际exit0（83.961秒）重建新完整证据、
异常payload源边界及四个受影响索引，43份关键报告SHA幂等、670份原件/日志SHA
保持，未生成重复归档，native DUT重跑次数为0。原31份不受影响报告直接核验SHA，
更新的四份索引按旧字节SHA保留在`audit-history/`；**不声称又执行了一次全部
历史审计全链**。原192完整FAIL和227统一FAIL、所有接口域限制继续显式保留。

`next-normal-load-replay-metadata-selection-v1.json`定位下一步实际源缺口：
LQ/Wrapper `LoadQueueReplay`余20447/11577点；其中vaddr5141/3586、fuOpType
1351/1073、MSHR id933/814、TLB hint id718/757。只完成选择与合法性边界分析，
**尚无该下一补例的合同、用例或新增DUT运行**，不预填通过或增益。
