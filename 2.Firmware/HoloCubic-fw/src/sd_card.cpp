#include "sd_card.h"
#include <string.h>

namespace
{
constexpr int kSdSck = 14;
constexpr int kSdMiso = 26;
constexpr int kSdMosi = 13;
constexpr int kSdCs = 15;

void removeCarriageReturn(String& line)
{
    if (line.length() && line.charAt(line.length() - 1) == '\r')
        line.remove(line.length() - 1);
}
}

SdCard::~SdCard()
{
    end();
}

bool SdCard::init()
{
    end();
    // Set the board's HSPI pins here; no Arduino core SPI.cpp patch is needed.
    if (!sdSpi_.begin(kSdSck, kSdMiso, kSdMosi, kSdCs))
    {
        // begin() can fail after partially allocating the bus. Do not let
        // SD.begin() retry it with default pins (GPIO12 is a boot strap pin).
        sdSpi_.end();
        Serial.println("SD SPI initialization failed");
        return false;
    }
    spiStarted_ = true;
    if (!SD.begin(kSdCs, sdSpi_))
    {
        Serial.println("Card Mount Failed");
        SD.end();
        end();
        return false;
    }
    if (SD.cardType() == CARD_NONE)
    {
        Serial.println("No SD card attached");
        SD.end();
        end();
        return false;
    }

    mounted_ = true;
    Serial.printf("SD Card Size: %lluMB\n",
                  static_cast<unsigned long long>(SD.cardSize() / (1024 * 1024)));
    return true;
}

void SdCard::end()
{
    if (mounted_) SD.end();
    mounted_ = false;
    if (spiStarted_) sdSpi_.end();
    spiStarted_ = false;
}

bool SdCard::requireMounted() const
{
    if (!mounted_) Serial.println("SD card is not mounted");
    return mounted_;
}

bool SdCard::listDir(const char* dirname, uint8_t levels)
{
    if (!requireMounted() || !dirname) return false;
    File root = SD.open(dirname);
    if (!root || !root.isDirectory())
    {
        root.close();
        return false;
    }

    bool success = true;
    File file = root.openNextFile();
    while (file)
    {
        Serial.print(file.isDirectory() ? "  DIR : " : "  FILE: ");
        Serial.println(file.name());
        // Arduino-ESP32 3.x name() is a basename; recursion needs the full path.
        if (file.isDirectory() && levels && !listDir(file.path(), levels - 1))
            success = false;
        file.close();
        file = root.openNextFile();
    }
    root.close();
    return success;
}

bool SdCard::createDir(const char* path)
{
    return requireMounted() && path && SD.mkdir(path);
}

bool SdCard::removeDir(const char* path)
{
    return requireMounted() && path && SD.rmdir(path);
}

bool SdCard::readFile(const char* path)
{
    if (!requireMounted() || !path) return false;
    File file = SD.open(path);
    if (!file || file.isDirectory())
    {
        file.close();
        return false;
    }
    while (file.available())
    {
        int value = file.read();
        if (value < 0)
        {
            file.close();
            return false;
        }
        Serial.write(static_cast<uint8_t>(value));
    }
    file.close();
    return true;
}

String SdCard::readFileLine(const char* path, int num)
{
    String line;
    if (readFileLine(path, num, line)) line.trim();
    return line;
}

bool SdCard::readFileLine(const char* path, int num, String& line)
{
    line = "";
    if (!requireMounted() || !path || num < 1) return false;
    File file = SD.open(path);
    if (!file || file.isDirectory())
    {
        file.close();
        return false;
    }

    int currentLine = 1;
    bool hasCharacters = false;
    while (file.available())
    {
        int value = file.read();
        if (value < 0)
        {
            file.close();
            line = "";
            return false;
        }
        char c = static_cast<char>(value);
        if (currentLine != num)
        {
            if (c == '\n') ++currentLine;
            continue;
        }
        hasCharacters = true;
        if (c == '\n')
        {
            removeCarriageReturn(line);
            file.close();
            return true;
        }
        if (!line.concat(c))
        {
            file.close();
            line = "";
            return false;
        }
    }
    file.close();
    if (currentLine != num || !hasCharacters) return false;
    removeCarriageReturn(line);
    return true;
}

bool SdCard::writeFile(const char* path, const char* message)
{
    if (!requireMounted() || !path || !message) return false;
    File file = SD.open(path, FILE_WRITE);
    if (!file) return false;
    bool success = file.print(message) == strlen(message);
    file.close();
    return success;
}

bool SdCard::appendFile(const char* path, const char* message)
{
    if (!requireMounted() || !path || !message) return false;
    File file = SD.open(path, FILE_APPEND);
    if (!file) return false;
    bool success = file.print(message) == strlen(message);
    file.close();
    return success;
}

bool SdCard::renameFile(const char* path1, const char* path2)
{
    return requireMounted() && path1 && path2 && SD.rename(path1, path2);
}

bool SdCard::deleteFile(const char* path)
{
    return requireMounted() && path && SD.remove(path);
}

bool SdCard::readBinFromSd(const char* path, uint8_t* buf, size_t capacity, size_t& bytesRead)
{
    bytesRead = 0;
    if (!requireMounted() || !path || (!buf && capacity)) return false;
    File file = SD.open(path);
    if (!file || file.isDirectory())
    {
        file.close();
        return false;
    }
    size_t remaining = file.size();
    if (remaining > capacity)
    {
        file.close();
        return false;
    }
    while (remaining)
    {
        size_t toRead = remaining > 512 ? 512 : remaining;
        size_t count = file.read(buf + bytesRead, toRead);
        if (!count || count > toRead)
        {
            file.close();
            return false;
        }
        bytesRead += count;
        remaining -= count;
    }
    file.close();
    return true;
}

bool SdCard::writeBinToSd(const char* path, uint8_t* buf)
{
    if (!requireMounted() || !path || !buf) return false;
    File file = SD.open(path, FILE_WRITE);
    if (!file) return false;
    for (size_t i = 0; i < 2048; ++i)
    {
        if (file.write(buf, 512) != 512)
        {
            file.close();
            return false;
        }
    }
    file.close();
    return true;
}

bool SdCard::fileIO(const char* path)
{
    if (!requireMounted() || !path) return false;
    File file = SD.open(path);
    uint8_t buffer[512] = {};
    if (!file || file.isDirectory())
    {
        file.close();
        return false;
    }
    size_t size = file.size();
    size_t remaining = size;
    uint32_t start = millis();
    while (remaining)
    {
        size_t count = file.read(buffer, remaining > sizeof(buffer) ? sizeof(buffer) : remaining);
        if (!count)
        {
            file.close();
            return false;
        }
        remaining -= count;
    }
    file.close();
    Serial.printf("%u bytes read for %lu ms\n", static_cast<unsigned>(size),
                  static_cast<unsigned long>(millis() - start));
    start = millis();
    bool success = writeBinToSd(path, buffer);
    Serial.printf("Benchmark write %s in %lu ms\n", success ? "completed" : "failed",
                  static_cast<unsigned long>(millis() - start));
    return success;
}
