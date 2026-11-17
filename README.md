# ucv4xs

基于 UnityChip 的香山单元测试（UT）仓库，统一组织验证工程、RTL 基线、工具链和回归入口。仓库与 Python 发行包名为 `ucv4xs`，命令及 Python 导入名为 `ucv`，验证框架为锁定版本的 toffee。

当前为**按验证对象管理的结构接入版**：29 个 suite、336 个 DUT、336 个独立 testbench 实现包。
以**模块树**管理与追踪，DUT＋合同绑定和验收，suite 组织代码与运行，新 DUT 独立初始化 testbench。现有 266 个 DUT 已保留并迁移，
新增 70 个父级/参数变体切点；新增项仍为显式失败骨架。实际 FAIL、XFAIL、SKIP 和证据边界见
[阶段状态](docs/status.md)，结构接入不代表硬件验收。

原 LSQ/MMU/VAGQ 的 6 组共用实现已拆开，29 个相关 DUT 各有独立环境和测试入口；
同族模块 ID 保持，schema2 拒绝多个 DUT 指向同一 testbench。迁移证据见
[独立化记录](docs/history/per-dut-migration-20261117.json)。

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

| 分组 | 工程 |
|---|---|
| frontend | [bpu](suites/frontend/bpu/README.md)、[ftq](suites/frontend/ftq/README.md)、[ifu](suites/frontend/ifu/README.md)、[ibuffer](suites/frontend/ibuffer/README.md)、[instr_uncache](suites/frontend/instr_uncache/README.md)、[icache](suites/frontend/icache/README.md)、[frontend_top](suites/frontend/frontend_top/README.md) |
| backend | [ctrl](suites/backend/ctrl/README.md)、[int_region](suites/backend/int_region/README.md)、[fp_region](suites/backend/fp_region/README.md)、[vec_region](suites/backend/vec_region/README.md) |
| memblock | [lsu](suites/memblock/lsu/README.md)、[lsq](suites/memblock/lsq/README.md)、[sbuffer](suites/memblock/sbuffer/README.md)、[dcache](suites/memblock/dcache/README.md)、[mmu](suites/memblock/mmu/README.md)、[prefetch](suites/memblock/prefetch/README.md)、[frontend_bridge](suites/memblock/frontend_bridge/README.md) |
| cache / bus | [l2](suites/cache/l2/README.md)、[llc](suites/cache/llc/README.md)、[ncb](suites/bus/ncb/README.md)、[peripheral](suites/bus/peripheral/README.md) |
| soc | [aia](suites/soc/aia/README.md)、[plic](suites/soc/plic/README.md)、[debug](suites/soc/debug/README.md)、[timer](suites/soc/timer/README.md)、[clock_reset](suites/soc/clock_reset/README.md)、[mbist](suites/soc/mbist/README.md) |
| vector | [vagq](suites/vector/vagq/README.md)，独立 internal 基线 |

公开根基线为 `public-e716c7658`（`e716c765824900ff78816b92ac827fd4aa2cab35`）；
VAGQ 显式使用 `internal-d4566d58a`。各工程设计规格索引登记 Chisel / RTL / 实例映射。
`ftq/commit_queue` 和 `mmu/tlbn` 的历史 top 在新基线缺失，保留实现并明确待适配。

- `public`：13 个 suite；保留调整前相同的 140 个 DUT，含骨架，不能视为全绿回归集合。
- `full`：`public` 加 VAGQ，共 14 个 suite / 152 DUT。
- `public_all`：全部 28 个公开 suite / 324 DUT，适合统一基线的资源/结构检查。
- `all`：全部 29 个 suite / 336 DUT，含 internal VAGQ。

准确 DUT 和基线由 `ucv list/info` 读取。旧新对应及快照哈希见
[第一版切分记录](docs/history/ut-split-20261116.json)及
[验证工作组织调整记录](docs/history/ut-management-20261116.json)。

### 认领、推进与验收

1. 用 `./scripts/ucv modules list` 查看已采用的模块树与持久 ID，再进入所属工程的
   `docs/spec/verification/README.md` 查看 **DUT 工作索引**；
   `./scripts/ucv docs <suite>` 可直接预览。索引一行一个 DUT，链接合同与实现入口。
