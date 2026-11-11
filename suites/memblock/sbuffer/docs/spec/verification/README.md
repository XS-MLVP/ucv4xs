# Sbuffer Verification spec

状态：**现有验证资产的统一入口，完整性待审查**。设计要求见 [Design spec](../design/README.md)。

最近统一入口记录绑定 `public-893e1580b` / DefaultConfig、`results/ucv-sbuffer-20261031`
（31 PASS）；2026-11-01 事务修复检查点另记录同源码 seed1/2 各 66 PASS。当前根默认基线
为 `public-a0c2a26cb`，本工程尚未在该基线重新构建或回归；本页不把旧 PASS 推到当前版本。

## 1. 验证范围与假设

- 验证两个实际 DUT：独立 `SbufferData` 和顶层 `Sbuffer`（内部保留真实 SbufferData）。
- 子块 UT 关注字节级存储/掩码语义和固定两拍延迟；顶层 UT 关注握手、状态机、排空和
  跨模块交互。顶层通过不代表 SQ、LSQ、DCache 或 MemBlock 通过。
- 激励只使用公开端口；不启用 VPI/internal-cfg，不保存逐周期 dump 或波形。
- 独立期望来自按行/lane/字节的模型、RISC-V CMO 规范、上游合同和 DCache 写回契约；
  未初始化字节不比较，只比较模型标记为已知的字节。
- 真实 FAIL/ERROR/XFAIL/SKIP 保留原判定；自检不计入硬件功能覆盖。

## 2. 功能项、场景与实现关联

| DUT | 测试入口 | 模型/检查器 | 功能点 | 主要证据 |
|---|---|---|---|---|
| SbufferData | [tests/sbuffer_data](../../../testbenches/sbuffer_data/tests) | `testbenches/sbuffer_data/model.py`、`env/ports.py`、`transactions.py`、`coverage.py` | [SBD-WRITE/FLUSH/RESET/STABLE](../design/functional-points-sbuffer-data.md) | [SbufferData 报告](evidence/sbuffer-data-20261024.md) |
| Sbuffer | [tests/sbuffer](../../../testbenches/sbuffer/tests) | `testbenches/sbuffer/model.py`、`env/driver.py`、`checker.py`、`coverage.py` | [SBT-ENQ/WRITE/FLUSH/FWD/RESET](../design/functional-points-sbuffer.md) | [顶层报告](evidence/sbuffer-top-20261024.md) |

覆盖组在对应 DUT 的 `coverage.py` 中实例化：SbufferData 为
`sbuffer_data.write/flush/reset/idle`；Sbuffer 为
`sbuffer.enq/capacity/sameblock/writeout/replay/flush/forward/reset`。功能点只在行为
比较成功后采样，未命中 bin 不因未覆盖而删除。

事务边界、accepted-edge、model-owned UID/尝试和响应/重试检查见
[Sbuffer 事务修复记录](../../../../../../docs/lessons/transaction-boundary-repair-20261101.md)；
该记录描述的修改不改变历史硬件判定。flush/empty 的独立依据见
[flush/empty 合同复核](evidence/flush-contract-review-20261024.md)。

## 3. 运行、覆盖与判定

### 3.1 历史分层结果（2026-10-24）

| 范围 | 运行 | 用例 | 功能覆盖 | DUT 行覆盖 | toggle | branch |
|---|---|---|---:|---:|---:|---:|
| SbufferData | `sbuffer-data-initial-04` | 15 PASS | 4 组 100% | 8518/8518 = 100% | 100% | 2115/2116 |
| Sbuffer 顶层 | `sbuffer-top-contract-03` | 16 PASS | 8 组 100% | 12648/13191 = 95.88% | 82.0% | 2690/2724 = 98.8% |

顶层剩余覆盖缺口位于 `waitInflightMask` 高槽同块写入（31 行）和 SbufferData 高槽 lane
的另一半字节端口路径（512 行），属于已有功能点 `SBT-ENQ-01/04`、`SBT-WRITE-01` 的
情形缺失，不是新的功能点。详见 [覆盖率闭环](evidence/coverage-loop-20261024.md)。

### 3.2 统一入口与事务修复检查点

- `results/ucv-sbuffer-20261031`：31 PASS，manifest `committed`、
  `coverage_complete=true`，5 个原生覆盖率产物，`ucv report` 无产物缺口。
- 2026-11-01 检查点：保持原四笔入队/响应，新增无额外请求尾部检查；同源码 seed1/2
  各 66 PASS。该数字属于事务修复范围，不替换 2026-10-24 的历史计数，也不表示新默认
  基线已复验。
- 以上记录都绑定各自源码/RTL/构建/seed；当前默认基线未重新运行。

## 4. 当前未关闭项与完成条件

范围、资源和合法输入域约束（含稳定 ID）见 [constraints.md](constraints.md)，
包括 wline 零 payload、无 VPI/internal-cfg 和无逐周期 dump；它们不是当前缺陷，也不是
设计退役。

- [SBT-SAMEBLOCK-SLOT-SWEEP](../../bugs/open/SBT-SAMEBLOCK-SLOT-SWEEP.md)：同块 inflight
  高槽写路径未全部激活，属于已有功能点的情形缺失。
- [SBD-SAME-LANE-PORT-HALVES](../../bugs/open/SBD-SAME-LANE-PORT-HALVES.md)：高槽同一
  lane 的另一半字节端口路径未覆盖。
- [SBT-TOGGLE-RESIDUAL](../../bugs/open/SBT-TOGGLE-RESIDUAL.md)：顶层 toggle 82.0%，剩余
  集中在高槽存储输出、行状态位和内部写流水。
- [SBD-TIME0-INIT](../../bugs/open/SBD-TIME0-INIT.md)：工具边界，`initial` 的
  `if(reset)` 另一分支不可由运行期激励到达。
- 历史误报分类：flush 两级空语义只在 `public-893e1580b` 判为非缺陷，当前默认基线未
  复验，见 [FLUSH-EMPTY-TWO-LEVELS-REVIEWED](../../bugs/closed/FLUSH-EMPTY-TWO-LEVELS-REVIEWED.md)。
- 范围/资源约束：wline 零 payload、无 VPI/internal-cfg、无逐周期 dump 见
  [constraints.md](constraints.md)。Picker 默认 dump 在旧基线已修复验证，但当前基线
  未复验，见 [PICKER-DEFAULT-DUMPFILE](../../bugs/open/PICKER-DEFAULT-DUMPFILE.md)。
- 完成条件：当前基线的构建/冒烟/功能运行和产物完整性可核验；功能点情形和 toggle
  缺口有归因或补例；flush/empty 合同和 wline 合法域有独立依据；未验证范围明确，
  不以修改期望、增加豁免或删除反例取得全绿。

## 5. 证据索引

重要历史运行材料保存在 [evidence/](evidence/README.md)，包括两个 DUT 报告、覆盖率
闭环、flush 合同复核、独立审计、二次裁决和旧版说明；文件保留原日期、基线和结论边界。
运行产物本身仍在被忽略的 `results/`，本次文档整理没有重新执行仿真。
