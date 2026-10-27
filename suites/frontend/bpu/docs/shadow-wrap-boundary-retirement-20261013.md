# 部分回绕的边界：停流不等于已接受任务消失

后续更新：upper slot1 已由真实集成 DUT 达到，但返回后的同槽训练清掉新 dirty，
完整场景正常 FAIL，正式 cross 仍29/30。见
[slot1 因果诊断](shadow-slot1-dirty-collision-20261013.md)。下文“尚未解决的边界”
保留为当时的模型阶段记录，现已由这份动态证据推进。

## 从行缺口到新功能需求

起点为已发布 `production-utage-split-context-20261013-v1`：BPU32947/46541，
shadow response-selection cross26/30，缺upper slot1/3/4/5 fallback。
它们不是新的 bank/set 需求，而是旧payload与回绕priority前缀的相对位置。
新 `BPU-INT-065` 复用已验证的两个稀疏四节点程序，同一输入几何、10个真实
MainBTB resident，不扩大物理坐标矩阵。

最高旧项 slot k 应紧邻首次新写之前，因此旧程序排空后必须 `enq%8=k+1`。
新程序部分回绕、排空和真实 D→A 恢复之后，还必须保留该项；最终响应不能
仅是同槽位任意数据，而必须对应本次恢复之后的合格 index/tag 请求和完整旧payload。

## 首轮失败暴露了准备层的问题

`sparse-wrap-boundaries-candidate-20261013-v1` 为1 PASS/1 FAIL，未发布。
slot5成功，但slot4在准备阶段期望enq=5、实际7，尚未进入返回阶段。
反复接受第一笔 A 的metadata后就暂停，会不断打断正常 index/tag 前后文，
并不能保证真实upper provider继续产生写入。增加循环次数不是解决办法。

该轮新测试也曾绕过输出目录fixture；三个误放的语义JSON已移入该候选目录的
`misplaced-artifacts/`，没有删除失败证据。新测试改用已有的worker/test隔离输出fixture，
正式产物只从本轮验证过的worker收据导入。

## 环境负责自然流和退休感知边界

`SparseProgramEnvironment.align_upper_boundary()` 保持正常程序流，按reset-derived
模型的enq停止；背压请求之后继续排空真正已经接受的任务。
记录停止前后模型enq差值，下一次将停止边界提前相同的写入数，直至**排空后**
达到输入计划要求的边界。8次是失败预算，不是每次需要等待的周期。

例如slot4的一次实际观测：

1. 目标enq低位5，首次在5停流；已有任务再写1笔，排空后变为6。
2. 下一次在4停流；已有任务再写1笔，排空后低位为5。
3. 再检查全部旧payload，才允许恢复第二程序开始部分回绕。

退休数来自独立模型对实际接受训练输入的推进，不来自DUT chosen/response；
没有固定settle延迟、时钟边沿操作、内部写入或伪造metadata。
已在正确边界时不会偷偷恢复年轻请求；历史无法推进或反复无法对齐必须直接失败。

## 最终源码的独立资格

三个场景分别在独立目录完整执行，均1 PASS、未替换正式报告：

| 最高旧项 | 排空后old hits | priority mask | 完整返回payload |
| --- | --- | --- | --- |
| slot5 | `0x3c` | `0x03` | valid1/tag75/position6/counter0 |
| slot4 | `0x1c` | `0x03` | valid1/tag75/position6/counter0 |
| slot3 | `0x0c` | `0x03` | valid1/tag75/position6/counter0 |

资格目录为 `sparse-wrap-upper3/4/5-qualified-20261013-v1`。
返回时明确区分更早C→D的index上下文与D→A的tag上下文，检查公开训练folds和
conditional provider元数据，并要求公开预测选择真正的position10 fallback、target B。
完整PHR、1024 counter、256 PLRU、两个shadow的全部cell/dirty/useful/pointer、
SRAM端口及输入/响应关联检查保留，随后再独立重放全部shadow记录。

三种边界×9项契约为27/27；lower slot1/2/7准备响应仍为必需断言，没有因参数化
放松原slot6场景。旧slot6覆盖schema保持原样。21项新增边界/异常契约加80项
已有几何/恢复/公开payload契约为101 PASS；中间三DUT联合回归也包含旧slot6 PASS。

与上述生产基线合并，response-selection cross候选为29/30（96.67%），组平均
99.17%不是cross闭合率。每个新场景的精确行差分分别为：slot3新增0、slot4新增10、
slot5新增3；**去重并集只有10**，都在`BypassShadowBuffer_1.sv`。
slot3证明了“原生行已命中不等于有效payload功能组合已验证”，不能省掉其检查。
独立增量不能冒称全量联合率；生产刷新必须通过零旧键丢失及收据/源码门禁后再发布。

## 完整生产发布

[`production-sparse-boundaries-20261013-v1`](../results/production-sparse-boundaries-20261013-v1/exit.json)
现已实际退出0并发布：14,702 PASS、7既有strict XFAIL、0 SKIP，298功能点全执行
（291 PASS/7 XFAIL），209组中197组达到完整目标。pytest447.06秒，完整刷新660.12秒。
response-selection cross正式为29/30（96.67%），组平均99.17%；新boundary组27/27。
BPU32957/46541，相同分母下精确新增10键，十DUT零旧命中丢失，其余9 DUT不变。
全部10键是旧物理范围曾命中的恢复路径；旧范围与当前仍相差7494个丢失旧命中，
另154个旧缺失当前已命中，不把范围损失全自动说成物理重复。

重新核验64份收据、967份功能输入文件、三个资格运行与全量相同的冻结源码、
JSON/HTML/全部原生LCOV以及production索引哈希，记录
[`增量与发布一致性检查`](../results/production-sparse-boundaries-20261013-v1/boundary-increment-audit.json)。
该检查不冒充独立完整动态审查，整体验证目标仍未完成。

## 尚未解决的边界

upper slot1仍未覆盖。这组实际停止/退休序列最终prefix为0..1，不能保留slot1
作为前缀外fallback；这只是当前输入计划的限制，不是整个DUT的不可达证明。
下一步需要研究回绕之前停流、将已接受写入纳入预计最终前缀，并核实返回后的
训练是否会触发既有same-slot dirty-copy缺陷。没有实际DUT证据前不增加PASS或豁免。

已执行一个**仅输入模型的局部反例**：10次old index265/tag75分配后，再7次
new index494/tag117分配，得到old hits=`0x02`、mask=`0x01`、enq=1。
随后从265读出旧owner并更新，`enq slot = train_slot = 1`。
独立模型要求新项dirty1；实际Scala的三个顺序赋值中，最后的
`when(t1_hasWrite && t1_hasHit)` 会将 `statusEntries(t1_cleanId).dirty` 清零，
覆盖前面的新项dirty1，见
[BypassShadowBuffer.scala:243–257](../XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/BypassShadowBuffer.scala)。
这个局部输入使用分配后的counter4，不冒充当前negative四节点程序的实际返回；
它只明确了必须排查的同槽条件，尚未证明集成BPU接受流能形成或避开该冲突。

已有7个strict XFAIL不变；不修改RTL、不删原生分母、不写内部状态、没有VPI，
波形和逐周期JSON仍默认关闭。也不声称完整FTQ生命周期合法性或整个目标完成。
