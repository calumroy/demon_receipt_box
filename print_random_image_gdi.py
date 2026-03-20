#!/usr/bin/env python3
"""
Print a random PNG from the printables folder using Windows GDI printing.
Optionally overlays random text from a .txt file in the same folder.
Uses the normal printer driver (like Paint does) instead of raw ESC/POS.
Press Enter to print. Ctrl+C to quit.
"""

import argparse
import random
import sys
import textwrap
from pathlib import Path

PRINTABLES_DIR = "printables"
DEFAULT_PRINTER = "XP-80C"
FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
FONT_SIZE_RATIO = 0.06


def overlay_text_on_image(img, text, font_path=FONT_PATH):
    """Draw text over a PIL Image with an outline for visibility on any background."""
    from PIL import ImageDraw, ImageFont

    img = img.copy().convert("RGBA")
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)

    font_size = max(16, int(img.width * FONT_SIZE_RATIO))
    try:
        font = ImageFont.truetype(font_path, font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    max_chars = max(1, int(img.width / (font_size * 0.55)))
    wrapped = textwrap.fill(text.strip(), width=max_chars)

    bbox = draw.textbbox((0, 0), wrapped, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (img.width - text_w) // 2
    y = (img.height - text_h) // 2

    outline_range = max(1, font_size // 12)
    for dx in range(-outline_range, outline_range + 1):
        for dy in range(-outline_range, outline_range + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), wrapped, font=font, fill="white")

    draw.text((x, y), wrapped, font=font, fill="black")

    return overlay.convert("RGB")


def list_printers():
    import win32print
    return [
        p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
    ]


def print_image_gdi(img, printer_name: str, doc_name: str = "image"):
    """Send a PIL Image to a Windows GDI printer."""
    import win32print
    import win32ui
    from PIL import ImageWin

    hprinter = win32print.OpenPrinter(printer_name)
    try:
        win32print.GetPrinter(hprinter, 2)
    finally:
        win32print.ClosePrinter(hprinter)

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)

    printable_w = hdc.GetDeviceCaps(8)   # HORZRES
    printable_h = hdc.GetDeviceCaps(10)  # VERTRES

    ratio = min(printable_w / img.width, printable_h / img.height)
    scaled_w = int(img.width * ratio)
    scaled_h = int(img.height * ratio)

    x_offset = (printable_w - scaled_w) // 2
    y_offset = 0

    hdc.StartDoc(doc_name)
    hdc.StartPage()

    dib = ImageWin.Dib(img)
    dib.draw(hdc.GetHandleOutput(), (x_offset, y_offset, x_offset + scaled_w, y_offset + scaled_h))

    hdc.EndPage()
    hdc.EndDoc()
    hdc.DeleteDC()


def main():
    if sys.platform != "win32":
        print("This script uses Windows GDI printing and only works on Windows.")
        print("Use print_random_image.py with ESC/POS on Linux instead.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Press Enter to print a random PNG using the Windows print driver"
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
        "--no-text",
        action="store_true",
        help="Don't overlay text from .txt files onto the image",
    )
    parser.add_argument(
        "-f", "--font",
        default=FONT_PATH,
        help=f"Path to a .ttf font file (default: {FONT_PATH})",
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

    from PIL import Image

    folder = Path(args.dir)
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(1)

    pngs = sorted(f for f in folder.iterdir() if f.suffix.lower() == ".png")
    if not pngs:
        print(f"No PNGs found in {folder}")
        sys.exit(1)

    txts = sorted(f for f in folder.iterdir() if f.suffix.lower() == ".txt")

    print(f"Images:  {len(pngs)} PNGs in {folder}")
    if not args.no_text:
        print(f"Texts:   {len(txts)} TXTs in {folder}")
    print(f"Printer: {args.printer}")
    if not args.no_text and not txts:
        print("(no .txt files found — printing images without text overlay)")
    print()
    print("Press ENTER to print a random image (Ctrl+C to quit)")
    print()

    try:
        while True:
            input()
            chosen_png = random.choice(pngs)
            img = Image.open(chosen_png)

            label = chosen_png.name
            if not args.no_text and txts:
                chosen_txt = random.choice(txts)
                text = chosen_txt.read_text(encoding="utf-8", errors="replace")
                img = overlay_text_on_image(img, text, font_path=args.font)
                label = f"{chosen_png.name} + {chosen_txt.name}"

            print(f"  Printing {label}...")
            print_image_gdi(img, args.printer, doc_name=str(chosen_png))
            print("  Done!\n")
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
