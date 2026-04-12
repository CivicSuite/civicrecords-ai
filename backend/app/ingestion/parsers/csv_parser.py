import csv
from pathlib import Path
from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult

class CsvParser(BaseParser):
    supported_extensions = [".csv", ".tsv"]

    def parse(self, file_path: Path) -> ParseResult:
        delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","
        rows = []
        with open(file_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                rows.append(" | ".join(row))
        text = "\n".join(rows)
        return ParseResult(
            pages=[ParsedPage(text=text, page_number=1)],
            metadata={"row_count": len(rows), "delimiter": delimiter},
            file_type="csv",
        )
