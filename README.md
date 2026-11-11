# ucv4xs

基于 UnityChip 的香山单元测试（UT）仓库，统一组织验证工程、RTL 基线、工具链和回归入口。仓库与 Python 发行包名为 `ucv4xs`，命令及 Python 导入名为 `ucv`，验证框架为锁定版本的 toffee。

当前版本是**结构整合版**：十二个工程、137 个 DUT 已接入统一构建与运行链路。BPU 对完整 DefaultConfig RTL 的模型和用例适配、完整生产回归及空缓存全链路验收仍在推进。实际 FAIL、XFAIL、SKIP 和证据边界见 [阶段状态](docs/status.md)；结构标签不代表硬件验收通过。

第一次使用从 **[BPU/MainBTB 第一个 UT](docs/tutorials/bpu-first-ut.md)** 开始；
只阅读源码和编写规格可以跳过工具安装。[使用文档](docs/README.md)按 Diátaxis 四类需求导航：

| 你的需要 | 入口 |
|---|---|
| 跟着完成第一次运行 | [教程](docs/tutorials/bpu-first-ut.md) |
| 准备 RTL、选跑用例或比较结果 | [工作空间指南](docs/how-to/workspace.md)、[运行指南](docs/how-to/run-tests.md) |
| 查目录、命令参数和配置 | [目录参考](docs/reference/repository-layout.md)、[ucv 参考](docs/reference/workspace.md) |
| 理解基线、分层和验收含义 | [结构解释](docs/architecture.md)、[基线与构建](docs/baselines.md)、[维护与验收](docs/maintenance.md) |

准备参与开发或使用 AI 修改本仓库，请先读 [协作开发与目录约定](CONTRIBUTING.md)。
当前交接范围与未完成项见[阶段状态](docs/status.md)，检查结果的含义见
[维护与验收](docs/maintenance.md)。

## 工程与基线

| 分组 | 工程 | DUT 数 | 当前有效基线 |
|---|---|---:|---|
| frontend | [BPU](suites/frontend/bpu/README.md) / [ICache](suites/frontend/icache/README.md) / [FTQ](suites/frontend/ftq/README.md) / [IFU](suites/frontend/ifu/README.md) / [IBuffer](suites/frontend/ibuffer/README.md) / [InstrUncache](suites/frontend/instr_uncache/README.md) | 10 / 11 / 3 / 7 / 2 / 3 | public-a0c2a26cb |
| memblock | [LSQ](suites/memblock/lsq/README.md) / [DCache](suites/memblock/dcache/README.md) / [MMU](suites/memblock/mmu/README.md) / [Sbuffer](suites/memblock/sbuffer/README.md) / [LSU](suites/memblock/lsu/README.md) | 38 / 13 / 17 / 2 / 19 | public-a0c2a26cb |
| vector | [VAGQ](suites/vector/vagq/README.md) | 12 | internal-d4566d58a，外部源码接入 |

`public` 集合包含十一个公开工程；`full` 另外包含 VAGQ。公开根基线固定为
`a0c2a26cbe3c862175174bad03a1a23c406315ed`，对应2026-11-02核对的上游
`kunminghu-v3` 分支头；保存完整commit，不自动漂移跟随分支。VAGQ工程继续显式覆盖
internal `d4566d58a5ace1f6a5df4409b37a84b971f48e43`。

各工程的判定、复验范围与历史证据从工程 README / 问题汇总进入，全仓当前摘要见
[阶段状态](docs/status.md)。基线升级的原记录见
[来源索引](docs/history/baseline-kunminghu-v3-20261102.json) 与
[LSQ 回归结论](docs/lessons/lsq-baseline-regression-20261103.md)。旧基线结果保持原版本含义。

