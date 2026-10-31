# Store 全宽载荷补例、真实目录重跑与统计边界复核

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


**结果：ForwardModule → PhysicalStoreQueue → StoreQueue 的新补例及三类覆盖
审计已通过；三个目录完整重跑为 268 PASS / 64 FAIL，原失败完整保留。
整体 LSQ 仍为 `ACTIVE_NOT_ACCEPTED`，目标不关闭。**

固定 `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` 原样 RTL；
未修改 RTL/Chisel、替换真实下级、改参考模型、使用 skip/xfail 或放宽检查。

## 请求到实际证据

| 要求 / 功能点 | 实际检查 | 可复核产物 |
|---|---|---|
| 先定义语义功能点 | 64 槽四代：全一→逐槽逐字节图样→互补图样→全零，高/低 VA、PA 交替；正常完成后同槽复用 | `docs/contracts/store-payload-pool.md`；先定义合同，再实现与探测 |
| 独立参考与公开检查 | 原参考模型和 DriveStable/RisingEdge 每拍比较不变；新字节 oracle、UID 台账只使用公开输入/输出 | `lsqverify/store_payload.py`、三层 `tests/*/test_pool_payload.py` |
| 真实父级层次 | PSQ 保留 Forward/Deq/UQ/Sbuffer 真连接；StoreQueue 保留 VSQ→PSQ 真连接与真实 ROB 许可、出队反馈 | 三组 baseline/after-02 的 `execution/manifest.json` 与固定 build/source SHA |
| 背压、容量、时序和正常复用 | 每代 64 槽在无退休许可、Sbuffer ready=0 时不提前释放；每槽三路有效 S2 检查后实际消费并正常出队，再进入下一代 | 每层 `cases/**/store-payload-pool-witness.json`；父级各 256 个 Store UID、256 次消费与完成，每层 768 个有效 S2 响应 |
| 数据和地址不能截断/串槽 | 真实父级 `dataEntries_<slot>_data[0..127]` 的 16384 个位方向点全中；VA[49:25] 的 3200 点及 PA[47:25] 的 2944 点全中；图样区分槽号与字节 | `store-payload-pool-evidence-v1.json`；逐点源位置由原 dat 恢复，目标声明行范围和固定源 SHA 可复核 |
| 每 build 的三类前后差集 | 同源集合摘要、同 build、相同点全集与分母，旧节点和旧命中不丢失；原始 line 点与 LCOV 源码行分开 | `directed-gap-closure-*-v1.json`、专项 audit、原 `coverage.dat`/`coverage.info` |
| 不用绿色补例代替原业务范围 | 完整执行 `tests/forward tests/psq tests/store_queue`，保留原 329 节点，增加 3 PASS；所有 64 个 FAIL 的归一化全文不变 | `results/store-payload-failure-retention-01/`、`store-payload-regression-evidence-v1.json` 与统一 failure-preservation audit |
| 逐缺口提供具体边界证据 | 对 137 个初始化 branch 点逐项验证固定源 SHA、initial 作用域和 ENABLE_INITIAL_REG_ 外层；纠正 130 个通用标签 | `initial-branch-boundary-audit-v1.json`；保留全部 563 个原未命中点与分母，不称作动态覆盖增益 |
| 统一完整范围与历史 | 38-DUT 矩阵收录 15 条独立定向报告；统一 regression15 的 2330 节点、2103 PASS/227 FAIL 不被重写或混入新命中 | `results/lsq-progress-regression-15/final-evidence-matrix-v1.json`、`gap-closure-summary-v1.json` |

## 独立 baseline/after-02 的结果

每行是一个独立 DUT 的实验，**不可跨行相加分母**。以下均排除 Picker wrapper。

| DUT | PASS 前→后 | 原始 line 点前→后 | toggle 前→后 | branch 前→后 | LCOV 原始源码闭包行前→后 |
|---|---:|---:|---:|---:|---:|
| ForwardModule | 19→20 | 2→2 / 2 | 3933→31767 / 40034 | 45→48 / 54 | 250→250 / 253 |
| PhysicalStoreQueue | 5→6 | 144→144 / 213 | 59276→77450 / 86318 | 1543→1544 / 1834 | 5438→5447 / 5817 |
| StoreQueue | 11→12 | 146→151 / 223 | 63832→86189 / 102374 | 1931→1934 / 2198 | 8558→8574 / 8968 |

正式目录：

- `results/forward-payload-pool-baseline-02/` → `results/forward-payload-pool-after-02/`
- `results/psq-payload-pool-baseline-02/` → `results/psq-payload-pool-after-02/`
- `results/sq-payload-pool-baseline-02/` → `results/sq-payload-pool-after-02/`

每个父级的 **16384/16384** 数据位方向点对应真实持久寄存器，不是叶子代替父级。
Forward 的同样 16384 点是公开 Store bank 输入，**不称为内部持久存储**。
每层 768 个 S2 响应属于 load 查询 UID；父级的 256 个 Store UID 另计，不混为同一数量。

`*-probe-01` 的三节点探测先检查两代高/低值；审阅发现其不能区分同代串槽，
因此先修订合同，正式增加逐槽图样与互补图样，`*-probe-02` 验证四代。
初次 baseline/after-01 用过等价的 actor 可选载荷参数；随后移除本轮对通用
actor 的这些改动，改为仅定制尚未发行的外部 producer record，并重跑 -02。
这样既不改参考模型/通用 actor，也保持历史失败栈位置。所有初次结果保留，
它们不替代正式 -02，也不混用不同 source aggregate。

