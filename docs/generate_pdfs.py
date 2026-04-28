"""
CivicRecords AI — PDF Generator
Produces README-FULL.pdf and README.pdf at the repository root.
Run: python docs/generate_pdfs.py
"""

from pathlib import Path
from datetime import date

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, HRFlowable, Flowable, Image as RLImage,
)
import re

# Markdown image-ref pattern: ![alt](path)
IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
CIVIC_DARK   = colors.HexColor("#1a3a5c")
CIVIC_MID    = colors.HexColor("#2563eb")
CIVIC_ACCENT = colors.HexColor("#3b82f6")
CIVIC_LIGHT  = colors.HexColor("#eff6ff")
CIVIC_ROW    = colors.HexColor("#f8fafc")
GRAY_BG      = colors.HexColor("#f3f4f6")
GRAY_BORDER  = colors.HexColor("#d1d5db")
WHITE        = colors.white
BLACK        = colors.black

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def make_styles():
    getSampleStyleSheet()
    styles = {}

    styles["title"] = ParagraphStyle(
        "CivicTitle",
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=CIVIC_DARK,
        alignment=TA_CENTER,
        spaceAfter=8,
        leading=34,
    )
    styles["subtitle"] = ParagraphStyle(
        "CivicSubtitle",
        fontName="Helvetica",
        fontSize=14,
        textColor=CIVIC_MID,
        alignment=TA_CENTER,
        spaceAfter=6,
        leading=18,
    )
    styles["tagline"] = ParagraphStyle(
        "CivicTagline",
        fontName="Helvetica-Oblique",
        fontSize=11,
        textColor=colors.HexColor("#374151"),
        alignment=TA_CENTER,
        spaceAfter=4,
        leading=14,
    )
    styles["h1"] = ParagraphStyle(
        "CivicH1",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=CIVIC_DARK,
        spaceBefore=18,
        spaceAfter=8,
        leading=20,
    )
    styles["h2"] = ParagraphStyle(
        "CivicH2",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=CIVIC_MID,
        spaceBefore=14,
        spaceAfter=6,
        leading=16,
    )
    styles["h3"] = ParagraphStyle(
        "CivicH3",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=CIVIC_DARK,
        spaceBefore=10,
        spaceAfter=4,
        leading=14,
    )
    styles["body"] = ParagraphStyle(
        "CivicBody",
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=6,
        leading=14,
    )
    styles["body_small"] = ParagraphStyle(
        "CivicBodySm",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#374151"),
        spaceAfter=4,
        leading=12,
    )
    styles["code"] = ParagraphStyle(
        "CivicCode",
        fontName="Courier",
        fontSize=8,
        textColor=colors.HexColor("#1f2937"),
        backColor=GRAY_BG,
        spaceBefore=4,
        spaceAfter=4,
        leading=11,
        leftIndent=8,
        rightIndent=8,
    )
    styles["bullet"] = ParagraphStyle(
        "CivicBullet",
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=3,
        leading=13,
        leftIndent=16,
        bulletIndent=4,
    )
    styles["toc_h1"] = ParagraphStyle(
        "TocH1",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=CIVIC_DARK,
        leading=14,
        spaceAfter=2,
    )
    styles["toc_h2"] = ParagraphStyle(
        "TocH2",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#374151"),
        leading=12,
        leftIndent=16,
        spaceAfter=1,
    )
    styles["center_body"] = ParagraphStyle(
        "CenterBody",
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#1f2937"),
        alignment=TA_CENTER,
        spaceAfter=4,
        leading=14,
    )
    styles["caption"] = ParagraphStyle(
        "Caption",
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER,
        spaceAfter=6,
        leading=10,
    )
    return styles

