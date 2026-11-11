# 工程与 testbench 目录规范

**验证谁，实现和测试就归谁；设计/验证规格与 Bug 集中在工程 `docs/`。**

## schema 版本与本轮范围

目录由工程 `workspace.json` 的 schema 决定，同一版本使用通用门禁，不按工程名放行。
新建工程的 `ucv init` 与本轮十二工程统一迁移使用 **schema2**；工具保留严格的
**schema1** 兼容。全仓既有 **137 DUT / 114 实现包**的映射保持，shared 不计作 DUT 实现包。

| 契约 | schema2：当前十二工程与新工程 | schema1：旧工作空间兼容 |
|---|---|---|
| DUT 实现目录 | `testbenches/<testbench>/`，通常与 DUT 同名 | `modules/<module>/` |
| workspace 归属字段 | 每个 `duts.<name>.testbench` 显式登记 | `duts.<name>.module`，省略时与 DUT 同名 |
| 跨 DUT 共享代码 | `testbenches/shared/`，同用六职责 | `runtime/`，沿用既有运行职责 |
| 配方收集根 | `tests: ["testbenches"]` | `tests: ["modules"]` |
| pytest 收集根 | `testpaths = testbenches` | `testpaths = modules` |
| `ucv info` 的实现字段 | `testbench` | `module` |

两种 schema 都使用工程根 `conftest.py`、`pytest_root: "."` 和封闭白名单；实现归属字段、
收集根及源码目录不得混用。向已有工程 `init` 新 DUT 时沿用其 schema，初始化不会隐式
迁移工程。schema1 的 `modules/`、`runtime/` 仍受原严格格式约束；例如 ICache 当前
用例路径为 `testbenches/metabank/tests/`。下文以 schema2 说明新结构；schema1 的实现层
名称按上表对应，规格、资产与验收规则相同。

## BPU 示例

```text
suites/frontend/bpu/
├── ucv.json                    # 基线继承、真实 DUT top、构建与运行配方
├── workspace.json              # schema2；DUT 到 testbench、规格、环境和用例的关联
├── conftest.py                 # 全工程唯一 fixture / pytest 插件注册入口
├── pytest.ini                  # testpaths = testbenches
├── docs/
│   ├── spec/{design,verification}/
│   └── bugs/{open,closed}/
├── testbenches/
│   ├── bpu/                    # BPU 顶层 DUT，包括子模块组合场景
│   ├── mbtb/                   # MainBTB DUT
│   │   ├── README.md           # 由配置生成的工作入口
│   │   ├── transactions/       # 查询、训练反馈、预测结果的数据类型
│   │   ├── env/                # 如何与 RTL 交互
│   │   │   ├── agent/          # 对测试公开 reset/predict/train 等操作
│   │   │   ├── bundle/         # 真实端口绑定
│   │   │   ├── driver/         # 发送与保持请求
│   │   │   └── monitor/        # 采样与解码
│   │   ├── model/              # 独立计算应该得到什么
│   │   ├── checker/            # 比较实际结果、检查不变量
│   │   ├── coverage/           # 统计已检查的行为
│   │   └── tests/              # 功能用例、环境自检、复用场景
│   ├── ras/
│   ├── shared/                 # 跨 DUT 组件；不是 DUT
│   │   ├── README.md           # 工具生成的共享职责与自检入口
│   │   ├── env/                # 加载、通用绑定/驱动/采样、pytest 插件
│   │   ├── transactions/       # 跨 DUT 共用的数据类型与合法域
│   │   ├── model/              # 跨 DUT 独立参考计算
│   │   ├── checker/            # 跨 DUT 比较与不变量
│   │   ├── coverage/           # 跨 DUT 覆盖机制与产物支持
│   │   └── tests/              # 共享自检、集成引用检查
│   └── …
└── tools/                      # 离线审计与汇总命令
```

BPU 工程是多个 DUT 的容器。BPU 顶层自身的驱动、模型和用例归 `testbenches/bpu/`。
图中职责按需存在，文件与同名包二选一，不为树形完整创建空壳。

## 固定层级使用封闭白名单

以下规则由 `src/ucv/layout.py` 按 schema 统一实现。检查读取**实际磁盘条目**，
包括 Git 忽略项；名称和类型必须同时匹配，白名单外的空目录、仅含缓存的目录、
隐藏目录、普通文件、符号链接及断链均报错。

