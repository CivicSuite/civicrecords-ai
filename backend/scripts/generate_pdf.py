"""
generate_pdf.py — CivicRecords AI Technical Documentation PDF Generator
Generates README-FULL.pdf in the project root using ReportLab Platypus.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable

# ── Output path ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "README-FULL.pdf")

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#1a2a4a")
BLUE   = colors.HexColor("#2563eb")
LTBLUE = colors.HexColor("#dbeafe")
TEAL   = colors.HexColor("#0d9488")
GRAY   = colors.HexColor("#6b7280")
LTGRAY = colors.HexColor("#f3f4f6")
WHITE  = colors.white
BLACK  = colors.black

# ── Style sheet ───────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def make_styles():
    s = getSampleStyleSheet()

    s.add(ParagraphStyle("DocTitle",
        fontName="Helvetica-Bold", fontSize=28, leading=36,
        textColor=WHITE, alignment=TA_CENTER, spaceAfter=12))

    s.add(ParagraphStyle("DocSubtitle",
        fontName="Helvetica", fontSize=14, leading=20,
        textColor=LTBLUE, alignment=TA_CENTER, spaceAfter=8))

    s.add(ParagraphStyle("DocVersion",
        fontName="Helvetica-Oblique", fontSize=11, leading=16,
        textColor=LTBLUE, alignment=TA_CENTER, spaceAfter=4))

    s.add(ParagraphStyle("H1",
        fontName="Helvetica-Bold", fontSize=18, leading=24,
        textColor=NAVY, spaceBefore=18, spaceAfter=8,
        borderPad=4))

    s.add(ParagraphStyle("H2",
        fontName="Helvetica-Bold", fontSize=13, leading=18,
        textColor=BLUE, spaceBefore=14, spaceAfter=6))

    s.add(ParagraphStyle("H3",
        fontName="Helvetica-Bold", fontSize=11, leading=15,
        textColor=NAVY, spaceBefore=10, spaceAfter=4))

    s.add(ParagraphStyle("Body",
        fontName="Helvetica", fontSize=10, leading=15,
        textColor=BLACK, spaceAfter=6, alignment=TA_JUSTIFY))

    s.add(ParagraphStyle("BulletItem",
        fontName="Helvetica", fontSize=10, leading=14,
        textColor=BLACK, leftIndent=18, spaceAfter=3,
        bulletIndent=6, bulletFontName="Helvetica"))

    s.add(ParagraphStyle("CodeBlock",
        fontName="Courier", fontSize=8.5, leading=13,
        textColor=colors.HexColor("#1e293b"),
        backColor=LTGRAY, leftIndent=12, rightIndent=12,
        spaceAfter=6, spaceBefore=4,
        borderWidth=1, borderColor=colors.HexColor("#cbd5e1"),
        borderPad=6, borderRadius=3))

    s.add(ParagraphStyle("TocEntry",
        fontName="Helvetica", fontSize=10, leading=16,
        textColor=NAVY, leftIndent=0, spaceAfter=2))

    s.add(ParagraphStyle("TocEntry2",
        fontName="Helvetica", fontSize=9.5, leading=14,
        textColor=GRAY, leftIndent=18, spaceAfter=1))

    s.add(ParagraphStyle("Caption",
        fontName="Helvetica-Oblique", fontSize=8.5, leading=12,
        textColor=GRAY, alignment=TA_CENTER, spaceAfter=8))

    s.add(ParagraphStyle("TableHeader",
        fontName="Helvetica-Bold", fontSize=9, leading=12,
        textColor=WHITE))

    s.add(ParagraphStyle("TableCell",
        fontName="Helvetica", fontSize=9, leading=12,
        textColor=BLACK))

    s.add(ParagraphStyle("Footer",
        fontName="Helvetica", fontSize=8, leading=10,
        textColor=GRAY, alignment=TA_CENTER))

    return s


# ── Flowable helpers ─────────────────────────────────────────────────────────

class ColorBand(Flowable):
    """A full-width horizontal band used for section headers on the title page."""
    def __init__(self, width, height, color):
        super().__init__()
        self.band_width = width
        self.band_height = height
        self.color = color

    def wrap(self, availW, availH):
        return self.band_width, self.band_height

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(0, 0, self.band_width, self.band_height, fill=1, stroke=0)


class ArchDiagram(Flowable):
    """Simple block-and-arrow architecture diagram drawn with ReportLab primitives."""

    def __init__(self, width=480, height=260):
        super().__init__()
        self.diagram_width = width
        self.diagram_height = height

    def wrap(self, availW, availH):
        return self.diagram_width, self.diagram_height

    def _box(self, c, x, y, w, h, label, sublabel=None,
             fill=BLUE, text_color=WHITE, font_size=9):
        c.setFillColor(fill)
        c.setStrokeColor(NAVY)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", font_size)
        c.drawCentredString(x + w / 2, y + h / 2 + (5 if sublabel else 3), label)
        if sublabel:
            c.setFont("Helvetica", font_size - 1.5)
            c.setFillColor(LTBLUE if fill == BLUE else GRAY)
            c.drawCentredString(x + w / 2, y + h / 2 - 7, sublabel)

    def _arrow_h(self, c, x1, y, x2):
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.5)
        c.line(x1, y, x2 - 6, y)
        c.setFillColor(NAVY)
        p = c.beginPath()
        p.moveTo(x2, y)
        p.lineTo(x2 - 8, y + 4)
        p.lineTo(x2 - 8, y - 4)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    def _arrow_v(self, c, x, y1, y2):
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.5)
        c.line(x, y1, x, y2 + 6)
        c.setFillColor(NAVY)
        p = c.beginPath()
        p.moveTo(x, y2)
        p.lineTo(x - 4, y2 + 8)
        p.lineTo(x + 4, y2 + 8)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    def draw(self):
        c = self.canv
        W, H = self.diagram_width, self.diagram_height

        # Layer labels
        c.setFillColor(LTGRAY)
        c.setStrokeColor(colors.HexColor("#cbd5e1"))
        c.setLineWidth(0.5)
        c.rect(5, H - 50, W - 10, 42, fill=1, stroke=1)    # Client
        c.rect(5, H - 105, W - 10, 42, fill=1, stroke=1)   # Gateway
        c.rect(5, H - 200, W - 10, 82, fill=1, stroke=1)   # Services
        c.rect(5, 8, W - 10, 42, fill=1, stroke=1)         # Worker

        c.setFillColor(GRAY)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(12, H - 14, "CLIENT")
        c.drawString(12, H - 69, "GATEWAY")
        c.drawString(12, H - 124, "BACKEND SERVICES")
        c.drawString(12, 44, "ASYNC WORKERS")

        bw, bh = 90, 30

        # Row 1 — Browser
        bx = W / 2 - bw / 2
        self._box(c, bx, H - 45, bw, bh, "Browser", "(React UI)",
                  fill=TEAL, text_color=WHITE)

        # Arrow Browser → nginx
        self._arrow_v(c, W / 2, H - 45, H - 98)

        # Row 2 — nginx
        self._box(c, bx, H - 98, bw, bh, "nginx", "port 8080",
                  fill=NAVY, text_color=WHITE)

        # Arrow nginx → FastAPI
        self._arrow_v(c, W / 2, H - 98, H - 152)

        # Row 3 — FastAPI (centre)
        api_x = W / 2 - bw / 2
        self._box(c, api_x, H - 195, bw + 10, bh, "FastAPI API", "port 8000",
                  fill=BLUE, text_color=WHITE)

        # Horizontal connectors from FastAPI to side services

        # Left services: PostgreSQL, pgvector
        pg_x = 30
        self._box(c, pg_x, H - 195, 82, bh, "PostgreSQL 17", "+ pgvector",
                  fill=colors.HexColor("#7c3aed"), text_color=WHITE)
        self._arrow_h(c, pg_x + 82, H - 195 + bh / 2, api_x - 2)

        # Right services: Redis, Ollama
        redis_x = W - 30 - 82
        self._box(c, redis_x, H - 160, 82, bh, "Redis 7.2", "(queue/cache)",
                  fill=colors.HexColor("#dc2626"), text_color=WHITE)
        self._arrow_h(c, api_x + bw + 10 + 2, H - 160 + bh / 2, redis_x)

        ollama_x = W - 30 - 82
        self._box(c, ollama_x, H - 198, 82, bh, "Ollama", "(LLM runtime)",
                  fill=colors.HexColor("#059669"), text_color=WHITE)
        self._arrow_h(c, api_x + bw + 10 + 2, H - 195 + bh / 2, ollama_x)

        # Arrow Redis → Celery Worker
        self._arrow_v(c, redis_x + 41, H - 160, 50)

        # Worker row
        worker_x = redis_x - 10
        self._box(c, worker_x, 12, 100, bh, "Celery Worker", "(ingestion/AI)",
                  fill=colors.HexColor("#b45309"), text_color=WHITE)
        self._box(c, worker_x - 115, 12, 100, bh, "Celery Beat", "(scheduler)",
                  fill=colors.HexColor("#92400e"), text_color=WHITE)


class DataFlowDiagram(Flowable):
    """Linear data-flow diagram: Files → Parsers → Chunker → Embedder → pgvector → Search → Results"""

    def __init__(self, width=480, height=90):
        super().__init__()
        self.diagram_width = width
        self.diagram_height = height

    def wrap(self, availW, availH):
        return self.diagram_width, self.diagram_height

    def draw(self):
        c = self.canv
        W, H = self.diagram_width, self.diagram_height

        stages = [
            ("Files", "PDF/DOCX\nCSV/Email"),
            ("Parsers", "7 format\nhandlers"),
            ("Chunker", "512-token\noverlap"),
            ("Embedder", "nomic-\nembed-text"),
            ("pgvector", "HNSW\nindex"),
            ("Search", "hybrid\nBM25+cos"),
            ("Results", "cited\nanswers"),
        ]

        box_colors = [
            colors.HexColor("#64748b"),
            colors.HexColor("#2563eb"),
            colors.HexColor("#7c3aed"),
            colors.HexColor("#0d9488"),
            colors.HexColor("#7c3aed"),
            colors.HexColor("#2563eb"),
            colors.HexColor("#059669"),
        ]

        n = len(stages)
        total_arrows = n - 1
        bw = 52
        bh = 52
        gap = 8
        total = n * bw + total_arrows * (gap + 12)
        start_x = (W - total) / 2
        y_box = (H - bh) / 2

        x = start_x
        for i, (label, sub) in enumerate(stages):
            # Draw box
            c.setFillColor(box_colors[i])
            c.setStrokeColor(NAVY)
            c.setLineWidth(0.8)
            c.roundRect(x, y_box, bw, bh, 5, fill=1, stroke=1)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawCentredString(x + bw / 2, y_box + bh - 13, label)
            c.setFont("Helvetica", 6.5)
            lines = sub.split("\n")
            for j, line in enumerate(lines):
                c.drawCentredString(x + bw / 2, y_box + bh - 23 - j * 9, line)

            x += bw
            if i < n - 1:
                # Arrow
                ax1, ax2 = x + 2, x + gap + 10
                ay = y_box + bh / 2
                c.setStrokeColor(NAVY)
                c.setLineWidth(1.2)
                c.line(ax1, ay, ax2 - 5, ay)
                c.setFillColor(NAVY)
                p = c.beginPath()
                p.moveTo(ax2, ay)
                p.lineTo(ax2 - 7, ay + 3.5)
                p.lineTo(ax2 - 7, ay - 3.5)
                p.close()
                c.drawPath(p, fill=1, stroke=0)
                x += gap + 12


# ── Table helpers ─────────────────────────────────────────────────────────────

def make_table(data, col_widths, header_bg=NAVY, alt_bg=LTGRAY):
    """Build a styled Platypus Table from a list of lists."""
    style = TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("TOPPADDING",    (0, 0), (-1, 0), 7),
        # Body rows
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 1), (-1, -1), 9),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, alt_bg]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(style)
    return t


# ── Page template ─────────────────────────────────────────────────────────────

def on_page(canvas, doc):
    """Footer on every page except the title page."""
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFillColor(GRAY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(inch, 0.5 * inch,
        "CivicRecords AI — Technical Documentation v1.0.0")
    canvas.drawRightString(doc.pagesize[0] - inch, 0.5 * inch,
        f"Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.setLineWidth(0.5)
    canvas.line(inch, 0.65 * inch, doc.pagesize[0] - inch, 0.65 * inch)
    canvas.restoreState()


# ── Content builders ──────────────────────────────────────────────────────────

def build_title_page(s, W):
    story = []
    # Navy banner background simulation using a color band
    story.append(Spacer(1, 0.3 * inch))
    story.append(ColorBand(W - 2 * inch, 0.04 * inch, BLUE))
    story.append(Spacer(1, 0.25 * inch))

    # Project badge row
    badge_data = [["Open Source", "Apache 2.0", "v1.0.0", "Python 3.12"]]
    badge_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLUE),
        ("TEXTCOLOR",     (0, 0), (-1, -1), WHITE),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("ROUNDEDCORNERS", [4]),
        ("GRID",          (0, 0), (-1, -1), 1, NAVY),
    ])
    badge_t = Table(badge_data, colWidths=[1.3 * inch] * 4)
    badge_t.setStyle(badge_style)

    # Centre the badge table
    wrapper = Table([[badge_t]], colWidths=[W - 2 * inch])
    wrapper.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(wrapper)
    story.append(Spacer(1, 0.35 * inch))

    # Title block on navy background
    title_data = [[
        Paragraph("CivicRecords AI", s["DocTitle"]),
    ], [
        Paragraph("Technical Documentation", s["DocSubtitle"]),
    ], [
        Paragraph("Version 1.0.0  ·  April 2026", s["DocVersion"]),
    ]]
    title_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 24),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 24),
        ("ROUNDEDCORNERS", [6]),
    ])
    title_t = Table(title_data, colWidths=[W - 2 * inch])
    title_t.setStyle(title_style)
    story.append(title_t)

    story.append(Spacer(1, 0.4 * inch))

    # Tagline
    story.append(Paragraph(
        "Open-source, locally-hosted AI that helps American cities respond to open records requests.",
        ParagraphStyle("Tagline", parent=s["Body"], fontSize=12, leading=18,
                       alignment=TA_CENTER, textColor=NAVY)))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        "Runs entirely on city hardware — no cloud, no vendor lock-in, no resident data leaving the building.",
        ParagraphStyle("Tagline2", parent=s["Body"], fontSize=10.5, leading=16,
                       alignment=TA_CENTER, textColor=GRAY)))

    story.append(Spacer(1, 0.5 * inch))
    story.append(ColorBand(W - 2 * inch, 0.04 * inch, BLUE))
    story.append(Spacer(1, 0.3 * inch))

    # Key stats row
    stats = [
        ["7", "Docker\nServices"],
        ["10", "DB\nTables"],
        ["5", "Completed\nSub-projects"],
        ["80+", "Automated\nTests"],
        ["7", "Document\nParsers"],
        ["$0", "Software\nLicensing"],
    ]
    stats_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), TEAL),
        ("BACKGROUND",    (0, 1), (-1, 1), LTBLUE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("TEXTCOLOR",     (0, 1), (-1, 1), NAVY),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, 0), 20),
        ("FONTSIZE",      (0, 1), (-1, 1), 8),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING",    (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.5, WHITE),
    ])
    col_w = (W - 2 * inch) / 6
    stats_t = Table(
        [[s[0] for s in stats], [s[1] for s in stats]],
        colWidths=[col_w] * 6
    )
    stats_t.setStyle(stats_style)
    story.append(stats_t)

    story.append(PageBreak())
    return story


def build_toc(s):
    story = []
    story.append(Paragraph("Table of Contents", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=10))

    toc = [
        ("1.", "Product Overview", None),
        ("", "Market gap, target users, value proposition", True),
        ("2.", "Architecture Overview", None),
        ("", "Seven Docker services, component roles", True),
        ("3.", "Architecture Diagram", None),
        ("", "Service topology with data flow arrows", True),
        ("4.", "Data Flow Diagram", None),
        ("", "Files → Parsers → Chunker → Embedder → pgvector → Results", True),
        ("5.", "Technology Stack", None),
        ("", "All components with versions, licenses, purpose", True),
        ("6.", "Database Schema", None),
        ("", "10 tables with key columns", True),
        ("7.", "API Endpoints", None),
        ("", "All endpoint groups and routes", True),
        ("8.", "Security & Compliance", None),
        ("", "Human-in-the-loop, audit logging, data sovereignty", True),
        ("9.", "Deployment", None),
        ("", "Docker Compose, install script, platforms", True),
    ]

    for num, title, is_sub in toc:
        if is_sub:
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{title}", s["TocEntry2"]))
        else:
            story.append(Paragraph(f"<b>{num}</b>&nbsp;&nbsp;{title}", s["TocEntry"]))

    story.append(PageBreak())
    return story


def build_overview(s):
    story = []
    story.append(Paragraph("1. Product Overview", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))

    story.append(Paragraph("What It Is", s["H2"]))
    story.append(Paragraph(
        "CivicRecords AI is a fully open-source, locally-hosted AI system that helps municipal staff "
        "respond to open records requests (FOIA, CORA, and state equivalents). It runs entirely on "
        "commodity hardware — a single Ryzen-based desktop with 32–64 GB RAM — inside a city's existing "
        "network perimeter. No cloud subscriptions, no vendor lock-in, no resident data leaving the building.",
        s["Body"]))

    story.append(Paragraph("The Market Gap", s["H2"]))
    story.append(Paragraph(
        "Every city in America is legally required to respond to open records requests. Staff manually "
        "search file shares, email archives, and databases, then review every document for exemptions "
        "before release. Request volumes are rising 20–50% year-over-year at many municipalities. "
        "No open-source tool exists for the <b>responder side</b> of open records at the municipal level.",
        s["Body"]))

    pain_points = [
        ("Volume is rising.", "20–50% YoY growth in request volume. Few cities have dedicated records officers below county level."),
        ("Records are scattered.", "Responsive documents may live in email archives, shared drives, paper cabinets, proprietary databases, body camera footage, council minutes, and financial systems."),
        ("Mistakes are expensive.", "Incomplete search, missed exemptions, or blown deadlines trigger litigation, sanctions, or public embarrassment."),
        ("Commercial AI is a non-starter.", "Cloud AI tools raise data sovereignty concerns, carry recurring SaaS costs, and conflict with public stewardship obligations."),
    ]
    for bold, text in pain_points:
        story.append(Paragraph(f"• <b>{bold}</b> {text}", s["BulletItem"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Target Users", s["H2"]))
    user_data = [
        ["Role", "Description", "Primary Interface"],
        ["Municipal Records Staff", "City clerks, paralegals, records officers who receive and process requests", "Search + Request Tracker"],
        ["Department Heads / City Attorneys", "Supervisors who review responses before release", "Review/Approval Workflow"],
        ["City IT Staff", "Install, configure, and maintain the system", "Admin Panel"],
        ["Future: Public", "Requester portal planned for v2 roadmap", "N/A (out of scope v0.1)"],
    ]
    story.append(make_table(user_data, [1.6*inch, 3.2*inch, 1.9*inch]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Key Capabilities", s["H2"]))
    caps = [
        ("AI-Powered Search", "Natural language hybrid search (semantic + BM25 keyword) across all ingested city documents with source attribution and confidence scores."),
        ("Document Ingestion", "Automatic parsing of PDF, DOCX, XLSX, CSV, email, HTML, and text files. Scanned documents processed via multimodal AI (Gemma 4) with Tesseract OCR fallback."),
        ("Exemption Detection", "Rules-based PII detection (SSN, phone, email, credit card) plus per-state statutory keyword matching. Optional LLM secondary review. All flags require human confirmation."),
        ("Request Management", "Full lifecycle tracking: intake → search → document attachment → review → approval → response. Deadline alerts for approaching and overdue requests."),
        ("Compliance by Design", "Hash-chained audit logs, human-in-the-loop enforcement, AI content labeling, data sovereignty verification. Designed for Colorado CAIA and 50-state regulatory compliance."),
        ("Federation-Ready", "REST API with service accounts enables future cross-jurisdiction record discovery between CivicRecords AI instances."),
    ]
    cap_data = [["Capability", "Description"]] + [[b, t] for b, t in caps]
    story.append(make_table(cap_data, [1.8*inch, 4.9*inch]))

    story.append(PageBreak())
    return story


def build_architecture(s):
    story = []
    story.append(Paragraph("2. Architecture Overview", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))

    story.append(Paragraph(
        "CivicRecords AI is deployed as a Docker Compose stack of seven services. All services run "
        "in Linux containers on the host machine — no cloud infrastructure required. The services "
        "communicate over an internal Docker bridge network; only nginx is exposed to the city LAN.",
        s["Body"]))

    story.append(Paragraph("The Seven Docker Services", s["H2"]))

    svc_data = [
        ["#", "Service", "Image", "Port", "Role"],
        ["1", "postgres", "postgres:17-pgvector", "5432 (internal)", "Primary relational database + vector similarity search via pgvector extension"],
        ["2", "redis", "redis:7.2-alpine", "6379 (internal)", "Celery task broker, result backend, and API response cache"],
        ["3", "ollama", "ollama/ollama:latest", "11434 (internal)", "Local LLM and embedding model runtime — serves nomic-embed-text and Gemma 4"],
        ["4", "api", "civicrecords/backend", "8000 (internal)", "FastAPI application server — all business logic, authentication, REST endpoints"],
        ["5", "worker", "civicrecords/backend", "— (no port)", "Celery worker — handles document ingestion, embedding, and async AI tasks"],
        ["6", "beat", "civicrecords/backend", "— (no port)", "Celery beat scheduler — periodic tasks: source re-ingestion, deadline checks"],
        ["7", "frontend", "civicrecords/frontend", "8080 (LAN)", "nginx serving React SPA + reverse proxy to API at /api/*"],
    ]
    story.append(make_table(svc_data, [0.25*inch, 0.85*inch, 1.7*inch, 1.3*inch, 2.6*inch]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Data Flow Summary", s["H2"]))
    story.append(Paragraph(
        "Staff browsers connect to nginx on port 8080. nginx serves the React frontend and proxies "
        "API calls to FastAPI. The API handles authentication (JWT), request validation, and business "
        "logic. Async tasks (ingestion, embedding, LLM analysis) are queued in Redis and consumed by "
        "Celery workers. All persistent data lives in PostgreSQL; vector embeddings are stored in "
        "pgvector within the same Postgres instance.", s["Body"]))

    story.append(Paragraph("Hardware Requirements", s["H2"]))
    hw_data = [
        ["Component", "Minimum", "Recommended"],
        ["CPU", "AMD Ryzen 7 (8-core)", "AMD Ryzen 9 (12–16 core)"],
        ["RAM", "32 GB DDR4/DDR5", "64 GB DDR5"],
        ["Storage", "1 TB NVMe SSD", "2 TB NVMe SSD"],
        ["GPU", "Integrated (CPU inference)", "Discrete GPU with 8+ GB VRAM"],
        ["Network", "Gigabit Ethernet", "Gigabit Ethernet"],
        ["OS", "Ubuntu 22.04+ / Windows 10/11 / macOS 13+", "Ubuntu 24.04 LTS"],
        ["Estimated Cost", "~$800", "~$1,200"],
    ]
    story.append(make_table(hw_data, [1.5*inch, 2.5*inch, 2.7*inch]))

    story.append(PageBreak())
    return story


def build_arch_diagram(s, W):
    story = []
    story.append(Paragraph("3. Architecture Diagram", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))
    story.append(Paragraph(
        "The diagram below shows the service topology and primary communication paths within the "
        "Docker Compose stack. Arrows indicate request/response direction. Colour coding: "
        "<font color='#7c3aed'>purple</font> = data stores, "
        "<font color='#dc2626'>red</font> = message broker, "
        "<font color='#059669'>green</font> = LLM runtime, "
        "<font color='#b45309'>amber</font> = async workers.",
        s["Body"]))
    story.append(Spacer(1, 12))

    # Centre the diagram
    diag = ArchDiagram(width=W - 2 * inch, height=270)
    wrapper = Table([[diag]], colWidths=[W - 2 * inch])
    wrapper.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), LTGRAY),
        ("BOX",    (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(wrapper)
    story.append(Paragraph(
        "Figure 1 — CivicRecords AI Docker service topology", s["Caption"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Network Isolation", s["H2"]))
    story.append(Paragraph(
        "All inter-service communication occurs over an internal Docker bridge network "
        "(<b>civicrecords_net</b>). Only the frontend service (nginx, port 8080) is bound "
        "to the host network interface. PostgreSQL, Redis, Ollama, and the API are not "
        "reachable from outside the Docker network. The system binds to localhost or a "
        "city-designated internal IP — never exposed to the public internet.", s["Body"]))

    story.append(PageBreak())
    return story


def build_dataflow_diagram(s, W):
    story = []
    story.append(Paragraph("4. Data Flow Diagram", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))
    story.append(Paragraph(
        "Documents enter the system through configured data sources and flow through a "
        "multi-stage pipeline before becoming searchable. The same pipeline handles initial "
        "ingestion and scheduled re-ingestion when source documents change.",
        s["Body"]))
    story.append(Spacer(1, 14))

    dfd = DataFlowDiagram(width=W - 2 * inch, height=90)
    wrapper = Table([[dfd]], colWidths=[W - 2 * inch])
    wrapper.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), LTGRAY),
        ("BOX",    (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(wrapper)
    story.append(Paragraph("Figure 2 — Document ingestion and search data flow", s["Caption"]))

    story.append(Paragraph("Pipeline Stage Detail", s["H2"]))
    stage_data = [
        ["Stage", "Component", "Description"],
        ["Files", "Data Sources", "PDF, DOCX, XLSX, CSV, EML/MBOX, HTML, TXT from configured directory or live connector"],
        ["Parsers", "7 Parser Classes", "Format-specific extractors: PDFParser, DocxParser, SpreadsheetParser, TextParser, EmailParser, HTMLParser, ImageParser (OCR)"],
        ["Chunker", "RecursiveChunker", "Splits extracted text into 512-token chunks with 64-token overlap; preserves sentence boundaries"],
        ["Embedder", "OllamaEmbedder", "Calls nomic-embed-text via Ollama REST API; returns 768-dim float32 vectors"],
        ["pgvector", "PostgreSQL + pgvector", "Stores vectors in document_chunks.embedding (vector(768)); HNSW index for sub-second ANN search"],
        ["Search Engine", "HybridSearchEngine", "Combines cosine similarity (pgvector) with BM25 keyword scoring; RRF fusion for final ranking"],
        ["Results", "LLM Synthesis", "Top-k chunks sent to Gemma 4 via Ollama; response includes source citations and confidence scores"],
    ]
    story.append(make_table(stage_data, [0.9*inch, 1.5*inch, 4.3*inch]))

    story.append(PageBreak())
    return story


def build_tech_stack(s):
    story = []
    story.append(Paragraph("5. Technology Stack", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))
    story.append(Paragraph(
        "All components are open source with permissive or weak-copyleft licenses. "
        "No AGPL, SSPL, or proprietary components. Cities may modify and deploy without "
        "open-sourcing local modifications.", s["Body"]))

    stack_data = [
        ["Layer", "Technology", "Version", "License", "Purpose"],
        ["Runtime", "Python", "3.12", "PSF", "Primary backend language"],
        ["API Framework", "FastAPI", "0.115", "MIT", "Async REST API server"],
        ["ORM", "SQLAlchemy", "2.0", "MIT", "Database access layer"],
        ["Migrations", "Alembic", "1.13", "MIT", "Schema version control"],
        ["Task Queue", "Celery", "5.3", "BSD-3", "Async background workers"],
        ["Message Broker", "Redis", "7.2", "BSD (< 8.0)", "Queue and cache"],
        ["Database", "PostgreSQL", "17", "PostgreSQL", "Primary relational store"],
        ["Vector Search", "pgvector", "0.8", "MIT", "Embedding similarity search"],
        ["LLM Runtime", "Ollama", "latest", "MIT", "Local model serving"],
        ["Default LLM", "Gemma 4", "e4b default (e2b/26b/31b also supported)", "Apache 2.0", "Document analysis, synthesis"],
        ["Embeddings", "nomic-embed-text", "v1.5", "Apache 2.0", "Text vectorization (768-dim)"],
        ["OCR", "Tesseract", "5.x", "Apache 2.0", "Scanned document text extraction"],
        ["PDF Parsing", "pdfplumber", "0.11", "MIT", "PDF text + structure extraction"],
        ["DOCX Parsing", "python-docx", "1.1", "MIT", "Word document extraction"],
        ["Auth", "PyJWT + bcrypt", "2.x / 4.x", "MIT", "JWT tokens, password hashing"],
        ["Frontend", "React", "18", "MIT", "Staff-facing SPA"],
        ["UI Components", "shadcn/ui + Tailwind CSS", "latest", "MIT", "Component library"],
        ["Build Tool", "Vite", "5.x", "MIT", "Frontend bundler"],
        ["Containerisation", "Docker + Compose", "26 / 2.x", "Apache 2.0", "Deployment isolation"],
        ["Web Server", "nginx", "1.25-alpine", "BSD-2", "Reverse proxy + static files"],
        ["Testing", "pytest + pytest-asyncio", "8.x", "MIT", "Backend test framework"],
    ]
    story.append(make_table(stack_data,
        [0.9*inch, 1.5*inch, 0.65*inch, 0.9*inch, 2.8*inch]))

    story.append(PageBreak())
    return story


def build_db_schema(s):
    story = []
    story.append(Paragraph("6. Database Schema", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))
    story.append(Paragraph(
        "CivicRecords AI uses a single PostgreSQL 17 database with the pgvector extension. "
        "All tables are managed by Alembic migrations. The schema supports the full request "
        "lifecycle, audit logging, and vector-based document retrieval.",
        s["Body"]))

    tables = [
        ("users", "Authentication and role management",
         "id (UUID PK), email, hashed_password, full_name, role (admin/staff/reviewer/readonly), "
         "is_active, created_at, updated_at"),

        ("sessions", "Active JWT session tokens",
         "id (UUID PK), user_id (FK→users), token_hash, created_at, expires_at, revoked"),

        ("audit_logs", "Hash-chained tamper-evident audit trail",
         "id (UUID PK), user_id (FK→users), action, resource_type, resource_id, "
         "details (JSONB), ip_address, prev_hash, hash, created_at"),

        ("data_sources", "Configured ingestion sources",
         "id (UUID PK), name, source_type (directory/api/database), connection_config (JSONB encrypted), "
         "schedule_cron, last_ingested_at, is_active, created_by (FK→users), created_at"),

        ("documents", "Ingested document metadata",
         "id (UUID PK), source_id (FK→data_sources), file_path, file_hash (SHA-256), "
         "mime_type, title, author, created_date, ingested_at, chunk_count, status"),

        ("document_chunks", "Text chunks with vector embeddings",
         "id (UUID PK), document_id (FK→documents), chunk_index, content (TEXT), "
         "embedding (vector(768)), token_count, page_number, section_heading, created_at"),

        ("requests", "Open records request lifecycle",
         "id (UUID PK), reference_number, requester_name, requester_email, "
         "description, statutory_deadline, status (received/searching/reviewing/responded/closed), "
         "assigned_to (FK→users), created_at, updated_at"),

        ("request_documents", "Responsive documents attached to requests",
         "id (UUID PK), request_id (FK→requests), document_id (FK→documents), "
         "chunk_ids (UUID[]), relevance_score, added_by (FK→users), added_at, notes"),

        ("exemption_rules", "Configurable exemption detection rules",
         "id (UUID PK), name, rule_type (regex/keyword/llm), pattern, state_code, "
         "exemption_category, description, is_active, created_by (FK→users), created_at"),

        ("exemption_flags", "Detected exemption instances requiring review",
         "id (UUID PK), request_id (FK→requests), document_id (FK→documents), chunk_id (FK→document_chunks), "
         "rule_id (FK→exemption_rules), flagged_text, confidence_score, status (pending/confirmed/dismissed), "
         "reviewed_by (FK→users), reviewed_at, ai_generated"),
    ]

    for tname, tdesc, tcols in tables:
        story.append(KeepTogether([
            Paragraph(f"<b>{tname}</b>", s["H3"]),
            Paragraph(tdesc, ParagraphStyle("SchemaDesc", parent=s["Body"],
                                             fontSize=9, textColor=GRAY, spaceAfter=2)),
            Paragraph(f"<i>Columns:</i> {tcols}",
                      ParagraphStyle("SchemaCols", parent=s["Body"],
                                     fontSize=8.5, fontName="Courier",
                                     backColor=LTGRAY, borderWidth=0.5,
                                     borderColor=colors.HexColor("#cbd5e1"),
                                     borderPad=5, spaceAfter=6)),
        ]))

    story.append(PageBreak())
    return story


def build_api_endpoints(s):
    story = []
    story.append(Paragraph("7. API Endpoints", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))
    story.append(Paragraph(
        "The FastAPI backend exposes a versioned REST API at <b>/api/v1/</b>. "
        "All endpoints except <b>/auth/login</b> and <b>/health</b> require a valid JWT "
        "bearer token. OpenAPI documentation is available at <b>http://localhost:8000/docs</b>.",
        s["Body"]))

    groups = [
        ("Authentication", "/api/v1/auth", [
            ("POST", "/login", "Authenticate user, return JWT access token", "Public"),
            ("POST", "/logout", "Revoke current session token", "Any role"),
            ("POST", "/refresh", "Refresh access token using refresh token", "Any role"),
            ("GET",  "/me", "Return current authenticated user profile", "Any role"),
        ]),
        ("User Management", "/api/v1/users", [
            ("GET",    "/",         "List all users (paginated)", "Admin"),
            ("POST",   "/",         "Create new user account", "Admin"),
            ("GET",    "/{id}",     "Get user by ID", "Admin"),
            ("PUT",    "/{id}",     "Update user details or role", "Admin"),
            ("DELETE", "/{id}",     "Deactivate user account", "Admin"),
        ]),
        ("Search", "/api/v1/search", [
            ("POST", "/",           "Execute hybrid semantic+keyword search", "Staff+"),
            ("GET",  "/history",    "Return recent searches for current user", "Staff+"),
        ]),
        ("Documents & Sources", "/api/v1/documents, /api/v1/sources", [
            ("GET",  "/sources",           "List configured data sources", "Admin"),
            ("POST", "/sources",           "Add new data source", "Admin"),
            ("POST", "/sources/{id}/ingest", "Trigger manual re-ingestion", "Admin"),
            ("GET",  "/documents",         "List ingested documents (paginated)", "Staff+"),
            ("GET",  "/documents/{id}",    "Get document metadata and chunk list", "Staff+"),
        ]),
        ("Requests", "/api/v1/requests", [
            ("GET",    "/",             "List open records requests (paginated, filterable)", "Staff+"),
            ("POST",   "/",             "Create new open records request", "Staff+"),
            ("GET",    "/{id}",         "Get request detail with attached documents", "Staff+"),
            ("PUT",    "/{id}",         "Update request status, assignment, or notes", "Staff+"),
            ("POST",   "/{id}/documents", "Attach responsive document to request", "Staff+"),
            ("POST",   "/{id}/approve",  "Approve response draft (advance to responded)", "Reviewer+"),
        ]),
        ("Exemptions", "/api/v1/exemptions", [
            ("GET",  "/rules",          "List exemption detection rules", "Admin"),
            ("POST", "/rules",          "Create new exemption rule", "Admin"),
            ("POST", "/scan",           "Scan document chunk for exemptions", "Staff+"),
            ("GET",  "/flags",          "List exemption flags for a request", "Staff+"),
            ("PUT",  "/flags/{id}",     "Confirm or dismiss an exemption flag", "Reviewer+"),
        ]),
        ("Audit", "/api/v1/audit", [
            ("GET",  "/",               "Query audit log (date range, user, action filters)", "Admin"),
            ("GET",  "/{id}",           "Get single audit log entry with hash verification", "Admin"),
        ]),
        ("Admin & Health", "/api/v1/admin, /health", [
            ("GET",  "/health",         "System health check (all services)", "Public"),
            ("GET",  "/admin/stats",    "Dashboard statistics (requests, documents, flags)", "Admin"),
            ("GET",  "/admin/service-accounts", "List API service accounts", "Admin"),
            ("POST", "/admin/service-accounts", "Create service account for federation", "Admin"),
        ]),
    ]

    for group_name, prefix, endpoints in groups:
        story.append(Paragraph(f"{group_name} — <font color='#2563eb'>{prefix}</font>", s["H2"]))
        ep_data = [["Method", "Path", "Description", "Auth"]]
        for method, path, desc, auth in endpoints:
            method_colors = {
                "GET": colors.HexColor("#059669"),
                "POST": colors.HexColor("#2563eb"),
                "PUT": colors.HexColor("#b45309"),
                "DELETE": colors.HexColor("#dc2626"),
            }
            ep_data.append([
                Paragraph(f'<font color="{method_colors.get(method, BLACK).hexval()}">'
                          f'<b>{method}</b></font>',
                          ParagraphStyle("EP", fontName="Courier", fontSize=8.5,
                                         textColor=method_colors.get(method, BLACK))),
                Paragraph(f'<font name="Courier">{path}</font>',
                          ParagraphStyle("EP2", fontName="Courier", fontSize=8.5)),
                Paragraph(desc, ParagraphStyle("EP3", fontName="Helvetica", fontSize=8.5,
                                               leading=12)),
                Paragraph(auth, ParagraphStyle("EP4", fontName="Helvetica", fontSize=8,
                                               textColor=GRAY)),
            ])
        ep_style = TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LTGRAY]),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 7),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ])
        ep_t = Table(ep_data, colWidths=[0.6*inch, 1.8*inch, 3.1*inch, 1.2*inch])
        ep_t.setStyle(ep_style)
        story.append(ep_t)
        story.append(Spacer(1, 6))

    story.append(PageBreak())
    return story


def build_security(s):
    story = []
    story.append(Paragraph("8. Security & Compliance", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))

    story.append(Paragraph("Human-in-the-Loop Enforcement", s["H2"]))
    story.append(Paragraph(
        "CivicRecords AI is designed with mandatory human review at every decision point. "
        "The system never auto-redacts, auto-denies, or auto-releases records. All AI-generated "
        "content is clearly labeled as a draft requiring human confirmation.", s["Body"]))
    hitl = [
        "Exemption flags require explicit Reviewer confirmation before any document is withheld.",
        "Response drafts generated by the LLM require Reviewer approval before being marked as sent.",
        "Ingestion of new data sources requires Admin authorization.",
        "All AI suggestions display a confidence score and the source context used to generate them.",
        "The system will not proceed past the 'In Review' stage without an authenticated Reviewer action.",
    ]
    for item in hitl:
        story.append(Paragraph(f"• {item}", s["BulletItem"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Audit Logging", s["H2"]))
    story.append(Paragraph(
        "All user actions are recorded in a hash-chained audit log that provides tamper evidence. "
        "Each log entry contains a SHA-256 hash of its own content combined with the hash of the "
        "previous entry — any retroactive modification breaks the chain.", s["Body"]))
    audit_data = [
        ["Property", "Value"],
        ["Storage", "PostgreSQL audit_logs table (append-only at API level)"],
        ["Retention", "1,095 days (3 years) default; configurable via AUDIT_RETENTION_DAYS"],
        ["Hash algorithm", "SHA-256 chained (each entry hashes over: action + resource + timestamp + prev_hash)"],
        ["Logged events", "Login/logout, search queries, document access, exemption flag changes, request status changes, admin actions"],
        ["Export", "Admin can export audit log as JSON or CSV for external compliance systems"],
        ["Verification", "GET /api/v1/audit/{id} returns hash verification status"],
    ]
    story.append(make_table(audit_data, [1.6*inch, 5.1*inch]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Data Sovereignty", s["H2"]))
    story.append(Paragraph(
        "CivicRecords AI is designed for environments where resident data must never leave the "
        "network perimeter. The verification script <b>scripts/verify-sovereignty.sh</b> "
        "confirms no outbound connections are made during normal operation.", s["Body"]))
    sov = [
        "Runs entirely on local hardware — no cloud dependencies of any kind.",
        "All LLM inference runs locally via Ollama; no API keys, no external model services.",
        "No telemetry, analytics, crash reporting, or usage statistics collected.",
        "No 'phone home' capability — the system has no scheduled outbound connections.",
        "Ollama models are downloaded once at install time; updates are manual and IT-controlled.",
        "Self-signed or city-provided TLS certificates; no external certificate authority required.",
    ]
    for item in sov:
        story.append(Paragraph(f"• {item}", s["BulletItem"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Application Security", s["H2"]))
    sec_data = [
        ["Control", "Implementation"],
        ["Authentication", "JWT (HS256) with configurable expiry; bcrypt password hashing (cost factor 12)"],
        ["Authorization", "Role-based: Admin > Reviewer > Staff > Read-Only; enforced at API middleware layer"],
        ["Session management", "Token revocation via sessions table; configurable inactivity timeout"],
        ["Password policy", "No default passwords; first-run requires admin account creation"],
        ["API access", "All endpoints except /health and /auth/login require valid JWT bearer token"],
        ["HTTPS", "nginx terminates TLS; HTTP redirected to HTTPS; self-signed cert generated at install"],
        ["Secrets", "All credentials via environment variables (.env); no plaintext secrets in code"],
        ["Prompt injection", "Document content sanitized before LLM context injection"],
        ["Network binding", "Binds to localhost or city-designated internal IP only"],
    ]
    story.append(make_table(sec_data, [1.7*inch, 5.0*inch]))

    story.append(Paragraph("Regulatory Compliance Design", s["H2"]))
    story.append(Paragraph(
        "CivicRecords AI is designed to support compliance with Colorado CAIA (Colorado Artificial "
        "Intelligence Act) and similar state AI governance frameworks, as well as all 50 state "
        "open records statutes.", s["Body"]))
    comp = [
        ("Colorado CAIA", "Human-in-the-loop enforcement, AI content labeling, audit logging, and bias mitigation documentation."),
        ("50-State Open Records", "Per-state exemption rule library; configurable statutory deadlines; response template system."),
        ("WCAG 2.1 AA", "Planned for v0.2; frontend accessibility compliance for staff with disabilities."),
        ("Data Retention", "Configurable retention policies; export and deletion tools for records lifecycle management."),
    ]
    comp_data = [["Framework", "Compliance Approach"]] + list(comp)
    story.append(make_table(comp_data, [1.7*inch, 5.0*inch]))

    story.append(PageBreak())
    return story


def build_deployment(s):
    story = []
    story.append(Paragraph("9. Deployment", s["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))

    story.append(Paragraph("Supported Platforms", s["H2"]))
    plat_data = [
        ["Platform", "Docker Runtime", "Install Script", "Status"],
        ["Ubuntu 22.04+ / Debian 12+", "Docker Engine 26+", "bash install.sh", "Primary / Recommended"],
        ["Windows 10/11 (x64)", "Docker Desktop 4.x+", ".\\install.ps1", "Supported"],
        ["macOS 13+ (Apple Silicon / Intel)", "Docker Desktop 4.x+", "bash install.sh", "Supported"],
    ]
    story.append(make_table(plat_data, [2.0*inch, 1.6*inch, 1.5*inch, 1.6*inch]))
    story.append(Paragraph(
        "All platforms run identical Linux containers. The application behavior is identical "
        "regardless of host OS.", s["Body"]))

    story.append(Paragraph("Install Script Walkthrough", s["H2"]))
    story.append(Paragraph(
        "The install script (<b>install.sh</b> / <b>install.ps1</b>) automates the full setup:", s["Body"]))
    steps = [
        ("Step 1", "Check prerequisites (Docker, Docker Compose, available RAM and disk space)"),
        ("Step 2", "Copy .env.example to .env; prompt for required secrets (JWT_SECRET, admin password)"),
        ("Step 3", "Run docker compose pull to download all service images"),
        ("Step 4", "Run docker compose up -d to start all services"),
        ("Step 5", "Wait for health checks to pass (postgres, redis, ollama, api)"),
        ("Step 6", "Pull required Ollama models: nomic-embed-text (auto) + Gemma 4 via installer picker (gemma4:e4b default; e2b/26b/31b also selectable, 26b/31b require stronger hardware than the 32 GB baseline)"),
        ("Step 7", "Run database migrations (alembic upgrade head via api container)"),
        ("Step 8", "Seed initial admin account using FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD from .env"),
        ("Step 9", "Print success message with URL: http://localhost:8080"),
    ]
    step_data = [["Step", "Action"]] + list(steps)
    story.append(make_table(step_data, [0.7*inch, 6.0*inch]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Docker Compose Service Configuration", s["H2"]))
    story.append(Paragraph(
        "The production stack is defined in <b>docker-compose.yml</b>. "
        "A development override (<b>docker-compose.dev.yml</b>) adds volume mounts for "
        "hot-reload and exposes the API port directly for debugging.", s["Body"]))

    story.append(Paragraph("Key Environment Variables", s["H2"]))
    env_data = [
        ["Variable", "Required", "Default", "Description"],
        ["JWT_SECRET", "Yes", "—", "Secret key for JWT token signing (min 32 chars)"],
        ["FIRST_ADMIN_EMAIL", "Yes", "admin@example.gov", "Email address for initial admin account"],
        ["FIRST_ADMIN_PASSWORD", "Yes", "—", "Password for initial admin account"],
        ["DATABASE_URL", "No", "postgresql+asyncpg://civicrecords:civicrecords@postgres:5432/civicrecords", "PostgreSQL connection string"],
        ["REDIS_URL", "No", "redis://redis:6379/0", "Redis connection string"],
        ["OLLAMA_BASE_URL", "No", "http://ollama:11434", "Ollama API endpoint"],
        ["AUDIT_RETENTION_DAYS", "No", "1095", "Audit log retention (days)"],
        ["EMBEDDING_MODEL", "No", "nomic-embed-text", "Ollama model for embeddings"],
        ["LLM_MODEL", "No", "gemma2:4b", "Ollama model for synthesis"],
    ]
    story.append(make_table(env_data, [1.8*inch, 0.65*inch, 1.5*inch, 2.75*inch]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Updates and Maintenance", s["H2"]))
    maint = [
        "Application updates: docker compose pull && docker compose up -d (migrations apply automatically on startup).",
        "LLM model updates: docker compose exec ollama ollama pull <model-name> (independent of app updates).",
        "Backup: pg_dump for PostgreSQL data; backup the .env file and any custom exemption rules.",
        "Logs: docker compose logs -f <service> for real-time service logs.",
        "Health: curl http://localhost:8000/health returns JSON status for all downstream services.",
    ]
    for item in maint:
        story.append(Paragraph(f"• {item}", s["BulletItem"]))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))
    story.append(Paragraph(
        "CivicRecords AI v1.0.0  ·  Apache License 2.0  ·  "
        "https://github.com/CivicSuite/civicrecords-ai",
        ParagraphStyle("FootNote", parent=s["Body"], fontSize=9,
                       textColor=GRAY, alignment=TA_CENTER)))

    return story


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Generating {OUTPUT_PATH} …")

    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=0.75 * inch,
        title="CivicRecords AI — Technical Documentation v1.0.0",
        author="CivicRecords AI Project",
        subject="Technical Reference",
    )

    W = letter[0]
    s = make_styles()

    story = []
    story += build_title_page(s, W)
    story += build_toc(s)
    story += build_overview(s)
    story += build_architecture(s)
    story += build_arch_diagram(s, W)
    story += build_dataflow_diagram(s, W)
    story += build_tech_stack(s)
    story += build_db_schema(s)
    story += build_api_endpoints(s)
    story += build_security(s)
    story += build_deployment(s)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"Done — {OUTPUT_PATH}")
    size_kb = os.path.getsize(OUTPUT_PATH) // 1024
    print(f"File size: {size_kb} KB")


if __name__ == "__main__":
    main()
