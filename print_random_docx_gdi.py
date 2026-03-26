#!/usr/bin/env python3
"""
Print a random DOCX from the printables folder using Windows GDI via Word COM.
Optionally appends a random .txt from the same folder onto the same receipt.
Press Enter to print. Ctrl+C to quit.
"""

import argparse
import random
import sys
import time
from pathlib import Path

PRINTABLES_DIR = "printables"
DEFAULT_PRINTER = "POS-80"


def list_printers():
    import win32print
    return [
        p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
    ]


def print_docx(docx_path: Path, printer_name: str, txt_content: str | None = None):
    import win32com.client

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False

    try:
        doc = word.Documents.Open(str(docx_path.resolve()))

        if txt_content:
            rng = doc.Content
            rng.Collapse(0)  # wdCollapseEnd
            rng.InsertParagraphAfter()
            rng.Collapse(0)
            rng.InsertAfter(txt_content)

        old_printer = word.ActivePrinter
        word.ActivePrinter = printer_name
        doc.PrintOut(Background=False)

        time.sleep(1)

        word.ActivePrinter = old_printer
        doc.Close(SaveChanges=False)
    finally:
        word.Quit()


def main():
    if sys.platform != "win32":
        print("This script uses Word COM automation and only works on Windows.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Press Enter to print a random DOCX using Word via the Windows print driver"
    )
    parser.add_argument(
        "-p", "--printer",
        default=DEFAULT_PRINTER,
        help=f"Printer name (default: {DEFAULT_PRINTER})",
    )
    parser.add_argument(
        "-d", "--dir",
        default=PRINTABLES_DIR,
        help=f"Folder with DOCX/TXT files (default: {PRINTABLES_DIR})",
    )
    parser.add_argument(
        "-t", "--txt",
        action="store_true",
        help="Also append a random .txt file from the folder onto the receipt",
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

    docx_files = sorted(f for f in folder.iterdir() if f.suffix.lower() == ".docx")
    if not docx_files:
        print(f"No DOCX files found in {folder}")
        sys.exit(1)

    txt_files = sorted(f for f in folder.iterdir() if f.suffix.lower() == ".txt")

    print(f"DOCX:    {len(docx_files)} files in {folder}")
    if args.txt:
        if txt_files:
            print(f"TXT:     {len(txt_files)} files (will append one per receipt)")
        else:
            print(f"TXT:     none found — ignoring --txt flag")
    print(f"Printer: {args.printer}")
    print()
    print("Press ENTER to print a random receipt (Ctrl+C to quit)")
    print()

    try:
        while True:
            input()
            chosen_docx = random.choice(docx_files)
            txt_content = None

            if args.txt and txt_files:
                chosen_txt = random.choice(txt_files)
                txt_content = chosen_txt.read_text(encoding="utf-8").strip()
                print(f"  DOCX: {chosen_docx.name}  +  TXT: {chosen_txt.name}")
            else:
                print(f"  DOCX: {chosen_docx.name}")

            print_docx(chosen_docx, args.printer, txt_content)
            print("  Done!\n")
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
