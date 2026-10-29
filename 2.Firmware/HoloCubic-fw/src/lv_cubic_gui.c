#include "lv_cubic_gui.h"
#include "images.h"

void lv_holo_cubic_gui(void)
{
    lv_obj_t* screen = lv_screen_active();
    if (!screen) return;
    lv_obj_clean(screen);
    lv_obj_set_style_bg_color(screen, lv_color_black(), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_scrollable(screen, false);
    lv_obj_t* image = lv_image_create(screen);
    lv_image_set_src(image, &logo);
    lv_obj_center(image);
}
