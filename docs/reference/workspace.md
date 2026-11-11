# ucv 工作空间参考

本页用于查询参数和文件契约，不是从零安装教程。首次运行见
[MainBTB 教程](../tutorials/bpu-first-ut.md)，常规选跑见[运行指南](../how-to/run-tests.md)，
目录总览见[目录参考](repository-layout.md)。实际 CLI 以 `src/ucv/cli.py` 和 `--help` 为准。

## 命令

| 命令 | 行为 / 依赖 |
|---|---|
| `list [SELECTION…] [--json]` | 列出 DUT 键、有效基线和继承来源；不构建或导入 native |
| `info <suite> [--dut KEY] [--json]` | 只读资源地图，Python 标准库，无安装要求 |
| `init SUITE --group GROUP --dut KEY --top TOP --export-name CLASS` | 新工程创建 schema2 的 `testbenches/<dut>/` 最小骨架；已有工程按其 schema 新增 DUT，保护已有文件 |
| `check <suite> [--json]` | workspace、testbench 结构、README/问题汇总时效和当前文档路径检查；无 native 导入 |
| `docs <suite> [--json] [--write]` | 无 --write 时计算问题汇总与工作入口状态；--write 更新 bugs/README.md 与 DUT/shared README 的生成区块 |
| `prepare <suite> --source-only` | 精确源码与子模块获取；需要 Git |
| `prepare/build <suite> --rtl-source auto\|release\|source` | RTL 提供方选择；默认 auto |
| `prepare/build … --archive PATH --rtl-source release` | 导入匹配锁定 SHA-256 的本地附件 |
| `setup --profile runtime\|full` | 默认 runtime；full 另安装 Mill/firtool |
| `doctor <suite> --stage source\|rtl\|run\|generate` | 按任务检查；默认 run，rtl 阶段检查 release 锁 |
| `build <suite> [--dut KEY] [--jobs N]` | 准备 RTL 闭包、调用锁定 Picker/Verilator、独立进程冒烟并保存真实收据 |
| `run <suite> [--dut KEY] [--workers N] [--seed N] [--output DIR] [--collect-only] [-- PYTEST_ARGS…]` | 当前构建预检与隔离运行；只收集时不做 native 构建预检 |
| `report [RESULTS] [--compare PRIOR]` | 重写本次 summary.json/md；比较基线、用例与已冻结的问题记录，不重新执行测试 |

全局 `--root DIR` 放在子命令前，例如 `ucv --root /path/to/ucv4xs info bpu`。
`./scripts/ucv` 自动定位本检出并优先调用 `.venv/bin/ucv`，未安装时使用
`python3.12 -m ucv`；默认仿真环境仍须通过 `setup` 安装。

| 参数 | 默认值 / 限制 |
|---|---|
| `--dut KEY` | `info/prepare/build/run` 支持重复指定；省略时为所选工程全部 DUT |
| `--jobs N` | `setup/prepare/build` 默认16，必须为正数；资源有限时显式降低 |
| `--workers N` | `run` 默认8，必须为正数，顶层总预算 |
| `--seed N` | `run` 默认1，范围0…4294967295；不保证覆盖测试中显式写定的参数种子 |
| `--output DIR` | `run` 要求目录尚不存在；省略时在根 results/ 中生成唯一目录 |
| `--collect-only` | 仍检查运行工具、导入测试与 internal 来源；不是无需环境的源码扫描 |
| `--archive PATH` | 仅与 `--rtl-source release` 同用，文件须匹配锁定附件哈希 |
| `--source-only` | 仅 `prepare`；不能再指定 RTL 来源或 --archive |
| `--json` | 仅 `list/info/check/docs/doctor`；report 本来输出 JSON 汇总，无此选项 |

### 选择器与参数转发

`list/info/check/docs/doctor/prepare/build/run` 支持多个工程、分组或集合选择器，
省略时选 `public`。`setup/init/report` 不接受这些集合选择器或统一基线选项。

| 选择器 | 含义 |
|---|---|
| `<suite>` | 根 ucv.json 注册的工程键，如 `lsq` |
| `frontend` / `memblock` / `vector` | 对应硬件分组 |
| `public` | 根 profiles 中的公开工程集合 |
| `full` | 根 profiles 中的完整集合，当前包括 internal VAGQ |
| `--require-unified-baseline` | 对上述八类选择命令在执行前拒绝混合有效基线；不证明 DUT 已构建 |

只有 `run` 接受 `--` 后的 pytest 参数。支持显式路径/nodeid、`-k`、`-m` 等选择；
`ucv` 管理 pytest 根、结果、worker 和 BPU 分区，因此拒绝转发 `-c`、`-o`、`-n`、
`--rootdir`、`--junitxml`、Toffee 输出覆盖和分区控制等选项。

