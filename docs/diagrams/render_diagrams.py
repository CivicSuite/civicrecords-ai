"""
render_diagrams.py
Generates 6 professional SVG (and PNG where available) architecture diagrams
for the CivicRecords AI project using reportlab.

Output directory: same directory as this script.
"""

import os
import traceback

from reportlab.graphics.shapes import (
    Drawing, Rect, String, Line, Group, Path, Polygon
)
from reportlab.graphics import renderSVG
from reportlab.lib import colors
from reportlab.lib.colors import HexColor, white, black

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
DARK   = HexColor("#1a3a5c")
MID    = HexColor("#2563eb")
LIGHT  = HexColor("#3b82f6")
PALE   = HexColor("#eff6ff")
GREEN  = HexColor("#166534")
GREEN2 = HexColor("#dcfce7")
AMBER  = HexColor("#92400e")
AMBER2 = HexColor("#fef3c7")
PURPLE = HexColor("#581c87")
PURPLE2= HexColor("#f3e8ff")
TEAL   = HexColor("#134e4a")
TEAL2  = HexColor("#ccfbf1")
GRAY   = HexColor("#374151")
GRAY2  = HexColor("#f3f4f6")
GRAY_BORDER = HexColor("#d1d5db")
GRAY_TEXT   = HexColor("#6b7280")
WHITE  = white
BLACK  = black
RED    = HexColor("#dc2626")
RED2   = HexColor("#fee2e2")

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def label(text, x, y, size=9, color=BLACK, bold=False, anchor="middle"):
    """Return a String shape."""
    font = "Helvetica-Bold" if bold else "Helvetica"
    return String(x, y, text, fontSize=size, fillColor=color,
                  fontName=font, textAnchor=anchor)


def box(x, y, w, h, fill=WHITE, stroke=GRAY_BORDER, strokeWidth=1, rx=4):
    """Rounded rect."""
    r = Rect(x, y, w, h, rx=rx, ry=rx,
             fillColor=fill, strokeColor=stroke, strokeWidth=strokeWidth)
    return r


def header_box(x, y, w, h, hdr_h, title, fill, hdr_fill,
               hdr_text_color=WHITE, subtitle=None, font_size=10):
    """Box with a colored header band."""
    g = Group()
    # outer box
    g.add(box(x, y, w, h, fill=fill, stroke=GRAY_BORDER, strokeWidth=1.2))
    # header rect — clip to top rounded corners via two rects trick
    g.add(Rect(x, y + h - hdr_h, w, hdr_h,
               fillColor=hdr_fill, strokeColor=None))
    # header text
    g.add(label(title, x + w/2, y + h - hdr_h + (hdr_h - font_size)/2 + 1,
                size=font_size, color=hdr_text_color, bold=True))
    if subtitle:
        g.add(label(subtitle, x + w/2,
                    y + h - hdr_h - 13,
                    size=8, color=GRAY, anchor="middle"))
    return g


def pill_label(x, y, text, bg=PALE, fg=DARK, size=8, w=None, h=16):
    """Small pill/chip label."""
    tw = w or (len(text) * size * 0.62 + 10)
    g = Group()
    g.add(Rect(x - tw/2, y - 1, tw, h, rx=4, ry=4,
               fillColor=bg, strokeColor=None))
    g.add(label(text, x, y + 3, size=size, color=fg))
    return g


def arrow(x1, y1, x2, y2, color=GRAY, width=1.5, label_text=None,
          label_color=None):
    """Simple straight arrow with arrowhead."""
    g = Group()
    g.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width))
    # arrowhead
    dx = x2 - x1
    dy = y2 - y1
    length = (dx*dx + dy*dy) ** 0.5
    if length > 0:
        ux, uy = dx/length, dy/length
        px, py = -uy, ux
        ah = 8
        aw = 4
        tip = (x2, y2)
        base_x = x2 - ux * ah
        base_y = y2 - uy * ah
        pts = [
            tip[0], tip[1],
            base_x + px*aw, base_y + py*aw,
            base_x - px*aw, base_y - py*aw,
        ]
        g.add(Polygon(pts, fillColor=color, strokeColor=color, strokeWidth=0))
    if label_text:
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        lc = label_color or color
        g.add(label(label_text, mx + 4, my + 2, size=7, color=lc, anchor="start"))
    return g


def dashed_line(x1, y1, x2, y2, color=GRAY_BORDER, width=1):
    ln = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width,
              strokeDashArray=[4, 3])
    return ln


def write_diagram(drawing, name):
    path_svg = os.path.join(OUT_DIR, name + ".svg")
    try:
        renderSVG.drawToFile(drawing, path_svg)
        print(f"Generated: {path_svg}")
    except Exception as e:
        print(f"ERROR writing SVG {name}: {e}")
        traceback.print_exc()
    # Try PNG
    try:
        from reportlab.graphics import renderPM
        path_png = os.path.join(OUT_DIR, name + ".png")
        renderPM.drawToFile(drawing, path_png, fmt="PNG", dpi=144)
        print(f"Generated: {path_png}")
    except Exception as e:
        print(f"  (PNG skipped for {name}: {e})")


