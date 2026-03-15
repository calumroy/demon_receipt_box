#!/usr/bin/env python3
"""
Random receipt printer — picks a random .txt or .png from a folder
and prints it to a USB ESC/POS thermal printer each time you hit Enter.
"""

import argparse
import random
import struct
import sys
from pathlib import Path


PRINTABLES_DIR = "printables"
PAPER_WIDTH_PX = 384  # 58mm paper = 384 dots; 80mm paper = 576 dots
PAPER_WIDTH_CHARS = 32  # 58mm paper; 48 for 80mm


def list_windows_printers():
    try:
        import win32print
    except ImportError:
        print("pywin32 not installed. Run: pip install pywin32")
        sys.exit(1)
    return [
        p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
    ]


def get_printable_files(folder: Path) -> list[Path]:
    exts = {".txt", ".png"}
    return sorted(f for f in folder.iterdir() if f.suffix.lower() in exts)


def image_to_escpos_raster(image_path: Path) -> bytes:
    """Convert a PNG to ESC/POS raster bit-image bytes."""
    from PIL import Image

    img = Image.open(image_path)

    # Scale to fit paper width, maintaining aspect ratio
    if img.width != PAPER_WIDTH_PX:
        ratio = PAPER_WIDTH_PX / img.width
        new_h = int(img.height * ratio)
        img = img.resize((PAPER_WIDTH_PX, new_h), Image.LANCZOS)

    img = img.convert("1")  # 1-bit monochrome, dithered

    width_bytes = (img.width + 7) // 8
    height = img.height
    pixels = img.load()

    data = bytearray()
    for y in range(height):
        row = bytearray(width_bytes)
        for x in range(img.width):
            if pixels[x, y] == 0:  # black pixel
                row[x // 8] |= 0x80 >> (x % 8)
        data.extend(row)

    # GS v 0 — raster bit image
    # m=0 (normal), xL xH = width_bytes, yL yH = height
    GS = b"\x1d"
    header = GS + b"v0\x00"
    header += struct.pack("<HH", width_bytes, height)

    return header + bytes(data)


def build_text_payload(text: str) -> bytes:
    ESC = b"\x1b"
    payload = bytearray()
    payload += ESC + b"@"          # initialize
    payload += ESC + b"t\x00"      # code table PC437
    payload += text.encode("cp437", errors="replace")
    return bytes(payload)


def build_image_payload(image_path: Path) -> bytes:
    ESC = b"\x1b"
    payload = bytearray()
    payload += ESC + b"@"          # initialize
    payload += image_to_escpos_raster(image_path)
    return bytes(payload)


def send_to_printer(data: bytes, printer_name: str):
    import win32print

    GS = b"\x1d"
    footer = b"\n\n\n\n" + GS + b"V\x41\x03"  # feed + partial cut

    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("receipt", None, "RAW"))
        win32print.StartPagePrinter(handle)
        win32print.WritePrinter(handle, data + footer)
        win32print.EndPagePrinter(handle)
        win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


def print_random(folder: Path, printer_name: str):
    files = get_printable_files(folder)
    if not files:
        print(f"No .txt or .png files in {folder}/")
        return

    chosen = random.choice(files)
    print(f"  >> {chosen.name}")

    if chosen.suffix.lower() == ".png":
        data = build_image_payload(chosen)
    else:
        text = chosen.read_text(encoding="utf-8")
        data = build_text_payload(text)

    send_to_printer(data, printer_name)
    print("  Printed!")


def main():
    parser = argparse.ArgumentParser(
        description="Press Enter to print a random receipt from a folder"
    )
    parser.add_argument(
        "-p", "--printer",
        help="Windows printer name (omit to list available printers)",
    )
    parser.add_argument(
        "-d", "--dir",
        default=PRINTABLES_DIR,
        help=f"folder of .txt/.png files (default: {PRINTABLES_DIR})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available printers and exit",
    )
    args = parser.parse_args()

    if args.list:
        for name in list_windows_printers():
            print(f"  {name}")
        return

    if not args.printer:
        printers = list_windows_printers()
        if not printers:
            print("No printers found. Plug in your thermal printer.")
            sys.exit(1)
        print("Available printers:")
        for i, name in enumerate(printers):
            print(f"  [{i}] {name}")
        print()
        print("Run again with: python print_receipt.py -p \"YourPrinterName\"")
        sys.exit(0)

    folder = Path(args.dir)
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(1)

    files = get_printable_files(folder)
    print(f"Loaded {len(files)} printable files from {folder}/")
    for f in files:
        print(f"  {f.name}")
    print()
    print(f"Printer: {args.printer}")
    print("Press ENTER to print a random receipt (Ctrl+C to quit)")
    print()

    try:
        while True:
            input()
            print_random(folder, args.printer)
            print()
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
