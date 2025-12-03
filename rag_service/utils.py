from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from pathlib import Path
from typing import List


DUPLICATE_HEADERS_TO_FILTER = ["Unknown Date"]


def clean_text(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def source_id_for_path(base_dir: str, filepath: str) -> str:
    try:
        relative_path = Path(filepath).relative_to(base_dir)
    except Exception:
        relative_path = Path(filepath).name
    path_hash = hashlib.sha1(str(relative_path).encode()).hexdigest()[:8]
    return f"DOC-{path_hash}"


def chunk_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def guess_mime_type(filepath: str) -> str:
    mt, _ = mimetypes.guess_type(filepath)
    return mt or "application/octet-stream"


def build_title_line(source_id: str, base_dir: str, filepath: str) -> str:
    try:
        relative_path = Path(filepath).relative_to(base_dir)
    except Exception:
        relative_path = Path(filepath).name
    return f"SOURCE ID: {source_id} | SOURCE PATH: {relative_path}\n\n"


def filter_duplicate_headers(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        s = (line or "").strip()
        if not s:
            continue
        is_duplicate = False
        for hdr in DUPLICATE_HEADERS_TO_FILTER:
            if s.startswith(f"[{hdr}]") and len(s) < 40:
                is_duplicate = True
                break
        if not is_duplicate:
            out.append(s)
    return out
