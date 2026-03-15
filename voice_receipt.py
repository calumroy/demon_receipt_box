#!/usr/bin/env python3
"""
Voice-to-receipt printer.

Loop:
  1. Wait for Enter
  2. Record 4 seconds of audio
  3. Transcribe with faster-whisper
  4. If speech detected, print the text on a thermal receipt printer
"""

import argparse
import struct
import sys

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as wav_write
from faster_whisper import WhisperModel


RECORD_SECONDS = 4
SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "base"

PAPER_TOTAL_PX = 576
MARGIN_PX = 40
PRINT_WIDTH_PX = PAPER_TOTAL_PX - 2 * MARGIN_PX

DEFAULT_PRINTER = "XP-80C"


# ── audio helpers ───────────────────────────────────────────────

def find_input_device() -> tuple[int, int]:
    """Find a working input device, return (device_id, sample_rate)."""
    devices = sd.query_devices()
    host_apis = sd.query_hostapis()
    api_names = {i: api["name"] for i, api in enumerate(host_apis)}
    default_input = sd.default.device[0]

    candidates = []
    default_name = (
        devices[default_input]["name"]
        if default_input is not None and default_input >= 0
        else ""
    )
    api_priority = {"Windows WASAPI": 0, "Windows DirectSound": 1, "MME": 2}

    for i, d in enumerate(devices):
        if d["max_input_channels"] < CHANNELS:
            continue
        api_name = api_names.get(d["hostapi"], "")
        priority = api_priority.get(api_name, 99)
        is_default_name = 0 if d["name"] == default_name else 1
        candidates.append((priority, is_default_name, i, d))

    candidates.sort(key=lambda x: (x[0], x[1]))

    if not candidates:
        raise RuntimeError("No input devices found.")

    rates = [SAMPLE_RATE, 44100, 48000]
    for _pri, _def, dev_id, dev_info in candidates:
        native_sr = int(dev_info["default_samplerate"])
        for sr in [native_sr] + [s for s in rates if s != native_sr]:
            try:
                stream = sd.InputStream(
                    device=dev_id, samplerate=sr, channels=CHANNELS, dtype="int16"
                )
                stream.start()
                sd.sleep(200)
                stream.stop()
                stream.close()
                return dev_id, sr
            except Exception:
                continue

    raise RuntimeError("Every input device failed a test recording.")


def record(seconds: int) -> tuple[np.ndarray, int]:
    """Record audio, return (samples, sample_rate)."""
    dev_id, sr = find_input_device()
    audio = sd.rec(
        int(seconds * sr), samplerate=sr, channels=CHANNELS,
        dtype="int16", device=dev_id,
    )
    sd.wait()
    return audio, sr


def transcribe(audio: np.ndarray, sr: int, model: WhisperModel) -> str:
    tmp = "_voice_receipt_tmp.wav"
    wav_write(tmp, sr, audio)
    segments, _ = model.transcribe(tmp, language="en", vad_filter=True)
    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    return " ".join(parts)


# ── ESC/POS helpers ─────────────────────────────────────────────

def margin_commands() -> bytes:
    GS = b"\x1d"
    cmds = bytearray()
    cmds += GS + b"L" + struct.pack("<H", MARGIN_PX)
    cmds += GS + b"W" + struct.pack("<H", PRINT_WIDTH_PX)
    return bytes(cmds)


def encode_text(text: str) -> bytes:
    return text.encode("cp437", errors="replace")


def build_text_receipt(text: str) -> bytes:
    ESC = b"\x1b"
    GS = b"\x1d"

    payload = bytearray()
    payload += ESC + b"@"
    payload += margin_commands()
    payload += ESC + b"t\x00"

    payload += encode_text(text)
    payload += b"\n"

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


# ── main ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Voice → receipt printer")
    parser.add_argument(
        "-p", "--printer",
        default=DEFAULT_PRINTER,
        help=f"Printer name (default: {DEFAULT_PRINTER})",
    )
    parser.add_argument(
        "-m", "--model",
        default=MODEL_SIZE,
        help=f"Whisper model size (default: {MODEL_SIZE})",
    )
    parser.add_argument(
        "-s", "--seconds",
        type=int,
        default=RECORD_SECONDS,
        help=f"Recording duration in seconds (default: {RECORD_SECONDS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Transcribe but don't actually send to printer",
    )
    args = parser.parse_args()

    print(f"Loading whisper model ({args.model})...")
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    print("Model loaded.")

    if not args.dry_run:
        print(f"Printer: {args.printer}")
    else:
        print("Dry-run mode — will not print.")

    print(f"\nPress ENTER to record {args.seconds}s of audio (Ctrl+C to quit)\n")

    try:
        while True:
            input()
            print(f"  Recording {args.seconds}s...")
            audio, sr = record(args.seconds)

            print("  Transcribing...")
            text = transcribe(audio, sr, model)

            if not text:
                print("  [No speech detected — nothing to print]\n")
                continue

            print(f"  Heard: {text}")

            if args.dry_run:
                print("  (dry-run, skipping print)\n")
                continue

            receipt = build_text_receipt(text)
            send_to_printer(receipt, args.printer)
            print("  Printed!\n")

    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
