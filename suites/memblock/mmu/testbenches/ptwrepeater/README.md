# ptwrepeater

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `ptwrepeater` | `PTWRepeaterNB` | `PtwRepeaterNBDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2-leaves.md](../../docs/spec/verification/functional-points/functional-points-l2-leaves.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2-filter-repeater-20261024.md](../../docs/spec/verification/evidence/reports/l2-filter-repeater-20261024.md)
- 公开环境：[testbenches/ptwrepeater/env/ptw.py](env/ptw.py)
- 用例与自检：[testbenches/ptwrepeater/tests](tests) · [testbenches/ptwrepeater/tests/test_ptwrepeater.py](tests/test_ptwrepeater.py)
- 实现职责：[testbenches/ptwrepeater/model.py](model.py) · [testbenches/ptwrepeater/checker.py](checker.py) · [testbenches/ptwrepeater/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut ptwrepeater
./scripts/ucv run mmu --dut ptwrepeater --collect-only --workers 1
./scripts/ucv run mmu --dut ptwrepeater --workers 1 -- testbenches/ptwrepeater/tests/test_ptwrepeater.py::test_request_to_ptw_and_response_hold
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->

## 实现职责

- [env/ptw.py](env/ptw.py)：`RepeaterEnv` 负责本 DUT 的请求接受、PTW 请求/响应握手、响应保持、flush 与结构激励。
- [model.py](model.py) / [checker.py](checker.py)：RPT-03 的透明 payload 期望来自驱动事务；原响应字段断言抽为本 DUT checker，保持读取顺序。请求/响应有效性和时序检查仍在原场景内。
- [coverage.py](coverage.py)：本 DUT 的既有 event/stage/hold bins。
- [tests/fixtures.py](tests/fixtures.py)：唯一 suite conftest 注册，按 fixture 请求延迟加载本 DUT。
- [事务自检](tests/test_ptwrepeater_transaction_selftest.py)保留四种 ready 转换和原逐沿压力轨迹；[checker 自检](tests/test_ptwrepeater_checker_selftest.py)用合法响应及逐字段错误对照验证透传检查。
