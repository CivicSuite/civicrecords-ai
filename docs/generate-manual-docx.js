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

// Page properties reused across sections
const pageProps = {
  page: {
    size: { width: 12240, height: 15840 },
    margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
  },
};

const defaultHeader = new Header({
  children: [new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 1, color: colors.border, space: 4 } },
    children: [new TextRun({ text: "CivicRecords AI \u2014 Complete System Manual v1.4.1", size: 9 * 2, font: "Arial", color: colors.muted })],
  })],
});

const defaultFooter = new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { top: { style: BorderStyle.SINGLE, size: 1, color: colors.border, space: 4 } },
    children: [
      new TextRun({ text: "Page ", size: 9 * 2, font: "Arial", color: colors.muted }),
      new TextRun({ children: [PageNumber.CURRENT], size: 9 * 2, font: "Arial", color: colors.muted }),
    ],
  })],
});

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
    // ===== COVER PAGE =====
    {
      properties: pageProps,
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
          children: [new TextRun({ text: "Complete System Manual", size: 28 * 2, font: "Arial", color: colors.primary })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 100 },
          border: { top: { style: BorderStyle.SINGLE, size: 2, color: colors.primary, space: 12 } },
          children: [new TextRun({ text: "Version v1.4.1", size: 14 * 2, font: "Arial", color: colors.muted })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 100 },
          children: [new TextRun({ text: "April 2026", size: 14 * 2, font: "Arial", color: colors.muted })],
        }),
        spacer(), spacer(), spacer(),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 60 },
          children: [new TextRun({ text: "Open-source, locally-hosted AI for municipal open records", size: 12 * 2, font: "Arial", italics: true, color: colors.muted })],
        }),
      ],
    },

    // ===== TABLE OF CONTENTS =====
    {
      properties: pageProps,
      headers: { default: defaultHeader },
      footers: { default: defaultFooter },
      children: [
        h1("Table of Contents"),
        new TableOfContents("Table of Contents", {
          hyperlink: true,
          headingStyleRange: "1-3",
        }),
        new Paragraph({
          spacing: { before: 200 },
          children: [new TextRun({ text: "Note: Update the table of contents in Word by right-clicking it and selecting \"Update Field\".", size: 10 * 2, font: "Arial", italics: true, color: colors.muted })],
        }),
      ],
    },

    // ===== PART I: USER GUIDE =====
    {
      properties: pageProps,
      headers: { default: defaultHeader },
      footers: { default: defaultFooter },
      children: [
        h1("PART I: USER GUIDE"),
        spacer(),

        // --- 1. Welcome ---
        h2("1. Welcome"),
        p("CivicRecords AI helps municipal staff respond to open records requests using AI-powered document search. It is designed to augment human decision-making, not replace it."),
        h3("What It Does"),
        bullet("Search across municipal documents using natural language queries"),
        bullet("Detect potential exemptions (PII, statutory) and flag them for human review"),
        bullet("Track open records requests through their full lifecycle"),
        bullet("Generate draft response letters for human review and approval"),
        h3("What It Does NOT Do"),
        bullet("No autonomous decisions \u2014 every action requires human approval"),
        bullet("No public-facing portal \u2014 staff-only internal tool"),
        bullet("No cloud services \u2014 all data stays on local infrastructure"),
        h3("Audience"),
        bullet("City clerks and records officers"),
        bullet("Department heads and supervisors"),
        bullet("IT administrators responsible for deployment and maintenance"),
        spacer(),

        // --- 2. Signing In ---
        h2("2. Signing In"),
        bullet("Access CivicRecords AI via http://localhost:8080 or your city\u2019s network URL"),
        bullet("Enter the email and password provided by your administrator"),
        bullet("If locked out after 5 failed login attempts, wait 1 minute or contact your administrator"),
        bullet("There is no self-registration \u2014 all accounts are created by an administrator"),
        spacer(),

        // --- 3. Dashboard Overview ---
        h2("3. Dashboard Overview"),
        p("Your dashboard and available actions depend on your assigned role. The following table shows what each role can do:"),
        makeTable(
          ["Role", "Search", "Create Requests", "Review Flags", "Approve Responses", "Manage Users"],
          [
            ["Admin", "Yes", "Yes", "Yes", "Yes", "Yes"],
            ["Staff", "Yes", "Yes", "Yes", "No", "No"],
            ["Reviewer", "Yes", "Yes", "Yes", "Yes", "No"],
            ["Read-Only", "Yes", "No", "No", "No", "No"],
          ],
          [1560, 1560, 1560, 1560, 1560, 1560]
        ),
        spacer(),

        // --- 4. Searching for Records ---
        h2("4. Searching for Records"),
        bullet("Type plain English queries in the search bar"),
        bullet("Results show: document name, page number, relevance score (0\u2013100%), and matched text snippet"),
        bullet("Filter results by date range, file type, department, or data source"),
        bullet("Follow-up searches refine results within the same session"),
        bullet("All AI-generated summaries are labeled as \u201cAI-Generated Draft\u201d"),
        spacer(),

        // --- 5. Managing Records Requests ---
        h2("5. Managing Records Requests"),
        h3("Creating a Request"),
        bullet("Enter requester name, email address, description of the request, and statutory deadline"),
        h3("Request Statuses"),
        p("Each request moves through a defined lifecycle with 11 possible statuses:"),
        makeTable(
          ["Status", "Description"],
          [
            ["Received", "New request logged"],
            ["Clarification Needed", "Awaiting requester clarification"],
            ["Assigned", "Assigned to staff member"],
            ["Searching", "Active document search"],
            ["In Review", "Documents under review"],
            ["Ready for Release", "Reviewed, pending approval"],
            ["Drafted", "Response letter drafted"],
            ["Approved", "Supervisor approved"],
            ["Fulfilled", "Documents delivered"],
            ["Sent", "Response sent to requester"],
            ["Closed", "Request complete"],
          ],
          [3120, 6240]
        ),
        spacer(),

        // --- 6. Reviewing Exemption Flags ---
        h2("6. Reviewing Exemption Flags"),
        p("The system automatically flags potential exemptions in documents. Staff must review and accept or reject every flag \u2014 there is no auto-redaction."),
        h3("PII Flags"),
        bullet("Social Security numbers, phone numbers, email addresses, credit card numbers, dates of birth"),
        h3("Statutory Flags"),
        bullet("State-specific keyword matches based on 180 rules across 51 jurisdictions"),
        h3("Confidence Scores"),
        bullet("Each flag includes a confidence score indicating match strength"),
        bullet("Every flag requires human review regardless of confidence level"),
        spacer(),

        // --- 7. Response Letters ---
        h2("7. Response Letters"),
        bullet("Generate an AI draft or use a template-based letter"),
        pRuns([
          { text: "All drafts are labeled: " },
          { text: "\"AI-GENERATED DRAFT \u2014 REQUIRES HUMAN REVIEW\"", bold: true, color: colors.danger },
        ]),
        bullet("Edit the draft, then submit for supervisor approval"),
        bullet("A Reviewer must approve the letter before it can be sent"),
        spacer(),

        // --- 8. Timeline & Messaging ---
        h2("8. Timeline & Messaging"),
        bullet("Every request has a chronological timeline showing all activity"),
        bullet("Internal messages are visible to staff only"),
        bullet("External messages are visible to the requester"),
        spacer(),

        // --- 9. Fee Tracking ---
        h2("9. Fee Tracking"),
        bullet("Add line items with description, quantity, and unit price"),
        bullet("The system automatically calculates totals"),
        spacer(),

        // --- 10. Department Access ---
        h2("10. Department Access"),
        bullet("Staff see only their own department\u2019s requests and documents"),
        bullet("Shared documents (not assigned to a department) are visible to all staff"),
        bullet("Admins can see everything across all departments"),
        spacer(),

        // --- 11. Quick Reference ---
        h2("11. Quick Reference \u2014 Glossary"),
        makeTable(
          ["Term", "Definition"],
          [
            ["Exemption Flag", "A system-detected potential exemption in a document that requires human review"],
            ["PII", "Personally Identifiable Information (SSN, phone, email, credit card, DOB)"],
            ["Confidence Score", "A numeric score (0\u2013100%) indicating how strong an exemption match is"],
            ["Statutory Deadline", "The legal time limit for responding to an open records request"],
            ["Hybrid Search", "Combined keyword + semantic vector search for better results"],
            ["RRF", "Reciprocal Rank Fusion \u2014 algorithm that merges keyword and vector search rankings"],
            ["Human-in-the-Loop", "Design principle requiring human approval for all AI-assisted decisions"],
            ["Audit Log", "Tamper-evident record of all system actions for legal compliance"],
          ],
          [2800, 6560]
        ),
      ],
    },

    // ===== PART II: IT ADMINISTRATION GUIDE =====
    {
      properties: pageProps,
      headers: { default: defaultHeader },
      footers: { default: defaultFooter },
      children: [
        h1("PART II: IT ADMINISTRATION GUIDE"),
        spacer(),

        // --- 12. System Architecture ---
        h2("12. System Architecture"),
        p("CivicRecords AI runs as 7 Docker containers orchestrated via Docker Compose:"),
        makeTable(
          ["Service", "Image", "Port", "Purpose"],
          [
            ["postgres", "postgres:17 + pgvector", "5432", "All data, vectors, audit logs"],
            ["redis", "redis:7.2 (BSD)", "6379", "Celery task broker"],
            ["ollama", "ollama/ollama", "11434", "Local LLM runtime"],
            ["api", "Dockerfile.backend", "8000", "FastAPI application"],
            ["worker", "(same as api)", "--", "Celery async worker"],
            ["beat", "(same as api)", "--", "Celery scheduler"],
            ["frontend", "nginx + React", "8080", "Static frontend"],
          ],
          [1800, 2800, 960, 3800]
        ),
        spacer(),
        h3("Technology Stack"),
        bullet("Backend: Python 3.12, FastAPI, SQLAlchemy 2.0, Celery, Alembic"),
        bullet("Frontend: React 18, shadcn/ui, Tailwind CSS"),
        bullet("Database: PostgreSQL 17 with pgvector extension"),
        bullet("Cache/Broker: Redis 7.2 (BSD licensed)"),
        bullet("AI Runtime: Ollama (local LLM inference)"),
        spacer(),
        p("See docs/architecture/system-architecture.html for interactive architecture diagrams.", { italics: true, color: colors.muted }),
        spacer(),
        imageParagraph("diagrams/deployment-stack.svg", "Deployment stack"),
        imageCaption("Deployment stack — entire system runs inside Docker Compose on the city's network. No cloud, no outbound by default."),
        imageParagraph("diagrams/llm-flow.svg", "LLM call flow"),
        imageCaption("LLM call flow — records-ai routes through civiccore.llm (context assembly, template resolution, model registry, provider factory) to a local Ollama provider."),
        imageParagraph("diagrams/sovereignty.svg", "Sovereignty boundary"),
        imageCaption("Sovereignty boundary — all runtime components (FastAPI, Celery, Postgres+pgvector, Ollama, local volumes) live inside the city's on-prem network."),
        spacer(),

        // --- 13. Hardware Requirements ---
        h2("13. Hardware Requirements"),
        makeTable(
          ["Component", "Minimum", "Recommended"],
          [
            ["CPU", "8 cores", "12\u201316 cores"],
            ["RAM", "32 GB", "64 GB"],
            ["Storage", "1 TB NVMe", "2 TB NVMe"],
            ["GPU", "Integrated GPU", "Discrete 8 GB+ VRAM"],
          ],
          [2400, 3480, 3480]
        ),
        spacer(),
        h3("GPU Support"),
        bullet("AMD ROCm (Linux)"),
        bullet("DirectML (Windows)"),
        bullet("NVIDIA CUDA"),
        p("Performance target: less than 30 seconds per query on minimum specification hardware."),
        spacer(),

        // --- 14. Installation ---
        h2("14. Installation"),
        h3("Windows"),
        codeBlock("git clone https://github.com/CivicSuite/civicrecords-ai.git"),
        codeBlock("cd civicrecords-ai"),
        codeBlock(".\\install.ps1"),
        h3("Linux / macOS"),
        codeBlock("git clone https://github.com/CivicSuite/civicrecords-ai.git"),
        codeBlock("cd civicrecords-ai"),
        codeBlock("bash install.sh"),
        h3("What the Installer Does"),
        bullet("1. Checks Docker is installed and running"),
        bullet("2. Detects hardware (CPU, RAM, GPU)"),
        bullet("3. Configures GPU acceleration (ROCm, DirectML, or CUDA)"),
        bullet("4. Builds Docker images"),
        bullet("5. Starts PostgreSQL and runs database creation"),
        bullet("6. Runs Alembic migrations"),
        bullet("7. Starts all services"),
        bullet("8. Pulls the AI model (gemma4)"),
        spacer(),

        // --- 15. Configuration Reference ---
        h2("15. Configuration Reference"),
        p("Key environment variables (set in .env file):"),
        makeTable(
          ["Variable", "Description", "Default"],
          [
            ["DATABASE_URL", "PostgreSQL connection string", "postgresql+asyncpg://civicrecords:civicrecords@postgres:5432/civicrecords"],
            ["JWT_SECRET", "JWT signing key", "(required)"],
            ["FIRST_ADMIN_EMAIL", "Initial admin email", "admin@example.gov"],
            ["FIRST_ADMIN_PASSWORD", "Initial admin password", "(required)"],
            ["OLLAMA_BASE_URL", "Ollama endpoint", "http://ollama:11434"],
            ["REDIS_URL", "Redis connection string", "redis://redis:6379/0"],
            ["AUDIT_RETENTION_DAYS", "Log retention period", "1095 (3 years)"],
          ],
          [2800, 3280, 3280]
        ),
        spacer(),

        // --- 16. User & Department Administration ---
        h2("16. User & Department Administration"),
        h3("Creating Users"),
        bullet("Create users via POST /admin/users (admin role required)"),
        bullet("Assign one of 4 roles: Admin, Reviewer, Staff, or Read-Only"),
        h3("Role Hierarchy"),
        p("Admin > Reviewer > Staff > Read-Only"),
        h3("Department Management"),
        bullet("Create departments via the admin panel"),
        bullet("Assign users to departments"),
        bullet("Department scoping controls which requests and documents each user can access"),
        spacer(),

        // --- 17. Data Source Management ---
        h2("17. Data Source Management"),
        h3("Source Types"),
        bullet("File directory sources (local filesystem paths)"),
        bullet("Manual file uploads via the web interface"),
        h3("Supported Formats"),
        bullet("PDF, DOCX, XLSX, CSV, HTML"),
        bullet("Email: EML, MBOX"),
        bullet("Plain text files"),
        bullet("Images (via Gemma 4 vision model)"),
        h3("Monitoring"),
        bullet("Ingestion progress is visible on the admin dashboard"),
        spacer(),

        // --- 18. Model Management ---
        h2("18. Model Management"),
        h3("Supported Gemma 4 Models"),
        p("The installer picker presents all four supported Gemma 4 models. Default is gemma4:e4b. Only e2b and e4b are supportable at the 32 GB baseline target profile; 26b and 31b require stronger hardware and must be selected explicitly."),
        bullet("gemma4:e2b \u2014 Edge / 2.3B effective params / 7.2 GB disk / ~16 GB RAM (supportable)"),
        bullet("gemma4:e4b \u2014 Edge / 4.5B effective params / 9.6 GB disk / ~20 GB RAM (supportable, DEFAULT)"),
        bullet("gemma4:26b \u2014 Workstation MoE / 25.2B total, 3.8B active / 18 GB disk / 48+ GB RAM recommended (not supportable at 32 GB baseline)"),
        bullet("gemma4:31b \u2014 Workstation dense / 30.7B params / 20 GB disk / 64+ GB RAM, GPU recommended (not supportable at 32 GB baseline)"),
        h3("Embedding Model"),
        bullet("nomic-embed-text \u2014 always required for vector search"),
        h3("Model Registry"),
        bullet("Tracks model metadata for compliance and auditing purposes"),
        spacer(),

        // --- 19. Exemption Rules Administration ---
        h2("19. Exemption Rules Administration"),
        bullet("180 rules across 50 states + District of Columbia"),
        h3("Rule Types"),
        bullet("regex \u2014 PII pattern matching (SSN, phone, email, etc.)"),
        bullet("keyword \u2014 statutory phrase matching"),
        bullet("llm_prompt \u2014 LLM-evaluated contextual rules"),
        h3("Administration"),
        bullet("Admins can create, enable/disable, and customize rules"),
        spacer(),

        // --- 20. Compliance & Audit ---
        h2("20. Compliance & Audit"),
        h3("Audit Logs"),
        bullet("Hash-chained audit logs using SHA-256 (append-only, tamper-evident)"),
        h3("Compliance Templates"),
        p("5 built-in compliance document templates:"),
        bullet("AI Use Disclosure"),
        bullet("Response Letter Disclosure"),
        bullet("CAIA Impact Assessment"),
        bullet("AI Governance Policy"),
        bullet("Data Residency Attestation"),
        h3("Template Rendering"),
        bullet("Templates support variable substitution using the city profile"),
        h3("Data Sovereignty"),
        bullet("Data sovereignty verification script confirms all data remains local"),
        spacer(),

        // --- 21. Security ---
        h2("21. Security"),
        bullet("Localhost binding \u2014 no public internet exposure by default"),
        bullet("JWT authentication for all API endpoints"),
        bullet("Rate limiting: 5 requests per minute per IP address"),
        bullet("No default passwords \u2014 admin password set during installation"),
        bullet("No telemetry or analytics \u2014 no outbound data transmission"),
        bullet("Service account API keys are hashed before storage"),
        spacer(),

        // --- 22. Backup & Recovery ---
        h2("22. Backup & Recovery"),
        h3("What to Back Up"),
        bullet("PostgreSQL database (use pg_dump)"),
        bullet(".env configuration files"),
        bullet("Uploaded documents directory"),
        h3("Restoring"),
        bullet("Restore database with pg_restore"),
        bullet("Restart services with docker compose up"),
        spacer(),

        // --- 23. Monitoring & Troubleshooting ---
        h2("23. Monitoring & Troubleshooting"),
        h3("Health Check"),
        codeBlock("GET /health  \u2192  {\"status\": \"ok\", \"version\": \"1.4.1\"}"),
        h3("Common Issues"),
        makeTable(
          ["Symptom", "Cause", "Fix"],
          [
            ["API not responding", "Container stopped", "docker compose up -d api"],
            ["Search returns no results", "No documents ingested", "Add data source and ingest"],
            ["Ollama model not found", "Model not pulled", "ollama pull gemma4:e4b (or the tag selected at install time)"],
            ["Login fails repeatedly", "Rate limited", "Wait 60 seconds"],
            ["Slow search performance", "No GPU, large dataset", "Enable GPU acceleration"],
          ],
          [2800, 2800, 3760]
        ),
        spacer(),

        // --- 24. Upgrading ---
        h2("24. Upgrading"),
        p("To upgrade CivicRecords AI to the latest version:"),
        codeBlock("git pull"),
        codeBlock("docker compose build"),
        codeBlock("docker compose run --rm api alembic upgrade head"),
        codeBlock("docker compose up -d"),
      ],
    },

    // ===== APPENDICES =====
    {
      properties: pageProps,
      headers: { default: defaultHeader },
      footers: { default: defaultFooter },
      children: [
        h1("APPENDICES"),
        spacer(),

        h2("A. Supported Platforms"),
        makeTable(
          ["Platform", "Docker Runtime"],
          [
            ["Windows 10/11", "Docker Desktop"],
            ["macOS 13+", "Docker Desktop"],
            ["Ubuntu 22.04+", "Docker Engine"],
            ["Debian 12+", "Docker Engine"],
          ],
          [4680, 4680]
        ),
      ],
    },
  ],
});

// Generate and save
Packer.toBuffer(doc).then(buffer => {
  const outPath = __dirname + "/civicrecords-ai-manual.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("Generated: " + outPath + " (" + buffer.length + " bytes)");
}).catch(err => {
  console.error("Error generating document:", err);
  process.exit(1);
});
