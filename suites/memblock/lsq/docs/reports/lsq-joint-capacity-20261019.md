# LsqWrapper 联合容量与实际公平服务：补充定向证据

**后续源准入纠正**：下文旧6 PASS、UID与DA原件保留，但公开历史审计发现缺原生
S3/revoke及CBO NoSpec/BlockBack，不再视为正常生产者满池证据。见[拒绝原件](../../results/lsq-joint-capacity-04/joint-producer-audit-v1.json)
与[源正确分阶段重建](lsq-ldu-joint-phases-20261019.md)。旧RAR96与LRQ120长期原UID
双占不能作为新正常稳定快照；新程序保留全部容量峰值但经真实原UID完成进行转移。

**状态：本批6例真实PASS，整体仍NOT_PASS、目标active。** 本批不是替换原8个
全域固定种子首失败的“保守随机”，不勾选三个STRESS总bin，也不改目标RTL。
完整扩大Wrapper和受影响LoadQueue回归也已结束并审计，不能把6例局部通过当整体验收。

## 1. 用例前语义和原生边界

用例前要求见[Wrapper合同](../contracts/lsq-wrapper.md)的联合容量/公平阶段补充。
新增`tests/lsq_wrapper/joint_owners.py`复用原独立混合UID/副作用账本，但使用显式
轮转服务；`test_joint_capacity.py`为两个固定payload/dispatch种子×普通、shared
redirect、共同系统reset。它们不是全域随机种子的替代，所有用例使用原严格
全输出`lsq` fixture，不新增probe或豁免。原样53文件native DUT及603/458引脚保持。

单一程序序是64个老Store、120个Load、64个年轻Store，共248个不同ROB身份，活动
跨度小于完整ROB640的半环320。Load真实SQ依赖边界64；SQ可虚拟占用128，但只
当前64物理窗口允许STA/STD。老SQ0保留真实地址缺口，其余63个真实STA/STD完成；
16个NC Load实际总线请求/方向ack保留未回包，104个缓存Load真实查询共同填池。
年轻64项含普通、NC、IO和CBO0..3，公平阶段逐原UID执行、消费、WB/释放。

### 同一时刻实际保留的容量

| 容量/义务 | 单个快照真实值 | 独立公开历史依据 |
|---|---:|---|
| SQ虚拟/可发行物理窗口 | **128 / 64** | 128个单flow uop、完整exclusive tail，后64未发STA/STD |
| LQ | **120** | 连续原LQ UID，无普通S3完成/无VLQ释放 |
| RAR | **96** | 原查询真实ready接受96，后续8拒绝，真实VLQ头仍未前进 |
| RAW | **56** | 原查询真实ready接受56，后续48拒绝，SQ0缺口阻止真实地址指针前进 |
| Replay | **120** | 120个不同原Load的单hot重放S3，尚无反馈；后续全120实际slot分别授予/反馈 |
| Uncache/外部未响应 | **16 / 16** | 16笔实际NC接受、16个mid和16个在用SID，未bypass/未返回 |

这些是同一真实Wrapper快照，不合并独立叶子或不同case峰值。共有22个原UID代际
快照：普通两例各3轮；redirect/reset四例各1轮取消/中止＋3轮真正完成。
`io_sqFull`在合法128边界仍为0：实际PSQ.sv16123为寄存计数`>128`，不能将名字
误当`==128`的VSQ full或伪造已经删除的canAccept端口。

## 2. 已结束局部运行、连续检查和独立审计

冻结目录：`results/lsq-joint-capacity-04/`，**6 PASS**，364份启动/结束验证源SHA
一致，原生artifact/build SHA已由`verify_common`复核。独立
`joint-history-audit-v3.json`核验**11766条连续原始记录**；它只使用输入/pre/post
公开历史重建语义，不读取DUT私有寄存器、actor/model/change作为答案或问题清单。

| 已审计义务 | 数量/守恒 |
|---|---:|
| 原UID | **5456＝4464完成＋496取消＋496共同reset中止** |
| 取消/reset同物理槽新UID真正完成 | **992 / 992** |
| 原Replay授予/原slot反馈 | **6030 / 6030**，多轮重放不是6030个新Load |
| 总线实际接受 | **388＝352 Load＋36 Store** |
| 原方向ack | **388** |
| 实际原响应 / 外部共同reset中止 | **356＋32＝388** |
| Load原数据消费 / 取消返回丢弃 | **288＋32**；另32个reset旧job未回包、未消费 |
| 原Store片段实际消费 | **2214** |
| 原Cache请求/响应 | **54 / 54** |
| 原Store WB.fire | **90** |
| 实际停止新分配后的公平服务段 | **18**，每段248原UID均真正完成 |

