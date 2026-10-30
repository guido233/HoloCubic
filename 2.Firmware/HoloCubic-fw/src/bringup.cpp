// Opt-in first-article diagnostics. Normal firmware compiles an empty unit.
#ifdef HOLOCUBIC_BRINGUP
#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <SD.h>
#include <SPI.h>
#include <TFT_eSPI.h>
#include <FastLED.h>
#include <esp_system.h>
#include <driver/gpio.h>
#include <string.h>

namespace {
constexpr int backlightPin = 5;
constexpr char scratchPath[] = "/holocubic-bringup.bin";
constexpr uint32_t scratchBytes = 65536;
SPIClass cardSpi(HSPI);
TFT_eSPI panel;
CRGB pixel[1];
bool pwmReady = false, displayReady = false, cardReady = false;
char line[96] = {};
size_t used = 0;
bool overflow = false;

void help() {
    Serial.println("Naive RevB BRINGUP / 115200 baud / LF commands:");
    Serial.println("status | i2c | display | backlight 0..100 | rgb");
    Serial.println("sd-status | sd-test | wifi-scan | wifi-load | help");
    Serial.println("sd-test creates, verifies and removes a NEW 64KiB scratch file.");
    Serial.println("wifi-load reads /wifi.txt lines1/2, connects for 10s while");
    Serial.println("reading SD/displaying; no HTTP requests or credential logging.");
    Serial.println("No automated command verifies assembly, supply waveforms,");
    Serial.println("backlight current/temperature or antenna matching.");
}

void status() {
    Serial.printf("BRINGUP chip=%s rev=%u flash_bytes=%lu sdk=%s reset_reason=%d\n",
        ESP.getChipModel(), ESP.getChipRevision(),
        static_cast<unsigned long>(ESP.getFlashChipSize()), ESP.getSdkVersion(),
        static_cast<int>(esp_reset_reason()));
    Serial.printf("CONFIG TFT_Hz=%lu SD_Hz=4000000 RGB=GPIO27 BL=GPIO5 active_low\n",
        static_cast<unsigned long>(SPI_FREQUENCY));
    Serial.println("EXTERNAL assembly/power_scope/thermal/RF=UNVERIFIED");
}

bool readRegister(uint8_t address, uint8_t reg, uint8_t *data, size_t count) {
    Wire.beginTransmission(address);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(address, count) != count) return false;
    for (size_t i = 0; i < count; ++i) data[i] = Wire.read();
    return true;
}

void sensors() {
    uint8_t identity = 0, data[14] = {};
    bool imu = readRegister(0x68, 0x75, &identity, 1) && (identity & 0x7e) == 0x68;
    if (imu) {
        Wire.beginTransmission(0x68); Wire.write(0x6b); Wire.write(0x01);
        imu = Wire.endTransmission() == 0;
        delay(20);
        imu = imu && readRegister(0x68, 0x3b, data, sizeof(data));
    }
    Serial.printf("RESULT imu_read=%s who_am_i=0x%02x\n", imu ? "PASS" : "FAIL", identity);
    if (imu) {
        Serial.print("IMU raw accel_xyz/temperature/gyro_xyz:");
        for (size_t i = 0; i < sizeof(data); i += 2)
            Serial.printf(" %d", static_cast<int16_t>((data[i] << 8) | data[i+1]));
        Serial.println();
    }
    Wire.beginTransmission(0x23); Wire.write(0x20);
    bool light = Wire.endTransmission() == 0;
    delay(180);
    light = light && Wire.requestFrom(static_cast<uint8_t>(0x23), static_cast<size_t>(2)) == 2;
    uint16_t raw = 0;
    if (light) {
        const uint8_t high = Wire.read(), low = Wire.read();
        raw = (static_cast<uint16_t>(high) << 8) | low;
    }
    Serial.printf("RESULT als_read=%s raw=%u; vary light and repeat; calibration unverified\n",
        light ? "PASS" : "FAIL", raw);
}

bool mountCard() {
    if (cardReady) return true;
    SD.end(); cardSpi.end();
    if (!cardSpi.begin(14, 26, 13, 15)) {
        cardSpi.end(); Serial.println("RESULT sd_mount=FAIL bus"); return false;
    }
    cardReady = SD.begin(15, cardSpi, 4000000) && SD.cardType() != CARD_NONE;
    if (!cardReady) { SD.end(); cardSpi.end(); }
    Serial.printf("RESULT sd_mount=%s\n", cardReady ? "PASS" : "FAIL");
    return cardReady;
}

