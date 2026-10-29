"""Small synthetic-image goldens for the LVGL image-file wire formats.

Run: python -m unittest discover -s test -v
No hardware, user images or third-party test runner is needed.
"""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from convertor.core import convert_raster, encode_legacy_v7_rgb565, encode_lvgl9_rgb565


class ImageConverterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="holocubic-image-test-")
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def source(self, name="image.png", color=(255, 0, 0)):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1, 1), color).save(path)
        return path

    def cli(self, *arguments):
        return subprocess.run([sys.executable, str(ROOT / "get_holo.py"),
                               *(str(arg) for arg in arguments)],
                              text=True, capture_output=True, check=False)

    def test_rgb_golden_and_exact_12_byte_header(self):
        image = Image.new("RGB", (3, 1))
        image.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        # magic, RGB565, flags, w=3, h=1, stride=6, reserved; then R/G/B LE.
        self.assertEqual(encode_lvgl9_rgb565(image), bytes.fromhex(
            "19 12 00 00 03 00 01 00 06 00 00 00 00 f8 e0 07 1f 00"))

    def test_odd_width_stride_and_second_row(self):
        image = Image.new("RGB", (3, 2))
        image.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255),
                       (255, 255, 255), (0, 0, 0), (128, 128, 128)])
        data = encode_lvgl9_rgb565(image)
        self.assertEqual(data[:12], bytes.fromhex("19 12 00 00 03 00 02 00 06 00 00 00"))
        self.assertEqual(data[12:], bytes.fromhex("00 f8 e0 07 1f 00 ff ff 00 00 10 84"))
        self.assertEqual(len(data), 12 + 6 * 2)

    def test_opaque_quantization_does_not_dim_boundary_values(self):
        image = Image.new("RGBA", (1, 1), (8, 4, 8, 255))
        self.assertEqual(encode_lvgl9_rgb565(image)[12:], bytes.fromhex("21 08"))

    def test_alpha_is_flattened_onto_black(self):
        image = Image.new("RGBA", (3, 1))
        image.putdata([(255, 0, 0, 128), (0, 0, 255, 0), (0, 255, 0, 255)])
        self.assertEqual(encode_lvgl9_rgb565(image)[12:], bytes.fromhex("00 80 00 00 e0 07"))

    def test_explicit_background(self):
        image = Image.new("RGBA", (1, 1), (0, 255, 0, 128))
        self.assertEqual(encode_lvgl9_rgb565(image, (255, 255, 255))[12:], bytes.fromhex("ef 7f"))

    def test_palette_transparency_is_resolved_before_rgb565(self):
        image = Image.new("P", (2, 1))
        image.putpalette([255, 0, 0, 0, 255, 0] + [0] * (768 - 6))
        image.putdata([0, 1])
        path = self.directory / "palette.png"
        image.save(path, transparency=0)
        self.assertEqual(convert_raster(path)[12:], bytes.fromhex("00 00 e0 07"))

    def test_grayscale_and_exif_orientation(self):
        self.assertEqual(encode_lvgl9_rgb565(Image.new("L", (1, 1), 128))[12:], bytes.fromhex("10 84"))
        path = self.directory / "oriented.jpg"
        exif = Image.Exif()
        exif[274] = 6  # rotate 90 degrees clockwise
        Image.new("RGB", (2, 1), "red").save(path, exif=exif)
        header = struct.unpack("<BBHHHHH", convert_raster(path)[:12])
        self.assertEqual(header[3:6], (1, 2, 2))

    def test_header_overflow_and_empty_images_are_rejected(self):
        for size in ((0, 1), (1, 0), (32768, 1), (1, 65536)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                encode_lvgl9_rgb565(Image.new("RGB", size))
        with self.assertRaises(ValueError):
            encode_legacy_v7_rgb565(Image.new("RGB", (2048, 1)))

    def test_legacy_is_explicit_four_byte_format(self):
        image = Image.new("RGB", (1, 1), "red")
        data = encode_legacy_v7_rgb565(image)
        self.assertEqual(data, bytes.fromhex("04 04 20 00 00 f8"))
        self.assertNotEqual(data[0], 0x19)
        path = self.source()
        result = self.cli("--legacy-v7", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.with_suffix(".lv7.bin").read_bytes(), data)
        self.assertFalse(path.with_suffix(".lv9.bin").exists())

    def test_cli_multiple_inputs_with_spaces_and_multidot_names(self):
        first = self.source("a red.test.png")
        second = self.source("b green.bmp", (0, 255, 0))
        result = self.cli(first, second)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(first.with_suffix(".lv9.bin").read_bytes()[12:], bytes.fromhex("00 f8"))
        self.assertEqual(second.with_suffix(".lv9.bin").read_bytes()[12:], bytes.fromhex("e0 07"))

    def test_binary_input_rejects_whole_batch_before_output(self):
        source = self.source()
        legacy = self.directory / "old.BIN"
        legacy.write_bytes(bytes.fromhex("04 04 20 00 00 f8"))
        result = self.cli(source, legacy)
        self.assertEqual(result.returncode, 2)
        self.assertIn(".bin", result.stderr)
        self.assertFalse(source.with_suffix(".lv9.bin").exists())
        with self.assertRaisesRegex(ValueError, "Existing .bin"):
            convert_raster(legacy)

    def test_existing_outputs_and_colliding_batch_names_are_protected(self):
        source = self.source()
        destination = source.with_suffix(".lv9.bin")
        destination.write_bytes(b"existing resource")
        result = self.cli(source)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(destination.read_bytes(), b"existing resource")
        result = self.cli("--force", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(destination.read_bytes()[:2], bytes.fromhex("19 12"))
        other = self.source("other/image.bmp")
        output = self.directory / "batch"
        result = self.cli("--output-dir", output, source, other)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_cli_invalid_source_and_background_report_failure(self):
        source = self.directory / "bad.png"
        source.write_bytes(b"not an image")
        result = self.cli(source)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(source.with_suffix(".lv9.bin").exists())
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.cli("--background", "oops", source).returncode, 2)

    def test_animated_sources_are_not_silently_truncated(self):
        path = self.directory / "animated.png"
        first = Image.new("RGB", (1, 1), "red")
        second = Image.new("RGB", (1, 1), "blue")
        first.save(path, save_all=True, append_images=[second], duration=100, loop=0)
        with self.assertRaisesRegex(ValueError, "Animated"):
            convert_raster(path)


if __name__ == "__main__":
    unittest.main()
