# LSQ阶段统一回归03：849例/31个独立DUT

## 结论与准确范围

**NOT_PASS：830通过、19失败。** 本运行覆盖启动时已经实现的全部11个测试家族、31个独立DUT，新增真实Replay父块与EnterSbufferQueue/UnalignQueue叶子。不是完整LSQ/真实LoadQueue/StoreQueue组合验收；ForwardModule功能UT在新目录/本地fixture独立开发，明确不在本849例内。

结果目录 `results/lsq-progress-regression-03/`；运行命令逐一列出11个家族，无-k、deselect、skip或xfail。旧651例和195例门禁及快照未覆盖；新门禁为 `tools/audit_progress_run_v3.py`。

| 家族 | 用例数 | 通过/失败 |
|---|---:|---:|
| FreeList四变体 | 52 | 52/0 |
| CAM三变体 | 24 | 24/0 |
| AgeDetector | 11 | 11/0 |
| VirtualLoadQueue | 22 | 22/0 |
| LoadQueueRAR | 54 | 47/7 |
| LoadQueueRAW | 32 | 32/0 |
| 全16个UncacheEntry | 384 | 384/0 |
| LoadQueueUncache真实父块 | 72 | 64/8 |
| LoadQueueReplay真实父块 | 131 | 127/4 |
| EnterSbufferQueue | 26 | 26/0 |
| UnalignQueue | 41 | 41/0 |
| **总计** | **849** | **830/19** |

19个普通失败完整nodeid与方向/数据签名经审核：RAR-REL-001 7例、LQU-SID-001合法SID重用7例、LQU-MMIO-IF-001仅接口边界1例、LRQ-STRICT-001 4例。known-issues只标识失败，未被测试/参考读取或当作豁免。

## 覆盖与证据审计

- xreactor manifest committed，coverage_complete/cleanup_complete，31个原生build、62个完整功能组；所有artifact/build及148份冻结源文件SHA核验通过。
- `source-consistency.json`确认这148份启动文件在结束时全部一致。ForwardModule新文件和本地fixture不影响旧回归，未冒充其覆盖。
- 只有RAR的3项、LQU的2项、Replay的2项语义未checked；所有reached完整，其余28个独立DUT的适用checked完整。
- 原始本体/真实子块DA除LQU六条guarded default外全部命中，包括Replay25806/25806、EnterSbuffer78/78和Unalign44/44。
- LQU保持原始1120/1126、真实闭包3169/3175，不改分母。`audit_lqu_static.py`对六条固定源哈希的互斥guard默认值重新证明，结论仅此六条，不是全DUT形式化证明。
- 各模块原来的独立公开输入历史审计保留；本统一门禁审计范围/签名/覆盖/哈希，不宣称重新实现所有模块的第二套语义参考。

重现审计：

```sh
python3 -B tools/coverage_audit.py lsq-progress-regression-03
python3 -B tools/audit_lqu_static.py lsq-progress-regression-03
python3 -B tools/audit_progress_run_v3.py lsq-progress-regression-03
```

新增ForwardModule初批已另外发现3lane跨16B别名旧值失败FWD-ALIAS-001，见其阶段报告；它没有被追溯加入本849例冻结结果。继续Forward完整62种语义及后续业务与组合层，整体目标保持活动，不能以本回归范围替代全部LSQ交付。
