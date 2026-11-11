# 协作开发与目录约定

本仓库欢迎人工或 AI 辅助贡献；**两者使用同一套目录、接口和验收规则**。
开始前读取 [AGENTS.md](AGENTS.md)、[当前状态](docs/status.md) 和
[项目工作流](skills/ucv4xs-workflow/SKILL.md)。接续范围以当前状态及所属工程的问题记录为准。

## 目录是固定边界，不是每位贡献者各建一套

| 内容 | 放置位置 | 不要放在 |
|---|---|---|
| 公共命令、路径解析、构建与报告 | `src/ucv/` | 工程领域包、测试场景 |
| 一个验证工程 | `suites/<group>/<suite>/` | 新的顶层工程、`*verify/` 外壳 |
| 单 DUT 的实现、用例和自检 | 工程 `testbenches/<dut>/` | 工程根的领域代码或第二套 tests 树 |
| 真正跨 DUT 共享的组件 | `testbenches/shared/`，与 DUT 同用六职责 | 单 DUT 专用代码、任意工具箱或复制的框架实现 |
| 功能场景 | `testbenches/<dut>/tests/`；复用步骤放其 scenarios/ | 环境装配层、根 tests/ |
| 编码、绑定、checker、生命周期负对照 | 所属模块 `tests/` 内已有的 `bundle/`、`scoreboard/`、`checkers/`、`framework/` 等自检目录 | 冒充硬件功能点 |
| 设计/验证规格 | 工程 `docs/spec/{design,verification}/`，沿用功能点、合同与覆盖正文 | 使用教程或逐轮运行报告 |
| 工程问题 | 工程 `docs/bugs/{open,closed}/`，稳定 ID 的完整记录 | 按轮复制的问题清单 |
| 公共层与审计工具自检 | 根 `tests/` | 工程功能用例 |
| 基线、工具锁和补丁 | `baselines/`、`dependencies/` | 单 DUT 私有源码 override |
| 完整运行结果、波形、生成 RTL、native 库 | 忽略的 `results/`、`.cache/` 等本地产物目录 | Git 源文件 |
| 简短交接、来源与哈希索引 | `docs/history/` | 内部源码或大结果拷贝 |

