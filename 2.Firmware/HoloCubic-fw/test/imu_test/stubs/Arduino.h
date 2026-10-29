#pragma once

#include <stdint.h>

extern uint32_t test_millis;

inline unsigned long millis() { return test_millis; }
inline void delay(unsigned long duration) { test_millis += static_cast<uint32_t>(duration); }

template <typename T>
T constrain(T value, T low, T high)
{
    return value < low ? low : (value > high ? high : value);
}