2. 按 DUT 与合同范围认领，记录负责人、当前工作、下一步、阻塞和验收证据。
   在既有合同正文或关联任务中维护，未认领项明确待认领；历史跟踪表的负责人不自动继承。
3. 以当前基线下的合同条款、实际运行和覆盖证据收口。骨架、已有资产待复验、构建、
   功能结果分别说明；suite/DUT 数量和已收集标签通过率不代表工作完成比例。

跨模块性质归实际集成 DUT 的合同，例如 `frontend_top/frontend`；目录分组用于查找，
无需另维护功能链路进度。包边界与后端 Region 的取舍见[组织依据](docs/architecture.md#验证工作如何管理)。
模块改名、移动、内联或缺失先做 `ucv modules diff`，保持身份和历史；
[模块目录](docs/modules.json)与[维护契约](docs/reference/modules.md)提供完整入口。

各工程的判定、复验范围与历史证据从工程 README / 问题汇总进入，全仓当前摘要见
[阶段状态](docs/status.md)。基线升级的原记录见
[来源索引](docs/history/baseline-kunminghu-v3-20261102.json) 与
[LSQ 回归结论](docs/lessons/lsq-baseline-regression-20261103.md)。旧基线结果保持原版本含义。

历史 `public-a0c2a26cb` 基线的完整生成 RTL（SystemVerilog，DefaultConfig，release 配置，等价于上游
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

资源导航只需要 Python 3.12；源码获取需要 Git。当前 `public-e716c7658` 尚无锁定
RTL release，首次运行使用源码生成路线，宿主还需 Java 17。
仿真支持 Linux x86_64，宿主需提供 Make、CMake、C++20 编译器、SWIG ≥ 4.2 及
Autoconf/Flex/Bison。工具和 Python 环境安装在 `.tools/` 与 `.venv/`。

```sh
git clone https://github.com/XS-MLVP/ucv4xs.git
cd ucv4xs
./scripts/ucv info bpu --dut mbtb
```

`info` 只读显示有效基线、规格、testbench、测试与资源路径，不构建 DUT。首次运行按
[完整教程](docs/tutorials/bpu-first-ut.md)安装工具、从源码准备 RTL 并构建。已有环境时，
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
| `ucv modules` | 模块树、持久 ID、版本变化对账和历史承接 |
| `ucv init --module-id ID` | 为新 DUT 生成独立 testbench、规格与环境骨架 |
| `ucv docs` | 生成 DUT 工作索引、问题汇总与 testbench 入口（含 shared），--write 刷新既有正文的生成区块 |
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
│   ├── frontend/{bpu,ftq,ifu,ibuffer,instr_uncache,icache,frontend_top}/
│   ├── backend/{ctrl,int_region,fp_region,vec_region}/
│   ├── memblock/{lsq,dcache,mmu,sbuffer,lsu,prefetch,frontend_bridge}/
│   ├── cache/{l2,llc}/
│   ├── bus/{ncb,peripheral}/
│   ├── soc/{aia,plic,debug,timer,clock_reset,mbist}/
│   └── vector/vagq/
├── skills/                    # 项目工作流与验证经验
├── docs/                      # 架构、维护、经验和历史索引
├── scripts/                   # 启动、资产检查和历史比较
├── tests/                     # ucv 与工具补丁检查
└── AGENTS.md                  # 仓库内协作约定
```

各工程根直接作为 Python 包，例如 `suites.memblock.lsq`，不再嵌套 lsqverify 等外壳，
也不使用无前缀的 import common。所有工程统一使用 workspace schema2：DUT 实现和测试
集中在 `testbenches/<dut>/`，跨 DUT 组件放 `testbenches/shared/`；双方同用 env、transactions、
model、checker、coverage、tests 六职责，按需实现。根包 ROOT 统一定位资源。
`ucv init` 生成骨架，`ucv docs --write` 生成各自 README，`ucv check` 按 schema 强制检查结构。
编辑安装后可从其他 cwd 导入实现，运行仍需当前检出的配置、工具链和生成 DUT。
参数变体通过 workspace 一对一关联独立实现；版本兼容及共享边界见
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
