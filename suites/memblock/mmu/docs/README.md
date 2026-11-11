# MMU 文档入口

本目录保存 MMU/TLB 验证工程的设计合同、功能点、验证规格、残余项和问题记录。工程命令见[工程 README](../README.md)，当前页面清单见 [navigation.json](navigation.json)。

## 当前入口

- [Design spec](spec/design/README.md)：真实 TLB/MMU 层次、PTW 完成合同和设计确认边界。
- [Verification spec](spec/verification/README.md)：17 个 DUT、功能点、覆盖/可信度复核和完成条件。
- [残余项](spec/verification/residuals.md)：未被分类为正式 bug 的覆盖/结构/已接受边界，保留稳定 ID。
- [问题记录](bugs/README.md)：开放缺陷、已关闭的误报/覆盖缺口及证据索引。

## 资料地图

| 内容 | 位置 | 说明 |
|---|---|---|
| 功能点 | [spec/verification/functional-points](spec/verification/functional-points) | TLBFA、TLB、TLBNonBlock、L2 叶子/中块、PtwCache、L2TLB、wrapper 的语义功能点。 |
| 设计合同 | [spec/design/contracts](spec/design/contracts) | 当前为 PTW 完成合同；其余层级的设计依据在功能点和报告中。 |
| 历史报告/审计 | [spec/verification/evidence/reports](spec/verification/evidence/reports) | 2026-10-24/25/26 报告与 `soundness-20261025` 证据快照。 |
| 版本/已知问题 | [`manifest/`](../manifest) | baseline、RTL 哈希、toolchain、known-issues。 |
| 当前页面登记 | [navigation.json](navigation.json) | schema 1；`./scripts/ucv check mmu` 使用。 |

## 资源登记

- `workspace.json`（schema 2）为每个 DUT 登记实际 `environment` 模块、现有测试文件、模块功能点/验证报告
  和固定 `public-a0c2a26cb` 的 `chisel` 定义/实例化来源；`duts.<dut>.testbench` 保留 17 DUT 到
  15 个实现包的参数化共用关系。`fixtures` 与 `loader` 为工程级共享入口（`conftest.py`、
  `testbenches/shared/env/native.py`），因此 `ucv info` 会在每个 DUT 下显示同一份夹具/加载器。
- 模块 `design_spec` 指向功能点/合同，`verification_spec` 先指向当前验证范围入口，再指向该 DUT
  的历史报告；`ucv info` 的“已存在”只说明本地文件存在，构建/运行仍要按缓存凭据校验。
- MMU 的逐 DUT 功能点文档位于 `docs/spec/verification/functional-points/`；当前把它们登记为
  `design_spec` 的行为依据，是因为本工程暂无逐 DUT 的 `spec/design` 页面。它们仍是功能点
  清单，不是设计 owner 签核，也不是验证通过的证明。
- TLBFA、TlbStorageWrapper、TLB、TLBNonBlock 使用各自 testbench 的 `env/` 与专用测试文件。
  L2 各 DUT 的环境类位于 `testbenches/<module>/env/`（例如 `testbenches/l2mq/env/missqueue.py`、
  `testbenches/bitmap/env/bitmap.py`、`testbenches/ptw/env/ptw_walker.py`），测试位于对应
  `testbenches/<module>/tests/`；`ptw` 另登记 `test_ptw_identity.py`。`ptwrepeater` 与 `ptwfilter`
  共用 `testbenches/ptwrepeater/env/ptw.py` 环境模块，但测试文件独立。
- 原 `runtime/` 的调用边界按职责归入 `testbenches/shared/env/`：`native.py` 为 loader，
  `execution.py` 为跨 DUT 的 toffee 执行上下文，`legacy_pins.py` 为跨 DUT 的逻辑引脚名映射。
  DUT 专属 fixture 归各 testbench 的 `tests/fixtures.py`，由工程根 `conftest.py` 显式注册。
- 共享参数化/共享环境模块会如实显示同一路径；`ucv --dut` 只限制测试路径，不能过滤 pytest fixture 的 param 变体。当前这些 L2 测试均按单 DUT fixture 组织，没有把 variant 选择伪装成 `--dut` 能力。
- 所有 DUT fixture 集中在 `conftest.py`；工具当前只支持工程级 `fixtures`/`loader`，`ucv info` 在每个 DUT 下显示同一份共享入口，不会按 DUT 过滤 fixture 定义。

## 阅读边界

- 最近可信度复核记录为 2026-10-26：17 个真实 RTL DUT suite，**395 PASS + 13 checker/model 自检 PASS = 408 PASS，0 FAIL/XFAIL/SKIP**；这不是整颗 MMU/SoC 或 ISA 签核。当前 `public-a0c2a26cb` 未复跑，本次文档整理未运行 native。
- 旧 376 PASS + 5 XFAIL 是历史基线；5 个 XFAIL 后被发现是验证侧问题，旧 RTL 根因结论已撤回。
- 采样功能 bin 的 100% 不等于语义闭合；残余/结构/已接受项在 [residuals.md](spec/verification/residuals.md) 中逐项保留，不用 waiver 消除。
- 正式问题按 [bugs/open](bugs/open)/[bugs/closed](bugs/closed) 的目录状态读取。当前为 **8 open / 9 closed**：8 个 open 均记录当前基线 `unverified`；closed 中 8 个是旧基线误报/归因撤回（当前基线 `unverified`，只关闭旧误报），1 个是独立 DUT 结构缺口关闭（当前树结构证据，非运行通过）。5 个旧 `fixed` 覆盖缺口因当前基线未复验已移回 open，旧 closed 版本和历史 resolution 保留。
- `manifest/known-issues.json` 仍保留原始机器记录，二者以目录为当前状态、以 manifest 为历史依据。
