#ifndef LV_PORT_INDEV_H
#define LV_PORT_INDEV_H

#include "lvgl.h"

#ifdef __cplusplus
extern "C" {
#endif

extern lv_indev_t* indev_encoder;
extern int32_t encoder_diff;
extern lv_indev_state_t encoder_state;

void lv_port_indev_init(void);

#ifdef __cplusplus
}
#endif

#endif
