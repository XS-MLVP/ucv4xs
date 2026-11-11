# VAGQ 验证工程

包含 12 个独立 DUT，统一使用 toffee。验证源码位于 `testbenches/<testbench>/`：
11 个实现包对应 12 个 DUT，两个 pipeline DUT 共用参数化实现。配方保留 schema 1，
`workspace.json` 使用 schema 2。完整配方见 `ucv.json`；VAGQ 通过本地来源接入
internal 基线，与其他公开工程的 `public-*` 基线不同，混合基线集合会被统一基线检查拒绝。

```sh
ucv prepare vagq
ucv build vagq
ucv run vagq --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。

## 当前入口

- [工程资料入口](docs/README.md)
- [Design spec](docs/spec/design/README.md)：职责、公共边界、组件行为与未确认的设计要求。
- [Verification spec](docs/spec/verification/README.md)：验证分层、场景矩阵、当前记录和未关闭项。
- [问题记录](docs/bugs/README.md)：当前 open/closed 状态；不复制 internal 源码或证据。
- `./scripts/ucv info vagq --dut <key>`：逐 DUT 显示 testbench 实现/测试入口和 internal 基线源码相对路径。

## 状态边界

最近已记录统一运行 `results/ucv-vagq-20261031` 为 **433 PASS / 1 FAIL / 33 SKIP**
（internal `d4566d58a`）；1 FAIL 是 MaskGen 元素窗口策略的 56/9024 native mismatch，
未登记 XFAIL；33 SKIP 是显式 campaign/audit 开关或普通回归不覆盖的边界。该结果未在
本次文档整理中重跑，当前汇总以根 [docs/status.md](../../../docs/status.md) 为准。

internal 源码、生成产物和包含 internal 源码的证据保持外部接入；本仓库只保留可公开的
验证代码、清单和结论引用。历史复盘通过
[经验索引](../../../docs/lessons/README.md#vagq-external-evidence) 访问外部证据。
历史说明不代表当前基线结论。
