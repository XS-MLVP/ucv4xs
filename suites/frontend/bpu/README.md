# BPU 验证工程

包含 10 个独立 DUT，统一使用 toffee。与其他公开工程共用 DefaultConfig 完整香山 RTL，再提取各模块闭包供 Picker 构建；不单独 elaboration BPU 或注入 Scala 入口。整芯片优化可能裁剪原独立顶层端口，旧用例的接口适配仍在进行。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
ucv prepare bpu
ucv build bpu
ucv run bpu --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。
领域模型与检查器保留在本工程，历史缺陷和功能合同见 `docs/`、`manifest/`。

整芯片 DefaultConfig 的 `Bpu` 导出会DCE掉未被FTQ消费的 prediction target 和 perfMeta；
当前事务显式保留 `None`/valid-only 观察边界，不伪造字段。metadata没有ready输入；SDK
协议适配使用只读常量，不能进入driver所有权。依赖被裁字段的场景不能借组件DUT结果签核。
`tests/framework/test_defaultconfig_dimensions.py`自检声明的4-way MainBTB、MicroTAGE
5/9两表和8-table TAGE/SC参数，并核对真实生成schema的公开投影及MainBTB槽数；它不证明
内部八张表的完整配置/语义都已验证。旧MinimalConfig场景的迁移和当前完整回归仍在进行。

PHR的当前物理投影、输入UID/fire/flush账本、收尾及给定输入流后的独立模型边界见
[PHR事务合同](docs/phr-transaction-contract.md)。PHR输入target的比较不是被DCE的公开BPU
target证据；旧52-cell/19-fold/flag描述不用于认证当前532-cell/33-fold value-only合同。

自主流水的20组lookup fold、真实训练沿前接受、4-way加victim metadata投影及精确原
owner计划见[流水事务合同](docs/pipeline-transaction-contract.md)。当前只将既有模型
与真实ABI接通，不宣称全BPU组合、短/长来源程序或MBTB写回清理已经全部完成。

MainBTB的四路owner计划、真实零tag、50/49位半字地址边界、嵌套只读metadata及有界
checked-close见[MainBTB事务合同](docs/mbtb-transaction-contract.md)。完整cleanup已核验，
但逐输入/训练来源账本及其余生命周期仍在审计；真实功能FAIL不改为期望或豁免。
