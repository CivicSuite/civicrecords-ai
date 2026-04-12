from pathlib import Path
import pdfplumber
from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult

class PdfParser(BaseParser):
    supported_extensions = [".pdf"]

    def parse(self, file_path: Path) -> ParseResult:
        pages = []
        metadata = {}
        with pdfplumber.open(file_path) as pdf:
            metadata = {"page_count": len(pdf.pages), "pdf_info": pdf.metadata or {}}
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append(ParsedPage(text=text, page_number=i))
        total_text = sum(len(p.text.strip()) for p in pages)
        if metadata.get("page_count", 0) > 0 and total_text < 50 * metadata["page_count"]:
            metadata["likely_scanned"] = True
        return ParseResult(pages=pages, metadata=metadata, file_type="pdf")
