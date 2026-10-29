#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <time.h>

class String {
public:
    String() = default;
    String(const char* value) : value_(value) {}
    String(std::string value) : value_(value) {}
    bool isEmpty() const { return value_.empty(); }
    size_t length() const { return value_.size(); }
    const char* c_str() const { return value_.c_str(); }
    char operator[](size_t index) const { return value_[index]; }
    bool concat(const char* data, size_t size) { value_.append(data, size); return true; }
    friend String operator+(const char* prefix, const String& value) {
        return String(std::string(prefix) + value.value_);
    }
private:
    std::string value_;
};

class Stream {
public:
    virtual ~Stream() = default;
    virtual size_t write(uint8_t) = 0;
    virtual size_t write(const uint8_t*, size_t) = 0;
    virtual int available() = 0;
    virtual int read() = 0;
    virtual int peek() = 0;
    virtual void flush() = 0;
};

struct SerialStub {
    std::string output;
    void println(const char* message) { output += std::string(message) + "\n"; }
};
extern SerialStub Serial;
extern uint32_t fakeMillis;
extern time_t fakeNow;
extern int configTimeCalls;
inline uint32_t millis() { return fakeMillis; }
inline void delay(uint32_t duration) { fakeMillis += duration; }
inline void configTime(long, int, const char*, const char*) { ++configTimeCalls; }
