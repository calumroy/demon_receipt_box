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


def record_audio(filename: str, seconds: int, sample_rate: int, channels: int) -> None:
    """Record audio from the default microphone and save it as a WAV file."""
    print(f"Recording for {seconds} seconds... Speak now.")

    audio = sd.rec(
        int(seconds * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
    )
    sd.wait()

    write(filename, sample_rate, audio)
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