`--` 后的路径相对每个所选工程根；多个工程共用同一组转发参数，单工程 nodeid
不应直接用于跨工程集合。当前 `full --require-unified-baseline` 因 VAGQ 的独立基线报错；
该拒绝发生在构建/运行前，不会自动替换基线或跳过 internal。

`init` 同时创建 `docs/README.md`、两个 spec 目录及入口、bugs 汇总与 open/closed 目录，
登记文档导航和所选 DUT 的资源关联。新工程 DUT 的骨架位于 `testbenches/<dut>/`：`__init__.py`、
`transactions.py`、`env.py`、`tests/` 与显式失败的占位 smoke；工程 `conftest.py` 是唯一
fixture / pytest 插件注册入口，`pytest.ini` 以 `testbenches` 为收集根。共享职责按需建立，
初始化不创建空 shared。向已有工程添加 DUT 时保留现有入口
正文，新增资源通过 `info` 展示。模板中的未实现用例仍显式失败，文档骨架不代表验证完成。

## workspace.json

十二工程与新工程的 `workspace.json` 使用 `schema: 2`；版本兼容和本轮范围见
[目录规范](module-layout.md#schema-版本与本轮范围)。`duts` 的键必须已在工程 `ucv.json` 登记。
导航元数据独立于构建配方，调整文档路径不改变构建缓存身份。
顶层 `fixtures` 必须指向工程 `conftest.py`；可选 `loader` 指向实际 DUT 加载入口，
BPU 为 `testbenches/shared/env/dut.py`。workspace 的 schema 与配方 `ucv.json` 的 schema
分别管理；使用 workspace schema2 时，配方使用 `pytest_root: "."`、`tests: ["testbenches"]`，工程
`pytest.ini` 使用 `testpaths = testbenches`。下表字段位于 `duts.<key>`。

| 字段 | 类型 | 含义 |
|---|---|---|
| `testbench` | 字符串 | 必填的实现包名；init 生成与 DUT 同名的值，多个 DUT 可显式共用同一实现；`shared` 为保留名 |
| `design_spec` | 路径或路径列表 | 默认 docs/spec/design/<dut>.md，其次该目录 README.md |
| `verification_spec` | 路径或路径列表 | 默认 docs/spec/verification/<dut>.md，其次该目录 README.md |
| `environment` | 路径或路径列表 | 实现包内查找顺序为 `env/agent/main.py`、`env/agent.py`、`env/__init__.py`、`env.py`；登记路径须位于本 testbench 的 `env/` 内或为其 `env.py` |
| `chisel` | 路径列表 | 相对基线源码根；在线 URL 使用所属仓库的锁定 commit，递归子模块取最深匹配项 |
| `tests` | 路径列表 | 工程相对测试根，默认 `testbenches/<testbench>/tests`；登记路径须位于本 testbench 的 `tests/` 内 |
| `smoke` | 字符串 | 一个具体 pytest nodeid，工程相对路径 |

`testbench` 只合并实现和测试；每个 DUT 的真实 top、Python 导出名和基线仍从 `ucv.json`
解析，产物路径从缓存身份解析。`design_spec` / `verification_spec` 至少登记工程
`docs/spec` 中的入口。`info` 的“已存在”只说明文件存在；构建/运行时才校验哈希与凭据。
schema2 的 `info` 输出使用 `testbench` 字段，并在存在 shared 时链接其独立 README。
`shared` 不在 DUT 表中，没有独立 top、导出类或本地原生库。实现包已有详细合同、功能点或
验证设计时，在 `design_spec` / `verification_spec` 的路径列表中直接登记这些材料，并注明
各自适用基线；工程 README 作为总览。生成模块或参数变体的
`chisel` 指向真实定义和实例化位置，生成名称与源码的对应关系写在所属规格中。

`check` 对未登记的 `chisel` 发出提示；已有对应源码缓存时，登记文件缺失是错误。
源码缓存尚未准备时，仅提示路径未作本地核对，仍可使用固定版本在线链接；需要本地
核对时执行 `ucv prepare <suite> --source-only`。这项检查不下载源码，也不认证源码内容或设计语义。
`check` 要求显式登记环境与测试入口，同时拒绝缺失或过期的 DUT/shared README 和未登记
实现目录；各 README 用 `ucv docs <suite> --write` 刷新。

`tests` 约束文件/目录范围，不会筛选共享 fixture 的参数变体。同一文件覆盖多个 DUT 时，
应传入带参数的完整 nodeid，或选择实际需要的全部 DUT，使构建核验覆盖本次加载对象。
schema2 按 DUT 默认选择时同时包含存在的 `testbenches/shared/tests`；显式 pytest 路径或
nodeid 仍限定实际选择，共享自检不得借此隐式加载未选中的原生 DUT。

## release 锁与缓存

`baselines/rtl-releases.json` 的 `releases` 按完整命名基线索引：

- `baseline_sha256`：完整基线 JSON 按 `ucv.common.digest` 规范化后的哈希，包含递归 gitlink。
- `url`：HTTPS 附件 URL。
- `sha256`：压缩包哈希。
- `package`：包内单一根目录名。

导入核对 `BUILD-PARAMETERS.json` 的源码、配置、生成参数、版本及子模块数量，校验
包内 `SHA256SUMS`、文件集合与 `filelist.f`。现有发布包未逐项列出 gitlink，完整递归锁
身份由仓库中审核过的 `baseline_sha256` 与固定附件 SHA-256 绑定。

`.cache/releases/<release-key>/` 保存原包内容和 `release.json`；
`.cache/generated/<generation-key>/` 继续保存真实本机生成与 `generation.json`。
闭包 `source.json` 和构建 `build.json` 携带来源。两种提供方并存时核对 RTL 字节。

当前 DUT 构建身份包含 `pipeline_version: 2`、完整工程配方、有效基线、DUT、工具锁
和构建选项。配方收集根从 `modules` 改为 `testbenches` 也会改变身份；旧目录或旧
smoke 不能自动成为当前身份的凭据。用 `ucv build` 建立真实收据，完整 RTL 缓存仍按自身身份与哈希复用。

## 运行结果文件

路径相对 `--output` 或工具生成的本次结果根；失败或中断运行可能缺部分产物。
`<task>` 通常是工程名，BPU 按 owner 分区可为 `bpu-<scope>`。

| 文件或目录 | 内容 |
|---|---|
| `run.json` | 工具、基线、问题快照、源码文件哈希、选择、种子、任务命令/状态及结束源码身份 |
| `<suite>-builds.json` | 所选 DUT 的 current key、RTL/native 哈希及来源；collect-only 不生成 |
| `cases/<task>/cases.json` | 实际 collected 列表、逐节点判定及阶段结果、退出码 |
| `logs/<task>.log` | 实际子进程命令和输出 |
| `<task>/manifest.json` | Toffee 执行与覆盖完整性、产物列表/哈希；有实际执行时核对 |
| `bpu-partition.json`、`collection/` | BPU native owner 分区与收集记录，按实际选择存在 |
| `summary.json`、`summary.md` | `ucv run/report` 生成的汇总和证据缺口 |

默认 `report` 使用 `.ucv/last-run.json`；它不是按时间扫描目录寻找“最新成功运行”。
`report --compare` 需要旧目录的 `summary.json`，比较只写入新目录的汇总。

## 报告字段与退出码

| 字段 | 含义 |
|---|---|
| `run_status` | 编排/执行状态；源码在运行中变化会成为完整性 ERROR |
| `counts` | 实际逐用例判定，包含模型/环境自检，不全是硬件功能用例 |
| `hardware_verdict` | 综合实际判定、收据/覆盖完整性及冻结问题后的汇总，不认证未选择范围 |
| `selected_duts`、`selection` | DUT、pytest 参数、种子和 collect-only 标志 |
| `verification_source` | 运行开始保存的验证源码指纹，含工程 Markdown |
| `gaps` | 开放问题、缺收据、覆盖未完成/变更等阻塞或完整性缺口 |
| `migration_acceptance` | 当前汇总保留 `NOT_CERTIFIED`；不会因部分用例通过自动变成迁移签核 |
| `comparison` | 可选的基线、源码、选择、nodeid/判定和问题快照差分 |

真实 `FAIL/ERROR/XPASS` 优先使硬件汇总为 `FAIL`。没有这些失败，但存在缺口、未完成
或只是 collect-only 时为 `INCOMPLETE`；其余按实际 `UNCERTAIN` 或 `PASS` 汇总。
`UNCERTAIN` 不计 PASS；没有其它阻塞时可返回0。历史 XFAIL/SKIP 和未尝试范围仍须
结合工程规格审查，不能从汇总绿色推出完整硬件签核。

- `run`：执行状态与硬件汇总均为 PASS/UNCERTAIN 才返回0，否则返回1。
- `report`：硬件汇总为 PASS/UNCERTAIN 返回0，否则返回1；返回1也可能已经成功写出报告。
- `check/doctor/build/prepare`：正常完成时按检查/构建结果返回0或1；`list/info/docs/init/setup`
  的正常命令路径返回0。统一的配置、文件或参数错误可返回2；argparse 语法错误也可返回2。

退出码不替代报告。收集、构建/冒烟、功能判断、适配接受与覆盖签核分别陈述。

## 当前文档导航

仓库根和工程根可放 `docs/navigation.json`，格式为 `{"schema":1,"current":["README.md",…]}`。
路径相对该根。`check` 验证当前页面及其相对文件链接，JSON 输出额外列出未索引 Markdown。
未索引页面不等同于失效内容；工具不自动删改或改写历史。
登记的规格和问题记录也参与链接检查。指向结果、源码检出或生成缓存的链接缺失时列为
不可用提示；它们不要求阅读文档前完成构建，但也不据此获得已核验证据信用。

可选的 `relocations` 对象记录旧文档路径到当前位置的映射，两端均相对该根。
`check` 检查目标文件并在 JSON 资源清单中返回映射；它只提供位置导航，不能证明内容
逐字节相同。冻结证据中的原路径、命令、日期与 SHA-256 保留原义。若当前文档已修改，
应从原 Git 版本或原产物核验旧哈希，不能用当前哈希覆盖旧执行身份。

## 问题记录

每个问题是一份 `docs/bugs/open/<ID>-<slug>.md` 或 `closed/` 下的 Markdown。
`open/closed` 是唯一当前状态。文件含一个 `ucv-bug` JSON 围栏，例如（示例 ID 与基线）：

````markdown
# UNIT-BUG-001：请求在恢复后丢失

```ucv-bug
{
  "id": "UNIT-BUG-001",
  "title": "请求在恢复后丢失",
  "kind": "investigation",
  "versions": [
    {"baseline": "release-A", "status": "open", "evidence": ["run-id / cases.json / sha256:…"], "note": "差异已复现，根因待确认"},
    {"baseline": "release-B", "status": "unverified", "evidence": [], "note": "尚未复验"}
  ]
}
```

## 现象与独立预期依据
## 触发步骤、最小用例与正常对照
## 根因、影响及合法输入范围
## 版本复验与证据
````

- `id`：工程内唯一且稳定；跨工程报告使用 `<suite>::<id>`。
- `title`：摘要；`kind`：`rtl / verification / spec / investigation`。
- `versions`：可选的逐基线结论；`status` 为 `open / closed / unverified`。
  closed 条目必须引用证据。完整设计配置、验证源码和运行身份在引用的证据中记录。
- `resolution`：移入 closed 必填对象，含 `reason`（`fixed / invalid / duplicate / retired`）、
  非空 `evidence` 字符串列表及 `note`。关闭原因和适用范围由人工 review；工具校验字段结构。
- `evidence` 是带上下文的引用，可含版本固定文档、运行位置、收据及哈希。
  字符串存在不代表产物已核验或当前可访问，关闭前须实际核对。

`ucv docs` 扫描记录并输出汇总；`--write` 只改生成区块，保留周围人工内容：问题汇总位于
`docs/bugs/README.md` 的 `<!-- ucv:bugs:start -->` 到 `<!-- ucv:bugs:end -->`；testbench 入口
位于 `testbenches/<testbench>/README.md` 及已有的 `testbenches/shared/README.md`，
继续使用稳定标记 `<!-- ucv:module:start -->` 到 `<!-- ucv:module:end -->`。
缺少 README 时创建汇总或工作入口；重复执行内容不变。`ucv check` 拒绝
重复编号、不完整关闭声明、过期的已登记汇总和过期工作入口。文档生成不会修改问题
分类、目录状态或硬件判定。
汇总同时显示当前有效基线的复验结论；没有该基线记录时显示“未登记复验”，历史关闭
不能借目录归档自动变成当前版本的已验证修复。

`ucv run` 将问题记录、目录状态及文档哈希写入运行快照。`report --compare` 按稳定 ID
输出新增、移除、关闭、重开和记录变化；没有旧快照时列出不可比较工程，不把缺失当修复。
这些是登记状态差分，不证明测试选择完整或修复成立；应同时核对报告中的基线和 nodeid 差分。
新运行显式标记 `acceptance_source='issue-records'`，按冻结的问题快照和实际运行完整性
评估验收：位于 `open/` 且在当前基线仍开放或未复验的问题，使纯 PASS 汇总为
`INCOMPLETE`，实际 case 计数保留，真实 FAIL/ERROR 优先。无此标志的历史运行沿用原
解释；若包含旧 `residuals` 字段，仍按该次冻结内容读取，不用当前问题记录重标历史。
功能标记统计显式使用 `scope=collected-test-markers`，只来自实际收集标签，不是完整计划分母。
比较还列出两侧 DUT/pytest 选择、种子，以及验证源码指纹是否相同；旧报告缺少身份字段时
保留未知值，不默认相同。
源码身份包含工程 Markdown，因而规格/合同/问题在运行中变化会触发完整性错误。

`check` 是结构检查：不执行仿真、不判断自然语言规格是否充分、不授予设计确认或硬件通过。
