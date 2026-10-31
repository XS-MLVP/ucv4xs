# 独占 SQ 前缀与字节低位：Forward→PSQ→SQ→真实 Wrapper 闭环

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


**结果：四层正式定向补例通过，完整贡献范围真实重跑为 1072 节点、903 PASS /
169 FAIL、0 ERROR/SKIP。原 1066 个节点结果与失败全文保持，新增 6 个节点
全部通过；四 build 三类分母/点全集不变、旧命中无丢失。整体仍为
`ACTIVE_NOT_ACCEPTED`，不能据此签核全部 LSQ。**

## 1. 请求→功能点→真实检查→证据

先建立 [语义合同](../contracts/store-prefix-byte-windows.md)，再实现补例。
固定开源 `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` 的原样
RTL/Chisel、Picker native build、X Reactor 安装和独立参考模型不变。

| 要求 | 实际补充的语义和检查 | 证据 |
|---|---|---|
| 人类可读功能点 | 较年轻同址 Store 已真实写入，但 Load 只能看到其派发时独占 SQ 上界之前的最年轻合法原字节 | `FWD/PSQ/SQ-WINDOW.prefix_byte`；Wrapper 复用原 82 项中的 aligned/youngest/sqid/wrap，不删旧功能 |
| 合法年龄窗口 | 连续 `[0,63)`、`[63,127)`、`[127,191)`、`[191,254)`、`[254,256)`，包含非满和 shifted-full 跨环；每个 Load 上界为对应 Store position+1 | `lsqverify/store_prefix.py`、各层 `test_prefix_byte_windows.py` |
| 年轻别名负对照 | 每窗首/末 Store 同 VA/PA、不同 byte；末项先写入再查询，早 Load 返回首项，末 Load 返回末项 | compact witness 的 alias 字节、SQ 前缀和响应摘要；有效 S2 独立字节 oracle |
| 地址和 mask | 普通 1B、offset0..15，VA/PA 页内偏移相同；只比较有效 mask 的原 byte，其他 byte 为 don't-care | `check_byte`、完整 staged 模型的逐拍实际比较与物理安全检查 |
| 真父级，不以叶子代替 | PSQ 由真实 STA/STD 写入；SQ 保留实际 VSQ→PSQ；Wrapper 实际交错派发 Store→Load，每个 Forward 对应真实 Load UID，再用原 uop 执行 S3 | PSQ/SQ 各 256 Store、768 三路响应；Wrapper 每 lane 各 256 Store＋256 Load、256 绑定查询 |
| 容量/背压/复用 | 最多 64 Store/64 Load、128 活跃 ROB；查询时禁止 Store 许可并保持 Sbuffer 背压，之后按真实消费和正常出队完成；窗口间不 reset/取消 | 五窗公开 head/tail、真实 Sbuffer 字节/mask/PA、出队时序与完成摘要 |
| 三类覆盖闭环 | 四组 fresh baseline/after，旧节点保留，同源摘要/build/点全集，三类差集及 LCOV 独立报告 | `tools/audit_store_prefix_byte_v1.py`、四组 `store-prefix-byte-evidence-v1.json` |
| 保留完整贡献范围和失败 | 实际重跑 1072 节点，保留主目录外的 local_reset/normal_mixed/sq_endpoint 贡献者；所有旧 169 FAIL 全文保持 | `store-prefix-contributor-regression-01` manifest/JUnit 与专项报告 |
| 最终矩阵不混域 | 38 DUT 矩阵收录 22 条独立定向报告，统一 regression15 的原分子、分母、缺口与 227 FAIL 不回填 | `results/lsq-progress-regression-15/final-evidence-matrix-v1.json` 与 gap/failure 审计 |

## 2. 两个探测失败：保留并修正消费归属能力

`store-prefix-byte-probe-01` 为 **4 PASS/2 FAIL**。Forward 和 Wrapper 三 lane
通过；通用 PSQ/SQ actor 消费时仅按 VA 查找 owner，合法重复 VA 的末项被匹配
到首 UID，触发“part 已消费”断言。原失败、栈及 source aggregate 保留，
不能把它当成 RTL 重复消费反例，也没有通过改成唯一地址来缩小目标。

新用例的独立消费者按外部程序顺序将真实 Sbuffer fire 绑定到原 UID，再检查
地址、mask、原字节和正常出队 `fire_tick+2`；只有真实 fire/出队才更新外部
台账。通用 PSQ/SQ actor、参考模型和历史测试没有修改，所有 staged 比较保持。
`store-prefix-byte-probe-02` 的六节点全部通过，旧探测产物均保留。

前两次探测采用 63/63/63/63/4 长度；固定源 `ForwardModule.sv:2907,9304`
显示 Low 年龄掩码受 `(1<<head.value)-1` 限制。要使物理 slot62 成为跨环 Low
候选，需 head.value=63 且同时保留 slot62，达到 64 项边界。因此正式合同在
运行前补入两个 shifted-full 窗口，不能把可合法到达的 slot62 判为不可达。

## 3. 正式 fresh baseline/after：与完整运行分开报告

| DUT | PASS 前→后 | raw line 点前→后 | toggle 前→后 / 同分母 | branch 前→后 / 同分母 |
|---|---:|---:|---:|---:|
| ForwardModule | 20→21 | 2→2 / 2 | 31767→35154 / 40034 | 48→54 / 54 |
| PhysicalStoreQueue | 7→8 | 144→145 / 213 | 77545→79503 / 86318 | 1548→1623 / 1834 |
| StoreQueue | 13→14 | 151→151 / 223 | 86371→89700 / 102374 | 1942→2014 / 2198 |
| LsqWrapper | 19→22 | 501→502 / 3654 | 138356→151877 / 322010 | 8675→9985 / 18670 |

