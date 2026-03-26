# demon_receipt_box
Voice recorder with local offline speech-to-text transcription.

## Quick Start -- Random Receipt Printer (Windows)

Print receipts on a thermal printer: a header image followed by a random PNG with random text overlaid on it -- all printed as one continuous strip with no paper cut in between.

### 1. Download the code

Go to [github.com/calumroy/demon_receipt_box](https://github.com/calumroy/demon_receipt_box), click the green **Code** button, then click **Download ZIP**. Extract the ZIP to a folder on your computer (e.g. `C:\demon_receipt_box`).

### 2. Install Python

1. Download the latest Python 3 installer from [python.org/downloads](https://www.python.org/downloads/)
2. Run the installer
3. **Important:** tick the checkbox that says **"Add Python to PATH"** at the bottom of the first screen before clicking Install

### 3. Open a Command Prompt

Press **Win + R**, type `cmd`, and press **Enter**. Then navigate to the folder you extracted:

```cmd
cd C:\demon_receipt_box
```

(Replace `C:\demon_receipt_box` with whatever path you extracted to.)

### 4. Install dependencies

```cmd
pip install pywin32 Pillow
```

That's it -- these are the only two packages this script needs.

### 5. Set up the `printables` folder

The `printables` folder should contain:

- **`receipt-header.png`** -- printed at the top of every receipt as a header (already included). A `.docx` header is also supported via `--header` but requires Microsoft Word.
- **`.png` images** -- a random one is picked each time you print (the header PNG is excluded from the random pool)
- **`random_text_lines.txt`** -- one random line from this file is overlaid on the image each time (already included)

If the header file is missing the header is skipped. If `random_text_lines.txt` is missing or empty the image prints without text.

### 6. Plug in your printer and run

Plug in your USB thermal receipt printer (Windows usually auto-installs the driver). The script defaults to the `POS-80` printer, so just run:

```cmd
python print_random_image_gdi.py
```

Press **Enter** each time you want to print a receipt. Press **Ctrl+C** to quit.

### Options

| Flag | Description |
|------|-------------|
| `-p "PrinterName"` | Printer to use (default: `POS-80`) |
| `-d folder` | Use a different folder instead of `printables` |
| `-n N` | Number of random lines to overlay on the image (default: `1`) |
| `-f path\to\font.ttf` | Custom `.ttf` font for the text overlay (default: `C:\Windows\Fonts\arial.ttf`). Other fonts live in `C:\Windows\Fonts\` -- try `arialbd.ttf` (Arial Bold), `comic.ttf` (Comic Sans), `impact.ttf`, `times.ttf`, etc. |
| `--header path` | Use a different header file -- `.png` (pure Pillow) or `.docx` (needs Word). Default: `receipt-header.png`, falls back to `receipt-header.docx` |
| `--no-header` | Skip the header and print only the image |
| `--no-text` | Print images without any text overlay |
| `--save-docx path` | Save each composed receipt (header + image) as a `.docx` file before printing |
| `--list` | List available printers and exit |

---

## Quick install (pip, no uv) for the other Python scritp e.g LLM and transcription.

Install all Python dependencies in one go:

```bash
pip install numpy sounddevice scipy faster-whisper llama-cpp-python huggingface-hub pywin32 Pillow docx2pdf pdf2image
```

On Linux, you also need PortAudio:
```bash
sudo apt install -y libportaudio2 portaudio19-dev
```

`pywin32`, `docx2pdf`, and `pdf2image` are only needed for the Windows printing scripts — skip them on Linux if you only want recording + transcription + LLM:
```bash
pip install numpy sounddevice scipy faster-whisper llama-cpp-python huggingface-hub
```

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
   Or without `uv` (Windows):
   ```cmd
   pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
   pip install huggingface-hub
   ```
   The `--extra-index-url` pulls a prebuilt CPU wheel so you don't need a C++ compiler.

   **If you have an NVIDIA GPU** and want GPU acceleration, use this index instead:
   ```cmd
   pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
   ```

2. **Run speech transcription first**
   ```bash
   python main.py
   ```

3. **Generate LLM output (download model from Hugging Face)**
   ```cmd
   python llm_postprocess.py --hf-repo bartowski/Llama-3.2-3B-Instruct-GGUF --hf-filename Llama-3.2-3B-Instruct-Q4_K_M.gguf --input-text transcription.txt --prompt-file prompts/joke_prompt.txt --output-file llm_response.txt
   ```

4. **Try a different model**
   ```cmd
   python llm_postprocess.py --hf-repo bartowski/Mistral-7B-Instruct-v0.2-GGUF --hf-filename Mistral-7B-Instruct-v0.2-Q4_K_M.gguf --input-text transcription.txt --prompt-file prompts/joke_prompt.txt --output-file llm_response_mistral.txt
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

### Prerequisites

**Microsoft Word** must be installed — `docx2pdf` uses Word to convert `.docx` → PDF.

### Install Poppler for Windows

`pdf2image` needs Poppler's `pdftoppm.exe` to render PDFs into images.

1. Download the latest ZIP from [github.com/oschwartz10612/poppler-windows/releases](https://github.com/oschwartz10612/poppler-windows/releases) (currently `Release-25.12.0-0`)
2. Extract to a permanent location, e.g. `C:\poppler`
3. Add the `Library\bin` folder to your system PATH:
   - Press **Start** → search **Environment Variables** → open **Edit the system environment variables**
   - Click **Environment Variables**
   - Under **System variables**, select **Path** → click **Edit** → click **New**
   - Paste the full path, e.g. `C:\poppler\poppler-25.12.0\Library\bin`
   - Click **OK** on everything
4. **Close and reopen** your terminal, then verify:
   ```cmd
   pdftoppm -h
   ```
   If it prints usage info, Poppler is set up correctly.

### Install Python dependencies

```cmd
pip install docx2pdf pdf2image Pillow pywin32
```
Or if using `uv`:
```cmd
uv sync
```

### Setup and run

1. **Find your printer name**
   ```cmd
   python print_docx.py --list
   ```

2. **Add `.docx` files to `printables/`**
   - Set page width to ~62mm (2.44in) with minimal/zero margins to match the 496-dot printable area
   - The rendered document is auto-scaled to fit the printable width

3. **Run**
   ```cmd
   python print_docx.py -p "YourPrinterName"
   ```
   Then press Enter each time you want a random print. Ctrl+C to quit.

Notes:
- Uses the same **80mm paper** / **5mm margin** settings as `print_receipt.py`.
- Rendering pipeline: `.docx` → Word (via `docx2pdf`) → PDF → `pdf2image` (Poppler) → ESC/POS raster.
- Multi-page documents are supported — each page is printed sequentially.
- Use `-d other_folder` to use a different folder instead of `printables/`.
- To change paper size or margins, edit the constants at the top of `print_docx.py`.
