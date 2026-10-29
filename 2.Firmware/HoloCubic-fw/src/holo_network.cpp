#include "holo_network.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <WiFi.h>
#include <esp_arduino_version.h>
#include <sdkconfig.h>
#include <time.h>

namespace
{
constexpr uint32_t kClockTimeoutMs = 10000;
constexpr size_t kMaxResponseBytes = 4096;
constexpr time_t kMinimumValidTime = 1704067200; // 2024-01-01 UTC

// HTTPClient decodes chunked responses before writing here. Bound both known-
// and unknown-length bodies, rather than allocating an unbounded getString().
class ResponseBuffer : public Stream
{
public:
    size_t write(uint8_t value) override { return write(&value, 1); }
    size_t write(const uint8_t* data, size_t size) override
    {
        if (size > kMaxResponseBytes - body.length())
        {
            tooLarge = true;
            return 0;
        }
        return body.concat(reinterpret_cast<const char*>(data), size) ? size : 0;
    }

    int available() override { return 0; }
    int read() override { return -1; }
    int peek() override { return -1; }
    void flush() override {}

    String body;
    bool tooLarge = false;
};

bool validUid(const String& uid)
{
    if (uid.isEmpty() || uid.length() > 20) return false;
    for (size_t i = 0; i < uid.length(); ++i)
    {
        if (uid[i] < '0' || uid[i] > '9') return false;
    }
    return true;
}

bool ensureClock()
{
    if (time(nullptr) >= kMinimumValidTime) return true;

    // Certificate validity dates require a clock. Do not bypass TLS validation
    // when NTP is unavailable; callers can also provide a valid RTC time.
    configTime(0, 0, "time.cloudflare.com", "pool.ntp.org");
    const uint32_t started = millis();
    while (time(nullptr) < kMinimumValidTime)
    {
        if (static_cast<uint32_t>(millis() - started) >= kClockTimeoutMs) return false;
        delay(100);
    }
    return true;
}
}

bool HoloNetwork::init(const String& ssid, const String& password, uint32_t timeoutMs)
{
    error_ = Error::None;
    httpStatus_ = 0;
    apiCode_ = 0;
    if (ssid.isEmpty() || ssid.length() > 32)
    {
        error_ = Error::InvalidSsid;
        return false;
    }

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());
    const uint32_t started = millis();
    while (WiFi.status() != WL_CONNECTED)
    {
        const uint32_t elapsed = millis() - started;
        if (elapsed >= timeoutMs)
        {
            WiFi.disconnect();
            error_ = Error::WifiTimeout;
            return false;
        }
        const uint32_t remaining = timeoutMs - elapsed;
        delay(remaining < 100 ? remaining : 100);
    }

    Serial.println("WiFi connected");
    return true;
}

bool HoloNetwork::getBilibiliFans(const String& uid, uint32_t& fans)
{
    error_ = Error::None;
    httpStatus_ = 0;
    apiCode_ = 0;
    if (!validUid(uid))
    {
        error_ = Error::InvalidUid;
        return false;
    }
    if (WiFi.status() != WL_CONNECTED)
    {
        error_ = Error::NotConnected;
        return false;
    }

#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 3, 12) && CONFIG_MBEDTLS_CERTIFICATE_BUNDLE
    if (!ensureClock())
    {
        error_ = Error::TimeSyncTimeout;
        return false;
    }

    NetworkClientSecure client;
    // Arduino-ESP32 3.3.12 exposes the ESP-IDF built-in Mozilla CA bundle.
    // Both the chain and api.bilibili.com hostname are verified by TLS.
    client.useBuiltinCACertBundle();
    client.setHandshakeTimeout(10);
    HTTPClient http;
    http.setConnectTimeout(5000);
    http.setTimeout(5000);
    http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
    if (!http.begin(client, "https://api.bilibili.com/x/relation/stat?vmid=" + uid))
    {
        error_ = Error::HttpBeginFailed;
        return false;
    }

    httpStatus_ = http.GET();
    if (httpStatus_ != HTTP_CODE_OK)
    {
        http.end();
        error_ = Error::HttpError;
        return false;
    }
    if (http.getSize() > static_cast<int>(kMaxResponseBytes))
    {
        http.end();
        error_ = Error::ResponseTooLarge;
        return false;
    }

    ResponseBuffer response;
    const int bytesRead = http.writeToStream(&response);
    http.end();
    if (response.tooLarge)
    {
        error_ = Error::ResponseTooLarge;
        return false;
    }
    if (bytesRead < 0)
    {
        error_ = Error::HttpError;
        return false;
    }

    JsonDocument document;
    if (deserializeJson(document, response.body.c_str(), response.body.length(),
                        DeserializationOption::NestingLimit(6)))
    {
        error_ = Error::InvalidJson;
        return false;
    }
    if (!document["code"].is<int>())
    {
        error_ = Error::InvalidJson;
        return false;
    }
    apiCode_ = document["code"].as<int>();
    if (apiCode_ != 0)
    {
        error_ = Error::ApiError;
        return false;
    }
    if (!document["data"]["follower"].is<uint32_t>())
    {
        error_ = Error::InvalidFans;
        return false;
    }
    fans = document["data"]["follower"].as<uint32_t>();
    return true;
#else
    // Fail closed for builds without the verified built-in CA bundle API.
    (void)fans;
    error_ = Error::TlsUnavailable;
    return false;
#endif
}
