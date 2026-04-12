from pathlib import Path
from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult

class TextParser(BaseParser):
    supported_extensions = [".txt", ".md", ".log", ".cfg", ".ini", ".json", ".xml", ".yaml", ".yml"]

    def parse(self, file_path: Path) -> ParseResult:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return ParseResult(
            pages=[ParsedPage(text=text, page_number=1)],
            metadata={"encoding": "utf-8"},
            file_type=file_path.suffix.lower().lstrip("."),
        )