# ===========================================================================
# 1. component.svg — Layered architecture diagram
# ===========================================================================

def make_component():
    W, H = 920, 780
    d = Drawing(W, H)
    d.add(Rect(0, 0, W, H, fillColor=WHITE, strokeColor=None))

    # Title
    d.add(label("CivicRecords AI — System Components (v1.2)", W/2, H - 24,
                size=14, color=DARK, bold=True))

    layers = [
        # (title, items, header_color, bg_color, y_top)
        ("Browser Layer (Staff; optional Public surface when PORTAL_MODE=public)",
         ["Search UI", "Request Tracker", "Data Sources",
          "Admin Panel", "Exemption Review", "Audit Log",
          "Public Landing (opt)", "Resident Register (opt)", "Public Submit (opt)"],
         DARK, PALE),
        ("Application Server",
         ["JWT Auth", "Dept Scoping", "Portal Mode API",
          "Search API", "Request API", "Public Router (opt)",
          "Sources API (at-rest enc.)", "Exemption Engine", "Admin API",
          "Notifications", "Audit API", "LLM Client", "Sync Runner"],
         GREEN, GREEN2),
        ("Workers",
         ["Celery Worker", "Celery Beat"],
         AMBER, AMBER2),
        ("Data Layer",
         ["PostgreSQL 17 + pgvector", "Redis 7.2"],
         PURPLE, PURPLE2),
        ("AI Layer",
         ["Ollama (Local LLM)", "Tesseract OCR"],
         TEAL, TEAL2),
        ("City Data Sources",
         ["File System", "Direct Upload", "REST API", "ODBC/SQL"],
         GRAY, GRAY2),
    ]

    LX = 30
    LW = W - 60
    HDR = 26
    ITEM_H = 28
    ITEM_PAD = 8
    LAYER_GAP = 12
    ARROW_MARGIN = 8

    # compute heights per layer
    def layer_height(items):
        per_row = max(1, LW // 140)
        rows = -(-len(items) // per_row)
        return HDR + rows * (ITEM_H + 4) + 12

    total_content = sum(layer_height(l[1]) for l in layers) + LAYER_GAP * len(layers)
    y_start = H - 48 - total_content

    layer_boxes = []  # (x, y, w, h) for arrows
    y = y_start
    for title, items, hdr_col, bg_col in layers:
        lh = layer_height(items)
        ly = y
        # outer box
        d.add(box(LX, ly, LW, lh, fill=bg_col, stroke=hdr_col, strokeWidth=1.5))
        # header
        d.add(Rect(LX, ly + lh - HDR, LW, HDR,
                   fillColor=hdr_col, strokeColor=None))
        d.add(label(title, LX + LW/2, ly + lh - HDR + 8,
                    size=11, color=WHITE, bold=True))

        # items
        per_row = max(1, LW // 140)
        item_w = (LW - (per_row + 1) * ITEM_PAD) / per_row
        for i, item in enumerate(items):
            col = i % per_row
            row = i // per_row
            ix = LX + ITEM_PAD + col * (item_w + ITEM_PAD)
            iy = ly + lh - HDR - 8 - (row + 1) * (ITEM_H + 4)
            d.add(box(ix, iy, item_w, ITEM_H,
                      fill=WHITE, stroke=GRAY_BORDER, strokeWidth=0.8, rx=3))
            d.add(label(item, ix + item_w/2, iy + 9,
                        size=8.5, color=DARK, anchor="middle"))

        layer_boxes.append((LX, ly, LW, lh))
        y += lh + LAYER_GAP

    # Arrows between layers
    def mid_right(box_tuple):
        x, y, w, h = box_tuple
        return x + w, y + h/2

    def mid_left(box_tuple):
        x, y, w, h = box_tuple
        return x, y + h/2

    arrow_pairs = [
        (0, 1, "HTTP/REST"),
        (1, 3, "SQL/Cache"),
        (2, 3, "SQL/Cache"),
        (2, 4, "Embed/OCR"),
        (5, 1, "Ingest"),
    ]
    arrow_x_offsets = [60, 120, 180, 240, 300]
    for idx, (src, dst, lbl) in enumerate(arrow_pairs):
        sx, sy, sw, sh = layer_boxes[src]
        dx, dy, dw, dh = layer_boxes[dst]
        ax = LX + LW + 20 + idx * 0  # draw on right side staggered
        # simple vertical arrow from bottom of src to top of dst
        ax = LX + 40 + idx * 30
        top_src = layer_boxes[src][1] + layer_boxes[src][3] / 2
        # use bottom of upper box to top of lower box
        if src < dst:
            y1 = layer_boxes[src][1]  # bottom of src box
            y2 = layer_boxes[dst][1] + layer_boxes[dst][3]  # top of dst box
        else:
            y1 = layer_boxes[src][1] + layer_boxes[src][3]
            y2 = layer_boxes[dst][1]
        # skip drawing internal arrows for clean look; just annotate
    # Draw clean side annotations
    annots = [
        ("Browser → API", LX + LW + 6, layer_boxes[0][1] + layer_boxes[0][3]/2 - 10),
        ("API → Data",    LX + LW + 6, layer_boxes[1][1] + layer_boxes[1][3]/2 - 10),
        ("Workers → Data/AI", LX + LW + 6, layer_boxes[2][1] + 10),
        ("Sources → API", LX + LW + 6, layer_boxes[5][1] + layer_boxes[5][3]/2 - 10),
    ]
    # draw arrows on right margin
    right_x = LX + LW + 4
    arrow_defs = [
        (layer_boxes[0], layer_boxes[1], "HTTP/REST", MID),
        (layer_boxes[1], layer_boxes[3], "SQL / Cache", PURPLE),
        (layer_boxes[2], layer_boxes[3], "SQL / Cache", PURPLE),
        (layer_boxes[2], layer_boxes[4], "Embed / OCR", TEAL),
        (layer_boxes[5], layer_boxes[1], "Ingest", GREEN),
    ]
    ax_positions = [right_x + 4, right_x + 44, right_x + 84,
                    right_x + 124, right_x + 164]
    # Use left side for source→dest arrows
    for i, (sb, db, lbl_text, col) in enumerate(arrow_defs):
        ax_pos = LX - 16 - i * 0  # stack on left
        ax_pos = 14
        sy1 = sb[1]   # bottom y of source (lowest y)
        sy2 = db[1] + db[3]  # top y of dest
        if sy1 > sy2:
            sy1, sy2 = sy2, sy1
        # vertical line on left margin
    # Simplified: draw arrows as horizontal stubs on right of drawing
    # Actually: draw arrows as descending lines at staggered x on left margin
    left_xs = [14, 20, 26, 20, 14]
    for i, (sb, db, lbl_text, col) in enumerate(arrow_defs):
        ax_pos = left_xs[i]
        # source box mid-y and dest box mid-y
        s_mid_y = sb[1] + sb[3] / 2
        d_mid_y = db[1] + db[3] / 2
        # horizontal stub out of source left
        d.add(Line(LX, s_mid_y, LX - ax_pos, s_mid_y,
                   strokeColor=col, strokeWidth=1.2))
        # vertical segment
        d.add(Line(LX - ax_pos, s_mid_y, LX - ax_pos, d_mid_y,
                   strokeColor=col, strokeWidth=1.2))
        # stub back to dest
        d.add(arrow(LX - ax_pos, d_mid_y, LX, d_mid_y,
                    color=col, width=1.2, label_text=None))
        # label at midpoint of vertical segment
        mid_y = (s_mid_y + d_mid_y) / 2
        d.add(label(lbl_text, LX - ax_pos - 2, mid_y,
                    size=6.5, color=col, anchor="end"))

    return d


# ===========================================================================
# 2. class.svg — UML class diagram
# ===========================================================================

def make_class():
    W, H = 920, 720
    d = Drawing(W, H)
    d.add(Rect(0, 0, W, H, fillColor=WHITE, strokeColor=None))
    d.add(label("CivicRecords AI — Domain Class Diagram", W/2, H - 24,
                size=14, color=DARK, bold=True))

    HDR = 22
    ROW = 14
    PAD = 8

    def uml_class(x, y, w, name, fields, methods=None, hdr_color=MID):
        methods = methods or []
        total_rows = len(fields) + (1 if methods else 0) + len(methods)
        h = HDR + PAD + total_rows * ROW + PAD
        g = Group()
        g.add(box(x, y, w, h, fill=WHITE, stroke=GRAY_BORDER, strokeWidth=1.2))
        # header
        g.add(Rect(x, y + h - HDR, w, HDR,
                   fillColor=hdr_color, strokeColor=None))
        g.add(label(name, x + w/2, y + h - HDR + 6,
                    size=9.5, color=WHITE, bold=True))
        # fields
        fy = y + h - HDR - PAD - ROW
        for f in fields:
            g.add(label(f, x + 6, fy, size=7.5, color=DARK, anchor="start"))
            fy -= ROW
        # divider before methods
        if methods:
            g.add(Line(x, fy + ROW - 2, x + w, fy + ROW - 2,
                       strokeColor=GRAY_BORDER, strokeWidth=0.8))
            for m in methods:
                g.add(label(m, x + 6, fy, size=7.5, color=GRAY, anchor="start"))
                fy -= ROW
        return g, x, y, w, h

    classes = [
        # (name, fields, methods, hdr_color, grid_col, grid_row)
        ("DataSource",
         ["+ id: UUID", "+ name: str", "+ source_type: str",
          "+ dept_id: UUID", "+ config: JSON", "+ is_active: bool",
          "+ circuit_state: str", "+ failure_count: int"],
         ["+ discover()", "+ fetch()"],
         MID, 0, 0),

        ("SyncFailure",
         ["+ id: UUID", "+ source_id: UUID", "+ error_msg: str",
          "+ failed_at: datetime", "+ dismissed: bool"],
         [],
         RED, 1, 0),

        ("SyncRunLog",
         ["+ id: UUID", "+ source_id: UUID", "+ started_at: datetime",
          "+ finished_at: datetime", "+ docs_synced: int",
          "+ status: str"],
         [],
         AMBER, 2, 0),

        ("Document",
         ["+ id: UUID", "+ source_id: UUID", "+ title: str",
          "+ content: text", "+ file_path: str",
          "+ content_hash: str", "+ dept_id: UUID",
          "+ synced_at: datetime"],
         [],
         DARK, 0, 1),

        ("Chunk",
         ["+ id: UUID", "+ doc_id: UUID", "+ text: str",
          "+ embedding: vector(384)", "+ chunk_index: int"],
         [],
         TEAL, 1, 1),

        ("Request",
         ["+ id: UUID", "+ requester_id: UUID", "+ dept_id: UUID",
          "+ subject: str", "+ status: str",
          "+ due_date: date", "+ created_at: datetime"],
         [],
         GREEN, 2, 1),

        ("ExemptionFlag",
         ["+ id: UUID", "+ request_id: UUID", "+ chunk_id: UUID",
          "+ exemption_code: str", "+ rationale: str",
          "+ reviewed: bool"],
         [],
         PURPLE, 0, 2),

        ("User",
         ["+ id: UUID", "+ email: str", "+ role: str",
          "+ dept_id: UUID", "+ is_active: bool"],
         [],
         MID, 1, 2),

        ("Department",
         ["+ id: UUID", "+ name: str", "+ code: str"],
         [],
         DARK, 2, 2),

        ("AuditLog",
         ["+ id: UUID", "+ user_id: UUID", "+ action: str",
          "+ entity: str", "+ entity_id: UUID",
          "+ timestamp: datetime", "+ detail: JSON"],
         [],
         GRAY, 0, 3),
    ]

    COL_W = 270
    COL_GAP = 30
    ROW_GAP = 28
    START_X = 30
    START_Y = H - 60

    positions = {}
    for name, fields, methods, hdr_color, gc, gr in classes:
        cw = COL_W
        x = START_X + gc * (COL_W + COL_GAP)
        # estimate height
        total_rows = len(fields) + (1 if methods else 0) + len(methods)
        ch = HDR + PAD + total_rows * ROW + PAD
        y = START_Y - gr * (180 + ROW_GAP) - ch

        g, cx, cy, cw2, ch2 = uml_class(x, y, cw, name, fields, methods, hdr_color)
        d.add(g)
        positions[name] = (x, y, cw, ch)

    # Relationships
    def center_bottom(name):
        x, y, w, h = positions[name]
        return x + w/2, y

    def center_top(name):
        x, y, w, h = positions[name]
        return x + w/2, y + h

    def right_mid(name):
        x, y, w, h = positions[name]
        return x + w, y + h/2

    def left_mid(name):
        x, y, w, h = positions[name]
        return x, y + h/2

    rels = [
        ("DataSource", "SyncFailure", "1..*", MID),
        ("DataSource", "SyncRunLog", "1..*", MID),
        ("DataSource", "Document", "1..*", DARK),
        ("Document", "Chunk", "1..*", TEAL),
        ("Request", "ExemptionFlag", "0..*", PURPLE),
        ("User", "Department", "*.1", GREEN),
        ("User", "AuditLog", "1..*", GRAY),
    ]

    for src, dst, card, col in rels:
        sx, sy, sw, sh = positions[src]
        dx, dy, dw, dh = positions[dst]
        # pick closest edges
        scx = sx + sw/2
        scy = sy + sh/2
        dcx = dx + dw/2
        dcy = dy + dh/2
        # horizontal or vertical based on position
        if abs(scx - dcx) > abs(scy - dcy):
            # horizontal connector
            if scx < dcx:
                x1, y1 = sx + sw, scy
                x2, y2 = dx, dcy
            else:
                x1, y1 = sx, scy
                x2, y2 = dx + dw, dcy
        else:
            if scy > dcy:
                x1, y1 = scx, sy
                x2, y2 = dcx, dy + dh
            else:
                x1, y1 = scx, sy + sh
                x2, y2 = dcx, dy
        d.add(arrow(x1, y1, x2, y2, color=col, width=1.2, label_text=card,
                    label_color=col))

    return d


# ===========================================================================
# 3. sequence-ingestion.svg — Ingestion pipeline sequence diagram
# ===========================================================================

def make_sequence_ingestion():
    W, H = 920, 680
    d = Drawing(W, H)
    d.add(Rect(0, 0, W, H, fillColor=WHITE, strokeColor=None))
    d.add(label("CivicRecords AI — Ingestion Pipeline Sequence", W/2, H - 24,
                size=14, color=DARK, bold=True))

    participants = [
        ("Celery Beat",      AMBER,  AMBER2),
        ("Celery Worker",    GREEN,  GREEN2),
        ("Sync Runner",      MID,    PALE),
        ("Connector",        TEAL,   TEAL2),
        ("Ingestion Pipeline", DARK, GRAY2),
        ("PostgreSQL",       PURPLE, PURPLE2),
        ("Ollama",           GRAY,   GRAY2),
    ]

    N = len(participants)
    TOP_Y = H - 55
    BOX_H = 36
    BOX_W = 108
    total_w = W - 60
    col_w = total_w / N
    xs = [30 + col_w * i + col_w/2 for i in range(N)]

    # Draw participant boxes
    for i, (name, hdr, bg) in enumerate(participants):
        bx = xs[i] - BOX_W/2
        by = TOP_Y - BOX_H
        d.add(box(bx, by, BOX_W, BOX_H, fill=bg, stroke=hdr, strokeWidth=1.5))
        d.add(label(name, xs[i], by + 12,
                    size=8, color=hdr, bold=True, anchor="middle"))

    # Lifelines
    LIFE_TOP = TOP_Y - BOX_H
    LIFE_BOT = 30
    for i, (name, hdr, bg) in enumerate(participants):
        d.add(dashed_line(xs[i], LIFE_TOP, xs[i], LIFE_BOT,
                          color=GRAY_BORDER, width=1))

    # Messages
    steps = [
        # (from_idx, to_idx, label, y, style, return_label)
        (0, 1, "trigger sync tasks",     620, "solid", None),
        (1, 2, "run_sync(source_id)",    590, "solid", None),
        (2, 3, "authenticate()",         560, "solid", None),
        (3, 2, "auth_token",             545, "dashed", None),
        (2, 3, "discover()",             520, "solid", None),
        (3, 2, "doc_list[]",             505, "dashed", None),
        (2, 3, "fetch(doc_id)",          480, "solid", None),
        (3, 2, "raw_content",            465, "dashed", None),
        (2, 4, "ingest(doc)",            440, "solid", None),
        (4, 5, "upsert document",        415, "solid", None),
        (5, 4, "doc_id",                 400, "dashed", None),
        (4, 5, "upsert chunks",          380, "solid", None),
        (4, 6, "embed(chunk_text)",      355, "solid", None),
        (6, 4, "vector[384]",            340, "dashed", None),
        (4, 5, "store embeddings",       320, "solid", None),
        (5, 4, "OK",                     305, "dashed", None),
        (4, 2, "pipeline_result",        280, "dashed", None),
        (2, 5, "log SyncRunLog",         255, "solid", None),
        (2, 2, "circuit_breaker check",  230, "self",  None),
        (2, 1, "done / exception",       205, "dashed", None),
    ]

    for fr, to, msg, y, style, ret in steps:
        x1, x2 = xs[fr], xs[to]
        col = MID if style == "solid" else GRAY_BORDER
        col = TEAL if style == "self" else col

        if style == "self":
            # self-call loop
            loop_w = 40
            loop_h = 18
            d.add(Line(xs[fr], y + loop_h, xs[fr] + loop_w, y + loop_h,
                       strokeColor=col, strokeWidth=1.2))
            d.add(Line(xs[fr] + loop_w, y + loop_h, xs[fr] + loop_w, y,
                       strokeColor=col, strokeWidth=1.2))
            d.add(arrow(xs[fr] + loop_w, y, xs[fr], y,
                        color=col, width=1.2))
            d.add(label(msg, xs[fr] + loop_w + 4, y + 5,
                        size=7.5, color=col, anchor="start"))
        else:
            if style == "dashed":
                d.add(Line(x1, y, x2, y, strokeColor=col,
                           strokeWidth=1, strokeDashArray=[4, 3]))
                # small arrowhead
                d.add(arrow(x1 if x1 > x2 else x2,
                            y,
                            x2 if x1 > x2 else x1,
                            y, color=col, width=1))
            else:
                d.add(arrow(x1, y, x2, y, color=MID, width=1.5))
            # label
            lx = (x1 + x2) / 2
            d.add(label(msg, lx, y + 4, size=7.5, color=DARK, anchor="middle"))

    # Activation boxes on Sync Runner lifeline
    act_pairs = [(590, 205)]
    for top_y, bot_y in act_pairs:
        d.add(Rect(xs[2] - 5, bot_y, 10, top_y - bot_y,
                   fillColor=PALE, strokeColor=MID, strokeWidth=1))

    # Legend
    leg_x = 30
    leg_y = 50
    d.add(label("Legend:", leg_x, leg_y + 20, size=8, color=GRAY, bold=True, anchor="start"))
    d.add(Line(leg_x, leg_y + 10, leg_x + 30, leg_y + 10,
               strokeColor=MID, strokeWidth=1.5))
    d.add(label("sync call", leg_x + 34, leg_y + 10, size=7.5, color=DARK, anchor="start"))
    d.add(Line(leg_x + 90, leg_y + 10, leg_x + 120, leg_y + 10,
               strokeColor=GRAY_BORDER, strokeWidth=1, strokeDashArray=[4, 3]))
    d.add(label("return", leg_x + 124, leg_y + 10, size=7.5, color=DARK, anchor="start"))

    return d


# ===========================================================================
# 4. deployment.svg — Docker deployment topology
# ===========================================================================

def make_deployment():
    W, H = 920, 640
    d = Drawing(W, H)
    d.add(Rect(0, 0, W, H, fillColor=WHITE, strokeColor=None))
    d.add(label("CivicRecords AI — Docker Deployment Topology", W/2, H - 24,
                size=14, color=DARK, bold=True))

    # Browser node (external)
    bw, bh = 120, 50
    bx, by = 30, H - 100
    d.add(box(bx, by, bw, bh, fill=PALE, stroke=DARK, strokeWidth=1.5, rx=6))
    d.add(label("Browser", bx + bw/2, by + 18, size=10, color=DARK, bold=True))
    d.add(label("(User)", bx + bw/2, by + 5, size=8, color=GRAY))

    # City Server outer box
    CSX, CSY, CSW, CSH = 30, 40, W - 60, H - 150
    d.add(box(CSX, CSY, CSW, CSH, fill=HexColor("#f8fafc"),
              stroke=DARK, strokeWidth=2, rx=8))
    d.add(label("City Server", CSX + 12, CSY + CSH - 18,
                size=11, color=DARK, bold=True, anchor="start"))

    # Docker Compose inner box
    DCX = CSX + 20
    DCY = CSY + 20
    DCW = CSW - 40
    DCH = CSH - 50
    d.add(box(DCX, DCY, DCW, DCH, fill=HexColor("#f0f9ff"),
              stroke=MID, strokeWidth=1.5, rx=6))
    d.add(label("Docker Compose Network (civicrecords-net)",
                DCX + 12, DCY + DCH - 16,
                size=9.5, color=MID, bold=True, anchor="start"))

    # Service boxes layout
    # Row 1: frontend, api
    # Row 2: worker, beat, ollama
    # Row 3: postgres, redis
    services = {
        "frontend\n(:8080)": (DCX + 30,  DCY + DCH - 90,  130, 52, HexColor("#0ea5e9"), HexColor("#e0f2fe")),
        "api\n(:8000)":      (DCX + 190, DCY + DCH - 90,  130, 52, GREEN,               GREEN2),
        "worker":            (DCX + 30,  DCY + DCH - 180, 130, 52, AMBER,               AMBER2),
        "beat":              (DCX + 190, DCY + DCH - 180, 130, 52, AMBER,               AMBER2),
        "ollama\n(:11434)":  (DCX + 370, DCY + DCH - 180, 130, 52, TEAL,                TEAL2),
        "postgres\n(:5432)": (DCX + 30,  DCY + DCH - 270, 130, 52, PURPLE,              PURPLE2),
        "redis\n(:6379)":    (DCX + 190, DCY + DCH - 270, 130, 52, RED,                 RED2),
    }

    svc_centers = {}
    for svc_name, (sx, sy, sw, sh, hc, bg) in services.items():
        d.add(box(sx, sy, sw, sh, fill=bg, stroke=hc, strokeWidth=1.5, rx=6))
        short = svc_name.split("\n")
        ty = sy + sh/2 + (6 if len(short) == 2 else 3)
        d.add(label(short[0], sx + sw/2, ty, size=9, color=hc, bold=True))
        if len(short) == 2:
            d.add(label(short[1], sx + sw/2, ty - 13, size=7.5, color=hc))
        svc_centers[svc_name] = (sx + sw/2, sy + sh/2, sx, sy, sw, sh)

    def svc_edge(name, side="right"):
        cx, cy, sx, sy, sw, sh = svc_centers[name]
        if side == "right": return sx + sw, cy
        if side == "left":  return sx, cy
        if side == "top":   return cx, sy + sh
        if side == "bottom": return cx, sy

    # Connections
    conn_defs = [
        ("frontend\n(:8080)", "right", "api\n(:8000)",     "left",  "HTTP", MID),
        ("api\n(:8000)",      "bottom","postgres\n(:5432)", "top",   "SQL",  PURPLE),
        ("api\n(:8000)",      "right", "ollama\n(:11434)",  "left",  "HTTP", TEAL),
        ("worker",            "bottom","postgres\n(:5432)", "top",   "SQL",  PURPLE),
        ("worker",            "right", "redis\n(:6379)",    "left",  "Queue",RED),
        ("worker",            "right", "ollama\n(:11434)",  "left",  "HTTP", TEAL),
        ("beat",              "right", "redis\n(:6379)",    "left",  "Sched",RED),
        ("api\n(:8000)",      "bottom","redis\n(:6379)",    "top",   "Cache",RED),
    ]

    drawn_lines = set()
    for src, src_side, dst, dst_side, lbl_text, col in conn_defs:
        x1, y1 = svc_edge(src, src_side)
        x2, y2 = svc_edge(dst, dst_side)
        key = tuple(sorted([src, dst]))
        # Draw orthogonal lines
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        d.add(Line(x1, y1, x2, y2, strokeColor=col,
                   strokeWidth=1.2, strokeDashArray=None))
        d.add(label(lbl_text, mid_x + 4, mid_y + 3,
                    size=7, color=col, anchor="start"))

    # Browser → frontend arrow
    bfx = bx + bw
    bfy = by + bh/2
    fe_cx = svc_centers["frontend\n(:8080)"][2]  # left x
    fe_cy = svc_centers["frontend\n(:8080)"][1]  # cy
    # need to go through the box border
    fe_lx = svc_centers["frontend\n(:8080)"][2]  # sx
    d.add(arrow(bfx, bfy, fe_lx, fe_cy, color=DARK, width=1.5,
                label_text="HTTPS :80"))

    return d


# ===========================================================================
# 5. sequence-request.svg — Records request lifecycle
# ===========================================================================

def make_sequence_request():
    W, H = 920, 700
    d = Drawing(W, H)
    d.add(Rect(0, 0, W, H, fillColor=WHITE, strokeColor=None))
    d.add(label("CivicRecords AI — Records Request Lifecycle", W/2, H - 24,
                size=14, color=DARK, bold=True))

    participants = [
        ("Requester",       HexColor("#0369a1"), HexColor("#e0f2fe")),
        ("Clerk",           GREEN,               GREEN2),
        ("CivicRecords AI", MID,                 PALE),
        ("Local LLM",       TEAL,                TEAL2),
        ("Supervisor",      PURPLE,              PURPLE2),
        ("Audit Log",       GRAY,                GRAY2),
    ]

    N = len(participants)
    TOP_Y = H - 55
    BOX_H = 36
    BOX_W = 118
    total_w = W - 60
    col_w = total_w / N
    xs = [30 + col_w * i + col_w/2 for i in range(N)]

    for i, (name, hdr, bg) in enumerate(participants):
        bx = xs[i] - BOX_W/2
        by = TOP_Y - BOX_H
        d.add(box(bx, by, BOX_W, BOX_H, fill=bg, stroke=hdr, strokeWidth=1.5))
        d.add(label(name, xs[i], by + 12,
                    size=8.5, color=hdr, bold=True, anchor="middle"))

    LIFE_TOP = TOP_Y - BOX_H
    LIFE_BOT = 30
    for i in range(N):
        d.add(dashed_line(xs[i], LIFE_TOP, xs[i], LIFE_BOT,
                          color=GRAY_BORDER, width=1))

    # Activation on CivicRecords AI
    d.add(Rect(xs[2] - 5, 80, 10, 540,
               fillColor=PALE, strokeColor=MID, strokeWidth=1))

    steps = [
        (0, 2, "submit_request(subject, dept)", 615, "solid"),
        (2, 5, "log(request.created)",          595, "solid"),
        (2, 2, "search documents (vector)",     575, "self"),
        (2, 3, "embed(query)",                  555, "solid"),
        (3, 2, "query_vector",                  540, "dashed"),
        (2, 2, "rank chunks by similarity",     520, "self"),
        (2, 3, "flag_exemptions(chunks)",       500, "solid"),
        (3, 2, "exemption_flags[]",             485, "dashed"),
        (2, 1, "review_flags(request_id)",      460, "solid"),
        (1, 2, "approve / override flags",      440, "dashed"),
        (2, 5, "log(flags.reviewed)",           420, "solid"),
        (2, 3, "generate_response_letter()",    400, "solid"),
        (3, 2, "draft_letter",                  385, "dashed"),
        (2, 1, "present draft + redactions",    365, "solid"),
        (1, 2, "submit_for_review(letter)",     345, "dashed"),
        (1, 4, "notify supervisor",             325, "solid"),
        (4, 1, "approve / request revision",    305, "dashed"),
        (1, 2, "update status = FULFILLED",     285, "solid"),
        (2, 5, "log(request.fulfilled)",        265, "solid"),
        (2, 0, "notify requester",              245, "solid"),
        (0, 2, "acknowledge receipt",           225, "dashed"),
    ]

    for fr, to, msg, y, style in steps:
        x1, x2 = xs[fr], xs[to]
        if style == "self":
            loop_w = 38
            loop_h = 16
            col = TEAL
            d.add(Line(xs[fr], y + loop_h, xs[fr] + loop_w, y + loop_h,
                       strokeColor=col, strokeWidth=1.2))
            d.add(Line(xs[fr] + loop_w, y + loop_h, xs[fr] + loop_w, y,
                       strokeColor=col, strokeWidth=1.2))
            d.add(arrow(xs[fr] + loop_w, y, xs[fr], y,
                        color=col, width=1.2))
            d.add(label(msg, xs[fr] + loop_w + 4, y + 4,
                        size=7, color=col, anchor="start"))
        elif style == "dashed":
            d.add(Line(x1, y, x2, y, strokeColor=GRAY_BORDER,
                       strokeWidth=1, strokeDashArray=[4, 3]))
            if x1 > x2:
                d.add(arrow(x1, y, x2, y, color=GRAY, width=1))
            else:
                d.add(arrow(x2, y, x1, y, color=GRAY, width=1))
            lx = (x1 + x2) / 2
            d.add(label(msg, lx, y + 4, size=7, color=GRAY, anchor="middle"))
        else:
            d.add(arrow(x1, y, x2, y, color=MID, width=1.4))
            lx = (x1 + x2) / 2
            d.add(label(msg, lx, y + 4, size=7, color=DARK, anchor="middle"))

    return d


# ===========================================================================
# 6. sync-failure.svg — State machine
# ===========================================================================

def make_sync_failure():
    W, H = 920, 600
    d = Drawing(W, H)
    d.add(Rect(0, 0, W, H, fillColor=WHITE, strokeColor=None))
    d.add(label("CivicRecords AI — Sync Failure State Machine", W/2, H - 24,
                size=14, color=DARK, bold=True))

    STATE_W = 140
    STATE_H = 52
    CORNER = 8

    states = {
        "Healthy":           (W/2 - STATE_W/2,       H - 120,              GREEN,   GREEN2),
        "Degraded":          (W/2 - STATE_W/2,       H - 240,              AMBER,   AMBER2),
        "CircuitOpen":       (W/2 - STATE_W/2 - 220, H - 360,              RED,     RED2),
        "PermanentlyFailed": (W/2 - STATE_W/2 + 220, H - 360,              GRAY,    GRAY2),
        "Dismissed":         (W/2 - STATE_W/2,       H - 480,              MID,     PALE),
    }

    def state_center(name):
        x, y, hc, bg = states[name]
        return x + STATE_W/2, y + STATE_H/2

    def state_edge(name, side):
        x, y, hc, bg = states[name]
        cx, cy = x + STATE_W/2, y + STATE_H/2
        if side == "top":    return cx, y + STATE_H
        if side == "bottom": return cx, y
        if side == "left":   return x, cy
        if side == "right":  return x + STATE_W, cy

    # Draw states
    for sname, (sx, sy, hc, bg) in states.items():
        d.add(box(sx, sy, STATE_W, STATE_H, fill=bg, stroke=hc,
                  strokeWidth=2, rx=CORNER))
        d.add(Rect(sx, sy + STATE_H - 22, STATE_W, 22,
                   fillColor=hc, strokeColor=None,
                   rx=CORNER))
        d.add(label(sname, sx + STATE_W/2, sy + STATE_H - 14,
                    size=9, color=WHITE, bold=True))
        # sub-label
        sub = {
            "Healthy":           "failure_count = 0",
            "Degraded":          "1 ≤ failures < 5",
            "CircuitOpen":       "failures ≥ 5",
            "PermanentlyFailed": "failures ≥ 10",
            "Dismissed":         "admin dismissed",
        }.get(sname, "")
        d.add(label(sub, sx + STATE_W/2, sy + 6,
                    size=7.5, color=hc, anchor="middle"))

    # Start indicator
    hx, hy, _, _ = states["Healthy"]
    d.add(arrow(hx + STATE_W/2 - 30, hy - 20, hx + STATE_W/2, hy,
                color=DARK, width=2))
    d.add(Rect(hx + STATE_W/2 - 38, hy - 28, 16, 16, rx=8,
               fillColor=DARK, strokeColor=None))
    d.add(label("Start", hx + STATE_W/2 - 30, hy - 14,
                size=7.5, color=DARK, anchor="end"))

    transitions = [
        ("Healthy",  "top",    "Degraded",          "bottom", "sync error",    AMBER),
        ("Degraded", "bottom", "Healthy",            "top",    "sync success",  GREEN),
        ("Degraded", "left",   "CircuitOpen",        "right",  "failures ≥ 5", RED),
        ("Degraded", "right",  "PermanentlyFailed",  "left",   "failures ≥ 10",GRAY),
        ("CircuitOpen","top",  "Dismissed",          "left",   "admin dismiss", MID),
        ("PermanentlyFailed","top","Dismissed",      "right",  "admin dismiss", MID),
        ("CircuitOpen","bottom","Degraded",          "right",  "cooldown reset",AMBER),
    ]

    for src, ss, dst, ds, lbl_text, col in transitions:
        x1, y1 = state_edge(src, ss)
        x2, y2 = state_edge(dst, ds)
        # offset parallel arrows slightly
        ox = 6 if (src, dst) in [("Healthy","Degraded"),
                                  ("Degraded","Healthy")] else 0
        d.add(arrow(x1 + ox, y1, x2 + ox, y2, color=col, width=1.5,
                    label_text=lbl_text, label_color=col))

    # Legend
    legend_items = [
        ("Healthy",          GREEN,  GREEN2),
        ("Degraded",         AMBER,  AMBER2),
        ("Circuit Open",     RED,    RED2),
        ("Perm. Failed",     GRAY,   GRAY2),
        ("Dismissed",        MID,    PALE),
    ]
    lx, ly = 30, 90
    d.add(label("States:", lx, ly + 10, size=8, color=GRAY, bold=True, anchor="start"))
    for i, (name, hc, bg) in enumerate(legend_items):
        bx = lx + i * 110
        d.add(box(bx, ly - 14, 100, 20, fill=bg, stroke=hc, strokeWidth=1, rx=3))
        d.add(label(name, bx + 50, ly - 6, size=7.5, color=hc))

    return d


# ===========================================================================
# Main
# ===========================================================================

def main():
    diagrams = [
        ("component",          make_component),
        ("class",              make_class),
        ("sequence-ingestion", make_sequence_ingestion),
        ("deployment",         make_deployment),
        ("sequence-request",   make_sequence_request),
        ("sync-failure",       make_sync_failure),
    ]

    print(f"Output directory: {OUT_DIR}")
    print("-" * 60)

    for name, fn in diagrams:
        try:
            drawing = fn()
            write_diagram(drawing, name)
        except Exception as e:
            print(f"ERROR in {name}: {e}")
            traceback.print_exc()

    print("-" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
