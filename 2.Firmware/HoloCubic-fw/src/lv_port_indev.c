#include "lv_port_indev.h"
#include <stdint.h>

lv_indev_t* indev_encoder;
int32_t encoder_diff = 0;
lv_indev_state_t encoder_state = LV_INDEV_STATE_RELEASED;

static void encoder_read(lv_indev_t* indev, lv_indev_data_t* data)
{
    (void)indev;
    int32_t difference = encoder_diff;
    if (difference > INT16_MAX) difference = INT16_MAX;
    else if (difference < INT16_MIN) difference = INT16_MIN;
    data->enc_diff = (int16_t)difference;
    data->state = encoder_state;
    encoder_diff -= difference;
    data->continue_reading = encoder_diff != 0;
}

void lv_port_indev_init(void)
{
    if (indev_encoder || !lv_display_get_default()) return;
    indev_encoder = lv_indev_create();
    if (!indev_encoder) return;
    lv_indev_set_type(indev_encoder, LV_INDEV_TYPE_ENCODER);
    lv_indev_set_read_cb(indev_encoder, encoder_read);

    lv_group_t* group = lv_group_get_default();
    if (!group)
    {
        group = lv_group_create();
        lv_group_set_default(group);
    }
    lv_indev_set_group(indev_encoder, group);
}
