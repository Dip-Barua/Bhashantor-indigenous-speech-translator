import os
import shutil
import sqlite3
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services.translator import translator
from services.transcription import transcribe_audio
from services.speech import synthesize_speech

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="Bhashantor API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LANG_NAMES = {"en": "English", "bn": "Bangla", "bl": "Banglish", "ccp": "Chakma", "rmz": "Marma"}

class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    source_lang: str
    target_lang: str
    include_banglish: bool = False
    mode: Literal["standard", "offline_fallback"] = "standard"

class VerifyRequest(BaseModel):
    source_text: str
    translated_text: str
    suggested_correction: str
    source_lang: str
    target_lang: str

class SpeakRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str = "English"

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "model_ready": translator.ready,
        "supported_languages": ["Bangla", "English", "Banglish", "Chakma", "Marma"],
        "language_codes": LANG_NAMES,
        "available_modes": ["standard", "offline_fallback"],
        "engine": translator.engine,
        "tts_provider": "piper-local" if os.getenv("PIPER_MODEL") else ("espeak-ng-local" if shutil.which("espeak-ng") or shutil.which("espeak") else "browser-voice"),
    }

@app.post("/api/translate")
def translate(req: TranslateRequest):
    return translator.translate(
        req.text, req.source_lang, req.target_lang,
        include_banglish=req.include_banglish, mode=req.mode,
    )

@app.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: Literal["Bangla", "English", "Banglish"] = Form("English"),
):
    audio = await file.read()
    text = await transcribe_audio(audio, file.filename or "audio.webm", file.content_type, language)
    return {"text": text, "language": language}

@app.post("/api/speak")
def speak(req: SpeakRequest):
    audio, provider = synthesize_speech(req.text, req.language)
    if audio:
        return Response(content=audio, media_type="audio/wav", headers={"X-TTS-Provider": provider})
    return Response(status_code=503, content="No local TTS provider configured; use browser voice.", media_type="text/plain")

@app.post("/api/verify")
def verify(req: VerifyRequest):
    db_path = BASE_DIR / "community_feedback.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_text TEXT, translated_text TEXT,
            suggested_correction TEXT, source_lang TEXT,
            target_lang TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("INSERT INTO corrections (source_text, translated_text, suggested_correction, source_lang, target_lang) VALUES (?, ?, ?, ?, ?)",
                   (req.source_text, req.translated_text, req.suggested_correction, req.source_lang, req.target_lang))
    return {"status": "saved", "message": "Thank you for improving Bhashantor."}
