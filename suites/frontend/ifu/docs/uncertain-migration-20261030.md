# UNCERTAIN 本地框架迁移核验（2026-10-30）

## 结论与边界

本次把“执行完成但证据不足”的声明从 ucv 迁入 Toffee，改名为 **UNCERTAIN**。
IFU 完整运行 `results/20261030T-uncertain-uc-toffee` 为
**144 PASS / 2 FAIL / 1 UNCERTAIN**，总体仍为 **FAIL**、退出 1。
硬件功能点为 **53 PASS / 1 FAIL / 1 UNCERTAIN**（55 点），环境功能点 5/5 PASS。

`IFU-TOP-011` 的 carry 用例仍只检查一种跨窗口位置，登记 R-09，不计 PASS。
`IFU-TR-002` 的两条 tdata2 高位反例仍为真实 FAIL，R-13 仍是唯一 blocking+open 残余。
没有修 RTL、改设计基线、放宽断言或扩大 XFAIL；也没有重建 Picker、xcomm 或 DUT。

与 `results/20261030T022604Z-107cb685` 逐项对账：

- 147 个 nodeid 的集合相同；七个 DUT 的 `ifu-builds.json` 内容完全相同。
- 唯一用例状态变化为 carry 用例：旧 `INCOMPLETE` → 新 `UNCERTAIN`。
  旧收据与报告保持原样；报告适配器仍支持读取旧 `declared_incomplete`。
- pytest 摘要、Toffee manifest、ucv `cases.json` 与汇总计数一致，原因与 R-09 引用一致。
- Toffee `state="committed"`、`coverage_complete=true`、清理完成；所有产物哈希复核通过。
- 运行源码前后 SHA-256 均为
  `ccf7fe07f9505ad41379e8b652b813ca86e22bc29cf7effe3c32bb0b5ef66c97`。

这是框架本机开发安装的验收，不是整个硬件验证或公共依赖升级的验收。

## 源码与安装身份

| 项目 | 实际身份 |
|---|---|
| Toffee 检出 | 用户指定的 `/home/xyl/xreactor/output/uc-packages/toffee`；`main`，基于 `d865442a15660afae407bb7bce3fdbf1c70ad0ca`，含未提交改动 |
| 分发版本 | `uc-toffee 2.0.1.dev1+uncertain.a886d1c12444`，从本地源码构建 wheel 后安装 |
| 完整源码 SHA-256 | `a886d1c124443eb79fc498c7e31b4f37ca71aafcb86f47c5e66ea804fb5d025a`（282 个 Git 跟踪/未忽略文件的规范 JSON 哈希表） |
| wheel SHA-256 | `358d637170583f5b165468d550733a326135a6365c0b064bb257d323073b58ef` |
| 运行环境 | 仓库内 `.venv-uc-toffee`；`uc-xcomm 1.1.1`、ABI 3、coverage protocol 5；pytest 9.2.0、xdist 3.8.0 |
| 原生构建 | 保留 `dependencies/versions.json` 的 Picker `4dd442c`、xcomm `0.3.0.dev3`（含原工具补丁）和 Verilator 5.052；DUT 内置绑定未替换 |
| 设计 | `public-893e1580b` / DefaultConfig，七个既有 DUT |

