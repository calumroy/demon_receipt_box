# demon_receipt_box
Voice recorder with local offline speech-to-text transcription.

## Code Review
- Records 10s of audio from microphone → saves as `recording.wav`
- Transcribes using faster-whisper (CPU, offline) → saves to `transcription.txt`
- Uses `base` model (good balance for Surface laptops)
- Adjustable: recording time, model size (tiny/base/small/medium/large-v3)

## Windows Setup (from scratch)

1. **Install Python 3.9+**
   - Download from python.org
   - ✓ Check "Add Python to PATH" during install

2. **Install dependencies**
   ```cmd
   pip install numpy sounddevice scipy faster-whisper
   ```

3. **Run**
   ```cmd
   python main.py
   ```

**First run**: Downloads whisper model (~140MB for base), then runs offline.

**Troubleshooting**:
- If microphone access denied: Settings → Privacy → Microphone → allow Python
- Model sizes: `tiny` (fastest) to `large-v3` (most accurate). Edit `MODEL_SIZE` in main.py 

## Python `uv` Setup (recommended)

Use `uv` to create and manage a local virtual environment for this project.
Dependencies are tracked in `pyproject.toml`, and exact resolved versions are locked in `uv.lock`.

1. **Install `uv`**
   - See the official install options: [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)

2. **Create a virtual environment**
   ```bash
   uv venv
   ```

3. **Activate the virtual environment**
   - macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```
   - Windows (PowerShell):
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - Windows (cmd):
     ```cmd
     .venv\Scripts\activate.bat
     ```

4. **Install dependencies**
   - Linux (Debian/Ubuntu), install system audio dependency first:
     ```bash
     sudo apt update
     sudo apt install -y libportaudio2 portaudio19-dev
     ```
   - Then install Python dependencies from `pyproject.toml`/`uv.lock`:
     ```bash
     uv sync
     ```
   - Windows:
     - `sounddevice` usually works from prebuilt wheels.
     - If you see `OSError: PortAudio library not found`, run:
       ```powershell
       uv pip install --reinstall sounddevice
       ```
     - If it still fails, install/update the Microsoft Visual C++ Redistributable (x64), then retry.

5. **Run**
   ```bash
   python main.py
   ```

6. **Optional: verify microphone backend**
   ```bash
   python -c "import sounddevice as sd; print(sd.query_devices())"
   ```

## Local LLM post-processing (`llama-cpp-python`)

Use a local GGUF model directly from Python (no separate Ollama service).

1. **Install Python dependencies**
   ```bash
   uv sync
   ```

2. **Run speech transcription first**
   ```bash
   python main.py
   ```

3. **Generate LLM output (download model from Hugging Face)**
   ```bash
   python llm_postprocess.py \
     --hf-repo bartowski/Llama-3.2-3B-Instruct-GGUF \
     --hf-filename Llama-3.2-3B-Instruct-Q4_K_M.gguf \
     --input-text transcription.txt \
     --prompt-file prompts/joke_prompt.txt \
     --output-file llm_response.txt
   ```

4. **Try a different model**
   ```bash
   python llm_postprocess.py \
     --hf-repo bartowski/Mistral-7B-Instruct-v0.2-GGUF \
     --hf-filename Mistral-7B-Instruct-v0.2-Q4_K_M.gguf \
     --input-text transcription.txt \
     --prompt-file prompts/joke_prompt.txt \
     --output-file llm_response_mistral.txt
   ```

5. **Use a model file you already downloaded**
   ```bash
   python llm_postprocess.py --model-file models/your-model.gguf --input-text transcription.txt --prompt-file prompts/joke_prompt.txt --output-file llm_response.txt
   ```

Notes:
- The prompt file supports a `{transcription}` placeholder.
- The included test prompt is `prompts/joke_prompt.txt` (turns speech text into a joke).
- Downloaded model files are stored in `models/` by default.

## Thermal receipt printer (ESC/POS via USB, Windows)

Random receipt dispenser — drop `.txt` and `.png` files into a folder, press Enter, and a random one prints.

1. **Plug in your USB thermal printer** (Windows usually auto-installs the driver)

2. **Install dependencies**
   ```cmd
   pip install pywin32 Pillow
   ```
   Or if using `uv`:
   ```cmd
   uv sync
   ```

3. **Find your printer name**
   ```cmd
   python print_receipt.py --list
   ```

4. **Add files to `printables/`**
   - `.txt` files — printed as text
   - `.png` files — converted to monochrome and printed as images

5. **Run**
   ```cmd
   python print_receipt.py -p "YourPrinterName"
   ```
   Then press Enter each time you want a random print. Ctrl+C to quit.

Notes:
- Configured for **80mm paper** with **5mm margins** on each side (496 dots printable).
- PNGs are auto-scaled to fit the printable width and dithered to 1-bit black/white.
- ~42 characters per line with the default font.
- Use `-d other_folder` to use a different folder instead of `printables/`.
- To change paper size or margins, edit the constants at the top of `print_receipt.py`.

## .docx receipt printer (ESC/POS via USB, Windows)

Prints a randomly selected `.docx` file from the printables folder as a raster image on a thermal receipt printer. Save your `.docx` files with the correct page width and margins for the receipt paper.

1. **Install Poppler for Windows**
   - Download the latest release from [github.com/oschwartz10612/poppler-windows/releases](https://github.com/oschwartz10612/poppler-windows/releases)
   - Extract it and add `poppler-XX/Library/bin` to your system PATH

2. **Install Python dependencies**
   ```cmd
   pip install docx2pdf pdf2image Pillow pywin32
   ```
   Or if using `uv`:
   ```cmd
   uv sync
   ```

3. **Microsoft Word** must be installed (used by `docx2pdf` to convert `.docx` → PDF)

4. **Find your printer name**
   ```cmd
   python print_docx.py --list
   ```

5. **Add `.docx` files to `printables/`**
   - Set page width to ~62mm (2.44in) with minimal/zero margins to match the 496-dot printable area
   - The rendered document is auto-scaled to fit the printable width

6. **Run**
   ```cmd
   python print_docx.py -p "YourPrinterName"
   ```
   Then press Enter each time you want a random print. Ctrl+C to quit.

Notes:
- Uses the same **80mm paper** / **5mm margin** settings as `print_receipt.py`.
- Rendering pipeline: `.docx` → Word (via `docx2pdf`) → PDF → `pdf2image` (poppler) → ESC/POS raster.
- Multi-page documents are supported — each page is printed sequentially.
- Use `-d other_folder` to use a different folder instead of `printables/`.
- To change paper size or margins, edit the constants at the top of `print_docx.py`.