void pattern(uint8_t *data, size_t block) {
    for (size_t i = 0; i < 256; ++i) data[i] = ((block * 31u + i * 17u) ^ 0xa5u) & 255u;
}

void cardTest() {
    if (!mountCard()) return;
    if (SD.exists(scratchPath)) {
        Serial.println("RESULT sd_rw=REFUSED existing scratch file; no files changed"); return;
    }
    uint8_t expected[256], actual[256];
    File file = SD.open(scratchPath, FILE_WRITE);
    if (!file) { Serial.println("RESULT sd_rw=FAIL create"); return; }
    bool ok = true;
    for (size_t b = 0; b < scratchBytes / sizeof(expected); ++b) {
        pattern(expected, b);
        if (file.write(expected, sizeof(expected)) != sizeof(expected)) { ok = false; break; }
    }
    file.flush(); file.close();
    file = SD.open(scratchPath, FILE_READ);
    ok = ok && file && file.size() == scratchBytes;
    for (size_t b = 0; ok && b < scratchBytes / sizeof(expected); ++b) {
        pattern(expected, b);
        ok = file.read(actual, sizeof(actual)) == sizeof(actual) &&
             memcmp(expected, actual, sizeof(actual)) == 0;
    }
    file.close();
    const bool removed = SD.remove(scratchPath); // This invocation created it.
    Serial.printf("RESULT sd_rw=%s bytes=%lu cleanup=%s\n", ok && removed ? "PASS" : "FAIL",
        static_cast<unsigned long>(scratchBytes), removed ? "PASS" : "FAIL");
}

void drawPattern(uint32_t frame = 0) {
    if (!displayReady) {
        panel.begin(); panel.setRotation(0);
        panel.writecommand(TFT_MADCTL);
        panel.writedata(TFT_MAD_MX | TFT_MAD_COLOR_ORDER);
        displayReady = true;
    }
    const uint16_t colors[3] = {TFT_RED, TFT_GREEN, TFT_BLUE};
    for (int i = 0; i < 3; ++i) panel.fillRect(i*80, 0, 80, 240, colors[(i+frame)%3]);
    panel.setTextColor(TFT_WHITE, TFT_BLACK); panel.setTextFont(2);
    panel.drawString("TL 1", 2, 2); panel.drawString("TR 2", 198, 2);
    panel.drawString("BL 3", 2, 218); panel.drawString("BR 4", 198, 218);
    panel.drawString("Naive / 10MHz", 52, 105);
}

bool backlight(const char *argument) {
    char *end = nullptr;
    const long percent = strtol(argument, &end, 10);
    if (end == argument || *end || percent < 0 || percent > 100) return false;
    if (!pwmReady && percent == 0) return gpio_set_level(GPIO_NUM_5, 1) == ESP_OK;
    if (!pwmReady) pwmReady = ledcAttach(backlightPin, 5000, 8);
    if (!pwmReady) return false;
    return ledcWrite(backlightPin, 255u - (255u * static_cast<unsigned>(percent) / 100u));
}

void wifiScan() {
    WiFi.persistent(false); WiFi.mode(WIFI_STA);
    const int count = WiFi.scanNetworks(false, false);
    int strongest = -127;
    for (int i = 0; i < count; ++i) strongest = max(strongest, WiFi.RSSI(i));
    Serial.printf("RESULT wifi_scan_api=%s networks=%d strongest_dBm=%d\n",
        count >= 0 ? "PASS" : "FAIL", count, strongest);
    Serial.println("Scan API success alone does not establish RF performance.");
    WiFi.scanDelete(); WiFi.disconnect(true, false);
}

