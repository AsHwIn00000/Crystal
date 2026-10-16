import re
from dataclasses import dataclass, field
from typing import List
from app.ingestion.parsers.base import ParsedPage


@dataclass
class Chunk:
    chunk_index: int
    content: str
    page_number: int
    metadata: dict = field(default_factory=dict)


def _split_into_sentences(text: str) -> List[str]:
    """Split text on sentence boundaries, falling back to space-separated tokens."""
    # Split on ., !, ? followed by whitespace or end of string
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def chunk_pages(pages: List[ParsedPage], chunk_size: int = 500, chunk_overlap: int = 50) -> List[Chunk]:
    """Sliding window chunker — splits parsed pages into overlapping chunks.

    Strategy:
    - Split each page's text on sentence boundaries
    - If a sentence exceeds chunk_size words, further split on word boundaries
    - Build chunks up to chunk_size words
    - Maintain chunk_overlap words of context between consecutive chunks
    - Each chunk carries the page number from its source page
    """
    chunks = []
    chunk_index = 0

    for page in pages:
        if not page.text or not page.text.strip():
            continue

        sentences = _split_into_sentences(page.text)
        if not sentences:
            continue

        current_words = []
        current_word_count = 0

        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_word_count = len(sentence_words)

            # If the sentence itself exceeds chunk_size, break it into sub-chunks
            if sentence_word_count > chunk_size:
                # Flush current buffer first
                if current_words:
                    content = ' '.join(current_words)
                    chunks.append(Chunk(
                        chunk_index=chunk_index,
                        content=content,
                        page_number=page.page_number,
                        metadata=dict(page.metadata)
                    ))
                    chunk_index += 1
                    current_words = current_words[-chunk_overlap:] if chunk_overlap > 0 else []
                    current_word_count = len(current_words)

                # Break the long sentence into sized pieces
                pos = 0
                while pos < len(sentence_words):
                    piece = sentence_words[pos:pos + chunk_size]
                    content = ' '.join(piece)
                    chunks.append(Chunk(
                        chunk_index=chunk_index,
                        content=content,
                        page_number=page.page_number,
                        metadata=dict(page.metadata)
                    ))
                    chunk_index += 1
                    pos += chunk_size - chunk_overlap
                continue

            # If adding this sentence would exceed chunk_size, emit the current chunk
            if current_word_count + sentence_word_count > chunk_size and current_words:
                content = ' '.join(current_words)
                chunks.append(Chunk(
                    chunk_index=chunk_index,
                    content=content,
                    page_number=page.page_number,
                    metadata=dict(page.metadata)
                ))
                chunk_index += 1

                # Keep overlap: retain the last chunk_overlap words
                overlap_words = current_words[-chunk_overlap:] if chunk_overlap > 0 else []
                current_words = overlap_words + sentence_words
                current_word_count = len(current_words)
            else:
                current_words.extend(sentence_words)
                current_word_count += sentence_word_count

        # Emit any remaining content
        if current_words:
            content = ' '.join(current_words)
            chunks.append(Chunk(
                chunk_index=chunk_index,
                content=content,
                page_number=page.page_number,
                metadata=dict(page.metadata)
            ))
            chunk_index += 1

    return chunks
