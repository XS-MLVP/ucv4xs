# 目录、清理与 Skill 复核（2026-10-31）

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 修正此前结论

此前“全部模块已完成事务架构迁移”的说法过宽。实际完成了 fixture 接线、原生句柄
访问收口和部分端口字符串集中；将 io_* 改成 P.p_* / P.io(...) 并没有改变测试的
引脚级语义。历史构建/回归数字仍属于原运行，不因此失效，也不构成架构认证。

修正后的 AST 扫描同时识别物理字符串、io_* keyword 和端口别名：

| 工程 | 功能测试文件中的引脚级表达式 | 状态 |
|---|---:|---|
| IFU | 313 | 需要事务适配 |
| LSQ | 1057 | 需要事务适配 |
| LSU | 140 | 需要事务适配 |
| MMU | 29 | 需要事务适配 |
| DCache | 2 | 需要事务适配 |
| VAGQ | 179 | 需要事务适配 |
| BPU / FTQ / ICache / Sbuffer | 0 | 本扫描未发现泄漏，不代表语义验收 |

这些是表达式/源文件统计，不是 pytest 参数化后的用例数。fixture entries 是静态可见
接线条目，包括 helper/session fixture，不等于 DUT owner 数。原报告将其称作每 DUT
owner 数的结论撤回。审计还不能证明采样、引脚 claim、独立 oracle 或负对照有效。

## lsqverify 这一层是否应去掉

`suites/memblock/lsq/` 是工程资产/配置边界；`lsqverify/` 是 Python 导入命名空间。
两者职责不同，并非两套框架。根 pyproject 只发布 src/ucv，工程验证包没有另立发行包。

| 方案 | 好处 | 代价与结论 |
|---|---|---|
| 保留 lsqverify | 显式独立命名空间；tests/配置/文档与实现分离；现有 imports 和资源路径稳定 | 名字略重复，但当前综合风险最低 |
| 将 common/deq/model 等提升到 lsq 根 | 磁盘少一层 | 需重写 imports、插件字符串、__file__ 资源锚点；十工程都有 common；进程隔离可以避免部分运行冲突，但同进程工具/IDE 的命名仍模糊 |
| 工程根自身成为 suites.memblock.lsq 命名空间 | 可去掉 lsqverify 层且保持唯一全限定导入 | 是合法的简化方向；需建立可安装/可发现的 namespace 包边界，统一 PYTHONPATH/runner，并迁移所有 imports 和资源锚点，不可退回 import common |
| src/ucv_lsq 或统一 ucv_suites.<group>.<suite> | 有规范 namespace，可做安装后导入验证 | 第一种更多一层；第二种需完整包边界与构建策略。应作为独立明确迁移，不能以删除目录冒充分层改进 |

**本轮决定：先保留当前唯一命名空间，不把分析请求擅自变成全仓路径迁移。**
lsqverify 不是必须存在；如果要落实用户提出的少一层方案，优先评估让工程根自身成为
suites.memblock.lsq，而不是把 common 提升成无前缀的顶级包。包名不是正式 skill 的
强制拼写，真正优先事项是：

- DUT 特有 ports/bundle 与事务类型回到 DUT；common 只容纳跨 DUT 共享机制；
- 减少测试侧 raw pin 字典/别名，驱动/采样/比较不因改名而被隐藏；
- fixture 显式命名/参数化，避免按测试文件路径暗换模型；
- 验证包不反向依赖 tests 的支持实现。LSQ 当前
  `lsqverify/local_reset/fixtures.py -> tests.local_reset.reference` 仍是已识别的反向依赖，
  本次不把它写成已修复，也不为统一外观大规模搬动测试支持代码。

## 本次实际修复

- 清理 22 个散落 fst/dat 与 596 个源码侧 Python/pytest 缓存目录，297830621 字节；
  删除清单与 SHA-256 在 [回收记录](../history/storage-reclamation-20261031.json)。
  已确认无活动工程运行/构建和打开的目标文件；未触碰受管 results、构建缓存、工具链、
  原生包或未提交源码。松散文件缺少受管 provenance，删除后不再可用。
