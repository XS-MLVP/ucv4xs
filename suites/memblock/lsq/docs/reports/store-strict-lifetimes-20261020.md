# Store strict 等待生命周期：三层补例、完整目录重跑与未通过的覆盖门禁

> **后续同范围重跑已解决覆盖丢失**：原 Wrapper 原生覆盖有 730 个贡献节点，
> 四目录命令遗漏了主目录外的 41 个；真实补跑逐点重现全部 2125 差集及计数。
> fresh 完整 1066 节点运行为 897 PASS/169 FAIL，三类旧命中无丢失，当前门禁
> PASS、未豁免。下文保留的是此前 1025 节点的真实失败及当时未建立根因的
> 历史调查，原产物不改；新证据见 [范围闭环报告](native-contributor-scope-20261020.md)。

**结果：PSQ、StoreQueue、完整 LsqWrapper 的新语义补例均通过；真实四目录
重跑为 1025 节点、868 PASS / 157 FAIL，原 1018 节点的结果和失败全文保持。
但 Wrapper 丢失 2125 个旧 toggle 命中，必需覆盖单调性门禁为 `FAILED_OPEN`，
未豁免，整体 LSQ 仍为 `ACTIVE_NOT_ACCEPTED`，目标继续活动。**

固定开源 `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` 原样
RTL/Chisel、Picker native build 和独立参考模型不变。以下所有分母均按 DUT
独立保留，不跨层或跨目录合并，也不回填统一 regression15。

## 请求到实际证据的检查矩阵

| 要求 | 新情形与真实检查 | 证据 |
|---|---|---|
| 用例前语义功能点 | 64 项中只缺最后 STA；strict 等所有较老地址，精确等待只等已就绪预测目标；填洞后原 UID 正常完成 | `docs/contracts/store-strict-wait-lifetimes.md`，先建立合同，再实现测试 |
| 独立公共接口检查 | `store_strict.check_response` 独立检查有效响应、完整依赖身份、解除等待后的 mask/8B 原字节；原 fixture 每拍参考与 PA 安全检查保持开启 | `lsqverify/store_strict.py`、三层测试文件；未改通用 actor/参考模型 |
| 真实父级 | PSQ 保留实际 Forward/Deq/UQ/Sbuffer；SQ 保留 VSQ→PSQ；Wrapper 由实际 Store 产生内部 ready，再经真实 Replay 授权/反馈与 VLQ 完成 | 三组 native manifest、固定 RTL/包/build SHA、`store-strict-lifetimes-evidence-v1.json` |
| 身份、背压、容量与复用 | 四代依赖 SQ63/127/191/255，双 flag 四种身份全部公开检查；每代 64 项先禁止许可并保持 Sbuffer 背压，真实 STA 到达后授予许可、消费并正常释放 | 各 after 的 `cases/**/store-strict-lifetimes-witness.json`；每父级 256 Store UID、36 个三路 S2 响应 |
| Wrapper 跨层完整完成 | 每代独立派发 3 strict＋3 precise Load，uop 解码字段不改。strict 真实 S3 进入地址依赖 Replay，precise 正常 S3 不能越过旧 strict 释放；真实 STA＋匹配 wakeup 后消费公开 slot 授权、检查 retry 并按原 slot 反馈 | Wrapper 累计 24 Load、12 次真实 Replay 握手及反馈、256 次 Store Sbuffer 消费和出队，最后 LQ/SQ/Replay 为空 |
| 三类覆盖及源位置 | baseline 节点保留，同 source aggregate/build/点全集；每个严格选择臂保留原源行和层次，分别报告 raw line 与 LCOV | 三组 `directed-gap-closure-*-v1.json` 和 strict 专项报告 |
| 不隐藏失败或缩小目标 | 完整执行四个测试目录，原 1018 节点及 157 FAIL 全文保持；7 个新增节点 PASS 不抵消旧失败 | `store-strict-directory-regression-01/pytest.xml`、manifest、`store-strict-regression-evidence-v1.json` |
| 不用净增益掩盖旧命中丢失 | Wrapper 新中 17340，同时旧中丢失 2125；差集摘要、源位置样本与失败门禁明确保留，根因尚未建立 | 专项目录报告 `open_toggle_loss`、`coverage_monotonicity` 与统一 required-gates 报告 |
| 统一完整范围 | 38 行最终矩阵收录 18 条独立补例；统一 regression15 2330 节点、2103 PASS/227 FAIL、原始 dat 与缺口全集不变 | `results/lsq-progress-regression-15/final-evidence-matrix-v1.json`、failure-preservation audit |

