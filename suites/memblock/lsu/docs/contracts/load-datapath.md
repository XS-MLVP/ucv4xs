# `LoadUnitDataPath`：load S2/S3 数据选择、移位与扩展

## 1. 职责

把 S1 的元数据延迟到 S2，在 S2 用五个来源按字节合并出 128 位数据，再延迟到 S3；
S3 做**逻辑右移**（按 bank offset）与 head/tail 合并，最后按 `fuOpType` 做
符号/零扩展或 NaN boxing，输出 `s3ShiftData` 与 `s3ShiftAndExtData`。

## 2. 流水与寄存器

```
S1→S2:  s2Valid <= s1Meta.valid;  s2Meta_* <= s1Meta_* (仅当 valid)
        isUnalignTail <= s2Meta.isUnalignHead & s2Valid
        unalignHeadBankOffset <= s2Meta.bankOffset (当 isUnalignHead & s2Valid)
S2→S3:  s3Valid <= s2Valid
        当 s2Valid: s3Data <= 合并结果；s3IsUnalignTail <= isUnalignTail;
                    s3RdataTypeOH[0..8] <= fuOpType 解码；
                    s3RdataSelByOffset[0..15] <= bankOffset 比较；
                    s3TailRdataSelByHeadOffset[0..14] <= unalignHeadBankOffset 比较
S3→S4:  当 s3Valid: s4ShiftHead <= s3ShiftHead
```

`reset` 只清 `s2Valid`/`isUnalignTail`/`s3Valid`；其余寄存器上电值随机（生成 RTL 的
`initial` 块），因此 payload 只在对应 valid 为 1 时比较。

## 3. 字节合并优先级（每字节独立）

| 顺序 | 条件 | 数据 |
|---:|---|---|
| 1 | `sqForward.forwardMask[j]` | `sqForward.forwardData[j]` |
| 2 | `uncacheForward.forwardMask[j] && isNCReplay` | `uncacheForward.forwardData[j]` |
| 3 | `sbufferForward.forwardMask[j]` | `sbufferForward.forwardData[j]` |
| 4 | `mshrForward.forwardMask[j]` | `mshrForward.forwardData[j]` |
| 5 | `tldForward.valid` | `tldForward.forwardData[j]` |
| 6 | 否则 | `rawData[j]` |

`rawData = (isNCReplay || isMMIOReplay) ? uncacheBypass.data : dcacheResp.data`。

**注意字节序**：字节 `j` 对应 `[8j+7:8j]`，即 `forwardData_15` 是最高字节。

## 4. 移位与 head/tail 合并

```
s3ShiftHead = s3Data >> (8 * bankOffset)          // 逻辑右移，高位补零
s4ShiftHead = Reg(s3ShiftHead)                     // 仅 s3Valid 时更新
s3ShiftData = s3IsUnalignTail
                ? (s4ShiftHead | (s3Data << (8 * (16 - unalignHeadBankOffset))))
                : s3ShiftHead
```

`unalignHeadBankOffset = 0` 时没有 tail 选择位，结果就是 `s4ShiftHead`（只用 head）。
`offset` 的取值范围 1..15 由 `s3TailRdataSelByHeadOffset` 的 one-hot 编码，
移位量隐含在该 one-hot 里。

## 5. 扩展（`s3ShiftAndExtData` 的 64 位低半部）

| `fuOpType` | 类型 | 扩展 |
|---|---|---|
| 0x10 / 0x50 | LBU / HLV.BU | 零扩展到 8 位 |
| 0x12 / 0x52 / 0x72 | LHU / HLV.HU | 零扩展到 16 位 |
| 0x14 / 0x54 / 0x74 | LWU / HLV.WU | 零扩展到 32 位 |
| 0x06 / 0x46 | LD | 64 位原值 |
| 0x00 / 0x40 | LB | 符号扩展到 8→64 |
| 0x02 / 0x42 | LH | 符号扩展到 16→64 |
| 0x04 / 0x44 | LW | 符号扩展到 32→64 |
| 0x02 且 `fpWen` | LH_FP | NaN box：高 48 位全 1，低 16 位为数据 |
| 0x04 且 `fpWen` | LW_FP | NaN box：高 32 位全 1，低 32 位为数据 |
| 其它 | — | 0 |

高 64 位恒为 0。

## 6. 输入合法域

- `s1Meta`：S1 的元数据；`bankOffset` 为 4 位，合法范围 0..15。
- 五路 forward 响应：`forwardMask` 每字节一位；`forwardData_j` 8 位。
  `uncacheForward` 的 mask 还要求 `isNCReplay`（NC replay 才用外部数据）。
- `tldForward.valid` 是唯一没有 mask 的整拍来源。
- `uncacheBypass`/`dcacheResp` 是 128 位原始数据。
- 无 `ready`；本 DUT 是固定延迟流水，`s3ShiftData` 始终驱动但只在 `s3Valid` 时有意义。

## 7. 语义功能点

| ID | 语义 |
|---|---|
| LDP-PIPE | 元数据寄存、空拍保持、valid 链（s1→s2→s3 各一拍） |
| LDP-MERGE | 六优先级字节合并，含 NC mask 条件与 bypass/dcache 二选一 |
| LDP-SHIFT | 16 个 bank offset 的逻辑右移（非循环） |
| LDP-TAIL | head 与左移后的 tail 按位 OR；offset=0 只用 head |
| LDP-EXT | 9 种 one-hot 扩展，含符号位复制与两种 NaN box |
| LDP-UNKNOWN | 未编码的 `fuOpType` 输出 0 |

## 8. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala`（S2 数据选择与 S3 shift/ext 的源逻辑）
- `soc-split/rtl/LoadUnitDataPath.sv`（本 DUT 的全部 assign 与两段 always）
