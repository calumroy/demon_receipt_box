from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib import error, request


DEFAULT_TRANSCRIPTION_FILE = "transcription.txt"
DEFAULT_PROMPT_FILE = "prompts/joke_prompt.txt"
DEFAULT_OUTPUT_FILE = "llm_response.txt"
DEFAULT_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def read_text(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return file_path.read_text(encoding="utf-8")


def build_prompt(prompt_template: str, transcription: str) -> str:
    if "{transcription}" in prompt_template:
        return prompt_template.replace("{transcription}", transcription.strip())

    return (
        f"{prompt_template.strip()}\n\n"
        f"Speech transcription:\n{transcription.strip()}\n"
    )


def call_ollama(
    model: str,
    prompt: str,
    ollama_url: str,
    temperature: float | None,
) -> str:
    endpoint = f"{ollama_url.rstrip('/')}/api/generate"
    payload: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    if temperature is not None:
        payload["options"] = {"temperature": temperature}

    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=180) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Ollama returned HTTP {exc.code}. Response: {detail}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            "Cannot connect to Ollama. Start it first (for example, run `ollama serve`)."
        ) from exc

    data = json.loads(body)
    llm_output = data.get("response", "").strip()
    if not llm_output:
        raise RuntimeError("Ollama response was empty.")
    return llm_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read transcription + prompt file, send to local Ollama model, "
            "and save LLM output to a text file."
        )
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument(
        "--input-text",
        default=DEFAULT_TRANSCRIPTION_FILE,
        help="Path to speech transcription text file",
    )
    parser.add_argument(
        "--prompt-file",
        default=DEFAULT_PROMPT_FILE,
        help="Prompt template file path. Use {transcription} placeholder if wanted.",
    )
    parser.add_argument(
        "--output-file",
        default=DEFAULT_OUTPUT_FILE,
        help="Path for generated LLM response text",
    )
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help="Base URL for local Ollama server",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Optional generation temperature",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        transcription = read_text(args.input_text)
        prompt_template = read_text(args.prompt_file)
        final_prompt = build_prompt(prompt_template, transcription)

        llm_output = call_ollama(
            model=args.model,
            prompt=final_prompt,
            ollama_url=args.ollama_url,
            temperature=args.temperature,
        )

        Path(args.output_file).write_text(llm_output + "\n", encoding="utf-8")
        print(f"Saved LLM output to: {args.output_file}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
