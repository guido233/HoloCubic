// Host regression tests exercise the production source with fake transport only.
#include "holo_network.h"
#include <HTTPClient.h>
#include <WiFi.h>
#include <cassert>
#include <iostream>
#include <limits>

SerialStub Serial;
WiFiStub WiFi;
HttpStub httpStub;
uint32_t fakeMillis = 0;
time_t fakeNow = 1800000000;
int configTimeCalls = 0;
extern "C" time_t time(time_t* result) {
    if (result) *result = fakeNow;
    return fakeNow;
}

void reset() {
    WiFi = WiFiStub();
    httpStub = HttpStub();
    Serial = SerialStub();
    fakeMillis = 0;
    fakeNow = 1800000000;
    configTimeCalls = 0;
}

int main() {
    HoloNetwork network;
    uint32_t fans = 123;
    reset();
    assert(!network.init("", "test-password", 100));
    assert(network.lastError() == HoloNetwork::Error::InvalidSsid && WiFi.begins == 0);
    assert(!network.init("test-network", "test-password", 250));
    assert(fakeMillis == 250 && WiFi.disconnects == 1);
    assert(network.lastError() == HoloNetwork::Error::WifiTimeout);
    assert(Serial.output.find("test-password") == std::string::npos);

    reset();
    fakeMillis = std::numeric_limits<uint32_t>::max() - 50;
    assert(!network.init("test-network", "test-password", 250));
    assert(network.lastError() == HoloNetwork::Error::WifiTimeout);
    assert(fakeMillis == 199); // elapsed-time check remains valid across wrap
    reset();
    WiFi.connectOnBegin = true;
    assert(network.init("test-network", "test-password", 250));
    assert(network.lastError() == HoloNetwork::Error::None);
    assert(Serial.output.find("test-password") == std::string::npos);

    reset();
    assert(!network.getBilibiliFans("1&evil=1", fans));
    assert(network.lastError() == HoloNetwork::Error::InvalidUid && httpStub.begins == 0);
    WiFi.state = WL_DISCONNECTED;
    assert(!network.getBilibiliFans("1", fans));
    assert(network.lastError() == HoloNetwork::Error::NotConnected);

    reset();
#if !TEST_CERTIFICATE_BUNDLE
    assert(!network.getBilibiliFans("1", fans));
    assert(network.lastError() == HoloNetwork::Error::TlsUnavailable);
    assert(httpStub.begins == 0 && fans == 123);
    std::cout << "HoloNetwork fail-closed CA-bundle regression passed\n";
#else
    assert(network.getBilibiliFans("1", fans) && fans == 42);
    assert(network.lastError() == HoloNetwork::Error::None && httpStub.ends == 1);
    assert(httpStub.url == "https://api.bilibili.com/x/relation/stat?vmid=1");
    httpStub.payload = "{\"data\":{\"other\":999,\"follower\":0},\"message\":\"ok\",\"code\":0}";
    assert(network.getBilibiliFans("1", fans) && fans == 0);
    fans = 123;

    struct InvalidCase { const char* payload; HoloNetwork::Error error; };
    const InvalidCase invalid[] = {
        {"broken JSON", HoloNetwork::Error::InvalidJson},
        {"{\"data\":{\"follower\":5}}", HoloNetwork::Error::InvalidJson},
        {"{\"code\":\"0\",\"data\":{\"follower\":5}}", HoloNetwork::Error::InvalidJson},
        {"{\"code\":-412,\"message\":\"blocked\",\"data\":null}", HoloNetwork::Error::ApiError},
        {"{\"code\":0,\"data\":{}}", HoloNetwork::Error::InvalidFans},
        {"{\"code\":0,\"data\":{\"follower\":-1}}", HoloNetwork::Error::InvalidFans},
        {"{\"code\":0,\"data\":{\"follower\":3.5}}", HoloNetwork::Error::InvalidFans},
        {"{\"code\":0,\"data\":{\"follower\":\"123\"}}", HoloNetwork::Error::InvalidFans},
        {"{\"code\":0,\"data\":{\"follower\":4294967296}}", HoloNetwork::Error::InvalidFans},
    };
    for (const auto& test : invalid) {
        httpStub.payload = test.payload;
        assert(!network.getBilibiliFans("1", fans));
        assert(network.lastError() == test.error && fans == 123);
        if (test.error == HoloNetwork::Error::ApiError) assert(network.lastApiCode() == -412);
    }
    reset();
    httpStub.status = 503;
    assert(!network.getBilibiliFans("1", fans));
    assert(network.lastError() == HoloNetwork::Error::HttpError && network.lastHttpStatus() == 503 && httpStub.ends == 1);
    httpStub.status = -1; // transport failure is distinct from a successful zero count
    assert(!network.getBilibiliFans("1", fans) && fans == 123);
    reset();
    httpStub.beginOk = false;
    assert(!network.getBilibiliFans("1", fans));
    assert(network.lastError() == HoloNetwork::Error::HttpBeginFailed);
    reset();
    httpStub.streamOk = false;
    assert(!network.getBilibiliFans("1", fans));
    assert(network.lastError() == HoloNetwork::Error::HttpError && httpStub.ends == 1);
    reset();
    httpStub.size = 4097;
    assert(!network.getBilibiliFans("1", fans));
    assert(network.lastError() == HoloNetwork::Error::ResponseTooLarge);
    reset();
    httpStub.payload = std::string(4097, ' '); // unknown/chunked length is also capped
    assert(!network.getBilibiliFans("1", fans));
    assert(network.lastError() == HoloNetwork::Error::ResponseTooLarge);
    reset();
    fakeNow = 0;
    assert(!network.getBilibiliFans("1", fans));
    assert(network.lastError() == HoloNetwork::Error::TimeSyncTimeout);
    assert(configTimeCalls == 1 && fakeMillis == 10000 && httpStub.begins == 0);
    assert(fans == 123);
    std::cout << "HoloNetwork timeout, HTTPS, JSON and failure regressions passed\n";
#endif
}
