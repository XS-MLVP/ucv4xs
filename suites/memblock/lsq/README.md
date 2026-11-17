# LSQ 验证工程

包含 38 个独立 DUT，统一使用 toffee。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

当前有效基线为 `public-e716c7658`，具体硬件绑定见设计索引。历史功能数字保持原基线；
2026-11-13 的 Forward 复核结论及模型修正依据继续保存在原问题记录中。

```sh
ucv prepare lsq
ucv build lsq
ucv run lsq --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。

FreeList 的 4 个 DUT、CAM 的 3 个 DUT 和 UncacheEntry 的 16 个 DUT 分别维护在
`testbenches/<dut>/`，各目录只收集本 DUT 的原参数场景。单 DUT 的环境、测试和 smoke
选择由 `workspace.json` 登记，工作入口由 `ucv docs lsq --write` 生成。例如：

```sh
./scripts/ucv info lsq --dut freelist_rar
./scripts/ucv run lsq --dut freelist_rar --workers 1 -- testbenches/freelist_rar/tests
./scripts/ucv run lsq --dut cam_mask --workers 1 -- testbenches/cam_mask/tests
./scripts/ucv run lsq --dut uncache_entry_0 --workers 1 -- testbenches/uncache_entry_0/tests
```

父级原有的 FreeList/Entry 参考计算位于 `testbenches/shared/model/`，共同事务位于
`testbenches/shared/transactions/`；叶子 DUT 的实现、测试和功能判定各自独立。
旧路径与 nodeid 通过仓库历史位置映射追溯，原日期报告及其 FAIL/覆盖数字保持原基线含义。

## 当前入口

- [文档入口](docs/README.md)与[当前页面登记](docs/navigation.json)。
- [Design spec](docs/spec/design/README.md)：层次、DUT 职责、事务/接口合同和设计确认边界。
- [Verification spec](docs/spec/verification/README.md)：功能点矩阵、覆盖证据、开放问题和完成条件。
- [问题记录](docs/bugs/README.md)：开放/关闭问题的稳定 ID 与证据；旧错误包在 `docs/bugs/evidence/`。
- [当前 UT 计划](docs/spec/verification/plan.md)、[逐轮历史进度](docs/spec/verification/evidence/plan-progress-20261018-20261019.md)与[历史证据索引](docs/spec/verification/evidence/README.md)。

## 状态摘要

最近完整记录为 2026-11-06、`public-a0c2a26cb`：2600 节点 **2369 PASS / 231 FAIL**；功能点矩阵为 23 pass / 2 fail / 4 gap / 19 na，交互窗口为 2 fail / 2 gap / 1 pass。**这不是整体 PASS**。本次 2026-11-09 文档整理未运行 native，也未重建 DUT；旧报告（含 `XiangShan 893e1580…` 基线）保留原日期、计数和结论边界，不能与当前基线数字合并。

2026-11-11 事务修补的**已审查适配范围通过**，不是上述完整硬件结论更新：20 个
受影响 DUT 的当前构建身份/冒烟核验通过，原 2600 节点、参数与标记保留，现共2608。
最后当前统一入口为 **87 PASS / 3 FAIL**（含22自检），随后 Deq 单点原断言域恢复的
4 个原参数仍 **4 FAIL**；原错误未豁免，硬件汇总保持FAIL。详见
[适配范围与未证明边界](docs/spec/verification/README.md#6-事务适配的限定接受范围)。
未运行最终全2608回归，未验收其它18 DUT；严格事务扫描仍报3个原类别标签，未绕过。

领域模型与检查器保留在本工程；历史缺陷、合同和运行报告分别见 `docs/bugs/`、`docs/spec/design/contracts/`、`docs/spec/verification/evidence/`。历史说明不代表当前基线结论。
