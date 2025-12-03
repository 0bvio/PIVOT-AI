from typing import List, Dict


def chunk_text(text: str, chunk_size: int, overlap: int, source_id: str) -> List[Dict]:
    """
    Simple paragraph-aware chunker with character-based windowing.
    Returns list of {text, metadata{source_id, chunk_index, chunk_method}}.
    """
    chunks: List[Dict] = []
    if not text:
        return chunks

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    current = ""
    chunk_index = 0

    for p in paragraphs:
        candidate_len = len(current) + (2 if current else 0) + len(p)
        if candidate_len > chunk_size and current:
            chunks.append({
                "text": current.strip(),
                "metadata": {
                    "source_id": source_id,
                    "chunk_index": chunk_index,
                    "chunk_method": "chunker_v1"
                }
            })
            chunk_index += 1
            back = current[-overlap:] if len(current) > overlap else current
            current = (back + "\n\n" + p).strip()
        else:
            current = (current + ("\n\n" if current else "") + p).strip()

    if current:
        chunks.append({
            "text": current.strip(),
            "metadata": {
                "source_id": source_id,
                "chunk_index": chunk_index,
                "chunk_method": "chunker_v1"
            }
        })

    return chunks
