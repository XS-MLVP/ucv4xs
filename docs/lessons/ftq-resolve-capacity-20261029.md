# 案例：ResolveQueue 100% 行覆盖下的分支槽溢出

日期：2026-10-29。基线：`public-893e1580b` + DefaultConfig。证据：
[缺陷记录](../../suites/frontend/ftq/docs/bugs/resolve-queue-branch-overflow.md)、
运行 `suites/frontend/ftq/results/ftq-final-20261029`。

## 原问题

ResolveQueue 的独立 DUT 已达到 100% 行覆盖，但一个 FTQ entry 的分支槽只有 8 个；
当第九条分支解析到达，或被解析的 entry 只剩 1–2 个空槽而同拍到达多条时，训练载荷
可能被改写。这个行为此前没有被功能点、用例或覆盖率数字暴露。

## 错误假设

1. “每个 entry 最多 8 条分支”被当成“生产者不会送第 9 条”。实际 DefaultConfig 的
   BPU meta 有 10 个 BTB 结果位置，fetch block 可以合法产生 9/10 条分支解析。
2. “`indexWhere` 找不到空槽返回 8，动态 Vec 下标会安全忽略”。实际动态下标被截断/回绕，
   写入落到仍有效的槽 0 或 7，并重新置 valid。
3. “行覆盖 100% 等于容量边界已验证”。溢出路径的赋值就在已覆盖的行里，行计数器无法区分
   “写空槽”和“覆盖有效槽”。

## 反例与定位

- 单条溢出：先记录 8 条，再送第 9 条；第 9 条的 position/target 覆盖 slot 7。
- 同拍溢出：先记录 6 条，再同拍送 3 条；前两条填 6/7，第三条回绕覆盖 slot 0。
- 两个 strict XFAIL 保留在 `test_resolve_overflow.py`；若 RTL 修复，strict XPASS 会要求
  重新评估，而不是静默通过。
- 根因：`ResolveQueue.scala:137-138` 的
  `branches(firstEmpty + PopCount(hitPrevious(i)))` 没有容量守卫。

## 修正与防复发

- 功能点新增 **FTQ-RQ-011**：超容量报告必须丢弃，已记录分支不可改写。
- 独立 `ResolveMergeModel` 按语义容量 8 建模；随机序列在 8 以内验证合并/冲刷/排空，
  溢出由定向用例单独覆盖。
- 顶层测试的 `allocate()` 强制合法生产者序列（prediction → meta → 可选 commit），
  被动不变量监视器每拍检查 `pnr ≤ bpu` 等设计声明；这同时暴露了早期在未预测索引上
  直接写 meta 的非法激励。
- 不比较无效分支槽的 payload：合同未定义这些字段，避免把 stale 数据当功能差异。

## 剩余限制

- RTL 未修复；本案例只提供缺陷证据和复现，不提供修复后的复验。
- 顶层闭包中 ResolveQueue 的 IFU 命中 fallback 仍未逐槽枚举（R-02），不能宣称顶层
  行覆盖 100%。
- 若上游后续已修复，需要按上游差分流程核对祖先关系与本地产物，而不是仅依据提交名。