void wifiLoad() {
    if (!mountCard()) return;
    File credentials = SD.open("/wifi.txt", FILE_READ);
    if (!credentials) { Serial.println("RESULT wifi_load=UNTESTED missing /wifi.txt"); return; }
    if (credentials.size() > 512) {
        credentials.close(); Serial.println("RESULT wifi_load=FAIL configuration too large"); return;
    }
    String ssid = credentials.readStringUntil('\n'), password = credentials.readStringUntil('\n');
    credentials.close();
    if (ssid.endsWith("\r")) ssid.remove(ssid.length()-1);
    if (password.endsWith("\r")) password.remove(password.length()-1);
    if (ssid.isEmpty() || ssid.length() > 32 || password.length() > 63) {
        Serial.println("RESULT wifi_load=FAIL credentials format"); return;
    }
    WiFi.persistent(false); WiFi.mode(WIFI_STA); WiFi.begin(ssid.c_str(), password.c_str());
    const uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) delay(50);
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("RESULT wifi_load=FAIL association/DHCP timeout");
        WiFi.disconnect(true, false); return;
    }
    File directory = SD.open("/");
    bool ok = directory && directory.isDirectory();
    directory.close();
    // Exercise actual SD file reads alongside display SPI and WiFi association.
    File source = SD.open("/wifi.txt", FILE_READ);
    ok = ok && source;
    uint8_t bytes[64];
    const uint32_t loadStart = millis();
    unsigned frames = 0;
    while (ok && millis() - loadStart < 10000) {
        drawPattern(frames++);
        ok = source.seek(0) && source.read(bytes, sizeof(bytes)) > 0 && WiFi.status() == WL_CONNECTED;
        delay(20);
    }
    source.close();
    Serial.printf("RESULT wifi_sd_display_10s=%s frames=%u RSSI_dBm=%d\n",
        ok ? "PASS" : "FAIL", frames, WiFi.RSSI());
    Serial.println("Local functional smoke only; no throughput, packet-loss or antenna certification.");
    WiFi.disconnect(true, false);
}

void dispatch(const char *command) {
    if (!strcmp(command, "help")) help();
    else if (!strcmp(command, "status")) status();
    else if (!strcmp(command, "i2c")) sensors();
    else if (!strcmp(command, "display")) {
        drawPattern(); Serial.println("RESULT display_write=SENT; visual confirmation REQUIRED");
    } else if (!strncmp(command, "backlight ", 10))
        Serial.printf("RESULT backlight_command=%s; measure current, PWM alone is not a current test\n",
            backlight(command+10) ? "APPLIED" : "REJECTED");
    else if (!strcmp(command, "rgb")) {
        for (const CRGB color : {CRGB::Red, CRGB::Green, CRGB::Blue}) {
            pixel[0] = color; FastLED.show(); delay(500);
        }
        pixel[0] = CRGB::Black; FastLED.show();
        Serial.println("RESULT rgb_write=SENT; visual confirmation REQUIRED");
    } else if (!strcmp(command, "sd-status")) {
        if (mountCard()) Serial.printf("SD bytes=%llu type=%u\n", SD.cardSize(), SD.cardType());
    } else if (!strcmp(command, "sd-test")) cardTest();
    else if (!strcmp(command, "wifi-scan")) wifiScan();
    else if (!strcmp(command, "wifi-load")) wifiLoad();
    else Serial.println("UNKNOWN command; use help");
}
}

void setup() {
    Serial.begin(115200);
    // Preload HIGH before enabling the output. ledcAttach's reset duty=0 would
    // briefly enable this active-low backlight, so attach only on explicit use.
    if (gpio_set_level(GPIO_NUM_5, 1) != ESP_OK ||
        gpio_set_direction(GPIO_NUM_5, GPIO_MODE_OUTPUT) != ESP_OK)
        Serial.println("ERROR backlight output initialization");
    Wire.begin(32, 33); Wire.setTimeOut(50); Wire.setClock(400000);
    FastLED.addLeds<WS2812, 27, GRB>(pixel, 1);
    FastLED.setBrightness(16); pixel[0] = CRGB::Black; FastLED.show();
    delay(100); status(); help();
}

void loop() {
    while (Serial.available()) {
        const char c = Serial.read();
        if (c == '\r') continue;
        if (c == '\n') {
            if (overflow) Serial.println("REJECTED command too long");
            else if (used) { line[used] = 0; dispatch(line); }
            used = 0; overflow = false;
        } else if (c < 32 || c > 126) overflow = true;
        else if (used < sizeof(line)-1 && !overflow) line[used++] = c;
        else overflow = true;
    }
    delay(5);
}
#endif
