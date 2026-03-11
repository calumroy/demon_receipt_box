from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_TRANSCRIPTION_FILE = "transcription.txt"
DEFAULT_PROMPT_FILE = "prompts/joke_prompt.txt"
DEFAULT_OUTPUT_FILE = "llm_response.txt"
DEFAULT_MODEL_PATH = "models"
DEFAULT_MAX_TOKENS = 256


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


def resolve_model_path(
    model_file: str | None,
    hf_repo: str | None,
    hf_filename: str | None,
    model_dir: str,
) -> str:
    if model_file:
        path = Path(model_file)
        if not path.exists():
            raise FileNotFoundError(
                f"Model file not found: {model_file}. Provide an existing GGUF file."
            )
        return str(path)

    if not hf_repo or not hf_filename:
        raise ValueError(
            "Provide either --model-file, or both --hf-repo and --hf-filename."
        )

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is not installed. Run `uv sync` first."
        ) from exc

    Path(model_dir).mkdir(parents=True, exist_ok=True)
    return hf_hub_download(
        repo_id=hf_repo,
        filename=hf_filename,
        local_dir=model_dir,
    )


def run_llama_cpp(
    model_path: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    context_size: int,
    threads: int | None,
) -> str:
    try:
        from llama_cpp import Llama  # type: ignore[reportMissingImports]
    except ImportError as exc:
        raise RuntimeError(
            "llama-cpp-python is not installed. Run `uv sync` first."
        ) from exc

    llm = Llama(
        model_path=model_path,
        n_ctx=context_size,
        n_threads=threads,
        verbose=False,
    )

    result = llm.create_completion(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = result["choices"][0]["text"].strip()
    if not text:
        raise RuntimeError("Model returned empty output.")
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read transcription + prompt file, run local llama.cpp model, "
            "and save LLM output to a text file."
        )
    )
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
        "--model-file",
        default=None,
        help="Path to a local GGUF model file",
    )
    parser.add_argument(
        "--hf-repo",
        default=None,
        help="Optional Hugging Face repo ID for GGUF download (for example bartowski/Llama-3.2-3B-Instruct-GGUF)",
    )
    parser.add_argument(
        "--hf-filename",
        default=None,
        help="Optional GGUF filename in the Hugging Face repo (for example Llama-3.2-3B-Instruct-Q4_K_M.gguf)",
    )
    parser.add_argument(
        "--model-dir",
        default=DEFAULT_MODEL_PATH,
        help="Directory used to store downloaded model files",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Generation temperature",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help="Maximum number of generated tokens",
    )
    parser.add_argument(
        "--context-size",
        type=int,
        default=4096,
        help="Context window size for llama.cpp",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Optional CPU thread count for inference",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        transcription = read_text(args.input_text)
        prompt_template = read_text(args.prompt_file)
        final_prompt = build_prompt(prompt_template, transcription)

        model_path = resolve_model_path(
            model_file=args.model_file,
            hf_repo=args.hf_repo,
            hf_filename=args.hf_filename,
            model_dir=args.model_dir,
        )
        print(f"Using model file: {model_path}")

        llm_output = run_llama_cpp(
            model_path=model_path,
            prompt=final_prompt,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            context_size=args.context_size,
            threads=args.threads,
        )

        Path(args.output_file).write_text(llm_output + "\n", encoding="utf-8")
        print(f"Saved LLM output to: {args.output_file}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
