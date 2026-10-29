/*
 * Copyright 2021 NXP
 * SPDX-License-Identifier: MIT
 */

#include "gui_guider.h"

static void hue_changed(lv_event_t* event)
{
    lv_ui* ui = lv_event_get_user_data(event);
    const int32_t hue = lv_slider_get_value(ui->home_hue);
    lv_obj_set_style_bg_color(ui->home_preview, lv_color_hsv_to_rgb((uint16_t)hue, 100, 100), LV_PART_MAIN);
    lv_label_set_text_fmt(ui->home_label, "Hue:%d", (int)hue);
}

void setup_scr_home(lv_ui* ui)
{
    ui->home = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(ui->home, lv_color_black(), LV_PART_MAIN);
    lv_obj_set_style_text_color(ui->home, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_scrollable(ui->home, false);

    // LVGL 9 removed cpicker. An encoder-friendly hue slider retains the color preview example.
    ui->home_preview = lv_obj_create(ui->home);
    lv_obj_set_pos(ui->home_preview, 20, 16);
    lv_obj_set_size(ui->home_preview, 200, 120);
    lv_obj_set_style_border_width(ui->home_preview, 0, LV_PART_MAIN);
    lv_obj_set_style_bg_color(ui->home_preview, lv_color_hsv_to_rgb(200, 100, 100), LV_PART_MAIN);
    lv_obj_set_scrollable(ui->home_preview, false);

    ui->home_label = lv_label_create(ui->home);
    lv_obj_set_style_text_font(ui->home_label, &lv_font_simsun_12, LV_PART_MAIN);
    lv_label_set_text(ui->home_label, "Hue:200");
    lv_obj_align(ui->home_label, LV_ALIGN_TOP_MID, 0, 148);

    ui->home_hue = lv_slider_create(ui->home);
    lv_obj_set_pos(ui->home_hue, 30, 184);
    lv_obj_set_size(ui->home_hue, 180, 12);
    lv_slider_set_range(ui->home_hue, 0, 359);
    lv_slider_set_value(ui->home_hue, 200, LV_ANIM_OFF);
    lv_obj_add_event_cb(ui->home_hue, hue_changed, LV_EVENT_VALUE_CHANGED, ui);
    if (lv_group_get_default()) lv_group_add_obj(lv_group_get_default(), ui->home_hue);
}
