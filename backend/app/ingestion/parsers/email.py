import email
from email import policy
from pathlib import Path
from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult

class EmailParser(BaseParser):
    supported_extensions = [".eml"]

    def parse(self, file_path: Path) -> ParseResult:
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
        parts = []
        headers = f"From: {msg.get('from', '')}\nTo: {msg.get('to', '')}\nDate: {msg.get('date', '')}\nSubject: {msg.get('subject', '')}\n"
        parts.append(headers)
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_content()
                    if isinstance(body, str):
                        parts.append(body)
        else:
            body = msg.get_content()
            if isinstance(body, str):
                parts.append(body)
        text = "\n\n".join(parts)
        metadata = {"from": msg.get("from", ""), "to": msg.get("to", ""), "subject": msg.get("subject", ""), "date": msg.get("date", "")}
        return ParseResult(pages=[ParsedPage(text=text, page_number=1)], metadata=metadata, file_type="eml")
