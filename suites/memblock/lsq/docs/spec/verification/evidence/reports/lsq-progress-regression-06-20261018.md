# LSQ阶段回归06：共享Deq合法域纠正后的1312例

结论：**1202 PASS / 110 FAIL，NOT_PASS**。这是36个独立原生DUT的阶段回归，
包括真实StoreQueue，但不包括正在开发的LoadQueue或尚未实施的LsqWrapper；
不构成完整LSQ验收。所有53份原始RTL哈希核验，未改目标RTL/Chisel。

## 范围与冻结证据

运行：`results/lsq-progress-regression-06/`，完整16个测试目录、1312个唯一case，
无`-k`、deselect、skip/xfail、ERROR或测试读取问题清单。36个build、72功能组；
全部artifact/build SHA、256份启动文件及结束源码哈希一致。

```sh
python3 -B tools/run.py --name lsq-progress-regression-06 --workers 4 -- \
  tests/age tests/cam tests/freelist tests/rar tests/raw tests/vlq \
  tests/uncache_entry tests/load_uncache tests/replay tests/enter_sbuffer \
  tests/unalign tests/forward tests/vsq tests/deq tests/psq tests/store_queue --tb=short
python3 -B tools/capture_end_sources.py lsq-progress-regression-06
python3 -B tools/coverage_audit.py lsq-progress-regression-06
python3 -B tools/audit_lqu_static.py lsq-progress-regression-06
python3 -B tools/audit_progress_run_v5.py lsq-progress-regression-06
python3 -B tools/audit_progress_run_v6.py lsq-progress-regression-06
python3 -B tools/audit_deq_lifecycle_v2.py lsq-progress-regression-06
python3 -B tools/audit_psq_lifecycle_v2.py lsq-progress-regression-06
```

`evidence-check-v6.json`为纠正分类后的最终阶段证据。v5门禁把6个PSQ/SQ完成
顺序断言错误标为WB，因为pytest的附加输出字典里也出现`exceptionVec`；v6优先
核对主断言，保留旧v5文件，**不改变任何PASS/FAIL、覆盖或领域判定**。

| 目录 | 总例 | PASS | FAIL |
|---|---:|---:|---:|
| age / cam / freelist | 11 / 24 / 52 | 全部 | 0 |
| VLQ / RAW / UncacheEntry全16 ID | 22 / 32 / 384 | 全部 | 0 |
| EnterSbufferQueue / UnalignQueue | 26 / 41 | 全部 | 0 |
| RAR | 54 | 47 | 7 |
| LoadQueueUncache | 72 | 64 | 8 |
| Replay | 131 | 127 | 4 |
| Forward | 184 | 165 | 19 |
| VSQ | 42 | 40 | 2 |
| Deq | 92 | 67 | 25 |
| PSQ | 66 | 45 | 21 |
| StoreQueue | 79 | 55 | 24 |

110失败例的首个违反合同分类：RAR7、SID复用7、Replay strict4、MMIO接口1、
Forward SQID11/alias9/range22、VSQ接口2、WB15、split wline13、
完成顺序14、zero所有权5。105例处于模块producer边界，5例仅接口边界。
这些是失败case数，不是110个独立缺陷或110个已证实架构错误。

## 回归05的参考问题不抹除

`lsq-progress-regression-05`真实结果为1198 PASS/114 FAIL，254份启动结束文件
一致；v5门禁因Deq容量/重叠两个reached缺失而正确拒绝。其新增11个Deq差异首先
来自身份前缀参考的post-edge旧指针、及split后inactive非最优吞吐误解，不是11个
RTL反例。修正只作用于参考的相位合同：独立leaf的post-edge组合控制尚未切换，
瞬态credit波形不能当作已退休身份；真正pre-edge及父级advance仍严格使用已完成
身份的年龄前缀，绝不退回无身份PopCount作释放oracle。保持扩大后的真实父级
许可刺激域，不恢复旧`read==head`的特殊committed门控。

修正后Deq的11例中容量、split/inactive等通过；原完整域随机继续执行后又遇到
zero/完成顺序/wline，故总体仅净少4失败，不能机械地声称114−11=103。
独立Deq轮`deq-domain-corrected-01`与回归06的92例均67 PASS/25 FAIL。

## 新版独立生命周期审计

- `lifecycle-audit-v2.json`（Deq）：6246条连续记录，2452 UID = 1990完成 +
  4 reset中止 + 458失败保留，4个reset旧槽均有同槽新UID实际完成；1796次
  Sbuffer fire、268 WB、135 NC确认。25例分别WB9、wline7、zero2、完成顺序7，
  均有公开字节/实际总线完成/未消费旧owner的独立证明；坏终止边沿不记为正常完成。
- `psq-lifecycle-audit-v2.json`：7489条连续记录；原63例**全部原始输入、全部
  pre/post输出与tick逐bit相同**于已独立UID/字节审计的`psq-expanded-05`，不是
  仅沿用旧PASS状态。新增3例分别重新证明年轻NC/IO完成、旧Sbuffer消费0次、
  head0→1且旧请求仍valid。旧63例审计与1429 UID等原始计数保持不改。
- StoreQueue仍为相同79例55/24；其此前7114记录、1556 flow及取消/reset同槽
  复用审计保留。本轮统一门禁本身不冒充为所有模块重新建立第二套参考。

## 覆盖及仍未完成范围

36个DUT本体及真实闭包除LQU六条guarded default外均全DA命中；LQU仍保留
1120/1126和闭包3169/3175原分母，重新做窄结构证明，不删除六行。
Deq43/47、PSQ39/46、StoreQueue43/51 checked，未通过功能均保持严格失败；
完整缺口列表见`line-audit.json`及`evidence-check-v6.json`。

后续必须完成真实LoadQueue的内部head/full/Uncache wake反馈与共享S3/恢复
组合闭环，再继续LsqWrapper整体。不能用本回归、叶子通过或行满关闭整体目标。
