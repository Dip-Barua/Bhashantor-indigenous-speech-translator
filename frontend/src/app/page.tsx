"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeftRight, AlertCircle, CheckCircle2, Copy, Mic, Square, Trash2, Volume2, Wifi, WifiOff, X } from "lucide-react";
import { api, TranslationResponse } from "@/lib/api";
import { offlinePhrases } from "@/data/offlinePhrases";

const languages = ["Bangla", "English", "Banglish", "Chakma", "Marma"] as const;
type Language = typeof languages[number];
type HistoryItem = TranslationResponse & { input: string };

declare global {
  interface Window { SpeechRecognition?: any; webkitSpeechRecognition?: any }
}

function roughBanglish(text: string) {
  const map: Record<string, string> = { "ক":"k","খ":"kh","গ":"g","ঘ":"gh","চ":"ch","ছ":"chh","জ":"j","ঝ":"jh","ট":"t","ঠ":"th","ড":"d","ঢ":"dh","ত":"t","থ":"th","দ":"d","ধ":"dh","ন":"n","প":"p","ফ":"ph","ব":"b","ভ":"bh","ম":"m","য":"j","র":"r","ল":"l","শ":"sh","স":"s","হ":"h","া":"a","ি":"i","ী":"i","ু":"u","ূ":"u","ে":"e","ো":"o","ং":"ng","।":"." };
  return text.split("").map((c) => map[c] ?? c).join("");
}

