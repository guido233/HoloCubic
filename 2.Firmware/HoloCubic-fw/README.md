# HoloCubic 固件维护版

本分支面向原版 ESP32-PICO-D4 电路板，升级编译工具链和图形库，同时保留 240×240 ST7789、棱镜镜像显示、MPU6050 手势输入和 SD 卡资源访问。默认启动显示原有 Logo。Naive 和 Ironman 的区别由编译环境选择。

## 编译与烧录

使用 Python 3.11 或更新版本，在仓库根目录执行：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install platformio==6.1.18
pio run -d 2.Firmware/HoloCubic-fw -e naive
```

Ironman 使用 `-e ironman`。Naive 配置一颗 RGB 灯，Ironman 配置两颗。USB 接口使用支持数据传输的线缆。

```sh
pio device list
pio run -d 2.Firmware/HoloCubic-fw -e naive -t upload --upload-port /dev/cu.SLAB_USBtoUART
pio device monitor --port /dev/cu.SLAB_USBtoUART --baud 115200
```

将串口替换成 `pio device list` 实际列出的端口，Windows 通常为 `COMx`。项目不再固定 `COM7`，也不需要修改已安装 SDK 或 TFT_eSPI 源码。

固件使用 4MB Flash 的 `huge_app.csv` 分区，应用槽为 3MiB，不提供双槽 OTA。首次从旧固件迁移时请使用 PlatformIO 的完整上传流程，同时更新 bootloader、分区表和应用；仅替换旧分区中的 application.bin 无法容纳此版本。

## 依赖版本

| 依赖 | 固定版本 |
|---|---|
| PlatformIO Espressif32 | 8.0.0 |
| Arduino-ESP32 | 3.3.12，框架包 4.30312.261024 |
| LVGL | 9.6.0 |
| TFT_eSPI | 2.5.43 |
| FastLED | 3.10.8 |
| Electronic Cats MPU6050 | 1.4.5 |
| ArduinoJson | 7.4.3 |

`platformio.ini` 使用托管依赖。`lib/` 与上一级 `Libraries/` 内的旧快照保留作原项目参考，不参与维护版构建。旧 Visual Studio 模拟器和 Windows 可执行程序也属于原版工具，不适用于新版资源格式。

屏幕配置在 `include/tft_setup.h`，LVGL 配置在 `include/lv_conf.h`。LVGL 使用 32KiB 内存池、RGB565 局部刷新缓冲，索引图片按行解码，以适配无外部 PSRAM 的原板。

Naive 与 Ironman 共用的 ST7789 **写时钟为 10MHz**。Naive RevB 候选 P133H002 指定 ST7789V；现有 [Sitronix v1.3 数据手册](https://newhavendisplay.com/content/datasheets/ST7789V.pdf) 第 44 页 Table 6 给出写时钟周期至少 66ns、高低脉宽各至少 15ns。先前 40MHz 的周期为 25ns，不能由这份时序表保证。10MHz 将纯数据带宽降为先前的四分之一，240×240 RGB565 全帧传输理论上约 92ms，尚未计命令及绘图开销；局部刷新按实际区域传输。调高时钟前须取得实际屏幕 / 控制器修订的有效时序依据，在最终 PCB、FFC 与外壳中测接收端的时钟、数据建立保持时间及振铃，并通过温度、电源和并发读卡压力验证。旧版归档固件未修改。

## SD 卡与联网

SD 使用显式 SPI 引脚：SCK 14、MISO 26、MOSI 13、CS 15。缺少 SD 或 IMU 时可继续显示内置 Logo；IMU 缺失时手势输入不可用。

如果要联网，在 SD 根目录创建 UTF-8 文本 `wifi.txt`：

```text
你的2.4GHz WiFi名称
你的WiFi密码
可选的Bilibili数字UID
```

第三行可以省略。开放网络保留空的第二行。SSID 和密码的首尾空格会保留，支持 CRLF 和末行无换行。不要把真实凭证提交到 Git。

有有效配置时启动后尝试连接，最长等待 15 秒。第三行存在 UID 时，通过 HTTPS 查询一次粉丝数并输出到串口；它没有被添加成完整桌面应用。校时或证书验证失败、网络错误、接口拒绝都会返回错误，程序继续离线运行。HTTPS 使用 Arduino 框架内置 CA 集合，不关闭证书校验；系统时间未知时先尝试 NTP 校时。

外部服务可能需要网络可达性、鉴权或额外接口适配。默认 Logo、相册素材文件接口和示例 GUI 可独立使用。

## 图片转换与 GUI 迁移

原项目 LVGL 7 的 `.bin` 资源应由原图重新生成，使用本分支的转换器：

```sh
python -m pip install -r 3.Software/ImageToHolo/requirements.txt
python 3.Software/ImageToHolo/get_holo.py picture.png
```

输出在原图旁，文件名为 `picture.lv9.bin`，是 LVGL 9 RGB565 二进制图片。支持多个图片、`--output-dir`、`--background RRGGBB`、`--force`；`--legacy-v7` 供原版固件使用，输出 `picture.lv7.bin`。转换器不会自动缩放图片，整屏图片应准备为 240×240；详见 `--help`。

将图片复制到 SD 后，通过 `S:/picture.lv9.bin` 访问。示例场景使用 `S:/Scenes/Holo3D/frame000.bin`，需要把新版输出复制或改名到该路径；文件缺失或格式不合法时回退到内置 Logo。

默认入口为 `lv_holo_cubic_gui()`。`setup_ui(&guider_ui)` 构建额外示例，`lv_screen_load(guider_ui.home)` 可显示色相滑条。LVGL 9 不再提供原 `cpicker` 控件，示例已改为可用编码器操作的滑条和颜色预览。原字体位图与内置 Logo 均已迁移。

## 回归验证

安装上述依赖和图片转换器依赖后，在仓库根目录运行：

```sh
sh 2.Firmware/HoloCubic-fw/test/imu_test/run.sh
sh 2.Firmware/HoloCubic-fw/test/sd_card_test/run.sh
sh 2.Firmware/HoloCubic-fw/test/lv_fs_test/run.sh
python 2.Firmware/HoloCubic-fw/test/network_test/run_host_tests.py
python 2.Firmware/HoloCubic-fw/test/gui_test/run.py
python -m unittest discover -s 3.Software/ImageToHolo/test -v
```

主机测试需要 C/C++ 编译器，覆盖传感器与存储故障、读取边界、HTTPS 错误处理、实际 LVGL 渲染以及图片二进制格式。GitHub Actions 同时编译两种板型并运行回归；编译生成物可在 workflow artifacts 中下载。

主机回归和交叉编译不能验证实际屏幕偏振方向、供电、SD 卡电气时序、手势手感以及线上接口可用性，这些项目需要上板确认。