# ---------------------------------------------------------------------------
# Table style helpers
# ---------------------------------------------------------------------------
def make_table_style(col_count, header_cols=None):
    """Standard civic table style with alternating rows."""
    cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0),  CIVIC_DARK),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  9),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, CIVIC_ROW]),
        ("GRID",        (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    return TableStyle(cmds)

# ---------------------------------------------------------------------------
# Page header/footer callback
# ---------------------------------------------------------------------------
def make_page_callback(doc_title, show_header=True):
    def on_page(canvas, doc):
        canvas.saveState()
        w, h = LETTER
        margin = inch

        if show_header and doc.page > 1:
            # Blue rule line
            canvas.setStrokeColor(CIVIC_ACCENT)
            canvas.setLineWidth(1.2)
            canvas.line(margin, h - 0.6 * inch, w - margin, h - 0.6 * inch)
            # Left header text
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(CIVIC_MID)
            canvas.drawString(margin, h - 0.48 * inch, doc_title)
            # Right: page number
            canvas.drawRightString(w - margin, h - 0.48 * inch, f"Page {doc.page}")

        # Footer
        canvas.setStrokeColor(CIVIC_ACCENT)
        canvas.setLineWidth(0.6)
        canvas.line(margin, 0.55 * inch, w - margin, 0.55 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(margin, 0.38 * inch, "Apache License 2.0 — github.com/CivicSuite/civicrecords-ai")
        canvas.drawRightString(w - margin, 0.38 * inch, "© 2026 CivicRecords AI")

        canvas.restoreState()
    return on_page

# ---------------------------------------------------------------------------
# Architecture Diagram Flowables
# ---------------------------------------------------------------------------
class SystemArchDiagram(Flowable):
    """Full system architecture box diagram."""

    def __init__(self, width=None, height=None):
        super().__init__()
        self.diagram_width = width or (6.5 * inch)
        self.diagram_height = height or (3.2 * inch)

    def wrap(self, aW, aH):
        return self.diagram_width, self.diagram_height

    def draw(self):
        c = self.canv

        def box(x, y, bw, bh, fill, label, sublabel=None, font_size=8):
            c.setFillColor(fill)
            c.setStrokeColor(CIVIC_DARK)
            c.setLineWidth(0.8)
            c.roundRect(x, y, bw, bh, 4, fill=1, stroke=1)
            c.setFillColor(WHITE if fill != WHITE else CIVIC_DARK)
            c.setFont("Helvetica-Bold", font_size)
            lx = x + bw / 2
            ly = y + bh / 2 + (4 if sublabel else 0)
            c.drawCentredString(lx, ly, label)
            if sublabel:
                c.setFont("Helvetica", font_size - 1)
                c.setFillColor(WHITE if fill != WHITE else colors.HexColor("#4b5563"))
                c.drawCentredString(lx, y + bh / 2 - 6, sublabel)

        def arrow(x1, y1, x2, y2, label=None):
            c.setStrokeColor(CIVIC_MID)
            c.setLineWidth(1)
            c.line(x1, y1, x2, y2)
            # Arrowhead
            import math
            angle = math.atan2(y2 - y1, x2 - x1)
            size = 5
            c.setFillColor(CIVIC_MID)
            p = c.beginPath()
            p.moveTo(x2, y2)
            p.lineTo(x2 - size * math.cos(angle - 0.4), y2 - size * math.sin(angle - 0.4))
            p.lineTo(x2 - size * math.cos(angle + 0.4), y2 - size * math.sin(angle + 0.4))
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            if label:
                mx = (x1 + x2) / 2
                my = (y1 + y2) / 2 + 4
                c.setFont("Helvetica", 6.5)
                c.setFillColor(colors.HexColor("#374151"))
                c.drawCentredString(mx, my, label)

        # Dimensions
        bw = 1.1 * inch   # box width
        bh = 0.48 * inch  # box height

        # Row y positions (bottom-up)
        row1_y = 0.1 * inch                     # bottom: infrastructure layer
        row2_y = row1_y + bh + 0.35 * inch      # middle: services
        row3_y = row2_y + bh + 0.35 * inch      # top: frontend/API

        # --- Top row: Browser -> nginx -> FastAPI ---
        x_browser = 0.05 * inch
        x_nginx   = x_browser + bw + 0.3 * inch
        x_api     = x_nginx + bw + 0.3 * inch

        box(x_browser, row3_y, bw, bh, CIVIC_ACCENT, "Browser", "React UI")
        box(x_nginx,   row3_y, bw, bh, CIVIC_MID,    "nginx",   "frontend")
        box(x_api,     row3_y, bw, bh, CIVIC_DARK,   "FastAPI",  "API :8000")

        arrow(x_browser + bw, row3_y + bh/2, x_nginx, row3_y + bh/2)
        arrow(x_nginx + bw,   row3_y + bh/2, x_api,   row3_y + bh/2)

        # --- Middle row: PostgreSQL, Redis, Ollama ---
        x_pg  = 0.05 * inch
        x_red = x_pg + bw + 0.3 * inch
        x_oll = x_red + bw + 0.3 * inch

        box(x_pg,  row2_y, bw, bh, colors.HexColor("#0f766e"), "PostgreSQL", "17+pgvector")
        box(x_red, row2_y, bw, bh, colors.HexColor("#b91c1c"), "Redis",      "7.2 queue")
        box(x_oll, row2_y, bw, bh, colors.HexColor("#7e22ce"), "Ollama",     "local LLM")

        # FastAPI -> services
        api_cx = x_api + bw / 2
        arrow(api_cx, row3_y, x_pg + bw/2, row2_y + bh, "SQL")
        arrow(api_cx, row3_y, x_red + bw/2, row2_y + bh, "tasks")
        arrow(api_cx, row3_y, x_oll + bw/2, row2_y + bh, "infer")

        # --- Bottom row: Celery Worker, Celery Beat ---
        x_cw = x_red - bw/2
        x_cb = x_cw + bw + 0.3 * inch

        box(x_cw, row1_y, bw, bh, colors.HexColor("#92400e"), "Celery",  "worker")
        box(x_cb, row1_y, bw, bh, colors.HexColor("#854d0e"), "Celery",  "beat")

        arrow(x_red + bw/2, row2_y, x_cw + bw/2, row1_y + bh, "dequeue")
        arrow(x_cb + bw/2, row1_y + bh, x_cw + bw/2, row1_y + bh/2)

        # Layer labels on right
        lx = x_oll + bw + 0.2 * inch
        for ly, label in [
            (row3_y + bh/2 - 4, "Presentation"),
            (row2_y + bh/2 - 4, "Services"),
            (row1_y + bh/2 - 4, "Workers"),
        ]:
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(colors.HexColor("#6b7280"))
            c.drawString(lx, ly, label)


class ConnectorDiagram(Flowable):
    """Connector framework overview diagram."""

    def __init__(self, width=None, height=None):
        super().__init__()
        self.diagram_width = width or (6.5 * inch)
        self.diagram_height = height or (2.4 * inch)

    def wrap(self, aW, aH):
        return self.diagram_width, self.diagram_height

    def draw(self):
        c = self.canv
        w = self.diagram_width

        def box(x, y, bw, bh, fill, label, sublabel=None):
            c.setFillColor(fill)
            c.setStrokeColor(CIVIC_DARK)
            c.setLineWidth(0.8)
            c.roundRect(x, y, bw, bh, 4, fill=1, stroke=1)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 8)
            ly = y + bh / 2 + (3 if sublabel else 0)
            c.drawCentredString(x + bw / 2, ly, label)
            if sublabel:
                c.setFont("Helvetica", 7)
                c.drawCentredString(x + bw / 2, y + bh / 2 - 6, sublabel)

        bw = 1.0 * inch
        bh = 0.42 * inch

        # Protocol layer (center)
        proto_x = (w - 1.4 * inch) / 2
        proto_y = 0.9 * inch
        c.setFillColor(CIVIC_DARK)
        c.setStrokeColor(CIVIC_DARK)
        c.roundRect(proto_x, proto_y, 1.4 * inch, bh, 5, fill=1, stroke=1)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(proto_x + 0.7 * inch, proto_y + bh/2 + 3, "Connector Protocol")
        c.setFont("Helvetica", 7)
        c.drawCentredString(proto_x + 0.7 * inch, proto_y + bh/2 - 6, "auth / discover / fetch / health_check")

        # Left connectors
        for i, (lbl, sub) in enumerate([
            ("File System",  "local dirs"),
            ("Manual Drop",  "watched folder"),
            ("REST API",     "API key/Bearer/OAuth2"),
            ("ODBC",         "pyodbc/SQL"),
        ]):
            bx = 0.1 * inch
            by = 2.1 * inch - i * (bh + 0.15 * inch)
            box(bx, by, bw, bh, CIVIC_ACCENT, lbl, sub)
            # Arrow to protocol
            c.setStrokeColor(CIVIC_MID)
            c.setLineWidth(0.8)
            c.line(bx + bw, by + bh/2, proto_x, proto_y + bh/2)

        # Right: ingestion pipeline
        pipe_x = proto_x + 1.4 * inch + 0.3 * inch
        pipe_y = proto_y
        box(pipe_x, pipe_y, bw, bh, colors.HexColor("#0f766e"), "Ingestion", "Pipeline")
        c.setStrokeColor(CIVIC_MID)
        c.setLineWidth(1)
        c.line(proto_x + 1.4 * inch, proto_y + bh/2, pipe_x, pipe_y + bh/2)

        # Right side: roadmap
        road_x = pipe_x + bw + 0.25 * inch
        for i, (lbl, sub) in enumerate([
            ("IMAP Email",  "roadmap"),
            ("SharePoint",  "roadmap"),
            ("SMB/NFS",     "roadmap"),
        ]):
            by = 1.7 * inch - i * (bh + 0.18 * inch)
            c.setFillColor(colors.HexColor("#9ca3af"))
            c.setStrokeColor(colors.HexColor("#6b7280"))
            c.setLineWidth(0.5)
            c.roundRect(road_x, by, bw, bh, 4, fill=1, stroke=1)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(road_x + bw/2, by + bh/2 + 3, lbl)
            c.setFont("Helvetica", 7)
            c.drawCentredString(road_x + bw/2, by + bh/2 - 6, sub)

        # Caption labels
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(colors.HexColor("#6b7280"))
        c.drawCentredString(0.1 * inch + bw/2, 0.1 * inch, "Available")
        c.drawCentredString(road_x + bw/2, 0.1 * inch, "Planned")


class CircuitBreakerDiagram(Flowable):
    """Sync failure / circuit breaker state machine."""

    def __init__(self, width=None, height=None):
        super().__init__()
        self.diagram_width = width or (6.0 * inch)
        self.diagram_height = height or (2.0 * inch)

    def wrap(self, aW, aH):
        return self.diagram_width, self.diagram_height

    def draw(self):
        c = self.canv

        def state(cx, cy, r, fill, label):
            c.setFillColor(fill)
            c.setStrokeColor(CIVIC_DARK)
            c.setLineWidth(1)
            c.circle(cx, cy, r, fill=1, stroke=1)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(cx, cy - 3, label)

        def edge(x1, y1, x2, y2, label, above=True):
            import math
            c.setStrokeColor(CIVIC_MID)
            c.setLineWidth(0.8)
            c.line(x1, y1, x2, y2)
            angle = math.atan2(y2 - y1, x2 - x1)
            size = 5
            c.setFillColor(CIVIC_MID)
            p = c.beginPath()
            p.moveTo(x2, y2)
            p.lineTo(x2 - size * math.cos(angle - 0.4), y2 - size * math.sin(angle - 0.4))
            p.lineTo(x2 - size * math.cos(angle + 0.4), y2 - size * math.sin(angle + 0.4))
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2 + (8 if above else -12)
            c.setFont("Helvetica", 6.5)
            c.setFillColor(colors.HexColor("#374151"))
            c.drawCentredString(mx, my, label)

        r = 0.38 * inch
        y_mid = self.diagram_height / 2

        s_healthy  = (1.0 * inch,  y_mid)
        s_degraded = (3.0 * inch,  y_mid)
        s_open     = (5.0 * inch,  y_mid)

        state(*s_healthy,  r, colors.HexColor("#16a34a"), "Healthy")
        state(*s_degraded, r, colors.HexColor("#ca8a04"), "Degraded")
        state(*s_open,     r, colors.HexColor("#dc2626"), "Circuit\nOpen")

        edge(s_healthy[0] + r,  s_healthy[1],  s_degraded[0] - r, s_degraded[1], "failure > 0", above=True)
        edge(s_degraded[0] - r, s_degraded[1], s_healthy[0] + r,  s_healthy[1],  "all success",  above=False)
        edge(s_degraded[0] + r, s_degraded[1], s_open[0] - r,    s_open[1],     "5 full-run fails", above=True)
        edge(s_open[0] - r,    s_open[1],     s_degraded[0] + r, s_degraded[1], "admin unpause", above=False)


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------
P = Paragraph


def _resolve_png(md_dir: Path, ref_path: str) -> Path:
    """Resolve a markdown image ref to a PNG on disk (path is relative to md_dir).

    Reportlab handles PNG well; SVG refs are mapped to .png siblings.
    """
    p = (md_dir / ref_path).resolve()
    if p.suffix.lower() == ".svg":
        p = p.with_suffix(".png")
    return p


def embed_markdown_image_flowables(md_dir: Path, alt: str, ref_path: str,
                                   styles, width_inches: float = 6.0):
    """Return a list of reportlab flowables embedding the resolved PNG.

    Skips with a logged warning if the resolved PNG is missing (does not crash).
    Calculates proportional height via PIL when available; falls back to
    reportlab.lib.utils.ImageReader otherwise.
    """
    png = _resolve_png(md_dir, ref_path)
    if not png.exists():
        print(f"  WARNING: image not found, skipping: {png} (ref: {ref_path})")
        return []
    try:
        try:
            from PIL import Image as PILImage
            with PILImage.open(str(png)) as im:
                iw, ih = im.size
        except Exception:
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(str(png)).getSize()
        target_w = width_inches * inch
        target_h = target_w * (ih / iw) if iw else target_w * 0.5
        out = [
            Spacer(1, 4),
            RLImage(str(png), width=target_w, height=target_h),
        ]
        if alt:
            out.append(P(alt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                         styles["caption"]))
        out.append(Spacer(1, 6))
        return out
    except Exception as e:
        print(f"  WARNING: failed to embed image {png}: {e}")
        return []


def sp(n=6):
    return Spacer(1, n)


def HR():
    return HRFlowable(width="100%", thickness=0.5, color=CIVIC_ACCENT, spaceAfter=6, spaceBefore=6)


def section_header(text, styles, level=1):
    key = "h1" if level == 1 else ("h2" if level == 2 else "h3")
    elems = []
    if level == 1:
        elems.append(sp(4))
        elems.append(HR())
    elems.append(P(text, styles[key]))
    return elems


def bullet_list(items, styles):
    return [P(f"• {item}", styles["bullet"]) for item in items]


def code_block(text, styles):
    lines = text.strip().split("\n")
    elems = [sp(2)]
    for line in lines:
        elems.append(P(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                       styles["code"]))
    elems.append(sp(2))
    return elems


def make_table(data, col_widths, styles_dict, style_override=None):
    ts = make_table_style(len(data[0]) if data else 1)
    if style_override:
        ts = style_override
    t = Table(data, colWidths=col_widths)
    t.setStyle(ts)
    return t

# ---------------------------------------------------------------------------
# README-FULL.pdf content
# ---------------------------------------------------------------------------
FEATURES = [
    ("AI-Powered Search",
     "Natural language hybrid search (semantic + keyword) across all ingested documents. "
     "Source attribution, normalized relevance scores, optional AI-generated summaries."),
    ("Document Ingestion",
     "Automatic parsing of PDF, DOCX, XLSX, CSV, email, HTML, and text files. "
     "Scanned documents processed via multimodal AI (Gemma 4) with Tesseract OCR fallback."),
    ("Exemption Detection",
     "Tier 1 PII detection (SSN, credit card with Luhn validation, phone, email, bank "
     "accounts, state-specific driver's licenses) plus per-state statutory keyword matching. "
     "Optional LLM secondary review. All flags require human confirmation."),
    ("Request Management",
     "Full lifecycle tracking with 11 statuses: intake → clarification → assignment → "
     "search → review → drafting → approval → fulfillment → closure. Timeline, messaging, "
     "fee tracking, and response letter generation."),
    ("Guided Onboarding",
     "3-phase wizard helps cities configure their profile, identify data systems across "
     "12 municipal domains, and surface coverage gaps."),
    ("Municipal Systems Catalog",
     "Curated knowledge base of 25+ municipal software vendors across 12 functional domains "
     "(finance, public safety, permitting, HR, etc.) with discovery hints and connector templates."),
    ("Universal Connector Framework",
     "Standardized protocol (authenticate/discover/fetch/health_check). Ships with file system, "
     "REST API (API key/Bearer/OAuth2/Basic; JSON/XML/CSV; page/offset/cursor pagination), "
     "and ODBC (SQL databases via pyodbc) connectors."),
    ("Scheduled Sync & Idempotent Ingestion",
     "Per-source cron scheduling via croniter with 5-minute floor and 7-day min-interval "
     "validation. Idempotent pipeline deduplicates by content hash (binary) or stable "
     "source-path (structured). Concurrent-update races prevented via SELECT FOR UPDATE."),
    ("Sync Failure Tracking & Circuit Breaker",
     "Two-layer retry (task-level exponential backoff + record-level per-tick retry). "
     "Automatic circuit breaker after 5 consecutive full-run failures. Admin UI with colored "
     "health badge, failed records panel, and Sync Now button."),
    ("Operational Analytics",
     "Real-time metrics: average response time, deadline compliance rate, overdue requests, "
     "status breakdown dashboard."),
    ("Notification Service",
     "Template-based notification system with SMTP email delivery via Celery beat (60s interval). "
     "12 templates across all status transitions."),
    ("Compliance by Design",
     "Hash-chained audit logs, human-in-the-loop enforcement, AI content labeling, data "
     "sovereignty verification. Designed for Colorado CAIA and 50-state regulatory compliance."),
    ("Civic Design System",
     "Professional UI built with shadcn/ui, civic blue design tokens, sidebar navigation. "
     "WCAG 2.2 AA targeted (44px touch targets, skip navigation, icon+color status badges)."),
    ("Federation-Ready",
     "REST API with service accounts enables future cross-jurisdiction record discovery "
     "between CivicRecords AI instances."),
    ("50-State Exemption Rules",
     "180 exemption rules across 51 jurisdictions (all 50 states + DC) with per-state "
     "statutory keyword matching and rule testing with ReDoS protection."),
    ("Department Access Controls",
     "Staff scoped to own department; admins see all. Department CRUD API with full audit "
     "logging and RBAC role hierarchy enforcement."),
    ("Compliance Templates",
     "5 compliance template documents (AI Use Disclosure, Response Letter Disclosure, "
     "CAIA Impact Assessment, AI Governance Policy, Data Residency Attestation) with city "
     "profile variable substitution."),
]

DB_TABLES = [
    ("users",              "Staff accounts with RBAC roles and department associations"),
    ("departments",        "City department definitions for access scoping"),
    ("audit_logs",         "Hash-chained, tamper-evident activity log"),
    ("requests",           "Open records request lifecycle tracking"),
    ("request_documents",  "Documents attached to requests with include/exclude decisions"),
    ("request_messages",   "Internal and requester communications per request"),
    ("request_fees",       "Fee line items, waivers, and collection status"),
    ("request_events",     "Timeline events for request audit trail"),
    ("documents",          "Ingested document metadata and content hashes"),
    ("document_chunks",    "Text segments from parsed documents"),
    ("embeddings",         "pgvector floating-point vectors for semantic search"),
    ("datasources",        "Connector configurations and sync state"),
    ("sync_failures",      "Per-record failure tracking with retry and dismiss workflow"),
    ("sync_run_log",       "One-row-per-run ingestion history"),
    ("exemption_rules",    "State-specific statutory exemption rules"),
    ("exemption_flags",    "Per-document flags awaiting human review"),
    ("exemption_outcomes", "Accepted/rejected flag decisions for auditability"),
    ("onboarding_state",   "Wizard progress and city profile data"),
    ("city_profile",       "City name, state, contact, statutory deadline"),
    ("municipal_systems",  "Known vendor catalog entries"),
    ("coverage_items",     "Gap map entries per functional domain"),
    ("service_accounts",   "API keys for federation access"),
    ("notification_templates", "Email template definitions"),
    ("notification_log",   "Delivery history for all notifications"),
    ("compliance_templates", "5 AI/compliance disclosure document templates"),
    ("model_registry",     "LLM model metadata and compliance records"),
    ("llm_interactions",   "Logged LLM calls with token counts"),
    ("settings",           "System-wide configuration key-value store"),
    ("alembic_version",    "Database migration version tracking"),
]

KEY_DECISIONS = [
    ("D-IDEM-1",  "Split idempotency: binary by (source_id, file_hash); structured by (source_id, source_path). REST/ODBC hash is non-deterministic."),
    ("D-IDEM-7",  "On UPDATE: DELETE existing Chunk rows and pgvector embeddings in same transaction before re-generating. Stale embeddings are a correctness bug."),
    ("D-IDEM-8",  "ingest_structured_record uses SELECT … FOR UPDATE before comparing hashes to prevent concurrent-worker race."),
    ("D-SCHED-1", "sync_schedule (cron/croniter) replaces schedule_minutes. Correct trigger: get_next(datetime) <= now(). Original spec had inverted logic."),
    ("D-SCHED-2", "Min interval validated via rolling 7-day sample (2016 intervals). Floor: 5 minutes. Catches adversarial cron expressions."),
    ("D-SCHED-3", "Cron evaluated in UTC. UI shows both UTC and local time. Wizard discloses 'All schedules run in UTC.'"),
    ("D-FAIL-1",  "Two retry layers: task-level (3 retries, 30s→90s→270s) for transient errors; record-level (N=100/T=90s cap) for persistent failures."),
    ("D-FAIL-2",  "Partial failure: cursor advances past successful records. Failed records written to sync_failures only."),
    ("D-FAIL-4",  "Circuit breaker: full-run failure = authenticate() or discover() throws OR all fetches fail. Zero-work does NOT move counter."),
    ("D-FAIL-5",  "Unpause grace: threshold=2 for first post-unpause window, returns to 5 after success. Prevents 5-cycle wait confusion."),
    ("D-FAIL-6",  "Dismiss = soft delete (status=dismissed + dismissed_at + dismissed_by). Hard delete prohibited — compliance artifact."),
    ("D-FAIL-8",  "health_status computed at response time via LEFT JOIN — not stored. Avoids cache staleness."),
    ("D-FAIL-12", "429 with Retry-After honored at task-level (not sync_failures). Capped at 600s to prevent worker starvation."),
    ("D-FAIL-13", "sync_failures and sync_run_log both CASCADE on DataSource delete."),
    ("D-UI-1",    "Sync Now button stays disabled until last_sync_at advances (exponential backoff polling: 5s→10s→20s→30s). Timeout 15 min."),
    ("D-UI-2",    "Circuit-open notifications: created_by recipient, fallback to ADMIN-role users. Rate-limit: 5-min digest."),
    ("D-TENANT-1","Single-tenant per install (one city per deployment). No org-level isolation within a deployment."),
]

# ---------------------------------------------------------------------------
# Build README-FULL.pdf
# ---------------------------------------------------------------------------
def build_readme_full(out_path):
    print(f"  Generating {out_path.name}...")
    styles = make_styles()
    doc = BaseDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
    )
    cb = make_page_callback("CivicRecords AI — Technical Reference")
    frame = Frame(inch, 0.75 * inch, 6.5 * inch, 9.4 * inch, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=cb)])

    story = []

    # --- Title page ---
    story.append(sp(80))
    story.append(P("CivicRecords AI", styles["title"]))
    story.append(sp(8))
    story.append(P("Technical Reference — v1.4.1", styles["subtitle"]))
    story.append(sp(4))
    story.append(P(f"Generated {date.today().strftime('%B %d, %Y')}", styles["tagline"]))
    story.append(sp(4))
    story.append(P("Apache License 2.0", styles["tagline"]))
    story.append(sp(12))
    story.append(HR())
    story.append(sp(8))
    story.append(P(
        "Open-source, locally-hosted AI that helps American cities respond to open records requests.",
        styles["center_body"]
    ))
    story.append(sp(4))
    story.append(P(
        "Runs entirely on a single machine inside your city's network — no cloud, no vendor lock-in, "
        "no resident data leaving the building.",
        styles["center_body"]
    ))
    story.append(sp(120))
    story.append(P("github.com/CivicSuite/civicrecords-ai", styles["tagline"]))

    story.append(PageBreak())

    # --- Table of Contents ---
    story += section_header("Table of Contents", styles, 1)
    toc_entries = [
        ("1.", "Executive Summary"),
        ("2.", "System Architecture"),
        ("3.", "Core Features"),
        ("4.", "Technology Stack"),
        ("5.", "Installation & Quick Start"),
        ("6.", "Database Schema (29 tables)"),
        ("7.", "API Reference"),
        ("8.", "Connector Framework"),
        ("9.", "Sync Failure & Circuit Breaker"),
        ("10.", "Security Architecture"),
        ("11.", "Key Engineering Decisions"),
        ("12.", "Test Suite"),
        ("13.", "License"),
    ]
    for num, title in toc_entries:
        story.append(P(f"<b>{num}</b>  {title}", styles["toc_h1"]))
    story.append(PageBreak())

    # --- 1. Executive Summary ---
    story += section_header("1. Executive Summary", styles, 1)
    story.append(P(
        "CivicRecords AI is an open-source, locally-hosted AI system purpose-built for "
        "municipal open records request processing. Every city in America handles FOIA, CORA, "
        "and equivalent state open-records laws. Staff manually search file shares, email "
        "archives, and databases — then review every document for exemptions before release. "
        "That process is slow, error-prone, and a growing burden as request volumes rise.",
        styles["body"]
    ))
    story.append(P(
        "No open-source tool existed for the <b>responder side</b> of open records at the "
        "municipal level. CivicRecords AI fills that gap.",
        styles["body"]
    ))
    story += section_header("Who It Is For", styles, 2)
    story += bullet_list([
        "City clerks and records officers processing day-to-day open records requests",
        "Department liaisons providing documents for specific requests",
        "Legal reviewers and supervisors approving responses before release",
        "City IT administrators installing and maintaining the system",
    ], styles)
    story += section_header("Key Capabilities", styles, 2)
    story += bullet_list([
        "AI-powered hybrid search (semantic + keyword) over all city documents",
        "Full request lifecycle management from intake to fulfillment",
        "Automatic PII and exemption detection with 180 rules across 51 jurisdictions",
        "Universal connector framework for file systems, REST APIs, and SQL databases",
        "Hash-chained audit logging designed for legal compliance",
        "Runs entirely on local hardware — no cloud, no telemetry, no vendor lock-in",
    ], styles)
    story.append(P(
        "Current release: <b>v1.4.1</b> (April 28, 2026). 29 database tables, ~30 API endpoints, "
        "617 backend + 36 frontend automated tests. Tier 5 and Tier 6 complete — ENG-001 "
        "(at-rest encryption for <tt>data_sources.connection_config</tt> via Fernet envelope) "
        "is closed. Tier 5 shipped the minimal public portal (T5D) and unsigned Windows "
        "installer (T5E).",
        styles["body"]
    ))

    story.append(PageBreak())

    # --- 2. System Architecture ---
    story += section_header("2. System Architecture", styles, 1)
    story.append(P(
        "CivicRecords AI deploys as a 7-service Docker Compose stack. All services run on "
        "Linux containers regardless of host operating system (Windows, macOS, or Linux). "
        "No internet connection is required after initial setup.",
        styles["body"]
    ))
    story += section_header("Service Architecture", styles, 2)
    story.append(P(
        "The diagram below shows the runtime service topology and primary data flows:",
        styles["body"]
    ))
    story.append(sp(4))
    story.append(SystemArchDiagram())
    story.append(P("Figure 1 — CivicRecords AI 7-service Docker Compose architecture.", styles["caption"]))
    story.append(sp(6))

    svc_data = [
        ["Service", "Image", "Port", "Role"],
        ["postgres",  "PostgreSQL 17 + pgvector", "5432",  "Primary data store + vector index"],
        ["redis",     "Redis 7.2",                "6379",  "Celery task queue and result backend"],
        ["ollama",    "Ollama latest",            "11434", "Local LLM inference (Gemma 4)"],
        ["api",       "Python 3.12 / FastAPI",    "8000",  "REST API, auth, business logic"],
        ["worker",    "Celery worker",            "—",     "Async document ingestion tasks"],
        ["beat",      "Celery beat",              "—",     "Scheduled sync trigger (cron)"],
        ["frontend",  "nginx + React 18",         "8080",  "Staff web interface"],
    ]
    story.append(make_table(svc_data, [1.2*inch, 1.8*inch, 0.7*inch, 2.8*inch], styles))
    story.append(sp(6))
    story.append(P(
        "All configuration is via environment variables in <font name='Courier'>.env</font>. "
        "AMD GPU/NPU hardware auto-detection is included (ROCm on Linux, DirectML on Windows).",
        styles["body"]
    ))

    # Embed architecture diagrams referenced by README.md
    for alt, ref in [
        ("Deployment stack — entire system runs inside Docker Compose on the city's network. "
         "No cloud, no outbound by default.",
         "docs/diagrams/deployment-stack.svg"),
        ("LLM call flow: records-ai routes through civiccore.llm to a local Ollama provider; "
         "cloud providers are opt-in only.",
         "docs/diagrams/llm-flow.svg"),
        ("Sovereignty boundary: all runtime components live inside the city's on-prem network. "
         "Connector credentials encrypted at rest with Fernet.",
         "docs/diagrams/sovereignty.svg"),
    ]:
        story.extend(embed_markdown_image_flowables(REPO_ROOT, alt, ref, styles))

    story.append(PageBreak())

    # --- 3. Core Features ---
    story += section_header("3. Core Features", styles, 1)
    story.append(P(
        f"CivicRecords AI ships with {len(FEATURES)} documented features across ingestion, "
        "request management, search, exemption detection, analytics, and compliance.",
        styles["body"]
    ))
    for i, (name, desc) in enumerate(FEATURES, 1):
        story.append(sp(4))
        story.append(KeepTogether([
            P(f"<b>{i}. {name}</b>", styles["h3"]),
            P(desc, styles["body"]),
        ]))

    story.append(PageBreak())

    # --- 4. Technology Stack ---
    story += section_header("4. Technology Stack", styles, 1)
    tech_data = [
        ["Layer",       "Technology",               "Version",  "Notes"],
        ["Language",    "Python",                   "3.12",     "Backend and Celery workers"],
        ["API",         "FastAPI",                  "0.115+",   "Async ASGI framework"],
        ["ORM",         "SQLAlchemy",               "2.0",      "Async ORM with type annotations"],
        ["Migrations",  "Alembic",                  "latest",   "16 migration scripts"],
        ["Database",    "PostgreSQL + pgvector",    "17",       "Primary store + vector search"],
        ["Queue",       "Redis",                    "7.2",      "BSD licensed (<8.0.0)"],
        ["Task runner", "Celery",                   "5.x",      "Worker + beat scheduler"],
        ["Scheduling",  "croniter",                 "latest",   "Apache 2.0, 5-field cron"],
        ["LLM runtime", "Ollama",                   "latest",   "Local inference, no cloud"],
        ["LLM model",   "Gemma 4 / nomic-embed",   "latest",   "Recommended configuration"],
        ["Frontend",    "React",                    "18",       "Vite build toolchain"],
        ["UI library",  "shadcn/ui + Tailwind CSS", "latest",   "Civic blue design tokens"],
        ["Auth",        "JWT + bcrypt",             "—",        "6-role RBAC hierarchy"],
        ["Containers",  "Docker Compose",           "v2",       "7-service stack"],
        ["Testing",     "pytest / vitest",          "latest",   "617 backend + 36 frontend tests"],
    ]
    story.append(make_table(tech_data, [1.0*inch, 1.6*inch, 0.7*inch, 3.2*inch], styles))

    story.append(PageBreak())

    # --- 5. Installation & Quick Start ---
    story += section_header("5. Installation & Quick Start", styles, 1)
    story += section_header("Requirements", styles, 2)
    story += bullet_list([
        "Docker Desktop (Windows 10/11, macOS 13+) or Docker Engine (Linux)",
        "8+ CPU cores, 32 GB RAM, 50 GB free disk space",
        "No internet connection required after initial setup",
    ], styles)
    story += section_header("Install (Windows)", styles, 2)
    story += code_block(
        "git clone https://github.com/CivicSuite/civicrecords-ai.git\n"
        "cd civicrecords-ai\n"
        ".\\install.ps1",
        styles
    )
    story += section_header("Install (macOS / Linux)", styles, 2)
    story += code_block(
        "git clone https://github.com/CivicSuite/civicrecords-ai.git\n"
        "cd civicrecords-ai\n"
        "bash install.sh",
        styles
    )
    story += section_header("First Use", styles, 2)
    first_use = [
        "Open http://localhost:8080 in your browser",
        "Sign in with the admin credentials configured in .env",
        "Go to Sources → Add Source → enter a directory path to your documents",
        "Click Ingest Now — documents are parsed, chunked, and indexed automatically",
        "Go to Search — type a natural language query and get cited results",
    ]
    for i, step in enumerate(first_use, 1):
        story.append(P(f"<b>{i}.</b> {step}", styles["bullet"]))

    story += section_header("Key Environment Variables", styles, 2)
    env_data = [
        ["Variable",              "Description",                              "Default"],
        ["DATABASE_URL",          "PostgreSQL connection string",             "postgres://civicrecords:..."],
        ["JWT_SECRET",            "Secret key for JWT tokens",               "(must set)"],
        ["FIRST_ADMIN_EMAIL",     "Initial admin account email",             "admin@example.gov"],
        ["FIRST_ADMIN_PASSWORD",  "Initial admin account password",          "(must set)"],
        ["OLLAMA_BASE_URL",       "Ollama API endpoint",                     "http://ollama:11434"],
        ["REDIS_URL",             "Redis connection string",                 "redis://redis:6379/0"],
        ["AUDIT_RETENTION_DAYS", "Audit log retention period",              "1095 (3 years)"],
        ["SMTP_HOST",             "SMTP server for email notifications",     "(optional)"],
    ]
    story.append(make_table(env_data, [1.8*inch, 2.7*inch, 2.0*inch], styles))

    story.append(PageBreak())

    # --- 6. Database Schema ---
    story += section_header("6. Database Schema", styles, 1)
    story.append(P(
        f"CivicRecords AI uses {len(DB_TABLES)} PostgreSQL tables managed by 16 Alembic "
        "migration scripts. pgvector extension provides the embeddings column used for "
        "semantic search.",
        styles["body"]
    ))
    schema_data = [["Table", "Description"]]
    for name, desc in DB_TABLES:
        schema_data.append([name, desc])
    story.append(make_table(schema_data, [1.8*inch, 4.7*inch], styles))

    story.append(PageBreak())

    # --- 7. API Reference ---
    story += section_header("7. API Reference Summary", styles, 1)
    story.append(P(
        "The FastAPI backend exposes approximately 30 REST endpoints under the "
        "<font name='Courier'>/api/v1/</font> prefix. Full OpenAPI docs available at "
        "<font name='Courier'>http://localhost:8000/docs</font> when running.",
        styles["body"]
    ))
    api_data = [
        ["Prefix",             "Description"],
        ["/api/v1/auth",       "Login, token refresh, logout"],
        ["/api/v1/users",      "User CRUD, role management (admin only)"],
        ["/api/v1/departments","Department CRUD, access scoping"],
        ["/api/v1/requests",   "Full request lifecycle (create, status transitions, fees, messages)"],
        ["/api/v1/documents",  "Document metadata, chunk retrieval"],
        ["/api/v1/search",     "Hybrid semantic + keyword search with filters"],
        ["/api/v1/datasources","Connector CRUD, sync triggers, health status"],
        ["/api/v1/ingestion",  "Ingestion job status, error logs"],
        ["/api/v1/exemptions", "Rules CRUD, flag review, auditability dashboard"],
        ["/api/v1/onboarding", "3-phase wizard endpoints, city profile"],
        ["/api/v1/compliance", "Template render, model registry"],
        ["/api/v1/audit",      "Audit log export (CSV/JSON)"],
        ["/api/v1/analytics",  "Dashboard metrics, deadline compliance"],
        ["/health",            "Service health check"],
    ]
    story.append(make_table(api_data, [2.0*inch, 4.5*inch], styles))

    story.append(PageBreak())

    # --- 8. Connector Framework ---
    story += section_header("8. Connector Framework", styles, 1)
    story.append(P(
        "All data source connectors implement a standardized 4-method protocol. "
        "This ensures consistent behavior, testability, and future extensibility.",
        styles["body"]
    ))
    story.append(sp(4))
    story.append(ConnectorDiagram())
    story.append(P("Figure 2 — Connector Framework: protocol layer with available and planned connectors.", styles["caption"]))
    story.append(sp(6))

    conn_data = [
        ["Method",          "Description"],
        ["authenticate()",  "Validate credentials. Returns success/error with human-readable message."],
        ["discover()",      "List available records. Returns list of {id, source_path} dicts."],
        ["fetch(source_path)", "Retrieve a single record's content. Returns text or binary."],
        ["health_check()",  "Lightweight liveness check. Used by the data source card health badge."],
    ]
    story.append(make_table(conn_data, [1.8*inch, 4.7*inch], styles))
    story += section_header("Available Connectors", styles, 2)
    story += bullet_list([
        "File System — local and network directories. Most common source type.",
        "Manual Drop — watched drop folder for files exported manually by staff. "
        "Use when a system has no API. Config key: drop_path.",
        "REST API — API key, Bearer token, OAuth2 client-credentials, Basic auth. "
        "JSON/XML/CSV response formats. Page/offset/cursor pagination. data_key dotted-path extraction.",
        "ODBC — SQL databases via pyodbc. Row-as-document with SQL-injection guards. "
        "Primary key encoding/decoding with special-character support.",
    ], styles)
    story += section_header("Planned Connectors", styles, 2)
    story += bullet_list([
        "IMAP Email — Exchange and Gmail/Google Workspace integration",
        "SharePoint — Graph API with Azure AD authentication",
        "SMB/NFS — Direct network share access",
    ], styles)

    story.append(PageBreak())

    # --- 9. Sync Failure & Circuit Breaker ---
    story += section_header("9. Sync Failure & Circuit Breaker", styles, 1)
    story.append(P(
        "CivicRecords AI implements a two-layer retry model designed to distinguish transient "
        "infrastructure failures from persistent data problems, and to protect the system from "
        "cascading failures on unreliable municipal APIs.",
        styles["body"]
    ))
    story.append(sp(4))
    story.append(CircuitBreakerDiagram())
    story.append(P("Figure 3 — Health state machine: Healthy → Degraded → Circuit Open.", styles["caption"]))
    story.append(sp(6))
    story += section_header("Retry Layers", styles, 2)
    retry_data = [
        ["Layer",        "Trigger",                    "Behavior"],
        ["Task-level",   "Transient error (IOError,\nOllama timeout)",  "3 retries: 30s → 90s → 270s. Max 10 min cap."],
        ["Record-level", "Task exhaustion → sync_failure row", "Per-tick retry. Cap: N=100 OR T=90s per run."],
    ]
    story.append(make_table(retry_data, [1.2*inch, 2.0*inch, 3.3*inch], styles))
    story += section_header("Circuit Breaker Rules", styles, 2)
    story += bullet_list([
        "Circuit opens after 5 consecutive full-run failures (authenticate or discover throws, OR all fetches fail)",
        "Zero-work runs (0 records discovered, no retries) do NOT increment the counter",
        "Any single success resets the counter to 0",
        "Admin unpause triggers a 2-failure grace period threshold before returning to threshold=5",
        "health_status computed live at response time: healthy / degraded / circuit_open",
    ], styles)

    story.append(PageBreak())

    # --- 10. Security Architecture ---
    story += section_header("10. Security Architecture", styles, 1)
    sec_items = [
        ("Authentication", "JWT tokens with bcrypt password hashing. Login rate limiting. Admin-only user creation."),
        ("Authorization",  "6-role RBAC hierarchy enforced at API layer. Department-level access controls for staff."),
        ("Credentials",    "Connector credentials encrypted AES-256 at rest. Never logged, exported, or returned."),
        ("Audit Logging",  "Hash-chained audit logs — every action, every user, every timestamp. CSV/JSON export. 3-year retention default."),
        ("Human-in-the-Loop", "No auto-redaction, no auto-denial, no auto-release. All AI suggestions require human confirmation."),
        ("Data Sovereignty", "Runs entirely on local hardware. No telemetry, analytics, or crash reporting. All LLM inference via Ollama."),
        ("Prompt Injection", "Central LLM client with prompt injection sanitization. ReDoS protection on all admin-entered regex."),
        ("CJIS Compliance", "Compliance gate enforced for public safety connectors."),
        ("Macro Stripping", "VBA macros stripped from all ingested DOCX/XLSX files."),
        ("AI Labeling",     "All AI-generated content is explicitly labeled. Labels cannot be removed by staff."),
    ]
    for name, desc in sec_items:
        story.append(KeepTogether([
            P(f"<b>{name}</b>", styles["h3"]),
            P(desc, styles["body"]),
        ]))

    story.append(PageBreak())

    # --- 11. Key Engineering Decisions ---
    story += section_header("11. Key Engineering Decisions", styles, 1)
    story.append(P(
        "The following decisions constrain implementation and are each proven by an automated "
        "test. Per the canonical spec: if you want to change a decision, update the test first.",
        styles["body"]
    ))
    dec_data = [["ID", "Decision", "Rationale"]]
    for did, desc in KEY_DECISIONS:
        # Split desc at first period for rationale
        parts = desc.split(". ", 1)
        decision = parts[0] + "."
        rationale = parts[1] if len(parts) > 1 else ""
        dec_data.append([did, decision, rationale])
    story.append(make_table(dec_data, [0.85*inch, 2.8*inch, 2.85*inch], styles))

    story.append(PageBreak())

    # --- 12. Test Suite ---
    story += section_header("12. Test Suite", styles, 1)
    story.append(P(
        "CivicRecords AI ships 617 backend tests across 45+ pytest modules and 36 frontend "
        "component tests. Tests are a first-class artifact — every key engineering decision "
        "is enforced by a named test function.",
        styles["body"]
    ))
    test_data = [
        ["Module Group",          "Count", "Coverage Focus"],
        ["Auth & users",          "38",    "JWT, RBAC, rate limiting, admin-only creation"],
        ["Requests lifecycle",    "52",    "Status transitions, fees, messages, timeline"],
        ["Exemption detection",   "47",    "PII regex, Luhn, state rules, ReDoS protection"],
        ["Ingestion pipeline",    "61",    "Idempotency, dedup, concurrent update, chunk atomicity"],
        ["Connector framework",   "44",    "REST, ODBC, file system, auth methods, pagination"],
        ["Scheduler",             "28",    "Cron validation, UTC disclosure, adversarial exprs"],
        ["Sync failure / CB",     "55",    "Retry layers, circuit breaker, dismiss workflow"],
        ["Audit logging",         "19",    "Hash chain, retention, export"],
        ["Analytics & notifs",    "31",    "Dashboard metrics, SMTP delivery, templates"],
        ["Onboarding / catalog",  "22",    "3-phase wizard, gap map, systems catalog"],
        ["Compliance & models",   "16",    "Template render, model registry, CAIA"],
        ["Migrations",            "10",    "Schema correctness, backfill logic"],
        ["Frontend (vitest)",     "5",     "DataSourceCard sync button, component rendering"],
    ]
    story.append(make_table(test_data, [1.8*inch, 0.6*inch, 4.1*inch], styles))
    story.append(sp(8))
    story += section_header("Running Tests", styles, 2)
    story += code_block(
        "# Unit tests (no Docker required)\n"
        "cd backend && python -m pytest tests/ -v\n\n"
        "# Integration tests (requires Docker)\n"
        "docker compose up -d postgres redis\n"
        "DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test \\\n"
        "  python -m pytest tests/ -v\n\n"
        "# Frontend tests\n"
        "cd frontend && npm run test",
        styles
    )

    story.append(PageBreak())

    # --- 13. License ---
    story += section_header("13. License", styles, 1)
    story.append(P(
        "CivicRecords AI is released under the <b>Apache License 2.0</b>.",
        styles["body"]
    ))
    story.append(P(
        "All dependencies use permissive (MIT, Apache 2.0, BSD) or weak-copyleft "
        "(LGPL, MPL) licenses. No AGPL, SSPL, or BSL dependencies. Redis is pinned to "
        "<8.0.0 (BSD licensed; 8.x changed licensing).",
        styles["body"]
    ))
    story.append(sp(12))
    story.append(HR())
    story.append(sp(8))
    story.append(P(
        "For complete documentation, source code, and issue tracking, see:\n"
        "github.com/CivicSuite/civicrecords-ai",
        styles["center_body"]
    ))

    doc.build(story)
    print(f"  Done: {out_path}")


