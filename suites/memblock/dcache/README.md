# DCache 验证工程

包含 13 个独立 DUT，统一使用 toffee。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
ucv prepare dcache
ucv build dcache
ucv run dcache --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。

## 当前入口

- [工程资料入口](docs/README.md)
- [Design spec](docs/spec/design/README.md)：层次、接口合同与各 DUT 功能点。
- [Verification spec](docs/spec/verification/README.md)：验证范围、用例映射、当前记录与未关闭项。
- [验证约束](docs/spec/verification/constraints.md)：范围、资源和接口边界约束（稳定 ID）。
- [问题记录](docs/bugs/README.md)：当前 open/closed 状态；历史台账保留在 `manifest/known-issues.json`。
- `./scripts/ucv info dcache --dut <key>`：逐 DUT 显示模块功能点、验证报告和固定基线 Chisel 定义/实例化来源。

## 状态边界

当前默认公开基线为根配置的 `public-a0c2a26cb`。覆盖与功能证据来自
`public-893e1580b`（`results/soundness-recheck-03`：210 PASS + 3 XFAIL，61 个功能组
100%）；2026-11-01 事务修复检查点另记录 **229 PASS + 3 XFAIL**，原项判定保持，新增项
包含事务/自检。两组记录都绑定旧基线，没有自动迁移到新默认基线；在新基线上完成
prepare/build/run 前，不得把历史 PASS 当作当前基线结论。`DCACHE-REFILL-NOT-RESIDENT`
已按验证环境误报关闭（`invalid`，只关闭 `public-893e1580b` 的旧 RTL 归因）；当前基线
仍为 `unverified`，不能把“新基线未跑”当成旧 RTL 指控复活。当前汇总以根
[docs/status.md](../../../docs/status.md) 为准。

历史报告保留原日期、基线、运行目录和结论边界；本次文档整理只改变存放位置和链接，
不回写判定。领域模型与检查器保留在本工程。
