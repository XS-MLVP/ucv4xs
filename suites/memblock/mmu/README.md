# MMU 验证工程

包含 17 个独立 DUT，统一使用 toffee。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
ucv prepare mmu
ucv build mmu
ucv run mmu --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。

## 当前入口

- [文档入口](docs/README.md)与[当前页面登记](docs/navigation.json)。
- [Design spec](docs/spec/design/README.md)：真实 TLB/MMU 层次、PTW 合同和设计确认边界。
- [Verification spec](docs/spec/verification/README.md)：17 个 DUT、功能点、可信度复核和完成条件。
- [残余项](docs/spec/verification/residuals.md)：未归为正式 bug 的覆盖/结构/范围边界。
- [问题记录](docs/bugs/README.md)；历史证据在 `docs/spec/verification/evidence/`。
- `./scripts/ucv info mmu --dut <key>`：逐 DUT 显示模块功能点、验证报告和固定基线 Chisel 定义/实例化来源。

## 状态摘要

2026-10-26 可信度复核（固定源码 `XiangShan 893e1580…`）记录 17 个真实 RTL DUT suite：**395 PASS + 13 checker/model 自检 PASS = 408 PASS，0 FAIL/XFAIL/SKIP**。旧 376 PASS + 5 XFAIL 是历史基线，5 个 XFAIL 已被验证侧反证，旧 RTL 根因结论撤回。采样 bin 100% 不等于语义闭合；fake-PTE、条件化 no-fence、HFENCE.GVMA、A/D/privilege 交叉和残余功能序列仍开放。本次 2026-11-09 文档整理未运行 native；当前 `public-a0c2a26cb` 未重建/复跑。

领域模型与检查器保留在本工程；历史缺陷和合同见 `docs/`、`manifest/`。历史说明不代表当前基线结论。
