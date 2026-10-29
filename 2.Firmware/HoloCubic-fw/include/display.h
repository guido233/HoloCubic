#ifndef DISPLAY_H
#define DISPLAY_H

#include <lvgl.h>

#define LCD_BL_PIN 5

class Display
{
private:
    lv_display_t* display = nullptr;
    bool backlight_ready = false;

public:
    void init();
    void routine();
    void setBackLight(float duty);
};

#endif
