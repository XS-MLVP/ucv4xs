# IFU 验证工程

基于 Picker 与 toffee 的 IFU 单元验证：七个 DUT，按实际层次自底向上组织。

**当前判定**（`results/20261030T-uncertain-uc-toffee`）：144 PASS / 2 FAIL / 1 UNCERTAIN。
硬件功能点 53/55 PASS + 1 FAIL + 1 UNCERTAIN —— `IFU-TR-002` 保留两条真实 FAIL：`FrontendTrigger` 只比较
`tdata2[49:0]`，而 CSR 把 `tdata2` 暴露为 `RW(63,0)`；`tdata2 ≥ 2^50` 时 EQ/GE
会在真实 PC 上误命中、LT 全不命中。失败不登记 XFAIL，复现与根因见
[docs/bugs/frontend-trigger-tdata2-width.md](docs/bugs/frontend-trigger-tdata2-width.md)，
修复方向与残余 R-13 见 [docs/exit-criteria.md](docs/exit-criteria.md)。验证环境功能点 5/5 通过。
本轮 Toffee 原生状态、退出码及同轮证据见
[UNCERTAIN 迁移核验](docs/uncertain-migration-20261030.md)；旧运行
`results/20261030T022604Z-107cb685` 的 1 INCOMPLETE 保留为历史，不改写旧收据。

```sh
.venv/bin/ucv build ifu --jobs 8
.venv/bin/ucv run ifu --workers 1
.venv-uc-toffee/bin/python -m pytest -q suites/frontend/ifu/tests   # 本地开发环境直接调试
```

从仓库根目录运行。RTL、原生包和运行结果不进入 Git；`ucv.json` 声明真实 top 与
Python 导出名，基线从根 `public-893e1580b` 继承，所有 DUT 来自同一份完整
DefaultConfig 香山 RTL 的实例闭包。

UNCERTAIN 能力目前来自本地 `uc-toffee` 开发版。`ucv run` 通过
`.ucv/local.json` 选择 `.venv-uc-toffee`，旧 `.venv` 和已构建 DUT 不替换；安装身份和
源码哈希单独进入运行凭据，见[本地环境配置](../../../docs/local-configuration.md#本地-toffee-开发环境)。

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

自底向上的理由：顶层 `Ifu` 的指令流语义由 RVC 展开、指令边界、预测检查三层共同
定义，先逐层固定合同，再在顶层组合验证；`IfuUncacheUnit`、`FrontendTrigger`、
`IfuPerfAnalysis` 是并列的旁路子模块，单独验证后在顶层复核其对外可观察行为。

## 目录

- `model/`：独立参考模型，导入前缀为 suites.frontend.ifu。`isa.py`/`cenc.py` 是架构级指令编码器，
  `rvc.py` 按 RISC-V 压缩指令规范定义展开与合法性，`boundary.py` 定义取指窗口的
  指令格点，`pred_checker.py` 定义预测合同，`uncache.py` 定义非缓存访问状态机，
  `trigger.py` 定义 Sdtrig 匹配/链/动作优先级，`perf.py` 定义 top-down 理由流水，
  `fetch.py` 把取指窗口组装为 IBuffer 写入拍并复用上述模型。
- `harness.py`：Picker DUT 装载与时钟/复位约定；fixtures.py 提供根 fixture 工厂。
- `legacy_pins.py`：临时物理名兼容字段，仍计事务边界技术债，不是新的事务 API。
- `pytest_plugin.py`：把 `@pytest.mark.feature` 汇总为功能点报告。
- `tests/<dut>/`：按功能点组织的用例；`tests/ifu/` 覆盖顶层组合。
- `tools/coverage_report.py`：从 toffee 运行清单读取原生 `v_line`/`v_branch`/
  `v_toggle`，逐 DUT 输出行/分支/toggle 覆盖与未覆盖明细。
- `docs/functional-points.md`：60 个功能点（硬件 55 + 验证环境 5）的语义定义、期望
  来源、DUT 合同字段与责任边界。
- `docs/behavior-matrix.md`：按模块的行为等价类与关键组合，说明哪些样本可合并、
  哪些必须拆开、正确/错误如何区分，以及未展开空间的抽样与残余。
- `docs/observation-coverage.md`：需求→驱动→观测→比较器→nodeid 对账，显式列出
  不比较字段及原因；完成性账本、采样约定与字段缺口残余。
- `docs/coverage-loop.md`：逐模块/顶层的“定义—用例—运行—缺口—补点—重跑”记录。
- `docs/coverage-summary.md`：该次运行的行/分支/toggle 命中与全部未覆盖项摘要（完整
  原生表在忽略目录 `results/`，摘要里记录源报告 sha256）。
- `docs/upstream-review-20261029.md`：基线之后上游 IFU 改动的有界复核；当前记录
  `b716aade` 的 guard-bit 修复不在本地，并以 `IFU-ENV-005` 探测该交接面限制。
- `docs/exit-criteria.md`：交付前逐项对账的退出合同——必验项、残余登记
  （R-01..R-13）、观察点精度扫描、允许的范围排除与结论边界。残余同时以机器可读
  形式存在于 `verification_plan.json` 的 `residuals`，插件校验结构、写入功能点报告，
  并在“有 blocking 残余却全 PASS”时报一致性错误；运行摘要 `summary.md` 会列出
  Residual register，只读摘要也能看到未证明范围。

`tools/coverage_report.py` 生成逐点报告与 markdown；`tools/coverage_summary.py`
从该报告生成上面这份可入库的小结。

## 约定

- 用例只覆盖功能点的一部分时，用
  `@pytest.mark.uncertain(reason="...", reference="R-xx")` 显式声明：正常执行并完成
  已有检查后，Toffee 原生显示 `U` / `UNCERTAIN`，不计为 PASS；真实 FAIL/ERROR 仍优先。
  框架只要求非空原因，IFU 另要求 `reference` 指向工程残余登记中未解决的条目。
  UNCERTAIN 本身不改变退出码，退出 0 不能替代验证结论；执行或产物未完成仍记
  INCOMPLETE。没有对应用例的未证明范围只登记残余，不进测试状态。
- 每个用例至少挂一个 `IFU-*` 功能点；未标注或引用未知 ID 会直接报错，防止
  “跑了但没验证点”。`IFU-ENV-*` 是验证环境点，报告按 `hardware`/`environment`
  分区，硬件通过率只统计 hardware。
- 参考模型只依据架构/规范表达意图，不复制 RTL 赋值；测试用独立编码器构造激励，
  因此模型与激励是两份独立描述。模型里出现 `& MASK` 时必须说明是规范约束还是抄了
  RTL：两边同时截断会让负对照一起失效（R-13 就是这样漏过第一轮的）。
- 生产者宽度优先：CSR/上游能写出的最宽值参与需求，不把本层端口宽度当合同；按
  [观察点精度](../../../skills/design/observation-precision.md) 扫描“内部宽/端口窄”。
- 复位、输入写入与采样由 `harness.py` 统一约定；`+verilator+rand+reset+0`
  关闭时零随机化，避免复位后首个有效周期的寄存器随机值混入判定。
- 顶层覆盖不足时，先按“缺口属于已有功能点的情况枚举，还是整体功能点缺失”归类，
  再补功能点或情况，重新运行并在 `docs/coverage-loop.md` 记录。
