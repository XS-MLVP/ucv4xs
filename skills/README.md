# ucv4xs Skill 索引

全部工程的经验入口见 [验证经验与复盘](../docs/lessons/README.md)。

## ucv4xs-workflow

[项目工作流](ucv4xs-workflow/SKILL.md)：面向本仓库的基线管理、项目内安装、完整 RTL 生成、DUT 构建、隔离回归及新增工程。仓库协作约定见 [AGENTS.md](../AGENTS.md)。

## rtl-verification-soundness

- [踩坑复盘与防复发手册](rtl-verification-soundness/SKILL.md)：按真实误报/漏检经历组织，每条包含当时的问题、错误处理、原因、迁移措施和防复发验收。
- [防复发速查卡](rtl-verification-soundness/CARD.md)：换模块或修改检查器时逐条检查。

这不是通用验证教材，也不是按模块堆叠 Bug 清单。核心是把过去的错误决策变成其他模块中可执行的防复发检查。

## 用法

1. 开始新模块时，先读速查卡，挑与接口、控制事件和状态相关的历史坑。
2. 回到主文查看具体来源及限制，不复制不适用的协议假设。
3. 落实三样工件：经验条目、合法/错误成对回归、持续检查入口。
4. 未执行的检查标待执行；不要把文档整理当成回归已通过。

主文带 skill frontmatter，可按文件路径读取复用；这里只维护文档，不代表已向当前工具注册或完成自动加载。

## 文档关系

| 文档 | 定位 |
|---|---|
| `skills/rtl-verification-soundness/SKILL.md` | 从实际踩坑提炼跨模块防复发动作；附原始复核来源 |
| `skills/rtl-verification-soundness/CARD.md` | 日常执行速查 |
| [跨模块假阴性总结](../docs/lessons/false-negatives-20261026.md) | 本项目既有跨模块案例、数字与状态快照；本轮未更新这些历史数据 |
| 各模块的审计、二次裁决和 Bug 报告 | 具体证据、修改历史及结论边界，不被本 skill 替代 |
