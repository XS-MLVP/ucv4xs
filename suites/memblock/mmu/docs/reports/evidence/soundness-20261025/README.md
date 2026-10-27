# 可信度复核证据入口

- before-reports.json、before-case-sources.json：修改前旧报告/case 全文。
- claims.json：按报告/归因开始的逐条复核，保留撤回结论。
- case-audit.json：395 个 test 定义；静态 PASS 不是语义正确证明。
- collection.json：408 unique nodeids，390 functional、2 characterization、
  3 structural-stress、13 checker-selftest。
- final-runs.json：17 个真实 RTL DUT run 共 395 PASS，checker 自检 13 PASS；
  精确 line/toggle/branch、manifest/build/source hashes。
- final-residuals.json：当前 run 全部分母与开放范围；详细逐点数据在各 run audit。
- source-drift-review.json：逐 run 选择/依赖、运行后源码差异和处置；不改历史快照。
- audit-cases-at-final-run.py.txt：hash 匹配的旧审计器；后续仅 category/review
  元数据变化，交付工具验证除这两个输出字段外 AST 完全相同。
- baseline-before-finalization.json、verify-delivery-before-finalization.py.txt、
  delivery-audit-before-finalization.json：旧交付配置/结果，不覆盖原始结论。
- isa-sources.json：官方固定版规范章节及本地 Fence.scala 哈希；正文未存档，
  raw_content_sha256=null，不能冒充规范原文的哈希证据。
- pma-configuration-provenance.json：固定 PMA oracle 与 SoC 配置源 SHA；
  build-specific 配置证据，不是独立架构正确性证明。
- wrapper-01-failure.log：保留完整首轮失败日志；原 results run 不删除、不覆盖。

最终 run 的 committed 表示 runner 产物完成，不是版本控制提交。
soundness-final-l2tlbwrapper-01 的 50 PASS + 1 FAIL 保留在 results/，不是最终
基线；PMP 正例未对齐 1GiB PPN 修正后 wrapper -02 为 52 PASS，另保留独立负例。
soundness-isa-controls-01 的 16 PASS 是对照证据，不重复加到最终 408 总数。

最终自检入口：tools/verify_delivery.py；结果：results/delivery-audit.json。
这不是所有语义点/ISA/MMU/SoC 签核。