该基线的完整生成 RTL（SystemVerilog，DefaultConfig，release 配置，等价于上游
`make verilog`）已作为 release 附件发布：tag
[`xiangshan-a0c2a26cb`](https://github.com/XS-MLVP/ucv4xs/releases/tag/xiangshan-a0c2a26cb)，
含 `rtl/*.sv`、`rtl/*.v`、`rtl/filelist.f` 和完整 `BUILD-PARAMETERS.json`。附件不含断言
（release 参数丢弃 verification layer），也不依赖 difftest；详见包内 README。

所有工程使用 **DefaultConfig**。基线按“根 → 硬件分组 → 工程”继承，最近的显式完整命名基线优先；一个工程的所有 DUT 共用基线。源码 commit、递归子模块、生成参数、工具版本和设计补丁均进入版本清单。

```text
完整香山 DefaultConfig → RTL → DUT 模块闭包 → Picker / Verilator → UT
```

同基线共享完整 RTL 生成结果，各 DUT 单独构建。BPU 使用这条完整香山链路；绑定与模型适配整芯片优化后的实际端口。详情见 [基线与构建](docs/baselines.md)。

各工程的开放问题、观察和集成缺口按所属工程登记；局部测试通过不代表工程签核。

## 快速开始：BPU/MainBTB 示例

资源导航和 release RTL 获取只需要 Python 3.12；源码获取需要 Git。
仿真支持 Linux x86_64，宿主需提供 Make、CMake、C++20 编译器、SWIG ≥ 4.2 及
Autoconf/Flex/Bison。工具和 Python 环境安装在 `.tools/` 与 `.venv/`。

```sh
git clone https://github.com/XS-MLVP/ucv4xs.git
cd ucv4xs
./scripts/ucv info bpu --dut mbtb
```

`info` 只读显示有效基线、规格、testbench、测试与资源路径，不构建 DUT。首次运行按
[完整教程](docs/tutorials/bpu-first-ut.md)继续获取 release、安装工具并构建。已有环境时，
可对当前已构建的 MainBTB 显式运行一个用例；以下输出目录必须是新目录：

```sh
./scripts/ucv run bpu --dut mbtb --workers 1 --seed 1 --output results/mbtb-first-ut -- \
  testbenches/mbtb/tests/testcase/test_reset.py::test_reset_completes_before_cold_lookup
./scripts/ucv report results/mbtb-first-ut
```

报告保留本次实际用例计数；运行开始冻结的问题记录若在当前基线仍开放或未复验，
纯 PASS 汇总会降为 `INCOMPLETE`，真实 FAIL/ERROR 优先。工程验收还须对照规格中的
未证明范围；单个 MainBTB 用例通过不代表 BPU 整体验收，具体见[BPU 教程](docs/tutorials/bpu-first-ut.md)。
构建/冒烟、功能判定、适配接受与覆盖签核分别报告，退出码也不能代替这些结论。

需要本地镜像或 internal 来源时，将 [本地配置示例](ucv.local.example.json) 中需要的字段写入 `.ucv/local.json`，按 [外部接入说明](docs/local-configuration.md) 配置；删除未使用的占位字段。VAGQ 缺少外部源码时会明确报错。`full` 当前是混合基线集合，启用 `--require-unified-baseline` 会拒绝执行。

## 常用命令

| 命令 | 用途 |
|---|---|
| `ucv list` / `ucv doctor` | 工程、DUT、有效基线、继承来源和环境检查 |
| `ucv info` / `ucv check` | 生成资源地图、检查登记路径与当前文档入口 |
| `ucv init` | 生成新工程或新 DUT 的规格与环境骨架 |
| `ucv docs` | 生成问题汇总与 testbench 工作入口（含 shared），--write 刷新 README 生成区块 |
| `ucv setup` | 安装版本清单中的项目依赖 |
| `ucv prepare` | 单独获取源码；从 release 或显式生成取得 RTL、提取 DUT 闭包 |
| `ucv build` | 原生构建与冒烟 |
| `ucv run` | 按 DUT、工程、分组或集合回归 |
| `ucv report` | 判定、覆盖率、来源与历史差异 |

统一从仓库根使用 `./scripts/ucv`；安装后也可使用 `.venv/bin/ucv`。选跑、参数化变体、
收集、种子、并发和结果比较见[运行指南](docs/how-to/run-tests.md)；准确默认值与转发限制
见[命令参考](docs/reference/workspace.md)。不要为了一个用例默认启动整个公开集合。

生产集合由各工程的 `pytest.ini` 定义，BPU 使用工程的 `production` profile；VAGQ 的独立 ISA audit 保留显式选择方式。每次运行记录验证源码、用例集合、基线、RTL/native 哈希、工具链和种子，判定按实际结果保留。

## 目录与资产

```text
ucv4xs/
├── ucv.json                   # 根默认基线、工程注册和集合
├── baselines/                 # 完整命名基线
├── dependencies/              # 依赖版本与工具补丁
├── src/ucv/                   # 公共编排工具
├── suites/
│   ├── frontend/{bpu,icache,ftq,ifu,ibuffer,instr_uncache}/
│   ├── memblock/{lsq,dcache,mmu,sbuffer,lsu}/
│   └── vector/vagq/
├── skills/                    # 项目工作流与验证经验
├── docs/                      # 架构、维护、经验和历史索引
├── scripts/                   # 启动、资产检查和历史比较
├── tests/                     # ucv 与工具补丁检查
└── AGENTS.md                  # 仓库内协作约定
```

各工程根直接作为 Python 包，例如 `suites.memblock.lsq`，不再嵌套 lsqverify 等外壳，
也不使用无前缀的 import common。十二工程统一使用 workspace schema2：DUT 实现和测试
集中在 `testbenches/<dut>/`，跨 DUT 组件放 `testbenches/shared/`；双方同用 env、transactions、
model、checker、coverage、tests 六职责，按需实现。根包 ROOT 统一定位资源。
`ucv init` 生成骨架，`ucv docs --write` 生成各自 README，`ucv check` 按 schema 强制检查结构。
编辑安装后可从其他 cwd 导入实现，运行仍需当前检出的配置、工具链和生成 DUT。
十二工程现已统一为该布局，全仓既有 137 DUT / 114 实现包映射保持；版本兼容及共享边界见
[testbench 目录规范](docs/reference/module-layout.md)，整体关系见[结构说明](docs/architecture.md)。

工程文档统一为 `docs/spec/{design,verification}/` 与 `docs/bugs/{open,closed}/`。
README 汇总当前范围和入口；同一问题保持稳定编号，历史基线结论及关闭证据写入原记录，
Git 固定每次迭代。通用维护规则见[文档维护](docs/how-to/maintain-docs.md)。
工程根的 `verification_plan.json` 已删除；功能点、合同和验证范围沿用既有规格正文，
真实缺陷维护在问题记录中。历史报告中的旧计划路径、哈希和判定保留当时含义。

`.cache/` 保存源码检出、生成 RTL/FIRRTL 和 DUT 构建；`results/` 保存运行结果；`.history/` 保存本地迁移备份；`.venv/`、`.tools/`、`.ucv/` 保存本地环境与状态。这些目录均被 Git 忽略。Git 中的 `docs/history/` 保存迁移记录和证据哈希，历史证据内容通过外部 `history://` 来源访问。internal 实现、生成文件和含内部源码的证据保持外部接入。完整目录职责见[目录参考](docs/reference/repository-layout.md)。

覆盖率收尾成功时会合并并清理中间输入；异常中断可能留下大量文件。当前按字节限制缓存和异常回收的机制仍待完善，清理记录见 [维护说明](docs/maintenance.md)。

## 文档、经验与开发

- [AGENTS.md](AGENTS.md)：修改本仓库时遵循的结构、基线和验证约定。
- [CONTRIBUTING.md](CONTRIBUTING.md)：人工与 AI 共用的目录、命名、分工、检查和交接模板。
- [项目工作流 skill](skills/ucv4xs-workflow/SKILL.md)：基线变更、构建、回归及新增工程的操作入口。
- [skill 索引](skills/README.md) 与 [经验总入口](docs/lessons/README.md)：保留原案例、误报漏检复盘与防复发手册。
- [维护与验收](docs/maintenance.md)、[阶段状态](docs/status.md)：当前工作边界、真实判定和未完成事项。

skills 可按文件路径读取；仓库中存在 skill 文件不表示已向客户端注册或自动加载。第一版没有 CI；本地检查入口为：

```sh
python3.12 scripts/audit-assets.py
.venv/bin/python -m pytest -q tests
.venv/bin/python scripts/audit-suite-layout.py --strict
.venv/bin/python scripts/audit-skills.py --strict --check-framework
```

布局 --strict 校验按 schema 的目录与 fixture 接线。`--require-transaction-boundary` 另查物理字段和
P.p_*/P.io 别名，保守命中仍须逐项分类并如实保留非零退出码，最新结果见[当前状态](docs/status.md)。
不把结构全绿、静态零命中或部分适配接受当成硬件验收。

自有代码和文档采用 [MPL-2.0](LICENSE)，导入文件原有许可声明保留，详见 [NOTICE](NOTICE.md)。
