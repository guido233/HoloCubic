#pragma once
#include <Arduino.h>
#include <NetworkClientSecure.h>
#include <algorithm>
#include <cassert>
constexpr int HTTP_CODE_OK = 200;
constexpr int HTTPC_DISABLE_FOLLOW_REDIRECTS = 0;
struct HttpStub {
    std::string payload = "{\"code\":0,\"data\":{\"follower\":42}}";
    int status = 200;
    int size = -1;
    int begins = 0;
    int ends = 0;
    bool beginOk = true;
    bool streamOk = true;
    std::string url;
};
extern HttpStub httpStub;
struct HTTPClient {
    void setConnectTimeout(int32_t) {}
    void setTimeout(uint16_t) {}
    void setFollowRedirects(int follow) { assert(follow == HTTPC_DISABLE_FOLLOW_REDIRECTS); }
    bool begin(NetworkClientSecure& client, const String& url) {
        assert(client.trusted);
        httpStub.url = url.c_str();
        assert(httpStub.url.rfind("https://api.bilibili.com/", 0) == 0);
        ++httpStub.begins;
        return httpStub.beginOk;
    }
    int GET() { return httpStub.status; }
    int getSize() { return httpStub.size; }
    int writeToStream(Stream* stream) {
        if (!httpStub.streamOk) return -1;
        for (size_t pos = 0; pos < httpStub.payload.size();) {
            const size_t count = std::min<size_t>(512, httpStub.payload.size() - pos);
            if (stream->write(reinterpret_cast<const uint8_t*>(httpStub.payload.data() + pos), count) != count) return -10;
            pos += count;
        }
        return static_cast<int>(httpStub.payload.size());
    }
    void end() { ++httpStub.ends; }
};