| 层级 | 允许的直接子目录 | 允许的直接文件 |
|---|---|---|
| 工程根 | `testbenches/`、`tools/`、`docs/`、`dependencies/`、`manifest/`；本地产物 `dut/`、`rtl/`、`results/`；标准缓存 `__pycache__/`、`.pytest_cache/` | `__init__.py`、`conftest.py`、`pytest.ini`、`README.md`、`ucv.json`、`workspace.json`、`requirements.txt` |
| `testbenches/` | `workspace.json` 对已登记 DUT 声明的 testbench 名、保留名 `shared`，以及两个标准缓存目录 | `__init__.py` |
| `testbenches/<dut>/` 与 `testbenches/shared/` | `env/`、`transactions/`、`model/`、`checker/`、`coverage/`、`tests/`，以及两个标准缓存目录 | `__init__.py`、`README.md`；前五种职责可用同名 `.py` 文件替代目录 |
| `docs/` | `spec/`、`bugs/`、`guides/` | `README.md`、`navigation.json`、`path-migrations.json` |
| `docs/spec/` | `design/`、`verification/` | `README.md` |
| `docs/bugs/` | `open/`、`closed/`、`evidence/` | Markdown 汇总与既有支持页面；正式问题归 open/closed |
| `dependencies/` | 无 | `versions.json`，指向仓库统一依赖锁 |
| `manifest/` | 无 | `.json`、`.sha256`、`.md` 元数据文件 |

白名单表示允许存在，按需创建；必需入口仍由 `init/check` 校验。工程根唯一允许的
符号链接名是 `XiangShan`，由 `prepare/build` 管理；它不能换成实际目录或普通文件。
`dut/<dut>`、`rtl/<dut>` 属于工具管理的本地产物链接。上述固定源码/资料层级不接受
符号链接替代目录或文件。

例如工程根出现 `drivers/`、`monitors/`、`checkers/`、`tests/`、`.scratch/` 或
`memory-direct.fst`，即使没有 Python 源码也会使 `ucv check` 失败。缓存只能留在
标准缓存位置；波形和运行资料归 `results/`，不能散落在工程根。

六个职责块内部按具体领域组织，shared 与 DUT 使用同样规则；`tools/` 按离线命令职责组织，
规格正文按主题组织。这些内部拆分沿用已有命名，不在固定层级另建平行验证目录。
需要新增固定层级名称时，统一修改门禁与本规范，不能给个别工程添加放行配置。
已删除的工程根 `verification_plan.json` 不属于白名单；功能点、合同和完成条件归既有
`docs/spec/` 正文，缺陷归 `docs/bugs/`，不建立改名替代计划文件。

## DUT 与 shared 同用六类职责

| 位置 | 内容 |
|---|---|
| `transactions.py` 或 `transactions/` | 事务数据类型、合法域、单位和身份 |
| `env.py` 或 `env/` | 公开环境 API、加载、端口、驱动、监视器、组件装配与运行插件 |
| `model.py` 或 `model/` | 独立参考计算；需要时设置 |
| `checker.py` 或 `checker/` | 比较规则、性质、不变量；需要时设置 |
| `coverage.py` 或 `coverage/` | 行为覆盖、覆盖收集与产物支持；需要时设置 |
| `tests/` | pytest 用例、自检；多处复用的流程放 `scenarios/` |

简单职责优先用单文件；复杂后再展开同名包。同一职责不能同时存在文件和目录，
`tests` 只能是目录。DUT 的 `README.md`、包入口、环境入口和 `tests/` 必须可定位；
shared 按真实共享需求建立相应职责及独立 README，不要求凑齐六个空壳。
`ucv init` 只生成最小可编辑骨架，未实现的冒烟用例显式失败；没有共享需求时不生成 shared。

测试描述场景，调用公开环境；驱动负责激励，监视器负责观察，checker 使用独立预期。
共同的数据定义放事务或模型，避免生产实现反向依赖测试流程。模块可以引用其他模块的
公开参考接口。shared 的职责与 DUT 同名同义，不能把任意跨目录文件都归为 env 或 tools。

### 共享边界与 BPU 落位

- 仅一个 DUT 使用的代码归该 DUT；实际跨 DUT 复用的组件才进入 shared。
- shared 实现不得反向 import 具体 DUT 或工程 `tools`。需要 DUT 参数或策略时由调用方
  显式传入；`shared/tests` 可检查具体 DUT 的集成引用，这不授权共享实现反向依赖。
- `shared` 是保留名，不能登记为 DUT 或 DUT 的 testbench；它没有独立 RTL top、导出类
   或本地原生库。需要真实原生 DUT 的自检归该 DUT 的 tests，明确实际加载对象并由对应
   DUT 管理构建；默认附带的共享自检不应引入额外 DUT 所有权。
