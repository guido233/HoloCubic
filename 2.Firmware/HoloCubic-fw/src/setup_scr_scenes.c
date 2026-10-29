/*
 * Copyright 2021 NXP
 * SPDX-License-Identifier: MIT
 */

#include "gui_guider.h"
#include "lv_cubic_gui.h"

static uint16_t read_le16(const uint8_t* bytes)
{
    return (uint16_t)bytes[0] | ((uint16_t)bytes[1] << 8);
}

static bool valid_scene_file(const char* path)
{
    lv_fs_file_t file;
    if (lv_fs_open(&file, path, LV_FS_MODE_RD) != LV_FS_RES_OK) return false;

    // Accept only the converter's uncompressed, tightly packed v9 RGB565 format.
    // get_info() alone also accepts legacy headers, which can misidentify v7 files.
    uint8_t bytes[12];
    uint32_t count = 0;
    bool valid = lv_fs_read(&file, bytes, sizeof(bytes), &count) == LV_FS_RES_OK && count == sizeof(bytes);
    if (valid)
    {
        const uint16_t width = read_le16(bytes + 4);
        const uint16_t height = read_le16(bytes + 6);
        const uint16_t stride = read_le16(bytes + 8);
        valid = bytes[0] == LV_IMAGE_HEADER_MAGIC && bytes[1] == LV_COLOR_FORMAT_RGB565
            && read_le16(bytes + 2) == 0 && read_le16(bytes + 10) == 0
            && width > 0 && width <= 240 && height > 0 && height <= 240 && stride == width * 2;
        if (valid)
        {
            uint32_t size = 0;
            valid = lv_fs_seek(&file, 0, LV_FS_SEEK_END) == LV_FS_RES_OK
                && lv_fs_tell(&file, &size) == LV_FS_RES_OK
                && size == sizeof(bytes) + (uint32_t)stride * height;
        }
    }
    if (lv_fs_close(&file) != LV_FS_RES_OK) valid = false;
    return valid;
}

void setup_scr_scenes(lv_ui* ui)
{
    ui->scenes = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(ui->scenes, lv_color_black(), LV_PART_MAIN);
    lv_obj_set_scrollable(ui->scenes, false);
    ui->scenes_canvas = lv_image_create(ui->scenes);

    const char* path = "S:/Scenes/Holo3D/frame000.bin";
    lv_image_header_t header;
    if (lv_fs_is_ready('S') && valid_scene_file(path)
        && lv_image_decoder_get_info(path, &header) == LV_RESULT_OK)
        lv_image_set_src(ui->scenes_canvas, path);
    else
        lv_image_set_src(ui->scenes_canvas, &logo);
    lv_obj_center(ui->scenes_canvas);
}
