# Naive RevB 采购与料号审查

核对日期：2026-10-29。范围：本目录 MainBoard / ExtendBoard 原生 KiCad 工程、原 Altium 嵌入模型及厂家资料。本文记录采购闭环条件，不把候选料号自动视为已获准替代料。

**当前结论：工程原型的电路改进及关键接口选型已经形成，仍需最终制造文件、装配和实测验收，不能据此声称可直接投产。** USB1 已选 GCT USB4105-GF-A、J1 已选 Molex 104031-0811、A1 已选 CrossAir CA-C03，最终主板原理图和受控封装字段已经同步。MPU-6050 已停产；ESP32-PICO 系列为 NRND。厂家生命周期与经销商是否暂有库存是两个不同事实。

## 1. 当前数据源与缺项

`tools/hardware/revise_schematic.py` 的 `BASE_PARTS` 是从原设计提取的基准数据。实际 RevB 应审查 **BASE_PARTS + revb_main_manifest.json 的覆盖结果 + 原理图实例字段**，不能直接把基准 Comment 当成完整采购型号。

初次审查 MainBoard.kicad_sch 的 58 个实件时，有 21 个实例没有 `MPN`。维护者审核接受的 18 个明确型号（15 个通用 R/C 与 U1/U3/U5）已写入 `revb_main_manifest.json.existing_mpn`；USB1、J1、A1 的最终型号也已实际同步。当前主板 **58 件**、屏板 **11 件**，合计 **69 个装配位号 / 39 个完整订货号**，均无缺失 MPN。

[BOM.json](BOM.json) 从两板原生 KiCad 网表逐位号导出，保留原理图 SHA-256、数量、MPN、厂家、受控封装和采购验收条件。`tools/hardware/export_bom.py` 可在 KiCad 10 环境重生该数据。数量为每台一套两板的装配用量，不包含 PCB 制造、排线、USB 线、SD 卡、光学件、外壳或焊接工具，也未加损耗备料。

最终六层主板冻结后，已从两板实际原理图及 PCB 重新导出：`BOM.csv` 为 69 个装配实例，`BOM-grouped.csv` 和 `BOM.xlsx` 的采购页均按完整 MPN 合并为 39 项，合计 69 件。`100nF / 0.1uF`、`10K / 10k` 等原文写法不再拆成不同采购项。C16 已同步为 100pF / GRM1555C1H101JA01D。

本次导出的工程来源 SHA-256 如下，与 `BOM.json` 的 `source_schematics` / `source_pcbs` 一致：

| 工程文件 | SHA-256 |
|---|---|
| MainBoard 原理图 | `ba9721f91173625fbde87724af5227dc38321b393ed119dc0b00860e52d91eca` |
| MainBoard 六层 PCB | `9027e617313d7e87af202d14787fecd7b6d484bee7a0b72a699a266f329cab9c` |
| ExtendBoard 原理图 | `39d4f003f0dabb8bb6c76697fec7b85b22cb5fad41692d653c4dc153018b5eab` |
| ExtendBoard PCB | `b86d3b57e9d1ea0eee3e62e688c22a6c4507c0328ddc385a6607309e95d6514f` |

JSON / 逐实例 CSV 的安装面、坐标及角度读取最终 PCB：R16 为 B 面 `(144.3,112.4)/180°`，C17 为 F 面 `(155.88,111.02)/90°`，C16 为 B 面 `(159.3,115.1)/180°`。这些是原生 CAD 工程坐标，不能直接当作已获装配厂确认的贴片机程序。

已补全的原缺项为：R1/R3/R4/R5/R6/R7/R8/R9/R10、C5/C6/C8/C9/C10/C11、U1/U3/U5。该字典已交主板维护者同步 PCB `MPN` 字段；型号不改变原电气网络或这些器件的封装。

ExtendBoard 的 11 个实例已有 `MPN`，但这不等于屏幕尾排、FFC 长度/接触面以及壳体装配验证已经完成。P133H002 尾排注册仍须跟随最终机械修订。

