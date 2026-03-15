#!/usr/bin/env python3
"""
Demon Talk — voice → transcribe → LLM → print receipt.

Loop:
  1. Press Enter
  2. Record audio (default 4 s)
  3. Transcribe with faster-whisper → save transcription.txt
  4. Run transcription through a local GGUF LLM with a prompt → save llm_response.txt
  5. Pick a random DOCX from printables/, append the LLM response, print via Word COM
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as wav_write

from llm_postprocess import build_prompt, resolve_model_path

RECORD_SECONDS = 4
SAMPLE_RATE = 16000
CHANNELS = 1
WHISPER_MODEL_SIZE = "base"

PRINTABLES_DIR = "printables"
DEFAULT_PRINTER = "XP-80C"
TRANSCRIPTION_FILE = "transcription.txt"
LLM_RESPONSE_FILE = "llm_response.txt"
DEFAULT_PROMPT_FILE = "prompts/joke_prompt.txt"
DEFAULT_HF_REPO = "bartowski/Llama-3.2-3B-Instruct-GGUF"
DEFAULT_HF_FILENAME = "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
TMP_WAV = "_demon_talk_tmp.wav"


# ── audio ────────────────────────────────────────────────────────

def find_input_device() -> tuple[int, int]:
    devices = sd.query_devices()
    host_apis = sd.query_hostapis()
    api_names = {i: api["name"] for i, api in enumerate(host_apis)}
    default_input = sd.default.device[0]

    default_name = (
        devices[default_input]["name"]
        if default_input is not None and default_input >= 0
        else ""
    )
    api_priority = {"Windows WASAPI": 0, "Windows DirectSound": 1, "MME": 2}
    candidates = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] < CHANNELS:
            continue
        api_name = api_names.get(d["hostapi"], "")
        priority = api_priority.get(api_name, 99)
        is_default = 0 if d["name"] == default_name else 1
        candidates.append((priority, is_default, i, d))

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
    dev_id, sr = find_input_device()
    audio = sd.rec(
        int(seconds * sr), samplerate=sr, channels=CHANNELS,
        dtype="int16", device=dev_id,
    )
    sd.wait()
    return audio, sr


def transcribe(audio: np.ndarray, sr: int, model) -> str:
    wav_write(TMP_WAV, sr, audio)
    segments, _ = model.transcribe(TMP_WAV, language="en", vad_filter=True)
    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    return " ".join(parts)


# ── LLM ──────────────────────────────────────────────────────────

def load_llm(model_path: str, context_size: int, threads: int | None):
    from llama_cpp import Llama
    return Llama(
        model_path=model_path,
        n_ctx=context_size,
        n_threads=threads,
        verbose=False,
    )


def generate(llm, prompt: str, temperature: float, max_tokens: int) -> str:
    result = llm.create_completion(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return result["choices"][0]["text"].strip()


# ── printing ─────────────────────────────────────────────────────

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


# ── main ─────────────────────────────────────────────────────────

def main():
    if sys.platform != "win32":
        print("This script uses Word COM automation and only works on Windows.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Voice → LLM → receipt printer (demon mode)"
    )
    parser.add_argument(
        "-p", "--printer", default=DEFAULT_PRINTER,
        help=f"Printer name (default: {DEFAULT_PRINTER})",
    )
    parser.add_argument(
        "-d", "--dir", default=PRINTABLES_DIR,
        help=f"Folder with DOCX files (default: {PRINTABLES_DIR})",
    )
    parser.add_argument(
        "--prompt-file", default=DEFAULT_PROMPT_FILE,
        help=f"Prompt template file (default: {DEFAULT_PROMPT_FILE})",
    )
    parser.add_argument(
        "-s", "--seconds", type=int, default=RECORD_SECONDS,
        help=f"Recording duration in seconds (default: {RECORD_SECONDS})",
    )
    parser.add_argument(
        "-w", "--whisper-model", default=WHISPER_MODEL_SIZE,
        help=f"Whisper model size (default: {WHISPER_MODEL_SIZE})",
    )
    parser.add_argument(
        "--model-file", default=None,
        help="Path to a local GGUF model file (overrides --hf-repo/--hf-filename)",
    )
    parser.add_argument(
        "--hf-repo", default=DEFAULT_HF_REPO,
        help=f"HuggingFace repo ID for GGUF download (default: {DEFAULT_HF_REPO})",
    )
    parser.add_argument(
        "--hf-filename", default=DEFAULT_HF_FILENAME,
        help=f"GGUF filename inside the HuggingFace repo (default: {DEFAULT_HF_FILENAME})",
    )
    parser.add_argument(
        "--model-dir", default="models",
        help="Directory for downloaded model files",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="LLM generation temperature",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=256,
        help="Max tokens for LLM generation",
    )
    parser.add_argument(
        "--context-size", type=int, default=4096,
        help="Context window size for llama.cpp",
    )
    parser.add_argument(
        "--threads", type=int, default=None,
        help="CPU thread count for LLM inference",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run the full pipeline but skip actual printing",
    )
    args = parser.parse_args()

    # ── validate printables folder ───────────────────────────────
    folder = Path(args.dir)
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(1)

    docx_files = sorted(f for f in folder.iterdir() if f.suffix.lower() == ".docx")
    if not docx_files:
        print(f"No DOCX files found in {folder}")
        sys.exit(1)

    # ── validate prompt file ─────────────────────────────────────
    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        print(f"Prompt file not found: {prompt_path}")
        sys.exit(1)
    prompt_template = prompt_path.read_text(encoding="utf-8")

    # ── load whisper ─────────────────────────────────────────────
    print(f"Loading whisper model ({args.whisper_model})...")
    from faster_whisper import WhisperModel
    whisper = WhisperModel(args.whisper_model, device="cpu", compute_type="int8")
    print("Whisper loaded.")

    # ── load LLM ─────────────────────────────────────────────────
    print("Resolving LLM model...")
    llm_model_path = resolve_model_path(
        model_file=args.model_file,
        hf_repo=args.hf_repo,
        hf_filename=args.hf_filename,
        model_dir=args.model_dir,
    )
    print(f"Loading LLM from {llm_model_path}...")
    llm = load_llm(llm_model_path, args.context_size, args.threads)
    print("LLM loaded.")

    # ── ready ────────────────────────────────────────────────────
    print()
    print(f"DOCX templates: {len(docx_files)} in {folder}/")
    print(f"Prompt file:    {args.prompt_file}")
    if not args.dry_run:
        print(f"Printer:        {args.printer}")
    else:
        print("Mode:           dry-run (no printing)")
    print()
    print(f"Press ENTER to record {args.seconds}s → transcribe → LLM → print")
    print("Ctrl+C to quit\n")

    try:
        while True:
            input()

            # 1. record
            print(f"  Recording {args.seconds}s...")
            audio, sr = record(args.seconds)

            # 2. transcribe
            print("  Transcribing...")
            text = transcribe(audio, sr, whisper)
            if not text:
                print("  [No speech detected — skipping]\n")
                continue
            print(f"  Heard: {text}")
            Path(TRANSCRIPTION_FILE).write_text(text + "\n", encoding="utf-8")

            # 3. LLM
            print("  Running LLM...")
            prompt = build_prompt(prompt_template, text)
            llm_response = generate(
                llm, prompt,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
            if not llm_response:
                print("  [LLM returned empty response — skipping]\n")
                continue
            print(f"  LLM says: {llm_response}")
            Path(LLM_RESPONSE_FILE).write_text(llm_response + "\n", encoding="utf-8")

            # 4. print random DOCX with LLM response appended
            chosen_docx = random.choice(docx_files)
            print(f"  Printing {chosen_docx.name} + LLM response...")

            if args.dry_run:
                print("  (dry-run — skipped print)\n")
                continue

            print_docx(chosen_docx, args.printer, llm_response)
            print("  Printed!\n")

    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
