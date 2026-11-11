# LSU Verification Spec

状态：验证侧当前索引。历史结论绑定各自源码提交；当前基线的局部适配与实测见 §2.2，完整工程尚未验收。

## 1. 范围与基线

- 19 个独立 DUT：NewStoreUnit 族 9 个、NewLoadUnit 族 9 个、StdExeUnit 1 个。
- 历史证据绑定源码：`XiangShan kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e`；RTL 为该基线的 `soc-split` 原样副本，逐文件哈希见 [`manifest/lsu-rtl.sha256`](../../../manifest/lsu-rtl.sha256)。当前工程继承 `public-a0c2a26cb`；不要把本行的 `893e1580…` 当当前源码。当前两个 Load DUT 的重建/选跑见 §2.2，其余 DUT 不承接旧基线结果。
- 最近完整记录：2026-10-26 `upstream-review-regression-02`，589 项 **582 PASS / 7 FAIL / 0 SKIP / 0 ERROR**，19 份原生 coverage 数据库；交付门禁 **FAIL**。当前 `public-a0c2a26cb` 尚未完成 19 DUT 全量重建/回归。

## 2. DUT 与测试

| 族 | DUT key | 测试目录 |
|---|---|---|
| Store | `store_arbiter`、`store_trigger`、`store_delay`、`store_s0`…`store_s4`、`new_store_unit` | `testbenches/store_*/tests`、`testbenches/new_store_unit/tests` |
| Load | `load_arbiter`、`load_trigger`、`load_datapath`、`load_s0`…`load_s4`、`new_load_unit` | `testbenches/load_*/tests`、`testbenches/new_load_unit/tests` |
| StdExe | `std_exe_unit` | `testbenches/std_exe_unit/tests` |
| 独立复核 | 上游端口/性能/检查器灵敏度 | `testbenches/new_load_unit/tests/upstream_spec`、`testbenches/store_delay/tests/checkers`、`testbenches/new_load_unit/tests/test_recheck_coverage.py` |

### 2.1 当前运行入口

从仓库根使用统一 `ucv` 流程。下面给出 `store_arbiter` 示例，其他 18 个 DUT 替换 `--dut`；`workspace.json` 为 19 个 DUT 登记测试根：

```sh
./scripts/ucv prepare lsu --dut store_arbiter --rtl-source release
./scripts/ucv build lsu --dut store_arbiter --jobs 2
./scripts/ucv run lsu --dut store_arbiter --workers 1 --seed 1 --output results/lsu-store-arbiter-seed1
./scripts/ucv report results/lsu-store-arbiter-seed1
```

`ucv run` 生成 `run.json` 和问题快照；`ucv report` 读取这些统一收据。重复运行时把示例中的
`results/lsu-store-arbiter-seed1` 换成尚不存在的新目录。仿真环境准备见根
[工作空间指南](../../../../../../docs/how-to/workspace.md)和 [BPU 入门教程](../../../../../../docs/tutorials/bpu-first-ut.md)。
以上是运行入口示例；本轮实际执行范围见下节及其收据。

### 2.2 Load 事务适配接口（当前）

`new_load_unit` 与 `load_s4` 的功能用例使用事务和不可变观察快照，环境承担端口绑定、解码与逐引脚比较：

- `testbenches/new_load_unit/transactions.py`：`LoadIssue`（地址、操作、ROB/LQ/SQ 身份、寄存器写、预取标志）、`Translation`、`ReplayRequest`、`Redirect`、`NukeQuery`、`TriggerSettings` 等请求事务，以及 `Stage0Observation`…`Stage3Observation`、`PrefetchTrain`、`PerfCounters` 组成的 `LoadPipelineSnapshot`。replay 原因用 `ReplayCause`/`ReplayCauses` 表示，`LqWrite.replay_cause()` 按合同查 cause 0..6、8..11。
- `testbenches/new_load_unit/env/stimulus.py`：把 `CycleInput` 降到驱动编码；`testbenches/new_load_unit/env/monitor.py`：在时钟沿后采样公开输出并解码快照，同时核对 273 个输出引脚的完整清单。`env/__init__.py` 仍逐拍把全部父块输出与独立 S0..S3/data-path 模型比较，模型期望不来自引脚读回。
- `testbenches/load_s4/transactions.py`：`S4HeadPayload` 为 41 字段的不可变事务载荷，`S4Observation` 为观察快照；`env/passthrough.py` 的 `LoadS4Env.check()` 逐字段比较并返回快照。S4 没有状态，valid=0 时按合同不比较 payload 位。
- `TriggerSettings` 将四槽配置和 enable 复制为 tuple；槽使用冻结的 `TriggerSlot`，编码时才创建驱动兼容对象。默认设置为四槽 idle，`CycleInput.nuke` 同样复制容器；单比特字段、位宽、槽数和嵌套类型在构造时校验。调用方修改原容器不改变已构造的请求。
- 输入/监视器负对照在 `tests/checkers/`（`pytest.mark.selftest`）：越界身份、非法标志、缺端口、被篡改的 expected 必须失败；保留默认合法配置与不可变性对照，不计硬件功能 credit。

