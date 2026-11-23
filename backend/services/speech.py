import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def synthesize_speech(text: str, language: str) -> tuple[bytes | None, str]:
    """Generate WAV locally. Prefer Piper, then espeak-ng, never require a cloud API."""
    text = text.strip()
    if not text:
        return None, "empty-text"

    piper = os.getenv("PIPER_EXECUTABLE") or shutil.which("piper")
    piper_model = os.getenv("PIPER_MODEL")
    if piper and piper_model and Path(piper_model).exists():
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "speech.wav"
            result = subprocess.run(
                [piper, "--model", piper_model, "--output_file", str(wav)],
                input=text,
                text=True,
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0 and wav.exists():
                return wav.read_bytes(), "piper-local"

    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if espeak:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "speech.wav"
            voice = "bn" if language in {"Bangla", "Banglish", "Chakma", "Marma"} else "en-us"
            result = subprocess.run(
                [espeak, "-v", voice, "-w", str(wav), text],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0 and wav.exists():
                return wav.read_bytes(), "espeak-ng-local"

    return None, "browser-voice"
