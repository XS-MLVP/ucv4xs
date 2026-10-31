---
name: pin-schema-and-suite-migration
description: 复核旧验证工程迁移是否只隐藏了端口名，区分 fixture 接线、兼容别名和真正事务边界；按调用链、采样所有权与独立正负对照验收。待审核，不替代正式分层方法。
---

# 迁移边界复核（待审核，2026-10-31 修订）

本草稿原版把替换 io_* 为 P.p_* / P.io(...) 当成迁移完成依据。该标准不成立，
现撤回这一推荐；原始测试结果不改写，历史修订见
[结构与 skill 复核](../../docs/lessons/structure-skill-review-20261031.md)。

## 适用场景与输入

旧工程仍用端口字典或 cycle-level harness，但目录/静态门禁已经全绿时使用。输入为
工程合同、fixtures、实际驱动/采样调用链、正负对照及新的收集清单。

## 正确区分三类工作

| 层次 | 能证明什么 | 不能证明什么 |
|---|---|---|
| fixture 集中与插件导入 | pytest 接线可发现、生命周期入口明确 | 每 DUT 唯一所有者、事务语义正确 |
| P.p_* 常量 / P.io 前缀助手 | 字符串集中管理，可能减少拼写重复 | 不再碰引脚、typed transaction、缺端口检查 |
| driver/monitor/agent/checker 边界 | 经合同和负对照验证后，才能证明相应职责 | 全硬件正确、全部 API 行为或覆盖闭环 |

不创建 common/pins.py。DUT 特有映射放在 DUT 的 ports/bundle；跨 DUT 共享机制
按职责命名。当前六工程根的 legacy_pins.py 是临时兼容列表，仍计入事务边界缺口，
不要把物理端口列表改名后继续当成已经合格的功能用例 API。

## 操作步骤

1. 用 `ucv run <suite> --collect-only` 保存实际收集清单；对照 nodeid 和判定，不能
   仅比较计数。fixture 可以参数化，不按 fixture 函数数量推导 DUT 覆盖。
2. 对一条用例跟踪请求类型 → driver 接受/撤销 → monitor 采样 → 独立 checker；
   发现 raw dict、物理字段别名或手工数拍时，列为待适配，而不是绕过静态扫描。
3. 为协议定义有单位、合法域和身份的事务；把编码/解码和精确拍对齐收进适配层。
   原生句柄仍由 fixture/harness 持有，事务 API 不是原生方法的同名转发。
4. fixture 首选显式名字/参数，不靠测试文件路径暗中选择不同参考模型。移动文件后
   检查 __file__.parents、资源路径、插件路径和临时目录恢复。
5. 用合法输入和针对性错误期望成对验证；缺端口、重复 claim、未知字段、丢采样应
   在边界报错。自检分类需按内容复核，目录名或 marker 本身不改变硬件 credit。
6. 汇总结构与事务迁移两个状态；保留所有真实 FAIL/ERROR/XFAIL/SKIP/UNCERTAIN。

## 产出与验收

从仓库根执行，ucv 在隔离进程中处理工程路径和原生覆盖：

```sh
.venv/bin/ucv run <suite> --collect-only
.venv/bin/python scripts/audit-suite-layout.py --strict
.venv/bin/python scripts/audit-suite-layout.py --require-transaction-boundary
.venv/bin/python -m pytest -q tests/test_suite_layout.py
```

结构门禁只证明接线；事务门禁当前会报告旧工程的真实未迁移项。零静态命中仍需
调用链审查及正负对照。记录测试选择、源码版本、合同、实际输出，不预填 PASS。

## 本次复核边界

十工程 fixture 结构已统一，但 IFU/LSQ/LSU/MMU/DCache/VAGQ 的功能用例仍使用
物理字段或兼容别名；不能称为全事务化完成。BPU/FTQ/ICache/Sbuffer 未发现本扫描
覆盖的静态泄漏，也不等于语义认证。已有构建、回归和历史判定保持各自原义。
