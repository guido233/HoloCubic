# Naive RevB 冻结检查记录

核对日期：2026-10-29。维护源为本目录的原生 KiCad 工程；主板六层，显示板两层。完整料号和位置见 [BOM](BOM.json)，机器可读结果与工程 SHA 见 [validation-results.json](validation-results.json)。

| 检查 | 实际结果 |
| --- | --- |
| KiCad 10.0.7 原生与电气约束 | 202 项，0 失败 |
| 两板 ERC | 各 0 项违规 |
| 两板 DRC（所有严重级别、全部走线错误、重新填铜） | 各 0 项违规、0 未连接项、0 原理图一致性问题 |
| 电气与机械故障回归 | 35 项通过 |
| 板框、孔与受控接口修订 | 两板通过 |
| 历史硬件 / STEP 源文件 | 40 个未改；四块原 Altium PCB 的基线 SHA 匹配 |
| BOM | 69 个位号、39 个完整 MPN、39 个采购合并项，数量合计 69 |
| 采购 Excel | 40 个公式，0 公式错误；已检查排版 |
| 主板过孔钻孔与 SMD 锡膏区域交叠筛查 | 0 项 |
| 显示焊接纵向搭接 | 144 项相关公差情景通过，最小 0.9611mm |

主板 PCB SHA-256：`a05fb4db8785f69a0e96533620440d110ff2dc13d2e4b28887b48de03e031c39`。显示板 PCB SHA-256：`7ba3a6e58040c57fe67f55df174be974967f560e97ab8b37d000d93db8e1c112`。原理图、项目及 BOM 文件的完整散列见 JSON。

原生报告如实记录项目未启用的检查：ERC 为单次全局标签、四路接点、SPICE 模型及 footprint filter；DRC 为 tuning profile track geometries。所有实际报告的 error / warning / exclusion 项均为空。USB1 厂图内部孔距采用范围限定的 0.19mm 规则，其余孔保持 0.20mm；这些工程规则及边界见 [工程说明](README.md)，不代表板厂已接受制造条件。

已实际启动 macOS 完整 KiCad 10.0.7 套件，并由项目管理器打开 eeschema，主板原理图正常渲染，无共享库或安装错误弹窗；应用签名与系统执行评估通过。已目视检查最终主板正反面 3D 图及全部六层铜图。新增 3D 模型明确标记为最大本体包络，不能当作带引脚和极性标记的精确厂家模型。

Naive 现代固件在 ST7789 写时钟 10MHz 下完整编译通过；RAM 98,060 / 327,680 bytes，Flash 2,247,967 / 3,145,728 bytes。esptool 验证 ESP32、4MB/DIO 映像的校验和与哈希通过，固件映像 SHA-256 为 `b2303e96d0b8b2c3103e8afad82af752f38de5679fb38f5b538c8f158142585b`。

另已完整编译独立 `naive-bringup` 诊断入口（RAM 50,100 bytes、Flash 1,229,107 bytes），esptool 映像检查通过；源码经过独立复核，尚未烧录到实物。当前主板选择公开 JLC06101H-3313 模板并以 1.06mm CAD 预算复核机械间隙；显示板长焊区无 F.Paste，明确 PCBA 后手工焊接。详见 [本轮闭合状态](Closure/README.md)。

## 复核

在仓库根目录执行：

```sh
python3 tools/hardware/verify_hardware.py --drc --output /tmp/hardware-checks.json
python3 -m unittest discover -s tools/hardware -p 'test_*.py' -v
python3 tools/hardware/export_bom.py
```

机械命令与下壳重建方式见 [工具说明](../../../tools/hardware/README.md)；下壳实体、包络及间隙见 [机械审查](MECHANICAL-REVIEW.md) 和 [实体检查](Mechanical/Lower-RevB-verification.json)。GitHub Hardware 工作流会重新执行双板检查与故障回归。

## 尚须样机验证

本次检查证明文件中的相应约束成立，尚未进行实物装配或通电。板厂实际六层叠层与公差、P133H002 尾排注册和折弯、FFC 长度与接触面、外壳试装、CP_VDD / 5V / 3.3V 上电与负载波形、USB 双方向与热插拔、背光电流和温升、SD / WiFi 并发、传感器与最终外壳内 RF 均仍需验收。MPU-6050 停产及 PICO-D4 NRND 的采购限制仍适用。本版未发布制造放行结论。
