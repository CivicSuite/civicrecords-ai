"""Tests for IMAP email connector and attachment sanitization."""

import pytest
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from app.connectors.imap_email import (
    ImapEmailConnector,
    is_attachment_safe,
    ALLOWED_MIME_TYPES,
    BLOCKED_EXTENSIONS,
    MAX_ATTACHMENT_BYTES,
)


# ── Attachment Sanitization Tests ─────────────────────────────────────────────

def test_safe_pdf_attachment():
    safe, reason = is_attachment_safe("report.pdf", "application/pdf", 1024)
    assert safe is True
    assert reason == "OK"


def test_safe_docx_attachment():
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    safe, reason = is_attachment_safe("memo.docx", mime, 5000)
    assert safe is True


def test_safe_xlsx_attachment():
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    safe, reason = is_attachment_safe("budget.xlsx", mime, 10000)
    assert safe is True


def test_safe_plain_text():
    safe, reason = is_attachment_safe("notes.txt", "text/plain", 500)
    assert safe is True


def test_safe_csv():
    safe, reason = is_attachment_safe("data.csv", "text/csv", 2000)
    assert safe is True


def test_safe_image_jpeg():
    safe, reason = is_attachment_safe("scan.jpg", "image/jpeg", 3000000)
    assert safe is True


def test_reject_executable():
    safe, reason = is_attachment_safe("virus.exe", "application/octet-stream", 1024)
    assert safe is False
    assert "Blocked extension" in reason


def test_reject_batch_file():
    safe, reason = is_attachment_safe("script.bat", "application/x-bat", 100)
    assert safe is False
    assert "Blocked extension" in reason


def test_reject_powershell():
    safe, reason = is_attachment_safe("deploy.ps1", "text/plain", 500)
    assert safe is False
    assert "Blocked extension" in reason


def test_reject_python_script():
    safe, reason = is_attachment_safe("hack.py", "text/x-python", 200)
    assert safe is False
    assert "Blocked extension" in reason


def test_reject_zip_archive():
    safe, reason = is_attachment_safe("files.zip", "application/zip", 5000)
    assert safe is False
    assert "Blocked extension" in reason


def test_reject_unknown_mime_type():
    safe, reason = is_attachment_safe("data.xyz", "application/x-unknown", 1000)
    assert safe is False
    assert "Disallowed MIME type" in reason


def test_reject_oversized_file():
    safe, reason = is_attachment_safe(
        "huge.pdf", "application/pdf", MAX_ATTACHMENT_BYTES + 1
    )
    assert safe is False
    assert "Too large" in reason


def test_reject_no_filename():
    safe, reason = is_attachment_safe(None, "application/pdf", 1000)
    assert safe is False
    assert "No filename" in reason


def test_reject_exe_even_with_pdf_mime():
    """Extension blocklist takes priority over MIME type."""
    safe, reason = is_attachment_safe("payload.exe", "application/pdf", 1000)
    assert safe is False
    assert "Blocked extension" in reason


def test_max_attachment_boundary():
    """Exactly at the limit should pass."""
    safe, reason = is_attachment_safe("big.pdf", "application/pdf", MAX_ATTACHMENT_BYTES)
    assert safe is True


# ── Email Parsing / Extraction Tests ──────────────────────────────────────────

def _build_email_with_attachments(attachments: list[tuple[str, str, bytes]]) -> bytes:
    """Build a raw email with specified attachments.

    attachments: list of (filename, mime_type, content) tuples
    """
    msg = MIMEMultipart()
    msg["Subject"] = "Test Email"
    msg["From"] = "sender@city.gov"
    msg["To"] = "records@city.gov"
    msg.attach(MIMEText("This is the email body.", "plain"))

    for filename, mime_type, content in attachments:
        maintype, subtype = mime_type.split("/", 1)
        part = MIMEBase(maintype, subtype)
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    return msg.as_bytes()


def test_extract_safe_pdf_attachment():
    raw = _build_email_with_attachments([
        ("report.pdf", "application/pdf", b"%PDF-1.4 fake content"),
    ])
    connector = ImapEmailConnector(config={})
    attachments = connector.extract_safe_attachments(raw)
    assert len(attachments) == 1
    assert attachments[0].filename == "report.pdf"
    assert attachments[0].file_type == "pdf"


def test_extract_rejects_exe_attachment():
    raw = _build_email_with_attachments([
        ("malware.exe", "application/octet-stream", b"\x4d\x5a" + b"\x00" * 100),
    ])
    connector = ImapEmailConnector(config={})
    attachments = connector.extract_safe_attachments(raw)
    assert len(attachments) == 0


def test_extract_mixed_safe_and_unsafe():
    raw = _build_email_with_attachments([
        ("budget.pdf", "application/pdf", b"%PDF content"),
        ("virus.exe", "application/octet-stream", b"\x4d\x5a data"),
        ("memo.txt", "text/plain", b"Meeting notes from Tuesday"),
    ])
    connector = ImapEmailConnector(config={})
    attachments = connector.extract_safe_attachments(raw)
    assert len(attachments) == 2
    filenames = {a.filename for a in attachments}
    assert filenames == {"budget.pdf", "memo.txt"}


def test_extract_preserves_email_metadata():
    raw = _build_email_with_attachments([
        ("data.csv", "text/csv", b"col1,col2\n1,2"),
    ])
    connector = ImapEmailConnector(config={})
    attachments = connector.extract_safe_attachments(raw)
    assert len(attachments) == 1
    assert attachments[0].metadata["email_subject"] == "Test Email"
    assert attachments[0].metadata["email_from"] == "sender@city.gov"


def test_extract_no_attachments():
    msg = MIMEText("Just a plain email, no attachments.", "plain")
    msg["Subject"] = "Plain Email"
    msg["From"] = "sender@city.gov"
    connector = ImapEmailConnector(config={})
    attachments = connector.extract_safe_attachments(msg.as_bytes())
    assert len(attachments) == 0


# ── Connector Protocol Tests ─────────────────────────────────────────────────

def test_connector_type():
    connector = ImapEmailConnector(config={})
    assert connector.connector_type == "imap_email"


@pytest.mark.asyncio
async def test_authenticate_fails_without_config():
    connector = ImapEmailConnector(config={})
    result = await connector.authenticate()
    assert result is False


@pytest.mark.asyncio
async def test_discover_raises_without_auth():
    connector = ImapEmailConnector(config={})
    with pytest.raises(RuntimeError, match="Not authenticated"):
        await connector.discover()


@pytest.mark.asyncio
async def test_fetch_raises_without_auth():
    connector = ImapEmailConnector(config={})
    with pytest.raises(RuntimeError, match="Not authenticated"):
        await connector.fetch("imap://INBOX/1")


@pytest.mark.asyncio
async def test_health_check_unreachable():
    connector = ImapEmailConnector(config={})
    result = await connector.health_check()
    assert result.status.value == "unreachable"


# imap_email dispatch removed from tasks.py (moved to Planned connectors in T3B).
# Attachment sanitization and connector protocol tests above remain valid — the
# ImapEmailConnector class still exists and is importable; it is simply not
# registered in the active connector registry until Planned status is lifted.