- 修复 DCache/LSU/MMU/Sbuffer 的 tests/conftest.py 从工程根搬迁后留下的 ROOT 错误；
  改为 parents[1]，临时目录统一从 ucv.runtime.scratch_root() 解析。DCache 退出恢复
  调用方原 cwd，而不是误切进 tests/。增加对应回归。
- 布局审计区分 structural wiring 与 transaction boundary；别名不再绕过统计。
- 新增 scripts/audit-skills.py 与测试，核对 YAML、项目便携命名、唯一名称、本地链接、
  锁定框架文档路径和实际 API。修复不存在的 MultiCycle 名、docs/guides 路径、
  临时 Git 检出中的 patch 相对路径、FTQ 索引死链和分层表格格式。
- 待审核 pin-schema 草稿撤回“别名替换等于迁移”的方法。待审核内容不晋升为正式规则。

## Skill 合法性的四个层次

1. **格式**：三个 SKILL.md 入口和四篇 pending 草稿的 YAML 可解析。便携小写 kebab
   name 是本项目约定，不宣称是 OpenCode V2 强制限制。
2. **发现/加载**：V2 标准源包括 .opencode/skills、.agents/skills 等，或配置 skills
   显式加入的目录。普通仓库 skills/ 下的方法文件不因此自动注册；本次不改客户端配置
   或全局权限，不声称安装生效。具体见官方
   [V2 Skills](https://opencode.ai/v2/docs/skills)。
   官方亦支持 source 根的平铺 Markdown；所以不应直接把 ./skills 或 ./skills/pending
   整目录配置成 source：README.md 可能被当成 skill，阶段子目录里的普通 .md 则未必
   被发现。当前 3/4/13 是项目意图分类，不是客户端 registry 的实际清单。发布时应给
   每个正式入口单独的 SKILL.md 目录和明确 source，草稿保持未审批，不自动启用。
3. **内容**：检查命令路径/API 与事实边界；入口存在不代表行为测试通过。
4. **权限**：skill 只是工作流指导，不授权删除范围外数据、上传、内部源码外传或改判定。

## 复核命令

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/audit-skills.py --strict --check-framework
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/audit-suite-layout.py --strict
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/audit-suite-layout.py --require-transaction-boundary
python3.12 -B scripts/audit-assets.py
```

事务边界命令对上述六工程返回非零是正确发现，不改成绿。本轮不重新认证硬件，
保留此前的 FAIL/XFAIL/UNCERTAIN/SKIP。缓存和受管结果不是“目录垃圾”；若另行回收，
须先选定具体 run、保留 verdict/log/manifest，并记录不可用的原始覆盖输入。


## 本轮实际验证结果

- 根 tests/：80 PASS；结构 --strict：十工程通过；技能审计：20 篇文档、3 个入口、
  4 个草稿、13 篇支持文档，元数据/引用/13 个框架 API 检查通过。
- 十工程 collect-only 全部 exit 0：BPU 41031、FTQ 111、ICache 294、IFU 147、
  DCache 213、LSQ 2575、LSU 529、MMU 408、Sbuffer 31、VAGQ 467。
- 定向原生检查：Sbuffer 31 PASS；MMU wrapper/tlb 33 PASS；DCache queue/ctrl
  24 PASS；LSU load_s2 47 PASS / 1 既有 FAIL（prefetch miss perf event）。
- 事务边界检查按预期 exit 1，保留六工程 needs-adapter，不伪造全绿。
- 资产审计 PASS：10 工程、132 DUT、134685 条历史证据、errors 为空。
- 检查后源码树（排除受管 results/、工具、环境、构建缓存）无散落 fst/vcd/dat/pyc，
  无 __pycache__ 或 .pytest_cache。受管 LSQ/VAGQ/Sbuffer 结果计数与 gaps 未改变。
- 未进行全硬件重回归、未移动验证包、未安装或启用客户端 skill、未提交/推送。