export default function Home() {
  const [source, setSource] = useState<Language>("Bangla");
  const [target, setTarget] = useState<Language>("English");
  const [input, setInput] = useState("");
  const [result, setResult] = useState<TranslationResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [connected, setConnected] = useState(false);
  const [offline, setOffline] = useState(false);
  const [recording, setRecording] = useState(false);
  const [speechError, setSpeechError] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>("All");
  const [seconds, setSeconds] = useState(0);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [correction, setCorrection] = useState("");
  const recognitionRef = useRef<any>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const shouldRestartRef = useRef(false);

  useEffect(() => {
    api.health().then(() => setConnected(true)).catch(() => setConnected(false));
    const saved = localStorage.getItem("bhashantor-history");
    if (saved) setHistory(JSON.parse(saved));
  }, []);

  useEffect(() => {
    if (!recording) return;
    const id = window.setInterval(() => setSeconds((v) => v + 1), 1000);
    return () => window.clearInterval(id);
  }, [recording]);

  async function translate() {
    if (!input.trim()) return;
    if (offline) {
      const local = history.find((h) => h.input.toLowerCase() === input.toLowerCase());
      if (local) setResult(local);
      else {
        const phrase = offlinePhrases.find((p) => [p.english, p.bangla, p.chakma, p.marma].some((value) => value.toLowerCase() === input.toLowerCase()));
        if (phrase) {
          const translated = target === "Chakma" ? phrase.chakma : target === "Marma" ? phrase.marma : target === "Bangla" ? phrase.bangla : phrase.english;
          setResult({ translated_text: translated, banglish_text: null, source_lang: source, target_lang: target, engine: "offline phrase" });
        }
      }
      return;
    }
    try {
      const res = await api.translate({ text: input, source_lang: source, target_lang: target, include_banglish: false, mode: "standard" });
      setResult(res);
      const item = { ...res, input }; setHistory((old) => { const next = [item, ...old].slice(0, 8); localStorage.setItem("bhashantor-history", JSON.stringify(next)); return next; });
    } catch {
      setConnected(false);
      if (offlinePhrases.some((p) => p.english.toLowerCase() === input.toLowerCase())) setOffline(true);
    }
  }

  async function toggleRecording() {
    if (recording) {
      shouldRestartRef.current = false;
      setRecording(false);
      recognitionRef.current?.stop();
      if (mediaRef.current?.state === "recording") mediaRef.current.stop();
      return;
    }

    setSpeechError("");
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setSpeechError("Live speech recognition is not supported here. Please use Chrome or Edge, or type manually.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setSeconds(0);
      setRecording(true);
      shouldRestartRef.current = true;

      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => stream.getTracks().forEach((track) => track.stop());
      recorder.start();
      mediaRef.current = recorder;

      const recognition = new Recognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = source === "Bangla" || source === "Banglish" ? "bn-BD" : source === "English" ? "en-US" : "en-US";
      let finalTranscript = "";

      recognition.onstart = () => setRecording(true);
      recognition.onresult = (event: any) => {
        let interimTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const piece = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalTranscript += piece + " ";
          else interimTranscript += piece;
        }
        setInput((finalTranscript + interimTranscript).trimStart());
      };
      recognition.onerror = (event: any) => {
        if (event.error === "not-allowed") {
          shouldRestartRef.current = false;
          setSpeechError("Microphone permission was denied. Allow microphone access and try again.");
        } else if (event.error === "network") {
          shouldRestartRef.current = false;
          setSpeechError("Speech recognition network unavailable. Check your internet connection or type manually. Browser recognition is a cloud-backed service.");
        } else if (event.error === "no-speech") {
          setSpeechError("No speech detected yet. Try speaking closer to the microphone.");
        } else if (event.error !== "aborted") {
          setSpeechError(`Speech recognition stopped: ${event.error}`);
        }
      };
      recognition.onend = () => {
        if (shouldRestartRef.current) {
          window.setTimeout(() => {
            try { recognition.start(); } catch { /* recognition is already active or unavailable */ }
          }, 350);
        }
      };
      recognition.start();
      recognitionRef.current = recognition;
    } catch {
      shouldRestartRef.current = false;
      setRecording(false);
      setSpeechError("Could not access the microphone. Check browser permissions and HTTPS/localhost access.");
    }
  }

  async function speakOutput() {
    if (!output || typeof window === "undefined") return;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();

    try {
      const blob = await api.speak(output, target);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      setSpeaking(true);
      audio.onended = () => { setSpeaking(false); URL.revokeObjectURL(url); };
      audio.onerror = () => { setSpeaking(false); URL.revokeObjectURL(url); };
      await audio.play();
      return;
    } catch {
      // Fall back to browser voices when espeak-ng/Piper is not available.
    }

    if (!("speechSynthesis" in window)) return;

    const segments = output.match(/[A-Za-z0-9'’.,!?;:()+\-]+(?:\s+|$)|[^A-Za-z0-9'’.,!?;:()+\-]+/g) || [output];
    let segmentIndex = 0;
    setSpeaking(true);

    const speakNext = () => {
      if (segmentIndex >= segments.length) {
        setSpeaking(false);
        return;
      }

      const text = segments[segmentIndex++].trim();
      if (!text) {
        speakNext();
        return;
      }

      const utterance = new SpeechSynthesisUtterance(text);
      const useEnglishVoice = target === "English" && /^[A-Za-z0-9]/.test(text);
      utterance.lang = useEnglishVoice ? "en-US" : "bn-BD";
      const matchingVoice = window.speechSynthesis.getVoices().find((voice) =>
        voice.lang.toLowerCase().startsWith(useEnglishVoice ? "en" : "bn")
      );
      if (matchingVoice) utterance.voice = matchingVoice;
      utterance.rate = useEnglishVoice ? 0.92 : 0.88;
      utterance.onend = speakNext;
      utterance.onerror = speakNext;
      window.speechSynthesis.speak(utterance);
    };

    speakNext();
  }

  function swapLanguages() {
    setSource(target); setTarget(source);
    setInput(result?.translated_text || input);
  }

  function usePhrase(phrase: typeof offlinePhrases[number]) {
    const sourceText = source === "Chakma" ? phrase.chakma
      : source === "Marma" ? phrase.marma
      : source === "Bangla" ? phrase.bangla
      : phrase.english;
    const targetText = target === "Chakma" ? phrase.chakma
      : target === "Marma" ? phrase.marma
      : target === "Bangla" ? phrase.bangla
      : phrase.english;
    setInput(sourceText);
    setResult({ translated_text: targetText, banglish_text: null, source_lang: source, target_lang: target, engine: "offline phrase" });
  }

  const output = result?.translated_text;
  const time = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <main className="min-h-screen px-4 py-5 md:px-8 lg:px-12">
      <header className="mx-auto flex max-w-[1380px] items-center justify-between">
        <div><div className="flex items-center gap-3"><img src="/bhashantor-icon.png" alt="Bhashantor" className="h-12 w-12 rounded-2xl object-contain"/><h1 className="text-xl font-bold tracking-tight md:text-2xl">Bhashantor <span className="text-emerald-700">(ভাষান্তর)</span></h1></div></div>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-full border border-emerald-100 bg-white px-3 py-2 text-xs font-semibold text-slate-600 sm:flex">
            {connected ? <Wifi size={15} className="text-emerald-600" /> : <WifiOff size={15} className="text-amber-500" />}{connected ? "Connected" : "Offline"}
          </div>
          <button onClick={() => setOffline((v) => !v)} className="flex items-center gap-2 text-sm font-semibold text-slate-600"><span>Offline</span><span className={`relative h-6 w-11 rounded-full transition ${offline ? "bg-emerald-600" : "bg-slate-300"}`}><span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${offline ? "left-6" : "left-1"}`} /></span></button>
        </div>
      </header>

      <section className="glass mx-auto mt-6 max-w-[1380px] rounded-3xl p-3 md:p-4">
        <div className="grid items-center gap-3 md:grid-cols-[1fr_auto_1fr]">
          <label className="flex items-center rounded-2xl bg-slate-50 px-4 py-3"><span className="mr-3 text-xs font-bold uppercase text-slate-400">From</span><select value={source} onChange={(e) => setSource(e.target.value as Language)} className="w-full bg-transparent font-semibold outline-none">{languages.map((l) => <option key={l}>{l}</option>)}</select></label>
          <button aria-label="Swap languages" onClick={swapLanguages} className="mx-auto grid h-11 w-11 place-items-center rounded-full border border-emerald-100 bg-white text-emerald-700 shadow-sm transition hover:-translate-y-0.5"><ArrowLeftRight size={18} /></button>
          <label className="flex items-center rounded-2xl bg-emerald-50 px-4 py-3"><span className="mr-3 text-xs font-bold uppercase text-emerald-500">To</span><select value={target} onChange={(e) => setTarget(e.target.value as Language)} className="w-full bg-transparent font-semibold text-emerald-900 outline-none">{languages.map((l) => <option key={l}>{l}</option>)}</select></label>
        </div>
      </section>

      <section className="mx-auto mt-5 grid max-w-[1380px] gap-5 lg:grid-cols-2">
        <div className="glass rounded-3xl p-5 md:p-6">
          <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-bold">Record & Speak</h2></div>
          <div className="flex min-h-28 items-center justify-center rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/40">
            <button onClick={toggleRecording} className={`relative grid h-16 w-16 place-items-center rounded-full text-white shadow-lg transition ${recording ? "bg-rose-500" : "bg-emerald-700"}`}>{recording ? <Square fill="currentColor" size={20} /> : <Mic size={24} />}{recording && <span className="absolute inset-0 animate-ping rounded-full border border-rose-400" />}</button>
            {recording && <div className="ml-6 flex h-10 items-end gap-1">{[18,30,22,38,26,34,16,28].map((h,i) => <span key={i} className="wave-bar w-1 rounded-full bg-emerald-500" style={{height:h, animationDelay:`${i*.08}s`}} />)}</div>}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs"><span className="font-bold text-slate-500">{recording ? "Listening…" : "Tap microphone to speak"}</span><span className="rounded-full bg-slate-100 px-2 py-1 font-mono font-bold">{time}</span></div>
          {speechError && <div className="mt-3 flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700"><AlertCircle className="mt-0.5 shrink-0" size={14}/><span>{speechError}</span></div>}
          <label className="mt-5 block text-sm font-bold text-slate-600">Live transcript</label>
          <textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="Speak or type here…" className="mt-2 h-36 w-full resize-none rounded-2xl border border-slate-200 bg-white p-4 text-lg outline-none transition focus:border-emerald-400" />
          {false && input && <p className="mt-2 text-xs text-slate-400" />}
          <button onClick={translate} disabled={!input.trim()} className="mt-4 w-full rounded-2xl bg-emerald-700 py-3.5 font-bold text-white shadow-lg shadow-emerald-700/10 transition hover:bg-emerald-800 disabled:opacity-40">Translate</button>
        </div>

        <div className="glass rounded-3xl p-5 md:p-6">
          <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-bold">Translation & Result</h2><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">{target}</span></div>
          <div className="min-h-64 rounded-2xl border border-emerald-100 bg-gradient-to-br from-white to-emerald-50/50 p-5">
            {result ? <><div className="mb-4 flex items-center justify-between text-xs font-bold uppercase tracking-wide text-emerald-700"><span>{target}</span><span className="normal-case text-slate-400">{result.engine}</span></div><p className="whitespace-pre-wrap text-2xl font-semibold leading-relaxed text-slate-800">{output}</p></> : <div className="grid min-h-52 place-items-center text-center text-slate-400"><div><CheckCircle2 className="mx-auto mb-3 opacity-30" size={36} /><p>Your translation will appear here</p></div></div>}
          </div>
          <div className="mt-3 flex gap-2">
            <button onClick={() => output && navigator.clipboard.writeText(output)} className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold"><Copy size={16}/>Copy</button>
            <button onClick={speakOutput} disabled={!output} className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-bold ${speaking ? "border-rose-200 bg-rose-50 text-rose-600" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}><Volume2 size={16}/>{speaking ? "Speaking" : "Speak"}</button>
            <button onClick={() => { setInput(""); setResult(null); }} className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold"><Trash2 size={16}/>Clear</button>
          </div>
          <div className="mt-5"><h3 className="mb-2 text-sm font-bold text-slate-500">Recent history</h3><div className="max-h-32 space-y-2 overflow-auto">{history.length ? history.map((h,i) => <button key={i} onClick={() => { setInput(h.input); setResult(h); }} className="flex w-full items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-left text-sm"><span className="truncate pr-3">{h.input}</span><span className="max-w-32 truncate text-emerald-700">{h.translated_text}</span></button>) : <p className="text-sm text-slate-400">No translations yet</p>}</div></div>
        </div>
      </section>

      <section className="glass mx-auto mt-5 max-w-[1380px] rounded-3xl p-4 md:p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold md:text-base">Offline Emergency & Trekking Phrases</h2>
          <button onClick={() => setVerifyOpen(true)} className="rounded-xl border border-emerald-200 px-3 py-2 text-sm font-bold text-emerald-700">Community Verify</button>
        </div>
        <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
          {["All", "Water", "Trail & Direction", "Help & Safety", "Medical & Fever", "Accommodation"].map((category) => (
            <button key={category} onClick={() => setActiveCategory(category)} className={`shrink-0 rounded-full px-3 py-2 text-xs font-bold ${activeCategory === category ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-600"}`}>{category}</button>
          ))}
        </div>
        <div className="grid max-h-64 gap-2 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
          {offlinePhrases.filter((p) => activeCategory === "All" || p.category === activeCategory).map((p) => (
            <button key={p.label} onClick={() => usePhrase(p)} className="rounded-2xl border border-slate-100 bg-white p-3 text-left transition hover:-translate-y-0.5 hover:border-emerald-200">
              <span className="text-[10px] font-bold uppercase text-emerald-600">{p.category}</span>
              <p className="mt-1 text-sm font-semibold">{p.label}</p>
              <p className="mt-1 text-xs text-slate-500">{p[target === "Chakma" ? "chakma" : target === "Marma" ? "marma" : target === "Bangla" ? "bangla" : "english"]}</p>
            </button>
          ))}
        </div>
      </section>

      {verifyOpen && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/30 p-4 backdrop-blur-sm"><div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl"><div className="flex items-center justify-between"><h2 className="text-xl font-bold">Community Verify</h2><button onClick={() => setVerifyOpen(false)}><X size={20}/></button></div><p className="mt-2 text-sm text-slate-500">Suggest a correction for the current translation.</p><textarea value={correction} onChange={(e) => setCorrection(e.target.value)} className="mt-4 h-28 w-full rounded-2xl border border-slate-200 p-3 outline-none" placeholder="Your correction…"/><button onClick={async () => { if (!result) return; await api.verify({ source_text: input, translated_text: result.translated_text, suggested_correction: correction, source_lang: source, target_lang: target }).catch(() => undefined); setVerifyOpen(false); setCorrection(""); }} className="mt-4 w-full rounded-xl bg-emerald-700 py-3 font-bold text-white">Submit correction</button></div></div>}
    </main>
  );
}
