#ifndef LV_PORT_FATFS_H
#define LV_PORT_FATFS_H

#ifdef __cplusplus
extern "C" {
#endif

// Register Arduino SD as LVGL drive S:. Call after lv_init().
void lv_fs_if_init(void);

#ifdef __cplusplus
}
#endif

#endif