下表经维护者审核后已写入 manifest / 原理图，采购时仍须逐批核验供应商、完整订货号、封装及来料标记。型号、封装或引脚发生变动时须重新跑原生 ERC / DRC / schematic parity。本文不替代最终导出的装配 BOM。

## 2. 关键芯片的生命周期与替代边界

| 位号 | 当前选用的订货号 | 核实结果 | 对采购 / 改板的影响 |
|---|---|---|---|
| Main U4 | ESP32-PICO-D4 | Espressif 系列数据手册 v1.5 将 D4、V3、V3-02 **全部标为 NRND**。NRND 不等于已经停产。 | 当前裸 SiP 的 PCB、RF、供电和固件继续依赖 D4。不能把改成 PICO-V3 当作长期供货问题已经解决；更换主控需重新设计和验证。 |
| Main U3 | MPU-6050 | TDK 官方产品页为 **Obsolete**。PCN-000614：通知日 2023-07-23，最后订购 2024-01-31，最后出货 2024-12-31。 | 复刻只能先落实来源可追溯的余货及来料检验；不能承诺持续量产。TDK 推荐 ICM-42670-P，并明确不保证互换，不能直接替换当前 QFN24 / 驱动。 |
| Main U1 | CP2102-GMR（卷带，经典 CP2102） | Silicon Labs 当前页面预计 CP2102 持续完整生产至少到 **2029 年 3 月**，日期适用于优选修订，不是无限期承诺。 | 保持经典 CP2102、QFN28 5×5 mm。CP2102N 不是只改 BOM 字符串的替换，必须核引脚、电源、复位和驱动。 |
| Main U5 | BH1750FVI-TR | 原 ROHM 型号及 WSOF6I 可由厂家数据手册确认。此次未取得 ROHM 当前单品生命周期页面；授权分销商 Mouser / DigiKey 均显示 NRND，这是供应链警示，不能冒充原厂当前确认。 | 可按原型号核库存与追溯；新批量计划应向 ROHM / 授权渠道确认供货。更换 ALS 型号需核封装、I²C 命令、量程换算及上电时序。 |
| Main U2 | TPS62162DSGR | TI 产品页为 Active，固定 3.3 V、DSG 8-pin WSON。 | 保持当前固定输出版本。相近名字或新一代 Buck 不能直接替换；须检查 FB / VOS 接法及电感、有效电容、布局。 |
| Main U6 | TPS22918DBVR | TI 产品页为 Active，DBV / SOT23-6。 | 是可调上升时间负载开关；**不是限流 eFuse**。采购不得用“2 A”推断它具有 2 A 过流关断。 |
| Main U7 | TPD4E05U06DQAR | TI 产品页为 Active，DQA / USON10。 | 保持精确封装后缀；NC 焊盘不是内部直通连接。 |
| Main U8 | SN74AHCT1G125DCKR | TI 产品页为 Active，DCK / SC70-5，4.5–5.5 V 供电、TTL 输入。 | 保留 AHCT，不以 AHC / LVC 等近名器件替代，以免失去 3.3 V 控制 5 V RGB 的电平保证。 |
| Main D2 | TPD1E10B06DPYR | TI 产品页为 Active，DPY / X1SON 1.0×0.6 mm。 | 同系列 DYA / SOD 封装不能混用。ESD TVS 不能视为持续过压保护器。 |

以上状态以核对日为准；“Active”也不表示已替项目预留库存。本文不引用随时变化的单价或现货数量作为设计放行依据。

原厂依据：

