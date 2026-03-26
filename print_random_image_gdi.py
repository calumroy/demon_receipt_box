#!/usr/bin/env python3
"""
Print a receipt with a .docx header followed by a random PNG (with optional
random text overlay) using Word COM automation and the Windows GDI driver.
Everything prints as one continuous document -- no paper cut between header
and image.

Press Enter to print. Ctrl+C to quit.
"""

import argparse
import os
import random
import sys
import tempfile
import textwrap
import time
from pathlib import Path

PRINTABLES_DIR = "printables"
DEFAULT_PRINTER = "XP-80C"
FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
FONT_SIZE_RATIO = 0.06
HEADER_DOCX = "receipt-header.docx"
RANDOM_LINES_FILE = "random_text_lines.txt"


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


def print_receipt(header_docx, composited_img, printer_name, save_path=None):
    """Open header docx in Word, append the composited image, and print."""
    import win32com.client

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(tmp_fd)
    try:
        composited_img.save(tmp_path)

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(header_docx.resolve()), ReadOnly=True)

            rng = doc.Content
            rng.Collapse(0)  # wdCollapseEnd
            rng.InsertParagraphAfter()
            rng.Collapse(0)
            doc.InlineShapes.AddPicture(
                FileName=tmp_path,
                LinkToFile=False,
                SaveWithDocument=True,
                Range=rng,
            )

            if save_path:
                abs_save = str(Path(save_path).resolve())
                doc.SaveAs2(FileName=abs_save, FileFormat=0)  # wdFormatDocument

            old_printer = word.ActivePrinter
            word.ActivePrinter = printer_name
            doc.PrintOut(Background=False)
            time.sleep(1)

            word.ActivePrinter = old_printer
            doc.Close(SaveChanges=False)
        finally:
            word.Quit()
    finally:
        os.unlink(tmp_path)


def print_image_gdi(img, printer_name, doc_name="image"):
    """Fallback: send a PIL Image directly to a Windows GDI printer (no Word)."""
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
        description="Print a docx header + random PNG receipt via the Windows print driver"
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
        "-n", "--lines",
        type=int, default=1,
        help="Number of random lines to overlay on the image (default: 1)",
    )
    parser.add_argument(
        "--no-text",
        action="store_true",
        help="Don't overlay any text onto the image",
    )
    parser.add_argument(
        "-f", "--font",
        default=FONT_PATH,
        help=f"Path to a .ttf font file (default: {FONT_PATH})",
    )
    parser.add_argument(
        "--header",
        default=None,
        help=f"Path to header .docx (default: <dir>/{HEADER_DOCX})",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Skip the .docx header and just print the image via GDI",
    )
    parser.add_argument(
        "--save-docx",
        default=None,
        metavar="PATH",
        help="Save each composed receipt as a .docx file to PATH before printing",
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

    # Header docx
    use_header = not args.no_header
    header_path = Path(args.header) if args.header else folder / HEADER_DOCX
    if use_header and not header_path.is_file():
        print(f"Header not found: {header_path} — printing without header")
        use_header = False

    # Random text lines
    lines = []
    lines_file = folder / RANDOM_LINES_FILE
    if not args.no_text and lines_file.is_file():
        raw = lines_file.read_text(encoding="utf-8", errors="replace")
        lines = [line for line in raw.splitlines() if line.strip()]

    print(f"Images:  {len(pngs)} PNGs in {folder}")
    if use_header:
        print(f"Header:  {header_path.name}")
    if not args.no_text:
        print(f"Lines:   {len(lines)} in {RANDOM_LINES_FILE} (picking {args.lines} per print)")
    print(f"Printer: {args.printer}")
    if not args.no_text and not lines:
        print(f"({RANDOM_LINES_FILE} not found or empty — printing without text overlay)")
    print()
    print("Press ENTER to print a receipt (Ctrl+C to quit)")
    print()

    try:
        while True:
            input()
            chosen_png = random.choice(pngs)
            img = Image.open(chosen_png)

            label = chosen_png.name
            if not args.no_text and lines:
                n = min(args.lines, len(lines))
                picked = random.sample(lines, n)
                text = "\n".join(picked)
                img = overlay_text_on_image(img, text, font_path=args.font)
                label = f"{chosen_png.name} + {n} line(s)"

            print(f"  Printing {label}...")
            if use_header:
                print_receipt(header_path, img, args.printer, save_path=args.save_docx)
                if args.save_docx:
                    print(f"  Saved to {args.save_docx}")
            else:
                print_image_gdi(img, args.printer, doc_name=str(chosen_png))
            print("  Done!\n")
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
