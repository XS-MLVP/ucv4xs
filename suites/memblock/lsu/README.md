# LSU 验证工程

包含 19 个独立 DUT，统一使用 toffee。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
ucv prepare lsu
ucv build lsu
ucv run lsu --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。

## 当前入口

- [文档入口](docs/README.md)与[当前页面登记](docs/navigation.json)。
- [Design spec](docs/spec/design/README.md)：真实层次、19 份 DUT 合同和设计确认边界。
- [Verification spec](docs/spec/verification/README.md)：DUT/测试、覆盖残余、7 个开放问题和完成条件。
- [问题记录](docs/bugs/README.md)；旧错误包在 `docs/bugs/evidence/`。
- [历史证据索引](docs/spec/verification/evidence/README.md)与[缺口归因](docs/spec/verification/gaps)。

## 状态摘要

2026-10-26 `upstream-review-regression-02`（固定源码 `XiangShan 893e1580…`）为 589 项 **582 PASS / 7 FAIL / 0 SKIP / 0 ERROR**，交付门禁 **FAIL**。7 个 FAIL 对应 7 个已确认 RTL 根因；21 组声明式功能 bin 的 100% 只是采样覆盖，剩余 338 个 toggle 点保留在逐 DUT gap 文件中。本次 2026-11-09 文档整理未运行 native；当前 `public-a0c2a26cb` 未重建/复跑。

领域模型与检查器保留在本工程；历史缺陷和合同见 `docs/`、`manifest/`。历史说明不代表当前基线结论。
