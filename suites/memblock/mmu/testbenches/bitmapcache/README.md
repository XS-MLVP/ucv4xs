# bitmapcache

## 实现职责

- [env/bitmap.py](env/bitmap.py)：独立 `BitmapCacheEnv`，拥有 refill、tag/order 请求、cfs 响应、BCLEAR、flush 与背压操作。
- [model.py](model.py)：原 64 位字的字节选择公式；[checker.py](checker.py)：原 refill/hit、order 和 cfs 位序断言。
- [coverage.py](coverage.py)：既有 BitmapCache event/byte/order bins；[tests/fixtures.py](tests/fixtures.py) 延迟加载本 DUT。
- [功能场景](tests/test_bitmapcache.py)保留组/路、替换、清除、背压、数据与 tag 极值；[checker 自检](tests/test_bitmapcache_checker_selftest.py)包含独立字节示例和 hit/order/cfs 错误对照。

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `bitmapcache` | `BitmapCache` | `BitmapCacheDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2-midblocks.md](../../docs/spec/verification/functional-points/functional-points-l2-midblocks.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2-midblocks-20261024.md](../../docs/spec/verification/evidence/reports/l2-midblocks-20261024.md)
- 公开环境：[testbenches/bitmapcache/env/bitmap.py](env/bitmap.py)
- 用例与自检：[testbenches/bitmapcache/tests](tests) · [testbenches/bitmapcache/tests/test_bitmapcache.py](tests/test_bitmapcache.py)
- 实现职责：[testbenches/bitmapcache/model.py](model.py) · [testbenches/bitmapcache/checker.py](checker.py) · [testbenches/bitmapcache/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut bitmapcache
./scripts/ucv run mmu --dut bitmapcache --collect-only --workers 1
./scripts/ucv run mmu --dut bitmapcache --workers 1 -- testbenches/bitmapcache/tests/test_bitmapcache.py::test_refill_then_hit_selects_byte
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
