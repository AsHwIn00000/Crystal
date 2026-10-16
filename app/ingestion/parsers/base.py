from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ParsedPage:
    page_number: int
    text: str
    metadata: dict = field(default_factory=dict)


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path) -> List[ParsedPage]:
        """Parse a file and return a list of ParsedPage objects."""
        ...
