import tempfile
from pathlib import Path
import pytest
from app.ingestion.parsers import detect_parser, is_image_file
from app.ingestion.parsers.text import TextParser
from app.ingestion.parsers.csv_parser import CsvParser
from app.ingestion.parsers.html import HtmlParser

def test_text_parser():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
        f.write("Hello world\n\nThis is a test document.")
        f.flush()
        parser = TextParser()
        result = parser.parse(Path(f.name))
        assert "Hello world" in result.full_text
        assert result.total_chars > 0
        assert len(result.pages) == 1

def test_csv_parser():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
        f.write("name,age,city\nAlice,30,Denver\nBob,25,Boulder\n")
        f.flush()
        parser = CsvParser()
        result = parser.parse(Path(f.name))
        assert "Alice" in result.full_text
        assert "Denver" in result.full_text
        assert result.metadata["row_count"] == 3

def test_html_parser():
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False, encoding="utf-8") as f:
        f.write("<html><head><title>Test</title></head><body><p>Hello HTML</p><script>var x=1;</script></body></html>")
        f.flush()
        parser = HtmlParser()
        result = parser.parse(Path(f.name))
        assert "Hello HTML" in result.full_text
        assert "var x=1" not in result.full_text
        assert result.metadata.get("title") == "Test"

def test_detect_parser_txt():
    parser = detect_parser(Path("test.txt"))
    assert parser is not None
    assert isinstance(parser, TextParser)

def test_detect_parser_pdf():
    assert detect_parser(Path("report.pdf")) is not None

def test_detect_parser_unknown():
    assert detect_parser(Path("file.xyz123")) is None

def test_is_image_file():
    assert is_image_file(Path("scan.jpg")) is True
    assert is_image_file(Path("photo.png")) is True
    assert is_image_file(Path("doc.pdf")) is False
    assert is_image_file(Path("file.txt")) is False
