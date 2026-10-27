# MicroRAS：在途事件关系、实际效果与年轻 RETURN 缺口

## 已发布基线与本轮范围

基线 `production-sc-threshold-events-20261013-v1` 完整发布：15228 PASS、7既有
strict XFAIL、0 SKIP；305功能点298 PASS；BPU33146/46541，十DUT原生零回退。
集成MicroRAS89/91，独立MicroRAS91/91；集成剩余两行的局部阶段控制约束不改变。

此前068的16格和069的10格混合reset、全状态检查、场景规模、来源、功能效果与
排空。它们是历史检查清单；断言有价值，但标签数不等于同层级的硬件功能点。
本轮保留功能编号068/069及其已有三个DUT case，不增加新的功能编号。

## 事件与义务

| 真实事件条件 | 应保证的效果 | 来源关联 |
| --- | --- | --- |
| 无优先级更正，S1接受RETURN，S2/S3均有pending push | RETURN与年轻S2 push配对，输出来自较老S3返回地址 | 已知程序的真实UBTB请求与精确S3 metadata |
| 无优先级更正，S1接受RETURN，S2无pending操作、S3有push | RETURN与S3 push配对，输出采用main RAS top输入 | 同上，不把main top冒称独立主栈模型 |
| 中性S2更正推进、S3旧push、S1真实CALL | 取消年轻CALL的效果，前递旧S3返回地址 | 真实中性请求→公开S2更正、老S3祖先、年轻哨兵CALL |
| 同样的更正关系，S1真实RETURN | 取消年轻RETURN的效果，不能弹掉应保留的旧CALL效果 | 同上，年轻哨兵为RETURN |

后两行是同一年龄范围取消规则的两种操作上下文，不是两种地址或bank。以前真实
集成用例只有CALL；模型truth table不能替代RETURN上下文的DUT事件证据。
新增一个RETURN case复用中性跳转冷MicroBTB/热MainBTB构造，全部训练metadata真实，
RAS在正式程序中开启。年轻操作不得产生最终metadata或进入主RASspec通道；
程序全部目标、完整PHR、六笔真实退休/全部提交单元与排空检查继续保留。

模型分类读取实际输入资格和reset-derived pending状态，不读取case名字或route标签。
redirect或更老S3更正优先时，不登记这些被抑制的交互；没有fire/旧push也不登记。
一条事件的分类范围不等于整个MicroRAS所有功能，本轮只要求上表四种交互。

## 实现边界

`model/ras/micro_events.py`负责事件分类；`coverage/ras_micro.py`使用现有xreactor
CoverGroup记录reached/checked；`checker/ras/micro.py`继续使用既有Scoreboard。
事件发生时只记录reached；下一观察周期的全部九寄存器及完整模块输出都比较通过，
且tick精确对应，才记录checked。任一状态/输出/时序错误保留reached与失败点，抛出
ScoreboardMismatch交给pytest；未确认的事件不能用finish当成排空。

程序检查还要求指定真实public source见证的那个tick存在独立checked事件，不能用
准备阶段或另一条同类事件替代。只保留64条事件见证和累计计数；不导出逐周期轨迹。
旧`coverage/ras_correction.py`清单式实现已合并移除，历史日志和报告没有删除。

生产门禁分别要求四格reached和四格checked完整；少一格或缺一组均拒绝发布。
这与pytest功能点通过率正交；一个事件被检查不自动豁免用例后续失败。
没有新base class、matcher、信号边沿等待、RTL修改、VPI或内部写入。

## 独立资格结果

[`四场景资格`](../results/integrated-micro-ras-events-qualified-20261013-v1/exit.json)
退出0、4 PASS，pytest12.48秒，完整选测处理33.97秒；不发布为全量。
原两个RETURN配对、年轻CALL取消和新增年轻RETURN取消均通过。
reached/checked各4/4，总计5个事件（其中一条配对场景自然产生两个交互）。
新增RETURN确实在中性S2更正时被解码，随后全部状态和公开效果检查通过。

相关纯契约154 PASS；加入完整门禁后的相关契约192 PASS，包含前述154项，
不是两个独立数量相加。全BPU scoreboard兼容回归9648 PASS，166.71秒。
最终1765文件源码的完整生产回归
[`production-micro-ras-events-20261013-v1`](../results/production-micro-ras-events-20261013-v1/exit.json)
64进程已退出0并发布：15252 PASS、7既有strict XFAIL、0 SKIP；305功能点298 PASS，
216覆盖组204满目标；pytest446.21秒、完整657.36秒。reached/checked各4/4，
十DUT原生零旧键回退、新增0，BPU仍33146/46541。
相同memory-direct构建下，相对正式基线的原生新增为0；功能验证证据得到加强，
不把旧26格改成新4格称为覆盖率上涨，也不称集成MicroRAS已从89/91增加。

## 下一步的行缺口归因

ITTAGE目录仍使用含“第一次/第二次替换”的旧清单，尚未迁移。
其有效写事件应区分已有region复用、空闲分配和满表替换；新预测消费事件应区分
保留指针重新解码与幸存指针保持，分别关联真实反馈、目录提交及公开S3结果。
当前容量用例只在满表后复用，尚未单独证明“已有region命中优先于空闲槽分配”
的部分占用上下文。它是下一项需要验证的事件条件，不是增加bank/set组合。

集成TAGE当前仍有71个Tage.sv缺失原生键，其中selector训练与useful reset有
实际资格和状态条件，不能因独立TAGE高行覆盖就判为物理复制缺口。候选算术、
有效更新、最终写入必须继续分开归因；本轮没有冒称这些需求已经关闭。
