# ncb_order_address_cam

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `ncb_order_address_cam` | `NCBOrderAddressCAM` | `NcbOrderAddressCamDut` |

## 工作入口

- 设计规格：[docs/spec/design/ncb_order_address_cam.md](../../docs/spec/design/ncb_order_address_cam.md)
- 验证合同与计划：[docs/spec/verification/ncb_order_address_cam.md](../../docs/spec/verification/ncb_order_address_cam.md)
- 公开环境：[testbenches/ncb_order_address_cam/env.py](env.py)
- 用例与自检：[testbenches/ncb_order_address_cam/tests](tests)
- 实现职责：[testbenches/ncb_order_address_cam/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ncb --dut ncb_order_address_cam
./scripts/ucv run ncb --dut ncb_order_address_cam --collect-only --workers 1
./scripts/ucv run ncb --dut ncb_order_address_cam --workers 1 -- testbenches/ncb_order_address_cam/tests/test_ncb_order_address_cam_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
