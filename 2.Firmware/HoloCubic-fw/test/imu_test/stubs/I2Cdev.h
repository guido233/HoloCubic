#pragma once

#include "Arduino.h"

struct TestWire
{
    bool begin_result = true;
    uint16_t timeout = 0;
    bool begin(int, int) { return begin_result; }
    void setClock(uint32_t) {}
    void setTimeOut(uint16_t value) { timeout = value; }
};

extern TestWire Wire;

struct I2Cdev
{
    static int8_t readByte(uint8_t, uint8_t, uint8_t*, uint16_t);
    static int8_t readBytes(uint8_t, uint8_t, uint8_t, uint8_t*, uint16_t);
};