# ---------------------------------------------------------------------------
# Build README.pdf (shorter overview)
# ---------------------------------------------------------------------------
def build_readme_short(out_path):
    print(f"  Generating {out_path.name}...")
    styles = make_styles()
    doc = BaseDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
    )
    cb = make_page_callback("CivicRecords AI — Overview")
    frame = Frame(inch, 0.75 * inch, 6.5 * inch, 9.4 * inch, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=cb)])

    story = []

    # Title page
    story.append(sp(80))
    story.append(P("CivicRecords AI", styles["title"]))
    story.append(sp(8))
    story.append(P("Open-Source Municipal Records Request AI", styles["subtitle"]))
    story.append(sp(4))
    story.append(P(f"v1.4.1 · {date.today().strftime('%B %Y')} · Apache 2.0", styles["tagline"]))
    story.append(sp(12))
    story.append(HR())
    story.append(sp(8))
    story.append(P(
        "Open-source, locally-hosted AI that helps American cities respond to open records "
        "requests — FOIA, CORA, and all 50-state equivalents.",
        styles["center_body"]
    ))
    story.append(PageBreak())

    # What it is
    story += section_header("What Is CivicRecords AI?", styles, 1)
    story.append(P(
        "Every city in America processes open records requests. Staff manually search file "
        "shares, email archives, and databases — then review every document for exemptions "
        "before release. It is slow, error-prone, and a growing burden.",
        styles["body"]
    ))
    story.append(P(
        "CivicRecords AI is the first open-source tool for the <b>responder side</b> of "
        "open records at the municipal level. It runs entirely inside your city's network — "
        "no cloud subscriptions, no vendor lock-in, no resident data leaving the building.",
        styles["body"]
    ))
    story += section_header("What It Does", styles, 2)
    story += bullet_list([
        "Ingests city documents (PDF, DOCX, XLSX, CSV, email, HTML, text) and makes them searchable",
        "Natural language hybrid search — type plain English, get cited, ranked results",
        "Full request lifecycle management: intake → review → approval → response",
        "Automatic PII and exemption detection with human-in-the-loop confirmation",
        "Guided onboarding wizard and gap map for city IT teams",
        "Hash-chained audit logging for legal compliance",
    ], styles)
    story += section_header("What It Does Not Do", styles, 2)
    story += bullet_list([
        "Make decisions for you — every flag, every draft response, every inclusion/exclusion is a human decision",
        "Send anything automatically — nothing leaves without a human approving it",
        "Connect to the internet — everything stays inside your city's network",
    ], styles)

    story.append(PageBreak())

    # Key features
    story += section_header("Key Features", styles, 1)
    # 2-column feature table
    feat_rows = [["Feature", "Description"]]
    for name, desc in FEATURES[:10]:
        feat_rows.append([f"• {name}", desc[:120] + ("…" if len(desc) > 120 else "")])
    story.append(make_table(feat_rows, [1.5*inch, 5.0*inch], styles))
    story.append(sp(8))

    story.append(PageBreak())

    # Quick start
    story += section_header("Quick Start", styles, 1)
    story += section_header("Requirements", styles, 2)
    story += bullet_list([
        "Docker Desktop (Windows 10/11, macOS 13+) or Docker Engine (Linux)",
        "8+ CPU cores, 32 GB RAM, 50 GB free disk space",
    ], styles)
    story += section_header("Install", styles, 2)
    story += code_block(
        "# Windows\n"
        "git clone https://github.com/CivicSuite/civicrecords-ai.git\n"
        ".\\install.ps1\n\n"
        "# macOS / Linux\n"
        "git clone https://github.com/CivicSuite/civicrecords-ai.git\n"
        "bash install.sh",
        styles
    )
    story += section_header("First Use", styles, 2)
    for i, step in enumerate([
        "Open http://localhost:8080",
        "Sign in with admin credentials from .env",
        "Add Source → point to a document directory",
        "Click Ingest Now",
        "Go to Search and type a natural language query",
    ], 1):
        story.append(P(f"<b>{i}.</b> {step}", styles["bullet"]))

    story.append(PageBreak())

    # Architecture diagram
    story += section_header("Architecture", styles, 1)
    story.append(P(
        "7 Docker services — PostgreSQL 17 + pgvector, Redis 7.2, Ollama, FastAPI, "
        "Celery worker, Celery beat, nginx frontend.",
        styles["body"]
    ))
    story.append(sp(8))
    story.append(SystemArchDiagram(width=6.5*inch, height=3.2*inch))
    story.append(P("Figure 1 — CivicRecords AI runtime service topology.", styles["caption"]))
    story.append(sp(10))
    story.append(P(
        "<b>Tech stack:</b> Python 3.12, FastAPI, SQLAlchemy 2.0, React 18, shadcn/ui, "
        "Tailwind CSS, Alembic, Celery, pgvector, nomic-embed-text, Gemma 4.",
        styles["body"]
    ))

    # Embed architecture diagrams referenced by README.md
    for alt, ref in [
        ("Deployment stack — entire system runs inside Docker Compose on the city's network. "
         "No cloud, no outbound by default.",
         "docs/diagrams/deployment-stack.svg"),
        ("LLM call flow: records-ai routes through civiccore.llm to a local Ollama provider; "
         "cloud providers are opt-in only.",
         "docs/diagrams/llm-flow.svg"),
        ("Sovereignty boundary: all runtime components live inside the city's on-prem network. "
         "Connector credentials encrypted at rest with Fernet.",
         "docs/diagrams/sovereignty.svg"),
    ]:
        story.extend(embed_markdown_image_flowables(REPO_ROOT, alt, ref, styles))

    story.append(PageBreak())

    # Links
    story += section_header("Links & Documentation", styles, 1)
    links = [
        ("Source Code",         "github.com/CivicSuite/civicrecords-ai"),
        ("Full Technical Ref",  "README-FULL.pdf (in this repository)"),
        ("User Manual",         "USER-MANUAL.md / USER-MANUAL.pdf"),
        ("Canonical Spec",      "docs/UNIFIED-SPEC.md"),
        ("Issue Tracker",       "github.com/CivicSuite/civicrecords-ai/issues"),
        ("License",             "Apache License 2.0 — see LICENSE"),
        ("Installation",        "install.ps1 (Windows) / install.sh (macOS/Linux)"),
    ]
    link_data = [["Resource", "Location"]] + [[k, v] for k, v in links]
    story.append(make_table(link_data, [1.8*inch, 4.7*inch], styles))
    story.append(sp(16))
    story.append(HR())
    story.append(P(
        "CivicRecords AI is open-source software released under Apache 2.0.",
        styles["center_body"]
    ))

    doc.build(story)
    print(f"  Done: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("CivicRecords AI PDF Generator")
    print("=" * 40)

    full_pdf  = REPO_ROOT / "README-FULL.pdf"
    short_pdf = REPO_ROOT / "README.pdf"

    build_readme_full(full_pdf)
    build_readme_short(short_pdf)

    print()
    print("Generated:")
    for p in [full_pdf, short_pdf]:
        size_kb = p.stat().st_size // 1024 if p.exists() else 0
        print(f"  {p}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
