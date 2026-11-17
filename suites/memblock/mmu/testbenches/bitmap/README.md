# bitmap

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `bitmap` | `Bitmap` | `BitmapDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2-midblocks.md](../../docs/spec/verification/functional-points/functional-points-l2-midblocks.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2-midblocks-20261024.md](../../docs/spec/verification/evidence/reports/l2-midblocks-20261024.md)
- 公开环境：[testbenches/bitmap/env/bitmap.py](env/bitmap.py)
- 用例与自检：[testbenches/bitmap/tests](tests) · [testbenches/bitmap/tests/test_bitmap.py](tests/test_bitmap.py)
- 实现职责：[testbenches/bitmap/transactions.py](transactions.py) · [testbenches/bitmap/model.py](model.py) · [testbenches/bitmap/checker.py](checker.py) · [testbenches/bitmap/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut bitmap
./scripts/ucv run mmu --dut bitmap --collect-only --workers 1
./scripts/ucv run mmu --dut bitmap --workers 1 -- testbenches/bitmap/tests/test_bitmap.py::test_cache_hit_pass_and_fail
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->

## 实现职责

- [env/bitmap.py](env/bitmap.py)：`BitmapEnv` 保留 PMP/cache/memory 独立 responder、并行 fire 捕获、refill/wakeup 和响应记录；[transactions.py](transactions.py) 定义 `BmReq`。
- [model.py](model.py)：原 level 合并公式；[checker.py](checker.py)：原 cf/cfs/id 完成断言。多请求合并、flush、wakeup、内存地址等检查仍在原场景内。
- [coverage.py](coverage.py)：既有 Bitmap event/level/result bins。
- [tests/fixtures.py](tests/fixtures.py)：按请求加载 Bitmap 环境与覆盖对象。
- [快照自检](tests/test_bitmap_transaction_selftest.py)和[结果/身份错误对照](tests/test_bitmap_checker_selftest.py)均为离线 selftest。
