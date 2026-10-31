# 仓库结构与扩展方式

本仓库的结构版统一工程组织、源码基线、命令入口和产物归属。硬件失败和 BPU 的后续适配单独登记在 [阶段状态](status.md)。

```text
ucv4xs/
├── ucv.json                    # 根基线、工程注册、public/full 集合
├── baselines/                  # 完整命名基线与递归源码锁
├── dependencies/               # Python/原生工具锁与带哈希的工具补丁
├── src/ucv/                    # 公共编排、路径、运行记录与报告
├── suites/
│   ├── frontend/{bpu,icache,ftq,ifu}/
│   ├── memblock/{lsq,dcache,mmu,sbuffer,lsu}/
│   └── vector/vagq/
├── skills/                     # 项目工作流、跨模块防复发手册与速查卡
├── AGENTS.md                   # 仓库协作约定
├── tests/                      # 编排层与工具补丁的检查
├── scripts/                    # 启动入口、资产审计、历史比较
└── docs/
    ├── architecture.md         # 结构与扩展方式
    ├── baselines.md            # 基线与构建
    ├── local-configuration.md  # 本地源码和历史证据接入
    ├── maintenance.md          # 维护与验收
    ├── status.md               # 阶段状态
    ├── lessons/                # 经验统一入口、跨模块案例总结
    └── history/                # 迁移记录、来源哈希与证据索引
```

验证经验从 [经验与复盘索引](lessons/README.md) 进入：`skills/` 保留可复用方法，工程 `docs/` 保留合同、缺陷与具体复盘，`docs/history/` 记录来源和历史证据。

每个工程保留 `ucv.json`、`pytest.ini`、独立验证包、`tests/` 和领域文档。共享层不导入任何工程的领域模型；各工程通过 `ucv.runtime` 解析项目工具、有效源码和历史证据路径。历史 `manifest/` 和审计文档保留原基线含义，当前构建以缓存中的 `source.json`、`generation.json`、`build.json` 为准。

| 层 | 配置与职责 |
|---|---|
| 根 | `ucv.json` 注册工程、集合、根默认基线 |
| 硬件分组 | `suites/<group>/ucv.json` 可引用命名基线 |
| 工程 | `ucv.json` 声明生成方式、DUT top、导出类、测试目录，可覆盖基线 |
| DUT | 继承整个工程的基线，不提供单 DUT commit/config override |

引用最近一级显式基线，不合并命名基线的内部字段。三个初始分组均继承根；VAGQ 单独引用 internal 基线。新增基线要复制完整定义并更新名称、commit、递归 gitlink、生成配置、工具版本和补丁哈希。所有当前工程使用 DefaultConfig。

命令链为 `setup → prepare → build → run → report`。`list` 和 `doctor` 用于确认选择、继承来源和环境。`prepare` 获取精确源码并按有效基线完整生成香山 RTL，同基线共享一次生成结果。各工程（包括 BPU）从这份产物提取模块闭包，不注入验证专用 Scala 入口。`build` 为各 DUT 调用 Picker 并在独立进程冒烟；`run` 按工程隔离进程，BPU 进一步按 DUT 分区，共享一个 worker 预算。显式用例路径替代默认测试目录，`-k`/`-m` 作用于默认集合。构建与运行共享工程锁，避免活动链接在回归期间被切换。

所有安装、源码和产物都属于当前检出：`.venv/`、`.tools/`、`.cache/`、`results/` 均忽略；工程中的 `rtl/`、`dut/`、`XiangShan` 是运行时创建的相对链接。`.ucv/local.json` 保存机器配置，Git 中没有通往旧工作区的链接。源目录移动后应重新建立虚拟环境和工具，不复用含绝对路径的二进制缓存。

新增工程时，在对应分组创建目录、验证包和 pytest 配置，在根注册工程，并声明完整 DUT 配方。公共编排变更运行根 `tests/`；工程内部检查通过 `ucv run <suite>` 运行。更改构建语义时应更新缓存身份中的 `pipeline_version`，不复用旧构建凭据。第一版不配置 CI。

公开文件边界检查：

```sh
python3 scripts/audit-assets.py
```

该检查不需要安装原生工具，验证源码边界、旧框架导入、工程入口和历史索引哈希。历史索引按工程拆为 JSONL，主索引保存数量和哈希；内容文件仍通过 `history://` 外部定位。简短的历史审计与缺陷文档可以留在 Git 中，大结果、覆盖率原始数据和内部 RTL 保持外部接入。

## 验证包与 pin 边界

当前 fixture 结构检查由 `scripts/audit-suite-layout.py` 和
`tests/test_suite_layout.py` 实现；它不是完整事务层架构认证：

- 每个工程只有 pytest 根的一个 `conftest.py` 注册 fixture；不存在
  `tests/<dut>/conftest.py` 或 `*/env/pytest.py` 转发层；
- fixture 负责原生资源生命周期，测试应通过 agent/env 的事务 API；静态 fixture
  条目数不等于 DUT owner 数，参数化工厂也可覆盖多个 DUT；
- 物理名属于 DUT 的 ports/bundle 适配层；跨 DUT 机制以明确职责命名，不建 common。
  `P.p_*` / `P.io(...)` 是兼容字符串别名，仍属引脚级耦合，不是事务 API；
- `pytest.ini` 注册 `selftest`，共享插件 `ucv.pytest_selftest` 按目录自动标记；自检不计
  硬件功能 credit；
- 原生时钟、复位、组合刷新和结构性 bit sweep 通过工程 execution/runtime 或 env/agent
  方法完成。

```sh
.venv/bin/python scripts/audit-suite-layout.py --strict
.venv/bin/python scripts/audit-suite-layout.py --require-transaction-boundary
```

`--strict` 只验结构接线。更严格的事务边界命令对 IFU/LSQ/LSU/MMU/DCache/VAGQ
仍报告真实待适配项；引脚 keyword、物理字符串和别名都被统计。零静态命中也不证明
采样、引脚所有权或独立 checker 已经合格。

## 工程目录和 Python 命名空间

工程根直接作为包：例如磁盘 suites/memblock/lsq 对应 Python suites.memblock.lsq。
十个旧 *verify 外壳均已去掉，common 按职责拆到 ports、drivers、monitors、runtime、
pytest_plugins 或 native.py/harness.py 等。没有新建另一个框架或逐工程发行项目。

ucv4xs 的安装包只包含 ucv 与 suites 的 Python 实现；测试、tools、docs、manifest、
结果、RTL 和原生二进制不纳入 wheel。正常运行仍依赖当前检出的配置/本地工具和生成
资源，不宣称单独 wheel 是可脱离检出运行的 DUT 产品。

runner 提供仓库根和选中工程目录，前者用于全限定实现 import，后者仅兼容工程内
tests/tools/dut 的既有入口。ROOT 由工程包解析；改布局不改 RTL/native 构建收据。
对比历史运行时保留旧源码键，当前路径用显式映射，不制造 sys.modules 旧名别名。
迁移清单、资源锚点与验证见[命名空间重构](lessons/suite-namespace-refactor-20261031.md)。
