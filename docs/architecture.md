# 仓库结构与扩展方式

本页解释仓库的层次和边界，不是一份安装或回归步骤。查具体文件看
[目录参考](reference/repository-layout.md)，实际操作从[工作空间](how-to/workspace.md)与
[运行指南](how-to/run-tests.md)进入；适配范围、硬件失败与未完成项只在[阶段状态](status.md)维护。

## 公共工具、工程和 DUT 为什么分开

仓库与发行包名是 `ucv4xs`，公共命令/导入名是 `ucv`，验证框架为锁定的 Toffee。
三者承担不同职责，不在每个工程里复制一套调度、安装或构建工具。

```text
ucv4xs/
├── ucv.json                    # 根基线、工程注册、public/full 集合
├── baselines/                  # 完整命名基线与递归源码锁
├── dependencies/               # Python/原生工具锁与带哈希的工具补丁
├── src/ucv/                    # 公共编排、路径、运行记录与报告
├── suites/
│   ├── frontend/{bpu,icache,ftq,ifu,ibuffer,instr_uncache}/
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

每个工程保留 `ucv.json`、`workspace.json`、`conftest.py`、`pytest.ini`、DUT 实现包和领域文档。
十二工程与新工程使用 schema2 的 `testbenches/<dut>/` 及跨 DUT 的 `testbenches/shared/`，
现有工程的版本兼容范围见[目录规范](reference/module-layout.md#schema-版本与本轮范围)。
公共编排层不导入工程领域模型；各工程通过 `ucv.runtime` 解析项目工具、有效源码和历史
证据路径。历史 `manifest/` 和审计文档保留原基线含义，当前构建以缓存中的 `source.json`、
`generation.json`、`build.json` 为准。

| 层 | 配置与职责 |
|---|---|
| 根 | `ucv.json` 注册工程、集合、根默认基线 |
| 硬件分组 | `suites/<group>/ucv.json` 可引用命名基线 |
| 工程 | `ucv.json` 声明生成方式、DUT top、导出类、pytest 收集根，可覆盖基线 |
| DUT | 继承整个工程的基线，不提供单 DUT commit/config override |

引用最近一级显式基线，不合并命名基线的内部字段。三个初始分组均继承根；VAGQ 单独引用 internal 基线。新增基线要复制完整定义并更新名称、commit、递归 gitlink、生成配置、工具版本和补丁哈希。所有当前工程使用 DefaultConfig。

工作入口为 `info/init/check/docs`。`prepare --source-only` 独立获取精确源码；
`prepare --rtl-source release` 下载锁定的完整 RTL 并提取模块闭包；本机完整生成由
`--rtl-source source` 显式选择。`setup --profile runtime` 安装仿真工具，full 另装生成工具。
各工程（包括 BPU）使用完整香山产物；`build` 为所选 DUT 调用 Picker 并在独立进程冒烟；
`run --dut` 限定测试根和构建检查，BPU 仍按 native owner 分进程。构建与运行共享工程锁。
导航元数据放工程 `workspace.json`，规格独立于使用文档；详见[工作空间参考](reference/workspace.md)。

一次用例的交互链是：

```text
ucv：选择、基线与构建身份预检、进程隔离、收据
  → 工程 conftest：装配 fixture，管理原生 DUT 生命周期
  → tests：经公开 agent/env 发送事务、施加背压、提出独立检查
  → env 的 driver/ports：编码并驱动真实 RTL
  ← env 的 monitor/ports：按合同窗口采样、解码
  → model/checker：用合同或独立依据比较
  → coverage 与 report：记录实际已检查行为及仍缺的证据
