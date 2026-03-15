from pathlib import Path
import sys

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel


# -----------------------------
# Settings
# -----------------------------
RECORD_SECONDS = 10
SAMPLE_RATE = 16000
CHANNELS = 1
OUTPUT_WAV = "recording.wav"
OUTPUT_TEXT = "transcription.txt"

# Model options:
# tiny, base, small, medium, large-v3
# For a Windows Surface laptop, "base" is a sensible default.
MODEL_SIZE = "base"


def _try_record_test(device_id: int, sr: int) -> bool:
    """Actually open a tiny stream to verify the device works (not just check_input_settings)."""
    try:
        sd.rec(int(0.1 * sr), samplerate=sr, channels=CHANNELS,
               dtype="int16", device=device_id)
        sd.wait()
        return True
    except sd.PortAudioError:
        return False


def find_input_device() -> tuple[int, int]:
    """Find a working input device, preferring WASAPI over MME on Windows."""
    devices = sd.query_devices()
    host_apis = sd.query_hostapis()

    api_names = {i: api["name"] for i, api in enumerate(host_apis)}
    default_input = sd.default.device[0]

    print("Available input devices:")
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            api = api_names.get(d["hostapi"], "?")
            marker = " <-- default" if i == default_input else ""
            print(f"  [{i}] {d['name']} "
                  f"(api={api}, inputs={d['max_input_channels']}, "
                  f"default_sr={d['default_samplerate']:.0f}){marker}")

    # Build candidate list: WASAPI first, then DirectSound, then MME, then rest.
    api_priority = {"Windows WASAPI": 0, "Windows DirectSound": 1, "MME": 2}
    candidates = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] < CHANNELS:
            continue
        api_name = api_names.get(d["hostapi"], "")
        priority = api_priority.get(api_name, 99)
        candidates.append((priority, i, d))

    candidates.sort(key=lambda x: x[0])

    if not candidates:
        raise RuntimeError(
            "No input devices found at all. Check Windows Settings > "
            "System > Sound and make sure a microphone is enabled, and "
            "Settings > Privacy > Microphone allows desktop apps."
        )

    # Try each candidate with a real test recording.
    sample_rates = [SAMPLE_RATE, 44100, 48000]
    for priority, dev_id, dev_info in candidates:
        api_name = api_names.get(dev_info["hostapi"], "?")
        native_sr = int(dev_info["default_samplerate"])
        rates_to_try = [native_sr] + [s for s in sample_rates if s != native_sr]

        for sr in rates_to_try:
            if _try_record_test(dev_id, sr):
                print(f"Using device [{dev_id}] {dev_info['name']} "
                      f"(api={api_name}) @ {sr} Hz")
                return dev_id, sr

    raise RuntimeError(
        "Every input device failed a real test recording. "
        "Check Windows Settings > Privacy > Microphone and allow desktop apps."
    )


def record_audio(filename: str, seconds: int, sample_rate: int, channels: int) -> None:
    """Record audio from the default microphone and save it as a WAV file."""
    device_id, actual_sr = find_input_device()

    print(f"Recording for {seconds} seconds... Speak now.")

    audio = sd.rec(
        int(seconds * actual_sr),
        samplerate=actual_sr,
        channels=channels,
        dtype="int16",
        device=device_id,
    )
    sd.wait()

    write(filename, actual_sr, audio)
    print(f"Saved recording to: {filename}")


def transcribe_audio(filename: str, model_size: str) -> str:
    """Transcribe audio to text using faster-whisper locally on CPU."""
    print("Loading speech-to-text model...")

    model = WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
    )

    print("Transcribing audio...")
    segments, info = model.transcribe(
        filename,
        language="en",
        vad_filter=True,   # helps ignore silence
    )

    text_parts = []
    for segment in segments:
        cleaned = segment.text.strip()
        if cleaned:
            text_parts.append(cleaned)

    return " ".join(text_parts)


def save_text(filename: str, text: str) -> None:
    Path(filename).write_text(text, encoding="utf-8")
    print(f"Saved transcription to: {filename}")


def main() -> int:
    try:
        record_audio(
            filename=OUTPUT_WAV,
            seconds=RECORD_SECONDS,
            sample_rate=SAMPLE_RATE,
            channels=CHANNELS,
        )

        text = transcribe_audio(
            filename=OUTPUT_WAV,
            model_size=MODEL_SIZE,
        )

        if not text:
            text = "[No speech detected]"

        print("\n--- Transcribed Text ---")
        print(text)

        save_text(OUTPUT_TEXT, text)
        return 0

    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 1
    except Exception as exc:
        print(f"\nError: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
