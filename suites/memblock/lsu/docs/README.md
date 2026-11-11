# LSU 文档入口

本目录保存 LSU 执行流水线独立 UT 的设计合同、验证规格、问题记录和历史证据。工程命令见[工程 README](../README.md)，当前页面清单见 [navigation.json](navigation.json)。

## 当前入口

- [Design spec](spec/design/README.md)：三个模块族的真实层次、职责和 19 份 DUT 合同。
- [Verification spec](spec/verification/README.md)：验证范围、DUT 清单、覆盖/交付状态与完成条件。
- [问题记录](bugs/README.md)：7 个已确认 RTL 问题的正式记录；旧基线 `893e1580…` 为 open，当前 `public-a0c2a26cb` 全部为 unverified（未重建/未复跑）。

## 资料地图

| 内容 | 位置 | 说明 |
|---|---|---|
| DUT 合同 | [spec/design/contracts](spec/design/contracts) | 每个 DUT 的职责、合法输入、握手/取消/异常/reset 与检查点；被 `tools/verify_delivery.py` 读取。 |
| 缺口归因 | [spec/verification/gaps](spec/verification/gaps) | 每个 DUT 的未覆盖点分类，被交付/复核工具读取；不是 waiver。 |
| 历史运行报告 | [spec/verification/evidence/reports](spec/verification/evidence/reports) | 2026-10-25/26 阶段报告；保留原基线和判定。 |
| 旧错误包 | [bugs/evidence/bug-reports-20261026](bugs/evidence/bug-reports-20261026) | 7 个 RTL 根因、上游核查、误报/漏报复核和证据限制。 |
| 版本/覆盖汇总 | [`manifest/`](../manifest) | baseline、DUT 映射、RTL 哈希、coverage-summary。 |
| 当前页面登记 | [navigation.json](navigation.json) | schema 1；`./scripts/ucv check lsu` 使用。 |

## 阅读边界

- 当前历史结论绑定固定提交 `893e1580…`：19 个 DUT，`upstream-review-regression-02` 为 **582 PASS / 7 FAIL / 589 项**，交付门禁 **FAIL**。这是 2026-10-26 的记录；本次文档整理未运行 native，也未在 `public-a0c2a26cb` 重建 DUT。
- 旧 `unified-regression-02` 的 518 PASS 是增强断言前的历史记录，不能覆盖 7 个新 FAIL。历史 17 次 FAIL 缺少逐节点日志，不能统一判成误报。
- 声明式功能 bin 的 100% 是采样覆盖，不是独立 reached/checked 完成率；剩余 338 个 toggle 点在 `gaps/` 中逐 DUT 分类。
- 设计合同由验证侧整理，未声明设计 owner 批准；未证明边界见 [Design spec](spec/design/README.md)。