事务适配不改变原有 nodeid、随机序列和独立模型；`public-a0c2a26cb` 上这两个 DUT 的真实运行收据保存在
`results/transaction-adapters-20261110/lsu/`。历史基线结论仍以各自日期和 `893e1580…` 记录为准。
该选择保留 gpaddr 高位、fuOpType=1 写回、软件预取写回三项 FAIL，RTL 与参考模型的责任
尚待独立归因；不能将接口适配通过写成硬件通过。原随机用例属于既有端口压力，未因此
获得生产可达性证明。

### 2.3 历史工具与专用审计

历史结论和复现命令仍按原日期/基线保留在 [evidence/reports](evidence/reports) 与 [bugs/evidence](../../bugs/evidence/bug-reports-20261026)。以下旧工具只用于旧证据复现或专用审计，不作为当前构建/运行入口：

- `tools/prepare_rtl.py`：旧 RTL 提取入口；当前 RTL 提供方由 `ucv prepare` 管理。
- `tools/build_dut.py`：旧 Picker 直接导出 + 最小 smoke，写 `results/builds/<stamp>-<dut>/report.json`，不生成 `ucv` 构建缓存/收据；已存在的 DUT 目录会被拒绝覆盖。
- `tools/run.py`：旧 Toffee managed runner，保存 `console.log`、JUnit、`run-provenance.json` 和原生覆盖，不生成 `run.json`，也没有问题快照；`ucv report` 不能读取其输出作为统一运行收据。
- `tools/coverage_audit.py`、`tools/verify_delivery.py`：专用覆盖/交付审计，读取旧运行目录、`manifest/` 和逐 DUT gap 文件；它们是证据审计，不是功能验收，也不替代 `ucv check/run/report`。

这些工具及其历史命令绑定 2026-10-25/26 的旧基线 `893e1580…` 和旧运行目录；不要把结果混入当前 `public-a0c2a26cb` 的结论。

## 3. 覆盖与功能点

- 每个 DUT 保留行/toggle/branch 独立分母；映射和逐 DUT 缺口见 [gaps/](gaps) 与 [`manifest/coverage-summary.json`](../../../manifest/coverage-summary.json)。
- 2026-10-26 最终回归仍有 338 个未覆盖 toggle 点，分类为 perf 位宽/死事件、entrance 编码、tail 地址/mask、DCache 命令常量、LQ cause 7/12、训练标志、scalar accessType 等；其中包含已确认 `LSU-HWPF-MISS-001`，不能统一说成“结构不可达”或“无缺陷”。
- 21 组声明式 covergroup 报告的 100% 是 bin 采样覆盖，不是独立 reached/checked 双证据；不能覆盖真实性能 FAIL，也不能支持“所有功能点检查完毕”。
- 历史 17 次 FAIL 观测缺少原始 nodeid/traceback 和当时测试源码，不能逐节点归因，也不能统一判为验证误报。旧 `unified-regression-02` 的 518 PASS 是增强断言前的历史记录。

## 4. 当前问题

7 个已确认 RTL 根因均在 [bugs/open](../../bugs/open)；每条旧基线版本为 `open`，当前基线 `public-a0c2a26cb` 版本为 `unverified`（§2.2 的局部选跑未完成这七项问题的逐项归因复验，不能写成当前已复现）：

- `LSU-HWPF-MISS-001`：硬件预取 miss 性能事件恒 0。
- `LSU-STORE-TVAL-001`、`LSU-CBO-NC-AF-001`、`LSU-S3-KILL-WB-001`、`LSU-MATCHINV-CAUSE-001`、`LSU-PREFETCH-W-INTENT-001`：上游核查新增并本地动态复现（前 5 个）。
- `LSU-STD-PERF-001`：StdExe 性能计数器条件取反，仅源码契约证据。

7 个 FAIL 正好对应 7 个根因；同一根因的种子、lane 和父子层传播不重复计数。历史误报/漏报复核见 [03-false-negative-review.md](../../bugs/evidence/bug-reports-20261026/03-false-negative-review.md)、[04-coverage-and-evidence-review.md](../../bugs/evidence/bug-reports-20261026/04-coverage-and-evidence-review.md)。

## 5. 完成条件

一个 DUT 只有同时满足以下条件才可声明验收：

1. 19 份合同对应的行为、合法输入、取消/异常/reset 和观察点均有独立依据；
2. 真实失败保留，不能通过 xfail/skip/waiver 或同源预期消除；
3. 每个 DUT 的行/branch/toggle 分母和缺口逐项分类，不以声明式 bin 100% 代替 reached/checked；
4. 父块使用真实子模块，外部代理边界明确；
5. 当前基线重新构建、运行并保留源码/构建/RTL 哈希、种子和日志。

当前交付门禁 FAIL；不声称 LSU、MemBlock 或全核已验收。
