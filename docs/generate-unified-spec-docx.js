const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak,
  TableOfContents, ImageRun
} = require("docx");

// ── Image embedding helper ──────────────────────────────────────────────────
// Resolve markdown-style image src relative to the docs/ directory and embed
// as an ImageRun paragraph. Prefer .png variants of .svg sources because the
// docx lib does not natively render SVG.
function imageParagraph(src, alt) {
  let resolved = path.resolve(__dirname, src);
  if (resolved.toLowerCase().endsWith(".svg")) {
    const pngVariant = resolved.replace(/\.svg$/i, ".png");
    if (fs.existsSync(pngVariant)) resolved = pngVariant;
  }
  if (!fs.existsSync(resolved)) {
    console.warn("[skip] missing image: " + resolved);
    return new Paragraph({ children: [new TextRun({ text: "[Image: " + (alt || src) + "]", italics: true })] });
  }
  const data = fs.readFileSync(resolved);
  const ext = path.extname(resolved).slice(1).toLowerCase();
  const type = (ext === "jpg" ? "jpeg" : ext);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 120 },
    children: [new ImageRun({
      data,
      transformation: { width: 600, height: 400 },
      type,
    })],
  });
}

function imageCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text, size: 10 * 2, font: "Arial", italics: true, color: "5B6975" })],
  });
}

// Design tokens
const colors = {
  primary: "1F5A84",
  primaryDark: "163D59",
  primaryLight: "E8F0F7",
  text: "1F2933",
  muted: "5B6975",
  border: "C8D3DC",
  surface: "F6F9FB",
  success: "2B6E4F",
  successLight: "E6F4ED",
  warning: "8A5A0A",
  warningLight: "FEF3E2",
  danger: "8B2E2E",
  dangerLight: "FBE9E9",
  white: "FFFFFF",
  headerBg: "D5E8F0",
};

const thinBorder = { style: BorderStyle.SINGLE, size: 1, color: colors.border };
const borders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };
const noBorders = {
  top: { style: BorderStyle.NONE, size: 0 },
  bottom: { style: BorderStyle.NONE, size: 0 },
  left: { style: BorderStyle.NONE, size: 0 },
  right: { style: BorderStyle.NONE, size: 0 },
};

const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

// Helper functions
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 200 },
    children: [new TextRun({ text, bold: true, size: 36 * 2, font: "Arial", color: colors.primaryDark })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 160 },
    children: [new TextRun({ text, bold: true, size: 28 * 2, font: "Arial", color: colors.primary })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true, size: 22 * 2, font: "Arial", color: colors.text })],
  });
}

function h4(text) {
  return new Paragraph({
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, bold: true, size: 18 * 2, font: "Arial", color: colors.text })],
  });
}

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text, size: 12 * 2, font: "Arial", color: opts.color || colors.text, bold: opts.bold, italics: opts.italics })],
  });
}

function pRuns(runs) {
  return new Paragraph({
    spacing: { after: 120 },
    children: runs.map(r => new TextRun({ text: r.text, size: 12 * 2, font: "Arial", color: r.color || colors.text, bold: r.bold, italics: r.italics })),
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 60 },
    children: [new TextRun({ text, size: 12 * 2, font: "Arial", color: colors.text })],
  });
}

function bulletRuns(runs, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 60 },
    children: runs.map(r => new TextRun({ text: r.text, size: 12 * 2, font: "Arial", color: r.color || colors.text, bold: r.bold, italics: r.italics })),
  });
}

function quote(text) {
  return new Paragraph({
    spacing: { after: 120 },
    indent: { left: 720, right: 720 },
    border: { left: { style: BorderStyle.SINGLE, size: 6, color: colors.primary, space: 8 } },
    children: [new TextRun({ text, size: 12 * 2, font: "Arial", italics: true, color: colors.muted })],
  });
}

function codeBlock(text) {
  return new Paragraph({
    spacing: { after: 120 },
    shading: { fill: colors.surface, type: ShadingType.CLEAR },
    indent: { left: 360 },
    children: [new TextRun({ text, size: 10 * 2, font: "Consolas", color: colors.text })],
  });
}

function tag(text, color) {
  return new TextRun({ text: ` [${text}] `, size: 10 * 2, font: "Arial", bold: true, color });
}

function spacer() {
  return new Paragraph({ spacing: { after: 80 }, children: [] });
}

// Table helpers
const W = 9360; // content width in DXA (US Letter with 1" margins)

function makeTable(headers, rows, colWidths) {
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      new TableCell({
        borders,
        width: { size: colWidths[i], type: WidthType.DXA },
        shading: { fill: colors.headerBg, type: ShadingType.CLEAR },
        margins: cellMargins,
        children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, size: 11 * 2, font: "Arial", color: colors.primaryDark })] })],
      })
    ),
  });

  const dataRows = rows.map(row =>
    new TableRow({
      children: row.map((cell, i) =>
        new TableCell({
          borders,
          width: { size: colWidths[i], type: WidthType.DXA },
          margins: cellMargins,
          children: [new Paragraph({ children: [new TextRun({ text: String(cell), size: 11 * 2, font: "Arial", color: colors.text })] })],
        })
      ),
    })
  );

  return new Table({
    width: { size: W, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows],
  });
}

