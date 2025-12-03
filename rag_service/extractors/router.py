from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

import fitz  # PyMuPDF
import docx

from ..utils import clean_text


CONTENT_KEYS = ['text', 'content', 'message', 'body', 'comment', 'post', 'description']
DATE_KEYS = ['created_at', 'timestamp', 'date', 'posted_on']


def _extract_txt(path: Path) -> List[str]:
    try:
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            return [clean_text(f.read())]
    except Exception:
        return []


def _extract_md(path: Path) -> List[str]:
    # Treat as plain text
    return _extract_txt(path)


def _extract_docx(path: Path) -> List[str]:
    try:
        document = docx.Document(str(path))
        paras = [p.text for p in document.paragraphs if p.text and p.text.strip()]
        return [clean_text("\n\n".join(paras))]
    except Exception:
        return []


def _extract_pdf(path: Path) -> List[str]:
    out: List[str] = []
    try:
        with fitz.open(str(path)) as doc:
            for page in doc:
                text = page.get_text()
                if text and text.strip():
                    out.append(clean_text(text))
    except Exception:
        return []
    return out


def _extract_csv(path: Path) -> List[str]:
    out: List[str] = []
    try:
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_text = " ".join([v for v in row.values() if v])
                if len(row_text) > 20:
                    out.append(clean_text(row_text))
    except Exception:
        return []
    return out


def _extract_json(path: Path) -> List[str]:
    out: List[str] = []
    try:
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                return []
        if isinstance(data, dict):
            data = [data]
        for item in data:
            content = None
            for k in CONTENT_KEYS:
                if k in item and item[k]:
                    content = item[k]
                    break
            date = "Unknown Date"
            for k in DATE_KEYS:
                if k in item and item[k]:
                    date = str(item[k])
                    break
            if content and isinstance(content, str) and len(content) > 20:
                out.append(f"[{date}] {clean_text(content)}")
    except Exception:
        return []
    return out


def extract_text_by_path(filepath: str) -> List[str]:
    path = Path(filepath)
    ext = path.suffix.lower()
    if ext in {'.txt'}:
        return _extract_txt(path)
    if ext in {'.md', '.markdown'}:
        return _extract_md(path)
    if ext in {'.pdf'}:
        return _extract_pdf(path)
    if ext in {'.docx'}:
        return _extract_docx(path)
    if ext in {'.csv'}:
        return _extract_csv(path)
    if ext in {'.json'}:
        return _extract_json(path)
    # Fallback: try read as text
    return _extract_txt(path)
