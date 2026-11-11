# LSQ 文档入口

本目录保存 LSQ 验证工程的设计合同、验证规格、缺陷记录和历史证据。工程命令与当前运行入口见[工程 README](../README.md)；当前页面清单见 [navigation.json](navigation.json)。

## 当前入口

- [Design spec](spec/design/README.md)：LSQ 层次、DUT 职责、接口/事务合同和设计确认状态。
- [Verification spec](spec/verification/README.md)：验证范围、功能点账本、覆盖与完成条件。
- [UT 计划](spec/verification/plan.md)：当前验证范围、真实层次、实施顺序、合同门禁和完成条件；逐轮进度见[历史材料](spec/verification/evidence/plan-progress-20261018-20261019.md)。
- [问题记录](bugs/README.md)：开放缺陷、已关闭问题及旧证据入口。

## 资料地图

| 内容 | 位置 | 说明 |
|---|---|---|
| 用例前合同 | [spec/design/contracts](spec/design/contracts) | 按 DUT/事务族拆分的微架构行为、合法输入和检查点；机器合同仍被测试和审计读取。 |
| 功能点账本 | [`testbenches/lsq_wrapper/coverage/function_points.py`](../testbenches/lsq_wrapper/coverage/function_points.py) | 8 个事务 kind × 6 个结果域的可执行矩阵，自检见 `testbenches/lsq_wrapper/tests/meta/test_function_points.py`。 |
| 交互语义 | [contracts/interaction-semantics.md](spec/design/contracts/interaction-semantics.md) | 跨模块边界 B1–B8 与交互窗口 IWL-*。 |
| 历史运行报告 | [spec/verification/evidence/reports](spec/verification/evidence/reports) | 保留原日期、基线、计数和失败结论；不是当前基线的新运行。 |
| 旧错误报告 | [bugs/evidence](bugs/evidence) | 2026-10-22 bug 包及其误报/同源复核，作为正式问题记录的历史依据。 |
| 版本/配置/已知问题 | [`manifest/`](../manifest) | 基线、RTL 哈希、DUT 映射和机器可读 known-issues。 |
| 当前页面登记 | [navigation.json](navigation.json) | schema 1；`./scripts/ucv check lsq` 使用。 |

## 资源登记

- `workspace.json` 为每个 DUT 登记实际 `environment` 模块和现有测试文件；`fixtures` 与 `loader` 为工程级共享入口（`conftest.py`、`testbenches/shared/env/dut.py`），因此 `ucv info` 会在每个 DUT 下显示同一份夹具/加载器。
- `freelist_*`、`cam_*`、`uncache_entry_*` 是共享参数化夹具：四个 FreeList、三个 CAM、16 个 UncacheEntry 变体分别共用同一 `environment` 模块和同一组测试文件。`ucv --dut` 只会限制测试路径，**不会过滤 pytest fixture 的 param 变体**；选择其中一个 DUT 时，这些共享文件仍会运行整个参数集。资源导航如实显示共享文件，不声称能按 DUT 变体自动筛选。
- `testbenches/load_uncache/tests/test_uncache_exception_property.py` 只加载 `load_queue_uncache`；`testbenches/forward/tests/test_independent_forward_property.py` 只加载 `forward_module`，因此分别归入对应 DUT。`test_public_contracts.py` 按实际所属分散在 `deq`、`rar`、`replay`、`load_uncache` 的 tests 中，未归入单个 DUT 的 tests 列表。
- 工具当前只支持工程级 `fixtures`/`loader`；`testbenches/deq/tests/fixtures.py`、`testbenches/lsq_wrapper/tests/fixtures.py` 等专用 fixture 模块由 `conftest.py` 统一导入，`ucv info` 在每个 DUT 下显示同一份工程级入口，不会按 DUT 过滤 fixture 模块。
- `workspace.json` 的 `chisel` 已按 `public-a0c2a26cb` 为每个 DUT 登记真实定义/实例化源码；`ucv info lsq --dut <key>` 显示固定 commit 的本地路径和在线 URL。FreeList/CAM/UncacheEntry 变体共享定义文件，具体实例化来源见 [Design spec](spec/design/README.md)。

## 阅读边界

- 旧报告的日期和基线保持原义；例如 2026-10-18/19 报告绑定 `XiangShan 893e1580…`，2026-11-03/06 报告绑定 `public-a0c2a26cb`。不能把不同基线的数字合并成一次通过率。
- 历史报告中的 PASS/FAIL、覆盖数字和失败签名只属于对应运行；2026-11-09 的文档整理没有运行 native，也没有重新构建 DUT。
- 设计合同用于说明验证侧采用的期望和合法域，不等于设计 owner 已签核。未确认项在 [Design spec](spec/design/README.md) 和 [Verification spec](spec/verification/README.md) 中显式标注。
- 正式问题使用稳定 ID，按当前状态放在 [bugs/open](bugs/open) 或 [bugs/closed](bugs/closed)；目录是当前状态的唯一依据。
