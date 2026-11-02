# 协作开发与目录约定

本仓库欢迎人工或 AI 辅助贡献；**两者使用同一套目录、接口和验收规则**。
开始前读取 [AGENTS.md](AGENTS.md)、[当前状态](docs/status.md) 和
[项目工作流](skills/ucv4xs-workflow/SKILL.md)。阶段交接见
[2026-11-02 协作检查点](docs/collaboration-checkpoint-20261102.md)。

## 目录是固定边界，不是每位贡献者各建一套

| 内容 | 放置位置 | 不要放在 |
|---|---|---|
| 公共命令、路径解析、构建与报告 | `src/ucv/` | 工程领域包、测试场景 |
| 一个验证工程 | `suites/<group>/<suite>/` | 新的顶层工程、`*verify/` 外壳 |
| 单 DUT 的事务、端口、驱动、采样、模型、检查器 | 工程中的 `<dut>/` | 根 `tests/`、泛化 `common/` |
| 跨 DUT 的真正共享机制 | 工程的 `runtime/`、`drivers/`、`monitors/` 等职责目录 | 任意工具箱或复制的框架实现 |
| 功能场景 | 工程的 `tests/<dut>/`，延续该工程已有子目录 | 实现包、根 `tests/` |
| 编码、绑定、checker、生命周期负对照 | 工程已有 `bundle/`、`scoreboard/`、`checkers/`、`framework/` 等自检目录 | 冒充硬件功能点 |
| 工程合同、缺陷、经验 | 工程 `docs/` | 大量运行产物 |
| 公共层与审计工具自检 | 根 `tests/` | 工程功能用例 |
| 基线、工具锁和补丁 | `baselines/`、`dependencies/` | 单 DUT 私有源码 override |
| 完整运行结果、波形、生成 RTL、native 库 | 忽略的 `results/`、`.cache/` 等本地产物目录 | Git 源文件 |
| 简短交接、来源与哈希索引 | `docs/history/` | 内部源码或大结果拷贝 |

现有工程键和目录保持一致：

```text
suites/
├── frontend/{bpu,icache,ftq,ifu}/
├── memblock/{lsq,dcache,mmu,sbuffer,lsu}/
└── vector/vagq/
```

工程根本身就是 Python 包。例如：

```python
from suites.frontend.icache.databank.agent.main import DataBankAgent
from suites.memblock.sbuffer.sbuffer.env import SbufferEnv
```

不要添加 `import common`、`import databank` 等顶级短导入，不新建 `xxxverify`、
`verify/common` 或第二套 DUT owner。资源根从工程包的 `ROOT` 或 `ucv.runtime` 获取，
不要按个人工作区路径或 `parents[n]` 猜位置。

## DUT 内部沿用现有布局

**同一工程、同一 DUT 优先延续周围命名，不为整齐批量搬目录。** 小模块可以用
`agent.py / ports.py / driver.py / monitor.py / model.py / types.py`；较大模块沿用
`agent/main.py / bundle/ports.py / driver/ / monitor/ / model/ / checker/ / transaction/types.py`。
不要为同一职责同时增加两份入口，也不要为了符合示意图创建空角色目录。

- 端口物理名只在 ports/bundle 适配层；功能场景调用有类型的事务 API。
- fixture 在工程 `tests/conftest.py` 集中注册；不在 DUT 子目录复制 `conftest.py`。
- 复用锁定 Toffee 的 Driver、SamplingMonitor、Agent、Scoreboard；确需领域适配时在
  工程文档说明框架缺口和行为差异，不另造通用调度或传输框架。
- 原有单 DUT 测试若有 `testcase/`，新增场景继续放在那里；原来是平铺则继续平铺。
- 新测试文件尽量带 DUT 前缀，例如 `test_metabank_transaction_contract.py`，避免同一
  pytest 根下裸模块重名造成 import mismatch。不要为解决重名全局改变旧收集方式。
- 自检必须真实检查环境错误，保持 `selftest` 分类；不能通过搬目录或改标记隐藏功能耦合。

更完整的分层依据见 [driver/monitor 分层方法](skills/execution/package-layout.md)。

## 分工和合并

1. 从同一个已发布 **Git commit/tag** 开始，各用独立分支或 worktree。
2. 在任务或 PR 中声明负责的工程/DUT及要改的共享文件；同一共享 `runtime/`、
   `tests/conftest.py`、工程配置或依赖锁不要由多个贡献者同时重构。
3. 以一个 DUT 或一条明确调用链提交，不顺带改别的工程目录、基线或公共框架。
4. 功能修改保留原 nodeid、合法激励、随机种子及真实非 PASS；新增控制另列。
   必须改变历史场景时说明合同依据和逐项差分。
5. 合并时带上真实检查结果、适用源码/RTL基线、待办和证据边界；不只给“全部通过”。
   本机 `results/` 不随 Git 发布，必要日志/收据按维护约定单独留存。

**协作检查点不是事务适配完工或硬件全绿发布。** 接手人可以从未完成项继续工作，
不要继承旧文档中超过其证据范围的完成结论。

## 最小检查集

在仓库根执行：

```sh
python3.12 scripts/audit-assets.py
.venv/bin/python scripts/audit-suite-layout.py --strict
.venv/bin/python scripts/audit-skills.py --strict --check-framework
.venv/bin/python -m pytest -q tests
```

工程代码变更再执行相关用例；输出目录每次取新名字，例如：

```sh
.venv/bin/ucv run icache --workers 1 --seed 1 --require-unified-baseline \
  --output results/icache-my-change-seed1 -- tests/metabank
```

另外报告事务边界债务，**不要为发布改成全绿**：

```sh
.venv/bin/python scripts/audit-suite-layout.py --strict --require-transaction-boundary
```

这条目前有真实未迁移项，非零退出码要保留。`--strict` 结构接线通过，不代表事务、
独立 oracle、DUT 功能或覆盖闭环通过。internal VAGQ 的运行还需要独立外部接入；
不要把 internal 源码或包含它的证据提交到公共仓库。

## 给 AI 的任务说明模板

```text
先读 AGENTS.md、CONTRIBUTING.md、docs/status.md 和项目工作流 Skill。
本次只负责 suites/<group>/<suite>/<dut>/ 及对应测试/合同文档。
保持现有工程根命名空间、目录和 fixture 注册方式，不新增 common/*verify 外壳。
先查真实合同与锁定 Toffee 能力，再修改事务/驱动/采样/checker。
保留原功能用例和真实非 PASS；关键修复提供合法控制与区分性错误控制。
若要改共享 runtime、工程配置或依赖，先说明影响和协调范围。
交付：变更文件、合同依据、实际命令与结果、原项差分、尚未验证的范围。
不要擅自发布、推送或把本次局部完成写成整个工程/仓库完成。
```
