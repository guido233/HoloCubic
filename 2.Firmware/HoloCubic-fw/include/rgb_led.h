#ifndef RGB_H
#define RGB_H

#include <FastLED.h>

#ifndef RGB_LED_NUM
// Original default: two LEDs. Use -DRGB_LED_NUM=1 for the Naive main board.
#define RGB_LED_NUM 2
#endif
#ifndef RGB_LED_PIN
#define RGB_LED_PIN 27
#endif

static_assert(RGB_LED_NUM > 0, "RGB_LED_NUM must be positive");


class Pixel
{
private:
	CRGB color_buffers[RGB_LED_NUM] = {};
	bool initialized = false;

public:
	void init();

	Pixel& setRGB(int id, int r, int g, int b);
	Pixel& setBrightness(float duty);
};

#endif
