# DuplicatedTagArray 功能点

DUT：`DuplicatedTagArray`（`soc-split/rtl/DuplicatedTagArray.sv`），层次：DCache 标签叶块。
它包含 4 份完全相同的 `TagArray`（读端口 0..3），每份 2 个 `TagSRAMBank`、每 bank 2 way，
共 256 set × 4 way；单写端口带 4-bit way 掩码；写数据 36-bit tag + 7-bit SECDED。

功能点用微架构语义表述，测试只使用公开端口。

## DTA-FP-001 复位扫描清零

复位释放后，硬件不是一次性异步清空，而是用 256 个时钟沿按 set 递增扫描，把每个 set 的
全部 4 个 way 写成零码字（tag=0、ECC=0）。扫描期间 SRAM 的单端口被写占用，四个读端口
都不接收请求；扫描结束后读端口恢复接收，任何 set 读出的都是零码字。

- 情形：扫描进行中、扫描完成边界、扫描后全 256 set 抽查。

## DTA-FP-002 四份标签副本的读一致性

同一 set 的 4-way 码字被复制保存在 4 份 `TagArray` 中。任一读端口读某 set 时，都必须
返回与其它端口完全相同的 4 个 43-bit 码字；读操作不修改任何副本。

- 情形：4 个端口各自读同一 set；4 个端口同拍读同一 set；同拍读不同 set。

## DTA-FP-003 set 独立寻址

256 个 set 是独立存储行。写某个 set 只改变该行的 way；读某 set 只返回该行。set 0 与
set 255 是边界，必须与中间 set 有相同行为。

- 情形：相邻 set、跨 64-set 区间、边界 set 0/255。

## DTA-FP-004 way 掩码写

写请求的 `way_en[3:0]` 是字节级 way 选择：只有置位的 way 更新 tag/ECC，其它 way 保留
原码字。单 way、任意两 way、任意三 way、全 way 都必须成立；way_en=0 的写不改变任何
way（但仍占用写端口一拍）。

- 情形：单 way ×4、双 way 组合、三 way 组合、全 way、零掩码。

## DTA-FP-005 单端口读写互斥与读延迟

标签 SRAM 是单端口：写有效（或复位扫描）时 `io_read_3_ready` 为低，读请求不生效；
无写时 ready 为高，读请求在下一个时钟沿后返回目标 set 的 4-way 码字。写与读同拍时
读被拒绝，不能让读看到写了一半的行。

- 情形：只读、只写、读写同拍（同 set / 不同 set）、连续背靠背读。

## DTA-FP-006 写后读可见性

一次写提交后，从任意读端口都能读到新码字；连续写同一 set 的不同 way 后，每个 way
保留最近一次写入的值；未选中的 way 不被邻近 way 的写污染。

## DTA-FP-007 SECDED 码字生成

写端口只给 36-bit tag，RTL 用固定线性 XOR 网络生成 7-bit 校验，与 tag 拼成 43-bit
码字存入 SRAM。功能要求：

- tag 原样出现在码字低 36 位；
- 相同 tag 的码字相同，与 set/way/端口无关；
- 编码是线性的：`ecc(a ^ b) = ecc(a) ^ ecc(b)`；
- tag=0 的码字为 0；
- 任意单 bit tag 差异都产生非零校验差异（可检测单 bit 错误）。

参考编码器直接由 `DuplicatedTagArray.sv` 的 XOR 常量实现（见 `model.py`），不是从 DUT
输出学习。

## DTA-FP-008 MBIST/DFT 旁路访问

当 `boreChildrenBd_bore_req` 有效且 `bore_array` 选中 0x20..0x27 之一时，DFT 控制口在
下一拍把地址/数据/写掩码送到对应的 `TagSRAMBank`，`bore_ack` 在请求后一拍有效：

- DFT 写按 2-bit 字节掩码直接写入原始 86-bit SRAM 行（绕过 SECDED 编码）；
- DFT 读在请求后第二拍返回该行的原始 86-bit 数据，未选中的 bank 不参与输出；
- DFT 写后的原始行对功能读端口可见（低 43 位属于低 way，高 43 位属于高 way）；
- 8 个 bank（4 份 TagArray × 2 个 SRAM bank）都可独立选中。

## 覆盖组（toffee CoverGroupDef）

- `dta.reset`：扫描中 / 扫描后。
- `dta.read`：读端口 0..3 × way 0..3；set 区间；端口×way cross。
- `dta.write`：way 掩码类别（单/双/三/全/零）、tag 形态（零/单 bit/多 bit/稠密）、
  set 区间。
- `dta.conflict`：只读、只写、读被写阻塞、写后读。
- `dta.mbist`：8 个 array 槽位 × 读写操作；载荷形态（零/交替/稠密）。
