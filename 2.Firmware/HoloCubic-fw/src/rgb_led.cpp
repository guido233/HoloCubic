#include "rgb_led.h"


void Pixel::init()
{
	if (initialized) return;
	FastLED.addLeds<WS2812, RGB_LED_PIN, GRB>(color_buffers, RGB_LED_NUM);
	FastLED.setBrightness(200);
	initialized = true;
	FastLED.show();
}

Pixel& Pixel::setRGB(int id, int r, int g, int b)
{
	if (id < 0 || id >= RGB_LED_NUM) return *this;
	color_buffers[id] = CRGB(constrain(r, 0, 255), constrain(g, 0, 255), constrain(b, 0, 255));
	if (initialized) FastLED.show();

	return *this;
}

Pixel& Pixel::setBrightness(float duty)
{
	// Treat NaN as off as well as clamping out-of-range brightness.
	if (!(duty > 0.0f)) duty = 0.0f;
	else if (duty > 1.0f) duty = 1.0f;
	FastLED.setBrightness((uint8_t)(255 * duty));
	if (initialized) FastLED.show();

	return *this;
}
