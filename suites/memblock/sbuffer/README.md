# SBUFFER 验证工程

包含 2 个独立 DUT，统一使用 toffee。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
ucv prepare sbuffer
ucv build sbuffer
ucv run sbuffer --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。

## 当前入口

- [工程资料入口](docs/README.md)
- [Design spec](docs/spec/design/README.md)：Sbuffer/SbufferData 职责、接口、功能点与合法域。
- [Verification spec](docs/spec/verification/README.md)：验证范围、用例映射、覆盖率、当前记录和未关闭项。
- [验证约束](docs/spec/verification/constraints.md)：范围、资源和合法输入域约束（稳定 ID）。
- [问题记录](docs/bugs/README.md)：当前 open/closed 状态；历史台账保留在 `manifest/known-issues.json`。
- `./scripts/ucv info sbuffer --dut <key>`：逐 DUT 显示模块功能点、验证报告和固定基线 Chisel 定义/实例化来源。

## 状态边界

当前默认公开基线为根配置的 `public-a0c2a26cb`。本工程最近统一入口记录为
`results/ucv-sbuffer-20261031`（31 PASS，`public-893e1580b`）；2026-11-01 事务修复检查点
另记录同源码 seed1/2 各 66 PASS。两组记录绑定各自的运行范围，均未在新默认基线复验。
当前汇总以根 [docs/status.md](../../../docs/status.md) 为准。

历史报告保留原日期、基线、运行目录和结论边界；本次文档整理只改变存放位置和链接，
不回写判定。领域模型与检查器保留在本工程。
