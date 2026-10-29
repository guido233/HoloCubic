#include "lvgl.h"
#include "lv_port_fatfs.h"
#include "sd_card.h"
#include <cassert>
#include <iostream>
#include <string>

SerialStub Serial;
SDClass SD;
SdCard tf;
bool String::failConcat = false;
int String::concatBudget = -1;
static lv_fs_drv_t* registered;
static int registrations;
void lv_fs_drv_init(lv_fs_drv_t* driver) { std::memset(driver, 0, sizeof(*driver)); }
lv_fs_drv_t* lv_fs_get_drv(char letter) {
    return registered && registered->letter == letter ? registered : nullptr;
}
void lv_fs_drv_register(lv_fs_drv_t* driver) {
    registered = driver;
    ++registrations;
}

int main() {
    lv_fs_if_init();
    assert(registered && registered->letter == 'S');
    lv_fs_drv_t* driver = registered;
    lv_fs_if_init();
    assert(registrations == 1 && registered == driver);
    assert(!driver->ready_cb(driver));
    assert(!driver->open_cb(driver, "/file", LV_FS_MODE_RD));
    assert(!driver->dir_open_cb(driver, "/"));

    assert(tf.init());
    assert(driver->ready_cb(driver));
    SD.put("/folder/data.bin", "abcdefgh");
    auto both = static_cast<lv_fs_mode_t>(LV_FS_MODE_RD | LV_FS_MODE_WR);
    void* file = driver->open_cb(driver, "folder/data.bin", both);
    assert(file);
    uint32_t count = 999;
    char buffer[16] = {};
    assert(driver->read_cb(driver, file, buffer, 3, &count) == LV_FS_RES_OK);
    assert(count == 3 && std::string(buffer, 3) == "abc");
    uint32_t position = 999;
    assert(driver->tell_cb(driver, file, &position) == LV_FS_RES_OK && position == 3);
    assert(driver->seek_cb(driver, file, 2, LV_FS_SEEK_CUR) == LV_FS_RES_OK);
    assert(driver->tell_cb(driver, file, &position) == LV_FS_RES_OK && position == 5);
    assert(driver->write_cb(driver, file, "XY", 2, &count) == LV_FS_RES_OK && count == 2);
    assert(*SD.files["/folder/data.bin"] == "abcdeXYh");
    assert(driver->seek_cb(driver, file, 0, LV_FS_SEEK_END) == LV_FS_RES_OK);
    assert(driver->tell_cb(driver, file, &position) == LV_FS_RES_OK && position == 8);
    assert(driver->read_cb(driver, file, buffer, sizeof(buffer), &count) == LV_FS_RES_OK && count == 0);
    assert(driver->seek_cb(driver, file, 0, LV_FS_SEEK_SET) == LV_FS_RES_OK);
    assert(driver->read_cb(driver, file, buffer, sizeof(buffer), nullptr) == LV_FS_RES_OK);
    assert(std::string(buffer, 8) == "abcdeXYh");
    assert(driver->read_cb(driver, file, nullptr, 0, &count) == LV_FS_RES_OK && count == 0);
    assert(driver->read_cb(driver, file, nullptr, 1, &count) == LV_FS_RES_INV_PARAM && count == 0);
    assert(driver->tell_cb(driver, file, nullptr) == LV_FS_RES_INV_PARAM);
    assert(driver->seek_cb(driver, file, 0, static_cast<lv_fs_whence_t>(3)) == LV_FS_RES_INV_PARAM);
    assert(driver->close_cb(driver, file) == LV_FS_RES_OK);

    file = driver->open_cb(driver, "/folder/data.bin", LV_FS_MODE_WR);
    assert(file);
    assert(driver->read_cb(driver, file, buffer, 1, &count) == LV_FS_RES_DENIED && count == 0);
    assert(driver->write_cb(driver, file, "!", 1, &count) == LV_FS_RES_OK);
    assert(*SD.files["/folder/data.bin"] == "!bcdeXYh"); // Original OPEN_ALWAYS is preserved.
    assert(driver->close_cb(driver, file) == LV_FS_RES_OK);
    file = driver->open_cb(driver, "new", both);
    assert(file);
    assert(driver->write_cb(driver, file, "created", 7, nullptr) == LV_FS_RES_OK);
    assert(*SD.files["/new"] == "created");
    assert(driver->close_cb(driver, file) == LV_FS_RES_OK);
    file = driver->open_cb(driver, "new", LV_FS_MODE_RD);
    assert(file);
    assert(driver->write_cb(driver, file, "x", 1, &count) == LV_FS_RES_DENIED && count == 0);
    assert(driver->close_cb(driver, file) == LV_FS_RES_OK);

    SD.readError = true;
    file = driver->open_cb(driver, "new", LV_FS_MODE_RD);
    assert(file);
    assert(driver->read_cb(driver, file, buffer, 1, &count) == LV_FS_RES_HW_ERR && count == 0);
    assert(driver->close_cb(driver, file) == LV_FS_RES_OK);
    SD.readError = false;
    SD.maxWrite = 2;
    file = driver->open_cb(driver, "new", both);
    assert(file);
    assert(driver->write_cb(driver, file, "ABCD", 4, &count) == LV_FS_RES_HW_ERR && count == 2);
    assert(driver->close_cb(driver, file) == LV_FS_RES_OK);
    SD.maxWrite = static_cast<size_t>(-1);

    assert(!driver->open_cb(driver, "missing", LV_FS_MODE_RD));
    assert(!driver->open_cb(driver, nullptr, LV_FS_MODE_RD));
    assert(!driver->open_cb(driver, "new", static_cast<lv_fs_mode_t>(0)));
    const std::string tooLong(LV_FS_MAX_PATH_LENGTH, 'x');
    assert(!driver->open_cb(driver, tooLong.c_str(), LV_FS_MODE_RD));
    assert(driver->close_cb(driver, nullptr) == LV_FS_RES_INV_PARAM);
    assert(driver->read_cb(driver, nullptr, buffer, 1, &count) == LV_FS_RES_INV_PARAM);

    SD.directories.insert("/");
    SD.directories.insert("/folder");
    SD.directories.insert("/folder/sub");
    SD.directories.insert("/folder/.");
    SD.directories.insert("/folder/..");
    SD.entries["/folder"] = {"/folder/.", "/folder/..", "/folder/data.bin", "/folder/sub"};
    assert(!driver->open_cb(driver, "/folder", LV_FS_MODE_RD));
    assert(!driver->dir_open_cb(driver, "/new"));
    assert(!driver->dir_open_cb(driver, "/missing"));
    void* directory = driver->dir_open_cb(driver, "folder");
    assert(directory);
    char filename[64];
    assert(driver->dir_read_cb(driver, directory, filename, sizeof(filename)) == LV_FS_RES_OK);
    assert(std::string(filename) == "data.bin");
    assert(driver->dir_read_cb(driver, directory, filename, sizeof(filename)) == LV_FS_RES_OK);
    assert(std::string(filename) == "/sub");
    assert(driver->dir_read_cb(driver, directory, filename, sizeof(filename)) == LV_FS_RES_OK);
    assert(filename[0] == '\0');
    assert(driver->dir_close_cb(driver, directory) == LV_FS_RES_OK);
    directory = driver->dir_open_cb(driver, "/folder");
    assert(directory);
    // Callback must honor fn_len without writing outside the caller's buffer.
    char small[3] = {'a', 'b', 'C'};
    assert(driver->dir_read_cb(driver, directory, small, 2) == LV_FS_RES_INV_PARAM);
    assert(small[0] == '\0' && small[2] == 'C');
    assert(driver->dir_read_cb(driver, directory, small, 0) == LV_FS_RES_INV_PARAM);
    assert(driver->dir_close_cb(driver, directory) == LV_FS_RES_OK);
    directory = driver->dir_open_cb(driver, "");
    assert(directory);
    assert(driver->dir_close_cb(driver, directory) == LV_FS_RES_OK);

    file = driver->open_cb(driver, "new", both);
    directory = driver->dir_open_cb(driver, "/folder");
    assert(file && directory);
    tf.end();
    assert(!driver->ready_cb(driver));
    assert(driver->read_cb(driver, file, buffer, 1, &count) == LV_FS_RES_HW_ERR && count == 0);
    assert(driver->write_cb(driver, file, buffer, 1, &count) == LV_FS_RES_HW_ERR && count == 0);
    assert(driver->seek_cb(driver, file, 0, LV_FS_SEEK_SET) == LV_FS_RES_HW_ERR);
    assert(driver->tell_cb(driver, file, &position) == LV_FS_RES_HW_ERR && position == 0);
    assert(driver->dir_read_cb(driver, directory, filename, sizeof(filename)) == LV_FS_RES_HW_ERR);
    assert(driver->close_cb(driver, file) == LV_FS_RES_OK);
    assert(driver->dir_close_cb(driver, directory) == LV_FS_RES_OK);
    std::cout << "lv_fs host callbacks passed against LVGL 9 API\n";
}
