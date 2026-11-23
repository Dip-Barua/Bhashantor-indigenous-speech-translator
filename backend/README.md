# Bhashantor Backend

## Detected model interface

- The project uses five language codes: `en`, `bn`, `bl`, `ccp`, and `rmz`.
- Public names are **English**, **Bangla**, **Banglish**, **Chakma**, and **Marma**.
- Training uses `facebook/nllb-200-distilled-600M` with target direction tags such as `<2ccp>` and a fine-tuned checkpoint.
- A local dictionary/lexicon model is supported when `ai-model/lexicon/model.pkl` exists.
- A no-checkpoint fallback performs exact dataset lookup, then passes text through unchanged.
- Banglish transliteration is available from `ai-model/bn_translit.py` for Bangla text.

Set `MODEL_CHECKPOINT` to a local Hugging Face checkpoint directory or model ID to enable NLLB loading. Set `GEMINI_API_KEYS` to comma-separated keys for server audio transcription.

## Bhashantor API Setup

### Supported model interface

- Languages and codes: English (`en`), Bangla (`bn`), Banglish (`bl`), Chakma (`ccp`), Marma (`rmz`).
- Training model: `facebook/nllb-200-distilled-600M`, with target tags such as `<2ccp>`.
- Local fallback: exact dataset lookup followed by unchanged text.
- Optional lexicon: `ai-model/lexicon/model.pkl`.
- Bangla Romanization: `ai-model/bn_translit.py`.

### API credentials

Copy `backend/.env.example` to `backend/.env`:

```bash
cp backend/.env.example backend/.env
```

```env
MODEL_CHECKPOINT=
GEMINI_API_KEYS=
```

- `MODEL_CHECKPOINT`: optional local NLLB checkpoint directory or Hugging Face model ID. Leave empty to use the local dataset/lexicon fallback.
- `GEMINI_API_KEYS`: optional comma-separated Gemini API keys. Example:

```env
GEMINI_API_KEYS=AIza_example_key_1,AIza_example_key_2
```

The transcription service rotates through keys and tries the next key when a key fails or reaches its quota. Browser speech recognition remains the primary live-recognition method and does not require a Gemini key.

Create Gemini keys in Google AI Studio, then store them only in `backend/.env`. Never commit API keys or place them in `NEXT_PUBLIC_*` variables. `backend/.env` is ignored by Git.

### Frontend configuration

Copy `frontend/.env.local.example` to `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

This public variable identifies the backend URL only. Do not add Gemini or private credentials to it.

## Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The API health endpoint is `http://localhost:8000/api/health`.

## Local text-to-speech

The `/api/speak` endpoint prefers Piper and otherwise uses `espeak-ng` locally. No TTS API key is required.

Ubuntu/Debian setup:

```bash
sudo apt-get install -y espeak-ng
```

Optional Piper neural-voice setup:

```env
PIPER_EXECUTABLE=/absolute/path/to/piper
PIPER_MODEL=/absolute/path/to/bangla-model.onnx
```

Piper is preferred when both variables point to valid files. The frontend falls back to browser voices if `/api/speak` is unavailable.
