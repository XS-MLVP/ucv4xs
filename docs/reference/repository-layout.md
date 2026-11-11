# 目录与文件职责

本页列出当前目录和文件的用途；具体 DUT 的实际映射以 `ucv info <suite> --dut <dut>`
及 `workspace.json` 为准。组织方式的理由见[结构解释](../architecture.md)，实现层级的
强制规则见[testbench 目录规范](module-layout.md)。

## 仓库根

```text
ucv4xs/
├── src/ucv/                    # 公共编排、配置、构建、运行与报告
├── suites/                     # 验证工程；不是额外的 *verify 外壳
│   ├── frontend/{bpu,ftq,icache,ifu,ibuffer,instr_uncache}/
│   ├── memblock/{lsq,dcache,mmu,sbuffer,lsu}/
│   └── vector/vagq/
├── baselines/                  # 完整命名基线和 RTL release 锁
├── dependencies/               # Python/原生工具版本与工具补丁
├── scripts/                    # ucv 启动与公共审计脚本
├── tests/                      # 公共 ucv 与工具补丁的自检
├── skills/                     # 项目工作流、验证方法与审查规范
├── docs/                       # 使用文档、当前状态、经验和来源索引
├── ucv.json                    # 根默认基线、工程注册、public/full 集合
├── pyproject.toml              # 发行包、依赖 Python 版本与 ucv 命令入口
├── ucv.local.example.json      # 本地配置示例，不是当前机器配置
├── README.md                   # 项目入口
├── CONTRIBUTING.md             # 协作与目录约定
└── AGENTS.md                   # 仓库内 Agent 工作约束
```

仓库和发行包叫 `ucv4xs`，命令及公共导入名叫 `ucv`。工程根本身是 Python 包，例如
`suites.memblock.lsq`；DUT 导入示例为 `suites.memblock.lsq.testbenches.replay.env`。

## 工程内

下列 `<testbench>` 是实现包名，通常与 DUT 同名；多个参数化 DUT 可显式共用实现。
允许的职责按需创建，不要求所有 DUT 都有六个实体目录。

```text
suites/<group>/<suite>/
├── __init__.py                 # 工程包入口、ROOT
├── README.md                   # 当前范围与资料入口
├── ucv.json                    # DUT 的真实 top、导出类、构建/收集配方
├── workspace.json              # schema2；DUT 到实现、规格、测试的关联
├── conftest.py                 # 唯一 fixture / pytest 插件注册入口
├── pytest.ini                  # 工程唯一 pytest 配置
├── testbenches/
│   ├── <testbench>/
│   │   ├── README.md           # 具体 DUT 工作入口
│   │   ├── transactions.py     # 或 transactions/；事务数据、身份、合法域
│   │   ├── env.py              # 或 env/；公开环境、端口适配、驱动、采样
│   │   ├── model.py            # 或 model/；独立参考计算，按需
│   │   ├── checker.py          # 或 checker/；比较与不变量，按需
│   │   ├── coverage.py         # 或 coverage/；行为覆盖，按需
│   │   └── tests/              # 功能用例、自检与复用场景
│   └── shared/                 # 真正跨 DUT 组件；同用六职责，不是 DUT
├── tools/                      # 工程专用离线审计与汇总，按需
├── manifest/                   # 来源、字段和哈希元数据，按需
├── docs/spec/{design,verification}/
└── docs/bugs/{open,closed}/
```

- 根 `tests/` 测公共工具，工程的 `testbenches/.../tests/` 测 DUT 或验证环境。
- 工程 `ucv.json` 的 recipe schema 与 `workspace.json` 的 schema 是两套版本号，不能混同。
- DUT 与 shared 的同名职责语义一致；单 DUT 专用实现归该 DUT，shared 不登记 top/native。
- 规格与问题集中在工程 `docs/`，不在每个 testbench 里再复制一套资料。
- 工程根的 `verification_plan.json` 已删除，不创建改名替代文件；现有功能点、合同和
  完成条件在规格正文中维护。

## 本机环境与产物

下表不是待提交的源码目录，也不表示可以直接删除。目录未必在新检出中存在。

| 路径 | 用途 / 管理者 |
|---|---|
| `.ucv/local.json` | 本机镜像、历史来源和可选开发运行环境；不纳入 Git |
| `.ucv/last-run.json` | 最近一次运行路径，供无参 `ucv report` 使用 |
| `.venv/` | 默认项目 Python 环境，由 `ucv setup` 安装 |
| `.venv-uc-toffee/` | 可选本地 Toffee 开发环境，不是默认前置依赖 |
| `.tools/` | 锁定工具源码与原生工具安装 |
| `.cache/sources/` | 锁定源码、递归子模块检出 |
| `.cache/generated/` | 本机完整 RTL/FIRRTL 生成结果与 `generation.json` |
| `.cache/releases/` | release 内容与导入收据 `release.json` |
| `.cache/duts/` | 按构建身份分区的 RTL 闭包、native、`build.json` 和日志 |
| `.cache/locks/`、`.cache/logs/`、`.cache/tmp/` | 编排锁、日志和临时数据 |
| `results/` | 运行收据、覆盖、日志、快照与临时分析 |
| `.history/` | 本地迁移备份；与 Git 中的 `docs/history/` 不同 |
| `build/`、`ucv4xs.egg-info/` | Python 构建/安装产生的数据 |

工程中的 `XiangShan`、`rtl/<dut>`、`dut/<dut>` 是工具管理的本地资源入口，通常链接到
本检出的缓存。不要手改链接或缓存收据。波形、coverage 原始数据和 native 库归产物
位置，不散落到工程源码层；internal 源码及含内部内容的证据保持忽略目录或外部存储。

完整构建/运行收据的位置见[工作空间参考](workspace.md#运行结果文件)。换目录后有绝对
路径依赖的虚拟环境和原生构建需重新建立，不能只移动旧环境后继续认定身份有效。
