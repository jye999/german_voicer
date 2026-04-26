from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

LANGUAGE_NAMES = {
    "en": "English",
    "de": "German",
    "zh": "Chinese",
    "es": "Spanish",
}

TRANSLATION_MODEL_NAMES = {
    ("en", "de"): "Helsinki-NLP/opus-mt-en-de",
    ("de", "en"): "Helsinki-NLP/opus-mt-de-en",
    ("en", "zh"): "Helsinki-NLP/opus-mt-en-zh",
    ("zh", "en"): "Helsinki-NLP/opus-mt-zh-en",
    ("en", "es"): "Helsinki-NLP/opus-mt-en-es",
    ("es", "en"): "Helsinki-NLP/opus-mt-es-en",
}


@dataclass(frozen=True)
class LanguageFlow:
    source_language: str
    target_language: str
    label: str


LANGUAGE_FLOWS = {
    "en-de": LanguageFlow("en", "de", "English -> German"),
    "de-de": LanguageFlow("de", "de", "German direct"),
    "en-zh": LanguageFlow("en", "zh", "English -> Chinese"),
    "zh-zh": LanguageFlow("zh", "zh", "Chinese direct"),
    "es-en": LanguageFlow("es", "en", "Spanish -> English"),
    "en-en": LanguageFlow("en", "en", "English direct"),
    "en-es": LanguageFlow("en", "es", "English -> Spanish"),
    "es-es": LanguageFlow("es", "es", "Spanish direct"),
    "de-en": LanguageFlow("de", "en", "German -> English"),
    "zh-en": LanguageFlow("zh", "en", "Chinese -> English"),
}


def language_name(language: str) -> str:
    try:
        return LANGUAGE_NAMES[language]
    except KeyError as exc:
        supported = ", ".join(sorted(LANGUAGE_NAMES))
        raise ValueError(f"Unsupported language '{language}'. Supported languages: {supported}.") from exc


def supported_language_codes() -> tuple[str, ...]:
    return tuple(LANGUAGE_NAMES)


def supported_translation_pairs() -> tuple[tuple[str, str], ...]:
    return tuple(TRANSLATION_MODEL_NAMES)


def supported_language_flows() -> dict[str, LanguageFlow]:
    return dict(LANGUAGE_FLOWS)


def _chunk_for_translation(text: str, max_chars: int = 400) -> list[str]:
    """Split into segments small enough for Marian's context window."""
    text = text.strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        while len(sent) > max_chars:
            if buf:
                chunks.append(" ".join(buf))
                buf = []
                size = 0
            chunks.append(sent[:max_chars])
            sent = sent[max_chars:].strip()
        if not sent:
            continue
        projected = size + len(sent) + (1 if buf else 0)
        if projected > max_chars and buf:
            chunks.append(" ".join(buf))
            buf = [sent]
            size = len(sent)
        else:
            buf.append(sent)
            size = projected
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def _translation_model_name(source_language: str, target_language: str) -> str:
    try:
        return TRANSLATION_MODEL_NAMES[(source_language, target_language)]
    except KeyError as exc:
        source = language_name(source_language)
        target = language_name(target_language)
        raise ValueError(f"Translation from {source} to {target} is not supported.") from exc


@lru_cache(maxsize=len(TRANSLATION_MODEL_NAMES))
def _model_tokenizer_device(
    source_language: str,
    target_language: str,
) -> tuple["AutoModelForSeq2SeqLM", "AutoTokenizer", "torch.device"]:
    """Load Marian once (no ``pipeline()`` — the ``translation`` task was removed in Transformers v5)."""
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    model_name = _translation_model_name(source_language, target_language)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model.to(device)
    model.eval()
    return model, tokenizer, device


def _translate_batch(texts: list[str], source_language: str, target_language: str) -> list[str]:
    import torch

    if not texts:
        return []
    model, tokenizer, device = _model_tokenizer_device(source_language, target_language)
    enc = tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.inference_mode():
        ids = model.generate(
            **enc,
            max_new_tokens=256,
            num_beams=4,
            early_stopping=True,
        )
    return tokenizer.batch_decode(ids, skip_special_tokens=True)


def _translate_chunks(chunks: list[str], source_language: str, target_language: str) -> str:
    if not chunks:
        return ""
    batch_size = 8
    parts: list[str] = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        parts.extend(s.strip() for s in _translate_batch(batch, source_language, target_language))
    return " ".join(parts).strip()


def translate_text_local(text: str, source_language: str, target_language: str) -> str:
    """Translate text using a local Marian model, or return it unchanged for direct speech."""
    source_language = source_language.strip().lower()
    target_language = target_language.strip().lower()
    language_name(source_language)
    language_name(target_language)
    text = text.strip()
    if not text:
        raise ValueError("Text cannot be empty.")
    if source_language == target_language:
        return text
    _translation_model_name(source_language, target_language)

    paragraphs = text.split("\n\n")
    out_paragraphs: list[str] = []
    for block in paragraphs:
        block = block.strip()
        if not block:
            out_paragraphs.append("")
            continue
        chunks = _chunk_for_translation(block)
        out_paragraphs.append(_translate_chunks(chunks, source_language, target_language))

    return "\n\n".join(out_paragraphs).strip()


def translate_english_to_german_local(text: str) -> str:
    """Translate English to German using a local Marian model (no network at inference)."""
    return translate_text_local(text, "en", "de")
