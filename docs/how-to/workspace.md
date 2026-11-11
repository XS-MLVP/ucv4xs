# 准备工作空间

本指南解决“找资源、准备源码/RTL、接入 DUT”；已准备好的工程如何选跑与读报告，见
[运行测试与查看报告](run-tests.md)。只查资料不需要安装仿真工具，也不要从全仓构建开始。

从仓库根使用 `./scripts/ucv`；它在环境安装前也能运行只依赖 Python 的命令。
下文 `<suite>`、`<group>`、`<dut>`、`<testbench>` 和 `<test-nodeid>` 是需要替换的占位符，
可用 `ucv list` / `ucv info` 查询实际值。完整具体示例见
[首次 UT 教程](../tutorials/bpu-first-ut.md)。

## 只找资料或准备源码

```sh
./scripts/ucv info <suite> --dut <dut>
./scripts/ucv info <suite> --json
./scripts/ucv prepare <suite> --source-only
```

`info` 是只读操作。源码获取会检出完整锁定 commit、递归子模块和补丁，但不运行生成器。
只读在线源码与写 spec 时可以直接使用 `info` 提供的固定版本链接。属于递归子模块的文件
链接到该子模块锁定的仓库和提交；生成模块的定义/实例化关系见所列模块规格。
`design_spec` / `verification_spec` 同时列出工程总览与已登记的模块详细材料。
`ucv check <suite>` 会提示未登记源码，以及尚未准备本地源码的情况；已有源码缓存中找不到
登记文件时则报错。schema2 的 `info` 显示 `testbench`，并链接已有 shared 的独立 README。
internal 来源按[本地配置](../local-configuration.md)接入。

## 使用 release RTL

先用 `./scripts/ucv doctor <suite> --stage rtl` 核对 release 锁和所选基线，再准备闭包：

```sh
./scripts/ucv prepare <suite> --dut <dut> --rtl-source release
```

已提前取得同一锁定附件时，可从本地导入；这只替代 RTL 下载，不保证整个工具/运行链离线：

```sh
./scripts/ucv prepare <suite> --dut <dut> --rtl-source release --archive /path/to/locked-rtl.tar.gz
```

本地附件也必须匹配 `baselines/rtl-releases.json` 的 SHA-256。
完整包缓存于 `.cache/releases/`，工程 `rtl/<dut>/` 指向闭包；导入收据为 `release.json`，
生成参数仍是发布者原件。导入过程中不伪造本机 RTL 生成命令。

## 从源码完整生成

需要基线锁定的生成工具和对应的宿主运行环境：

```sh
./scripts/ucv setup --profile full --jobs 4
./scripts/ucv doctor <suite> --stage generate
./scripts/ucv prepare <suite> --dut <dut> --rtl-source source
```

`--dut` 选择提取与原生构建范围，完整设计生成仍共享工程的基线与生成参数，
具体配置和工具需求见基线清单及[基线规则](../baselines.md)。

默认 `--rtl-source auto` 优先核验已有完整本地生成；否则使用锁定 release。
无 release 时提示显式生成，避免意外启动高资源任务。

## 创建新工程或接入新 DUT

填写工程、分组、真实 top 和导出类名：

```sh
./scripts/ucv init <suite> --group <group> --dut <dut> \
  --top <ActualRtlTop> --export-name <DutClass>
./scripts/ucv info <suite>
```

`init` 为新工程创建 schema2 workspace、工程根 Python 包和 `testbenches/<dut>/` 最小骨架
（事务、环境占位和 `tests/`），生成集中规格模板、唯一 fixture/插件入口、配方并注册工程。
配方 `tests` 为 `["testbenches"]`，`pytest.ini` 的 `testpaths` 为 `testbenches`。
若工程已存在则按其 schema 加入新 DUT，保留其 fixture 与现有文件；适用范围见
[目录规范](../reference/module-layout.md#schema-版本与本轮范围)。新工程暂不加入
`public/full` 集合，完成接入后维护根集合。

需要填写的内容：

1. `docs/spec/design/<dut>.md`：设计要求、接口、时序、依据与 review。
2. `docs/spec/verification/<dut>.md`：场景、合法前态、独立预期、观察、覆盖和完成条件。
3. `workspace.json` 的 `chisel`：相对基线源码根的路径。
4. `testbenches/<testbench>/env.py`（复杂时 `env/`）与工程 `conftest.py`：实际 Toffee 环境、
   fixture 注册和 DUT 生命周期。
5. `testbenches/<testbench>/tests/test_<dut>_smoke.py`：用真实事务检查替换显式失败占位。
6. 参数化共享实现：多个 DUT 的 `workspace.json` 以 `duts.<name>.testbench` 显式指向同一实现；每个 DUT 仍在
   `ucv.json` 登记自己的真实 top 和导出名。

DUT 与 `testbenches/shared/` 同用 `env`、`transactions`、`model`、`checker`、`coverage`、
`tests` 六类职责：tests 为目录，其余按需选单文件或同名包。shared 仅承接真正跨 DUT 的
组件，没有独立 top 或原生库；只有单 DUT 使用的实现归该 DUT。共享加载器可登记为
`loader: "testbenches/shared/env/dut.py"`，通用插件归 `shared/env/pytest_plugins/`；DUT 专用
参数生成归其 tests/插件，均由工程唯一 conftest 注册，离线汇总与审计归 tools。
各实现包根不放 `agent/`、`conftest.py` 或 `pytest.ini`。重复初始化和覆盖现有路径会报错。规格模板
不需要 RTL，原生 build 的通用冒烟由 ucv 提供；初始化产生的功能用例在实现前明确失败。
`ucv docs <suite> --write` 生成 DUT 与已有 shared 的独立 README 工作入口。
工程根和集中资料目录也遵循[封闭白名单](../reference/module-layout.md#固定层级使用封闭白名单)。
`init` 给已有工程添加 DUT 前会检查布局；额外目录（包括空目录、旧缓存和隐藏目录）、
非指定符号链接或根目录散落波形都会报错。先核对用途与占用并归档，再重新初始化。

## 检查与运行

```sh
./scripts/ucv docs <suite> --write
./scripts/ucv check <suite>
./scripts/ucv build <suite> --dut <dut> --jobs 2
```

`docs --write` 只用于你新增/修改了资源或问题记录、需要刷新生成入口的情况；单纯运行
现有用例不必先写文档。构建需已完成 `setup --profile runtime` 或 `full`，工具安装步骤
见[首次教程](../tutorials/bpu-first-ut.md#4-安装仿真工具并构建-mainbtb)。

单 DUT 使用 `workspace.json` 登记的 `tests`；schema2 常规入口为
`testbenches/<testbench>/tests`，默认选择同时包含存在的 `testbenches/shared/tests`。
显式传入其它 DUT 的测试路径会被拒绝；显式路径或 nodeid 仍限定实际选择。多 DUT 可重复 `--dut`。
共享参数化测试仍须用完整 nodeid 选择变体；仅指定 DUT 键不会自动过滤 fixture 参数。
下一步按[运行指南](run-tests.md)选择用例、使用新结果目录并读取实际收据；新增工程的
显式失败占位用例必须先实现，不将构建冒烟或文档生成当作功能验证通过。

问题维护到 `docs/bugs/open/` 或 `closed/` 的稳定编号记录，问题汇总与 testbench README 的生成
区块由 `ucv docs --write` 刷新。移动记录和改变处置必须有依据；具体见
[文档与问题维护](maintain-docs.md)。
