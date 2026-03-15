#!/usr/bin/env python3
"""
Print a random PNG from the printables folder on a thermal receipt printer.
Press Enter to print. Ctrl+C to quit.
"""

import argparse
import random
import struct
import sys
from pathlib import Path


PRINTABLES_DIR = "printables"
DEFAULT_PRINTER = "XP-80C"

PRINT_WIDTH_PX = 576


def image_to_escpos_raster(image_path: Path) -> bytes:
    from PIL import Image

    img = Image.open(image_path)

    if img.width != PRINT_WIDTH_PX:
        ratio = PRINT_WIDTH_PX / img.width
        new_h = int(img.height * ratio)
        img = img.resize((PRINT_WIDTH_PX, new_h), Image.LANCZOS)

    img = img.convert("1")

    width_bytes = (img.width + 7) // 8
    height = img.height
    pixels = img.load()

    data = bytearray()
    for y in range(height):
        row = bytearray(width_bytes)
        for x in range(img.width):
            if pixels[x, y] == 0:
                row[x // 8] |= 0x80 >> (x % 8)
        data.extend(row)

    GS = b"\x1d"
    header = GS + b"v0\x00"
    header += struct.pack("<HH", width_bytes, height)

    return header + bytes(data)


def build_image_receipt(image_path: Path) -> bytes:
    ESC = b"\x1b"
    GS = b"\x1d"

    payload = bytearray()
    payload += ESC + b"@"

    payload += image_to_escpos_raster(image_path)

    payload += b"\n\n\n\n"
    payload += GS + b"V\x41\x03"

    return bytes(payload)


def send_to_printer(data: bytes, printer_name: str):
    if sys.platform == "win32":
        import win32print
        handle = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(handle, 1, ("receipt", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)
    else:
        import subprocess
        proc = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", "-"],
            input=data,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"lp failed (exit {proc.returncode}): {proc.stderr.decode()}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Press Enter to print a random PNG from the printables folder"
    )
    parser.add_argument(
        "-p", "--printer",
        default=DEFAULT_PRINTER,
        help=f"Printer name (default: {DEFAULT_PRINTER})",
    )
    parser.add_argument(
        "-d", "--dir",
        default=PRINTABLES_DIR,
        help=f"Folder with PNGs (default: {PRINTABLES_DIR})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available printers and exit",
    )
    args = parser.parse_args()

    if args.list:
        if sys.platform == "win32":
            import win32print
            for p in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            ):
                print(f"  {p[2]}")
        else:
            import subprocess
            subprocess.run(["lpstat", "-p", "-d"])
        return

    folder = Path(args.dir)
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(1)

    pngs = sorted(f for f in folder.iterdir() if f.suffix.lower() == ".png")
    if not pngs:
        print(f"No PNGs found in {folder}")
        sys.exit(1)

    print(f"Images:  {len(pngs)} PNGs in {folder}")
    print(f"Printer: {args.printer}")
    print()
    print("Press ENTER to print a random image (Ctrl+C to quit)")
    print()

    try:
        while True:
            input()
            chosen = random.choice(pngs)
            print(f"  Printing {chosen.name}...")
            data = build_image_receipt(chosen)
            send_to_printer(data, args.printer)
            print("  Done!\n")
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