没有提交、打 tag、推送、发布或新增 Toffee patch 文件。原 `.venv` 保持不动；
`.ucv/local.json` 显式选择开发运行环境，`.ucv/toffee-development.json` 保存完整源码、
安装包文件哈希和绑定身份。运行前校验这些实物，实际身份进入
`run.json.installed_tools.runtime`，不改写旧原生构建凭据。
配置与复核方式见[本地环境说明](../../../../docs/local-configuration.md#本地-toffee-开发环境)。

## 判定规则与框架/工程分工

```python
@pytest.mark.uncertain(reason="只覆盖窗口末尾一种 carry 位置", reference="R-09")
def test_partial(dut): ...
```

- Toffee 负责标记校验、完整阶段判定、黄色 `U` / `UNCERTAIN`、pytest session 数量与原因、
  manifest 的 `tests.UNCERTAIN` 与 `uncertain` 列表。
- `reason` 为必填非空字符串，`reference` 在框架中可选且不限格式；IFU 另加残余追溯门禁。
- 测试照常执行。断言失败仍 FAIL，setup/teardown 错误仍 ERROR，skip 仍 SKIP；不与
  xfail 叠加。完整 teardown 到达前，call 的 `U` 只是暂定结果。
- UNCERTAIN 不计 PASS，但本身不改变退出码。只有 PASS/UNCERTAIN 且没有其他错误或
  验收阻塞时返回 0；正常退出不代表验证全通过。INCOMPLETE 仍用于执行/产物/必需验收项未完成。
- ucv 和 IFU 功能点适配器消费 `toffee.outcomes`，不重复定义 UNCERTAIN。
  xdist 控制进程收到功能点附件与声明后统一分类，避免只在 worker 中留状态。
- ucv 同时核对新 Toffee manifest 与用例收据的数量、原因；不一致属于完整性缺口，不能
  以 UNCERTAIN 正常退出掩盖。

## 实际测试

| 核验 | 结果 |
|---|---|
| 本地 Toffee 全量 `tests/`，使用安装后的开发环境 | 1165 PASS，另有 3 个 subtest PASS；日志 `toffee-tests.log` |
| Toffee runner 测试 | 65 PASS，含单/双 worker、`U`/详细状态、声明原因、非零错误优先、skip、strict/non-strict XFAIL/XPASS、覆盖提交 |
| ucv 根测试，`.venv-uc-toffee` | 54 PASS（含单/双 worker 收据与功能点对账、teardown ERROR、源码/安装变化拒绝、CLI 退出码） |
| ucv 根测试，原 `.venv` | 50 PASS / 4 SKIP；4 项明确需要新 Toffee 的集成测试，未伪装为通过 |
| `.venv-uc-toffee/bin/python -m pip check` | PASS，无依赖缺口 |
| IFU 全量，seed 1 / workers 1 | 144 PASS / 2 FAIL / 1 UNCERTAIN；执行于 07:12:35–07:13:51 UTC |
| 真实 carry 用例，workers 2 | `results/20261030T-uncertain-only-xdist`：1 UNCERTAIN、退出 0、2 份 worker 收据，原生覆盖提交且哈希正确 |
| `python3.12 scripts/audit-assets.py` | PASS，132 DUT / 10 工程，无资产错误 |

pytest-asyncio 仍提示未设置 `asyncio_default_fixture_loop_scope` 的弃用警告；这不影响本次结果，
本次未顺带修改各工程异步 fixture 策略。没有重跑其他工程全量仿真。

## 同轮覆盖率

从本轮 manifest 重新生成 `coverage.json`，与旧 manifest 直接计算的结果比较；
七个 DUT 的 line/branch/toggle 命中数和分母均不变（`coverage-comparison.json`）。

| DUT | line | branch | toggle bin |
|---|---:|---:|---:|
| RvcExpander | 174/174 (100.00%) | 66/66 (100.00%) | 140/146 (95.89%) |
| InstrBoundary | 90/90 (100.00%) | 153/154 (99.35%) | 2015/2196 (91.76%) |
| PredChecker | 105/105 (100.00%) | 23/24 (95.83%) | 15968/15998 (99.81%) |
| IfuUncacheUnit | 43/43 (100.00%) | 15/16 (93.75%) | 546/546 (100.00%) |
| FrontendTrigger | 193/193 (100.00%) | 155/156 (99.36%) | 7602/7982 (95.24%) |
| IfuPerfAnalysis | 711/711 (100.00%) | 21/22 (95.45%) | 112/644 (17.39%) |
| Ifu | 4053/4053 (100.00%) | 1648/1652 (99.76%) | 30590/34924 (87.59%) |

本次没有新覆盖闭环或残余关闭。先前[覆盖率缺口分析](coverage-loop.md)与
[退出合同](exit-criteria.md)的证明边界继续适用；高覆盖不能替代 R-09/R-13 的处置。

## 证据索引

以下文件都在 `results/20261030T-uncertain-uc-toffee/`；完整运行数据保持忽略，不进入 Git。
`feature-points.json` 是本次结束后立即保存的功能点报告快照，不依赖可被后续运行覆盖的工程默认报告。

| 文件 | SHA-256 |
|---|---|
| `run.json` | `7e706e4b20661df6825d81f111dec1b45f0f3a791aa52280a6ab7c224a4c54d5` |
| `ifu/manifest.json` | `eb177b2d81dd599cc8c2b04deb376d6c109ba49fdad110ac02ef91fcb77061e6` |
| `cases/ifu/cases.json` | `471c844f9f76707bcbe48acc23a87421903bc9f2df98dbce4e35893fdd9b0c33` |
| `summary.json` | `5fdb5c91fd441777963624164eab3ceeda2b1535cd0a0dc6ade42ab234049010` |
| `feature-points.json` | `0490612172d85b68346dfa9e856de238b07dbc378bc14ea0fb9b609b0fa12a8d` |
| `coverage.json` | `7e2174679c5058294f53542b4f09ca5d511b1eadb758b8080ed5c317d9be6eb7` |
| `coverage-comparison.json` | `d93ee04dddfef87243c20e3f1b53123cfb59eed885dabd3155dd33cd76b9a56e` |
| `toffee-tests.log` | `51c470c2b7d58ed828163a820a4d02895f208f7892460841e35d0010196547bc` |
