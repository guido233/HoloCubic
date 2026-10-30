# HoloCubic Naive RevB 工程修订

本目录维护 Naive 外形的原生 KiCad 10 工程。原作者的 Altium 工程保留在 `1.Hardware/Naive Version/`，没有覆盖。Ironman 尚未作本轮硬件修订。

单台整机材料见 [采购说明](PURCHASING.md)；板上用量见 [BOM.csv](BOM.csv) 和 [合并采购表](BOM-grouped.csv)。

**当前为工程验证版本，尚未完成实物装配和通电验收。** 原生 ERC、DRC、网表一致性检查通过只能证明文件内的相应约束成立；屏幕尾排折弯、外壳净高、天线性能、USB 热插拔与供电波形仍需样机验证。不要根据文件名或一张渲染图直接批量下单。

## 打开工程

使用 KiCad 10.0 或更新的兼容版本，分别打开：

- `MainBoard/MainBoard.kicad_pro`：主板、电源、USB、ESP32、传感器、SD。
- `ExtendBoard/ExtendBoard.kicad_pro`：显示板、FFC、屏幕、背光恒流驱动。

每块板附有本地 `.pretty` 封装库、`.kicad_sym` 符号库和库表，电路与焊盘均在原生文件中，工程并非仅包含一份修改建议。macOS 从完整 KiCad 套件启动原理图编辑器；不要把内部的 `eeschema.app` 单独拷出安装，否则其相对路径共享库可能失效。

## 本轮电路修订

| 部位 | 修订内容与目的 |
| --- | --- |
| USB-C | CC1、CC2 各自接独立 5.1kΩ Rd；数据、CC 与 VBUS 增加所选器件的保护路径。USB 数据线保持两种插头方向的连接关系。 |
| 3.3V 电源 | 原 250mA LP2992 改为 TPS62162 1A 降压方案；增加电感、有效容量设计所需的输入输出电容。TPS22918 控制系统 5V 的上电斜率；RC/CT 时序需要示波器验证。 |
| USB-UART | CP2102 的 VDD6 接独立 `CP_VDD` 本地旁路，不与主板 3.3V 稳压输出并联；REGIN 增加本地去耦。 |
| MPU6050 | 删除原中心焊盘、中心锡膏与孔；中心区域禁止顶层铜、走线和过孔，遵循该封装的装配要求。 |
| ESP32-PICO | 热焊盘使用 4.5mm 接地铜、4.0mm 阻焊开口、21 个 0.25mm 热过孔，以及 16 个 0.75mm 锡膏窗口；与 MPU 的中心禁焊区分别处理。 |
| 总线与启动 | 增加 I²C 外部上拉和 SD DAT1/DAT2 上拉；保留 GPIO12 隔离；EN 电容改为 1µF；BH1750 DVI 增加复位延迟 RC。 |
| RGB | 5V WS2812B 前增加 AHCT 缓冲、旁路、串联电阻及复位默认电平，避免依赖 3.3V 直接驱动 5V 数据输入。 |
| 显示板 | 增加逻辑与 5V 本地去耦；AL5802 加 27Ω 电流设定电阻，背光典型约 24mA；NMOS 分流 EN，保持 GPIO5 低电平点亮的固件极性。 |
| FFC | 两板使用确切的 Hirose FH12-8S-0.5SH(55)，按官方 8 针焊盘替换未识别的旧封装；原文件嵌入的 16 针模型不能用于认证 8 针连接器。 |

主板仍使用 ESP32-PICO-D4、MPU6050、BH1750、CP2102 以维持复刻电路与固件接口。ESP32-PICO 系列已列为 NRND；MPU6050 已停产。它们不是当前可随意等效采购的新设计器件。采购替代、旧料来源及接口验收条件请见 [BOM 审查](BOM-review.md)。

USB1、J1、A1 已分别选定 GCT USB4105-GF-A、Molex 104031-0811、CrossAir CA-C03，采用相应厂图重新定义焊盘。Molex 完全插入后的卡端比原版左移 0.65mm，以避开 USB 贯穿固定脚；这项接口调整及下壳配合见机械审查。CA-C03 的第二端是机械焊端，保持独立未连接，不能接地。

GPIO5 是启动配置脚。显示板 Q1 选用在 2.5V 栅压下有导通规格的 AO3400A，栅极直流高阻，配合 100kΩ 上拉维持复位默认高电平；1kΩ 栅极串联电阻兼顾 5kHz 背光 PWM。此项检查需要核器件类型，单看引脚网络相同不足以确认启动电平正确。

