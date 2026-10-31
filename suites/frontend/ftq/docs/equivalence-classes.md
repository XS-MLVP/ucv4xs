# FTQ 行为等价类与关键组合

状态：2026-10-30，`public-893e1580b` + DefaultConfig。验证包按 agent / driver / monitor / checker / transaction 分层。每一类都有实际断言；没有只关联
bin 名或 `sample()` 的条目。

| 类/组合 ID | 合法前提及构造序列 | 为什么可合并/必须拆开 | 正确/错误结果差异 | 断言/nodeid | 状态 |
|---|---|---|---|---|---|
| E-RQ-ID | 同一 `{flag,value}` 的多次解析；同 value 不同 flag | 身份由完整循环指针决定，flag 不同是不同 entry | 合并 vs 两个独立队首 | `FTQ-RQ-001`，`test_resolve_flag.py`、`test_resolve_queue.py` | 已检查 |
| E-RQ-PHYS | 16 个物理槽、enq/deq 回绕 | 槽号只是存储位置，语义按插入顺序；回绕必须覆盖全部槽 | 所有槽可用、顺序不因槽号改变 | `FTQ-RQ-002/006`，`test_resolve_stream.py`、`test_resolve_slot_sweep.py` | 已检查 |
| E-RQ-SLOT | 8 个分支槽 × 4 个来源 | 槽位是训练载荷的显式位置，不能合并 | 槽位置/target 正确；越界槽被丢弃 | `FTQ-RQ-002`，`test_resolve_branch_slots.py`、`test_resolve_slot_sweep.py` | 已检查（8 以内）；越界见 E-RQ-OVERFLOW |
| E-RQ-SRC | 后端 lane 0/1/2 + IFU 的所有 16 种有效组合 | 来源优先级固定 b0→b1→b2→IFU，顺序不同会产生不同槽内容 | 分支槽顺序与来源一致 | `FTQ-RQ-002`，`test_resolve_lane_matrix.py` | 已检查 |
| E-RQ-FILTER | 正确 direct、return、误预测条件、非返回间接 | 过滤器只去掉无需训练的报告；不能把误预测当正确丢弃 | 是否产生训练事务 | `FTQ-RQ-005`，`test_resolve_queue.py` | 已检查 |
| E-RQ-FLUSH | 老/新指针的 backend redirect；同 value 的 bpuEnqueue | 重定向按循环顺序只冲刷年轻条目；BPU 入队只比较 value | 保留 vs 冲刷 | `FTQ-RQ-007/008`，模型测试 | 已检查 |
| E-RQ-GUARD | 12 条驻留后继续接纳 | 保留区阻止新条目但允许排空 | 第 13 条丢弃、已接纳序列不丢 | `FTQ-RQ-009` | 已检查 |
| E-RQ-OVERFLOW | 8 条已记录后第 9 条；6 条后同拍 3 条 | 容量满后必须丢弃；不能把 Vec 越界当成新槽 | 8 条保留 vs 覆盖 slot 0/7 | `FTQ-RQ-011`，**strict XFAIL** | 真实缺陷，未修复 |
| E-CQ-LANE | CommitWidth=8 的 lane 优先级；64 个物理槽 | lane 顺序是程序顺序；槽号只影响存储 | payload/顺序正确；门限整组拒绝 | `FTQ-CQ-002/004`，lane 矩阵、随机流 | 已检查 |
| E-CQ-GUARD | 56 条驻留、8 条 reserve | 门限按整组拒绝，排空后恢复 | 不覆盖未消费动作 | `FTQ-CQ-004` | 已检查 |
| E-TOP-PTR | bpu/pf/fetch/pnr/commit 的正常推进、32/64 深度、回绕 | 五个所有权有独立合同，不能用一个指针代替 | 每拍顺序/距离不变量 | `FTQ-TOP-003/008/013` + 被动不变量监视器 | 已检查 |
| E-TOP-TWOPREF | SameLine/Overlap1/Overlap2/Interleave/Conflict | 五种 case 的 `valid` 和推进量不同；跨页必须 Conflict | `twoPrefetchCase.value`、`pfPtr` | `FTQ-TOP-005`，case 矩阵 | 已检查 |
| E-TOP-TWOFETCH | PNR、总大小、同页、realTwoFetch、异常标记 | 每个条件都能单独否决第二请求 | `req_1.valid`、`fetchPtr` | `FTQ-TOP-006/009` | 已检查 |
| E-TOP-REDIRECT | 后端/IFU、flushAfter/flush、ahead 命中/不命中、同拍冲突 | 重定向来源和延迟不同；先写指针再转发 meta | 指针/目标/meta/flush | `FTQ-TOP-010/011` | 已检查 |
| E-TOP-EXC | IPF/GPF/AF、satp、首个 block、三个 block 后清除 | 异常种类映射不同；标记只污染窗口内块 | prefetch/fetch 标记 | `FTQ-TOP-012` | 已检查（第二块见残余） |
| E-TOP-META | 64 个物理索引、全 1/全 0 payload、高索引 | 索引是存储身份；bit 方向是独立可观察量 | 读回值/重定向/训练/提交 meta | `FTQ-TOP-017` | 已检查 |
| E-TOP-TRAIN | 首误预测掩码、训练缓存保持、同索引/更老重定向 | 首误预测后分支不能训练；同索引重定向保留该训练 | 分支 valid 掩码、`train.valid` | `FTQ-TOP-015/016` | 已检查 |
| E-TOP-RESOLVE-MATRIX | 顶层物理槽 0..15 × 分支槽 0..7 × 来源（b0/b1/b2/IFU） | 槽号只是存储位置，来源顺序决定分支位置；顶层必须逐槽验证被实例化 ResolveQueue 的写入路径 | 每个组合的分支位置、顺序、target；IFU 命中驻留 entry 时只追加 | `FTQ-RQ-002/TOP-015`，`test_top_level_branch_slot_and_source_priority_sweep`、`test_ifu_resolve_hits_resident_entry_in_every_physical_slot` | 已检查（顶层行覆盖 100%） |

## 组合策略与边界

- ResolveQueue 的物理槽 × 分支槽 × 来源做了有界穷举（16×8×4）；顶层 Ftq 用同一
  矩阵逐槽验证被实例化的 ResolveQueue，并单独覆盖 IFU 逐物理槽命中；CommitQueue 做了
  64 槽 × 8 lane 的有界穷举；FTQ 的 meta 做了 64 索引 × 全 bit 双向。
- 大空间（任意 PC、任意分支历史、任意重定向序列）不做“pairwise 即闭合”的声明：
  `test_resolve_model.py` 在 8 分支容量内做 180 轮约束随机，覆盖合并、冲刷、BPU 入队、
  排空的时序组合；超出容量的部分单独列为缺陷类。
- 同拍竞争、背压多拍、先错后对、失效后重建、回绕都有定向用例；非法输入不进入等价类，
  由构建器拒绝或标注为压力。