- [Espressif ESP32-PICO 系列数据手册 v1.5](https://documentation.espressif.com/esp32-pico_series_datasheet_en.html)，封面与系列比较表。
- [TDK MPU-6050 产品状态](https://product.tdk.com/en/search/sensor/mortion-inertial/imu/info?part_no=MPU-6050)、[TDK PCN-000614 停产通知](https://invensense.tdk.com/wp-content/uploads/2023/09/PCN-000614.pdf)。
- [Silicon Labs 经典 CP2102 产品页](https://www.silabs.com/interface/usb-bridges/classic/device.cp2102)、[CP2102/9 数据手册](https://www.silabs.com/documents/public/data-sheets/CP2102-9.pdf)。
- [ROHM BH1750FVI 原厂数据手册镜像](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/6165/bh1750fvi-e.pdf)；当前分销状态参见 [Mouser](https://www.mouser.ca/en/ProductDetail/ROHM-Semiconductor/BH1750FVI-TR?qs=phc6PQ%252BTPUNy88lRCs6mVA%3D%3D)、[DigiKey](https://www.digikey.ca/en/products/detail/rohm-semiconductor/BH1750FVI-TR/2041441)。后两项只用于描述渠道所标状态。
- TI：[TPS62162](https://www.ti.com/product/TPS62162)、[TPS22918](https://www.ti.com/product/TPS22918)、[TPD4E05U06](https://www.ti.com/product/TPD4E05U06)、[SN74AHCT1G125](https://www.ti.com/product/SN74AHCT1G125)、[TPD1E10B06](https://www.ti.com/product/TPD1E10B06)。

## 3. 已审核选用并回填的通用 R / C

以下料号已审核选用并写入工程，保持原数值、0402 外形及用途。须逐批核验完整后缀，不得把本表当作允许任意同值代料。

| 位号 | 数量 | 当前数值 | 已选制造商料号 | 规格 / 选择理由 |
|---|---:|---|---|---|
| R1、R6、R7、R8、R9、R10 | 6 | 10 kΩ | YAGEO RC0402FR-0710KL | 0402 / 1005，1%，0.063 W；用于上拉，不是电源跳线。 |
| R4、R5 | 2 | 12 kΩ | YAGEO RC0402FR-0712KL | 0402，1%，0.063 W，保持双 NPN 自动下载基极限流值。 |
| R3 | 1 | 200 Ω | YAGEO RC0402FR-07200RL | 0402，1%，0.063 W，保持 UART 串联值。 |
| C5、C8、C10、C11 | 4 | 100 nF | Murata GRM155R71C104KA88D | 0402，16 V，X7R，±10%；与本版其它 100 nF 可共用采购项。C8 是 MPU REGOUT 电容，不能随意省略。 |
| C6 | 1 | 10 nF | Murata GRM155R71H103KA88D | 0402，50 V，X7R，±10%。 |
| C9 | 1 | 2.2 nF | Murata GRM1555C1H222JA01D | 0402，50 V，C0G，±5%；用于 MPU CPOUT，保持 2.2 nF。 |

厂家规格链接：[YAGEO 10 kΩ](https://www.yageogroup.com/component-documentation/download/specsheet/RC0402FR-0710KL)、[12 kΩ](https://www.yageogroup.com/component-documentation/download/specsheet/RC0402FR-0712KL)、[200 Ω](https://www.yageogroup.com/component-documentation/download/specsheet/RC0402FR-07200RL)；Murata [100 nF 产品页](https://www.murata.com/en-global/products/productdetail?partno=GRM155R71C104KA88%23)、[10 nF SimSurfing](https://ds.murata.com/simsurfing/mlcc.html?oripartnumbers=%5B%22GRM155R71H103KA88D%22%5D&partnumbers=%5B%22GRM155R71H103KA88%22%5D)、[2.2 nF SimSurfing](https://ds.murata.com/simsurfing/mlcc.html?oripartnumbers=%5B%22GRM1555C1H222JA01D%22%5D&partnumbers=%5B%22GRM1555C1H222JA01%22%5D)。

已锁定的特殊被动件不能与上述表格混用：R2 是指定额定电流的 0 Ω 跳线；C2/C3/C4/C13 的 22 µF 0805 需按直流偏压后的有效电容核对；C16 定时电容已改为 **100pF / C0G / 50V / ±5%，Murata GRM1555C1H101JA01D**。厂家 2026 年 10 月 EC 资料确认 0402 / 1005，外形 1.00±0.05 × 0.50±0.05 × 0.50±0.05 mm，最大本体高度仍为 0.55 mm，保留现有受控封装及装配包络。采购代料不应只比较标称容量和封装。

改小 C16 的目的是兼顾 CP2102 上电时序：Silicon Labs CP2102/9 Rev1.8 Table5 要求 VDD 到 2.7V 的时间不超过 1ms；TI TPS22918 RevC 的 1nF / 5V 输出上升典型值约 2.54ms。按 TI Eq.3，100pF 的 SR≈85µs/V，5V 输出 10–90% 上升时间估算约 **0.425ms**，不是最大值保证，且不等于已经测得 CP_VDD 的实际波形。约 13µF 有效 5V 负载的纯充电电流估计约 0.12–0.15A，负载启动和容差另计。首板须测 CP_VDD 到 2.7V 的时间、USB 枚举及热插拔入口电流。来源：[Murata 100pF 原厂 EC](https://ds.murata.com/simserve/characteristics?ReqType=TechPDF&partnumber=GRM1555C1H101JA01&techpdfname=technical_pdf_Capacitor01&lang=en)、[TI TPS22918](https://www.ti.com/lit/ds/symlink/tps22918.pdf)、[Silicon Labs CP2102/9](https://www.silabs.com/documents/public/data-sheets/CP2102-9.pdf)。

C20 经官方偏压曲线复核后，已改选 **GRM155R61A475MEAAD，4.7 µF / 10 V / X5R / 0402 / ±20%**，保留 CP2102 REGIN 本地 C23=100 nF。Murata 2026 年 10 月 EC 数据在 5 V 下约剩 1.88 µF、5.5 V 下约 1.7 µF，均为典型值，不保证全温、容差及老化下限；量产前须采样核验。原候选 GRM155R61C105KA12D 的 1 µF 0402 在 5 V 下典型仅约 0.35 µF，因此不能靠标称 1 µF 认定满足 REGIN 本地退耦目标。

C7、C15 仍采用 GRM155R61C105KA12D 的 1 µF / 16 V / X5R / 0402；C7 在 3.3 V 下典型有效电容约 0.55 µF，会影响 EN 实际 RC 延时；C15 在 5 V 下约 0.35 µF。它们的作用、允许范围和验证条件与 C20 不同，不能由“同一 nominal”推断用途可以互换。来源：[Murata C20 官方 EC](https://ds.murata.com/simserve/characteristics?ReqType=TechPDF&partnumber=GRM155R61A475MEAA&techpdfname=technical_pdf_Capacitor01&lang=en)、[1 µF 候选官方 EC](https://ds.murata.com/simserve/characteristics?ReqType=TechPDF&partnumber=GRM155R61C105KA12&techpdfname=technical_pdf_Capacitor01&lang=en)。

## 4. USB1：原模型不能识别完整型号

已确认原 Altium 的 USB1 是 16 个 USB2 电气触点、4 个外壳焊脚及 2 个定位孔；原 SchDoc 的 24-contact 图符包含 PCB 上不存在的 SuperSpeed 引脚，RevB 图符已经清理。原模型导出为 `1.step`，STEP 产品名只是 `User Library-USB - C` / `User Library-USB - C v1`，不包含厂家、系列或订货后缀。

证据可直接从仓库保留的 [原 Naive 主板 PcbDoc](<../../Naive Version/HoloCubic-Assembled/MainBoard/MainBoard.PcbDoc>) 复核。该文档的 `/Models/Data` 嵌入模型表中，USB1 对应 `1.step`，模型 ID 为 `{0C0AA5BC-D37F-49C3-80B7-E9B2EEE21A9A}`；J1 对应 `3.stp`，ID 为 `{9B38544A-6C44-4BAB-A416-35A1F708EB28}`。模型名与实体焊盘共同取自原文件，无需依赖本机临时导出目录。文件名 `Type-C-TOP`、16Pin、外观相似均不是可采购 MPN。

维护者已决定采用 **GCT USB4105-GF-A**，manifest / 原理图已锁定该 MPN，图符为 16 个触点加公共外壳 SH。主板按官方 land pattern 重建 USB 焊盘，而不是给旧封装换名。以下差异说明为何必须实施这项工程修订；对两套焊盘采用一致朝向、以两定位孔所在行归一：

| 项目 | 当前源焊盘 | GCT USB4105 官方 KiCad 封装 | 影响 |
|---|---:|---:|---|
| 两定位孔中心距 / 孔径 | 5.78 mm / Ø0.65 mm | 5.78 mm / Ø0.65 mm | 这一项相同不足以证明适配。 |
| 信号焊盘中心行至定位孔行距离 | 1.54 mm | 1.075 mm | 相差 0.465 mm，不能按原信号焊盘直接认定兼容。 |
| 前、后外壳槽孔中心行距 | 4.00 mm | 4.18 mm | 需要采用所选厂家焊盘并重新核对口位。 |
| 原外壳前槽孔长 | 1.20 mm | 1.40 mm | 钻孔 / 铣槽不能仅靠焊盘铜皮包容。 |

GCT 的端子长度后缀、插入口基准面和高度也必须和板厚、外壳开孔共同确认。当前已选料并实施官方封装修订，整机样件仍待验收；须按最终 RevB PCB 采购装配，不能拿原 Altium 焊盘直接下该型号。具体口位与高度注册以机械审查为准。

来源：[GCT USB4105 原厂图纸](https://gct.co/files/drawings/usb4105.pdf)、[原厂产品规格](https://gct.co/files/specs/usb4105-spec.pdf)。本地官方 KiCad 库文件为 `Connector_USB.pretty/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.kicad_mod`。

## 5. J1 microSD 卡座：选用 Molex 104031-0811

原元件名 `TF-Card-Amphenol with TF` 没有完整料号。嵌入 `3.stp` 的产品名为 `SW3dPS-Micro_SD`，还包含已插入的卡，不能把整个 STEP 外包络直接当作卡座壳体尺寸。

当前源焊盘的可重复核对特征：1–8 为 1.10 mm 间距；两检测/开关点 9、10；外壳 S1–S4；焊盘局部坐标见下表。单位 mm，原 footprint 局部坐标，不是厂图视图，比较前需做刚体配准和 B 面镜像处理。

| 焊盘 | 中心 (x,y) | 焊盘 size（原文件存储值） |
|---|---|---|
| 1 / 8 | (3.300,0) / (-4.400,0) | 0.70 × 1.75，原实例角度 90° |
| 9 | (5.675,10.800) | 1.00 × 1.55，90° |
| 10 | (-5.525,9.225) | 1.45 × 1.00，90° |
| S1 | (5.750,0.125) | 1.50 × 1.50，90° |
| S2 | (-5.727,0.125) | 1.016 × 1.50，90° |
| S3 | (6.075,8.375) | 0.80 × 1.40，90° |
| S4 | (-5.850,7.725) | 0.80 × 1.50，90° |

可验证的新候选为 **Amphenol GTFP08431BEU**：厂家当前单品页为 Active，并公开提供 drawing / STEP。它有确定采购身份，但尚不能据源模型名认定为原型号；必须逐 pad、开关触点、安装面、高度、卡的伸出量和按压退卡行程比对后再决定采用。

原厂来源：[产品与当前 Active 状态](https://www.amphenol-cs.com/product/gtfp08431beu.html)、[GTFP084xxBEU 原厂工程图](https://cdn.amphenol-cs.com/media/wysiwyg/files/drawing/gtfp084xxbeu.pdf)、[原厂 STEP ZIP](https://cdn.amphenol-cs.com/media/wysiwyg/files/3d/sgtfp08431beu.zip)。现已通过正常浏览器下载官方 PDF / STEP，并实际查看 Rev F（2017-07-14）的两页图纸。可访问的同一原厂图纸镜像为 [DigiKey 留存的 Rev F](https://media.digikey.com/pdf/Data%20Sheets/Amphenol%20PDFs/GTFP084xxBEU-F.pdf)。

已确认不是 drop-in，差异为：

- 厂图壳体横向 14.40 mm、主壳深 14.23 mm、含外伸锁扣的整体深度达 15.20 mm、标称板上高度 1.85 mm。原 STEP 的整体宽为 12.00 mm，顶面离板面 1.6875 mm；它含插卡，16.6375 mm 的总深度不能直接与新壳深比较。仅横向就需额外容纳 2.40 mm；标称顶高增加约 0.1625 mm，尚未叠加厂家 / 装配 / 壳体公差。
- 新厂图为 8 个信号焊盘（1.10 mm pitch、0.80×1.50 mm），检测点为一个 Normal Open CD 对外壳接地触点，另有 3 个 GND 固定焊盘。源封装为 8 个信号 + 两个开关点 9/10 + 4 个固定脚，焊盘数量和位置均不同。
- 新厂图的纵向中心尺寸有 9.90 / 10.30 / 10.50 mm 三档，并非源封装的八脚完全同排；这些尺寸属于厂家图自身基准，不能直接作为原 KiCad 局部 Y 坐标。
- 官方网页给出的 STEP ZIP 文件名为 GTFP084XXB1EU.stp，但 STEP 内部 PRODUCT 标识为 GTFP084XXB1HR。该复用模型需与 BEU 工程图逐项比对；不能只凭官网链接把坐标、朝向、板面或形状当作已确认的精确订货版本。

因此采用此在产候选，需要新建厂家焊盘、确认 CD / SH 的图符映射，并重新做整个 B 面元件 / 插卡及退卡行程的碰撞检查；目前不能保证原外壳与已布 B 面小件可原样保留。

维护者现已选用更紧凑的 **Molex 104031-0811（厂家无连字符格式 1040310811）**，不采用上述较大的 GTFP 候选。厂家当前系列页和规格书确认其为前插、push-pull、1.10 mm pitch、1.42 mm 高、8 个电气触点及独立常开卡检测。官方工程图 SD-104031-001 Rev B2 已正常下载并实际查看，主体宽 11.95±0.15 mm、深 11.40±0.5 mm，仍须替换旧焊盘并按真实卡口 / 卡中心轴注册，不能沿用旧 J1 origin 推断壳体位置。

官方图的 T1–T8 分别为 DAT2、CD/DAT3、CMD、VDD、CLK、VSS、DAT0、DAT1；对应本项目 SD_DAT2、GPIO15、GPIO13、3V3、GPIO14、GND、GPIO26、SD_DAT1，保持 SPI 固件映射。厂家 G1–G4 是壳体地焊盘；KiCad 对应库用四个重复 `SH`。库内 9 / 10 是两独立检测端的工程编号，厂家图只称 switch / detect terminal；无卡开路、插卡闭合。当前 manifest 和原理图已明确 **9 / 10 均接 GND，检测功能未使用，SH 接 GND**；这两个检测端不属于信号 DAT3。

厂家规格为每触点最大 0.5 A、10 V、工作环境 −25～85°C、10,000 次插拔。PS-104031-001 §7.1 还建议外壳设置防掉卡挡盖，并将锁卡状态下卡与盖间隙控制在 0.25 mm 以内；几何无碰撞不能代替冲击 / 振动保卡验证。厂家产品页已在正常浏览器实际渲染核实，Part Details 的 Status 为 **Active**；文字抽取中混入的 limited-information / no-result 模板不代表此料已停产。采购前仍须由授权渠道核验供货状态及批次。

原厂来源：[产品页](https://www.molex.com/en-us/products/part-detail/1040310811)、[当前系列表](https://www.molex.com/en-us/products/series-chart/104031)、[正式工程图](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/104/104031/1040310811_sd.pdf)、[产品规格书 PS-104031-001](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/104/104031/PS-104031-001-001.pdf)。J1 已采用受控 `RevB_J1`，原理图同步单一 SH 编号；安装注册、插卡外端变化及 B 面器件对新下壳的约束以最终机械审查为准，仍保留整壳装配与插拔实测门槛。

## 6. A1 天线与已锁接口件

A1 的图符 / 封装标成 RAINSUN / AN5120，但原作者在 [Issue #2 明确回复“crossair c3”](https://github.com/peng-zhihui/HoloCubic/issues/2#issuecomment-771743607)，[Issue #56 又确认 CrossAir](https://github.com/peng-zhihui/HoloCubic/issues/56#issuecomment-872680393)。这与源标签不一致。

Rainsun 官网现列有 5.1×2.0 mm 的 [AN-2051](https://rainsun.com/rswordpress/index.php/wifi_bluetooth-antenna/)，不能据大小接近把它当作原器件。维护者现已选定 **CrossAir / 广州寒武纪电子科技有限公司 CA-C03**，以厂家 [CA-C03 资料页](https://gzhwjdz.com/DownLoad/45858.html) 的规格为追溯依据，改正源 RAINSUN 标签。

A1 的完整型号已明确；工程 land 采用受控修订，仍需确认馈点方向、净空及机壳注册，再做 VNA / 装机 RF 验证。不能把“SiP 内有匹配网络”等同于更换外部天线免验证。

现已取得厂家网页提供的 **CA-C03_V02** 原始规格书，完整 PN 确认为 **CA-C03**，厂商为广州寒武纪电子科技有限公司 / CrossAir。已核对的工程差异如下：

| 项目 | 原 AN5120 标签对应源几何 | CrossAir CA-C03_V02 |
|---|---|---|
| 器件身份 | RAINSUN / AN5120 标签，无法据此确定采购料号 | CA-C03；供货应指定厂家和规格版本，不只购买印有“C3”的泛名件 |
| 本体 | 源 STEP 约 5.115×1.846 mm，不能作为 CA-C03 厂图 | 5.5±0.2 × 2.0±0.1 × 1.0±0.1 mm |
| 两端 land | 0.8×1.8 mm，中心距约 5.103 mm | 各 1.2×2.0 mm，内边间隔 4.3 mm，即中心距 5.5 mm |
| 端子功能 | 一个信号 pad，另一端无号 / 无网 | 有标识端为 feed；另一端仅固定焊端，参考原理图不接 GND |
| 参考布局 | 不能由源 footprint 名称推出 RF 条件 | 厂家采用 58×40 mm、1.0 mm 板厚测试板，角部图示 Empty Area 为 10×7 mm |

厂家参考网络列出 0 Ω / 3 nH / 0 Ω，但规格书也明确工作频率需要通过匹配调试实现；该值不能直接移植后当作本机 RF 已合格。当前选择 CA-C03 恢复原作者明确实物身份，pin 1 为 RF feed，pin 2 为固定焊端并标 NC，**不能接 GND**。现有 RF 七段走线保留，局部焊盘采用受控 heel / toe / 高度修订并由机械检查锁定；此项属于工程 land 偏离，须通过焊接工艺和实物验证，不能声称与厂家推荐焊盘完全一致。本版不增加厂家参考板的 3 nH 匹配网络；保留 VNA、整壳 RF 及厂家供货追溯门槛。

两板 CON1 已明确选用 Hirose **FH12-8S-0.5SH(55)**，采用实际 8P land pattern、固定焊盘 MP 接 GND。还需采购 8 芯 / 0.5 mm 排线并锁定长度、厚度、同面/异面接触形式；电路要求主板 pin i 对屏板 pin 9-i，不能仅凭卖家“A线/B线”名称下单。LCD1 目前锁 P133H002，但须等待屏体、尾排与外壳最终注册结论。

## 7. 采购放行条件

1. 69 个装配位号的完整 MPN 已从两板原生原理图导出；布线及最终机械版本冻结后核对 PCB 字段和装配面，再发布制造 BOM。逐批核验来源、订货后缀、封装和来料标记，尤其 MPU-6050 旧库存。
2. USB1、J1、A1 必须各有完整料号、版本受控的厂家工程图和对应 PCB 焊盘。若采用新候选，先完成原位/开孔/高度约束核对，再修改电路板与机械基线。
3. MPU-6050 的供货策略要明确为“可追溯旧库存复刻”或另立硬件/固件迁移任务，不能在量产 BOM 中忽略其已停产状态。
4. 屏幕 / FFC 最终装配注册完成后，重新跑两板原生 ERC、DRC、schematic parity、机械检查和整机静态验证；随后进行实际上电、USB、背光电流、热插拔、SD、IMU 和 RF 检验。

这些未闭合项是本版实际观察到的采购与装配问题，不由 ERC / DRC 通过自动消除。
