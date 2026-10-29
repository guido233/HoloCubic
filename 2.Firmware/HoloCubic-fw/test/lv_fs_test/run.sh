#!/bin/sh
set -eu
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
firmware_dir=$(CDPATH= cd -- "$test_dir/../.." && pwd)
lvgl_include="$firmware_dir/.pio/libdeps/naive/lvgl/include"
if [ ! -f "$lvgl_include/lvgl/fs/lv_fs.h" ]; then
    lvgl_include=
    for candidate in "$firmware_dir"/.pio/libdeps/*/lvgl/include; do
        if [ -f "$candidate/lvgl/fs/lv_fs.h" ]; then
            lvgl_include=$candidate
            break
        fi
    done
fi
if [ -z "$lvgl_include" ]; then
    echo "LVGL dependency missing; install a firmware environment's dependencies first." >&2
    exit 1
fi
test_binary=$(mktemp /tmp/holocubic-lv-fs-test.XXXXXX)
trap 'rm -f "$test_binary"' EXIT HUP INT TERM
c++ -std=c++11 -Wall -Wextra -Werror -pedantic \
    -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -DLV_CONF_SKIP \
    -I"$test_dir/stubs" -I"$firmware_dir/include" \
    -I"$lvgl_include" \
    "$firmware_dir/src/sd_card.cpp" "$firmware_dir/src/lv_port_fatfs.cpp" \
    "$test_dir/main.cpp" -o "$test_binary"
"$test_binary"
