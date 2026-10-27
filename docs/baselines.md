# 基线与构建

`ucv.json` 指定根默认基线。`suites/<group>/ucv.json` 和 `suites/<group>/<suite>/ucv.json` 可以用 `baseline` 引用 `baselines/<name>.json`。最近一级显式声明优先；缺省继承父级。空值、未知引用、不完整定义均报错。子目录只引用完整的命名基线，不对其字段做隐式合并。一个工程的所有 DUT 共用该基线，不支持 DUT 内单独改 commit。

基线完整定义包含源码 URL、40 位 commit、递归子模块 gitlink、设计配置、Chisel 参数、firtool 参数、Mill/Chisel/firtool/Java 版本和带 SHA-256 的补丁列表。初始所有硬件分组均继承根；仅 VAGQ 工程 override。设计补丁必须列入命名基线。BPU 原修复及工作区修改存于 `docs/history/bpu/`，默认补丁列表为空。

公开基线使用原 Makefile 的发布参数：DefaultConfig、单核、`--fpga-platform --reset-gen --issue E.b --llc OpenLLC`、firtool 1.149.0 的发布优化、关闭 layer specialization。直接调用 `top.TopMain`，保留 Chisel 原始断言，不对生成 RTL 做硬件逻辑改写。BPU 与其他公开工程共享这次完整生成的 RTL，十个 DUT 均从整芯片产物提取闭包。没有 BPU 专用生成入口、额外 Scala 注入或单模块 elaboration。UT 绑定以整芯片优化后的实际端口为准，旧用例的接口差异由模型、适配层和用例处理，不为了保留旧接口改写 RTL。历史独立入口只保存在 `docs/history/bpu/BpuVerifyMain.original.scala` 和 Git 历史中，不参与当前构建。

internal 基线按原 `build/time.log` 中的命令使用 `xiangshan.test.runMain top.XiangShanSim`、DefaultConfig、单核、`--enable-difftest` 和启用的 layer specialization。此配置保留 VAGQ 的断言层输入与 difftest 元数据端口。它独立记录在 internal 命名基线中，不影响公开工程。

`prepare` 先校验完整递归源码，再生成 RTL，按实例关系提取最小闭包。闭包遇到缺失或重名模块即报错，复制前后字节保持一致。每个 DUT 的顶层与导出名记录在工程 `ucv.json`。

`build` 使用锁定 Picker、xcomm 和 Verilator，启用 mem_direct 与原生行覆盖率。接受构建需要完整导出文件及独立 Python 进程冒烟通过。Picker 对 Python 保留字端口的绑定修正在 `ucv.build.repair_python_keywords` 中显式实现，只改变 Python 属性访问方式，记录修正前后哈希。

`.cache/sources/` 保存独立 Git 检出；`.cache/generated/` 保存生成结果和命令；`.cache/duts/` 按完整有效基线、工程、DUT、配方、工具链和构建选项隔离。工程下的 `rtl/`、`dut/` 是指向本仓库缓存的相对链接，均被 Git 忽略。缓存命中仍会核验文件哈希；失败构建不生成通过凭据。

命令输出及报告包含基线来源；集合中不同有效基线会标记 MIXED。统一版本验收必须使用 `--require-unified-baseline`。
