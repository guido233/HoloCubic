#pragma once

#include <stdint.h>

inline uint32_t display_test_ticks = 0;
inline uint8_t display_test_pwm_pin = 0;
inline uint8_t display_test_pwm_bits = 0;
inline uint32_t display_test_pwm_frequency = 0;
inline uint32_t display_test_pwm_value = 0;

inline unsigned long millis() { return display_test_ticks; }
inline bool ledcAttach(uint8_t pin, uint32_t frequency, uint8_t bits)
{
    display_test_pwm_pin = pin;
    display_test_pwm_frequency = frequency;
    display_test_pwm_bits = bits;
    return true;
}
inline bool ledcWrite(uint8_t pin, uint32_t value)
{
    display_test_pwm_pin = pin;
    display_test_pwm_value = value;
    return true;
}

struct TestSerial
{
    void print(const char*) {}
    void println(const char*) {}
};

inline TestSerial Serial;
