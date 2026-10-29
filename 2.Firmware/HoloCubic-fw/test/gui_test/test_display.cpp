#include <cassert>
#include <limits>
#include <Arduino.h>
#include <TFT_eSPI.h>
#include "display.h"

extern "C" void test_display_driver(void)
{
    Display screen;
    screen.init();
    assert(lv_display_get_default());
    assert(display_test_tft && display_test_tft->_width == 240 && display_test_tft->_height == 240);

    // The original HoloCubic driver used 0x36 / 0x48 (MX | BGR) for rotation 4.
    // The new dependency's modulo-four rotation alone would produce 0x08 and fail here.
    const auto& operations = display_test_tft->operations;
    assert(operations.size() >= 2);
    assert(operations[operations.size() - 2].command);
    assert(operations[operations.size() - 2].value == 0x36);
    assert(!operations.back().command && operations.back().value == 0x48);
    assert(display_test_tft->rotation == 0);

    assert(display_test_pwm_pin == LCD_BL_PIN);
    assert(display_test_pwm_bits == 8 && display_test_pwm_frequency == 5000);
    assert(display_test_pwm_value == 255);
    screen.setBackLight(1.0f);
    assert(display_test_pwm_pin == LCD_BL_PIN && display_test_pwm_value == 0);
    screen.setBackLight(0.0f);
    assert(display_test_pwm_value == 255);
    screen.setBackLight(std::numeric_limits<float>::quiet_NaN());
    assert(display_test_pwm_value == 255);
    display_test_ticks = 1234;
    assert(lv_tick_get() == 1234);

    lv_display_delete(lv_display_get_default());
}
