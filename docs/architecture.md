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
│   ├── frontend/{bpu,ftq,ifu,ibuffer,instr_uncache,icache,frontend_top}/
│   ├── backend/{ctrl,int_region,fp_region,vec_region}/
│   ├── memblock/{lsq,dcache,mmu,sbuffer,lsu,prefetch,frontend_bridge}/
│   ├── cache/{l2,llc}/
│   ├── bus/{ncb,peripheral}/
│   ├── soc/{aia,plic,debug,timer,clock_reset,mbist}/
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
所有工程使用 schema2 的 `testbenches/<dut>/` 及跨 DUT 的 `testbenches/shared/`，
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

引用最近一级显式基线，不合并命名基线的内部字段。公开工程继承根；VAGQ 单独引用 internal 基线。新增基线要复制完整定义并更新名称、commit、递归 gitlink、生成配置、工具版本和补丁哈希。所有当前工程使用 DefaultConfig。

suite 是代码维护与执行边界，DUT＋合同是工作认领与验收单元，testbench 是每个 DUT 的独立验证实现。
先确定对象与合同，再按真实需求提取共享组件。父级负责接口协作，关键子级承担独立性质；父级包含子模块不自动
证明子级覆盖。源码 package、RTL top 和父实例共同确定绑定，参数化数字后缀不作为稳定身份。
当前工程设计索引和 workspace 的 `binding` 保存一次具体基线的观察，不是源码/配置 override；
升级基线后须重新核对，旧绑定观察不能代替新构建凭据。

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

## 验证工作如何管理

以**模块树**作为管理主轴，模块 ID 长期延续；DUT＋合同作为技术绑定与验收单元。
根配置引用的模块目录保存名称、管理父级、基线观察和有依据的承接历史，workspace 的
`module_id` 将每个 DUT 关联到模块。`ucv modules diff/apply` 比较旧记录与新观察的并集；
改名/移动保留身份，缺失保留待核实记录，拆分/合并/内联显式关联后继。具体见
[模块维护契约](reference/modules.md)。

每个 DUT 独立维护 testbench 与测试入口，模块族只承担管理归组；实际共用组件按职责提取到 shared。
大 DUT 内按合同条款拆任务，同族参数变体也分别保留硬件绑定与结果。suite 数量、DUT 数量、测试条数表示资产
规模，不作为总体完成率的分母；一次运行的标签通过率也不表示完整合同已证明。

使用现有入口即可形成管理闭环：

- 工程验证规格首页的 **DUT 工作索引**由 `ucv docs --write` 从配方和 workspace 生成；
  每个 DUT 链接自己的合同与实现入口，接入观察明确区分骨架、已有资产待复验和 top 缺失。
- 负责人、当前工作、下一步、阻塞及证据维护在对应合同正文或关联任务中。没有认领证据时
  保持待认领；不将历史跟踪表的姓名自动分派给新对象。
- 范围、要求与完成条件继续属于原规格；实际执行结果来自冻结收据与 `ucv report`，问题
  状态来自稳定问题记录。工作索引只是导航，不另造计划文件或第二份状态数据库。
- 跨模块性质归实际集成对象，例如 `frontend_top/frontend`、`frontend_bridge/frontend_bridge`
  和各 Region 顶层。设计分组用于查找，无需另维护功能链路视图或链路进度。

### 验证包边界的依据

| 包 | 维护与执行依据 | 工作拆分口径 |
|---|---|---|
| `ftq`、`ifu`、`ibuffer`、`instr_uncache` | 各自已有独立事务环境、生命周期、模型和覆盖工具；原 `fetch` 的四套 shared/env 并未形成共同环境 | 各 DUT 的既有合同、问题与结果独立；通用报告机制复用 `ucv.pytest_features` |
| `frontend_top` | 真实 `Frontend` 闭包的组合验证；尚为骨架 | 只承接顶层连接、取消/背压、WFI 等经评审的集成性质；不汇总冒充子模块验收 |
| `frontend_bridge` | MemBlock 内真实 `FrontendBridge` 与三个 A/D 缓冲切点；尚为骨架 | 各缓冲合同与父级三通道隔离/组合性质；物理位于 memblock |
| `ctrl` | 控制块及已有后端顶层切点的维护容器；尚为骨架 | rename/dispatch/ROB 等各自认领，`backend` 与 `ctrl_block` 的集成范围分别定义 |
| `int_region` | 整数调度、DataPath、执行协作及已登记参数变体；尚为骨架 | 发射队列、连接变体、DataPath、ExuBlock、Region 分别验收；访存流水归 LSU |
| `fp_region` | 浮点发射/IssuePipe、寄存器读取与写回使用关联的事务身份；尚为骨架 | 队列/流水变体、寄存器、仲裁和 Region 顶层分别认领；不宣称已实现联合环境 |
| `vec_region` | 向量发射/IssuePipe、寄存器/写回和异常组件的维护容器；尚为骨架 | 各对象独立合同；异常合并的 Backend 实例边界显式记录；internal VAGQ 独立 |
| 其余缓存、访存、互联与系统服务包 | 保留已有环境及第一版纠正后的硬件绑定；scaffold 仍是接入资产 | 统一使用逐 DUT 工作索引，不给整包自动分配“验证完成”状态 |

Region 的保留是当前维护选择，预期联合环境不是已证明的复用。如果实现时出现独立维护、
独立运行需求，应据具体成本调整；仅因位于相同物理层级或功能链路不构成强制合并理由。

## 工程文档与问题记录

所有工程共用 `docs/spec/{design,verification}/` 与 `docs/bugs/{open,closed}/` 结构。
工程 README 汇总工程入口，docs/README 汇总规格和问题，bugs/README 的表格与
各 DUT 实现包的 README 工作入口、验证规格首页的 DUT 工作索引由 `ucv docs <suite> --write` 生成；schema2 的已有
shared 包同样有独立生成入口。人工说明保留在生成区块之外，行为要求和问题分析各有
一个维护位置。

问题使用稳定 ID，当前状态由目录决定；记录保留各基线结论、复现/正常对照、关闭或重开
依据。Git commit/tag 固定正式迭代，工程不新建通用 history 目录。现有独立历史证据按
所属主题链接，仓库级来源/哈希索引仍用于外部证据访问。

运行开始时冻结问题记录及哈希，工程 Markdown 纳入验证源码身份。报告比较使用收据中的
快照，分别列出基线、用例和问题状态变化；报告不会从一个用例 PASS 推断 Bug 已修复。
语义 review 与最小复验仍由工程师负责，具体约定见[文档维护](how-to/maintain-docs.md)。

所有安装、源码和产物都属于当前检出：`.venv/`、`.tools/`、`.cache/`、`results/` 均忽略；工程中的 `rtl/`、`dut/`、`XiangShan` 是运行时创建的相对链接。`.ucv/local.json` 保存机器配置，Git 中没有通往旧工作区的链接。源目录移动后应重新建立虚拟环境和工具，不复用含绝对路径的二进制缓存。

新增工程/DUT 用 `ucv init --module-id <id>` 创建独立实现骨架、pytest 配置和规格入口，在根注册工程，
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

`workspace.json` 以 `duts.<name>.testbench` 一对一关联实现，`module_id` 关联稳定模块身份。
新增时 testbench 与 DUT 同名；同一模块 ID 可以关联多个独立 DUT，不能合并其实现与测试根。
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
