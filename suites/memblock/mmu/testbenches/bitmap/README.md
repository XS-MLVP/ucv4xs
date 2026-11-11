# bitmap

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `bitmap` | `Bitmap` | `BitmapDut` |
| `bitmapcache` | `BitmapCache` | `BitmapCacheDut` |

这些 DUT 显式共用参数化实现；运行共享用例时选择其实际需要的全部 DUT。

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2-midblocks.md](../../docs/spec/verification/functional-points/functional-points-l2-midblocks.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2-midblocks-20261024.md](../../docs/spec/verification/evidence/reports/l2-midblocks-20261024.md)
- 公开环境：[testbenches/bitmap/env/bitmap.py](env/bitmap.py)
- 用例与自检：[testbenches/bitmap/tests](tests) · [testbenches/bitmap/tests/test_bitmap.py](tests/test_bitmap.py) · [testbenches/bitmap/tests/test_bitmapcache.py](tests/test_bitmapcache.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut bitmap --dut bitmapcache
./scripts/ucv run mmu --dut bitmap --dut bitmapcache --collect-only --workers 1
./scripts/ucv run mmu --dut bitmap --dut bitmapcache --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
