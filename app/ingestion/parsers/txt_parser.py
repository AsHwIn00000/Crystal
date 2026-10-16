import logging
from pathlib import Path
from app.ingestion.parsers.base import BaseParser, ParsedPage

logger = logging.getLogger(__name__)


class TxtParser(BaseParser):
    def parse(self, file_path: Path):
        # Returns the entire file as a single ParsedPage.
        # The word-based chunker handles all subdivision, giving TXT files the
        # same chunk granularity as other formats. No pre-splitting into blocks
        # to avoid double-chunking (chunk_pages would split again).
        try:
            text = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            text = file_path.read_text(encoding='latin-1')
        return [ParsedPage(page_number=1, text=text, metadata={})]
