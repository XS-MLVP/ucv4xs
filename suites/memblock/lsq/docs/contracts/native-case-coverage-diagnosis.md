# Wrapper 旧 toggle 命中丢失的逐用例导出诊断

本契约在观测插件及新诊断运行前建立。目标是解释已保留的 2125 个旧 toggle
命中为何在真实四目录重跑中消失，不删除它们、不把净增益当门禁通过。
整体 LSQ 的分层语义 UT、补例、全部 DUT/变体/父级和历史失败要求保持不变。

## 要回答的具体问题

1. 原 Wrapper 用例单独或在明确前序下运行时，是否实际命中这些原本丢失的点？
2. 同一原节点的公开输入/检查/actor 摘要相同时，native 导出计数和目标点集合
   是否相同？若不同，是观察到的差异而不是自动推定的初始化/don't-care。
3. 从单用例 Finish 导出，到 X Reactor 的 worker 合并及最终合并，已观测到的
   目标位图 OR 与计数和是否守恒？不得以新工具声明替代真实 artifact 核验。

## 只读观测边界

- opt-in pytest 插件只在 function fixture 已 Finish、原 NativeCollector
  `end_case` 尚未消费/清理原 dat 的 teardown 边界读取它。
- 不调用新的 DUT Step、RefreshComb、ResetCoverage、SetCoverage 或内部信号
  访问，不改变库/RTL/Chisel、测试选择逻辑、公开引脚或参考模型。
- 原 NativeCollector 的注册、原始导出、点全集验证、计数合并与清理照常执行；
  插件不接管产物、不替换原覆盖文件，不修改锁定的 Picker/X Reactor 工具库。
- 每个 wrapper 节点只保存一次 compact 导出摘要：原 dat SHA、build ID、
  三类 raw/非 wrapper 指标、2125 目标的固定顺序 hit 位图及计数和、目标集合 SHA。
  目标集合由两个原始 dat 的确切差集恢复，不保存完整源副本、逐拍 JSON 或波形。
- 位图只用于定位 coverage 导出，不作为 stimulus/功能 oracle；测试输入仍由
  用例前的独立 producer 合同决定，原实际比较与真实 FAIL 不屏蔽。

## 诊断用例及验收边界

先以原 `[aligned-0]` Wrapper 用例对比插件关闭/开启，要求实际结果、三份
公开 journal 摘要、native build/点全集/全部计数不变，证明该观测器未扰动这一
控制流。随后重复原 Uncache 全池、Replay 全池、非零 SQ 窗口等相关原节点，
包括已知 FAIL；节点结果及归一化失败与原回归逐项核对。

每组诊断必须核验真实 native 汇总与逐用例目标位图/计数和的守恒。源集合在
一组运行启动/结束之间不变；成对比较除显式 opt-in 插件外使用相同测试与 build。
只能在有具体逐点/逐节点证据后解释某个丢失点。无法解释的点和单调性门禁继续
`FAILED_OPEN`，小型复现通过不替代 1025/2330 节点或整个 LSQ 验收。

## 实际 native 贡献者范围修正（新运行前）

原 manifest 的 Wrapper native `input_files=730`，而四目录运行只有 691。
从原实际 `lsq_wrapper/lsq_probe.summary.json` 可恢复 730 个唯一贡献节点：
主目录 689，另有 `tests/local_reset` 的 15、`tests/normal_mixed` 的 8、
`tests/sq_endpoint/test_ldu_joint_phases.py` 的 12 和
`tests/sq_endpoint/test_wrapper_raw_boundary.py` 的 6。后三类共 41 个节点未在
先前四目录命令中，不能以目录名当成同 native build 的完整用例范围。

下一步真实运行这 41 个旧节点（包含原 12 个 FAIL），使用已有 fixture/模型
不变；按实际原生导出摘要和 journal 识别贡献者，不按 `tests/lsq_wrapper` 路径
过滤。要求每个节点的结果/失败全文及公开/check/actor 摘要与原回归相等，
逐点比较所命中的 2125 差集及 case→merged 守恒。仅若实际完整差集被重现，
才可认定本次丢失源于少跑了贡献节点，而不是初始化或随机上下文。

随后必须 fresh 实际重跑完整贡献范围，不能把 1025 节点与 41 节点的覆盖
OR 后冒充一次真实运行。旧 `FAILED_OPEN` 运行/报告仍保留；新的门禁只有在
所有旧节点、失败和 line/toggle/branch 点集真实保留后才可通过。

诊断命令选取 `tests/normal_mixed` 目录时还执行了 2 个旧 Python-only ledger
检查，因此诊断总计 43 节点（31 PASS/12 FAIL），其中真正 Wrapper 原生贡献者
仍为 41 节点（29 PASS/12 FAIL）；这两项不当作 native DUT 的覆盖贡献。
后续完整贡献范围命令显式选择 `tests/normal_mixed/test_original_seeds.py`，
使全部 1066 个执行节点与四 build 的原生导出一一对应。
