# ptwfilter

## 实现职责

- [env/ptw.py](env/ptw.py)：独立 `FilterEnv`，拥有 PTWFilter 的端口绑定、8 项队列激励、响应匹配观察和 flush 操作。
- [transactions.py](transactions.py)：`Req` 的 vpn/s2xlate/get_gpa；[model.py](model.py)：原 `s1_values` / `staged_values` 响应构造，期望来自请求身份和 stage。
- [checker.py](checker.py)：原单请求响应的 valid/stage/tag/PPN/valididx/ppn_low 断言；容量、重复合并、错配、同拍抑制等仍由原场景检查。
- [coverage.py](coverage.py)：既有 PTWFilter bins；[tests/fixtures.py](tests/fixtures.py) 延迟加载本 DUT。
- [事务自检](tests/test_ptwfilter_transaction_selftest.py)保留四种 ready 转换及结构 payload 保持；[checker 自检](tests/test_ptwfilter_checker_selftest.py)包含合法响应和身份/字段错误对照。

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `ptwfilter` | `PTWFilter` | `PtwFilterDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2-leaves.md](../../docs/spec/verification/functional-points/functional-points-l2-leaves.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2-filter-repeater-20261024.md](../../docs/spec/verification/evidence/reports/l2-filter-repeater-20261024.md)
- 公开环境：[testbenches/ptwfilter/env/ptw.py](env/ptw.py)
- 用例与自检：[testbenches/ptwfilter/tests](tests) · [testbenches/ptwfilter/tests/test_ptwfilter.py](tests/test_ptwfilter.py)
- 实现职责：[testbenches/ptwfilter/transactions.py](transactions.py) · [testbenches/ptwfilter/model.py](model.py) · [testbenches/ptwfilter/checker.py](checker.py) · [testbenches/ptwfilter/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut ptwfilter
./scripts/ucv run mmu --dut ptwfilter --collect-only --workers 1
./scripts/ucv run mmu --dut ptwfilter --workers 1 -- testbenches/ptwfilter/tests/test_ptwfilter.py::test_single_request_issue_match_and_release
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
