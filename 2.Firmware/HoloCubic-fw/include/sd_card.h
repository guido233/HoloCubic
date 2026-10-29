#ifndef SD_CARD_H
#define SD_CARD_H

#include "FS.h"
#include "SD.h"
#include "SPI.h"

class SdCard
{
private:
    SPIClass sdSpi_{HSPI};
    bool mounted_ = false;
    bool spiStarted_ = false;

    bool requireMounted() const;

public:
    SdCard() = default;
    ~SdCard();
    SdCard(const SdCard&) = delete;
    SdCard& operator=(const SdCard&) = delete;

    bool init();
    void end();
    bool isMounted() const { return mounted_; }

    bool listDir(const char* dirname, uint8_t levels);
    bool createDir(const char* path);
    bool removeDir(const char* path);
    bool readFile(const char* path);

    // Legacy convenience API: returns a trimmed line, or an empty String on error.
    String readFileLine(const char* path, int num = 1);
    // Reports missing files/lines separately from empty lines. Only strips CRLF;
    // other whitespace is preserved, including spaces in WiFi credentials.
    bool readFileLine(const char* path, int num, String& line);

    bool writeFile(const char* path, const char* message);
    bool appendFile(const char* path, const char* message);
    bool renameFile(const char* path1, const char* path2);
    bool deleteFile(const char* path);

    // Rejects files larger than capacity before writing. On an I/O failure,
    // bytesRead reports the successfully read prefix; it is zero on open errors.
    bool readBinFromSd(const char* path, uint8_t* buf, size_t capacity, size_t& bytesRead);
    // Legacy benchmark helper: repeats a 512-byte buffer to write 1 MiB.
    bool writeBinToSd(const char* path, uint8_t* buf);
    bool fileIO(const char* path);
};

extern SdCard tf;

#endif
