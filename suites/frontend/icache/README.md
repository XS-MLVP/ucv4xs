# ICACHE 验证工程

当前原生加载器使用`ucv.runtime.native_seed`转发`ucv run --seed`，不再固定为1。
根`tests/test_frontend_runtime_seed.py`核验实际构造参数及构造间环境变化；历史CLI
seed标注不等于当时已使用该原生seed。此修复不改变RTL/native构建或已知XFAIL的判定。

当前全仓事务适配在协作发布检查点收尾，不声明全仓完成。DataBank 与 MetaBank 已接入
严格类型/固定ABI、SDK唯一驱动、双相lossless持续采样、逐输入UID和严格fixture finish。
MetaBank实际两138-bit宏，tag/valid来源分开；共享SRAM控制事务进一步区分hold、真实
消费相位和逐row reset清扫，不能用模型瞬间清零代替真实写入。两DUT最新定向 **305 PASS**，
原功能项及判定保持；全文与最终运行见
[MetaBank/SRAM当前合同](docs/metabank-transaction-adaptation.md)、
[DataBank历史检查点及后续](docs/databank-transaction-adaptation.md)和
[全仓协作交接](../../../docs/collaboration-checkpoint-20261102.md)。
其他DUT与进一步生命周期/API组合仍未签核，不因目录或静态零命中获得完整事务验收信用。

包含 11 个独立 DUT，统一使用 toffee。完整配方见 `ucv.json`，基线按根目录、硬件分组、工程目录继承。

```sh
ucv prepare icache
ucv build icache
ucv run icache --workers 8
```

从仓库根目录运行 `.venv/bin/ucv` 或 `scripts/ucv`。生成 RTL、原生包和运行结果不纳入 Git。领域模型与检查器保留在本工程，历史缺陷和功能合同见 `docs/`、`manifest/`。历史说明不代表当前基线结论。
