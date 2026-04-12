from pathlib import Path
from bs4 import BeautifulSoup
from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult

class HtmlParser(BaseParser):
    supported_extensions = [".html", ".htm"]

    def parse(self, file_path: Path) -> ParseResult:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string if soup.title else None
        return ParseResult(
            pages=[ParsedPage(text=text, page_number=1)],
            metadata={"title": title} if title else {},
            file_type="html",
        )