```

这样分层不意味着测试不能观察业务结果，而是避免让场景依赖物理字段名、私有句柄或
参考模型预测来决定下一笔合法刺激。期望、实际观察、刺激所有权及覆盖证明仍需独立审查；
目录分层只能提供边界，不能自动证明这些语义正确。

## 工程文档与问题记录

所有工程共用 `docs/spec/{design,verification}/` 与 `docs/bugs/{open,closed}/` 结构。
工程 README 汇总工程入口，docs/README 汇总规格和问题，bugs/README 的表格与
各 DUT 实现包的 README 工作入口由 `ucv docs <suite> --write` 生成；schema2 的已有
shared 包同样有独立生成入口。人工说明保留在生成区块之外，行为要求和问题分析各有
一个维护位置。

问题使用稳定 ID，当前状态由目录决定；记录保留各基线结论、复现/正常对照、关闭或重开
依据。Git commit/tag 固定正式迭代，工程不新建通用 history 目录。现有独立历史证据按
所属主题链接，仓库级来源/哈希索引仍用于外部证据访问。

运行开始时冻结问题记录及哈希，工程 Markdown 纳入验证源码身份。报告比较使用收据中的
快照，分别列出基线、用例和问题状态变化；报告不会从一个用例 PASS 推断 Bug 已修复。
语义 review 与最小复验仍由工程师负责，具体约定见[文档维护](how-to/maintain-docs.md)。

所有安装、源码和产物都属于当前检出：`.venv/`、`.tools/`、`.cache/`、`results/` 均忽略；工程中的 `rtl/`、`dut/`、`XiangShan` 是运行时创建的相对链接。`.ucv/local.json` 保存机器配置，Git 中没有通往旧工作区的链接。源目录移动后应重新建立虚拟环境和工具，不复用含绝对路径的二进制缓存。

新增工程/DUT 优先用 `ucv init` 创建实现骨架、pytest 配置和规格入口，在根注册工程，
并声明完整 DUT 配方。新工程使用 schema2 的 `testbenches/<dut>/`，向已有工程添加 DUT
则沿用其 schema。公共编排变更运行根 `tests/`；工程内部检查通过 `ucv run <suite>` 运行。
更改构建语义时应更新缓存身份中的 `pipeline_version`，不复用旧构建凭据。第一版不配置 CI。

Git 保存可复现的代码、配方、工具锁、必要文档与哈希索引，不保存完整运行工作目录。
资产审计核对实际跟踪文件、工程入口和历史索引；它不需要仿真，也不证明某个 DUT 已通过。
历史索引按工程拆为 JSONL，主索引保存数量和哈希，内容通过 `history://` 外部定位。
具体检查操作见[协作约定](../CONTRIBUTING.md#最小检查集)。

## 验证包与 pin 边界

当前 fixture 结构检查由 `scripts/audit-suite-layout.py` 和
`tests/test_suite_layout.py` 实现；它不是完整事务层架构认证：

- 每个工程只有 pytest 根的一个 `conftest.py` 注册 fixtures/pytest 插件；DUT 与 shared
  实现包内不设嵌套 conftest、根级 `agent/` 或 `*/env/pytest.py` 转发层；
- fixture 负责原生资源生命周期，测试应通过 agent/env 的事务 API；静态 fixture
  条目数不等于 DUT owner 数，参数化工厂也可覆盖多个 DUT；
- 物理名属于 DUT 的 ports/bundle 适配层；跨 DUT 机制以明确职责命名，不建 common。
  `P.p_*` / `P.io(...)` 是兼容字符串别名，仍属引脚级耦合，不是事务 API；
- `pytest.ini` 注册 `selftest`，共享插件 `ucv.pytest_selftest` 按目录自动标记；自检不计
  硬件功能 credit；
- 原生时钟、复位、组合刷新和结构性 bit sweep 通过所属 DUT 的 env/agent 或真正跨 DUT
  共享的环境机制完成。

布局 `--strict` 只验结构接线；附加事务边界扫描还统计引脚 keyword、物理字符串、
别名及环境内部访问，保守命中需要审查实际用途。最新残余和已接受的适配范围以
[状态页](status.md)为准，不在结构解释里维护第二份工程进度表。
零静态命中也不证明采样、引脚所有权或独立 checker 已经合格。

2026-11-01 进一步补上 raw_dut、xport/xclock 和通道字典 .Set/.U 等盲区，
以 signal_operations 单列，不改写旧 pin expressions 的历史口径。由此 Sbuffer 也有
事务边界待适配项；结构通过不代表其用例已经完全摆脱信号对象。修复记录见
[提交后语义复核](lessons/semantic-boundary-repair-20261101.md)。

随后在 2026-11-01 完成 Sbuffer/SbufferData 的框架 Driver、lossless Monitor、不可变事务与接受/响应
账本修复，Sbuffer 的上述静态两类计数已清零，且有正常/错误对照，不再仅凭目录或零计数
论证。当时其余六工程待适配是历史检查点，不是当前状态；具体证据与不包含的证明范围见
[事务边界修复](lessons/transaction-boundary-repair-20261101.md)。

## 工程目录和 Python 命名空间

多人/AI协作的统一放置表、测试命名和交接规则见
[CONTRIBUTING.md](../CONTRIBUTING.md)。沿用同一工程/DUT现有布局，不为发布批量搬迁
或强制创建空角色目录；共享文件改动先协调。

schema2 的每个 DUT 实现和用例集中在 `testbenches/<dut>/`，`testbenches/shared/` 只放
真正跨 DUT 的组件。双方同用 `transactions`、`env`、`model`、`checker`、`coverage`、
`tests` 六职责且同名同义：tests 为目录，其余按需选单文件或同名包，不造空壳。
共享实现不得反向导入具体 DUT 或工程 tools，shared/tests 可检查集成引用；shared 是
保留名，没有独立 DUT/top/本地原生库。DUT 专用参数生成归其 tests/插件，由工程唯一
`conftest.py` 注册，离线汇总和审计命令归 tools。

`workspace.json` 以 `duts.<name>.testbench` 显式关联实现，参数化 DUT 可指向同一包。
配方 `tests` 与 `pytest.ini` 的 `testpaths` 都使用 `testbenches`。规格和问题集中工程
`docs/`；完整规则及 schema 兼容边界见[testbench 目录规范](reference/module-layout.md)。

工程根直接作为包：例如磁盘 suites/memblock/lsq 对应 Python suites.memblock.lsq。
十个旧 *verify 外壳均已去掉。绑定、驱动、采样和加载机制按职责归各 DUT 或 shared，
工程根保持唯一 fixture / 插件注册入口，没有另一个框架或逐工程发行项目。

Python 安装入口和包发现规则由 `pyproject.toml` 定义；安装 Python 包不等于取得已构建
RTL/native 或运行证据。正常运行仍依赖当前检出的配置、本地工具与生成资源，不宣称
单独 wheel 是可脱离检出运行的 DUT 产品；发布边界由资产审计核对。

runner 提供仓库根和选中工程目录，前者用于全限定实现 import，后者用于工程内按 schema
解析的实现、tools 与 dut 相对入口。ROOT 由工程包解析；旧 RTL/native 收据保留原身份，
配方更新后由 `ucv build` 建立当前身份的真实构建凭据。
对比历史运行时保留旧源码键，当前路径用显式映射，不制造 sys.modules 旧名别名。
迁移清单、资源锚点与验证见[命名空间重构](lessons/suite-namespace-refactor-20261031.md)。
