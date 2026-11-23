import importlib.util
import os
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai-model"
DATA = AI_DIR / "data" / "raw" / "dataset.csv"

LANG_NAMES = {"en": "English", "bn": "Bangla", "bl": "Banglish", "ccp": "Chakma", "rmz": "Marma"}
NAME_TO_CODE = {v: k for k, v in LANG_NAMES.items()}

class TranslatorService:
    def __init__(self):
        self.ready = False
        self.engine = "lexicon/fallback"
        self.df = None
        self.lex_model = None
        self._load()

    def _load(self):
        if DATA.exists():
            self.df = pd.read_csv(DATA, dtype=str, keep_default_na=False)
            self.ready = True
        pkl = AI_DIR / "lexicon" / "model.pkl"
        if pkl.exists():
            spec = importlib.util.spec_from_file_location("bhashantor_lexicon", AI_DIR / "lexicon_translate.py")
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(AI_DIR))
            spec.loader.exec_module(module)
            self.lex_model = module.LexModel.load(pkl)
            self.engine = "lexicon model"
        checkpoint = os.getenv("MODEL_CHECKPOINT")
        if checkpoint:
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(checkpoint)
                self.nllb_model = AutoModelForSeq2SeqLM.from_pretrained(checkpoint)
                self.engine = "NLLB checkpoint"
                self.ready = True
            except Exception:
                pass

    def _code(self, lang):
        lang = lang.strip()
        return lang if lang in LANG_NAMES else NAME_TO_CODE.get(lang, "en")

    def _banglish(self, text):
        try:
            sys.path.insert(0, str(AI_DIR))
            from bn_translit import sentence
            return sentence(text)
        except Exception:
            return None

    def translate(self, text, source_lang, target_lang, include_banglish=False, mode="standard"):
        source = self._code(source_lang)
        target = self._code(target_lang)
        if source == target:
            result = text
            engine = "passthrough"
        elif hasattr(self, "nllb_model"):
            try:
                enc = self.tokenizer([f"<2{target}> {text}"], return_tensors="pt", padding=True, truncation=True)
                generated = self.nllb_model.generate(**enc, max_new_tokens=64, num_beams=4)
                result = self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
                engine = "NLLB checkpoint"
            except Exception:
                result = self._fallback(text, source, target)
                engine = "lexicon/fallback"
        elif self.lex_model:
            result, _, _ = self.lex_model.translate(text, source, target)
            engine = "lexicon model"
        else:
            result = self._fallback(text, source, target)
            engine = "dataset exact/fallback"

        banglish = self._banglish(result) if include_banglish and target != "bl" else (result if include_banglish else None)
        if include_banglish and target == "en" and banglish is None:
            banglish = None
        return {
            "translated_text": result,
            "banglish_text": banglish,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "engine": engine,
        }

    def _fallback(self, text, source, target):
        if self.df is not None:
            source_col = LANG_NAMES[source]
            target_col = LANG_NAMES[target]
            key = re.sub(r"\s+", " ", text.strip().lower())
            row = self.df[self.df[source_col].str.strip().str.lower() == key]
            if not row.empty:
                return str(row.iloc[0][target_col])
        return text

translator = TranslatorService()
