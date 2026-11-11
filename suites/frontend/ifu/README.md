# IFU 验证工程

基于 Picker 与 toffee 的 IFU 单元验证：七个 DUT，按真实层次自底向上组织。

## 当前结论

**2026-11-08 收口（`public-a0c2a26cb` / DefaultConfig，硬件未签核）**：只做验证侧
工作（未改 RTL/Scala/生成物）。完整 seed 1 为
**939 PASS / 6 FAIL / 0 UNCERTAIN**（945 nodeid，
`results/ifu-a0c2a26cb-carry-sweep-seed1-20261108`）；同源码 seed 2 定向为
**350 PASS / 4 FAIL / 0 UNCERTAIN**（`results/ifu-a0c2a26cb-carry-sweep-seed2-20261108`）。
相对 2026-11-07 的 727 nodeid **无删除**；carry 扫掠扩为 217 条（16 个奇数位置 ×
7 类 × 2 种前导形状，覆盖写 bank lane 0..3，全 PASS），新增 1 条 GE 常驻反例、
1 条 UNCERTAIN→PASS。**R-09 已关闭**（有证据，不是无证据删除）；**R-13、R-14 仍
开放阻塞**，6 条 FAIL 全部归因为真实 RTL，未改期望、未登记 XFAIL。

6 条硬件 FAIL 的逐条归因、根因行号和上游只读检索记录见
[退出标准](docs/spec/verification/exit-criteria.md) §3、
[R-13 缺陷](docs/bugs/open/frontend-trigger-tdata2-width.md)与
[R-14 缺陷](docs/bugs/open/instr-boundary-carry-ftq-owner.md)。上游检索范围：本地
镜像 `origin/kunminghu-v3` = `2145ba1c9`（基线后 10 个提交），未发现 R-13/R-14 修复；
未访问网络、未提交 issue/PR。R-13 的两个候选修复方向只记录未实施。

**本节不表示硬件通过**；R-13/R-14 修复前不得写成完整验收。

**2026-11-07 新基线适配（`public-a0c2a26cb`）**：七个 DUT 已按统一基线重新
prepare/build，**7/7 `BUILT + SMOKE PASS`**；当时完整 seed 1 为
**721 PASS / 5 FAIL / 1 UNCERTAIN**（727 nodeid），同源码 seed 2 定向为
**132 PASS / 3 FAIL / 1 UNCERTAIN**（136 nodeid），两轮同 nodeid 判定一致。
非 PASS 原样保留：R-13 两条 FAIL、R-14 三条 FAIL、R-09 一条 UNCERTAIN（后于
2026-11-08 关闭）。本基线包含上游 `b716aade`，`toFtq.wbRedirect.pc` 由 50 位加宽为
51 位 `GuardedPc`；`IFU-ENV-005` 已改为正向对照并关闭。完整逐 nodeid 差分、构建身份
与覆盖表见[机器记录](../../../docs/history/ifu-baseline-a0c2a26cb-20261107.json)、
[上游复核](docs/spec/verification/evidence/upstream-review-20261029.md)与
[覆盖率摘要](docs/spec/verification/coverage/coverage-summary.md)。本节只覆盖
IFU / DefaultConfig / `public-a0c2a26cb`。

**历史：事务适配已移交（2026-11-01，`public-893e1580b`）**：七个 DUT 已完成当前框架
事务边界；Ifu 顶层全部 49 个旧功能体及两个 guard 已接入同一事务链。最终语义审计补齐
raw 字节/派生描述绑定、13 个性能事件的两级延迟比较及生命周期控制；独立 oracle、
两阶段/组合采样、严格合法域、根 fixture 和正反对照见
[事务适配状态](docs/spec/verification/transaction-adapters.md)。当时完整回归为
719 PASS / 5 FAIL / 1 UNCERTAIN；真实 seed2 顶层定向为 278 PASS / 1 FAIL /
1 UNCERTAIN。R-13、R-14 均开放，不删除反例或扩大 XFAIL。

**2026-10-30 历史判定**：144 PASS / 2 FAIL / 1 UNCERTAIN。`IFU-TR-002` 保留两条
真实 FAIL；失败不登记 XFAIL。当时 Toffee 原生状态、退出码及同轮证据见
[UNCERTAIN 迁移核验](docs/spec/verification/evidence/uncertain-migration-20261030.md)。
旧运行 `results/20261030T022604Z-107cb685` 的 1 INCOMPLETE 保留为历史。

## 层次与验证顺序

| 层 | DUT | top | 功能点前缀 |
|---|---|---|---|
| 1 | `rvc_expander` | `RvcExpander` | `IFU-RVC-*` |
| 1 | `instr_boundary` | `InstrBoundary` | `IFU-IB-*` |
| 1 | `pred_checker` | `PredChecker` | `IFU-PC-*` |
| 1 | `uncache_unit` | `IfuUncacheUnit` | `IFU-UC-*` |
| 1 | `frontend_trigger` | `FrontendTrigger` | `IFU-TR-*` |
| 1 | `perf_analysis` | `IfuPerfAnalysis` | `IFU-PA-*` |
| 2 | `ifu` | `Ifu` | `IFU-TOP-*` |

