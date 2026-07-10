"""
Translator — turns any English string into a supported Indian language.

Backend priority (per string, cached):
  1. Google Translate (deep-translator) — best Indian-language quality, no API key
  2. LLM (Claude / Ollama)              — fallback if Google is unreachable
  3. English                           — final fallback (nothing breaks)

Quoted button names / proper nouns are masked before translation and restored
afterwards, so on-screen instructions keep the exact English label the user must
click on the (English) government portal.

Adding a new language = add one row to LANGUAGES. No other code changes.
"""

from __future__ import annotations

import re
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

from services.llm_client import get_llm

try:
    from deep_translator import GoogleTranslator
    _HAS_GOOGLE = True
except Exception:  # pragma: no cover
    GoogleTranslator = None
    _HAS_GOOGLE = False


LANGUAGES = [
    {"code": "en", "name": "English", "native": "English"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
    {"code": "te", "name": "Telugu", "native": "తెలుగు"},
    {"code": "ta", "name": "Tamil", "native": "தமிழ்"},
    {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ"},
    {"code": "ml", "name": "Malayalam", "native": "മലയാളം"},
    {"code": "mr", "name": "Marathi", "native": "मराठी"},
    {"code": "gu", "name": "Gujarati", "native": "ગુજરાતી"},
    {"code": "bn", "name": "Bengali", "native": "বাংলা"},
    {"code": "pa", "name": "Punjabi", "native": "ਪੰਜਾਬੀ"},
    {"code": "or", "name": "Odia", "native": "ଓଡ଼ିଆ"},
]

_LANG_BY_CODE: Dict[str, Dict[str, str]] = {lang["code"]: lang for lang in LANGUAGES}
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


class Translator:
    def __init__(self) -> None:
        self.llm = get_llm()
        self._cache: Dict[str, str] = {}

    # ── public API ────────────────────────────────────────────────────────────
    def is_supported(self, lang: str) -> bool:
        return lang in _LANG_BY_CODE

    def translate(self, text: str, lang: str) -> str:
        if not text or lang == "en" or not self.is_supported(lang):
            return text
        return self.translate_batch([text], lang)[0]

    def translate_batch(self, texts: List[str], lang: str) -> List[str]:
        if lang == "en" or not self.is_supported(lang):
            return list(texts)

        out: List[Optional[str]] = [None] * len(texts)
        pending, pending_idx = [], []
        for i, t in enumerate(texts):
            if not t or not t.strip():
                out[i] = t
                continue
            cached = self._cache.get(self._key(lang, t))
            if cached is not None:
                out[i] = cached
            else:
                pending.append(t)
                pending_idx.append(i)

        if pending:
            translated = self._translate_pending(pending, lang)
            for j, orig_i in enumerate(pending_idx):
                tr = translated[j] if j < len(translated) and translated[j] else texts[orig_i]
                self._cache[self._key(lang, texts[orig_i])] = tr
                out[orig_i] = tr

        return [out[i] if out[i] is not None else texts[i] for i in range(len(texts))]

    # ── translation backends ──────────────────────────────────────────────────
    def _translate_pending(self, texts: List[str], lang: str) -> List[str]:
        # 1. Google Translate (threaded for speed on first language switch)
        if _HAS_GOOGLE:
            try:
                with ThreadPoolExecutor(max_workers=8) as ex:
                    results = list(ex.map(lambda t: self._google_one(t, lang), texts))
                if all(r is not None for r in results):
                    return results  # type: ignore
            except Exception as e:
                print(f"[Translator] Google batch error: {e}", flush=True)

        # 2. LLM fallback
        if self.llm.available:
            llm = self._llm_translate(texts, lang)
            if llm:
                return llm

        # 3. English fallback
        return texts

    def _google_one(self, text: str, lang: str) -> Optional[str]:
        masked, tokens = self._protect(text)
        try:
            translated = GoogleTranslator(source="en", target=lang).translate(masked)
            if not translated:
                return None
            return self._restore(translated, tokens)
        except Exception:
            return None

    def _llm_translate(self, texts: List[str], lang: str) -> Optional[List[str]]:
        lang_name = _LANG_BY_CODE[lang]["name"]
        system = (
            f"Translate each string in the JSON array to {lang_name}. Keep any text inside quotes and "
            "brand names (CivicOS AI, ePASS, Aadhaar, OTP) unchanged. Return ONLY a JSON array of the "
            "translations in order, nothing else."
        )
        try:
            reply = self.llm.chat(system, json.dumps(texts, ensure_ascii=False), temperature=0.0, max_tokens=2000)
            if not reply:
                return None
            s = reply.strip()
            m = re.search(r"\[[\s\S]*\]", s)
            if m:
                data = json.loads(m.group(0))
                if isinstance(data, list) and all(isinstance(x, str) for x in data) and len(data) == len(texts):
                    return data
        except Exception as e:
            print(f"[Translator] LLM fallback error: {e}", flush=True)
        return None

    # ── quoted-name protection ────────────────────────────────────────────────
    @staticmethod
    def _protect(text: str):
        tokens: List[str] = []

        def repl(m):
            tokens.append(m.group(0))
            return f"{{{len(tokens) - 1}}}"

        return _QUOTED.sub(repl, text), tokens

    @staticmethod
    def _restore(text: str, tokens: List[str]) -> str:
        for i, tok in enumerate(tokens):
            text = text.replace(f"{{{i}}}", tok)
        return text

    @staticmethod
    def _key(lang: str, text: str) -> str:
        return f"{lang}\x00{text}"


_translator: Optional[Translator] = None


def get_translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator
