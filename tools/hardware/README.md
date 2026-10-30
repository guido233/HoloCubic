# Naive RevB 硬件维护工具

最终维护对象是 `1.Hardware/RevB-KiCad/Naive/` 内的原生 KiCad PCB、原理图、项目和本地库。日常修改直接在 KiCad 中进行；下列迁移脚本不是一键重建已布线主板的构建命令。

## 日常检查

```sh
python3 tools/hardware/verify_hardware.py --drc --output /tmp/hardware-checks.json
python3 -m unittest discover -s tools/hardware -p 'test_*.py' -v
python3 tools/hardware/mechanical_baseline.py check Naive_MainBoard '1.Hardware/RevB-KiCad/Naive/MainBoard/MainBoard.kicad_pcb' --revision naive-revb --json
python3 tools/hardware/mechanical_baseline.py check Naive_ExtendBoard '1.Hardware/RevB-KiCad/Naive/ExtendBoard/ExtendBoard.kicad_pcb' --revision naive-revb --map-ref 1=LCD1 --json
python3 tools/hardware/export_bom.py
python3 tools/hardware/display_interface_allowance.py --output-dir /tmp/display-interface
python3 tools/hardware/export_probe_map.py --output /tmp/probe-map
```

前四项需要 KiCad 10 CLI，验证器可自动查找 PATH 和标准 macOS 安装位置；也可用 `--cli`。机械基线与故障回归除调用 CLI 外只使用 Python 标准库。`export_bom.py` 从当前原生网表和 PCB 导出 JSON、逐位号 CSV 与合并采购 CSV，完整 MPN 缺失会失败；坐标不是机台贴片文件。

可选的 `build_bom_workbook.mjs` 把该 JSON 排成 Excel，使用 Codex 随附的 Node 和 `@oai/artifact-tool`；由 `ARTIFACT_NODE_MODULES` 指定包目录，三个位置参数依次为输入 JSON、输出目录、预览目录。CSV/JSON 和电气检查不依赖这个运行时。

`display_interface_allowance.py` 核对当前 12 个长焊盘、无锡膏开口、引脚/间距及 144 个纵向搭接情景，写新目录的 JSON 和 1:1 SVG；它不验证未知折弯路径或横向注册。`export_probe_map.py` 从当前两板提取 15 个现有元件测量端子、源 SHA、CSV 和正反面示意，其中 M10/M11 用于 BH1750 VCC/DVI 复位波形；没有在板上新增测试点，也不测量电压。两者的确定性结果由 CI 与仓库记录比较，防止工程变更后继续引用旧源证据。

## 下壳复现

`revb_case.py --output <新目录>` 只读原 STEP 和当前 PCB，从原下壳重新减材；需要独立环境的 `cadquery-ocp==8.0.1.1.0`。输出 STEP 与验证 JSON 记录输入 SHA、包络、间隙、体积和重读结果。不能以脚本成功代替承托、打印公差及显示组件的实物试装。

## 布局迁移与布线试验

`revise_mainboard.py`、`revise_extendboard.py` 和对应原理图工具用于从原 Altium 导入结果迁移电路与初始布局。`main_four_layer_variant.py`、`finalize_main_assembly.py`、`rearrange_main_bank.py` 等记录本轮明确的叠层、焊盘和布局修订。它们需要各自的冻结输入，**可能丢弃现有布线**；不是日常维护入口。原始 Altium 文件和历史 SHA 不得用最终工程覆盖。

主板当前采用六层，已选公开 JLC06101H-3313 模板（CAD 含阻焊预算 1.06mm），见 [叠层约定](../../1.Hardware/RevB-KiCad/Naive/Closure/STACKUP-SPEC.md)。下述 `main_six_layer_variant.py` 保留为**历史迁移工具**：从 1.0192mm 四层中间副本增加两层，输出仍为旧厚度预算，不会重建当前模板或最终布线，也不接受已是六层的 PCB。只有复查历史中间步骤时才运行，例如：

```sh
"$KICAD_PYTHON" -B tools/hardware/main_six_layer_variant.py \
  /tmp/revb-four-layer/MainBoard.kicad_pcb \
  /tmp/revb-six-layer/MainBoard.kicad_pcb
```