顶层 `Ifu` 的指令流语义由 RVC 展开、指令边界、预测检查三层共同定义；`IfuUncacheUnit`、
`FrontendTrigger`、`IfuPerfAnalysis` 是并列旁路子模块，单独验证后在顶层复核对外可
观察行为。

## 文档入口

- [文档总览](docs/README.md)
- [设计规格](docs/spec/design/README.md)、[功能点](docs/spec/design/functional-points.md)、
  [行为矩阵](docs/spec/design/behavior-matrix.md)
- [验证规格](docs/spec/verification/README.md)、[事务适配](docs/spec/verification/transaction-adapters.md)、
  [观察覆盖](docs/spec/verification/observation-coverage.md)
- [覆盖闭环](docs/spec/verification/coverage/coverage-loop.md)、
  [覆盖摘要](docs/spec/verification/coverage/coverage-summary.md)
- [退出标准与残余](docs/spec/verification/exit-criteria.md)
- [问题索引](docs/bugs/README.md)

工程根的 `verification_plan.json` 已删除；功能点、合同和未证明范围从上述规格进入，
真实缺陷维护在问题记录中。历史报告中的计划统计与残余门禁仅描述当时运行。

## 目录

- `testbenches/<dut>/model/`：各 DUT 的独立参考模型。`testbenches/ifu/model/` 的
  `isa.py`/`cenc.py` 是架构级指令编码器，`fetch.py` 把取指窗口组装为 IBuffer 写入拍，
  `fetch_events.py` 分类性能事件；`testbenches/rvc_expander/model/rvc.py` 按 RISC-V
  压缩指令规范定义展开与合法性；`testbenches/instr_boundary/model/boundary.py` 定义
  取指窗口的指令格点；`testbenches/pred_checker/model/pred_checker.py` 定义预测合同；
  `testbenches/uncache_unit/model/uncache.py` 定义非缓存访问状态机；
  `testbenches/frontend_trigger/model/trigger.py` 定义 Sdtrig 匹配/链/动作优先级；
  `testbenches/perf_analysis/model/perf.py` 定义 top-down 理由流水。
- `testbenches/shared/env/`：Picker DUT 装载与时钟/复位约定（`harness.py`）、异步 fixture
  生命周期桥（`agent_runtime.py`）、显式槽 Driver（`driver/`）、工程 feature 报告插件
  （`pytest_plugins/features.py`）。旧 `case_loader.py` 无活动消费者，已从运行包移除；
  原文与哈希保留在本机 `results/testbenches-all-20261110/before/` 及源码快照清单。
- `testbenches/<dut>/`：DUT 专属 agent/ports/checker 与协议账本。
  `testbenches/ifu/` 是顶层缓存/uncache 事务链，80 输入/405 输出严格绑定、
  UID/阶段/peer 关联、持续双阶段采样与有界收尾。
- `testbenches/ifu/env/legacy_pins.py`：临时物理名兼容字段，仍计事务边界技术债，
  不是新的事务 API。
- `testbenches/<dut>/tests/`：按功能点组织的用例与 DUT 专属 fixture；
  `testbenches/ifu/tests/` 覆盖顶层组合。

## 运行

```sh
.venv/bin/ucv prepare ifu --require-unified-baseline --jobs 8
.venv/bin/ucv build ifu --require-unified-baseline --jobs 8
.venv/bin/ucv run ifu --workers 16 --seed 1 --require-unified-baseline \
  --output results/ifu-full-seed1
.venv/bin/python -m pytest -q suites/frontend/ifu/testbenches   # 直接调试，不替代受管运行凭据
```

从仓库根目录运行。RTL、原生包和运行结果不进入 Git；`ucv.json` 声明真实 top 与
Python 导出名，基线从根 `public-a0c2a26cb` 继承，所有 DUT 来自同一份完整
DefaultConfig 香山 RTL 的实例闭包。

当前使用仓库锁定的 `uc-toffee==2.1.0` 和 `.venv/`，UNCERTAIN 是框架原生能力。
2026-10-30 历史运行使用独立本地开发版，其环境身份与源码收据保持历史含义，见
[本地环境配置](../../../docs/local-configuration.md#本地-toffee-开发环境)。

## 约定

- 用例只覆盖功能点的一部分时，用
  `@pytest.mark.uncertain(reason="...", reference="R-xx")` 显式声明；正常执行并完成
  已有检查后显示 `U` / `UNCERTAIN`，不计 PASS。真实 FAIL/ERROR 仍优先。
- 功能用例与所属规格的 `IFU-*` 标识保持可追溯；`IFU-ENV-*` 是验证环境点，
  不作为硬件行为通过证据。
- 参考模型只依据架构/规范表达意图，不复制 RTL 赋值；生产者宽度优先，不把本层端口
  宽度当合同。复位、输入写入与采样由 `testbenches/shared/env/harness.py` 统一约定。
- 顶层覆盖不足时，先按“已有功能点的情况枚举，还是整体功能点缺失”归类，再补功能点或
  情况，重新运行并在[覆盖闭环](docs/spec/verification/coverage/coverage-loop.md)记录。
