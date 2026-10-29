#!/bin/sh
# Host regression checks exercise the production sources with simulated hardware.
set -eu

test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
firmware_dir=$(CDPATH= cd -- "$test_dir/../.." && pwd)
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/holocubic-imu-test.XXXXXX")
trap 'rm -rf "$build_dir"' EXIT HUP INT TERM
test_cxx=${CXX:-c++}

for led_count in 1 2; do
    "$test_cxx" -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined \
        -DRGB_LED_NUM="$led_count" -I"$test_dir/stubs" -I"$firmware_dir/include" \
        "$test_dir/test.cpp" "$firmware_dir/src/imu.cpp" "$firmware_dir/src/rgb_led.cpp" \
        -o "$build_dir/test-$led_count"
    "$build_dir/test-$led_count"
done
