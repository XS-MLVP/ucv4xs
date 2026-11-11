# 基线与构建

本页解释设计基线、RTL 来源与构建身份的关系。准备源码、导入 release 或本机生成的
操作步骤在[工作空间指南](how-to/workspace.md)，具体字段/收据见
[工作空间参考](reference/workspace.md#release-锁与缓存)。编译问题可查
[构建经验](lessons/build-and-toolchain.md)，不从历史成功记录推断当前已构建。

## 为什么锁定完整基线

源码 commit 只确定顶层仓库，不足以确定递归子模块、DefaultConfig、生成器参数和补丁。
因此一次有效基线是完整命名定义；同一工程全部 DUT 共用它，不能在一个 DUT 中悄悄
替换 commit/config 来维持旧接口。不同基线的功能结论也不能直接合并。

```text
命名基线 → 完整香山 DefaultConfig RTL → 实例依赖闭包 → DUT native 包 → 测试运行
```

release 与本机生成是取得完整 RTL 的两种来源，不是两套硬件设计；两种来源并存时仍
核对实际 RTL 字节。构建成功/冒烟只证明产物可用，功能、独立检查与覆盖需要后续运行。

## 查询有效基线

```sh
./scripts/ucv list full
./scripts/ucv info <suite> --dut <dut>
```

`<suite>`、`<dut>` 为实际工程/DUT 键。命令显示完整源码身份、设计配置和继承位置；
当前状态从工程 README 和对应运行收据读取。旧报告的结论只属于其记录的版本。

## 本仓库配置示例与历史边界

本节保留 2026-11-02/03 的来源变更事实，包含当时尚未执行的工作。当前构建与适配范围
看[阶段状态](status.md)及对应工程收据，不把下面“其余九个工程”的历史描述当作现状。

2026-11-02将公开根默认切换为
[`public-a0c2a26cb`](../baselines/public-a0c2a26cb.json)，固定上游`kunminghu-v3`
当次分支头`a0c2a26cbe3c862175174bad03a1a23c406315ed`（commit日期2026-10-30）。
当时九个公开工程整工程继承；后续新增工程的有效配置用 `ucv list` 查询。
VAGQ 的 `internal-d4566d58a` 覆盖不变。

76个递归子模块条目从父commit的`.gitmodules`和实际gitlink逐层核对；相对旧基线仅
`difftest`与`XSCache`两个gitlink变化。DefaultConfig、生成参数及工具版本保持当前
显式锁定。旧[`public-893e1580b`](../baselines/public-893e1580b.json)字节不变，供历史
来源/显式重放引用；不复用旧构建收据假称新基线构建完成。

该次 2026-11-02 更新没有执行新基线源码工作区准备、RTL生成、DUT构建/冒烟或功能回归。新源码、生成及
native缓存身份自动与旧版分离，已有旧链接不手工切换；执行`ucv run`前必须先按新默认
`prepare`/`build`。无参`ucv.runtime.source_path()`与`soc_rtl()`现在读取根默认，
需要历史路径时显式传旧命名基线；按工程解析仍使用`source_path_for`/`soc_rtl_for`。
来源与检查见[更新记录](history/baseline-kunminghu-v3-20261102.json)。

> 后续进度（2026-11-03）：LSQ 已完成整条链路——`prepare` 生成 2020 个 RTL 文件、
> 38/38 DUT `BUILT + SMOKE PASS`、完整回归 2575 项 **2356 PASS / 219 FAIL**（旧基线
> 2325/250）。完整生成 RTL 已作为 release 附件发布，tag `xiangshan-a0c2a26cb`，
> 参数等价于上游 `make verilog`。其余九个工程仍未在新基线上构建或回归，上文
> "不执行"的表述只保留 2026-11-02 当时含义。详见
> [LSQ 回归结论](lessons/lsq-baseline-regression-20261103.md)。

## 继承与生成规则

`ucv.json` 指定根默认基线。`suites/<group>/ucv.json` 和 `suites/<group>/<suite>/ucv.json` 可以用 `baseline` 引用 `baselines/<name>.json`。最近一级显式声明优先；缺省继承父级。空值、未知引用、不完整定义均报错。子目录只引用完整的命名基线，不对其字段做隐式合并。一个工程的所有 DUT 共用该基线，不支持 DUT 内单独改 commit。

基线完整定义包含源码 URL、40 位 commit、递归子模块 gitlink、设计配置、Chisel 参数、firtool 参数、Mill/Chisel/firtool/Java 版本和带 SHA-256 的补丁列表。设计补丁必须列入命名基线。生成参数以该完整清单为准；通用工具不为某个 DUT 隐式增加生成入口或私有参数。

**配置示例：本仓库公开基线。** 使用原 Makefile 的发布参数：DefaultConfig、单核、`--fpga-platform --reset-gen --issue E.b --llc OpenLLC`、firtool 1.149.0 的发布优化、关闭 layer specialization。直接调用 `top.TopMain`；生成 RTL 的硬件逻辑保持原样。BPU 等工程从完整整芯片产物提取闭包，UT 绑定以优化后的实际端口为准；旧用例的接口差异在验证侧处理。历史 BPU 独立入口保存在 `docs/history/bpu/BpuVerifyMain.original.scala`，原工作区修改及补丁记录也在该历史目录，均不参与默认构建。

**配置示例：本仓库 internal 基线。** 按原 `build/time.log` 中的命令使用 `xiangshan.test.runMain top.XiangShanSim`、DefaultConfig、单核、`--enable-difftest` 和启用的 layer specialization。此配置保留 VAGQ 的断言层输入与 difftest 元数据端口，独立记录在 internal 命名基线中。

`prepare` 默认复用核验过的完整本机生成，否则获取 `baselines/rtl-releases.json` 锁定的
release；无匹配附件时明确报错。`--rtl-source source` 才校验完整递归源码并启动本机生成。
`--source-only` 单独准备源码。两种 RTL 来源均按实例关系提取最小闭包，遇到缺失或重名模块
即报错，复制前后字节保持一致。真实 top 与导出名记录在工程 `ucv.json`。
导入收据、完整基线绑定及缓存版本见[工作空间参考](reference/workspace.md)。

`build` 使用锁定 Picker、xcomm 和 Verilator，启用 mem_direct 与原生行覆盖率。接受构建需要完整导出文件及独立 Python 进程冒烟通过。Picker 对 Python 保留字端口的绑定修正在 `ucv.build.repair_python_keywords` 中显式实现，只改变 Python 属性访问方式，记录修正前后哈希。

`.cache/sources/` 保存独立 Git 检出；`.cache/generated/` 保存生成结果和命令；`.cache/duts/` 按完整有效基线、工程、DUT、配方、工具链和构建选项隔离。工程下的 `rtl/`、`dut/` 是指向本仓库缓存的相对链接，均被 Git 忽略。缓存命中仍会核验文件哈希；失败构建不生成通过凭据。

命令输出及报告包含基线来源；集合中不同有效基线会标记 MIXED。统一版本验收必须使用 `--require-unified-baseline`。
