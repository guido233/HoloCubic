#include <Arduino.h>
#include "display.h"
#include "imu.h"
#include "holo_network.h"
#include "sd_card.h"
#include "rgb_led.h"
#include "lv_port_indev.h"
#include "lv_port_fatfs.h"
#include "lv_cubic_gui.h"
#include "gui_guider.h"

Display screen;
IMU mpu;
Pixel rgb;
SdCard tf;
HoloNetwork wifi;
lv_ui guider_ui;

static void connectFromSd()
{
    String ssid;
    String password;
    if (!tf.isMounted() || !tf.readFileLine("/wifi.txt", 1, ssid) ||
        !tf.readFileLine("/wifi.txt", 2, password) || ssid.isEmpty()) {
        Serial.println("No WiFi configuration; continuing offline.");
        return;
    }

    if (!wifi.init(ssid, password)) {
        Serial.printf("WiFi connection failed (%u); continuing offline.\n",
                      static_cast<unsigned>(wifi.lastError()));
        return;
    }

    // Optional third line: a Bilibili UID. No request is made without it.
    String uid;
    if (tf.readFileLine("/wifi.txt", 3, uid)) {
        uid.trim();
        if (!uid.isEmpty()) {
            uint32_t fans = 0;
            if (wifi.getBilibiliFans(uid, fans)) {
                Serial.printf("Bilibili followers: %lu\n", static_cast<unsigned long>(fans));
            } else {
                Serial.printf("Follower request failed (%u).\n",
                              static_cast<unsigned>(wifi.lastError()));
            }
        }
    }
}

void setup()
{
    Serial.begin(115200);
    screen.init();
    screen.setBackLight(0.2f);
    lv_port_indev_init();
    lv_holo_cubic_gui();
    lv_refr_now(nullptr);

    if (!mpu.init()) {
        Serial.println("IMU unavailable; display will run without gesture input.");
    }
    rgb.init();
    rgb.setBrightness(0.1f);
    for (int i = 0; i < RGB_LED_NUM; ++i) {
        rgb.setRGB(i, 0, 122, 204);
    }

    if (!tf.init()) {
        Serial.println("SD unavailable; using built-in resources.");
    }
    lv_fs_if_init();
    connectFromSd();
}

void loop()
{
    mpu.update(200);
    screen.routine();
    delay(5);
}
