#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>

#include "imu.h"
#include "rgb_led.h"

uint32_t test_millis = 0;
TestWire Wire;
TestFastLED FastLED;
int test_initializations = 0;
int32_t encoder_diff = 0;
lv_indev_state_t encoder_state = LV_INDEV_STATE_RELEASED;

namespace
{
bool connected = false;
uint8_t identity = 0x68;
int motion_reads = 0;
int8_t motion_size = 14;
uint8_t motion[14] = {};

void setAxis(int offset, int16_t value)
{
    motion[offset] = static_cast<uint16_t>(value) >> 8;
    motion[offset + 1] = static_cast<uint16_t>(value) & 0xff;
}

void assertZero(const IMU& sensor)
{
    assert(sensor.getAccelX() == 0 && sensor.getAccelY() == 0 && sensor.getAccelZ() == 0);
    assert(sensor.getGyroX() == 0 && sensor.getGyroY() == 0 && sensor.getGyroZ() == 0);
}
}

int8_t I2Cdev::readByte(uint8_t, uint8_t, uint8_t* data, uint16_t)
{
    if (!connected) return 0;
    *data = identity;
    return 1;
}

int8_t I2Cdev::readBytes(uint8_t, uint8_t, uint8_t length, uint8_t* data, uint16_t)
{
    ++motion_reads;
    if (motion_size > 0) std::memcpy(data, motion, motion_size < length ? motion_size : length);
    return motion_size;
}

int main()
{
    IMU sensor;
    assert(!sensor.isReady());
    assertZero(sensor);

    // Missing hardware has a bounded startup and never produces input or stale motion.
    encoder_diff = 7;
    encoder_state = LV_INDEV_STATE_PRESSED;
    assert(!sensor.init(25));
    assert(test_millis == 25);
    assert(!sensor.isReady() && test_initializations == 0);
    assert(encoder_diff == 0 && encoder_state == LV_INDEV_STATE_RELEASED);
    sensor.update(0);
    assert(motion_reads == 0);
    assertZero(sensor);

    // An unexpected WHO_AM_I or failed I2C controller also fails without blocking.
    connected = true;
    identity = 0;
    assert(!sensor.init(0));
    assert(test_millis == 25);
    identity = 0x68;
    Wire.begin_result = false;
    assert(!sensor.init());
    Wire.begin_result = true;

    setAxis(0, 12001);
    setAxis(2, -4000);
    setAxis(4, -32768);
    setAxis(8, 32767);
    setAxis(10, -1);
    setAxis(12, 42);
    test_millis = UINT32_MAX - 100;
    assert(sensor.init(0));
    assert(sensor.isReady() && Wire.timeout > 0);
    assert(sensor.getAccelZ() == -32768 && sensor.getGyroX() == 32767);
    assert(sensor.getGyroY() == -1 && sensor.getGyroZ() == 42);

    // Sampling is throttled even when millis() wraps after about 49 days.
    const int reads_after_init = motion_reads;
    test_millis = 98; // 199 ms later
    sensor.update(200);
    assert(motion_reads == reads_after_init);
    assert(encoder_diff == 0 && encoder_state == LV_INDEV_STATE_RELEASED);
    test_millis = 99; // exactly 200 ms later
    sensor.update(200);
    assert(motion_reads == reads_after_init + 1);
    assert(encoder_diff == 1 && encoder_state == LV_INDEV_STATE_PRESSED);

    // A partial transaction releases a pressed input and clears all six cached axes.
    motion_size = 6;
    test_millis += 200;
    sensor.update(200);
    assert(!sensor.isReady());
    assertZero(sensor);
    assert(encoder_diff == 0 && encoder_state == LV_INDEV_STATE_RELEASED);
    const int reads_after_failure = motion_reads;
    sensor.update(0);
    assert(motion_reads == reads_after_failure);
    motion_size = 14;
    assert(sensor.init(0)); // Caller can explicitly recover after repairing the sensor.

    Pixel pixels;
    pixels.init();
    pixels.init();
    assert(FastLED.registrations == 1 && FastLED.count == RGB_LED_NUM);
    for (int index = 0; index < RGB_LED_NUM; ++index)
        assert(FastLED.pixels[index].r == 0 && FastLED.pixels[index].g == 0 && FastLED.pixels[index].b == 0);

    const int shows_after_init = FastLED.shows;
    pixels.setRGB(-1, 255, 255, 255).setRGB(RGB_LED_NUM, 255, 255, 255);
    assert(FastLED.shows == shows_after_init);
    pixels.setRGB(0, -20, 256, 17);
    assert(FastLED.pixels[0].r == 0 && FastLED.pixels[0].g == 255 && FastLED.pixels[0].b == 17);
    // The original main calls both indices; this must also be safe for the one-LED board.
    pixels.setRGB(0, 0, 122, 204).setRGB(1, 0, 122, 204);
    pixels.setBrightness(-1.0f);
    assert(FastLED.brightness == 0);
    pixels.setBrightness(2.0f);
    assert(FastLED.brightness == 255);
    pixels.setBrightness(std::numeric_limits<float>::quiet_NaN());
    assert(FastLED.brightness == 0);

    std::cout << "IMU timeout, rollover, I2C failure and RGB bounds passed (" << RGB_LED_NUM << " LED(s))\n";
}
