# LSQ 三类 RTL 覆盖率证据与缺口契约

本契约用于 `memblock-hash/lsq/` 的 Picker/X Reactor 原生运行。它定义
line、toggle、branch 的证据边界和缺口闭环格式，不把覆盖率指标当成功能
PASS，也不把独立叶子覆盖率合并成父级覆盖率。

## 1. 计数边界

1. 每个 committed native build、每个 DUT export、每个结果目录分别保留
   `hit/total` 分母；不得跨 DUT、跨叶子、跨历史运行或跨结果目录相加分子/分母
   后宣称一个 DUT 的覆盖率。
2. `coverage.dat` 使用 Verilator `SystemC::Coverage-3` 点记录。每个 line、
   toggle、branch 点至少有源文件 `f`、源位置 `l`、类型 `t`、点描述 `o`、层次
   `h` 和命中计数；`S`（存在时）保留额外源范围。
3. `coverage.info` 的 `DA` 可提供 line，`BRDA` 可提供 branch；没有 toggle
   点记录时，不能从 line/branch 或功能覆盖推导 toggle 已覆盖。默认摘要保留
   各 native build 的 coverage artifact SHA、工具命令、命中/分母和缺口清单
   SHA，不保留逐拍 JSON、波形或完整源副本。
4. 当前 Picker 导出参数包含
   `--vflag=--no-coverage-expr --no-coverage-fsm`，所以 expr/FSM 的 `0/0`
   是配置限制，不应被解释为 expr/FSM 已完成验证。用户本目标的强制指标仍是
   line、toggle、branch。
5. `coverage-scope-audit-v1.json` 从同一 dat 明确分离 `raw_all`、
   `picker_wrapper` 和 `original_nonwrapper`；每个域必须满足 hit+missing=total，
   且 raw_all=wrapper+nonwrapper。锁定 Verilator 的 summary 是含 wrapper 的原始域，
   不得把它的 hit/total 与非 wrapper 的 missing 混写在同一矩阵栏。
   最终矩阵 toggle/branch 使用非 wrapper 点；line 使用原始源码闭包的 LCOV 行，
   原始 line 点另行保留。修正报告域不是激励增益，也不改变原 dat 或任意点身份。
6. 一次性初始化分支与时钟驱动业务分支必须分开。不能因为源行含 `reset`
   就断言它是动态 reset 情形，也不能仅凭关键词就断言它不可达。
   `initial-branch-boundary-audit-v1.json` 对具体缺口核验固定源 SHA、精确
   `initial begin` 到 `end // initial` 范围及 `ENABLE_INITIAL_REG_` 外层范围。
   这种分支在 time-zero 执行一次；后续事务/reset 不能重新进入。同一初始化
   的另一启动值也许命中另一臂，但不等于 LSQ 动态功能验证。分类为工具/初始化
   边界后仍保留全部未命中点和原分母，不称作覆盖率提升或全局不可达。

## 2. 缺口记录

每个可审计缺口（不论 line、toggle 还是 branch）应能还原以下字段；摘要模式
可只保存按源位置/点描述聚合后的记录和完整记录 SHA，需逐项复核时再生成受限
的 gaps 产物：

```json
{
  "run": "lsq-progress-regression-13",
  "build_id": "<native build id>",
  "dut_export": "DUTLsqWrapperDut",
  "metric": "line|toggle|branch",
  "source": "dut/.../<generated source>.v",
  "source_line": 123,
  "point": "<toggle transition or branch arm or line block>",
  "hierarchy": "TOP...",
  "hit": 0,
  "feature_id": "<human-readable microarchitecture feature>",
  "case_id": "<actual test/case or explicit untested case>",
  "classification": "existing_feature_missing_case|missing_feature_point|unreachable_or_dont_care|configuration_not_retained|tool_or_artifact_limit",
  "evidence": "<contract, source context, test result or tool limitation>",
  "before_after": "before_missing|after_hit|after_still_missing|not_rerun",
  "reproducer": "<seed/command/result artifact when applicable>"
}
```

分类含义：

- `existing_feature_missing_case`：功能点和行为合同已有，但合法输入/时序/背压/
  取消/reset/异常/配置枚举尚未被实际用例打到；必须补例重跑。
- `missing_feature_point`：覆盖点对应的微架构行为在现有功能点合同中整体缺失；
  必须先补充可读功能点和独立参考语义，再补例。
- `unreachable_or_dont_care`：由固定接口合同、生成参数或明确 don't-care 证明
  不可达；保留源位置和证明，不修改分母。
- `configuration_not_retained`：当前实际 Picker/RTL 配置没有保留该覆盖域，例如
  expr/FSM 被显式关闭；不能用其他配置结果代替当前 DUT 证据。
- `tool_or_artifact_limit`：工具、清理策略或产物格式无法取得该指标；必须保留
  具体版本、命令、缺失文件/字段和影响范围，不能当作覆盖通过。

真实 DUT/参考模型 FAIL 不得改写成上述“已覆盖”分类；它们要在功能结果和缺口
审计中独立保留，并记录是否阻止了对应的补例闭环。

## 3. 前后比较与门禁

每轮补例至少保存：

1. 同一 DUT/同一结果目录的 `before`、`after` 三类点集合或命中计数；
2. 新命中集合 SHA、仍未命中集合 SHA、分母变化（正常情况下应为零）以及
   实际功能检查结果；
3. 新增 FAIL、历史 FAIL、UID/外部请求终态和源聚合指纹是否保持；
4. 每条仍未覆盖点的分类、证据和下一步边界。

覆盖提升只能由真实激励和真实重跑产生。不得通过删除点、修改目标 RTL/Chisel、
屏蔽失败、xfail/skip、改变分母或跨目录借用命中结果来制造提升。
