# 使用文档

仓库与发行包名为 **ucv4xs**，命令和 Python 包名为 **ucv**。当前十二工程统一使用
`testbenches/` 布局；使用文档说明如何操作，实际适配范围、失败和未验证项看
[当前状态](status.md)，不能从教程或结构检查推断硬件通过。

本文按 [Diátaxis](https://diataxis.fr/) 的四种读者需求导航，不要求先读完全部文档。
所有命令默认从仓库根执行；`<suite>`、`<dut>` 等占位符须替换，首次学习请用完整示例。

## 教程：跟着完成第一次运行

面向首次使用者，选择一个固定例子，从准备到结果逐步完成。

- [第一次运行 BPU/MainBTB UT](tutorials/bpu-first-ut.md)：找到现有实现，获取 release
  RTL，构建一个 DUT，运行一个复位/冷查询用例并读取报告。

## 操作指南：完成手头的任务

已知道要做什么时，直接进入相应步骤，不必重走教程。

| 任务 | 指南 |
|---|---|
| 找工程资料、只获取源码、准备 RTL 或新增 DUT | [准备工作空间](how-to/workspace.md) |
| 选跑单个或多个 DUT、只收集用例、控制种子与并发、比较两次结果 | [运行测试与查看报告](how-to/run-tests.md) |
| 使用源码镜像、接入 internal 来源或外部历史证据 | [配置本地来源与运行环境](local-configuration.md) |
| 更新使用文档、工程规格或问题记录 | [维护文档与工程规格](how-to/maintain-docs.md) |

## 参考：查准确名称、参数与位置

按需要检索，不要求顺序阅读。

- [目录与文件职责](reference/repository-layout.md)：根目录、工程目录、本地环境与产物的区别。
- [ucv 工作空间参考](reference/workspace.md)：CLI 参数、默认值、配置字段、收据与退出码。
- [工程与 testbench 目录规范](reference/module-layout.md)：schema2、六职责、shared 边界及目录白名单。

## 解释：理解设计取舍与结论边界

- [仓库结构与扩展方式](architecture.md)：为什么分开公共编排、工程和 DUT；测试如何到达 RTL。
- [基线与构建](baselines.md)：为什么锁定完整基线；release、本机生成和缓存身份的关系。
- [维护与验收](maintenance.md)：为什么执行成功、适配接受和硬件通过是不同结论；如何理解
  [事务边界扫描](maintenance.md#如何理解事务边界检查)。

## 工程规格、问题与历史证据

这些不是使用教程，不为凑齐四类文档而搬目录或改写历史内容：

- **当前进展**：[阶段状态](status.md)。
- **工程资料**：先看工程 `README.md`，或执行 `./scripts/ucv info <suite> --dut <dut>`；
  设计/验证规格在工程 `docs/spec/{design,verification}/`，问题在 `docs/bugs/{open,closed}/`。
- **DUT 工作入口**：`testbenches/<testbench>/README.md`；已有 shared 包另有独立 README。
  `ucv docs <suite> --write` 只刷新工作入口与问题汇总的生成区块，不生成验证结论。
- **经验与复盘**：[经验索引](lessons/README.md)；保留各案例的日期、基线和适用范围。
- **历史来源**：`docs/history/` 和外部运行存储。旧引用可通过
  [`navigation.json`](navigation.json) 的 `relocations` 找到当前页面；位置映射不是字节或执行身份相同的证明。

资源地图和运行统计由 `ucv` 生成；当前页面不手工复制长期变化的用例计数和问题清单。
要维护这些文档，先看[文档维护指南](how-to/maintain-docs.md#先选择文档类型)。
