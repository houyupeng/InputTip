from __future__ import annotations

import argparse
import struct
from pathlib import Path


CURSOR_MAP = {
    "Arrow": "aero_arrow.cur",
    "IBeam": "beam_m.cur",
    "Wait": "busy_m.cur",
    "Crosshair": "cross_m.cur",
    "UpArrow": "aero_up.cur",
    "SizeNWSE": "aero_nwse.cur",
    "SizeNESW": "aero_nesw.cur",
    "SizeWE": "aero_ew.cur",
    "SizeNS": "aero_ns.cur",
    "SizeAll": "aero_move.cur",
    "No": "aero_unavail.cur",
    "Hand": "aero_link.cur",
    "AppStarting": "wait_m.cur",
    "Help": "aero_helpsel.cur",
    "Pin": "aero_pin.cur",
    "Person": "aero_person.cur",
    "NWPen": "aero_pen.cur",
}

COLORS = {
    "red": (235, 44, 44),
    "blue": (50, 105, 245),
    "green": (30, 155, 80),
}


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def i32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def row_stride(width: int, bits: int) -> int:
    return ((width * bits + 31) // 32) * 4


def read_mask_bit(buf: bytes, stride: int, x: int, y: int) -> int:
    byte = buf[y * stride + x // 8]
    shift = 7 - (x % 8)
    return (byte >> shift) & 1


def palette_entry(dib: bytes, palette_offset: int, index: int) -> tuple[int, int, int, int]:
    pos = palette_offset + index * 4
    b, g, r, _ = dib[pos : pos + 4]
    return r, g, b, 255


def decode_dib(dib: bytes) -> tuple[bytearray, int, int]:
    header_size = u32(dib, 0)
    width = i32(dib, 4)
    raw_height = i32(dib, 8)
    height = abs(raw_height) // 2
    planes = u16(dib, 12)
    bit_count = u16(dib, 14)
    compression = u32(dib, 16)
    colors_used = u32(dib, 32) if header_size >= 40 else 0
    if planes != 1 or compression != 0:
        raise ValueError(f"unsupported DIB: planes={planes} compression={compression}")

    palette_count = colors_used
    if palette_count == 0 and bit_count <= 8:
        palette_count = 1 << bit_count

    palette_offset = header_size
    pixel_offset = header_size + palette_count * 4
    xor_stride = row_stride(width, bit_count)
    and_offset = pixel_offset + xor_stride * height
    and_stride = row_stride(width, 1)
    pixels = bytearray(width * height * 4)

    for y in range(height):
        src_y = height - 1 - y if raw_height > 0 else y
        for x in range(width):
            r = g = b = 0
            a = 255
            base = pixel_offset + src_y * xor_stride
            if bit_count == 32:
                p = base + x * 4
                b, g, r, a = dib[p : p + 4]
                if a == 0:
                    mask = read_mask_bit(dib[and_offset:], and_stride, x, src_y)
                    if mask:
                        a = 0
            elif bit_count == 24:
                p = base + x * 3
                b, g, r = dib[p : p + 3]
                mask = read_mask_bit(dib[and_offset:], and_stride, x, src_y)
                if mask:
                    a = 0
            elif bit_count == 8:
                idx = dib[base + x]
                r, g, b, a = palette_entry(dib, palette_offset, idx)
                mask = read_mask_bit(dib[and_offset:], and_stride, x, src_y)
                if mask:
                    a = 0
            elif bit_count == 4:
                byte = dib[base + x // 2]
                idx = (byte >> 4) if x % 2 == 0 else (byte & 0x0F)
                r, g, b, a = palette_entry(dib, palette_offset, idx)
                mask = read_mask_bit(dib[and_offset:], and_stride, x, src_y)
                if mask:
                    a = 0
            elif bit_count == 1:
                xor_bit = read_mask_bit(dib[pixel_offset:], xor_stride, x, src_y)
                and_bit = read_mask_bit(dib[and_offset:], and_stride, x, src_y)
                if and_bit == 1 and xor_bit == 0:
                    r, g, b, a = 0, 0, 0, 0
                elif and_bit == 0 and xor_bit == 0:
                    r, g, b, a = 0, 0, 0, 255
                elif and_bit == 0 and xor_bit == 1:
                    r, g, b, a = 255, 255, 255, 255
                else:
                    r, g, b, a = 0, 0, 0, 255
            else:
                raise ValueError(f"unsupported bit depth: {bit_count}")

            out = (y * width + x) * 4
            pixels[out : out + 4] = bytes((b, g, r, a))

    return pixels, width, height


def recolor_pixels(pixels: bytearray, rgb: tuple[int, int, int], preserve_white: bool = False) -> None:
    rr, gg, bb = rgb
    for p in range(0, len(pixels), 4):
        b, g, r = pixels[p : p + 3]
        a = pixels[p + 3]
        if a == 0:
            continue
        if preserve_white and min(r, g, b) > 220:
            continue
        pixels[p] = bb
        pixels[p + 1] = gg
        pixels[p + 2] = rr


def thicken_visible_pixels(pixels: bytearray, width: int, height: int, radius: int = 1) -> bytearray:
    out = bytearray(pixels)
    for y in range(height):
        for x in range(width):
            p = (y * width + x) * 4
            if pixels[p + 3] == 0:
                continue
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx = x + dx
                    ny = y + dy
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    np = (ny * width + nx) * 4
                    if out[np + 3] == 0:
                        out[np : np + 4] = pixels[p : p + 4]
    return out


def encode_32bit_dib(pixels: bytearray, width: int, height: int) -> bytes:
    header = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height * 2,
        1,
        32,
        0,
        width * height * 4,
        0,
        0,
        0,
        0,
    )
    out_pixels = bytearray()
    for y in range(height - 1, -1, -1):
        row = y * width * 4
        out_pixels.extend(pixels[row : row + width * 4])
    mask = bytes(row_stride(width, 1) * height)
    return header + bytes(out_pixels) + mask


def recolor_cur(source: Path, dest: Path, rgb: tuple[int, int, int], thicken: bool = False) -> None:
    data = source.read_bytes()
    if data[:4] != b"\x00\x00\x02\x00":
        raise ValueError(f"not a cursor file: {source}")
    count = u16(data, 4)
    entries = []
    images = []
    for i in range(count):
        entry_offset = 6 + i * 16
        width_byte, height_byte, colors, reserved = data[entry_offset : entry_offset + 4]
        hotspot_x = u16(data, entry_offset + 4)
        hotspot_y = u16(data, entry_offset + 6)
        size = u32(data, entry_offset + 8)
        image_offset = u32(data, entry_offset + 12)
        dib = data[image_offset : image_offset + size]
        pixels, width, height = decode_dib(dib)
        preserve_white = dest.stem in {"No", "SizeAll", "SizeWE", "SizeNS", "SizeNWSE", "SizeNESW"}
        recolor_pixels(pixels, rgb, preserve_white=preserve_white)
        if thicken:
            pixels = thicken_visible_pixels(pixels, width, height, 1)
        new_dib = encode_32bit_dib(pixels, width, height)
        entries.append((width_byte, height_byte, colors, reserved, hotspot_x, hotspot_y, len(new_dib)))
        images.append(new_dib)

    header_size = 6 + count * 16
    offset = header_size
    out = bytearray()
    out.extend(struct.pack("<HHH", 0, 2, count))
    for width_byte, height_byte, colors, reserved, hotspot_x, hotspot_y, size in entries:
        out.extend(bytes((width_byte, height_byte, colors, reserved)))
        out.extend(struct.pack("<HHII", hotspot_x, hotspot_y, size, offset))
        offset += size
    for image in images:
        out.extend(image)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(out))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows-cursors", default=r"C:\Windows\Cursors")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    source_root = Path(args.windows_cursors)
    output_root = Path(args.output_root)
    for color_name, rgb in COLORS.items():
        theme_dir = output_root / f"native-color-{color_name}"
        theme_dir.mkdir(parents=True, exist_ok=True)
        for target_name, source_name in CURSOR_MAP.items():
            source = source_root / source_name
            dest = theme_dir / f"{target_name}.cur"
            recolor_cur(source, dest, rgb, thicken=(target_name == "IBeam"))
        print(theme_dir)


if __name__ == "__main__":
    main()
