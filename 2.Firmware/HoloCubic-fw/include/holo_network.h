#ifndef HOLOCUBIC_NETWORK_H
#define HOLOCUBIC_NETWORK_H

#include <Arduino.h>

class HoloNetwork
{
public:
    enum class Error : uint8_t
    {
        None,
        InvalidSsid,
        WifiTimeout,
        NotConnected,
        InvalidUid,
        TlsUnavailable,
        TimeSyncTimeout,
        HttpBeginFailed,
        HttpError,
        ResponseTooLarge,
        InvalidJson,
        ApiError,
        InvalidFans
    };

    bool init(const String& ssid, const String& password, uint32_t timeoutMs = 15000);
    // On failure, leave fans unchanged. A successful count can legitimately be zero.
    bool getBilibiliFans(const String& uid, uint32_t& fans);

    Error lastError() const { return error_; }
    int lastHttpStatus() const { return httpStatus_; }
    int lastApiCode() const { return apiCode_; }

private:
    Error error_ = Error::None;
    int httpStatus_ = 0;
    int apiCode_ = 0;
};

#endif
