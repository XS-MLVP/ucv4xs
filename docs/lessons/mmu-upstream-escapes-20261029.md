# MMU：全绿基线之外的上游差分漏检案例

> 这是 2026-10-29 旧工作区审计的案例摘要，不是新一轮上游查询、仿真或 ucv4xs 验收。原始报告、探针和完整结果仍在外部历史工作区；本次只保存案例与可核对的来源身份，没有迁入或运行探针，没有修改 RTL/正式模型。

## 当时相信了什么、反例是什么

旧工作区的 408 PASS 由 395 个真实 RTL DUT 测试节点和 13 个 checker/model 自检组成。它只能说明该次选择通过，不能推出行为空间完整。固定基线 `893e1580b705d81f113c30c7a05734e09a08050e` 之后的上游修复，促使复核者在真实 DUT 上编写独立探针。

原报告记录：fetch 到 `5c80ed989e73627875fc0d7ff03516daee0aec84`（2026-10-28），候选修复不属于本地基线祖先；8 个失败探针覆盖 7 类行为，PTW/LLPTW 的同类 MXR 问题各占一个。探针在 `probes/`，不在原 408 的默认选择中，未转 XFAIL；因此“408 PASS”和“另有 8 FAIL”可以同时成立。

## 逐项漏检机制和证明范围

| 行为与历史上游线索 | 原用例为何漏掉 | 探针证明及边界 |
|---|---|---|
| PTW/LLPTW 隐式 G-stage MXR，#6099 / `c9c7b3706` | LLPTW 正例把错误权限行为写成 expected，PTW 缺对应场景 | 两个 DUT 的权限/访存观察；不能借此声称整个虚拟化链路合规 |
| global HFENCE.GVMA 的 VS-stage 失效，#6082 / `761139eb5` | 只填 h=2，漏 h=1 | 指定 PageCache 条目的失效行为 |
| HLVX 最终 PMP 命令，#6017 / `6df1c45d9` | `hlvx` 已接线但从未置 1 | TLB 发出的命令错误；最终 PMP/PMA 异常需要集成验证 |
| need_gpa 阶段匹配，#6285 / `d0cb19e78` | 只送正确阶段响应，无同 VPN 异阶段负例 | 等待期间错误阶段响应被消费的局部行为 |
| 混合 NAPOT L0 sector，#5961 / `c44e9389d` | 全 NAPOT 用例走了另一条路径 | 混合 sector 的 n/PPN/命中行为，不等于全路径穷举 |
| 地址定向 HFENCE.GVMA 非叶失效，#6681 | 填过非叶项，但只检查叶项/superpage | 非叶 G-stage 项失效缺口 |
| AF/PF 优先级，#6670 | 只测高 PPN 且权限允许；模型以 `and not af` 压制 PF | 直接注入 `s1_af=1` 且 X=0 的优先级反例；**没有完成高 PPN 页表到最终异常的全链路复现** |

前五类在当时已有上游修复，后两类在该次查询时仍 open；这里不声明它们此后的状态。它们与之前已撤回的五个历史 XFAIL 归因不同，不能混记。

## 为什么这不是“多跑几个种子”能解决的

- 合同/责任没有落实：端口可接线，不等于该语义有人验证；叶块命令不能替代最终异常证明。
- oracle 同源：错误权限和优先级被 expected 固化，更多相等比较仍会通过。
- 行为空间缺口：阶段、混合编码、非叶项及错误响应历史没有进入区分性组合。
- 复核没有闭环：只填不查、只到达不比较，默认选择之外的反例未反馈回需求和持续检查。

ISA 能提供架构语义依据，但不会自动生成模块状态/协议断言，也不能独自规定内部匹配和缓存组织。原审计使用的官方 ISA 固定版本为 `v20260120`；本摘要没有重新查验正文。原来源清单未保存网页正文，`raw_content_sha256=null`，不能补造原文哈希。

## 原审计尚未证明或尚未实施的内容

另三项 need_gpa clear/计数清理/年龄与重放冻结仅有代码级线索，未动态复现；二态 DUT 不能证明 robidx X 传播。SPVP、PMA LR、Fence VMID、CSR/TLB 的 MPRV/MPV、NC replay 等需要集成/全核，不能记为本层已验证。

原审计定位了危险 oracle，但没有据此修改正式测试/model 或回移 RTL。本次文档整理同样不实施这些整改，不把探针失败写成已修复。

## 案例对应的方法

| 从本案例应迁移的动作 | 具体方法 |
|---|---|
| 分清叶块责任、上层承接与缺观察点 | [需求与边界](../../skills/design/requirements-boundary.md) |
| 加入异阶段、混合编码、非叶失效和故障交叉 | [行为等价类](../../skills/design/behavior-equivalence.md) |
| 撤销实现自证，建立独立答案与错误控制 | [独立 oracle](../../skills/execution/independent-oracle.md) |
| 对账字段、collection 和实际 checker | [checker 与运行时](../../skills/execution/checker-and-runtime.md) |
| 将有界探针结果与残余登记对齐 | [归因与证据](../../skills/review/triage-and-evidence.md) |

## 外部来源与可复核身份

以下 `history://mmu/` 路径相对原 MMU 历史工作区，通过本机 `historical_roots` 配置定位，见 [外部接入说明](../local-configuration.md)。本次整理实际读取并核对了下列文件；未将其注册进既有 `docs/history/evidence-index.json`，也不保证别的机器已配置或可用。

| 来源 | 本次读取到的 SHA-256 |
|---|---|
| `history://mmu/docs/reports/upstream-escaped-defects-20261029.md` | `0023d2b7861c63b8c87064e3846283decb178ef706902e9e6892ff814be00e60` |
| `history://mmu/probes/test_upstream_escaped.py` | `af480b22d35134467b46613d4ef59d1cf2c91373e087e55e1e078d2681748e11` |
| `history://mmu/docs/reports/evidence/upstream-audit-20261029/probe-results.json` | `fb145f65aaef104f309a2f51875d87827dd3ae78bdcc8eb730577d8fdf64f3cf` |

同目录的 `probe-source.sha256` 与本次读取的探针哈希一致。完整失败日志、上游提交和 RTL/build 身份仍由原报告指向的 evidence 目录保存；摘要不替代原始证据。
