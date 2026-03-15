#!/usr/bin/env python3
"""
Random receipt printer — each receipt is:
  1. Header text (from header_always_print.txt)
  2. A random PNG from printables/
  3. 5 random lines from slopyanus.txt

Press Enter to print. Ctrl+C to quit.
"""

import argparse
import random
import struct
import sys
from pathlib import Path


PRINTABLES_DIR = "printables"
HEADER_FILE = "header_always_print.txt"
LINES_FILE = "slopyanus.txt"
NUM_RANDOM_LINES = 5
DEFAULT_PRINTER = "XP-80C"

PAPER_TOTAL_PX = 576
MARGIN_PX = 40
PRINT_WIDTH_PX = PAPER_TOTAL_PX - 2 * MARGIN_PX


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


def margin_commands() -> bytes:
    GS = b"\x1d"
    cmds = bytearray()
    cmds += GS + b"L" + struct.pack("<H", MARGIN_PX)
    cmds += GS + b"W" + struct.pack("<H", PRINT_WIDTH_PX)
    return bytes(cmds)


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


def encode_text(text: str) -> bytes:
    return text.encode("cp437", errors="replace")


def build_receipt(folder: Path, header_text: str, all_lines: list[str]) -> bytes:
    ESC = b"\x1b"
    GS = b"\x1d"

    payload = bytearray()
    payload += ESC + b"@"          # initialize
    payload += margin_commands()
    payload += ESC + b"t\x00"      # code table PC437

    # --- header ---
    payload += encode_text(header_text.rstrip("\n"))
    payload += b"\n\n"

    # --- random PNG ---
    pngs = sorted(f for f in folder.iterdir() if f.suffix.lower() == ".png")
    if pngs:
        chosen_png = random.choice(pngs)
        print(f"  image: {chosen_png.name}")
        payload += image_to_escpos_raster(chosen_png)
        payload += b"\n\n"
    else:
        print("  (no PNGs found, skipping image)")

    # --- 5 random lines ---
    if all_lines:
        picks = random.sample(all_lines, min(NUM_RANDOM_LINES, len(all_lines)))
        for line in picks:
            payload += encode_text(line)
            payload += b"\n"

    # --- feed and cut ---
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
        description="Press Enter to print a random composite receipt"
    )
    parser.add_argument(
        "-p", "--printer",
        default=DEFAULT_PRINTER,
        help=f"Printer name (default: {DEFAULT_PRINTER})",
    )
    parser.add_argument(
        "-d", "--dir",
        default=PRINTABLES_DIR,
        help=f"folder with PNGs, header, and lines file (default: {PRINTABLES_DIR})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available printers and exit",
    )
    args = parser.parse_args()

    if args.list:
        if sys.platform == "win32":
            for name in list_windows_printers():
                print(f"  {name}")
        else:
            import subprocess
            subprocess.run(["lpstat", "-p", "-d"])
        return

    folder = Path(args.dir)
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(1)

    header_path = folder / HEADER_FILE
    if not header_path.exists():
        print(f"Header file not found: {header_path}")
        sys.exit(1)
    header_text = header_path.read_text(encoding="utf-8")

    lines_path = folder / LINES_FILE
    if not lines_path.exists():
        print(f"Lines file not found: {lines_path}")
        sys.exit(1)
    all_lines = [l for l in lines_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    pngs = sorted(f for f in folder.iterdir() if f.suffix.lower() == ".png")
    print(f"Header:  {header_path.name}")
    print(f"Images:  {len(pngs)} PNGs")
    print(f"Lines:   {len(all_lines)} from {lines_path.name} (picking {NUM_RANDOM_LINES} per receipt)")
    print(f"Printer: {args.printer}")
    print()
    print("Press ENTER to print a receipt (Ctrl+C to quit)")
    print()

    try:
        while True:
            input()
            data = build_receipt(folder, header_text, all_lines)
            send_to_printer(data, args.printer)
            print("  Printed!\n")
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
