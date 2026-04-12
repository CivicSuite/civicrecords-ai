import re
from dataclasses import dataclass

@dataclass
class Chunk:
    text: str
    index: int
    page_number: int | None = None
    token_count: int = 0

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def split_into_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50, page_number: int | None = None) -> list[Chunk]:
    if not text.strip():
        return []
    sentences = split_into_sentences(text)
    if not sentences:
        return []
    chunks = []
    current_sentences: list[str] = []
    current_tokens = 0
    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)
        if current_tokens + sentence_tokens > chunk_size and current_sentences:
            chunk_text_str = " ".join(current_sentences)
            chunks.append(Chunk(text=chunk_text_str, index=len(chunks), page_number=page_number, token_count=estimate_tokens(chunk_text_str)))
            overlap_sentences: list[str] = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                if overlap_tokens + estimate_tokens(s) > chunk_overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += estimate_tokens(s)
            current_sentences = overlap_sentences
            current_tokens = overlap_tokens
        current_sentences.append(sentence)
        current_tokens += sentence_tokens
    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        chunks.append(Chunk(text=chunk_text_str, index=len(chunks), page_number=page_number, token_count=estimate_tokens(chunk_text_str)))
    return chunks

def chunk_pages(pages: list[dict], chunk_size: int = 500, chunk_overlap: int = 50) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for page in pages:
        page_chunks = chunk_text(text=page["text"], chunk_size=chunk_size, chunk_overlap=chunk_overlap, page_number=page.get("page_number"))
        for chunk in page_chunks:
            chunk.index = len(all_chunks)
            all_chunks.append(chunk)
    return all_chunks