公平段所有公开服务ready持续有效，按原UID轮转查询/S3/bypass，同时消费真实
Replay候选；每个已接受job按原方向/mid/SID ack/resp，Cache请求实际应答，
原Store字节及zero由实际Sbuffer消费，SQ只按完整完成前缀释放。结束需要全部
原UID、原slot、外部job、Cache和合法ROB前缀完成，再核对empty/replay状态，
而不是等固定拍数、仅看empty或把grant当完成。超时只会普通FAIL。

每例正常三轮实际完成**744个UID**，完整ROB640编码都由dispatch及后续执行完成
见证，SQ256、LQ240也跨完整编码复用；不是低index排序或reset假装跨圈。
redirect后32笔旧Load响应全部真实偿还、丢弃而不造bypass；共同reset则32笔
明确中止而非响应。此处reset发生在NC读等待，不声称可撤销已接受Store写，
也未验证local-only reset后迟到旧回包的不同合同。

## 3. 参考相位纠正和审计器自身边界

全部首失败及版本保留：

1. `lsq-joint-capacity-01`六例停于新helper假设。最后两个RAW credit按输入lane
   而非旋转后的UID顺序接受。只将整个第19组三个Load绑定真实SQ0缺口；仍只有
   56条RAW实际分配，不增加池、不伪造重放原因、不改参考或RTL。
2. `lsq-joint-capacity-02`实际联合满池后停于helper误要求`io_sqFull==1`。依据真实
   PSQ连接更正为0，保持128 UID/64发行和实际释放检查，不非法增占用到129。
3. `lsq-joint-capacity-03`为4PASS/2FAIL。两个reset在tick324的perf17/24失配来自
   参考仍把复位前满池111当新采集事件。FreeList三个相关变体均异步清占用，
   reset拍真实full_mask已是000；LoadQueue.sv1060-1075的无reset流水却必须继续
   传递历史。只更正父参考的**新采集mask**，不清历史、不重开unknown屏蔽或改
   比较掩码。v3确认04的4个原PASS全部raw逐bit不变、两个旧失败完整raw为新例
   前缀。reset实际perf17/24在tick318/320/322为0/1，到tick324才为1/0。
4. 独立history-v1误写原因编号。v2依据开源Replay.scala47-67更正MA2/SMF1/
   RAR9/RAW10，原v1及拒绝保留，不改任何事务或参考。v2又只用恢复后相同队列尾
   去重容量快照，遗漏两次新UID代际标签。v3增加原UID代并要求fair owners恰等
   自己的容量快照owners，确认22代/18段，而非把取消老代贴给新事务；v2报告和
   源也保留。

`joint-negative-audit-v2.json`另在内存副本中分别污染同bank原反馈slot、CBO
opcode、zero实际字节、删去一笔已接受但取消的原响应。opcode/zero连对应
expected一起污染，前两输入变异也同步改两份raw pins；四项均被独立原UID语义
拒绝，原日志SHA不变。negative-v1最初误找反馈输入`replayQueueIdx`而非真实
`schedIndex`，尚未执行语义负判即拒绝；v2只修正变异器字段名，保留原器。

## 4. 尚未完成的整体范围

- 本批是**干净响应、对齐且地址不重叠**的联合正条件；不包含全域随机的别名、
  split、错误WB背压、SID未消费即合法复用等所有失败域，不将其替换或设skip。
- 八个原固定种子全域尝试仍中途FAIL，原取消/失败在途义务仍不能计最终完成。
  本批18个实际fair段只证明本批原UID排空，不给原失败种子补造fair阶段。
- STRESS容量/fair已实际到达，但三个STRESS总项仍未checked；完整混合随机、
  更广的联合恢复/reset交错和最终完整请求→证据/未验证边界审计仍需继续。
- `lsq-expanded-16`完整317例为**269PASS/48FAIL**、364源；`lq-joint-impact-02`
  原199例仍**187PASS/12FAIL**、367源。结束源已捕获；`joint-impact-audit-v1`
  核验72918＋28820＝**101738记录**、旧311/199原始轨迹/全部60失败签名保持，
  新6例与04冻结原始历史相同；原DA集合/命中分别59595/59602、50513/50520不变。
  参考AST仅reset采集mask=0，其他语义/流水/knownness不变。`lq-joint-impact-01`
  仅因shell300秒超时中断，无活动遗留
  进程、已捕获367结束源，不冒称完整199结果；新目录重跑，不覆盖该残留。
- 本批不追溯混入旧38DUT1808例统一回归07；扩大范围仍需新38DUT回归及审计。

重审已完成局部证据：

```sh
python3 -B tools/audit_lsq_joint_history_v3.py lsq-joint-capacity-04
python3 -B tools/audit_lsq_joint_negative_v2.py lsq-joint-capacity-04
python3 -B tools/audit_lsq_joint_history_v3.py lsq-expanded-16
python3 -B tools/audit_lsq_joint_impact_v1.py
```
