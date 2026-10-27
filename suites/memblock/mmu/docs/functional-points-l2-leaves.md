# L2TLB 叶子功能点（MissQueue / Prefetch / PTWRepeater / PTWFilter）

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


## L2TlbMissQueue

| ID | 功能点 | 关键行为 |
|---|---|---|
| L2MQ-01 | 40 项 FIFO 保持入队顺序和完整 payload | VPN/s2xlate/source/isLLptw 原样出队 |
| L2MQ-02 | 满时 in_ready=0，空时 out_valid=0 | 容量边界与 valid 一致 |
| L2MQ-03 | flush（sfence 或 CSR changed）清空所有条目 | 输出立即无效、可重新入队 |
| L2MQ-04 | 同时入队/出队时队列推进正确 | 不丢项、不重复 |
| L2MQ-05 | isHptwReq/hptwId 在本生成配置中恒为 0 | 仅记录结构常量，不伪造 1 值 |

## L2TlbPrefetch

| ID | 功能点 | 关键行为 |
|---|---|---|
| L2PF-01 | 对输入 VPN 的下一 4KB 行发起预取 | 输出 `next_line(vpn)`，valid 保持至 ready |
| L2PF-02 | 最近 4 个已消费预取行作为历史过滤 | 重复的下一行被抑制 |
| L2PF-03 | 消费时写历史并循环 index | 4 个历史槽和 index 回绕都可达 |
| L2PF-04 | flush 清 valid 与历史；CSR mode changed 也触发 flush | 之后同一请求可重新预取 |
| L2PF-05 | s2xlate 编码由 virt/vsatp/hgatp 生成 | 0/1/2/3 四类都由实际模式组合产生 |
| L2PF-06 | next-line 加法在 VPN 高位回绕到 0 | 不走越界值 |
| L2PF-07 | 仅预取，不检查 TLB 是否已命中；历史表只做去重 | 这是预取器的功能边界 |

## 范围与已知缺口

- 本轮只验证 `L2TlbMissQueue` 和 `L2TlbPrefetch` 两个叶子；不包含 `PtwCache`、
  `PTW`、`HPTW`、`LLPTW`、`Bitmap`、`MptChecker` 或 L2TLB 顶层组合。
- 两个叶子的行覆盖均为 100%；分支各剩一个时间零 initial reset 隐式 else。
- MissQueue 的 `isHptwReq`/`hptwId` 在本配置为常量 0，toggle 的 0->1/1->0 在结构上
  不可达；其余 toggle 缺口为未构造的历史槽/输入组合。

## PTWRepeaterNB（Frontend/MemBlock 的 PTW 请求重复器）

真实实例：`Frontend.sv:inner_itlbRepeater2`、`MemBlock.sv:inner_itlbRepeater3`。

| ID | 功能点 | 关键行为 |
|---|---|---|
| RPT-01 | 空闲时接收一条 TLB 请求并向 PTW 发射 | `tlb_req_0_ready=~sent`；请求先锁存，再以 `ptw_req_0_valid=sent` 保持到 PTW ready |
| RPT-02 | PTW 响应寄存并保持给 TLB | `recv` 置位后 `tlb_resp_valid` 保持，直到 `tlb_resp_ready` |
| RPT-03 | 翻译阶段/payload 原样透传 | vpn、s2xlate、s1 entry、s2 entry、PPN 等均不改写 |
| RPT-04 | 单 outstanding：完成前不接受第二条请求 | 请求相位未完成时 `req_ready=0`，第二次 valid 不改变已锁存 VPN |
| RPT-05 | flush 取消请求和响应两个相位 | sfence 或 satp/vsatp/hgatp/priv-virt changed 经 1 拍延迟后同时清 sent/recv |
| RPT-06 | 全 0/全 1 payload 位保持 | 数据位压力测试下响应的 tag/PPN 与驱动值一致 |

## PTWFilter（Frontend ITLB 的 8 项 PTW 待处理过滤器）

真实实例：`Frontend.sv:inner_itlbRepeater1`。它不是 L2TLB 内部实例，不能由 L2TLB
顶层结果代替。

| ID | 功能点 | 关键行为 |
|---|---|---|
| FIL-01 | 8 项待处理队列与容量 | 最多 8 条 distinct 请求；满时 `tlb_req_0_ready=0`，drain 后恢复 |
| FIL-02 | 向 PTW 发射并按翻译键匹配响应 | PTW 响应经 tag/asid/vmid/level/valididx 命中后，下一拍产生一次 TLB 响应 |
| FIL-03 | 相同 VPN+s2xlate 的重复请求合并 | 只产生一条 PTW 请求、一个 pending entry；一次响应完成重复请求 |
| FIL-04 | 不匹配响应不释放请求 | 错误 tag 的响应不产生 TLB 响应；之后正确响应仍可完成 |
| FIL-05 | 响应 payload/getGpa/valididx/ppn_low 透传 | s1/s2 entry、getGpa、8 个 valididx/ppn_low/pteidx 与匹配响应一致 |
| FIL-06 | 四类翻译阶段都参与匹配 | noS2 / onlyStage1 / onlyStage2 / allStage 的响应键均可命中 |
| FIL-07 | flush 清空所有 pending 与 inflight 状态 | sfence 和四类 CSR changed 均独立生效；flush 后可重新入队 |
| FIL-08 | 同周期响应抑制发射 | 响应与队头发射同拍时置 `issue_filtered`，不重复发射并释放 entry |
| FIL-09 | 8 条 outstanding 的 inflight 计数 | 连续发射 8 条后计数升到 8，再随响应逐条降回 |
| FIL-10 | 输入/输出全位扫描 | 全 0/全 1 payload、vpn、s2xlate、getGpa 位均实际翻转两方向 |

## 范围与已知缺口

- 已验证的 L2 叶子/小中层块：`L2TlbMissQueue`、`L2TlbPrefetch`、`PTWRepeaterNB`、
  `PTWFilter`。四者行覆盖均为 100%。
- `PtwCache`、`PTW`、`HPTW`、`LLPTW`、`Bitmap`、`BitmapCache`、`PMP` 目前只在
  真实 L2TLB 顶层中以真实 RTL 被驱动，**尚未**建立独立 DUT 的叶级功能点闭环；
  不能把 L2TLB 顶层覆盖数字当作这些子块的独立验收。
- `PTWFilter` 的 `PTWNewFilter` 变体（带 vector/hint 端口）未单独建 DUT；本工程验证的是
  Frontend 实例化到的 8 项 `PTWFilter` 生成变体。
- `PTWRepeaterNB` 的 `passReady` 变体未覆盖；本工程使用实际生成的 non-passReady 端口。


## 第二阶段残余分类（PTWFilter）

`PTWFilter` 最终 run `ptwfilter-final-16` 为 14 PASS，行 206/206、branch 91/92、
toggle 4411/4414；残余仅 3 个 toggle：`issue_filtered_vmid_hit:1->0` 与
`ptwResp_newMatchVec_onlyS2_hit_tag_match_1/2:1->0`，属于特定并发响应/边界组合的
情况枚举，不是缺失功能点。新增 `test_high_tag_match_directions` 和
`test_only_s2_high_tag_match` 覆盖高 VPN 位 33..35、way 1..7 与 onlyStage2
tag/vmid 匹配方向。
完整未覆盖点见 `results/ptwfilter-final-16/coverage-audit.json`，known-issue
`PTWFILTER-RESIDUAL-TOGGLE` 已记录。