// Build the document
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Arial", size: 12 * 2, color: colors.text } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36 * 2, bold: true, font: "Arial", color: colors.primaryDark },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28 * 2, bold: true, font: "Arial", color: colors.primary },
        paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22 * 2, bold: true, font: "Arial", color: colors.text },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "-", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
        ],
      },
      {
        reference: "numbers",
        levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        ],
      },
    ],
  },
  sections: [
    // ===== TITLE PAGE =====
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children: [
        spacer(), spacer(), spacer(), spacer(), spacer(), spacer(),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: "CivicRecords AI", size: 48 * 2, bold: true, font: "Arial", color: colors.primaryDark })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 400 },
          children: [new TextRun({ text: "Unified Design Specification", size: 28 * 2, font: "Arial", color: colors.primary })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 100 },
          border: { top: { style: BorderStyle.SINGLE, size: 2, color: colors.primary, space: 12 } },
          children: [new TextRun({ text: "Version 2.0", size: 14 * 2, font: "Arial", color: colors.muted })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 100 },
          children: [new TextRun({ text: "April 12, 2026", size: 14 * 2, font: "Arial", color: colors.muted })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 400 },
          children: [new TextRun({ text: "Draft for Review", size: 14 * 2, font: "Arial", color: colors.warning, bold: true })],
        }),
        spacer(), spacer(), spacer(),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 60 },
          children: [new TextRun({ text: "Supersedes: Master Design Specification v1 (April 11, 2026)", size: 10 * 2, font: "Arial", color: colors.muted })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 60 },
          children: [new TextRun({ text: "Incorporates: Master Design Spec, Municipal Open Records UX Style Guide,", size: 10 * 2, font: "Arial", color: colors.muted })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Design Critique (April 2026), Context-Mode Architecture Patterns,", size: 10 * 2, font: "Arial", color: colors.muted })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Universal Discovery & Connection Architecture", size: 10 * 2, font: "Arial", color: colors.muted })],
        }),
      ],
    },

    // ===== HOW TO READ + TOC =====
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            border: { bottom: { style: BorderStyle.SINGLE, size: 1, color: colors.border, space: 4 } },
            children: [new TextRun({ text: "CivicRecords AI \u2014 Unified Design Specification v2.0", size: 9 * 2, font: "Arial", color: colors.muted })],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            border: { top: { style: BorderStyle.SINGLE, size: 1, color: colors.border, space: 4 } },
            children: [
              new TextRun({ text: "Page ", size: 9 * 2, font: "Arial", color: colors.muted }),
              new TextRun({ children: [PageNumber.CURRENT], size: 9 * 2, font: "Arial", color: colors.muted }),
            ],
          })],
        }),
      },
      children: [
        h2("How to Read This Document"),
        p("This is the single source of truth for CivicRecords AI. Every feature, data model change, design decision, and implementation detail lives here. Each feature is tagged with a phase:"),
        spacer(),
        bulletRuns([{ text: "[BUILT]", bold: true, color: colors.success }, { text: " \u2014 Available since v0.1.0; tested through v1.4.1" }]),
        bulletRuns([{ text: "[REDESIGN]", bold: true, color: colors.warning }, { text: " \u2014 Built but needs UI/UX overhaul" }]),
        bulletRuns([{ text: "[MVP-NOW]", bold: true, color: colors.danger }, { text: " \u2014 Must be added before v1.0 release" }]),
        bulletRuns([{ text: "[v1.1]", bold: true, color: colors.primary }, { text: " \u2014 Next release after initial deployment" }]),
        bulletRuns([{ text: "[v2.0]", bold: true, color: colors.muted }, { text: " \u2014 Future capability, architecture should not preclude it" }]),
        spacer(),
        new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 1: PRODUCT SUMMARY =====
        h1("1. Product Summary"),

        h3("What It Is"),
        p("Open-source, locally-hosted AI system for municipal open records request processing. Runs on commodity hardware via Docker. No cloud, no vendor lock-in, no telemetry."),

        h3("North-Star Statement"),
        quote("Any resident should be able to search for public records, request what is missing, and understand the status of their request without needing insider knowledge of city government."),
        p("Staff corollary: Any records clerk should be able to triage, search, review, redact, and respond to records requests from a single calm interface without falling back to email, spreadsheets, or paper.", { italics: true }),

        h3("What It Is Not"),
        bullet("Not a records management system \u2014 it indexes and searches what already exists."),
        bullet("Not a legal advisor \u2014 it surfaces suggestions, staff make all decisions."),
        bullet("Not a cloud service \u2014 every deployment is a sovereign instance owned by the city."),
        bullet("Not a public-facing portal in v1.0 \u2014 internal staff tool first. Public portal in v1.1."),

        h3("Design Stance"),
        p("Transparent, calm, accessible, and government-appropriate. Civic and competent: calmer than a startup SaaS product, but cleaner and more modern than a legacy government form portal. The aesthetic target is trust through clarity, not visual excitement."),

        h3("Core Design Principles"),
        bulletRuns([{ text: "Clarity over bureaucracy", bold: true }, { text: " \u2014 residents should not need to understand government structure to make a good request." }]),
        bulletRuns([{ text: "Transparency over mystery", bold: true }, { text: " \u2014 statuses, timelines, costs, and next actions should always be visible." }]),
        bulletRuns([{ text: "Consistency over one-off screens", bold: true }, { text: " \u2014 shared patterns reduce confusion and development cost." }]),
        bulletRuns([{ text: "Accessibility over compliance theater", bold: true }, { text: " \u2014 forms and documents must be usable, not merely technically valid." }]),
        bulletRuns([{ text: "Operational calm over case chaos", bold: true }, { text: " \u2014 staff views should help triage and decision-making, not add clutter." }]),
        bulletRuns([{ text: "Human-in-the-loop always", bold: true }, { text: " \u2014 no auto-redaction, no auto-denial, no auto-release. Every AI output is a draft." }]),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 2: USER GROUPS =====
        h1("2. User Groups"),

        h3("Staff Users (v1.0)"),
        makeTable(
          ["User Group", "Primary Need", "Design Response"],
          [
            ["City clerk / records officer", "Triage, route, communicate, and complete requests.", "Queue views, routing rules, templates, SLA timers, full event history."],
            ["Department liaison", "Provide documents and answer scoped questions quickly.", "Scoped assignment view, internal notes, due dates, one-click return to records team."],
            ["Legal / reviewer", "Review exemptions, redactions, and sensitive material.", "Review queue, exemption tags, redaction ledger, approval state."],
            ["City IT administrator", "Install, configure, and maintain the system.", "Docker Compose, admin panel, model management, audit export."],
          ],
          [2200, 3200, 3960]
        ),

        spacer(),
        h3("Public Users (v1.1)"),
        makeTable(
          ["User Group", "Primary Need", "Design Response"],
          [
            ["Resident / first-time requester", "Submit a request without knowing the exact record title or department.", "Guided request flow, plain-language examples, estimated turnaround, visible help."],
            ["Journalist / researcher", "Search existing records and request additional material efficiently.", "Robust search, saved filters, exportable results, request history."],
          ],
          [2200, 3200, 3960]
        ),

        spacer(),
        h3("RBAC Roles"),
        makeTable(
          ["Role", "Scope", "Phase"],
          [
            ["admin", "Full system access, user management, configuration", "[BUILT]"],
            ["staff", "Request management, search, ingestion, exemption review", "[BUILT]"],
            ["reviewer", "Read-only access plus exemption review approval", "[BUILT]"],
            ["read_only", "View dashboards and reports only", "[BUILT]"],
            ["liaison", "Scoped to assigned department, can attach documents and add notes", "[MVP-NOW]"],
            ["public", "Submit requests, track own requests, search published records", "[v1.1]"],
          ],
          [1800, 5560, 2000]
        ),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 3: INFORMATION ARCHITECTURE =====
        h1("3. Information Architecture"),

        h3("Staff Workbench (v1.0) \u2014 8 Pages"),
        makeTable(
          ["Page", "Purpose", "Phase"],
          [
            ["Dashboard", "System health, operational metrics, SLA overview", "[REDESIGN]"],
            ["Search", "Hybrid RAG search across ingested documents", "[REDESIGN]"],
            ["Requests", "Request queue with triage, routing, SLA timers", "[REDESIGN]"],
            ["Request Detail", "Single request: details, workflow, documents, timeline, response letter", "[REDESIGN]"],
            ["Exemptions", "Exemption rules management and flag review dashboard", "[REDESIGN]"],
            ["Sources", "Data source configuration and file upload", "[REDESIGN]"],
            ["Ingestion", "Document processing status and pipeline monitoring", "[REDESIGN]"],
            ["Users", "User management and role assignment", "[REDESIGN]"],
          ],
          [2000, 5360, 2000]
        ),

        spacer(),
        h3("Public Portal (v1.1) \u2014 5 Pages"),
        makeTable(
          ["Page", "Purpose", "Phase"],
          [
            ["Home", "Search bar, common categories, response-time guidance, top tasks", "[v1.1]"],
            ["Search Records", "Published records index with filters", "[v1.1]"],
            ["Make a Request", "Guided intake wizard with scope helper", "[v1.1]"],
            ["Track a Request", "Public timeline, messages, delivered files, fees", "[v1.1]"],
            ["Help & Policy", "Open records law summary, fee schedule, exemptions, contact info", "[v1.1]"],
          ],
          [2000, 5360, 2000]
        ),

        spacer(),
        h3("Navigation Rules"),
        bulletRuns([{ text: "Staff workbench:", bold: true }, { text: " Sidebar navigation (not top nav). Better for 8+ items, standard for admin panels. Active page highlighted with left border accent." }]),
        bulletRuns([{ text: "Public portal:", bold: true }, { text: " Top navigation with no more than 6 top-level choices. Complex routing inside guided flows." }]),
        bullet("Every page must be identifiable from peripheral vision \u2014 unique page icon, header treatment, or accent color."),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 4: SYSTEM ARCHITECTURE =====
        h1("4. System Architecture"),

        h3("Docker Compose Stack [BUILT]"),
        codeBlock("1. postgres    \u2014 PostgreSQL 17 + pgvector (data, vectors, audit)"),
        codeBlock("2. redis       \u2014 Redis 7.2 (BSD license, pinned <8.0)"),
        codeBlock("3. api         \u2014 FastAPI application server (port 8000)"),
        codeBlock("4. worker      \u2014 Celery worker(s) for async ingestion/embedding/notifications"),
        codeBlock("5. beat        \u2014 Celery Beat scheduler for periodic tasks"),
        codeBlock("6. ollama      \u2014 Local LLM runtime (Gemma 4 + nomic-embed-text)"),
        codeBlock("7. frontend    \u2014 React/nginx (port 8080)"),

        spacer(),
        imageParagraph("diagrams/deployment-stack.svg", "Deployment stack"),
        imageCaption("Deployment stack \u2014 entire system runs inside Docker Compose on the city's network. No cloud, no outbound by default."),
        imageParagraph("diagrams/llm-flow.svg", "LLM call flow"),
        imageCaption("LLM call flow \u2014 records-ai routes through civiccore.llm (context assembly, template resolution, model registry, provider factory) to a local Ollama provider."),
        imageParagraph("diagrams/sovereignty.svg", "Sovereignty boundary"),
        imageCaption("Sovereignty boundary \u2014 all runtime components live inside the city's on-prem network. Cloud is opt-in only."),
        spacer(),
        h3("Application Modules"),
        makeTable(
          ["Module", "Responsibility", "Phase"],
          [
            ["Auth Module", "fastapi-users, JWT, RBAC, service accounts", "[BUILT]"],
            ["Search API", "RAG queries, hybrid retrieval, source attribution, session context", "[BUILT]"],
            ["Workflow API", "Request CRUD, status transitions, document association, deadline mgmt", "[BUILT]"],
            ["Audit Logger", "Hash-chained append-only logging, CSV/JSON export", "[BUILT]"],
            ["LLM Abstraction", "Model-agnostic Ollama wrapper, chat + embedding endpoints", "[BUILT]"],
            ["Exemption Engine", "Rules engine (regex, keyword, statutory) + LLM suggestions", "[BUILT]"],
            ["Context Manager", "Smart prompt assembly with token budgeting for local LLM", "[MVP-NOW]"],
            ["Notification Service", "Email templates via Celery tasks, SMTP integration", "[MVP-NOW]"],
            ["Fee Tracking", "Fee estimation, payment status, waiver management", "[MVP-NOW]"],
            ["Response Generator", "Template-based response letter generation with LLM assist", "[MVP-NOW]"],
            ["Analytics API", "Operational metrics, SLA compliance, workload reporting", "[MVP-NOW]"],
            ["Federation API", "REST endpoints for inter-instance queries via service accounts", "[BUILT]"],
            ["Public API", "Read-only endpoints for public portal with rate limiting", "[v1.1]"],
          ],
          [2200, 5160, 2000]
        ),

        spacer(),
        h3("Context Management for Local LLM [MVP-NOW]"),
        p("Local LLMs (Ollama) have limited context windows (8K\u2013128K tokens). Municipal documents are large. The system must be deliberate about what enters the LLM prompt."),
        spacer(),
        h4("Token Budget System"),
        p("Each LLM call has a configurable maximum context budget, partitioned into reserved sections:"),
        codeBlock("System instruction:    ~500 tokens (fixed)"),
        codeBlock("Request context:       ~500 tokens (requester, deadline, description)"),
        codeBlock("Retrieved chunks:      ~5000 tokens (top-k from hybrid search)"),
        codeBlock("Exemption rules:       ~500 tokens (applicable state rules)"),
        codeBlock("Output reservation:    ~1500 tokens (response generation space)"),
        codeBlock("Safety margin:         ~192 tokens"),
        spacer(),
        h4("Smart Context Assembly"),
        bullet("Pre-filter with PostgreSQL FTS (tsvector) for keyword relevance."),
        bullet("Rank with pgvector for semantic relevance."),
        bullet("Select top-k chunks that fit within budget."),
        bullet("Include metadata (source filename, page number, date) but not full text of non-relevant sections."),
        spacer(),
        h4("Model-Aware Budgeting"),
        p("Context budget reads from model_registry table. When the admin switches from Gemma 4 (8K) to Llama 3.3 (128K), budgets auto-adjust via the context_window_size column."),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 5: DATA MODEL =====
        h1("5. Data Model"),
        p("All tables below are annotated with their implementation phase. New tables and columns added in this spec are marked."),

        h3("Auth & Administration"),
        codeBlock("users: id, email, hashed_password, display_name, role, department_id [MVP-NOW],"),
        codeBlock("       is_active, is_verified, created_at"),
        codeBlock("  role ENUM: admin, staff, reviewer, read_only, liaison [MVP-NOW]"),
        spacer(),
        codeBlock("departments [MVP-NOW]: id, name, code, contact_email, created_at"),
        spacer(),
        codeBlock("audit_log: id, user_id, action, resource_type, resource_id,"),
        codeBlock("           details (JSON), ip_address, previous_hash, current_hash, created_at"),
        spacer(),
        codeBlock("service_accounts: id, name, api_key_hash (SHA-256), role, scopes (JSON),"),
        codeBlock("                  created_by, is_active"),

        h3("Documents & Ingestion"),
        codeBlock("data_sources: id, name, type (file_share/database/email/upload/sharepoint/api),"),
        codeBlock("              connection_config (encrypted JSON), schedule, status, created_by"),
        spacer(),
        codeBlock("documents: id, source_id, source_path, filename, display_name [MVP-NOW],"),
        codeBlock("           file_type, file_hash (SHA-256), file_size, ingestion_status,"),
        codeBlock("           ingested_at, metadata (JSON), department_id [MVP-NOW]"),
        spacer(),
        codeBlock("document_chunks: id, document_id, chunk_index, content_text,"),
        codeBlock("                 embedding Vector(768), token_count"),

        h3("Search & RAG"),
        codeBlock("search_sessions: id, user_id, created_at"),
        codeBlock("search_queries: id, session_id, query_text, filters (JSON), results_count,"),
        codeBlock("                ai_summary, created_at"),
        codeBlock("search_results: id, query_id, chunk_id, similarity_score, rank,"),
        codeBlock("                normalized_score [MVP-NOW] (0-100 scale)"),
        codeBlock("saved_searches [v1.1]: id, user_id, name, query_text, filters (JSON), created_at"),

        h3("Request Tracking"),
        codeBlock("records_requests: id, requester_name, requester_email,"),
        codeBlock("  requester_phone [MVP-NOW], requester_type [MVP-NOW],"),
        codeBlock("  date_received, statutory_deadline, description,"),
        codeBlock("  scope_assessment [MVP-NOW] (narrow/moderate/broad),"),
        codeBlock("  status, assigned_to, department_id [MVP-NOW],"),
        codeBlock("  estimated_fee [MVP-NOW], fee_status [MVP-NOW],"),
        codeBlock("  fee_waiver_requested [MVP-NOW], priority [MVP-NOW],"),
        codeBlock("  created_by, closed_at [MVP-NOW], closure_reason [MVP-NOW]"),
        spacer(),
        p("Status ENUM (expanded):", { bold: true }),
        codeBlock("  received, clarification_needed [MVP-NOW], assigned [MVP-NOW],"),
        codeBlock("  searching, in_review, ready_for_release [MVP-NOW],"),
        codeBlock("  drafted, approved, fulfilled [MVP-NOW], closed [MVP-NOW]"),
        spacer(),
        codeBlock("request_documents: id, request_id, document_id, relevance_note,"),
        codeBlock("                   exemption_flags (JSON), inclusion_status"),
        spacer(),
        codeBlock("request_timeline [MVP-NOW]: id, request_id, event_type, actor_id,"),
        codeBlock("                            actor_role, description, internal_note, created_at"),
        spacer(),
        codeBlock("request_messages [MVP-NOW]: id, request_id, sender_type, sender_id,"),
        codeBlock("                            message_text, is_internal, created_at"),
        spacer(),
        codeBlock("response_letters [MVP-NOW]: id, request_id, template_id, generated_content,"),
        codeBlock("                            edited_content, status (draft/approved/sent),"),
        codeBlock("                            generated_by, approved_by, sent_at"),

        h3("Fees [MVP-NOW]"),
        codeBlock("fee_schedules: id, jurisdiction, fee_type, amount, description,"),
        codeBlock("               effective_date, created_by"),
        codeBlock("fee_line_items: id, request_id, fee_schedule_id, description,"),
        codeBlock("                quantity, unit_price, total, status"),

        h3("Notifications [MVP-NOW]"),
        codeBlock("notification_templates: id, event_type, channel, subject_template,"),
        codeBlock("                        body_template, is_active, created_by"),
        codeBlock("notification_log: id, template_id, recipient_email, request_id,"),
        codeBlock("                  channel, status, sent_at, error_message"),

        h3("Exemption Detection"),
        codeBlock("exemption_rules [BUILT]: id, state_code, category, rule_type,"),
        codeBlock("                         rule_definition, enabled, created_by"),
        codeBlock("exemption_flags [BUILT]: id, chunk_id, rule_id, request_id, category,"),
        codeBlock("                         confidence, status, reviewed_by, reviewed_at,"),
        codeBlock("                         review_note [MVP-NOW]"),
        codeBlock("redaction_ledger [v1.1]: id, request_id, document_id, page_number,"),
        codeBlock("                         redaction_type, exemption_basis, redacted_by, created_at"),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 6: VISUAL DESIGN SYSTEM =====
        h1("6. Visual Design System"),

        h3("Design Tokens"),
        makeTable(
          ["Token", "Value", "Usage"],
          [
            ["brand.primary", "#1F5A84", "Core actions, links, active navigation"],
            ["brand.primaryDark", "#163D59", "Page titles, hover states"],
            ["brand.primaryLight", "#E8F0F7", "Info backgrounds, selected states"],
            ["text.default", "#1F2933", "Body text, headings"],
            ["text.muted", "#5B6975", "Secondary text, labels, metadata"],
            ["surface.default", "#FFFFFF", "Page background, card background"],
            ["surface.subtle", "#F6F9FB", "Alternate row, section background"],
            ["surface.border", "#C8D3DC", "Card borders, dividers"],
            ["status.success", "#2B6E4F", "Completed, released, available"],
            ["status.warning", "#8A5A0A", "Pending, clarification needed, approaching deadline"],
            ["status.danger", "#8B2E2E", "Overdue, denied, failed"],
          ],
          [2200, 1600, 5560]
        ),

        spacer(),
        h3("Typography Scale"),
        makeTable(
          ["Element", "Phase 0 baseline (v0.1.0)", "Target (v1.0)"],
          [
            ["H1 (page title)", "Not used", "36px / 700 weight"],
            ["H2 (section head)", "20px / 600 weight", "28px / 600 weight"],
            ["H3 (subsection)", "14px / 500 weight", "22px / 600 weight"],
            ["Body", "16px / 400 weight", "16px / 400 weight (no change)"],
            ["Labels", "14px / mixed", "13px / 500 weight / uppercase / 0.05em spacing"],
            ["Stat card numbers", "Mixed sizes", "36px / 700 weight for primary metrics"],
          ],
          [2500, 3430, 3430]
        ),

        spacer(),
        h3("Status Badge Color Mapping"),
        makeTable(
          ["Status", "Color Role", "Icon"],
          [
            ["Received", "info (blue)", "Inbox"],
            ["Clarification needed", "warning (amber)", "MessageCircle"],
            ["Assigned", "info (blue)", "UserCheck"],
            ["Searching", "info (blue)", "Search"],
            ["In review", "warning (amber)", "Eye"],
            ["Ready for release", "success (green)", "CheckCircle"],
            ["Drafted", "info (blue)", "FileText"],
            ["Approved", "success (green)", "ShieldCheck"],
            ["Fulfilled", "success (green)", "Send"],
            ["Closed", "neutral (gray)", "Archive"],
          ],
          [3000, 3360, 3000]
        ),
        p("Every badge includes an icon \u2014 never color-only. Accessible for colorblind users.", { italics: true }),

        spacer(),
        h3("Button Variants (3 only)"),
        makeTable(
          ["Variant", "Use", "Style"],
          [
            ["Primary", "Main page action (New Request, Submit for Review)", "Filled brand.primary, white text"],
            ["Secondary", "Supporting actions (Search & Attach, Export)", "Outlined brand.primary border, transparent bg"],
            ["Ghost", "Tertiary actions (Sign out, Cancel, Back)", "Text-only, hover bg surface.subtle"],
          ],
          [1800, 4060, 3500]
        ),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 7: WORKFLOW PATTERNS =====
        h1("7. Workflow Patterns"),

        h3("7.1 Request Lifecycle"),
        p("The full request lifecycle from receipt to closure:"),
        codeBlock("[Received] \u2192 [Clarification Needed]? \u2192 [Assigned] \u2192 [Searching]"),
        codeBlock("  \u2192 [In Review] \u2192 [Ready for Release] \u2192 [Drafted]"),
        codeBlock("  \u2192 [Approved] \u2192 [Fulfilled] \u2192 [Closed]"),
        spacer(),
        p("Every status transition:"),
        bullet("Writes to request_timeline"),
        bullet("Writes to audit_log"),
        bullet("Triggers notification (if template exists for that transition)"),
        bullet("Updates records_requests.status"),

        spacer(),
        h3("7.2 Response Letter Generation [MVP-NOW]"),
        bullet("Clerk clicks [Generate Response Letter] on Request Detail"),
        bullet("System assembles context within token budget: request, documents, exemptions, templates, fees"),
        bullet("LLM generates draft letter (labeled as AI-generated draft)"),
        bullet("Clerk edits in rich text editor"),
        bullet("Submit for Approval \u2192 Supervisor reviews \u2192 Approve \u2192 Send"),

        spacer(),
        h3("7.3 Notification Templates [MVP-NOW]"),
        makeTable(
          ["Event", "Recipient", "Channel"],
          [
            ["Request received", "Requester", "Email"],
            ["Clarification needed", "Requester", "Email"],
            ["Request assigned", "Liaison", "In-app"],
            ["Deadline approaching (3 days)", "Assigned staff", "In-app + Email"],
            ["Deadline overdue", "Assigned staff + Admin", "In-app + Email"],
            ["Records ready", "Requester", "Email"],
            ["Request closed", "Requester", "Email"],
          ],
          [3200, 3160, 3000]
        ),
        p("Tone: reassuring, plain language, explain process. Never defensive or legalistic.", { italics: true }),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 8: ACCESSIBILITY =====
        h1("8. Accessibility Standards"),
        p("Target: WCAG 2.2 AA from day one.", { bold: true }),

        makeTable(
          ["Requirement", "Current State", "Target"],
          [
            ["Color contrast", "Passes (text ~15:1, muted ~5.7:1)", "Maintain"],
            ["Touch targets", "FAIL (nav links 20px, no padding)", "44x44px minimum on all interactive elements"],
            ["Focus visibility", "No visible focus styles", "focus:ring-2 focus:ring-primary on all focusables"],
            ["Skip navigation", "Missing", "Add skip-to-content link"],
            ["ARIA landmarks", "Good (nav role, table aria-labels)", "Maintain + add to new components"],
            ["Color-only indicators", "Status badges use color only", "Add icons to every badge"],
            ["Keyboard navigation", "Untested", "Full keyboard completion for all workflows"],
            ["Form error handling", "Not tested", "Preserve data on validation error, focus first error"],
            ["Screen reader", "Untested", "Test with NVDA/VoiceOver before v1.0"],
          ],
          [2200, 3580, 3580]
        ),

        spacer(),
        h3("Content Design Rules"),
        bulletRuns([{ text: "Lead with action:", bold: true }, { text: ' "Tell us what records you need" not "Records Request Submission Form"' }]),
        bullet("Explain why data is requested when the reason is not obvious."),
        bullet("Never hide important policy terms only in tooltips."),
        bullet("Every closed/denied request shows reason in human language plus formal basis."),
        bulletRuns([{ text: "Replace jargon:", bold: true }, { text: ' "responsive documents" becomes "records found for release"' }]),
        bullet("Every error state explains: what happened, how to fix it, how to get help."),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 9: COMPLIANCE =====
        h1("9. Compliance Architecture [BUILT]"),
        p("Based on the 50-state regulatory analysis. These are hard requirements enforced at the API layer."),

        h3("Human-in-the-Loop"),
        bullet("No auto-redaction. Every exemption flag requires affirmative human action."),
        bullet("No auto-denial. No denial or partial-denial response generated without human decision."),
        bullet("No auto-release. No document transmitted to requester without explicit human authorization."),
        bullet('All AI content labeled as "AI-generated draft requiring human review" at the API layer.'),

        h3("Audit Logging"),
        bullet("Hash-chained, append-only audit log."),
        bullet("Every API call logged with user, action, resource, timestamp, IP."),
        bullet("Exportable as CSV/JSON for compliance audits."),
        bullet("Retention policy configurable (cleanup job [MVP-NOW])."),

        h3("Data Sovereignty"),
        bullet("No outbound network connections (verification scripts provided)."),
        bullet("No telemetry, analytics beacons, or external API calls."),
        bullet("All processing local. LLM runs on-premises via Ollama."),
        bullet("All dependencies permissive or weak-copyleft licensed."),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 10: IMPLEMENTATION PLAN =====
        h1("10. Technical Implementation Plan"),

        h3("Build Order"),
        spacer(),
        h4("Phase 0: Design Foundation [MVP-NOW \u2014 do first]"),
        bullet("Install shadcn/ui"),
        bullet("Map design tokens to CSS variables"),
        bullet("Build sidebar layout shell"),
        bullet("Create component variants (buttons, badges, cards, tables)"),
        bullet("Typography scale implementation"),

        spacer(),
        h4("Phase 1: Staff Workbench Redesign [MVP-NOW \u2014 8 pages]"),
        bullet("Dashboard with operational metrics"),
        bullet("Search with normalized scores and empty states"),
        bullet("Requests with filtering, priority, SLA indicators"),
        bullet("Request Detail with timeline, messages, fees"),
        bullet("Exemptions with flag review workflow"),
        bullet("Sources with guided setup and integration cards"),
        bullet("Ingestion with clean filenames and progress"),
        bullet("Users with department assignment"),

        spacer(),
        h4("Phase 2: New Backend Features [MVP-NOW]"),
        bullet("Database migrations (departments, fees, timeline, messages, notifications, prompts)"),
        bullet("Notification service (Celery + SMTP)"),
        bullet("Response letter generation (LLM + templates)"),
        bullet("Context manager (token budgeting for Ollama)"),
        bullet("Fee tracking API"),
        bullet("Request scope assessment API"),
        bullet("Operational analytics API"),
        bullet("Liaison role + department scoping"),
        bullet("Audit retention cleanup task"),

        spacer(),
        h4("Phase 3: Public Portal [v1.1]"),
        bullet("Public API with rate limiting"),
        bullet("Public homepage and search"),
        bullet("Guided request wizard"),
        bullet("Public request tracker"),
        bullet("Published records index and saved searches"),

        spacer(),
        h4("Phase 4: Transparency Layer [v2.0]"),
        bullet("Open records library with curated collections"),
        bullet("Reporting dashboards and trend analytics"),
        bullet("Public request archive (closed requests, opt-in)"),
        bullet("Federation between CivicRecords AI instances"),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 12: UNIVERSAL DISCOVERY =====
        h1("12. Universal Discovery & Connection Architecture"),

        h3("12.0 Why This Section Matters"),
        p("Open records requests can touch any system a city operates. Clerks often spend more time finding records than reviewing them. This section defines how CivicRecords AI finds, connects to, and monitors data sources automatically."),
        quote("Instead of you tracking down every system that might have responsive records, CivicRecords AI learns what systems your city uses and goes looking for you. You still decide what gets released."),

        h3("12.1 Municipal Knowledge Graph"),
        p("The system ships with a curated Municipal Systems Catalog \u2014 a structured graph mapping functional domains to systems, data shapes, access protocols, and discovery hints. Organized by 12 functional domains."),
        spacer(),
        makeTable(
          ["Domain", "Typical Systems", "Sensitivity"],
          [
            ["Finance & Budgeting", "Tyler Munis, Caselle, OpenGov, SAP", "Tax IDs, bank accounts, SSNs"],
            ["Public Safety", "Mark43, Spillman, Axon, Genetec", "CJIS-protected, juvenile records"],
            ["Land Use & Permitting", "Accela, CityWorks, EnerGov", "Homeowner PII, contractor data"],
            ["Human Resources", "NEOGOV, Workday, ADP, Paylocity", "HIPAA, background checks, SSNs"],
            ["Document Management", "Laserfiche, OnBase, SharePoint", "Varies"],
            ["Email & Communication", "Microsoft 365, Google Workspace", "Personal emails, deliberations"],
            ["Utilities & Public Works", "CIS Infinity, Cartegraph, Lucity", "Account numbers, payment info"],
            ["Courts & Legal", "Tyler Odyssey, Journal Technologies", "Sealed records, juvenile cases"],
            ["Parks & Recreation", "RecTrac, CivicRec, ActiveNet", "Minor personal info, payment data"],
            ["Asset & Fleet Mgmt", "Samsara, Asset Panda, FleetWave", "Driver IDs, GPS patrol patterns"],
            ["Legacy & Custom", "AS/400, Access DBs, FoxPro, flat files", "Often unknown"],
          ],
          [2600, 4160, 2600]
        ),
        p("The catalog is community-maintained and versioned. Cities contribute updates. Local config is never overwritten.", { italics: true }),

        spacer(),
        h3("12.2 Guided Onboarding Interview"),
        p("An LLM-guided adaptive interview that starts broad and gets specific based on answers. Three phases:"),
        bulletRuns([{ text: "Phase 1: City Profile (5\u201310 min)", bold: true }, { text: " \u2014 state, population, email platform, IT staffing, request volume." }]),
        bulletRuns([{ text: "Phase 2: System Identification (10\u201320 min)", bold: true }, { text: " \u2014 walks through each domain, asks targeted questions based on city profile." }]),
        bulletRuns([{ text: "Phase 3: Gap Map (5 min)", bold: true }, { text: " \u2014 identifies domains where the city should have data but hasn't identified a source." }]),
        p("Output: a City Profile with confirmed systems, gap map, IT environment notes, and priority ranking."),

        spacer(),
        h3("12.3 Active Discovery Engine [v1.1]"),
        p("With explicit IT permission, scans the local network and cross-references findings against the Systems Catalog."),
        quote("After setup, the system looks around your network and says: 'I found a database that looks like your parks reservation system. Want me to connect to it?' It never connects without your approval."),
        bulletRuns([{ text: "Method 1: Network Service Scanning", bold: true }, { text: " \u2014 fingerprints on common ports (SQL 1433, PostgreSQL 5432, SMB, HTTP)." }]),
        bulletRuns([{ text: "Method 2: Directory Enumeration", bold: true }, { text: " \u2014 Active Directory service accounts and security groups." }]),
        bulletRuns([{ text: "Method 3: API Endpoint Probing [v2.0]", bold: true }, { text: " \u2014 standard vendor API paths. Probe only, no auth." }]),
        spacer(),
        h4("Confidence Scoring"),
        makeTable(
          ["Score", "Meaning", "Admin Action"],
          [
            ["90\u2013100%", "High confidence \u2014 vendor API confirmed", "One-click confirm and connect"],
            ["60\u201389%", "Probable match \u2014 DB name or service account pattern", "Review details, confirm, authorize"],
            ["30\u201359%", "Possible match \u2014 type unclear", "Investigate with IT, classify manually"],
            ["Below 30%", "Unknown \u2014 unidentifiable", "Flag for IT review or ignore"],
          ],
          [1800, 4560, 3000]
        ),

        spacer(),
        h3("12.4 Universal Connector Protocol"),
        p("Every connector implements four standard operations:"),
        bulletRuns([{ text: "authenticate()", bold: true }, { text: " \u2014 secure connection via OAuth2, DB credentials, API key, or service account." }]),
        bulletRuns([{ text: "discover()", bold: true }, { text: " \u2014 enumerate available records in the source system." }]),
        bulletRuns([{ text: "fetch()", bold: true }, { text: " \u2014 pull records and convert to standard document format." }]),
        bulletRuns([{ text: "health_check()", bold: true }, { text: " \u2014 verify connection alive, credentials valid, schema unchanged." }]),
        spacer(),
        makeTable(
          ["Protocol", "Best For", "Phase"],
          [
            ["File System / SMB", "Shared drives, document repos, scanned archives", "[MVP-NOW]"],
            ["SMTP / IMAP Journal", "Email archives (#1 source for records requests)", "[MVP-NOW]"],
            ["REST API (Modern SaaS)", "Tyler, Accela, NEOGOV, cloud platforms", "[v1.1]"],
            ["ODBC / JDBC Bridge", "On-prem databases, legacy SQL, AS/400", "[v1.1]"],
            ["GIS REST API", "Esri ArcGIS, spatial data, property records", "[v2.0]"],
            ["Vendor SDK", "Evidence management (Axon), CAD systems", "[v2.0]"],
            ["Manual / Export Drop", "Systems with no API \u2014 clerk uploads", "[MVP-NOW]"],
          ],
          [2600, 4760, 2000]
        ),

        spacer(),
        h3("12.5 Continuous Discovery & Self-Healing"),
        p("Weekly scheduled discovery runs detect new, changed, and lost sources. Connection health monitoring with automatic handling:"),
        bullet("Expired OAuth2 tokens: auto-refreshed."),
        bullet("Temporary outages: exponential backoff (1m \u2192 5m \u2192 15m \u2192 60m)."),
        bullet("Password rotation: detects auth failures, prompts admin."),
        bullet("Schema drift: pauses ingestion, alerts admin with change description."),
        bullet("API rate limiting: auto-throttles, shifts to off-peak hours."),
        spacer(),
        h4("Coverage Gap Analysis"),
        p("Cross-references connected sources against request patterns monthly. Example:"),
        quote("32% of your requests reference 'police' or 'incident report,' but you don't have a public safety data source connected. Would you like help setting that up?"),

        spacer(),
        h3("12.6 Handling Unknown and Legacy Systems"),
        p("For unknown databases, the system can enumerate table/column names (with authorization) and feed metadata to the LLM for characterization."),
        h4("Schema Metadata Sensitivity"),
        bullet("Schema enumeration results stored encrypted at rest, never in plaintext."),
        bullet("LLM characterization subject to same context management rules as document content."),
        bullet("Audit trail records enumeration occurred but does not log table/column names in plaintext."),
        bullet("LLM describes system function in general terms without echoing sensitive names."),
        spacer(),
        h4("Manual Fallback Paths (priority order)"),
        bulletRuns([{ text: "1. Watched folder", bold: true }, { text: " \u2014 department exports to designated folder, system auto-ingests." }]),
        bulletRuns([{ text: "2. Scheduled export", bold: true }, { text: " \u2014 IT cron job dumps data to drop location." }]),
        bulletRuns([{ text: "3. Manual upload", bold: true }, { text: " \u2014 staff upload via Sources page. Universal fallback." }]),
        bulletRuns([{ text: "4. RPA bridge [v2.0]", bold: true }, { text: " \u2014 last resort. Deploy only when: no API, no export, no DB access, AND high request frequency." }]),

        new Paragraph({ children: [new PageBreak()] }),

        h3("12.7 Tiered Redaction Engine"),
        p("Extends the Exemption Engine with automated detection in three tiers. All redaction is proposal-only \u2014 humans approve."),
        spacer(),
        makeTable(
          ["Tier", "Method", "What It Detects", "Phase"],
          [
            ["Tier 1", "RegEx pattern matching", "SSNs, credit cards, phone numbers, email, bank accounts, driver's licenses", "[MVP-NOW]"],
            ["Tier 2", "NLP/NER (Ollama or spaCy)", "Person names in sensitive contexts, medical info, juvenile IDs, attorney-client privilege", "[v1.1]"],
            ["Tier 3", "Visual AI (GPU required)", "Faces/plates in video, OCR for scanned docs, speech-to-text for 911 recordings", "[v2.0]"],
          ],
          [1200, 2800, 3360, 2000]
        ),

        spacer(),
        h3("12.8 Security & Compliance"),
        h4("Permission Model"),
        bullet("Network discovery: disabled by default, explicit IT opt-in, scope-limited, audit-logged."),
        bullet("Every connection: admin must review, confirm, provide credentials, and authorize."),
        bullet("Credentials: AES-256 encrypted at rest. Never logged, exported, or displayed after entry."),
        bullet("Least-privilege: read-only accounts and API scopes. System never writes to source systems."),
        spacer(),
        h4("Originals vs. Redacted Derivatives"),
        p("Redaction produces a separate Derivative copy. Original preserved read-only. Redaction ledger records every redaction with legal basis and approving staff member. Non-destructive."),
        spacer(),
        h4("CJIS Compliance for Public Safety Connectors"),
        p("Connecting to police records triggers FBI CJIS Security Policy. Architecture already satisfies encryption (5.10.1), audit logging (5.4), access control (5.5), and no cloud egress (5.10.3.2)."),
        p("City must also satisfy: fingerprint-based background checks (5.12), signed CJIS Security Addendum, and security awareness training (5.2)."),
        pRuns([{ text: "Enforcement:", bold: true }, { text: " CJIS compliance checklist blocks public safety connector activation until admin confirms all requirements. Gate applies regardless of how the source was discovered." }]),

        spacer(),
        h3("12.9 Data Model Additions"),
        p("7 new tables:"),
        codeBlock("city_profile [MVP-NOW], system_catalog [MVP-NOW], connector_templates [MVP-NOW]"),
        codeBlock("discovered_sources [v1.1], discovery_runs [v1.1], source_health_log [v1.1], coverage_gaps [v1.1]"),
        spacer(),
        p("Extended columns on existing tables:"),
        codeBlock("data_sources: +discovered_source_id, connector_template_id, sync_schedule, health_status, schema_hash"),
        codeBlock("documents: +redaction_status, derivative_path, original_locked"),
        codeBlock("exemption_flags: +detection_tier, detection_method, auto_detected"),
        codeBlock("model_registry: +supports_ner, supports_vision"),

        spacer(),
        h3("12.11 Engineering Acceptance Criteria"),
        p("13 criteria including: onboarding completable by clerk alone, network discovery opt-in, connector authorization logged, health checks surfaced on Dashboard, AES-256 credentials, gap map auto-updates, zero false negatives for Tier 1 regex, all redaction proposal-only, CJIS gate enforced, schema metadata encrypted, RPA self-diagnostics."),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== SECTION 13: ROLLOUT ROADMAP =====
        h1("13. Phased Rollout Roadmap"),
        makeTable(
          ["Phase", "What", "Exit Criteria"],
          [
            ["0. Foundations", "Token set, component library, sidebar shell, content model", "Team agrees on tokens, components, and page patterns"],
            ["1. Staff redesign", "Redesign all 8 pages with new design system", "All pages match spec, WCAG 2.2 AA passes, 80+ tests green"],
            ["2. New features", "Fees, notifications, response letters, context manager, analytics", "Clerk can process request end-to-end: receive, clarify, search, review, draft, approve, fulfill, close"],
            ["3. Public portal", "Homepage, search, request wizard, tracker, help", "Requester can submit, track, and receive records end-to-end"],
            ["4. Transparency", "Open records library, analytics, public archive, federation", "City can publish record sets and measure self-service adoption"],
          ],
          [2000, 3680, 3680]
        ),

        spacer(),
        h3("Engineering Acceptance Criteria"),
        bullet("Every component must support loading, empty, error, and disabled states."),
        bullet("Every workflow must support keyboard-only completion."),
        bullet("Role-based permissions change available actions, not layout or naming."),
        bullet("All status transitions write to audit log automatically."),
        bullet("Public status pages understandable without staff login."),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== APPENDIX A =====
        h1("Appendix A: Migration history (v0.1.0 → v1.4.1)"),

        h3("Status Value Migration"),
        codeBlock("-- 'received', 'searching', 'in_review', 'drafted', 'approved' remain valid"),
        codeBlock("-- New: clarification_needed, assigned, ready_for_release, fulfilled, closed"),
        codeBlock("-- Note: legacy 'sent' value removed in migration 010_remove_sent_status"),

        spacer(),
        h3("New Database Tables (12)"),
        p("departments, fee_schedules, fee_line_items, request_timeline, request_messages, response_letters, notification_templates, notification_log, prompt_templates, saved_searches (v1.1), published_records (v1.1), redaction_ledger (v1.1)"),

        spacer(),
        h3("New Columns on Existing Tables"),
        bullet("users: department_id"),
        bullet("documents: display_name, department_id"),
        bullet("records_requests: requester_phone, requester_type, scope_assessment, department_id, estimated_fee, fee_status, fee_waiver_requested, priority, closed_at, closure_reason"),
        bullet("search_results: normalized_score"),
        bullet("exemption_flags: review_note"),
        bullet("model_registry: context_window_size"),

        new Paragraph({ children: [new PageBreak()] }),

        // ===== APPENDIX B =====
        h1("Appendix B: Document Manifest"),
        makeTable(
          ["File", "Purpose"],
          [
            ["docs/UNIFIED-SPEC.md", "This document \u2014 single source of truth (markdown version)"],
            ["docs/DESIGN-CRITIQUE.md", "Historical: design audit of v0.1.0 UI"],
            ["docs/superpowers/specs/2026-04-11-civicrecords-ai-master-design.md", "Original build spec (superseded)"],
            ["QA-VERIFICATION-REPORT.docx", "Historical QA report from v0.1.0 (archived)"],
            ["Municipal Open Records UX Style Guide", "External design direction document"],
          ],
          [5000, 4360]
        ),

        spacer(), spacer(),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 1, color: colors.border, space: 12 } },
          spacing: { before: 400 },
          children: [new TextRun({
            text: "This specification was assembled from the original master design spec (67 commits, 80 tests, 5 sub-projects), a live UI design critique of 8 running pages, the Municipal Open Records UX Style Guide, and context-mode architectural patterns.",
            size: 10 * 2, font: "Arial", italics: true, color: colors.muted,
          })],
        }),
      ],
    },
  ],
});

// Generate
Packer.toBuffer(doc).then(buffer => {
  // Resolve output next to this generator so it works from any repo path
  // (previously hardcoded to a non-OneDrive clone that only existed on the
  // original author's machine — produced ENOENT on every other checkout).
  const path = require("path");
  const outPath = path.join(__dirname, "UNIFIED-SPEC.docx");
  fs.writeFileSync(outPath, buffer);
  console.log(`Written to ${outPath} (${(buffer.length / 1024).toFixed(0)} KB)`);

  // Also write the spec-v3.1-pinned copy used as a release-asset snapshot.
  // The spec is currently at v3.1 (see §1 of UNIFIED-SPEC.md); when the
  // spec bumps to v3.2 or higher, add a new pinned name here and keep the
  // old ones as archival.
  const pinnedV31 = path.join(__dirname, "CivicRecordsAI-UnifiedSpec-v3.1.docx");
  fs.writeFileSync(pinnedV31, buffer);
  console.log(`Written to ${pinnedV31} (${(buffer.length / 1024).toFixed(0)} KB)`);
});
