#!/bin/sh
set -eu
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
firmware_dir=$(CDPATH= cd -- "$test_dir/../.." && pwd)
test_binary=$(mktemp /tmp/holocubic-sd-test.XXXXXX)
trap 'rm -f "$test_binary"' EXIT HUP INT TERM
c++ -std=c++11 -Wall -Wextra -Werror -pedantic \
    -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
    -I"$test_dir/stubs" -I"$firmware_dir/include" \
    "$firmware_dir/src/sd_card.cpp" "$test_dir/main.cpp" -o "$test_binary"
"$test_binary"
