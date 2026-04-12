from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ParsedPage:
    text: str
    page_number: int | None = None
    metadata: dict = field(default_factory=dict)

@dataclass
class ParseResult:
    pages: list[ParsedPage]
    metadata: dict = field(default_factory=dict)
    file_type: str = ""

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def total_chars(self) -> int:
        return sum(len(p.text) for p in self.pages)

class BaseParser(ABC):
    supported_extensions: list[str] = []

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult: ...

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions
