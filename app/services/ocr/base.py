from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List


@dataclass
class OCRPage:
    page_number: int
    text: str           # extracted markdown/plain text
    raw_response: str   # raw model output before cleanup
    error: Optional[str] = None


@dataclass
class OCRResult:
    provider: str
    pages: List[OCRPage]
    total_pages: int
    error: Optional[str] = None

    @property
    def full_text(self) -> str:
        return '\n\n'.join(p.text for p in self.pages if p.text)


class OCRProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def ocr_image(self, file_path: Path) -> OCRResult: ...

    @abstractmethod
    def ocr_pdf(self, file_path: Path) -> OCRResult: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
