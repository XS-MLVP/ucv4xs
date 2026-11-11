# ucv4xs 协作约定

本仓库是基于 UnityChip / toffee 的香山 UT 集合。命令和公共 Python 包是 `ucv`，仓库与发行包名是 `ucv4xs`。当前阶段及未完成事项以 [docs/status.md](docs/status.md) 为准。

## 从哪里开始

- 多人或 AI 协作先读 [CONTRIBUTING.md](CONTRIBUTING.md)，在既有工程/DUT目录中工作；目录与命名遵循同一约定，不为每位贡献者新建验证外壳。
- 编排、构建、基线或工程接入：按需读取 [项目工作流 skill](skills/ucv4xs-workflow/SKILL.md)。
- 模型、驱动、检查器或失败归因：先定位工程的合同，再查 [经验索引](docs/lessons/README.md) 中相关案例。
- 阅读或修改历史报告时保留其日期、基线和结论边界；当前命令从 [README](README.md) 和 `src/ucv/` 获取。
- 工作空间用 `ucv info/init/prepare/check` 管理，运行汇总用 `ucv report` 生成。优先更新已有主题；临时分析留在结果目录。使用文档遵循 [文档维护](docs/how-to/maintain-docs.md)，设计/验证 spec 按工程规格组织。
- 工程规格统一放 `docs/spec/{design,verification}/`，问题放 `docs/bugs/{open,closed}/`；README 负责当前汇总和入口，问题索引用 `ucv docs <suite> --write` 生成。同一问题保留稳定 ID、各基线结论和处置证据；工程不新增泛化 history 目录。通用工具要求使用工程/DUT 参数，具体设计只用于明确标注的示例。
- 功能点、合同与未证明范围维护在既有规格正文；真实缺陷与配置/观察/集成边界分别说明。工程根的 `verification_plan.json` 已删除，不恢复或改名重建替代计划文件；历史提及和哈希清单保持原字节。

## 结构边界

- 公共编排放在 `src/ucv/`，不导入工程领域模型。十二工程统一使用 workspace schema2：`suites/<group>/<suite>/testbenches/<dut>/` 放 DUT 实现和 tests，`testbenches/shared/` 放真正跨 DUT 复用的组件。双方同用 env、transactions、model、checker、coverage、tests 六职责；除 tests 为目录外，按需选文件或同名包，不造空壳。规格和问题集中在 docs/。
- 新工程/DUT 用 `ucv init` 生成，`ucv docs --write` 生成 DUT 与 shared 的独立工作入口，`ucv check` 强制校验结构。schema2 以 `duts.<name>.testbench` 显式关联实现；参数化 DUT 可共用实现。schema1 兼容边界与本轮范围见 [testbench 目录规范](docs/reference/module-layout.md#schema-版本与本轮范围)。
- shared 与 DUT 的同名职责语义一致；单 DUT 专用代码归该 DUT。shared 实现不得反向导入具体 DUT 或工程 tools；shared/tests 可检查集成引用。shared 是保留名，不是 DUT，不登记独立 top 或本地原生库。工程唯一 conftest.py 注册 fixtures/pytest 插件；DUT 专用参数生成归其 tests/插件，离线汇总与审计命令归 tools/。
- 工程根、实现包层与集中资料层级采用按 schema 的封闭白名单；额外空目录、缓存残留目录、隐藏目录和未授权符号链接同样报错。允许项统一定义在 `ucv.layout`，不为个别工程放宽；归档旧目录前确认无活动占用并记录清单。
- 工程根直接作为 `suites.<group>.<suite>` Python 包；不新建 *verify/common 外壳，不用通用顶级短导入。共享代码按职责命名，工程 ROOT 从包入口解析；安装包不携带 DUT/RTL/结果。
- 从配置解析路径，使用 `ucv.runtime` 等公共入口接入源码、工具和外部历史证据；新增运行逻辑不硬编码个人工作区路径。
- 工程隔离进程运行，BPU 原生库按 DUT 分区；顶层控制总 worker 预算。
- 首版不接 CI；依赖和原生工具安装在本检出的 `.venv/`、`.tools/`，版本及补丁由清单管理。

## RTL 与构建

- 当前所有工程使用 DefaultConfig；从完整香山生成 RTL，再提取 DUT 实例闭包。BPU 同样使用该链路，接口差异在验证侧适配。
- 根、分组、工程可引用完整的命名基线，最近显式引用优先。工程内所有 DUT 共用同一基线，不增加单 DUT commit/config override。
- 变更源码、子模块、工具、生成参数或设计补丁时更新对应完整清单。设计补丁进入基线，工具补丁进入 `dependencies/`，并记录哈希。
- 提取闭包时保留 RTL 字节。新增 DUT 需在工程 `ucv.json` 声明真实 top 和导出名；不通过生成专用 Scala 入口维持旧接口。
- 构建语义变更更新缓存身份；不手改缓存伪造构建成功凭据。搬迁仓库后重新建立有绝对路径依赖的环境和原生构建。

## 验证与结论

- 编排或工具补丁变更运行 `.venv/bin/python -m pytest -q tests`；文档变更核对链接、配置和命令即可。按实际变更选择工程回归，避免无关全量仿真。
- DUT 构建、冒烟、功能判定、覆盖结果分别说明。保留真实 FAIL / ERROR / XFAIL / XPASS / SKIP；不为得到全绿扩大豁免或删除反例。
- 参考模型的关键期望应有合同或独立依据；修正误报或漏检时保留合法对照和针对性错误对照。经验来源和适用范围写回所属工程文档。
- 回归使用新输出目录，保留实际选择、版本、种子和日志。不同源码基线的结论分开记录；公开集合的统一验收启用 `--require-unified-baseline`。

## 资产与空间

- Git 保存验证代码、配方、版本锁、补丁、经验和必要的哈希索引。生成 RTL/FIRRTL、原生库、波形、完整运行结果和本机配置放在忽略目录或外部存储。
- VAGQ internal 源码、生成产物和包含内部源码的证据保持外部接入。文档中引用历史结果不代表当前环境已复现。
- 在用户要求的清理范围内，先确认运行不再活动及文件用途，保留必要判定、日志和删除清单。中间数据删除后明确记录其不可用，不改写旧结果为通过。
- 更新发布内容时执行 `python3.12 scripts/audit-assets.py`，审查 Git 实际跟踪的文件；从 Git 推送，避免把工作目录整体打包上传。

## 可复用资料

[基线与构建](docs/baselines.md)、[编译构建经验](docs/lessons/build-and-toolchain.md)、[本地来源配置](docs/local-configuration.md)、[维护与验收](docs/maintenance.md)。新增经验保留问题、错误假设、修正依据、检查位置和剩余限制。
