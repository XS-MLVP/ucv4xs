# ITTAGE周期语义与074合格覆盖增量

2026-10-15，`BPU-INT-074`已通过；相对最后已发布
`production-ittage-directory-events-20261015-v1`，严格归因**31个原生新行点**。
这是单场景资格验证，不是新全量发布。总体覆盖率、其他模块缺口和剩余模型工作仍需
独立完成，不能用本报告宣称目标已完成。

## 功能缺口和oracle问题

原缺口是全局qualified no-allocation tick饱和触发useful维护的完整生命周期：实际
反馈资格、排除条件、read/update优先级、全SRAM清除，以及清除后的保留目标消费者。
此前候选把已发送反馈立即写入`IttageContextModel.entries`，使得读取压力下合法的
旧目标被误判为错误。该失败不能归因于RTL。

本轮使用独立[IttageReference](../bpuverify/ittage/model/semantic.py)，由集成组件的
PC、折叠上下文、阶段推进和训练输入驱动。输入只是组件接口事件，模型自有全部表、
计数器、目录、在途更新和读取快照；不从DUT SRAM/计数器读取golden。
集成层没有重复实现学习算法。

[memory-direct绑定](../bpuverify/bpu/bundle/ittage_semantic.py)覆盖所需端口，包括
Verilator优化后的合法派生视图；没有VPI、没有内部写入或伪造端口。组件输入是已经
求值的RTL输入，所以monitor不套用顶层pending RiseWrite的额外launch转换。
用例没有新增边沿等待或等待固定周期来掩盖时序。

消费者的expected来自其**meta tick对应的不可变读取快照**，不是当前表，更不是
最后发送的反馈。辅助维护审计也不再修改这些历史快照的useful。
S3纠正资格按实际被选择的上游S1/S2预测基线检查；最后发送目标尚未提交时，不能
据此要求一个本来不需要发生的纠正。

最终读自由维护窗口完成后显式恢复prediction ready，再捕获消费者。初次接入在
最后一步超时，是未恢复ready的用例控制错误；保留失败证据，未增加timeout绕过。

## 权威证据

候选：[integrated-ittage-semantic-aging-20261015-v3](../results/integrated-ittage-semantic-aging-20261015-v3/summary.json)。
`process_exitstatus=0`、`selected_regression_complete=True`、`reports_published=False`、
`full_regression_complete=False`。1PASS，30.91秒（call21.16s/setup7.63s/teardown1.06s）。

- 精确收集1项，JUnit与test-results一致，source epoch1816项与当前源码相同。
- 独立组件语义9054检查全PASS，269个公共来源关联，1546个自有模型提交。
- 每周期独立tick/维护状态与已核实硬件审计比较，最终tick0、三个busy0/cursor0。
- 265个真实反馈：increment256、decrement6（实际下降1次）、correct-update排除2、
  correct-unconfident排除1；自动饱和reset一次，不需要追加触发反馈。
- read-blocked21、update-blocked1，实际useful-only SRAM握手1024次，完整地址足迹
  由硬件自身扫掠产生，输入没有枚举bank/set。
- training、maintenance、consumption的reached/checked共六组全部100%。
- 纯事件、历史快照、错误源/输出、周期错位及旧维护诊断测试174PASS，0.56秒。

## 原生行点归因

[qualified-line-delta.json](../results/integrated-ittage-semantic-aging-20261015-v3/qualified-line-delta.json)
校验同一DUT/signal构建身份、相同46541个LCOV键、唯一PASS场景、功能点与测试
关联、原未命中文本和源文件哈希。新增行点如下。

| 源文件 | 新行点 | 硬件事件语义 |
| --- | ---: | --- |
| Ittage.sv | 2 | tick正饱和后的自动归零，源位置696–697 |
| IttageTable.sv / IttageTable_1.sv / IttageTable_2.sv | 3 | 全局useful维护使游标实际推进，各1点 |
| WriteBuffer_24.sv / WriteBuffer_28.sv | 26 | 维护写入触发slot1的完整缓存更新路径，各13点 |

两个WriteBuffer模块确由ITTAGE三张表使用，不是无关模块顺带事件。完整逐行清单、
Scala引用及实际计数在delta中；有些生成行没有直接Scala行注释，未伪造归因位置。
独立选测命中25030/46541，不能与全量33257/46541直接当涨跌比较；+31仅描述原
基线未命中、这个场景已命中的同构行点，不是把并集33288当成已发布当前覆盖率。

## 未完成项与权限边界

ITTAGE无新表分配的跨区域零可信度学习、UBTB耗尽后连续not-taken复活、URAS组合
动作解码仍有普通FAIL。没有新增skip/XFAIL或把失败结果同步到golden。完整BPU
FTQ合法性、主路由/历史组合reference及其他七个UT模型仍未完成。
当前XiangShan是detached HEAD；本轮没有改RTL或重建DUT。任何硬件修复都先请求
独立本地分支的授权，不直接在detached HEAD覆盖已有工作。
