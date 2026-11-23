import asyncio
import json
import os
import urllib.request

_KEY_INDEX = 0

async def transcribe_audio(audio: bytes, filename: str, content_type: str | None, language: str) -> str:
    keys = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
    if not keys:
        return "Live browser speech recognition is active. Add GEMINI_API_KEYS to enable server transcription."

    global _KEY_INDEX
    prompt = "Transcribe the audio to clean plain text. "
    if language == "Bangla":
        prompt += "Write the result in Bengali script."
    elif language == "Banglish":
        prompt += "Write the result in Romanized Bangla (Banglish)."
    else:
        prompt += "Write the result in English."

    for _ in range(len(keys)):
        key = keys[_KEY_INDEX % len(keys)]
        _KEY_INDEX = (_KEY_INDEX + 1) % len(keys)
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}, {"inline_data": {
                    "mime_type": content_type or "audio/webm", "data": __import__("base64").b64encode(audio).decode()
                }}]}]
            }
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as res:
                data = json.load(res)
            candidates = data.get("candidates", [])
            if candidates:
                return "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", [])).strip()
        except Exception:
            continue
    return ""
