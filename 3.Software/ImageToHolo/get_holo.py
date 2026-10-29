#!/usr/bin/env python3
"""Batch-convert original raster images to LVGL 9.6 RGB565 image resources."""

import argparse
from pathlib import Path
import re
import sys


def parse_background(value):
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("背景色应为 RRGGBB，例如 000000 或 FFFFFF")
    value = value.lstrip("#")
    return tuple(int(value[offset:offset + 2], 16) for offset in (0, 2, 4))


def main(argv=None):
    if sys.version_info < (3, 11):
        print("需要 Python 3.11 或更新版本；请安装 requirements.txt 中锁定的 Pillow。", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(
        description="将原始图片批量转为 LVGL 9.6 的 RGB565 .bin；默认透明背景合成为黑色。",
        epilog="默认在原图旁输出 name.lv9.bin；旧版输出 name.lv7.bin。已有 .bin 不能作为输入。")
    parser.add_argument("images", nargs="+", type=Path, help="PNG/JPEG/BMP/WebP 原始图片，可同时指定多张")
    parser.add_argument("--legacy-v7", action="store_true", help="显式生成 LVGL 7 的 RGB565 旧格式（4 字节头）")
    parser.add_argument("--background", type=parse_background, default=(0, 0, 0), metavar="RRGGBB",
                        help="透明像素的背景色，默认 000000")
    parser.add_argument("--output-dir", type=Path, help="输出到指定目录，默认在各原图旁")
    parser.add_argument("--force", action="store_true", help="覆盖已有输出文件")
    args = parser.parse_args(argv)

    # Preflight the whole batch before creating files. In particular, passing a
    # v7/v9 .bin alongside source images must never silently mix resource sets.
    jobs = []
    destinations = set()
    suffix = ".lv7.bin" if args.legacy_v7 else ".lv9.bin"
    for source in args.images:
        if source.suffix.lower() == ".bin":
            parser.error(f"不接受已有 .bin：{source}。请用原始图片重新生成对应 LVGL 版本的资源。")
        if not source.is_file():
            parser.error(f"找不到原始图片：{source}")
        destination = (args.output_dir or source.parent) / (source.stem + suffix)
        resolved = destination.resolve()
        if resolved in destinations:
            parser.error(f"多张输入会写入同一输出文件：{destination}")
        destinations.add(resolved)
        if destination.exists() and (not args.force or not destination.is_file()):
            parser.error(f"输出已存在：{destination}；确认要覆盖文件时可加 --force。")
        jobs.append((source, destination))

    try:
        from convertor.core import convert_raster
    except ImportError as error:
        print(f"图片依赖不可用：{error}。请运行 python -m pip install -r requirements.txt", file=sys.stderr)
        return 2

    failed = False
    for source, destination in jobs:
        try:
            data = convert_raster(source, legacy_v7=args.legacy_v7, background=args.background)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also protects against a collision after the
            # preflight. Raster inputs are never opened for writing.
            with destination.open("wb" if args.force else "xb") as output:
                output.write(data)
            print(f"{source} -> {destination} ({len(data)} bytes)")
        except (OSError, ValueError) as error:
            failed = True
            print(f"转换失败 {source}：{error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
