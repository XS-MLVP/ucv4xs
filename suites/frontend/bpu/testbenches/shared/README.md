# shared

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；跨 testbench 共享实现与自检入口。

shared 是保留的共享包，不对应 RTL top；实现按实际职责组织，自检归 tests/。

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同：[docs/spec/verification/README.md](../../docs/spec/verification/README.md)
- env：[testbenches/shared/env](env)
- transactions：[testbenches/shared/transactions.py](transactions.py)
- checker：[testbenches/shared/checker](checker)
- coverage：[testbenches/shared/coverage](coverage)
- tests：[testbenches/shared/tests](tests)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv run bpu --collect-only --workers 1 -- testbenches/shared/tests
./scripts/ucv run bpu --workers 1 -- testbenches/shared/tests
./scripts/ucv report
```

按 DUT 默认选择时同时收集这些共享自检；显式 pytest 路径或 nodeid 仍限定实际选择。

<!-- ucv:module:end -->

## 退役空壳导航

2026-11-10 迁移移除了仅含注释的 `runtime/model_parameters.py`，它没有模型实现或
活动消费者。原文及哈希保存在本机 `results/testbenches-bpu-20261110/` 的源码快照；
旧路径导航到本说明，不表示原文件仍可执行。
