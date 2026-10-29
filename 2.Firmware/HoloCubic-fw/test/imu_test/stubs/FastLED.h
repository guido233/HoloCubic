#pragma once

#include "Arduino.h"

struct CRGB
{
    uint8_t r = 0, g = 0, b = 0;
    CRGB() = default;
    CRGB(uint8_t red, uint8_t green, uint8_t blue) : r(red), g(green), b(blue) {}
};

struct WS2812 {};
constexpr uint8_t GRB = 0;

struct TestFastLED
{
    CRGB* pixels = nullptr;
    int count = 0;
    int registrations = 0;
    int shows = 0;
    uint8_t brightness = 0;

    template <typename Chipset, uint8_t Pin, uint8_t Order>
    void addLeds(CRGB* data, int length)
    {
        pixels = data;
        count = length;
        ++registrations;
    }
    void setBrightness(uint8_t value) { brightness = value; }
    void show() { ++shows; }
};

extern TestFastLED FastLED;
