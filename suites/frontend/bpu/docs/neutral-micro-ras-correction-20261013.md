# 中性S2修正：保留较老CALL并冲刷真实较年轻CALL

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


归因起点为已发布的 `production-early-ras-pipeline-20261013-v1`：BPU33119/46541，
集成MicroRAS87/91。剩余180/181是中性S2 correction与较老S3 push的地址前递，
不能由普通连续call/return或独立MicroRAS的91/91替代。133/134仍受当前集成推进
连接局部排除，完整91行分母保持，见 [前一轮归因](early-micro-ras-pipeline-20261013.md)。

## 功能点 BPU-INT-069 与输入准备

只用一个输入几何：三次不同call、一个action0跳转、三次LIFO return；在action0
跳转的fallthrough地址安装一条不同返回地址的CALL作为错误路径哨兵。
前三次call和三个return由真实公开反馈同时安装到MicroBTB/MainBTB。哨兵也通过
真实冷metadata训练，不直接写任何表或伪造hit/resolve metadata。

中性跳转必须**最后准备**，全程关闭MicroBTB、开启MainBTB，使其resolve及fastTrain
都不能把这条跳转提前教给MicroBTB。停止年轻请求、按实际状态排空后，再开启
MicroBTB和真实RAS，从先前真实checkpoint恢复程序。这样中性跳转必须在S1
FALLTHROUGH、S2修正为taken，不能靠修改target就假定出现S2 override：当前S2
只比较taken、position和attribute。

[`case`](../bpu/case/ras/correction.py) 仅编排输入与已有agent/retirement
driver；[`checker`](../bpu/checker/ras/correction.py) 负责精确来源关联、
完整S1/S3目标、真实S2修正及错误路径排除。不增加时钟边沿操作或经验性settle。
沿用静态memory-direct Bundle、lossless @on Monitor和reset-derived九寄存器
MicroRAS参考，不新增调度器、队列或框架hack。

## 必须实际观测的三方重叠

以下是最终隔离资格的实际tick，**不是刺激等待常数**：

| tick | S1 | S2 | S3 | 关键检查 |
| --- | --- | --- | --- | --- |
| 536 | 第三个热CALL | 第二个CALL | 第一个CALL | UBTB连续接受，三个返回地址不同 |
| 538 | 冷中性跳转：not-taken | 第三个CALL | 第二个CALL | 公开fallthrough指向错误路径哨兵 |
| 540 | 错误路径CALL真实解码 | 中性跳转taken correction | 第三个CALL push | S2优先；前递较老返回地址，flush年轻S1 |
| 542 | 正确路径第一个return | flush后的年轻槽 | 中性跳转 | 公开目标/精确S3关联正确 |

540拍MicroRAS必须选`s2-neutral/s3-push`，实际S2输入action0、fire2=1、valid1；
不得用redirect或较老S3 correction替代。较老S3 pending必须为push、非pop，地址
为第三个CALL的`0x40010890`；较年轻S1输入必须为哨兵CALL，PC=`0x40010910`。
参考预测下一输出usable1/地址`0x40010890`，而不是年轻CALL的`0x40010920`；
年轻pending push/pop都必须清零。后续周期的全部实际寄存器/输出继续与参考比较。

公开S2 correction必须完整返回中性跳转的真实目标；每笔最终S3目标也按已知程序
逐项检查，不能只检查S3 perf对早级错误预测的回显。错误路径CALL在正式窗口内
不得产生最终公开metadata，也不得进入main RAS的实际speculative端口。
准备期哨兵的真实metadata不被误算为正式窗口泄漏。

三个CALL和三个return的六份真实metadata按程序顺序退休，检查全部8个保留提交
单元、head、接受/应用一一对应；最终head回0。完整PHR状态/metadata关联从reset
持续比较，停止年轻请求并排空后再要求全部MicroRAS pending操作为0。
十项契约全部通过后才导出功能覆盖，不把wrong-path CALL伪装成neutral commit。

main speculative RAS top仍是MicroRAS的显式模块输入，不声称main speculative
stack全状态已独立建模或完整FTQ合法性；已知程序目标、真实SSP顺序和提交栈则
另行独立检查。没有VPI、内部写入、bank/set枚举、波形或逐周期JSON。
最终只导出七个语义输入见证、一份修正见证及计数summary。

## 负向检查、资格和原生增量

相关纯契约137 PASS，其中新70项：错误/缺失/重复来源、晚期寄存器结果、较老
地址与年轻CALL、public correction、wrong-path metadata/spec泄漏、S1和最终S3
全部字段、时间窗口及每项缺失coverage门禁，均要求普通contextual mismatch。
复用前一轮67项reset-derived pending模型/全寄存器/输出/flush/drain契约。

[`正式隔离资格`](../results/integrated-neutral-ras-correction-qualified-20261013-v1/exit.json)
退出0，10/10语义格；1758文件源码epoch。实际288观察周期、930项MicroRAS检查、
6612项PHR检查、937项提交检查，六笔接受/应用与全部返回均完成。
[`原生差分`](../results/integrated-neutral-ras-correction-qualified-20261013-v1/functional-line-delta.json)
精确新增10键：MicroRAS180/181、MicroBTB哨兵entry写入7键、替换器1键。
10键旧全物理范围也未见；后8键是语义哨兵带出的自然路径，不是8个新功能点。
隔离MicroRAS至89/91；以下完整生产精确重现该增量后才替换正式指标。

## 完整生产发布与复核

[`全量终态`](../results/production-neutral-ras-correction-20261013-v1/exit.json) 已退出0并
发布：15,069 PASS、7项原有strict XFAIL、0 SKIP；303个计划功能点全执行，296 PASS。
214功能组中202达到完整目标，新组10/10格闭合。64worker pytest446.93秒，
包含原生处理/报告/门禁的完整刷新658.85秒。只增加70项纯契约和1个DUT case，
无旧测试移除、功能状态退化或XFAIL集合变化。

[`增量/发布一致性复核`](../results/production-neutral-ras-correction-20261013-v1/neutral-ras-increment-audit.json)
重新验证64收据、973功能输入及1758文件冻结epoch；资格、全量和发布代码一致。
十DUT原生分母及构建身份不变，memory-direct/VPI=False，旧命中零丢失；唯一新增
集合精确等于隔离10键，BPU33119→33129/46541，其余九DUT不变。
集成MicroRAS87→89/91，只剩133/134局部约束，不扣分母；独立MicroRAS91/91不变。
有界语义summary和资格完全相同，全部旧schema/重复命名实例保留；根JSON/HTML、
canonical LCOV及production profile索引一致。

旧全物理与当前生产仍分开比较：旧命中丢失7428键，新命中260键，不把所有范围
损失都自动说成physical-only。前一轮16/16早级MicroRAS与10/10ITTAGE目录组保留，
shadow cross仍29/30。`formal_current=false`、
`independent_full_dynamic_audit_complete=false`、`goal_complete=false`保持。

既有7项strict XFAIL、ITTAGE零置信度跨region重写普通FAIL、shadow upper1普通FAIL
仍开放，不因这次新功能PASS或MicroRAS剩余行的集成约束而被豁免。
