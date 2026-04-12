from pathlib import Path
from app.ingestion.parsers.base import BaseParser, ParseResult
from app.ingestion.parsers.csv_parser import CsvParser
from app.ingestion.parsers.docx import DocxParser
from app.ingestion.parsers.email import EmailParser
from app.ingestion.parsers.html import HtmlParser
from app.ingestion.parsers.pdf import PdfParser
from app.ingestion.parsers.text import TextParser
from app.ingestion.parsers.xlsx import XlsxParser

_PARSERS: list[BaseParser] = [PdfParser(), DocxParser(), XlsxParser(), CsvParser(), EmailParser(), HtmlParser(), TextParser()]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}

def detect_parser(file_path: Path) -> BaseParser | None:
    for parser in _PARSERS:
        if parser.can_parse(file_path):
            return parser
    return None

def is_image_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in IMAGE_EXTENSIONS

__all__ = ["detect_parser", "is_image_file", "ParseResult", "BaseParser"]