CP2102 内部电源到 2.7V 的上升时间要求不超过 1ms（Silicon Labs 数据手册 Table 5）。TPS22918 在 CT=1nF、5V 时的输出 10–90% 上升典型值约 2.54ms，不能据此保证 CP 内部 LDO 的上升时间。因此 C16 选择 **100pF、C0G、50V、±5%（GRM1555C1H101JA01D）**，按 TI Eq.3 估算 5V 上升约 0.425ms；这是典型估算，不能代替 CP_VDD 实测。按约 13µF 有效 5V 负载电容估计，纯充电电流约 0.12–0.15A，负载启动及偏差另计。首板需同时量 CP_VDD 到 2.7V 的时间、USB 枚举和入口电流。CP2102 REGIN 的工作范围上限为 5.25V，电源应为受控 5V，不把 5.5V 当作其保证工作条件。

## 屏幕、排线与结构

P133H002 是电气接口候选：12 针、0.7mm 间距、ST7789V，VDD 与 LEDA/LEDK 分开，厂家背光电路没有内置限流。本版外置恒流驱动针对这类裸屏设计，不能把任意“1.3 寸 ST7789 模块”当作同一物料。

配套现代固件将共用 ST7789 写时钟设为 **10MHz**。现有 [Sitronix ST7789V v1.3](https://newhavendisplay.com/content/datasheets/ST7789V.pdf) 第 44 页 Table 6 要求写周期至少 66ns、高低脉宽各至少 15ns，不能据此保证先前的 40MHz。10MHz 的全帧 RGB565 纯传输时间约 92ms；更高刷新速度须先取得实际屏幕的时序保证，再在最终排线和板上测接收端建立保持时间、过冲 / 振铃，并完成并发读卡及温度 / 电源范围验证。SD 仍使用当前 Arduino 驱动默认的 4MHz，不因这一屏幕调整改动。

**P133H002 尚未通过整机机械适配验收。** 本轮把显示板改为 12 个 5.5×0.50mm 长焊盘，并重排连接器及相邻器件、完成重新布线，覆盖裸屏背折图与旧落点的纵向差异。144 项相关公差计算通过，最小纵向搭接 0.9611mm；0.75mm 是项目手工焊接阈值，不是屏厂保证。长焊盘没有 F.Paste，须在 PCBA 回流后受控手工焊接 FPC。此项只核纵向落区，不能证明尾排允许的折弯、露铜面、横向注册或整机就座；见 [显示接口计算和 1:1 图](Closure/DISPLAY-INTERFACE.md)及 [机械审查](MECHANICAL-REVIEW.md)。

两板 FFC 功能保持反序：主板 1↔显示板 8，直到主板 8↔显示板 1。已明确两端底接触及摊平后露铜同面的无交叉排线，并给出 [端部尺寸、映射和定制图要求](Closure/FFC-CABLE-SPEC.md)。最终长度仍取决于尚未锁定的整机路径；不能把 51/76mm 的有条件样品候选直接当作最终采购料号，也不能忽略其端部公差差异。

使用新的 [RevB 下壳 STEP](Mechanical/Lower-RevB.step)，与原 Naive 上壳配合。它保留外观、USB 开口和承托高度，内部增加背面元件避让槽；[实体检查记录](Mechanical/Lower-RevB-verification.json)包含来源 SHA、尺寸、体积与间隙。`tools/hardware/revb_case.py` 可重现该减材操作，依赖 `cadquery-ocp==8.0.1.1.0`。承托注册和打印公差仍需实物确认。**更换 TF 卡需要拆下壳**，本版没有新增外部取卡口。

板框与受保护孔位由 `tools/hardware/baseline.json` 记录，保留原 Altium 文件 SHA。原两层设计有约 1.000mm 介质和两面约 35.56µm 铜，总厚约 1.071mm（不含阻焊），这是历史几何基准，不能作为本轮主板的最终制造厚度。

本轮主板采用**六层原型方案**，最终布线与检查记录以本目录冻结的工程为准：F.Cu / In1.Cu / In2.Cu / In3.Cu / In4.Cu / B.Cu。In1、In4 为专用 GND 层；In2 混合承载 3V3 铜面、其它电源与信号；In3 承载信号与 GND 铜面。显示板保留两层。三处严格 RF 内层禁布区覆盖四个内层，原七段外层 RF 几何保持；这一约束不等于天线匹配或阻抗已经验证，仍需在实际层叠与外壳内做 VNA 和无线性能测试。

当前选择 JLCPCB 公开的 **JLC06101H-3313** 六层、订单名义 1.0mm 模板。公开铜与介质合计 1.04mm，加当前双面阻焊预算后 CAD 总厚 **1.06mm**。这已替换先前自定义的 1.0192mm 层叠；[完整公开请求/响应、模板参数和 DFM 约定](Closure/STACKUP-SPEC.md)均已保存。工程选择不等于板厂已经接受本工程订单，交付总厚口径及公差仍须回签。

| 自顶向下 | CAD 名义厚度 |
| --- | ---: |
| F.Mask / F.Cu | 10µm / 35µm |
| prepreg / In1.Cu | 99.4µm / 15.2µm |
| core / In2.Cu | 250µm / 15.2µm |
| prepreg / In3.Cu | 210.4µm / 15.2µm |
| core / In4.Cu | 250µm / 15.2µm |
| prepreg / B.Cu / B.Mask | 99.4µm / 35µm / 10µm |

模板的 3313/core/7628 厚度及公开设计 Dk 已同步 PCB，移除无依据的 Df 占位值；不宣称控阻抗或 RF 已合格。已按 1.06mm 重新筛查主板与壳体、USB 的几何关系。订单名义 1.0mm、模板铜与介质 1.04mm、CAD 含阻焊预算 1.06mm 不是同一厚度定义，须取得板厂交付口径和范围。受保护孔位及接口修订使用显式 profile，不改写历史 Altium 基线。

主板属于密集双面贴装。制造商须确认约 0.102mm 局部细线、0.127mm 铜间距、0.25mm 成品孔及至少 0.10mm 孔环的能力；电源主干使用更宽走线。GCT 自身孔与焊盘的厂图间距约 0.194mm，由限定在 USB1 内部的 0.19mm 规则检查，板上其余孔仍要求 0.20mm。两板收紧为阻焊桥至少 0.10mm、开窗到异网铜至少 0.09mm；显示板外扩调整为 +0.025mm 后原 33 项阻焊错误归零。询价目标采用绿色阻焊、ENIG，PICO 热孔单独标识树脂填孔盖镀并保留底面阻焊，80µm 钢网作为装配评估起点；不得把盖油等同填孔，最终工艺由制造方回签。

## 检查

2026-10-29 冻结版本的实际结果见 [检查记录](VALIDATION.md) 和 [可追溯结果](validation-results.json)。

在仓库根目录执行；`kicad-cli` 可以在 PATH，也可通过 `--cli` 给出绝对路径：

```sh
python3 tools/hardware/verify_hardware.py --drc --output /tmp/holocubic-checks.json
python3 -m unittest discover -s tools/hardware -p 'test_*.py' -v
```

验证器重新导出原生网表、运行 ERC/DRC，并核对两板所有引脚节点集合、网络名、料值、封装、原理图 UUID 链接，以及电源隔离、CC、电平缓冲、SD/I²C 上拉、背光路径、MPU 禁布区和 PICO 热焊盘。故障注入测试检查验证器能识别错误连接、启动脚加载及不当锡膏等故障。报告记录原生工具的规则、忽略项和失败项；检查脚本不会修改工程或把实测结果写成通过。

`revise_mainboard.py`、`revise_extendboard.py` 是从原始导入建立本轮布局的工程迁移工具，**重新运行会产生需要重新布线的布局**。日常维护请直接编辑本目录原生工程，修改后重新运行验证，不要把布局生成成功当成完成布线。

## 首块样机的释放条件

本轮已完成的文件修订、仍待厂家资料或实物验证的项目见 [闭合状态](Closure/README.md)。新增 [诊断固件、测量位置和记录表](Closure/BRINGUP.md)只准备验收工具，尚未在样机上执行。

先锁定所有关键料号和推荐焊盘，完成屏幕/FFC/壳体的实物配合，再检查短路、限流上电、5V 与 3.3V 启动/负载阶跃、USB-C 两个方向和热插拔、串口枚举/自动下载、背光实际电流与温升、SD 读写和 WiFi 同时运行、传感器及天线在最终外壳内的表现。背光 24mA 来自典型 VBE/27Ω，不能用 1% 电阻公差推导成全温恒定电流保证；需实际测量。

电源预算要求合格 5V 电源及线缆，建议额定至少 1A。满负载不能假定所有电脑 USB 2.0 的 500mA 端口都足够；CC Rd 也不是 USB PD 或电流档位检测器。本工程没有完成 USB 合规认证。

## 主要原厂依据

- [TI TPS62162 数据手册](https://www.ti.com/lit/ds/symlink/tps62162.pdf)、[TPS22918 数据手册](https://www.ti.com/lit/ds/symlink/tps22918.pdf)：电源及上电控制。
- [Silicon Labs CP2102/9 数据手册](https://www.silabs.com/documents/public/data-sheets/CP2102-9.pdf)：VDD/REGIN、典型应用与输入额定；不能套用 CP2102N 的不同要求。
- [Diodes AL5802 数据手册](https://www.diodes.com/datasheet/download/AL5802.pdf)：低边电流设定和外部 NMOS 分流 EN 的调光方式。
- [POLCD P133H002](https://www.polcd-digital.com/products/1-3-inch-tft-lcd-display-240x240-pixels-p133h002)：候选屏接口、背光和机械尺寸。
- [Hirose FH12-8S-0.5SH(55)](https://www.hirose.com/en/product/p/CL0586-0744-5-55)：8 针、底接触、0.3mm FFC/FPC、2mm 高连接器。
- [Espressif ESP32-PICO 系列数据手册](https://documentation.espressif.com/esp32-pico_series_datasheet_en.html)：针脚、电源与 NRND 状态。

这些文件保留原项目的著作权和许可证；RevB 新增内容的维护记录在 Git 提交中。
