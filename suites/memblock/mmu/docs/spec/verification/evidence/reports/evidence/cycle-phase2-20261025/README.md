# 第二阶段闭合项与残余证据（2026-10-25）

本目录汇总第二阶段（TLBNonBlock、TLB GPA、并发缺口、Bitmap、PMA、PTW full_gvpn、
HPTW accessFault、satp/sfence、残余覆盖、MBIST 边界）的 compact 证据。

- `phase2-closures.json`：每个缺口的处置、最终 run、覆盖与功能指标、证据摘要。
- `phase2-residuals.json`：仍未闭合项的逐项分类与证据边界。
- 完整覆盖数据库、manifest、lcov/html 在对应 `results/<run>/`。
- RTL SHA-256 见 `manifest/*-rtl.sha256`；构建报告、Picker/Verilator 版本与 seed
  记录在 JSON 的 `tools` 字段和 `results/builds/`。

所有 run 均为 committed、coverage_complete=true、pytest_exitstatus=0；strict XFAIL
只用于已明确记录边界的候选行为，不计入 PASS，也不冒充通过。
