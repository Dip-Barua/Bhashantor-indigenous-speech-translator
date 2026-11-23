const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type TranslationResponse = {
  translated_text: string;
  banglish_text: string | null;
  source_lang: string;
  target_lang: string;
  engine: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

export const api = {
  health: () => request<{ status: string; model_ready: boolean; supported_languages: string[]; available_modes: string[] }>("/api/health"),
  translate: (body: { text: string; source_lang: string; target_lang: string; include_banglish: boolean; mode: "standard" | "offline_fallback" }) =>
    request<TranslationResponse>("/api/translate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  transcribe: (form: FormData) => request<{ text: string }>("/api/transcribe", { method: "POST", body: form }),
  verify: (body: { source_text: string; translated_text: string; suggested_correction: string; source_lang: string; target_lang: string }) =>
    request<{ status: string; message: string }>("/api/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  speak: async (text: string, language: string): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }),
    });
    if (!res.ok) throw new Error("Local TTS unavailable");
    return res.blob();
  },
};
