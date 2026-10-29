#include "gui_guider.h"

void setup_ui(lv_ui* ui)
{
    setup_scr_home(ui);
    setup_scr_scenes(ui);
    // Preserve the original example's final scene. Load ui->home to try the hue control.
    lv_screen_load(ui->scenes);
}
