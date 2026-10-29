#include "display.h"
#include <Arduino.h>
#include <TFT_eSPI.h>

namespace
{
constexpr uint32_t screen_width = 240;
constexpr uint32_t screen_height = 240;
constexpr uint32_t buffer_rows = screen_height / 10;
static_assert(LV_COLOR_FORMAT_DEFAULT == LV_COLOR_FORMAT_RGB565, "HoloCubic requires RGB565 rendering");

TFT_eSPI tft;
alignas(LV_DRAW_BUF_ALIGN) uint8_t draw_buffer[screen_width * buffer_rows * sizeof(uint16_t)];

uint32_t tickMillis()
{
    return static_cast<uint32_t>(millis());
}

#if LV_USE_LOG
void printLog(lv_log_level_t level, const char* message)
{
    (void)level;
    Serial.print(message);
}
#endif

void flushDisplay(lv_display_t* display, const lv_area_t* area, uint8_t* pixels)
{
    const uint32_t width = static_cast<uint32_t>(lv_area_get_width(area));
    const uint32_t height = static_cast<uint32_t>(lv_area_get_height(area));
    tft.startWrite();
    tft.setAddrWindow(area->x1, area->y1, width, height);
    // LVGL renders native RGB565; the ST7789 SPI stream requires high byte first.
    tft.pushColors(reinterpret_cast<uint16_t*>(pixels), width * height, true);
    tft.endWrite();
    lv_display_flush_ready(display);
}
}

void Display::init()
{
    if (display) return;
    backlight_ready = ledcAttach(LCD_BL_PIN, 5000, 8);
    if (backlight_ready) ledcWrite(LCD_BL_PIN, 255); // Active-low backlight: start off.
    else Serial.println("Backlight PWM initialization failed");

    if (!lv_is_initialized()) lv_init();
    lv_tick_set_cb(tickMillis);
#if LV_USE_LOG
    lv_log_register_print_cb(printLog);
#endif

    tft.begin(); // Pins and the ST7789 driver are configured in tft_setup.h.
    // TFT_eSPI 2.5.43 folds rotation 4 back to 0. Reapply the original
    // vendor driver's case-4 MADCTL setting explicitly for the beam-splitter mirror.
    tft.setRotation(0);
    tft.writecommand(TFT_MADCTL);
    tft.writedata(TFT_MAD_MX | TFT_MAD_COLOR_ORDER);

    display = lv_display_create(screen_width, screen_height);
    if (!display)
    {
        Serial.println("LVGL display allocation failed");
        return;
    }
    lv_display_set_color_format(display, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(display, draw_buffer, nullptr, sizeof(draw_buffer), LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(display, flushDisplay);
}

void Display::routine()
{
    if (display) lv_timer_handler();
}

void Display::setBackLight(float duty)
{
    if (!(duty > 0.0f)) duty = 0.0f;
    else if (duty > 1.0f) duty = 1.0f;
    if (backlight_ready) ledcWrite(LCD_BL_PIN, static_cast<uint32_t>((1.0f - duty) * 255.0f));
}
