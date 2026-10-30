#ifndef HOLOCUBIC_TFT_SETUP_H
#define HOLOCUBIC_TFT_SETUP_H

// Project-owned configuration: do not edit the installed TFT_eSPI library.
#define USER_SETUP_LOADED
#define ST7789_DRIVER
#define TFT_WIDTH 240
#define TFT_HEIGHT 240
#define TFT_MISO 19
#define TFT_MOSI 23
#define TFT_SCLK 18
#define TFT_CS -1
#define TFT_DC 2
#define TFT_RST 4
// ST7789V v1.3 Table 6: write cycle >=66ns, clock high/low >=15ns.
// Use 10MHz for the shared ST7789 configuration until the exact panel,
// interconnect and receiver waveforms qualify a higher write clock.
#define SPI_FREQUENCY 10000000
#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_FONT8
#define LOAD_GFXFF
#define SMOOTH_FONT

#endif
