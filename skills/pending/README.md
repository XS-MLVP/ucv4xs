# 待审核 Skill

本目录保存本轮重构总结出、**尚未经过项目维护者审核**的方法。它们可以按需阅读和试用，
但在审核前不替代 [AGENTS.md](../../AGENTS.md)、[项目工作流](../ucv4xs-workflow/SKILL.md)
或已发布 skill 的约束。审核通过后，再移动到 `skills/<阶段>/` 并更新正式索引。

| 文件 | 适用问题 | 本轮依据 |
|---|---|---|
| [依赖升级与能力核对](dependency-upgrade-and-capability-audit.md) | 虚拟环境依赖落后、分发名变化、需要确认框架实际能力 | `uc-toffee 2.1.0` / `uc-xcomm 1.1.1` 实际安装与根测试 |
| [Fixture 集中与 agent 边界](fixture-consolidation.md) | 每 DUT 的 `env/pytest.py`、子目录 conftest、测试直接摸引脚 | 十工程根 fixture 迁移与布局审计 |
| [框架能力选型](framework-capability-selection.md) | 该复用 toffee 的哪个组件，何时允许工程自建 | BPU/FTQ/ICache 现有分层与 Toffee 2.1 公共 API |
| [迁移边界复核](pin-schema-and-suite-migration.md) | 目录/静态门禁全绿但仍有引脚级耦合 | 2026-10-31 撤回“端口别名等于事务迁移”的错误标准 |

审核时至少核对：命令是否仍与当前锁定版本一致、证据是否可复现、是否把未执行项写成了
通过、是否保留真实 FAIL/XFAIL/SKIP。
