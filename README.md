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

## Local LLM post-processing (Ollama)

Use a local LLM to transform `transcription.txt` with a prompt template and save the result to a new file.

1. **Install Ollama**
   - [https://ollama.com/download](https://ollama.com/download)

2. **Pull one or more local models**
   ```bash
   ollama pull llama3.2
   ollama pull mistral
   ```

3. **Run speech transcription first**
   ```bash
   python main.py
   ```

4. **Generate LLM output from transcription + prompt file**
   ```bash
   python llm_postprocess.py --model llama3.2 --input-text transcription.txt --prompt-file prompts/joke_prompt.txt --output-file llm_response.txt
   ```

5. **Try different local models**
   ```bash
   python llm_postprocess.py --model mistral --input-text transcription.txt --prompt-file prompts/joke_prompt.txt --output-file llm_response_mistral.txt
   ```

Notes:
- The prompt file supports a `{transcription}` placeholder.
- The included test prompt is `prompts/joke_prompt.txt` (turns speech text into a joke).
- If Ollama is not running, start it (`ollama serve`) and retry.
