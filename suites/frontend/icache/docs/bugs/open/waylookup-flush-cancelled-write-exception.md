```ucv-bug
{
  "id": "WAYLOOKUP-020",
  "title": "WayLookup 在 flush 同拍取消写时仍锁存异常并阻塞后续写",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "tests/waylookup/testcase/test_flush.py::test_flush_in_the_write_cycle_discards_the_entry_and_its_exception",
        "docs/spec/verification/reports/verification-report.md"
      ],
      "note": "旧基线已登记 strict XFAIL；ICacheWayLookup.sv 与后续基线字节相同。"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "tests/waylookup/testcase/test_flush.py::test_flush_in_the_write_cycle_discards_the_entry_and_its_exception",
        "docs/spec/verification/reports/baseline-update-a0c2a26cb.md"
      ],
      "note": "2026-11-08 收口保持 strict XFAIL；两种 seed 判定一致，RTL 未修复。"
    }
  ]
}
```

# WAYLOOKUP-020：flush 同拍取消的写仍锁存异常备忘

状态：**真实 RTL 缺陷，仍未修复**。保留 strict XFAIL，不转正；本轮只登记复现、影响
和证据，修复决定交回用户。未修改 RTL、未向上游提交 issue/PR/patch。

适用边界：ICache / DefaultConfig / `public-a0c2a26cb`
（`a0c2a26cbe3c862175174bad03a1a23c406315ed`）。DUT 的
`ICacheWayLookup.sv` 与旧基线 `893e1580b` 字节相同，sha256
`6433fed2ff7d5defc2b4977469334ffa858c480df5c6e2ba4773dbb3f9b08ce9`，所以这
不是新基线引入的回归。

## 最小复现

用例：`tests/waylookup/testcase/test_flush.py::test_flush_in_the_write_cycle_discards_the_entry_and_its_exception`
（功能点 `ICACHE-WAYLOOKUP-020`，strict XFAIL）。

```python
payload = entry(0x7201, exception=True)
await agent.write_with_flush(payload, ftq_value=4)

agent.expect_empty()                                  # 队列确实被清空
assert agent.rtl_write_ready() == 1                   # 失败点：实际为 0
```

`write_with_flush` 在同一个采样沿同时给出 `io_write_0.valid`、带 ITLB 异常的
payload 和 `io_flush`。队列的读写指针被 flush 归零，`status.empty` 也为 1，但
`write.ready` 停在 0，后续写全部被拒，直到再发一次完整 `flush` 才恢复。

## 根因（生成 RTL，行号为 `public-a0c2a26cb` 的 ICacheWayLookup.sv）

```verilog
1403  wire io_write_0_ready_0 = (|(_numFreeEntries_T[5:1])) & ~exceptionEntry_valid;
1417  wire _GEN_17 = io_write_0_ready_0 & io_write_0_valid;      // write_0_fire
4193  exceptionEntry_valid <=
4194    _GEN_83                                                   // 没与 io_flush 相与
4195    | ~(io_flush | bpuS3FlushValid & ...) & exceptionEntry_valid;
```

`_GEN_83` 是"本拍有写且带异常"的置位项，它没有被 `io_flush` 门控；同拍的 flush
只清理 `readPtr`/`writePtr`/`tailFtqIdx`。于是被取消的写仍把
`exceptionEntry_valid` 置 1，而 `write.ready` 又被这个标志压住
（1403），形成"空队列拒绝写"的停滞。

对比正常路径：异常条目被读走之后，`exceptionEntry_valid` 由读指针比较清除，写口
恢复；只有"flush 与带异常写同拍"这一种组合会留下孤儿标志。

## 影响评估

- **可观测后果**：`write.ready` 停摆（队列空但拒写），生产者在收到下一次完整
  `flush` 前无法入队。不是错误异常载荷泄漏：stale `exceptionPtr` 指向的槽会在被
  读之前被新写覆盖，所以后续条目的载荷不会被污染。
- **芯片级可达性**：整块 ICache 中不可达。`ICachePrefetchPipe` 的
  `io_wayLookupWrite_*_valid` 含 `~s1_flush`，而 `s1_flush` 包含
  `io_flush | <stage-3 条件>`；redirect flush 的同拍预取管道不会给出写有效。
  因此这是子模块接口合同层面的潜在缺陷，不影响当前 ICache 集成。
- **验证侧风险**：如果将来预取管道改掉 `~s1_flush` 门控，或 WayLookup 被别的
  生产者复用，该停滞会直接暴露为前端取指停顿；因此不能因为"集成不可达"就删掉
  该用例。

## 证据

- 参考模型按规范修正：被 flush / stage-3 drop 取消的写不得产生任何副作用（包括
  异常备忘）。模型不再照抄 RTL 的 `_GEN_83` 行为。
- 用例先断言 `expect_empty()` 与 `rtl_write_ready()`，再用"后续写入必须可入队"
  和"新条目不得继承旧异常"两条断言固定两个可观测后果。
- 运行：`results/ucv-icache-a0c2a26cb-final4-seed1-20261107` 与
  `...-final4-seed2-20261107`（strict XFAIL，两种 seed 判定一致）。
- 历史分析见 [错误复核](../../spec/verification/error-review.md) §1.3 与
  [整块覆盖闭环](../../spec/verification/coverage/icache-coverage-closure.md)。