## 真实完整目录重跑，不是覆盖率 OR/合并

命令保存在 `results/store-payload-failure-retention-01/command.json`：

```sh
python3 -B tools/run_summary.py --name store-payload-failure-retention-01 --workers 6 -- tests/forward tests/psq tests/store_queue
```

结果 **332 节点，268 PASS / 64 FAIL，0 ERROR / 0 SKIP**。原 329 节点的结果及
失败全文只归一化 Python 对象进程地址后逐节点相等；没有把 assertion 实际值、
数据或栈行号抹掉。64 个旧 FAIL 的整体摘要在前后均为
`f1bcc634065d52395dcaa99a64047886c8aa4113e800c9bdb347fa57413ab92d`。

下表是该**实际重跑**与 regression15 对应 native build 的比较，点全集相等，
旧命中无丢失；不是把定向 dat 合并进历史运行。

| DUT | toggle 原→新 / 同一分母 | 新命中 | 剩余 toggle | branch 原→新 / 同一分母 |
|---|---:|---:|---:|---:|
| ForwardModule | 28717→36329 / 40034 | 7612 | 3705 | 54→54 / 54 |
| PhysicalStoreQueue | 70532→81791 / 86318 | 11259 | 4527 | 1826→1826 / 1834 |
| StoreQueue | 78334→92232 / 102374 | 13898 | 10142 | 2183→2183 / 2198 |

三层原始 line 点均保持全中（分别 2/2、213/213、223/223）；LCOV 原始源码
闭包行保持 253/253、5817/5817、8968/8968。定向 baseline 的 branch 小幅增益
没有关闭 regression15 的 branch 缺口，统一 563 个原缺口不扣减。

## 修正最终矩阵的统计域

旧矩阵的 toggle hit/total 来自含 Picker wrapper 的原始分析器摘要，但 missing
来自非 wrapper 分类。例如 Forward 曾写为 51384/72604、missing=11317，
三者不闭合。原始数据本身未变。

`coverage-scope-audit-v1.json` 从 38 个真实 dat 重新验证：

- `raw_all = picker_wrapper + original_nonwrapper`，每域 hit+missing=total；
- 非 wrapper 源文件逐项匹配固定 RTL 闭包 SHA；
- raw_all 与锁定 Verilator 5.052 分析器相等；
- 非 wrapper 缺口数与原分类逐 DUT 一致。

最终矩阵改用同域的非 wrapper 统计；Forward 的统一历史值因此为
28717/40034、missing=11317。**这是报告口径修正，不是激励增益或缩小目标。**
旧矩阵原始字节已按 SHA 保留在 `audit-history/`。

## 初始化 branch 的具体证据，不是动态闭环

在完整固定 RTL 上逐点复核，137 个未命中点位于明确的生成初始化进程中。
例如 `DeqModule.sv:463` 处于 initial 449..470，
`EnterSbufferQueue.sv:248` 处于 initial 207..260，
`PhysicalStoreQueueDut.v:14247` 处于 initial 12535..14930；均受
`ENABLE_INITIAL_REG_` 包围。专项报告对每个点保留源 SHA、准确范围、层次、
点描述及 dat SHA，不以单行含 `reset` 这一关键词作结论。

Verilog initial 仅在启动执行一次，后续时钟事务/reset 不能重新进入；改变
time-zero 启动值可能命中另一臂，但不等于动态 LSQ 功能验证，也不代表该臂
在所有初始化配置下不可达。137 点仍未命中、仍在各自 native 分母内。

原分类报告已按原字节 SHA `44a6d3022f7be8ee4a708bfa350caeee3738127a639feed8c22a2d35474ed53d`
归档。原来 556 个“既有功能缺情形”中 130 个经具体作用域证据改为初始化边界；
现在为 **426 个既有功能缺情形 + 137 个工具/初始化边界 = 563 个未命中点**。
每个 DUT 的 build ID、dat SHA、missing 点全集摘要及数量均与旧版相等。

## 审计命令与剩余工作

```sh
python3 -B tools/audit_store_payload_pool_v1.py
python3 -B tools/audit_initial_branch_boundaries_v1.py lsq-progress-regression-15
python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15
```

最终全链 exit 0；日志为
`results/lsq-progress-regression-15/post-regression-store-payload-01.log`。
再次完整执行全链也为 exit 0，六份关键派生报告的 SHA 完全不变，未新增
重复归档；日志为 `post-regression-store-payload-idempotence-01.log`。
这是证据审计通过，**不是 64/227 个功能 FAIL 变成 PASS**。
所有运行启动/结束 source aggregate 相等，无逐拍 JSON、波形或完整源码副本。
摘要不代表当前工作区与所有历史源集合永远相同，也没有执行或宣称 Git 提交。

统一 regression15 仍保留 235610 个非 wrapper toggle 缺口及 20 条 line 边界，
本轮目录结果不回填其分子。后续优先补真实 PSQ/SQ strict 等待/身份/生命周期
的动态分支情形，以及尚未触达的地址低位、特殊总线、取消和异常组合；
Wrapper 的 Store/Load 混合域及其他 DUT 可达缺口仍属于完整目标。