PSQ/SQ 新增各自 `*-STRICT.lifecycle` 情形 bin；Wrapper 为原 82 项主目录内
strict/addr_hole/sqid/wrap 的复合补例，不删除旧目录或改变其功能覆盖率分母。
本轮不声明 disabled feedback、bitmap-only 唤醒、别名、越窗、总线、取消和
异常的旧失败已修复。

## 三组 fresh baseline/after

| DUT | PASS 前→后 | 原始 line 点前→后 | toggle 前→后 | branch 前→后 | LCOV 原始源码闭包行前→后 |
|---|---:|---:|---:|---:|---:|
| PhysicalStoreQueue | 6→7 | 144→144 / 213 | 77450→77545 / 86318 | 1544→1548 / 1834 | 5447→5447 / 5817 |
| StoreQueue | 12→13 | 151→151 / 223 | 86189→86371 / 102374 | 1934→1942 / 2198 | 8574→8574 / 8968 |
| LsqWrapper | 18→19 | 157→501 / 3654 | 86617→138356 / 322010 | 7222→8675 / 18670 | 24275→28032 / 59602 |

每对同源集合摘要、相同 native build 和完整点全集，三类均无旧命中丢失。
这些是有边界的定向实验，不是完整目录/统一回归的覆盖率。

目录：`psq-strict-lifetimes-baseline-01 → psq-strict-lifetimes-after-01`、
`sq-strict-lifetimes-baseline-01 → sq-strict-lifetimes-after-01`、
`lsq-strict-lifetimes-baseline-01 → lsq-strict-lifetimes-after-01`，均位于 `results/`。

三层真实 Forward child 的 strict 选择臂各 **12/12** 命中。原始源行是
`ForwardModule.sv:11330/11340/11342/11344`，另两 lane 分别加 62/124；
专项报告保留每个源行、层次、原始计数和 regression15 计数。
其中 PSQ 命中 regression15 原缺口 4 个，SQ 命中 8 个；Wrapper 原先已中
这些选择臂，因此其本轮定向 branch 增益 **不**代表关闭原 78 个 branch 缺口。
统一 563 个缺口仍是原运行的真实记录，不从中扣掉定向交集。

## 四目录实际重跑：不是 coverage OR

命令与 source aggregate 保存在 `results/store-strict-directory-regression-01/`：

```sh
python3 -B tools/run_summary.py --name store-strict-directory-regression-01 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper
```

真实运行 **2536.47 秒**，结果 **868 PASS / 157 FAIL，0 ERROR / 0 SKIP**。
与 regression15 对应 1018 个旧节点逐项比较，结果和失败全文只归一化 Python
对象地址，其他 assertion 实际值、数据及栈行号保持。157 FAIL 的前后摘要均为：
`5ca60c251f9b47cae9b2e53ca51eccd27f04e96b47efb2d1016265015f0dbf7f`。

| DUT | toggle 原→新 / 同分母 | 新命中 | 旧命中丢失 | branch 原→新 / 同分母 |
|---|---:|---:|---:|---:|
| ForwardModule | 28717→36329 / 40034 | 7612 | 0 | 54→54 / 54 |
| PhysicalStoreQueue | 70532→81886 / 86318 | 11354 | 0 | 1826→1830 / 1834 |
| StoreQueue | 78334→92398 / 102374 | 14064 | 0 | 2183→2191 / 2198 |
| LsqWrapper | 258044→273259 / 322010 | 17340 | **2125** | 18592→18592 / 18670 |

原始 line 点均无变化：2/2、213/213、223/223、3654/3654。
LCOV 源码闭包行保持 253/253、5817/5817、8968/8968、59595/59602。
PSQ 剩余 4 个 branch 都是已有具体源范围证据的初始化点；SQ 剩余 7 个中，
5 个初始化点、2 个仍待合法恢复情形补例。不能据此签核 PSQ/SQ 全部语义。

Wrapper 的净 toggle 增益是 15215，但**净增益不是旧命中保留门禁通过**。
失败门禁明确为：

