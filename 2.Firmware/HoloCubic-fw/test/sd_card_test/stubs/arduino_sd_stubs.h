#ifndef ARDUINO_SD_STUBS_H
#define ARDUINO_SD_STUBS_H

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstring>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>

class String {
    std::string value_;
public:
    static bool failConcat;
    static int concatBudget;
    String() = default;
    String(const char* value) : value_(value) {}
    String& operator=(const char* value) { value_ = value; return *this; }
    bool concat(char c) {
        if (failConcat || concatBudget == 0) return false;
        if (concatBudget > 0) --concatBudget;
        value_ += c;
        return true;
    }
    size_t length() const { return value_.size(); }
    char charAt(size_t index) const { return value_.at(index); }
    void remove(size_t index) { value_.erase(index); }
    void trim() {
        auto first = value_.find_first_not_of(" \t\r\n");
        if (first == std::string::npos) { value_.clear(); return; }
        auto last = value_.find_last_not_of(" \t\r\n");
        value_ = value_.substr(first, last - first + 1);
    }
    const char* c_str() const { return value_.c_str(); }
};

constexpr int HSPI = 1;
class SPIClass {
public:
    int bus;
    int pins[4] = {};
    int beginCalls = 0;
    int endCalls = 0;
    bool started = false;
    explicit SPIClass(int value) : bus(value) {}
    static bool& beginResult() { static bool result = true; return result; }
    static SPIClass*& lastStarted() { static SPIClass* bus = nullptr; return bus; }
    bool begin(int sck, int miso, int mosi, int cs) {
        pins[0] = sck; pins[1] = miso; pins[2] = mosi; pins[3] = cs;
        ++beginCalls; started = true;
        lastStarted() = this;
        return beginResult();
    }
    void end() { ++endCalls; started = false; }
};

struct SerialStub {
    template<typename T> void print(const T&) {}
    template<typename T> void println(const T&) {}
    template<typename... T> void printf(const char*, T...) {}
    void write(uint8_t) {}
};
extern SerialStub Serial;
inline uint32_t millis() { return 100; }

constexpr int FILE_READ = 0;
constexpr int FILE_WRITE = 1;
constexpr int FILE_APPEND = 2;
constexpr uint8_t CARD_NONE = 0;
constexpr uint8_t CARD_MMC = 1;
constexpr uint8_t CARD_SD = 2;
constexpr uint8_t CARD_SDHC = 3;

namespace fs { enum SeekMode { SeekSet, SeekCur, SeekEnd }; }
class SDClass;

struct FileState {
    std::shared_ptr<std::string> data;
    std::string path;
    size_t position = 0;
    bool closed = false;
    bool directory = false;
    int* closeCount = nullptr;
    size_t maxRead = 512;
    bool readError = false;
    size_t readLimit = static_cast<size_t>(-1);
    size_t maxWrite = static_cast<size_t>(-1);
    std::vector<std::string> entries;
    size_t nextEntry = 0;
    SDClass* owner = nullptr;
    std::string basename;
};
class File {
    std::shared_ptr<FileState> state_;
public:
    File() = default;
    explicit File(std::shared_ptr<FileState> state) : state_(state) {}
    explicit operator bool() const { return state_ && !state_->closed; }
    bool isDirectory() const { return state_ && state_->directory; }
    bool available() const {
        return *this && state_->position < state_->data->size();
    }
    int read() {
        if (!available() || state_->readError || state_->position >= state_->readLimit) return -1;
        return static_cast<unsigned char>((*state_->data)[state_->position++]);
    }
    size_t read(uint8_t* output, size_t size) {
        if (!available() || state_->readError || state_->position >= state_->readLimit) return 0;
        size = std::min(size, state_->data->size() - state_->position);
        size = std::min(size, state_->maxRead);
        size = std::min(size, state_->readLimit - state_->position);
        std::memcpy(output, state_->data->data() + state_->position, size);
        state_->position += size;
        return size;
    }
    size_t write(const uint8_t* input, size_t size) {
        if (!*this) return 0;
        size = std::min(size, state_->maxWrite);
        if (state_->position + size > state_->data->size())
            state_->data->resize(state_->position + size);
        std::memcpy(&(*state_->data)[state_->position], input, size);
        state_->position += size;
        return size;
    }
    size_t print(const char* message) {
        return write(reinterpret_cast<const uint8_t*>(message), std::strlen(message));
    }
    size_t size() const { return state_ ? state_->data->size() : 0; }
    uint32_t position() const { return state_ ? static_cast<uint32_t>(state_->position) : 0; }
    bool seek(uint32_t position, fs::SeekMode mode) {
        if (!*this) return false;
        uint64_t base = 0;
        if (mode == fs::SeekCur) base = state_->position;
        if (mode == fs::SeekEnd) base = state_->data->size();
        if (base + position > UINT32_MAX) return false;
        state_->position = static_cast<size_t>(base + position);
        return true;
    }
    const char* name() const { return state_->basename.c_str(); }
    const char* path() const { return state_->path.c_str(); }
    File openNextFile();
    void close() {
        if (*this) {
            state_->closed = true;
            ++*state_->closeCount;
        }
    }
};