每对 source aggregate、native build 和三类点全集相同，旧节点结果及命中无丢失。
这里的 branch 增益是定向选择集的差异，不等同于关闭统一回归的旧 branch 缺口。

LCOV 原始源码闭包行分别为 **250→253/253、5447→5461/5817、
8574→8580/8968、28032→30856/59602**，与 raw line 点分开保留。

正式目录前缀为 `forward/psq/sq/lsq-prefix-byte-{baseline,after}-01`，均在
`results/` 下。baseline 继承上一 payload/strict 的原选择集，after 只增加
本合同的 1/1/1/3 个节点，不删已有失败或改其结果。

### 指定向量与地址目标

- 每 build 的 `s1CanForwardLow` bits0..62 与 `s1SelectLowOH` bits1..63，
  三路、两个方向，共 **756/756** 命中（四组 baseline 均为 0/756）。
- 位编号按原生信号分别报告，**不把反向编码的 OH bit 当作同号物理槽**。
  另外 12 个向量方向点原样保留在分母和缺失库存中；本轮没有用这个定向
  目标子集豁免初始化或宣称全局不可达。
- 所有 64 槽的 VA bits[3:0] 双方向共 **512/512** 命中。Forward 是公开 bank
  输入；其余三层对应真实 `dataEntries_<slot>_vaddr` 寄存器，不混称为存储。
  前值分别 0、446、257、280；输入 PA 的合法页内偏移亦由公共响应/消费检查。
- 叶子 768 查询 UID；PSQ/SQ 各 256 Store UID 和 768 有效 S2；Wrapper
  三个 lane 用例合计 **768 Store、768 原 Load** 正常完成，各有独立 witness。

## 4. 完整同 native build 贡献范围的实际重跑

```sh
python3 -B tools/run_summary.py --name store-prefix-contributor-regression-01 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper tests/local_reset tests/normal_mixed/test_original_seeds.py tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py
```

实际运行 **2554.67 秒**，结果 **903 PASS/169 FAIL，0 ERROR/0 SKIP**。
相对 `store-strict-contributor-regression-02`，全部原 **1066 节点**结果和失败
全文保持，新增 **6 节点 PASS**。前后 169 FAIL 归一化全文 SHA 相同：
`31bff24c501b3d000c5c9ae3eb572f8210133ff0218d0a89803f92451eec04cf`。
只归一化 Python 对象地址，不删真实值、payload、行号或断言。

| DUT | 实际导出数前→后 | toggle 前→后 / 同分母 | 真正新增 | 旧命中丢失 |
|---|---:|---:|---:|---:|
| ForwardModule | 185→186 | 36329→37654 / 40034 | **1325** | 0 |
| PhysicalStoreQueue | 68→69 | 81886→82574 / 86318 | **688** | 0 |
| StoreQueue | 81→82 | 92398→93468 / 102374 | **1070** | 0 |
| LsqWrapper | 732→735 | 275384→276779 / 322010 | **1395** | 0 |

完整运行三类点全集与固定 build 不变，**line/branch 无新命中也无丢失**。
branch 仍为 54/54、1830/1834、2191/2198、18592/18670；LCOV 仍为
253/253、5817/5817、8968/8968、59595/59602。
不能把上一节的 6/75/72/1310 个定向 branch 增益加到本表。
完整运行的 VA 低四位目标也独立重建：Forward **188→512/512**、PSQ
**511→512/512**、SQ **477→512/512**、Wrapper **404→512/512**。这些是
对应完整贡献范围的方向点变化，不使用定向 baseline 的前值替换它们。

四 build 的原 primary journal 摘要逐项保持；Wrapper 原 **2196 份**公开/
check/actor 摘要的 records、字节数及 SHA 均相等。新六份 compact witness
与正式定向对应者相等。既有 Wrapper 主目录外的 41 个贡献节点实际执行，
不是旧 dat OR 新 dat，也没有再次漏掉原生贡献者。

## 5. 复核、审计状态与剩余边界

```sh
# 四组定向及1072节点实际完整贡献范围证据
python3 -B tools/audit_store_prefix_byte_v1.py
python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15
```

完整审计链 `post-regression-prefix-byte-01.log` 已 **exit 0**，22 条定向报告、
新完整运行、旧 169/227 FAIL 和历史 scope 失败均进入索引。当前覆盖单调性门禁
PASS/required=true/waived=false；这表示证据和该门禁完成，不是功能失败变绿。
派生报告旧字节按 SHA 归档到 `audit-history/`，原 dat/JUnit/历史失败不改。

最终全链连续两次 exit 0，日志为 `post-regression-prefix-byte-final-01.log` 与
`post-regression-prefix-byte-idempotence-01.log`。12 份关键报告 SHA 全等，
52 份受检历史 manifest/JUnit/dat SHA 保持，未新增重复归档。12 份相关 Python
源通过语法解析，24 份补例/辅助源的无 skip/xfail 检查保持通过。

新完整运行仍有非 wrapper toggle 缺口：Forward **2380**、PSQ **3744**、SQ
**8906**、Wrapper **45231**。原统一 regression15 的 235610 toggle、563 branch
库存不变，不将独立结果回填；其余 DUT/变体、真实父级失败和最终全范围验收仍
开放。下一优先项包括真实恢复状态分支、UQ/跨页和其余可达业务载荷情形。

本轮不覆盖所有 size、跨 word/page、别名重放、strict 禁用反馈、异常、取消或
总线组合，原有用例与失败不删减。未生成逐拍 JSON、波形、完整源码副本；
未执行或声称 Git commit/push。目标保持 active，gap-closure 尚未完成。