上表实现路径采用十二工程统一的 schema2 布局；现有工程先查 `workspace.json`，
版本兼容与本轮迁移范围见[目录规范](docs/reference/module-layout.md#schema-版本与本轮范围)。

现有工程键和目录保持一致：

```text
suites/
├── frontend/{bpu,icache,ftq,ifu,ibuffer,instr_uncache}/
├── memblock/{lsq,dcache,mmu,sbuffer,lsu}/
└── vector/vagq/
```

工程根本身就是 Python 包。例如：

```python
from suites.frontend.icache.testbenches.databank.env.agent.main import DataBankAgent
from suites.memblock.sbuffer.testbenches.sbuffer.env import SbufferEnv
```

不要添加 `import common`、`import databank` 等顶级短导入，不新建 `xxxverify`、
`verify/common` 或第二套 DUT owner。资源根从工程包的 `ROOT` 或 `ucv.runtime` 获取，
不要按个人工作区路径或 `parents[n]` 猜位置。

## DUT 按验证对象集中组织

### Testbench 目录规范

**验证谁，实现和测试就归谁；规格与 Bug 集中放工程 docs。** BPU 顶层自身的模型和
集成测试归 `testbenches/bpu/`，MainBTB 的实现和测试归 `testbenches/mbtb/`。
完整规则及 BPU 示例见[工程与 testbench 目录规范](docs/reference/module-layout.md)。
工程根、testbench 根与集中资料层级使用封闭白名单；未列出的目录即使为空、仅有缓存或被
Git 忽略也会失败，符号链接不能绕过。`ucv check`、布局审计和资产审计共用同一门禁。

```text
<suite>/
├── testbenches/<dut>/
│   ├── __init__.py              # 导入时不创建 DUT 或启动仿真
│   ├── README.md                # 由工具生成的工作入口
│   ├── transactions.py          # 事务类型；复杂时用 transactions/
│   ├── env.py                   # 公开环境；复杂时用 env/ 包含 agent/ports/driver/monitor
│   ├── model.py                 # 按需：独立参考计算
│   ├── checker.py               # 按需：比较与不变量
│   ├── coverage.py              # 按需：行为覆盖
│   └── tests/                   # 本 DUT 用例、自检、scenarios/ 复用步骤
├── testbenches/shared/          # 按需：跨 DUT 组件，同用上述六职责及独立 README
├── conftest.py                  # 唯一 fixture / pytest 插件注册入口
├── pytest.ini                   # testpaths = testbenches
├── tools/                       # 按需：离线审计和报告命令
├── docs/spec/{design,verification}/  # 按 DUT 或跨 DUT 主题组织正文
├── docs/bugs/{open,closed}/     # 全工程统一问题记录
├── workspace.json              # DUT 与实际资料、实现、测试的关联
└── ucv.json                    # 真实 top、导出名与构建/运行配方
```

除 `tests/` 必须为目录外，其余五个职责块可以采用单文件或同名子包，按复杂度选择；
可选角色不建空壳。
同一参数化实现的多个 DUT 可通过 `workspace.json` 的 `duts.<name>.testbench` 字段共用实现包。
每个 DUT 的真实 top、基线和测试选择仍明确登记。跨 DUT 的行为合同放工程规格，
shared 的同名职责与 DUT 同义：共同事务归 transactions，独立参考计算归 model，比较归
checker，覆盖归 coverage，环境机制归 env，自检归 tests。仅一个 DUT 使用的内容留在该
DUT；shared 实现不得反向导入具体 DUT 或工程 tools，shared/tests 可检查集成引用。
`shared` 是保留名，不登记为 DUT，也没有独立 top 或本地原生库。

### Testbench 工作入口

`testbenches/<dut>/README.md` 应让接手人一跳找到以下内容：

1. DUT 键、实际 top 与适用基线的查询方式：`ucv info <suite> --dut <dut>`。
2. 当前设计规格、功能点与验证合同的具体入口；共享正文注明本 DUT 对应部分。
3. 公开 agent/env、事务类型及测试位置，说明主要职责所在。
4. 最小运行选择和报告命令，使用真实已存在的用例。
5. 工程问题汇总及相关稳定 Bug ID，未完成项链接所属规格。

配置、统计和问题状态以配方、运行收据及正式问题记录为准；README 不手工复制问题
状态表、历史 PASS 数字或源码锁。`ucv info` 提供资源地图，`ucv docs --write` 更新问题
汇总与 testbench README 的生成区块，保留人工补充。已有 shared 包有独立生成的
`testbenches/shared/README.md`，链接共享职责、工程合同和自检入口；各入口自动参与文档检查。
独立实现包尚未建立、仍处于源码/规格阶段时，先在工程规格和资源地图维护对应入口。

### 分层与测试约束

- 端口物理名只在 ports/bundle 适配层；功能场景调用有类型的事务 API。
- 功能用例经公开 agent/env 访问环境，不直接调用 driver、读取 ports 或修改 model；
  model/checker 的期望来自合同或独立依据，不能从 DUT 观察反推正确答案。
- fixtures 与 pytest 插件在工程唯一 `conftest.py` 显式注册；DUT 专用实现和参数生成放其
  `tests/fixtures.py` 或 tests 内插件，跨 DUT 插件放 `testbenches/shared/env/pytest_plugins/`。
- `tools/` 放离线汇总与审计命令；运行中的环境、覆盖和插件按 testbench 的职责归属维护。
- 复用锁定 Toffee 的 Driver、SamplingMonitor、Agent、Scoreboard；确需领域适配时在
  工程文档说明框架缺口和行为差异，不另造通用调度或传输框架。
- 原有单 DUT 测试若有 `testcase/`，新增场景继续放在那里；原来是平铺则继续平铺。
- 新测试文件尽量带 DUT 前缀，例如 `test_metabank_transaction_contract.py`，避免同一
  pytest 根下裸模块重名造成 import mismatch。不要为解决重名全局改变旧收集方式。
- 自检必须真实检查环境错误，保持 `selftest` 分类；不能通过搬目录或改标记隐藏功能耦合。

更完整的分层依据见 [driver/monitor 分层方法](skills/execution/package-layout.md)。

## 工作空间与资料维护

先运行 `./scripts/ucv info <suite> --dut <dut>` 找到资源；新增对象使用 `ucv init`。
能由配置和证据计算的地图、索引、计数由工具生成，人工/AI维护行为要求、独立预期与解释。
源码阅读和 spec 编写可先于工具安装；RTL 使用有效基线对应的锁定 release，源码生成显式选择。

同主题文档原位更新；规格使用稳定文件名，运行数据放结果目录。README 只维护当前摘要和
入口，问题汇总用 `ucv docs <suite> --write` 更新生成区块。问题编号不变，open/closed
表示当前处理状态，各基线的复验与关闭依据保留在同一记录；正式迭代由 Git 版本固定。
工程不新增泛化 history 目录，既有独立证据按所属主题引用。

工程根的 `verification_plan.json` 已删除，不新建改名替代文件。功能点与实现关联、
适用范围及完成条件维护在既有规格和合同中；确认的缺陷或待核问题进入问题记录，
配置限制、观察边界和集成范围留在所属规格。历史报告、日期记录和哈希清单保留原字节，
其中的旧计划路径仅用于追溯当时版本。

新增当前页面登记到 `docs/navigation.json`，用 `./scripts/ucv check full` 检查所有工程。
设计/验证 spec 采用工程结构，使用文档采用 Diátaxis。通用规则使用 `<suite>/<dut>`，
具体设计只用于明确示例。详细流程见[文档维护](docs/how-to/maintain-docs.md)。

## 分工和合并

1. 从同一个已发布 **Git commit/tag** 开始，各用独立分支或 worktree。
2. 在任务或 PR 中声明负责的工程/DUT及要改的共享文件；同一共享组件、
   `conftest.py`、工程配置或依赖锁不要由多个贡献者同时重构。
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
./scripts/ucv check full
.venv/bin/python scripts/audit-suite-layout.py --strict
.venv/bin/python scripts/audit-skills.py --strict --check-framework
.venv/bin/python -m pytest -q tests
```

工程代码变更再执行相关用例；输出目录每次取新名字，例如：

```sh
.venv/bin/ucv run icache --workers 1 --seed 1 --require-unified-baseline \
  --output results/icache-my-change-seed1 -- testbenches/metabank/tests
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
本次只负责 suites/<group>/<suite>/testbenches/<dut>/ 及对应合同文档；先核对工程 workspace schema。
保持现有工程根命名空间、目录和 fixture 注册方式，不新增 common/*verify 外壳。
先查真实合同与锁定 Toffee 能力，再修改事务/驱动/采样/checker。
保留原功能用例和真实非 PASS；关键修复提供合法控制与区分性错误控制。
若要改 testbenches/shared、工程配置或依赖，先说明影响和协调范围。
交付：变更文件、合同依据、实际命令与结果、原项差分、尚未验证的范围。
不要擅自发布、推送或把本次局部完成写成整个工程/仓库完成。
```
