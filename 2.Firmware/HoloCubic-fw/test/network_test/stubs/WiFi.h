#pragma once
#include <Arduino.h>
constexpr int WIFI_STA = 1;
constexpr int WL_CONNECTED = 3;
constexpr int WL_DISCONNECTED = 6;
struct WiFiStub {
    int state = WL_CONNECTED;
    bool connectOnBegin = false;
    int begins = 0;
    int disconnects = 0;
    void mode(int) {}
    void begin(const char*, const char*) { ++begins; state = connectOnBegin ? WL_CONNECTED : WL_DISCONNECTED; }
    int status() { return state; }
    void disconnect() { ++disconnects; state = WL_DISCONNECTED; }
};
extern WiFiStub WiFi;
