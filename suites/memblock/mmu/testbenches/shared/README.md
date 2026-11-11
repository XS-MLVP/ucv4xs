# shared

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；跨 testbench 共享实现与自检入口。

shared 是保留的共享包，不对应 RTL top；实现按实际职责组织，自检归 tests/。

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同：[docs/spec/verification/README.md](../../docs/spec/verification/README.md)
- env：[testbenches/shared/env](env)
- tests：[testbenches/shared/tests](tests)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv run mmu --collect-only --workers 1 -- testbenches/shared/tests
./scripts/ucv run mmu --workers 1 -- testbenches/shared/tests
./scripts/ucv report
```

按 DUT 默认选择时同时收集这些共享自检；显式 pytest 路径或 nodeid 仍限定实际选择。

<!-- ucv:module:end -->
