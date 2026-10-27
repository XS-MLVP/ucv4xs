# VAGQ 验证工程

包含 12 个独立 DUT，统一使用 toffee。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
ucv prepare vagq
ucv build vagq
ucv run vagq --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。领域模型与检查器保留在本工程，接口与功能点清单见 `manifest/`。历史复盘通过 [经验索引](../../../docs/lessons/README.md#vagq-external-evidence) 访问外部证据。历史说明不代表当前基线结论。
