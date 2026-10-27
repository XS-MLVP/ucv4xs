# BPU 验证工程

包含 10 个独立 DUT，统一使用 toffee。与其他公开工程共用 DefaultConfig 完整香山 RTL，再提取各模块闭包供 Picker 构建；不单独 elaboration BPU 或注入 Scala 入口。整芯片优化可能裁剪原独立顶层端口，旧用例的接口适配仍在进行。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
ucv prepare bpu
ucv build bpu
ucv run bpu --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。领域模型与检查器保留在本工程，历史缺陷和功能合同见 `docs/`、`manifest/`。历史说明不代表当前基线结论。
