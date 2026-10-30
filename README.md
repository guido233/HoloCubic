> 本 Fork 的固件已迁移到 Arduino-ESP32 3.3.12 和 LVGL 9.6，保留原版硬件接口。
> 编译、烧录、板型选择和资源迁移请阅读 [固件维护说明](2.Firmware/HoloCubic-fw/README.md)。
> 下文硬件设计与价格描述保留原作者历史记录；MPU6050 已停产，ESP32-PICO-D4 已标记为 NRND。
> Naive 硬件修订源文件在 [RevB KiCad 工程](1.Hardware/RevB-KiCad/Naive/README.md)。这是待样机验证的工程修订，采购、装配限制及检查命令均写在该目录。

![](/5.Docs/Images/Holo1.jpg)

# HoloCubic--多功能透明显示屏桌面站

**视频介绍：** https://www.bilibili.com/video/BV1VA411p7MD/

## 0. 关于本项目

> 稚晖君注：这是为了更新视频，缓解本人拖更两个月的尴尬，用一个周末时间赶出来的一个有意思的小玩意 :D

如视频所述，本项目有意思的地方在于使用了一个分光棱镜来设计出`伪全息显示`的效果。这个小设备总的来说功能比较多，因为搭载了WiFi和蓝牙能力可以实现很多网络应用，在本仓库中给大家提供了一个开发框架以及一些基础功能（天气、粉丝数监视器等），大家可以基于我的方案继续扩展实现更多应用。

本项目的硬件方案是基于`ESP32PICO-D4`的，乐鑫的一个很实用的MCU芯片，由于采用了SiP封装是的PCBA整板面积能做到一个硬币大小；软件方面主要是基于`lvgl-GUI`库，我移植了ST7789 1.3寸`240x240`分辨率屏幕的显示屏驱动，同时将`MPU6050`作为输入设备通过感应的方式模拟编码器键值来交互。

## 1. 硬件打样说明

原 Altium 文件保留作为历史基线。复刻前请先阅读 [Naive RevB 说明](1.Hardware/RevB-KiCad/Naive/README.md)：原板的 USB-C CC、电源、MPU6050 焊盘、上拉与背光驱动存在需要修正或验证的项目。原文的价格是历史估算，不能作为当前采购预算。

`Hardware`文件内目前包含两个版本的PCB电路：

* **Naive Version** ：即视频中出现的版本，板载ESP32、IMU、环境光传感器、SD卡槽、下载电路、以及一颗RGB灯
* **Ironman Version** ：基于上面的版本轻微修改，删去了环境光传感器，修改了PCB形状以适配新的外壳

> 因为新款的外壳计划是使用CNC进行金属加工，因此环境光容易被遮挡，而且该功能使用场景不多所以在新版删去了。

**外壳加工** 根据自己喜欢的版本选择，`3D Model`文件夹目前包含四个版本的外壳文件：

* **Naive Version** ：即视频中出现的版本，比较简约（因为临时赶工设计的），最好使用光固化3D打印加工

  ![](/5.Docs/Images/Holo3.png)

* **Bilibili Version** ：视频中后面出现的B站百大奖杯形式的外壳结构，适配`Naive Version`的PCB， **属于娱乐性质，非百大UP不建议采用**。

* **Metal Version** ：视频发布后全新改版的外壳结构设计，优化了布局控件整体更紧凑精致，适配`Naive Version`的PCB，该建议使用CNC加工制作

  ![](/5.Docs/Images/Holo2.jpg)

* **Ironman Version** ：新设计的野生钢铁侠风格结构件，该版本为和朋友合作设计的，后面可能会授权他联名量产，该结构适配`Ironman Version`的PCB

  ![](/5.Docs/Images/Holo.jpg)

> 野生钢铁侠联名的版本的结构件加工比较复杂，而且需要后期喷砂、阳极氧化等工艺所以单件制造成本很高（打听了下整套3个部件至少要1000元+），因此大家自己有加工渠道的可以用提供的文件自己去做。
>
> 没有渠道但是又想要这个版本硬件的，**我授权了那位朋友量产一小批**，他的店铺名为[Xikii](https://shop68240117.taobao.com)，是做客制化键盘很有经验的一个极客，大家感兴趣的可以去关注一下~

## 2. 固件编译说明

维护版使用 PlatformIO，固定依赖版本，支持 `naive` 和 `ironman` 两种环境。Naive 为一颗 RGB 灯，Ironman 为两颗；以实际 PCB 为准。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install platformio==6.1.18
pio run -d 2.Firmware/HoloCubic-fw -e naive
```

使用 Python 3.11 或更新版本。Ironman 将最后的环境名替换为 `ironman`。本版不需要复制 `Libraries`，不需要修改 ESP32 SDK 或 TFT_eSPI；屏幕和 SD 引脚由项目配置。新固件使用 4MB Flash 上的 3MiB 应用分区，首次升级应使用完整 PlatformIO 烧录流程。

完整命令、WiFi 配置、依赖版本、迁移事项和验证范围见 [固件维护说明](2.Firmware/HoloCubic-fw/README.md)。默认显示内置 Logo，提供传感器输入、SD 图片与联网查询基础功能，原视频中的所有应用仍需单独实现或移植。

## 3. 模拟器与图片转换

原 `3.Software/LvglSimulator` 的 Visual Studio 工程和 `HoloTool.exe` 保留作历史参考，使用旧版 LVGL，与当前固件的图片和接口格式不同。维护版通过主机 GUI 回归测试检查 LVGL 9 渲染与输入行为。

新版图片转换器支持 Windows、macOS 和 Linux，要求 Python 3.11 或更新版本：

```sh
python -m pip install -r 3.Software/ImageToHolo/requirements.txt
python 3.Software/ImageToHolo/get_holo.py picture.png
```

默认输出原图旁的 `picture.lv9.bin`，是 LVGL 9 RGB565 格式；复制到 SD 后用 `S:/picture.lv9.bin` 访问。原版图片需要从原图重新生成，供旧固件使用时可加 `--legacy-v7` 输出 `picture.lv7.bin`。更多选项见 `--help`。

## 4. 关于分光棱镜

我用的时25.4mm x 25.4mm x 25.4mm的棱镜，淘宝应该可以搜到，单个价格80元左右。

分光棱镜的固定比较麻烦，用胶水的话容易渗入屏幕导致水印，因此建议去TB搜一下`OCA胶`，这是一种`全贴合屏幕工艺`中用来粘合屏幕的固态胶，效果很不错也很便宜。

> 但是OCA粘性非常强，大家操作一定要仔细不要留气泡，不然粘上后就很难取下了。

## 其他的后续再补充，有用的话记得点星星~

