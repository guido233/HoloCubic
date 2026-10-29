#pragma once

#include <stdint.h>
#include <vector>
#include "tft_setup.h"
#include <TFT_Drivers/ST7789_Defines.h>

class TFT_eSPI;
inline TFT_eSPI* display_test_tft = nullptr;

class TFT_eSPI
{
public:
    struct Operation { bool command; uint8_t value; };
    std::vector<Operation> operations;
    int rotation = 0;
    int colstart = 0, rowstart = 0;
    int _width = TFT_WIDTH, _height = TFT_HEIGHT;
    int _init_width = TFT_WIDTH, _init_height = TFT_HEIGHT;

    TFT_eSPI() { display_test_tft = this; }
    void begin() {}
    void writecommand(uint8_t value) { operations.push_back({true, value}); }
    void writedata(uint8_t value) { operations.push_back({false, value}); }
    void setRotation(uint8_t m)
    {
        // Execute the actual pinned driver's rotation sequence, rather than duplicating it.
#include <TFT_Drivers/ST7789_Rotation.h>
    }
    void startWrite() {}
    void setAddrWindow(int32_t, int32_t, uint32_t, uint32_t) {}
    void pushColors(uint16_t*, uint32_t, bool) {}
    void endWrite() {}
};