```json
{"name":"all_old_native_hits_retained","passed":false,"status":"FAILED_OPEN","failed_duts":["lsq_wrapper"],"newly_missing_toggle_points":2125,"required":true,"waived":false}
```

## 2125 个丢失点：已知事实与未建立的根因

- 原 dat 与新 dat 的点全集、源位置、native build、固定 RTL SHA 相同。
  差集 SHA 是 `02745152ec8d03a8b3fc0fe1bd36d8db6a3de8adc33705aae55dda486b2bf03d`。
- 丢失点分散于 Replay（693）、Forward（132）、TwoLevelRRArbiter（117）、
  PSQ（71）以及 Uncache 等源文件，不把它们统称为初始化/常量/don't-care。
  报告保存完整按源计数、旧计数分布、12 个源行/位域样本及可从两 dat 恢复的摘要，
  没有复制全部源代码或逐点列表。
- 旧 Wrapper **689 节点的 2067 份** public/check/actor journal 摘要逐项相同，
  records、serialized bytes、streamed SHA 均相等。整体 stream 摘要为
  `86c58a53d1ea227adbc20ac279df7fadc3cb4395acad87f5a15ed44a9a41b7a8`。
  这排除了这些已记录流的可见差异，但**不能推出内部轨迹或 native 上下文相同**。
- 重复相同 18 节点/2-worker baseline：54 份 stream 与全部 native 点计数相同；
  dat SHA 均为 `a4c6f8ddc64dbaaf7237e66e289a1bdc1157f40e186c68907b04b051e4dc9c89`。
- 进一步单 worker 比较：单独执行原 Wrapper `[aligned-0]`，与先执行既有
  Forward/PSQ/SQ 三个节点再执行它；Wrapper 的三份 stream 及全部 native
  计数也相同，dat SHA 均为
  `7e4f339d30dcacf69c8e663cca5be73ca6175191738ba4ab96e64f11f6844e6a`。
- 原完整回归使用 4 workers，新目录运行使用 8 workers；这是实验差异，
  **不是已证明的因果解释**。上述两个小型诊断均未复现大目录的丢失。
  根因状态为 `NOT_ESTABLISHED`，尚需更细的原节点→native 导出点摘要与隔离实验。

新严格依赖用例只见证依赖 value=63 和四组双 flag，不声称所有依赖 value
或每一个方向点都在有效负载阶段完成了语义验证。

## 审计结果与复核

```sh
# 各定向 PSQ/SQ/Wrapper 补例可独立复核；这些命令应 exit 0
python3 -B tools/audit_store_strict_lifetimes_v1.py --dut physical_store_queue
python3 -B tools/audit_store_strict_lifetimes_v1.py --dut store_queue
python3 -B tools/audit_store_strict_lifetimes_v1.py --dut lsq_wrapper

# 包含完整目录的必需单调性门禁，目前应 exit 1，不是绿色验收
python3 -B tools/audit_store_strict_lifetimes_v1.py
python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15
```

全链完成其他证据检查、失败保持、18 条定向索引及 38 行矩阵更新后，仍以
**exit 1** 返回必需门禁失败。日志是
`results/lsq-progress-regression-15/post-regression-store-strict-01.log`。
`post-regression-required-gates-v1.json` 明确 `evidence_checks_completed=true` 与
`status=OPEN_REQUIRED_GATES`；“证据已审计”不等于“覆盖门禁通过”。
失败门禁同时位于最终矩阵的 Wrapper 剩余边界与顶层，不因刷新报告消失。
再次完整执行全链仍为 exit 1，七份关键报告 SHA 全等、无新增重复归档，门禁
继续失败；日志为 `post-regression-store-strict-idempotence-01.log`。11 份本轮
Python 源已通过语法解析，18 份补例/辅助源的无 skip/xfail 检查保持通过。

所有运行启动/结束 source aggregate 相等，未生成逐拍 JSON、波形或完整源码副本。
源码摘要不表示当前工作区与所有历史源集合永远相等；无 Git 提交/推送声明。
派生矩阵/摘要/失败报告的旧版本按原字节 SHA 保存在 `audit-history/`。

整体目标仍须处理 Wrapper 覆盖丢失根因、其他可达 toggle/branch 情形、恢复、
异常/总线和全部 DUT/真实父级的剩余范围；本轮没有关闭目标或暂停后续工作。