`KICAD_PYTHON` 应由本机 KiCad 安装位置指定。目标 PCB 和 `.variant.json` 必须不存在，源文件不会被覆盖。工具检查完整原生封装及模型字段、走线/过孔、RF 七段（含弧中点）、21 个 PICO 热过孔、16 个锡膏窗口和原区域定义保持不变；仅新增 In3/In4 地铜面，并把三处严格 RF 内层禁布区扩至四个内层。报告记录输入/输出 SHA。它只输出 PCB 和报告；原理图、项目规则、本地库和模型须配套复制到独立项目，并保持文件主名以便网表一致性检查。新增层必须重新填铜，随后完成布线及原生检查。

六层次序为 F.Cu / In1.Cu / In2.Cu / In3.Cu / In4.Cu / B.Cu；In1/In4 专用 GND，In2 为电源与信号混合层，In3 为信号与 GND 铜面。工具写入的 **1.0192mm（含双面阻焊）只是自定义原型厚度记账**，具体厚度见 [工程说明](../../1.Hardware/RevB-KiCad/Naive/README.md)。它不是板厂确认的六层标准叠层，未指定可靠的介电常数或损耗参数，不能用于宣称控阻抗或 RF 合规。[JLCPCB 六层能力页](https://jlcpcb.com/resources/6-layer-pcbs)列有 1.0mm 和厚度不小于 1.0mm 时 ±10% 的一般能力；实际层叠、成品厚度及公差须另行确认。

使用 `pcbnew` 的脚本应由 KiCad 对应版本的 Python 运行，并加 `-B`，避免向签名应用目录写入 Python 缓存。源、目标必须分开，先在仓库外的临时副本试验。`route_copy.py` 会复制项目、保留元件位姿与锁定铜，完成后重新跑原生 DRC/网表一致性；路由器自己的完成状态不能作为验收结果。六层主板的 In1/In4 专用地层用 DSN `power` 类型限制信号走线，并在导入后再次拒绝这些层上的非地走线；In2/In3 保持混合用途，最终由原生填铜和连通性检查验收。

`--plane-ground`、`--skip-router-power` 仅跳过路由任务，供已经手工完成的接地/电源和铜面使用；最终原生检查仍要求所有网络实际连通，任何剩余空气线都会失败。`route_main_usb.py --apply-delta` 可按原 UUID 与几何核对合并经过审查的 USB 修改；合并之后仍须检查整体间距与连通性。

## 模型与导入精度修复

以下两个工具只使用 Python 标准库，并要求新输出路径：

```sh
python3 tools/hardware/finalize_model_metadata.py input.kicad_pcb models.kicad_pcb
python3 tools/hardware/repair_ses_via_rounding.py input.kicad_pcb fresh-drc.json repaired.kicad_pcb
```

`finalize_model_metadata.py` 核对已记录的 STEP 资产 SHA，为指定器件加入明确标注的最大本体包络，并按最大外形修正 D2 装配庭院。它比较保存前后的走线、过孔、焊盘、位姿、铜区与规则；输出旁的 `.models.json` 记录来源及变化。包络不是原厂精确三维模型，也不能证明装配适配。采用副本前须重跑原生 DRC，并将相应修改同步到本地封装库，避免 PCB 与库模型或庭院不一致。

`repair_ses_via_rounding.py` 只处理**该输入板最新原生 DRC 报告**中的 `track_not_centered_on_via` 项：把同网、未锁定直线段的一个端点对齐到距其不超过 2µm 的既有过孔中心，不移动过孔或锁定铜，也不删除检查项。输出旁的 `.rounding.json` 逐项记录修正。它用于 Specctra 整数微米舍入造成的微小偏差，不能修复一般间距、短路、缺线或不合理走线；修正后须重新填铜并通过全部原生 DRC/网表一致性与连通性检查。

本轮使用 KiCad 10.0.7、Freerouting 2.5.0 JAR、fastroute 0.1.14 进行试验。只有经过最终原生检查的 PCB 才是维护源；临时 DSN/SES 或未收敛的自动布线结果不应替代它。通电、时序、屏幕尾排和 RF 等样机条件见硬件目录的工程说明。