class SDClass {
public:
    bool beginResult = true;
    uint8_t type = CARD_SDHC;
    SPIClass* spi = nullptr;
    int cs = -1;
    int beginCalls = 0;
    int endCalls = 0;
    int openCalls = 0;
    int closeCalls = 0;
    int mutationCalls = 0;
    size_t maxRead = 512;
    bool readError = false;
    size_t readLimit = static_cast<size_t>(-1);
    std::map<std::string, std::shared_ptr<std::string>> files;
    std::set<std::string> directories;
    std::map<std::string, std::vector<std::string>> entries;
    size_t maxWrite = static_cast<size_t>(-1);
    bool begin(int pin, SPIClass& bus) {
        ++beginCalls; cs = pin; spi = &bus;
        return beginResult;
    }
    void end() { ++endCalls; }
    uint8_t cardType() const { return type; }
    uint64_t cardSize() const { return 1024 * 1024; }
    void put(const std::string& path, const std::string& value) {
        files[path] = std::make_shared<std::string>(value);
    }
    File open(const char* path, int mode = FILE_READ) {
        ++openCalls;
        auto it = files.find(path);
        bool directory = directories.count(path);
        if (!directory && it == files.end()) {
            if (mode == FILE_READ || mode == 3) return File();
            put(path, "");
            it = files.find(path);
        }
        auto state = std::make_shared<FileState>();
        state->data = directory ? std::make_shared<std::string>() : it->second;
        state->path = path;
        state->basename = std::string(path).substr(std::string(path).find_last_of('/') + 1);
        state->entries = entries[path];
        state->owner = this;
        state->directory = directory;
        state->closeCount = &closeCalls;
        state->maxRead = maxRead;
        state->readError = readError;
        state->readLimit = readLimit;
        state->maxWrite = maxWrite;
        if (mode == FILE_APPEND) state->position = state->data->size();
        if (mode == FILE_WRITE) state->data->clear();
        return File(state);
    }
    bool exists(const char* path) const { return files.count(path) || directories.count(path); }
    File open(const char* path, const char* mode) {
        if (std::strcmp(mode, "r+") == 0) return open(path, 3);
        if (std::strcmp(mode, "w+") == 0) return open(path, FILE_WRITE);
        return open(path, FILE_READ);
    }
    bool mkdir(const char* path) { ++mutationCalls; return directories.insert(path).second; }
    bool rmdir(const char* path) { ++mutationCalls; return directories.erase(path); }
    bool rename(const char* a, const char* b) {
        ++mutationCalls;
        auto it = files.find(a);
        if (it == files.end()) return false;
        files[b] = it->second; files.erase(it); return true;
    }
    bool remove(const char* path) { ++mutationCalls; return files.erase(path); }
};
extern SDClass SD;
inline File File::openNextFile() {
    if (!*this || !isDirectory() || state_->nextEntry == state_->entries.size()) return File();
    return state_->owner->open(state_->entries[state_->nextEntry++].c_str());
}

#endif
