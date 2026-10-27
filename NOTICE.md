# 许可与第三方来源

本仓库自有验证代码、`ucv` 编排工具和维护文档采用 MPL-2.0，全文见 `LICENSE`。导入文件已有的版权或许可声明保留并优先适用；迁移不授予第三方源码额外权利。

香山及其递归依赖从各自源码仓库获取，其许可证保留在独立检出中。toffee、Picker、xcomm、Verilator 也保留各自许可证；版本和仓库见 `dependencies/versions.json`。这些工具与生成产物不作为本仓库自有代码重新许可。

历史 BPU 独立生成入口存于 `docs/history/bpu/BpuVerifyMain.original.scala` 和 Git 历史，不参与当前构建。`docs/history/bpu/*.patch` 保存针对上游香山的历史差异，其所引用上游代码继续适用香山原有许可。VAGQ 的 internal 实现源码与生成结果不纳入公开 Git 资产。
