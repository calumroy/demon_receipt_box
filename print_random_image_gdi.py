#!/usr/bin/env python3
"""
Print a random PNG from the printables folder using Windows GDI printing.
Uses the normal printer driver (like Paint does) instead of raw ESC/POS.
Press Enter to print. Ctrl+C to quit.
"""

import argparse
import random
import sys
from pathlib import Path

PRINTABLES_DIR = "printables"
DEFAULT_PRINTER = "XP-80C"


def list_printers():
    import win32print
    return [
        p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
    ]


def print_image_gdi(image_path: Path, printer_name: str):
    import win32print
    import win32ui
    from PIL import Image, ImageWin

    img = Image.open(image_path)

    hprinter = win32print.OpenPrinter(printer_name)
    try:
        devmode = win32print.GetPrinter(hprinter, 2)["pDevMode"]
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

    hdc.StartDoc(str(image_path))
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
            print_image_gdi(chosen, args.printer)
            print("  Done!\n")
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
