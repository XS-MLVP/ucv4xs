# ICache 验证工程

基于 Picker 与 toffee 验证香山 ICache 及 10 个子模块。11 个 DUT 平级构建，整块
`ICache` 闭包保留真实子模块 RTL；领域模型、检查器和事务适配保留在本工程。

当前原生加载器使用 `ucv.runtime.native_seed` 转发 `ucv run --seed`，不再固定为 1。
根 `tests/test_frontend_runtime_seed.py` 核验实际构造参数及构造间环境变化；历史 CLI
seed 标注不等于当时已使用该原生 seed。该修复不改变 RTL/native 构建或已知 XFAIL 判定。

## 当前结论

基线 `public-a0c2a26cb` / DefaultConfig / 单核。2026-11-08 收口：11/11 DUT 完成
prepare/build/冒烟，seed 1 与 seed 2 完整回归均为 **572 PASS / 1 XFAIL，exit 0**
（573 节点 = 571 硬件 nodeid + 2 个 selftest；旧 570 个节点全部保留）。

三个历史标记的最终处置：

- `ICACHE-012`（stale `vSetIdx`）：上游 `4b9f938b7`（#6691）已修，改为普通正向用例；
  红/绿对照保留在 `testbenches/icache/tests/scoreboard/test_hint_install_control.py`。
- `ICACHE-030`（软预取合并未接受请求）：接口退役，改写为 FTQ `PrefetchQueue` 承接的
  “未完成握手不得触达内存”合同，nodeid 保留，结论 PASS。
- `WAYLOOKUP-020`（flush 同拍取消写仍锁存异常）：真实缺陷仍在，保持 strict XFAIL；
  最小复现与影响见[缺陷文档](docs/bugs/open/waylookup-flush-cancelled-write-exception.md)。

ICache 行事务审计 **owner/pin/signal 全部为 0**（上一轮 329→6，本轮 6→0）；全仓
`--require-transaction-boundary` 仍因其他工程债务 exit 1，未声称全仓闭合。逐 nodeid
差分、覆盖归因、CtrlUnit 源码守卫与残余见
[新基线适配记录](docs/spec/verification/reports/baseline-update-a0c2a26cb.md)。
本轮不改 RTL、未提上游、未 push。

DataBank 与 MetaBank 已接入严格类型/固定 ABI、SDK 唯一驱动、双相 lossless 持续采样、
逐输入 UID 和严格 fixture finish。MetaBank 实际两 138-bit 宏，tag/valid 来源分开；
共享 SRAM 控制事务进一步区分 hold、真实消费相位和逐 row reset 清扫，不能用模型瞬间
清零代替真实写入。两 DUT 合同与历史运行见
[MetaBank/SRAM 当前合同](docs/spec/verification/transactions/metabank-transaction-adaptation.md)、
[DataBank 历史检查点及后续](docs/spec/verification/transactions/databank-transaction-adaptation.md)
和[全仓协作交接](../../../docs/collaboration-checkpoint-20261102.md)。其他 DUT 的生命
周期/API 组合仍未签核，不因目录或静态零命中获得完整事务验收信用。

## 文档与证据

- [文档总览](docs/README.md)
- [设计规格](docs/spec/design/README.md)：11 个 DUT 的层次、职责、配置与未确认边界
- [验证规格](docs/spec/verification/README.md)：结果、完成条件与所有验证入口
- [错误复核](docs/spec/verification/error-review.md)、
  [覆盖闭环](docs/spec/verification/coverage/icache-coverage-closure.md)、
  [line/branch/toggle 分析](docs/spec/verification/coverage/coverage-line-toggle-branch.md)
- [历史交付报告（893e1580b）](docs/spec/verification/reports/verification-report.md)、
  [历史工程快照](docs/spec/verification/evidence/legacy-readme-20261031.md)
- [问题索引](docs/bugs/README.md)

## 构建与运行

完整配方见 `ucv.json`；基线按根目录、硬件分组、工程目录继承。

```sh
.venv/bin/ucv doctor icache --require-unified-baseline
.venv/bin/ucv prepare icache --require-unified-baseline
.venv/bin/ucv build icache --require-unified-baseline
.venv/bin/ucv run icache --workers 8 --seed 1 --require-unified-baseline \
  --output results/<new-icache-run>
.venv/bin/ucv report results/<new-icache-run>
```

每次回归使用新的结果目录。生成 RTL、原生包和运行结果不纳入 Git。历史说明不代表
当前基线结论；旧 `public-893e1580b` 的 290+3、95.67% 等数字保持历史含义。