- 工程唯一 `conftest.py` 注册 fixtures 与 pytest 插件。DUT 专用参数生成归其 `tests/`
  或 tests 内插件；跨 DUT 通用插件归 `shared/env/pytest_plugins/`。离线汇总与审计命令归
  工程 `tools/`，运行所需的覆盖实现归 coverage。

以下是 BPU 的具体落位，路径均相对工程根：

| 内容 | 位置 |
|---|---|
| BPU 顶层 plain sampler | `testbenches/bpu/env/bundle/plain_sampler.py` |
| BPU 顶层 replay | `testbenches/bpu/coverage/replay.py` |
| BPU 顶层 timing 场景步骤 | `testbenches/bpu/tests/scenarios/timing.py` |
| 通用 ports/bundle、driver、monitor 机制 | `testbenches/shared/env/{bundle,driver,monitor}/` |
| 共享 DUT 加载器 | `testbenches/shared/env/dut.py`，由 workspace 的 `loader` 登记 |
| 通用 pytest 插件 | `testbenches/shared/env/pytest_plugins/` |
| 通用覆盖、native 覆盖、exports、local_guards | `testbenches/shared/coverage/` 下按职责组织 |

这些落位使用通用 schema2 约束；BPU 顶层自身的功能不会因名称为 bpu 而自动成为共享组件。

## DUT 与参数化实现

初始化生成与 DUT 同名的 testbench。共享参数化实现时，在 `workspace.json` 显式声明；
下面是新工程中参数变体 `leaf_0` 共用 `leaf` 实现的 schema2 示例：

```json
{
  "schema": 2,
  "fixtures": "conftest.py",
  "duts": {
    "leaf_0": {
      "testbench": "leaf",
      "environment": "testbenches/leaf/env/__init__.py",
      "tests": ["testbenches/leaf/tests"],
      "design_spec": "docs/spec/design/README.md",
      "verification_spec": "docs/spec/verification/README.md"
    }
  }
}
```

每个 DUT 仍在 `ucv.json` 声明真实 top、导出名，共用工程基线。多个实例可以指向同一
testbench 包和参数化测试。`--dut` 限制测试文件范围；schema2 默认选择同时包含存在的
`shared/tests`。参数化用例还需选择实际加载的全部 DUT 或完整参数化 nodeid。
testbench 内不得按测试路径暗中选择不同模型。

fixture 在工程 `conftest.py` 显式注册，DUT 相关实现可放其 `tests/fixtures.py`。一个工程
保留一个 pytest 根，DUT 和 shared 下都不另设 `pytest.ini` 或 `conftest.py`。

## 生成、检查与维护

```sh
# 示例：新增独立 DUT；suite/group/top 均由实际设计确定。
./scripts/ucv init demo --group frontend --dut leaf --top Leaf --export-name LeafDut
./scripts/ucv info demo --dut leaf
./scripts/ucv docs demo --write
./scripts/ucv check demo
```

- `init` 生成 testbench、测试、集中规格和配置，遇到已有文件或未登记实现目录即拒绝覆盖；
  给已有工程添加 DUT 前，先拒绝违反目录规范的工程，避免写入部分骨架。
- `docs --write` 更新 DUT、已有 shared 的独立 README 和问题汇总的生成区块，保留人工说明；
  shared 入口链接实际存在的职责、工程规格和自检，不生成虚构的 DUT 构建命令。
- `check` 校验封闭白名单、所有 DUT 的归属、资源位置、重复布局、缺失入口及过期 README；
  只读报告错误，清理前需核对用途与活动状态并保留归档清单。
- `audit-suite-layout.py --strict` 使用同一结构规则，并检查 fixture/namespace 接线。
  `audit-assets.py` 同样调用此白名单，根工具回归覆盖全部已登记工程。
  `--require-transaction-boundary` 另外报告引脚级耦合；结构通过不等于硬件通过。

旧路径导航记在工程 `docs/path-migrations.json`。冻结报告、问题中的原始路径、命令、
日期、哈希和判定保留原义；路径映射只帮助找到当前实现，不能证明字节或执行身份相同。
目录调整后的新运行使用新 nodeid；比较历史记录时必须先声明路径映射，再核对具体用例。
同文件拆分到多个 DUT 时，映射可细到 `文件.py::测试函数`；`ucv.layout.relocated_name`
保留参数后缀，`relocated` 返回当前文件。最长匹配优先，历史原文不经导航函数重写。
