#include "lv_port_fatfs.h"
#include "lvgl.h"
#include "sd_card.h"
#include <new>
#include <string.h>

namespace
{
constexpr char kDriveLetter = 'S';

struct FileHandle
{
    File file;
    lv_fs_mode_t mode;
};

bool makeAbsolutePath(const char* path, char* output, size_t capacity)
{
    if (!path) return false;
    const size_t length = strlen(path);
    const size_t prefix = path[0] == '/' ? 0 : 1;
    if (length + prefix >= capacity) return false;
    if (prefix) output[0] = '/';
    memcpy(output + prefix, path, length + 1);
    return true;
}

bool fsReady(lv_fs_drv_t*)
{
    return tf.isMounted();
}

lv_fs_res_t checkFile(const FileHandle* handle)
{
    if (!handle) return LV_FS_RES_INV_PARAM;
    if (!tf.isMounted()) return LV_FS_RES_HW_ERR;
    return handle->file ? LV_FS_RES_OK : LV_FS_RES_FS_ERR;
}

void* fsOpen(lv_fs_drv_t*, const char* path, lv_fs_mode_t mode)
{
    if (!tf.isMounted()) return nullptr;
    if (mode != LV_FS_MODE_RD && mode != LV_FS_MODE_WR &&
        mode != (LV_FS_MODE_RD | LV_FS_MODE_WR)) return nullptr;

    char absolutePath[LV_FS_MAX_PATH_LENGTH];
    if (!makeAbsolutePath(path, absolutePath, sizeof(absolutePath))) return nullptr;
    FileHandle* handle = new (std::nothrow) FileHandle;
    if (!handle) return nullptr;
    handle->mode = mode;
    // Preserve the original FA_OPEN_ALWAYS behavior: writing starts at byte zero
    // without truncating an existing file. New files use read/write creation.
    const char* openMode = "r";
    if (mode & LV_FS_MODE_WR) openMode = SD.exists(absolutePath) ? "r+" : "w+";
    handle->file = SD.open(absolutePath, openMode);
    if (!handle->file || handle->file.isDirectory())
    {
        handle->file.close();
        delete handle;
        return nullptr;
    }
    return handle;
}

lv_fs_res_t fsClose(lv_fs_drv_t*, void* filePointer)
{
    FileHandle* handle = static_cast<FileHandle*>(filePointer);
    if (!handle) return LV_FS_RES_INV_PARAM;
    // Always release the handle, including after an SD unmount.
    handle->file.close();
    delete handle;
    return LV_FS_RES_OK;
}

lv_fs_res_t fsRead(lv_fs_drv_t*, void* filePointer, void* buffer, uint32_t requested, uint32_t* bytesRead)
{
    if (bytesRead) *bytesRead = 0;
    FileHandle* handle = static_cast<FileHandle*>(filePointer);
    lv_fs_res_t result = checkFile(handle);
    if (result != LV_FS_RES_OK) return result;
    if (!(handle->mode & LV_FS_MODE_RD)) return LV_FS_RES_DENIED;
    if (!buffer && requested) return LV_FS_RES_INV_PARAM;
    if (!requested) return LV_FS_RES_OK;

    const size_t count = handle->file.read(static_cast<uint8_t*>(buffer), requested);
    if (count > requested) return LV_FS_RES_HW_ERR;
    if (bytesRead) *bytesRead = static_cast<uint32_t>(count);
    if (!count && handle->file.position() < handle->file.size()) return LV_FS_RES_HW_ERR;
    return LV_FS_RES_OK;
}

lv_fs_res_t fsWrite(lv_fs_drv_t*, void* filePointer, const void* buffer,
                   uint32_t requested, uint32_t* bytesWritten)
{
    if (bytesWritten) *bytesWritten = 0;
    FileHandle* handle = static_cast<FileHandle*>(filePointer);
    lv_fs_res_t result = checkFile(handle);
    if (result != LV_FS_RES_OK) return result;
    if (!(handle->mode & LV_FS_MODE_WR)) return LV_FS_RES_DENIED;
    if (!buffer && requested) return LV_FS_RES_INV_PARAM;
    if (!requested) return LV_FS_RES_OK;

    const size_t count = handle->file.write(static_cast<const uint8_t*>(buffer), requested);
    if (count > requested) return LV_FS_RES_HW_ERR;
    if (bytesWritten) *bytesWritten = static_cast<uint32_t>(count);
    return count == requested ? LV_FS_RES_OK : LV_FS_RES_HW_ERR;
}

lv_fs_res_t fsSeek(lv_fs_drv_t*, void* filePointer, uint32_t position, lv_fs_whence_t whence)
{
    FileHandle* handle = static_cast<FileHandle*>(filePointer);
    lv_fs_res_t result = checkFile(handle);
    if (result != LV_FS_RES_OK) return result;
    bool success;
    switch (whence)
    {
        case LV_FS_SEEK_SET: success = handle->file.seek(position, fs::SeekSet); break;
        case LV_FS_SEEK_CUR: success = handle->file.seek(position, fs::SeekCur); break;
        case LV_FS_SEEK_END: success = handle->file.seek(position, fs::SeekEnd); break;
        default: return LV_FS_RES_INV_PARAM;
    }
    return success ? LV_FS_RES_OK : LV_FS_RES_FS_ERR;
}

lv_fs_res_t fsTell(lv_fs_drv_t*, void* filePointer, uint32_t* position)
{
    if (!position) return LV_FS_RES_INV_PARAM;
    *position = 0;
    FileHandle* handle = static_cast<FileHandle*>(filePointer);
    lv_fs_res_t result = checkFile(handle);
    if (result != LV_FS_RES_OK) return result;
    *position = handle->file.position();
    return LV_FS_RES_OK;
}

void* fsDirOpen(lv_fs_drv_t*, const char* path)
{
    if (!tf.isMounted()) return nullptr;
    char absolutePath[LV_FS_MAX_PATH_LENGTH];
    if (!makeAbsolutePath(path, absolutePath, sizeof(absolutePath))) return nullptr;
    File* directory = new (std::nothrow) File;
    if (!directory) return nullptr;
    *directory = SD.open(absolutePath);
    if (!*directory || !directory->isDirectory())
    {
        directory->close();
        delete directory;
        return nullptr;
    }
    return directory;
}

lv_fs_res_t fsDirRead(lv_fs_drv_t*, void* directoryPointer, char* filename, uint32_t capacity)
{
    if (!filename || !capacity) return LV_FS_RES_INV_PARAM;
    filename[0] = '\0';
    if (!directoryPointer) return LV_FS_RES_INV_PARAM;
    if (!tf.isMounted()) return LV_FS_RES_HW_ERR;
    File* directory = static_cast<File*>(directoryPointer);
    if (!*directory || !directory->isDirectory()) return LV_FS_RES_FS_ERR;

    while (true)
    {
        File entry = directory->openNextFile();
        if (!entry) return LV_FS_RES_OK; // Empty name signals end of directory.
        const char* name = entry.name();
        if (!name)
        {
            entry.close();
            return LV_FS_RES_FS_ERR;
        }
        // name() is normally a basename; tolerate implementations returning paths.
        const char* slash = strrchr(name, '/');
        if (slash) name = slash + 1;
        if (!name[0] || strcmp(name, ".") == 0 || strcmp(name, "..") == 0)
        {
            entry.close();
            continue;
        }
        const size_t prefix = entry.isDirectory() ? 1 : 0;
        const size_t length = strlen(name);
        if (length + prefix >= capacity)
        {
            entry.close();
            return LV_FS_RES_INV_PARAM;
        }
        if (prefix) filename[0] = '/';
        memcpy(filename + prefix, name, length + 1);
        entry.close();
        return LV_FS_RES_OK;
    }
}

lv_fs_res_t fsDirClose(lv_fs_drv_t*, void* directoryPointer)
{
    File* directory = static_cast<File*>(directoryPointer);
    if (!directory) return LV_FS_RES_INV_PARAM;
    directory->close();
    delete directory;
    return LV_FS_RES_OK;
}
}

void lv_fs_if_init(void)
{
    // LVGL 9 saves this pointer; a stack-local descriptor would dangle.
    static lv_fs_drv_t driver;
    if (lv_fs_get_drv(kDriveLetter)) return;
    lv_fs_drv_init(&driver);
    driver.letter = kDriveLetter;
    driver.ready_cb = fsReady;
    driver.open_cb = fsOpen;
    driver.close_cb = fsClose;
    driver.read_cb = fsRead;
    driver.write_cb = fsWrite;
    driver.seek_cb = fsSeek;
    driver.tell_cb = fsTell;
    driver.dir_open_cb = fsDirOpen;
    driver.dir_read_cb = fsDirRead;
    driver.dir_close_cb = fsDirClose;
    lv_fs_drv_register(&driver);
}
