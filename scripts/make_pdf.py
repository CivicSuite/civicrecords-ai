"""Convert README.md to README-FULL.pdf using reportlab + markdown-it-py."""

import re
import sys
from pathlib import Path
from markdown_it import MarkdownIt
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Preformatted,
    Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ── paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
README = ROOT / "README.md"
OUTPUT = ROOT / "README-FULL.pdf"

# ── styles ───────────────────────────────────────────────────────────────────
BASE = getSampleStyleSheet()

CIVIC_BLUE = colors.HexColor("#1e40af")
CODE_BG    = colors.HexColor("#f1f5f9")
RULE_COLOR = colors.HexColor("#cbd5e1")

styles = {
    "h1": ParagraphStyle("H1", parent=BASE["Title"],
          fontSize=22, textColor=CIVIC_BLUE, spaceAfter=8, spaceBefore=4),
    "h2": ParagraphStyle("H2", parent=BASE["Heading2"],
          fontSize=15, textColor=CIVIC_BLUE, spaceAfter=5, spaceBefore=12,
          borderPad=0),
    "h3": ParagraphStyle("H3", parent=BASE["Heading3"],
          fontSize=12, textColor=colors.HexColor("#1e3a8a"),
          spaceAfter=4, spaceBefore=8),
    "body": ParagraphStyle("Body", parent=BASE["Normal"],
          fontSize=9.5, leading=14, spaceAfter=4),
    "bullet": ParagraphStyle("Bullet", parent=BASE["Normal"],
          fontSize=9.5, leading=14, spaceAfter=2,
          leftIndent=16, bulletIndent=4),
    "code": ParagraphStyle("Code", parent=BASE["Code"],
          fontSize=8, leading=11, fontName="Courier",
          backColor=CODE_BG, borderPad=4,
          leftIndent=12, spaceAfter=6, spaceBefore=4),
    "table_hdr": ParagraphStyle("TblHdr", parent=BASE["Normal"],
          fontSize=8.5, fontName="Helvetica-Bold", textColor=colors.white),
    "table_cell": ParagraphStyle("TblCell", parent=BASE["Normal"],
          fontSize=8.5, leading=12),
}


def escape(text: str) -> str:
    """Escape XML special chars for Paragraph."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline_fmt(text: str) -> str:
    """Convert inline backtick code and **bold** to ReportLab markup."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # Inline code  — escape first, then wrap
    def code_repl(m):
        inner = escape(m.group(1))
        return f'<font name="Courier" size="8.5" color="#0f4c81">{inner}</font>'
    text = re.sub(r"`([^`]+)`", code_repl, text)
    return text


def md_to_story(md_text: str):
    """Parse markdown tokens into a ReportLab story list."""
    md = MarkdownIt()
    tokens = md.parse(md_text)
    story = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # ── headings ─────────────────────────────────────────────────────────
        if tok.type == "heading_open":
            level = tok.tag  # h1, h2, h3
            inline = tokens[i + 1]
            text = escape(inline.content)
            text = inline_fmt(text)
            s = styles.get(level, styles["h3"])
            story.append(Paragraph(text, s))
            if level == "h2":
                story.append(HRFlowable(width="100%", thickness=0.5,
                                        color=RULE_COLOR, spaceAfter=2))
            i += 3
            continue

        # ── paragraphs ───────────────────────────────────────────────────────
        if tok.type == "paragraph_open":
            inline = tokens[i + 1]
            text = escape(inline.content)
            text = inline_fmt(text)
            story.append(Paragraph(text, styles["body"]))
            i += 3
            continue

        # ── bullet lists ─────────────────────────────────────────────────────
        if tok.type == "bullet_list_open":
            i += 1
            while i < len(tokens) and tokens[i].type != "bullet_list_close":
                t = tokens[i]
                if t.type == "inline":
                    text = escape(t.content)
                    text = inline_fmt(text)
                    story.append(Paragraph(f"• {text}", styles["bullet"]))
                i += 1
            i += 1  # skip bullet_list_close
            story.append(Spacer(1, 4))
            continue

        # ── fenced code blocks ───────────────────────────────────────────────
        if tok.type == "fence":
            code = tok.content.rstrip()
            # Preformatted handles long lines better than Paragraph for code
            story.append(Preformatted(code, styles["code"]))
            i += 1
            continue

        # ── tables ───────────────────────────────────────────────────────────
        if tok.type == "table_open":
            rows = []
            current_row = []
            in_header = False
            header_rows = 0
            i += 1
            while i < len(tokens) and tokens[i].type != "table_close":
                t = tokens[i]
                if t.type == "thead_open":
                    in_header = True
                elif t.type == "thead_close":
                    in_header = False
                    header_rows = len(rows)
                elif t.type == "tr_open":
                    current_row = []
                elif t.type == "tr_close":
                    rows.append(current_row)
                elif t.type == "inline":
                    cell_text = escape(t.content)
                    cell_text = inline_fmt(cell_text)
                    cell_style = styles["table_hdr"] if in_header else styles["table_cell"]
                    current_row.append(Paragraph(cell_text, cell_style))
                i += 1

            if rows:
                col_count = max(len(r) for r in rows)
                available = 6.5 * inch
                col_w = available / col_count

                tbl = Table(rows, colWidths=[col_w] * col_count,
                            repeatRows=header_rows)
                tbl_style = TableStyle([
                    ("BACKGROUND",  (0, 0), (-1, header_rows - 1), CIVIC_BLUE),
                    ("TEXTCOLOR",   (0, 0), (-1, header_rows - 1), colors.white),
                    ("FONTNAME",    (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
                    ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
                    ("ROWBACKGROUNDS", (0, header_rows), (-1, -1),
                     [colors.white, colors.HexColor("#f8fafc")]),
                    ("GRID",        (0, 0), (-1, -1), 0.4, RULE_COLOR),
                    ("VALIGN",      (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",  (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ])
                tbl.setStyle(tbl_style)
                story.append(tbl)
                story.append(Spacer(1, 8))
            i += 1  # skip table_close
            continue

        i += 1

    return story


def build_pdf():
    md_text = README.read_text(encoding="utf-8")

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title="CivicRecords AI — README",
        author="CivicRecords AI Project",
    )

    story = md_to_story(md_text)
    doc.build(story)
    print(f"PDF written to: {OUTPUT}")
    size_kb = OUTPUT.stat().st_size // 1024
    print(f"File size: {size_kb} KB")


if __name__ == "__main__":
    build_pdf()
