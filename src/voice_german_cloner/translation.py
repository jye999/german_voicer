from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

_MODEL_NAME = "Helsinki-NLP/opus-mt-en-de"


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


@lru_cache(maxsize=1)
def _model_tokenizer_device() -> tuple["AutoModelForSeq2SeqLM", "AutoTokenizer", "torch.device"]:
    """Load Marian once (no ``pipeline()`` — the ``translation`` task was removed in Transformers v5)."""
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_NAME)
    model.to(device)
    model.eval()
    return model, tokenizer, device


def _translate_batch(texts: list[str]) -> list[str]:
    import torch

    if not texts:
        return []
    model, tokenizer, device = _model_tokenizer_device()
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


def _translate_chunks(chunks: list[str]) -> str:
    if not chunks:
        return ""
    batch_size = 8
    parts: list[str] = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        parts.extend(s.strip() for s in _translate_batch(batch))
    return " ".join(parts).strip()


def translate_english_to_german_local(text: str) -> str:
    """Translate English to German using a local Marian model (no network at inference)."""
    text = text.strip()
    if not text:
        raise ValueError("Text cannot be empty.")

    paragraphs = text.split("\n\n")
    out_paragraphs: list[str] = []
    for block in paragraphs:
        block = block.strip()
        if not block:
            out_paragraphs.append("")
            continue
        chunks = _chunk_for_translation(block)
        out_paragraphs.append(_translate_chunks(chunks))

    return "\n\n".join(out_paragraphs).strip()
