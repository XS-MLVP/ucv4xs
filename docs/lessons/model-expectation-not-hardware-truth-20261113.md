# 把参考模型期望当成硬件事实（LSQ Forward，#839/#840，2026-11-13）

## 问题

在 `public-e716c7658` 上做 LSQ 待回归定向时，我报告：

- `#839 FWD-RANGE-001`：**失败**，结论写成「上游 `43fe084b3` 修过头，把本应前递的字节也裁掉了」；
- `#840 FWD-ALIAS-001`：**失败**，结论写成「`302c0fe19` 的 PA/VA 解耦只修了一部分，跨 16B 别名仍漏 PA 命中」。

两个结论都是错的。

## 错误假设

1. **FAIL 等于 RTL 错。** 用例期望来自 `testbenches/forward/model.py`；FAIL 只说明
   `RTL ≠ 模型`，不说明哪一侧错。我没有先确定 oracle 归属。
2. **把断言元组读反。** `ForwardEnv.compare()` 抛的是
   `(..., name, actual[name], value)`，最后一位才是模型期望。我把 #840 的
   `actual=1, expected=0` 读成「期望 1、实际 0」，方向正好相反，由此编出
   「解耦只修一部分」的机制。
3. **先有结论再找解释。** 我在同一轮里刚强调过「`43fe084b3` 只在新 HEAD」，形成
   「新 HEAD 应当修好了」的预期，见到 FAIL 就去维护预期，而不是质疑它。

## 修正依据

用与 RTL、参考模型都无关的第三方判据：**物理字节交集**。

- store 的 PA 由硬件定义 `Cat(paddrHigh, vaddr(11,0))` 给出
  （`NewStoreQueue.scala:116-118`），`byteMask` 以 store 起点为 0 位
  （`:117`、`:2013-2017`），宽度由 `1 << size` 给出（双方共用 `byte_count`）。
- 只看测试输入（逐拍引脚采样）即可算出「哪些 load 字节有物理生产者、最年轻的是谁」，
  不需要读 DUT 内部选择信号或参考模型。

判定规则来自 [反向前递合同](../spec/design/contracts/forward-module.md)：
安全前递必须字节来源正确；任何一个阻塞标志有效时，旧数据不算被消费。

结果：

| 单 | 场景 | 物理交集 | 模型期望 | RTL 实际 | 谁错 |
|---|---|---|---|---|---|
| #839 word0 | 8B store @PA `0xABC00C`，16B load @`0xABC000` | `0xf000` | `0xf00f` | `0xf000` | 模型 |
| #839 word1 | 同上，16B load @`0xABC010` | `0x000f` | `0xf00f` | `0x000f` | 模型 |
| #840 | 年轻 8B cross16 @`0xABC00C` vs 老 4B @`0xABC010` | 最年轻为 slot1 | `matchInvalid=0` | `matchInvalid=1` | 模型 |

两处模型缺陷都能在代码里定位：

1. `forward/model.py` 的 `relative = (byte - store.vaddr % 16) % 16` 对 16 取模，
   把跨 16B store 的**另一半折回本 word**——正是 #6718 在 RTL 里修掉的环形折回。
2. `select()` 的 `same/following` 直接把 VA 页号编进 16B 坐标匹配，PA 别名因此
   同时掉出 `potential` 与 `virtual`；而同一模型的 `check_physical_safety()`
   按 PA 算生产者，两套判据自相矛盾。

## 修正

`suites/memblock/lsq/testbenches/forward/model.py`：

- 16B 坐标匹配改为**页内**（`(vaddr % 4096) // 16`），VA tag 只门控 `virtual`，
  与 RTL `s1Same16BMatchVec` / `s1VaddrMatchVec` 的分工一致；
- `forwardMask/forwardData` 改为按**绝对地址**求 store 内偏移
  （`load_word_base + byte - store.vaddr`），不再 `% 16` 折回。

只改测试侧期望，未改 RTL、未改断言域、未删除用例。

## 检查位置

- `suites/memblock/lsq/testbenches/forward/model.py`（`select`、`expected`）
- 复跑：`.venv/bin/ucv run lsq --dut forward_module` → **201 PASS / 6 FAIL**
  （修正前 19 FAIL）。

## 剩余限制

1. 修正后仍 FAIL 的 6 项是**另一个根因**，不是本次修正的回退：
   `test_multi_match_partial_forward_mask_must_block[0/1/2]` 与
   `test_partial_store_coverage_must_block_or_forward_every_produced_byte[0/1/2]`。
   该场景多候选、所选 store 只写低 8B，RTL 按跨度判「完整覆盖」而不按真实 mask，
   属已登记 `LSQ-UPSTREAM-6229`（#6229/#6312），保留为真实 FAIL。
2. 本修正只覆盖 `forward_module` 的 207 项。其他目录的 FAIL 未逐个归因。
3. 历史记录里 `FWD-RANGE-001` 的「28 个失败节点」、`FWD-ALIAS-001` 的「12 个节点」
   在登记时用的是同一个带缺陷的模型，**可能含同源假阳性**。本次未逐 nodeid 复核，
   不能据此改写那些数字，只能标注该风险。
4. 合同 §3.3「单候选可部分前递」仍未被设计 owner 签核；本次没有改动该边界。
