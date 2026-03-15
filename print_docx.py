#!/usr/bin/env python3
"""
Random .docx receipt printer — picks a random .docx from the printables
folder, renders it to images via docx2pdf + pdf2image, and prints it on a
thermal receipt printer as ESC/POS raster data.

Windows: uses docx2pdf (which calls Microsoft Word) and pdf2image + poppler.
Requires: pip install docx2pdf pdf2image Pillow pywin32
          + poppler for Windows (add poppler/Library/bin to PATH)

Press Enter to print. Ctrl+C to quit.
"""

import argparse
import random
import struct
import sys
import tempfile
from pathlib import Path


PRINTABLES_DIR = "printables"
DEFAULT_PRINTER = "XP-80C"

PAPER_TOTAL_PX = 576
MARGIN_PX = 40
PRINT_WIDTH_PX = PAPER_TOTAL_PX - 2 * MARGIN_PX
RENDER_DPI = 203


def list_printers():
    import win32print
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


def pil_image_to_escpos_raster(img) -> bytes:
    from PIL import Image

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


def docx_to_images(docx_path: Path) -> list:
    """Convert a .docx to a list of PIL Images via Word → PDF → poppler."""
    from docx2pdf import convert
    from pdf2image import convert_from_path

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / (docx_path.stem + ".pdf")
        convert(str(docx_path), str(pdf_path))

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF conversion produced no output: {pdf_path}")

        images = convert_from_path(str(pdf_path), dpi=RENDER_DPI)

    return images


def build_receipt(docx_path: Path) -> bytes:
    ESC = b"\x1b"
    GS = b"\x1d"

    payload = bytearray()
    payload += ESC + b"@"
    payload += margin_commands()

    images = docx_to_images(docx_path)
    for img in images:
        payload += pil_image_to_escpos_raster(img)
        payload += b"\n"

    payload += b"\n\n\n\n"
    payload += GS + b"V\x41\x03"

    return bytes(payload)


def send_to_printer(data: bytes, printer_name: str):
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


def main():
    parser = argparse.ArgumentParser(
        description="Press Enter to print a random .docx receipt"
    )
    parser.add_argument(
        "-p", "--printer",
        default=DEFAULT_PRINTER,
        help=f"Printer name (default: {DEFAULT_PRINTER})",
    )
    parser.add_argument(
        "-d", "--dir",
        default=PRINTABLES_DIR,
        help=f"Folder with .docx files (default: {PRINTABLES_DIR})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available printers and exit",
    )
    args = parser.parse_args()

    if args.list:
        for name in list_printers():
            print(f"  {name}")
        return

    folder = Path(args.dir)
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(1)

    docx_files = sorted(
        f for f in folder.iterdir() if f.suffix.lower() == ".docx"
    )
    if not docx_files:
        print(f"No .docx files found in {folder}")
        sys.exit(1)

    print(f"Documents: {len(docx_files)} .docx files in {folder}")
    print(f"Printer:   {args.printer}")
    print()
    print("Press ENTER to print a receipt (Ctrl+C to quit)")
    print()

    try:
        while True:
            input()
            chosen = random.choice(docx_files)
            print(f"  Rendering {chosen.name} ...")
            data = build_receipt(chosen)
            send_to_printer(data, args.printer)
            print("  Printed!\n")
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
