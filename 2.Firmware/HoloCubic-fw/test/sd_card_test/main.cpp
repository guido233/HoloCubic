#include "sd_card.h"
#include <cassert>
#include <iostream>
#include <vector>

SerialStub Serial;
SDClass SD;
bool String::failConcat = false;
int String::concatBudget = -1;

void expectLine(SdCard& card, const char* path, int number,
                bool expectedSuccess, const std::string& expected = "") {
    String actual("stale value");
    int opened = SD.openCalls;
    int closed = SD.closeCalls;
    assert(card.readFileLine(path, number, actual) == expectedSuccess);
    assert(std::string(actual.c_str()) == expected);
    // Every successful open must close even when the requested line is absent.
    assert(SD.openCalls - opened == SD.closeCalls - closed);
}

int main() {
    {
        SdCard card;
        uint8_t buffer[512] = {};
        size_t bytesRead = 999;
        String value("stale");
        assert(!card.isMounted());
        assert(!card.readFileLine("/wifi.txt", 1, value));
        assert(std::string(value.c_str()).empty());
        assert(!card.listDir("/", 1));
        assert(!card.createDir("/x"));
        assert(!card.removeDir("/x"));
        assert(!card.readFile("/x"));
        assert(!card.writeFile("/x", "x"));
        assert(!card.appendFile("/x", "x"));
        assert(!card.renameFile("/x", "/y"));
        assert(!card.deleteFile("/x"));
        assert(!card.readBinFromSd("/x", buffer, sizeof(buffer), bytesRead));
        assert(bytesRead == 0);
        assert(!card.writeBinToSd("/x", buffer));
        assert(!card.fileIO("/x"));
        assert(SD.openCalls == 0 && SD.mutationCalls == 0);

        SPIClass::beginResult() = false;
        int mountCalls = SD.beginCalls;
        assert(!card.init());
        assert(!card.isMounted());
        assert(SD.beginCalls == mountCalls);
        assert(SPIClass::lastStarted()->endCalls == 1);
        assert(!SPIClass::lastStarted()->started);
        assert(!card.readFileLine("/wifi.txt", 1, value));
        assert(SD.openCalls == 0);
        SPIClass::beginResult() = true;

        SD.beginResult = false;
        assert(!card.init());
        assert(!card.isMounted());
        assert(!SD.spi->started);
        assert(SD.spi->pins[0] == 14 && SD.spi->pins[1] == 26);
        assert(SD.spi->pins[2] == 13 && SD.spi->pins[3] == 15);
        assert(SD.cs == 15);
        assert(!card.readFileLine("/wifi.txt", 1, value));
        assert(SD.openCalls == 0);

        SD.beginResult = true;
        SD.type = CARD_NONE;
        assert(!card.init());
        assert(!card.isMounted() && !SD.spi->started);

        SD.type = CARD_SDHC;
        assert(card.init());
        assert(card.isMounted() && SD.spi->started);
        int ends = SD.endCalls;
        assert(card.init()); // Remount uses the same owned SPI object and releases the old mount.
        assert(SD.endCalls == ends + 1);
        SPIClass::beginResult() = false;
        mountCalls = SD.beginCalls;
        assert(!card.init()); // A failed reinitialization also releases the previous mount.
        assert(!card.isMounted() && !SPIClass::lastStarted()->started);
        assert(SD.beginCalls == mountCalls);
        SPIClass::beginResult() = true;
        assert(card.init()); // Recovery retains the explicit board pin mapping.
        assert(SD.spi->pins[1] == 26);

        SD.put("/lf", "ssid\npassword");
        expectLine(card, "/lf", 1, true, "ssid");
        expectLine(card, "/lf", 2, true, "password");
        expectLine(card, "/lf", 3, false);
        SD.put("/crlf", "  ssid  \r\n pass phrase \r\n");
        expectLine(card, "/crlf", 1, true, "  ssid  ");
        expectLine(card, "/crlf", 2, true, " pass phrase ");
        expectLine(card, "/crlf", 3, false);
        assert(std::string(card.readFileLine("/crlf").c_str()) == "ssid");
        SD.put("/empty", "");
        expectLine(card, "/empty", 1, false);
        SD.put("/blank", "\n\r\nlast\r");
        expectLine(card, "/blank", 1, true, "");
        expectLine(card, "/blank", 2, true, "");
        expectLine(card, "/blank", 3, true, "last");
        expectLine(card, "/blank", 4, false);
        expectLine(card, "/lf", 0, false);
        expectLine(card, "/lf", -1, false);
        // Exercise both sides of the original fixed 128-byte buffer boundary,
        // a multi-kilobyte value, and skipping a much longer preceding line.
        for (size_t length : {size_t(127), size_t(128), size_t(129), size_t(8192)}) {
            const std::string payload(length, 'x');
            SD.put("/long", std::string(16384, 's') + "\n" + payload + "\r\n");
            expectLine(card, "/long", 2, true, payload);
            SD.put("/last", payload);
            expectLine(card, "/last", 1, true, payload);
        }
        String stale("stale");
        assert(!card.readFileLine("/missing", 1, stale));
        assert(std::string(stale.c_str()).empty());
        SD.directories.insert("/dir");
        expectLine(card, "/dir", 1, false);
        String::failConcat = true;
        expectLine(card, "/lf", 1, false);
        String::failConcat = false;
        String::concatBudget = 2;
        expectLine(card, "/lf", 1, false);
        String::concatBudget = -1;
        SD.readError = true;
        expectLine(card, "/lf", 1, false);
        SD.readError = false;

        std::string binary(1500, '\0');
        for (size_t i = 0; i < binary.size(); ++i) binary[i] = static_cast<char>(i);
        SD.put("/binary", binary);
        SD.maxRead = 37; // Real reads may return fewer bytes than requested.
        std::vector<uint8_t> data(binary.size() + 16, 0xa5);
        int closes = SD.closeCalls;
        assert(!card.readBinFromSd("/binary", data.data(), binary.size() - 1, bytesRead));
        assert(bytesRead == 0 && SD.closeCalls == closes + 1);
        assert(std::all_of(data.begin(), data.end(), [](uint8_t value) { return value == 0xa5; }));
        assert(!card.readBinFromSd("/binary", data.data(), 0, bytesRead));
        assert(bytesRead == 0 && data[0] == 0xa5);
        assert(!card.readBinFromSd("/binary", nullptr, binary.size(), bytesRead));
        assert(bytesRead == 0);
        assert(card.readBinFromSd("/binary", data.data(), binary.size(), bytesRead));
        assert(bytesRead == binary.size());
        assert(std::memcmp(data.data(), binary.data(), binary.size()) == 0);
        assert(std::all_of(data.begin() + binary.size(), data.end(), [](uint8_t value) { return value == 0xa5; }));
        std::fill(data.begin(), data.end(), 0xa5);
        SD.readLimit = 100; // Truncated read after several successful short chunks.
        assert(!card.readBinFromSd("/binary", data.data(), data.size(), bytesRead));
        assert(bytesRead == 100);
        assert(std::memcmp(data.data(), binary.data(), bytesRead) == 0);
        assert(std::all_of(data.begin() + bytesRead, data.end(), [](uint8_t value) { return value == 0xa5; }));
        SD.readLimit = static_cast<size_t>(-1);
        SD.readError = true;
        assert(!card.readBinFromSd("/binary", data.data(), data.size(), bytesRead));
        assert(bytesRead == 0);
        SD.readError = false;
        assert(!card.readBinFromSd("/missing", data.data(), data.size(), bytesRead));
        assert(bytesRead == 0);
        assert(!card.readBinFromSd("/dir", data.data(), data.size(), bytesRead));
        assert(bytesRead == 0);
        assert(card.readBinFromSd("/empty", nullptr, 0, bytesRead));
        assert(bytesRead == 0);
        SD.maxRead = 512;
        card.end();
        assert(!card.isMounted() && !SD.spi->started);
        int opens = SD.openCalls;
        assert(!card.readFile("/lf"));
        assert(SD.openCalls == opens);
    }
    {
        int ends = SD.endCalls;
        {
            SdCard card;
            assert(card.init());
        }
        assert(SD.endCalls == ends + 1); // Destructor unmounts before destroying SPI.
    }
    std::cout << "sd_card host tests passed\n";
}
