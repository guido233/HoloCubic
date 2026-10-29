#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "gui_guider.h"
#include "lv_cubic_gui.h"
#include "lv_port_indev.h"

static uint32_t test_ticks;
static uint32_t flushes;
static uint32_t warnings;
void test_display_driver(void);
static uint16_t framebuffer[240 * 240];
_Alignas(LV_DRAW_BUF_ALIGN) static uint8_t draw_buffer[240 * 24 * 2];

typedef struct { const uint8_t* data; uint32_t size, offset; } memory_file_t;
static const uint8_t* asset_data;
static uint32_t asset_size;

static bool asset_ready(lv_fs_drv_t* driver)
{
    (void)driver;
    return true;
}

static void* asset_open(lv_fs_drv_t* driver, const char* path, lv_fs_mode_t mode)
{
    (void)driver;
    if (strcmp(path, "/Scenes/Holo3D/frame000.bin") != 0 || mode != LV_FS_MODE_RD || !asset_data) return NULL;
    memory_file_t* file = malloc(sizeof(*file));
    assert(file);
    *file = (memory_file_t){asset_data, asset_size, 0};
    return file;
}

static lv_fs_res_t asset_close(lv_fs_drv_t* driver, void* handle)
{
    (void)driver;
    free(handle);
    return LV_FS_RES_OK;
}

static lv_fs_res_t asset_read(lv_fs_drv_t* driver, void* handle, void* buffer, uint32_t requested, uint32_t* read)
{
    (void)driver;
    memory_file_t* file = handle;
    *read = requested < file->size - file->offset ? requested : file->size - file->offset;
    memcpy(buffer, file->data + file->offset, *read);
    file->offset += *read;
    return LV_FS_RES_OK;
}

static lv_fs_res_t asset_seek(lv_fs_drv_t* driver, void* handle, uint32_t offset, lv_fs_whence_t whence)
{
    (void)driver;
    memory_file_t* file = handle;
    uint64_t target = offset;
    if (whence == LV_FS_SEEK_CUR) target += file->offset;
    else if (whence == LV_FS_SEEK_END) target += file->size;
    if (target > file->size) return LV_FS_RES_INV_PARAM;
    file->offset = (uint32_t)target;
    return LV_FS_RES_OK;
}

static lv_fs_res_t asset_tell(lv_fs_drv_t* driver, void* handle, uint32_t* offset)
{
    (void)driver;
    *offset = ((memory_file_t*)handle)->offset;
    return LV_FS_RES_OK;
}

static void test_scene_files(lv_display_t* display, lv_obj_t* return_screen)
{
    static lv_fs_drv_t driver;
    lv_fs_drv_init(&driver);
    driver.letter = 'S';
    driver.ready_cb = asset_ready;
    driver.open_cb = asset_open;
    driver.close_cb = asset_close;
    driver.read_cb = asset_read;
    driver.seek_cb = asset_seek;
    driver.tell_cb = asset_tell;
    lv_fs_drv_register(&driver);

    // Legacy v7 headers and truncated v9 data must select the built-in logo.
    static const uint8_t legacy_v7[] = {8, 0, 0x3c, 0x78, 4, 2, 4, 255, 0, 0, 0, 0, 0, 0, 0, 0};
    static const uint8_t truncated_v9[] = {0x19, 0x12, 0, 0, 240, 0, 240, 0, 0xe0, 1, 0, 0, 0, 0};
    static const uint8_t invalid_stride[] = {0x19, 0x12, 0, 0, 2, 0, 2, 0, 6, 0, 0, 0, 0, 0};
    const uint8_t* invalid[] = {legacy_v7, truncated_v9, invalid_stride};
    const uint32_t lengths[] = {sizeof(legacy_v7), sizeof(truncated_v9), sizeof(invalid_stride)};
    for (size_t index = 0; index < sizeof(invalid) / sizeof(invalid[0]); ++index)
    {
        asset_data = invalid[index];
        asset_size = lengths[index];
        lv_ui candidate = {0};
        setup_scr_scenes(&candidate);
        assert(lv_image_get_src(candidate.scenes_canvas) == &logo);
        lv_screen_load(candidate.scenes);
        lv_refr_now(display);
        lv_screen_load(return_screen);
        lv_obj_delete(candidate.scenes);
    }

    // A complete converter-format RGB565 image is accepted and rendered from the filesystem.
    static const uint8_t valid_v9[] = {
        0x19, 0x12, 0, 0, 2, 0, 2, 0, 4, 0, 0, 0,
        0x00, 0xf8, 0xe0, 0x07, 0x1f, 0x00, 0xff, 0xff
    };
    asset_data = valid_v9;
    asset_size = sizeof(valid_v9);
    lv_ui candidate = {0};
    setup_scr_scenes(&candidate);
    assert(lv_image_get_src(candidate.scenes_canvas) != &logo);
    lv_screen_load(candidate.scenes);
    lv_refr_now(display);
    assert(framebuffer[119 * 240 + 119] == 0xf800);
    assert(framebuffer[119 * 240 + 120] == 0x07e0);
    assert(framebuffer[120 * 240 + 119] == 0x001f);
    assert(framebuffer[120 * 240 + 120] == 0xffff);
    lv_screen_load(return_screen);
    lv_obj_delete(candidate.scenes);
}

static uint32_t ticks(void)
{
    return test_ticks;
}

static void log_message(lv_log_level_t level, const char* message)
{
    if (level >= LV_LOG_LEVEL_WARN) ++warnings;
    fputs(message, stderr);
}

static void flush(lv_display_t* display, const lv_area_t* area, uint8_t* pixels)
{
    const int32_t width = lv_area_get_width(area);
    const int32_t height = lv_area_get_height(area);
    assert(area->x1 >= 0 && area->y1 >= 0 && area->x2 < 240 && area->y2 < 240);
    for (int32_t row = 0; row < height; ++row)
        memcpy(&framebuffer[(area->y1 + row) * 240 + area->x1], pixels + row * width * 2, width * 2);
    ++flushes;
    lv_display_flush_ready(display);
}

static void assert_logo_pixels(void)
{
    // Compare the real LVGL decoder/render output against every original palette index.
    // This also checks that the 240x240 logo fits the configured heap when decoded by scanline.
    assert(logo.header.cf == LV_COLOR_FORMAT_I2 && logo.header.stride == 60);
    assert(logo.header.w == 240 && logo.header.h == 240 && logo.data_size == 14416);
    for (uint32_t y = 0; y < 240; ++y)
        for (uint32_t x = 0; x < 240; ++x)
        {
            const uint8_t packed = logo.data[16 + y * 60 + x / 4];
            const uint8_t index = (packed >> (6 - (x % 4) * 2)) & 3;
            const uint8_t* color = &logo.data[index * 4];
            assert(color[3] == 255);
            const uint16_t expected = lv_color_to_u16(lv_color_make(color[2], color[1], color[0]));
            assert(framebuffer[y * 240 + x] == expected);
        }
}

int main(void)
{
    lv_init();
    test_display_driver();
    lv_tick_set_cb(ticks);
    lv_log_register_print_cb(log_message);
    lv_display_t* display = lv_display_create(240, 240);
    assert(display);
    lv_display_set_color_format(display, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(display, draw_buffer, NULL, sizeof(draw_buffer), LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(display, flush);
    lv_port_indev_init();
    assert(indev_encoder && lv_indev_get_group(indev_encoder));

    lv_holo_cubic_gui();
    lv_refr_now(display);

    assert(flushes > 0);
    assert_logo_pixels();

    // No SD filesystem is registered. The example scene still renders its built-in fallback.
    lv_ui ui = {0};
    setup_ui(&ui);
    assert(lv_image_get_src(ui.scenes_canvas) == &logo);
    lv_refr_now(display);
    assert_logo_pixels();

    // The migrated custom bitmap font must supply both metrics and actual bitmap data.
    const char* characters = "Hue:200";
    while (*characters)
    {
        lv_font_glyph_dsc_t glyph = {0};
        assert(lv_font_get_glyph_dsc(&lv_font_simsun_12, &glyph, (uint32_t)*characters++, 0));
        assert(glyph.box_h > 0 && lv_font_get_glyph_static_bitmap(&glyph));
        lv_font_glyph_release_draw_data(&glyph);
    }

    lv_screen_load(ui.home);
    lv_group_t* group = lv_indev_get_group(indev_encoder);
    lv_group_focus_obj(ui.home_hue);
    lv_group_set_editing(group, true);
    assert(lv_slider_get_value(ui.home_hue) == 200);
    encoder_diff = 1;
    test_ticks += 200;
    lv_indev_read(indev_encoder);
    assert(encoder_diff == 0 && lv_slider_get_value(ui.home_hue) == 201);
    assert(strcmp(lv_label_get_text(ui.home_label), "Hue:201") == 0);
    lv_refr_now(display);

    test_scene_files(display, ui.home);

    lv_mem_monitor_t memory;
    lv_mem_monitor(&memory);
    assert(memory.total_size <= LV_MEM_SIZE);
    assert(warnings == 0);
    printf("LVGL 9: ST7789 mirror command, PWM/tick, original logo pixels, configured heap, legacy/truncated image fallback, RGB565 file decoding, custom font and encoder hue control passed\n");
    printf("LVGL heap: %zu bytes total, %zu bytes free\n", memory.total_size, memory.free_size);
    lv_deinit();
    return 0;
}
