#!/usr/bin/env node
/**
 * docs/generate-deliverables.js
 * Generates Rule 9 deliverables from README.md and USER-MANUAL.md.
 * Outputs: README.txt, README.docx, README.pdf, USER-MANUAL.docx, USER-MANUAL.pdf
 * Requires: docs/node_modules (docx@9.6.1, puppeteer) — already installed.
 *
 * Usage (from repo root):  node docs/generate-deliverables.js
 */

'use strict';
const fs   = require('fs');
const path = require('path');

// Resolve node_modules relative to this script so it works from any cwd
const NM   = path.join(__dirname, 'node_modules');
const { Document, Packer, Paragraph, TextRun, HeadingLevel } = require(path.join(NM, 'docx'));
const puppeteer = require(path.join(NM, 'puppeteer'));

// Repo root is one level up from docs/
const ROOT = path.join(__dirname, '..');

// ── Plain text (copy as-is — markdown is readable plain text) ────────────────
function generateTxt(src, dest) {
  fs.copyFileSync(src, dest);
  console.log('✓', path.relative(ROOT, dest));
}

// ── DOCX ─────────────────────────────────────────────────────────────────────

/**
 * Minimal markdown → docx paragraph array.
 * Handles: # ## ### headings, - bullet lists, blank lines, plain text.
 * Bold (**text**) and inline code (`text`) stripped to plain text —
 * the docx is a structural deliverable, not a pixel-perfect render.
 */
function mdToDocxParagraphs(md) {
  const paragraphs = [];
  for (const raw of md.split('\n')) {
    const line = raw
      .replace(/\*\*(.+?)\*\*/g, '$1')        // strip bold markers
      .replace(/`([^`]+)`/g, '$1')             // strip inline code markers
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'); // strip links → label only

    if (line.startsWith('# ')) {
      paragraphs.push(new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: line.slice(2).trim(), bold: true, size: 48 })],
      }));
    } else if (line.startsWith('## ')) {
      paragraphs.push(new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun({ text: line.slice(3).trim(), bold: true, size: 36 })],
      }));
    } else if (line.startsWith('### ')) {
      paragraphs.push(new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun({ text: line.slice(4).trim(), bold: true, size: 28 })],
      }));
    } else if (/^[-*] /.test(line)) {
      paragraphs.push(new Paragraph({
        bullet: { level: 0 },
        children: [new TextRun({ text: line.slice(2).trim() })],
      }));
    } else if (line.trim() === '' || line.startsWith('---')) {
      paragraphs.push(new Paragraph({ children: [new TextRun('')] }));
    } else {
      paragraphs.push(new Paragraph({ children: [new TextRun({ text: line })] }));
    }
  }
  return paragraphs;
}

async function generateDocx(src, dest) {
  const md  = fs.readFileSync(src, 'utf8');
  const doc = new Document({
    creator: 'CivicRecords AI',
    title:   path.basename(src, '.md'),
    sections: [{ children: mdToDocxParagraphs(md) }],
  });
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(dest, buf);
  console.log('✓', path.relative(ROOT, dest));
}

// ── PDF (puppeteer) ───────────────────────────────────────────────────────────

/** Minimal markdown → styled HTML for puppeteer PDF rendering. */
function mdToHtml(md, title) {
  const escaped = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  const body = escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
    .replace(/^# (.+)$/gm,   '<h1>$1</h1>')
    .replace(/^## (.+)$/gm,  '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/^---+$/gm, '<hr>')
    .replace(/\n\n/g, '\n</p>\n<p>');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${title}</title>
<style>
  body { font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.6;
         max-width: 750px; margin: 0 auto; padding: 20px; color: #1F2933; }
  h1   { font-size: 22pt; color: #163D59; border-bottom: 2px solid #1F5A84;
         padding-bottom: 6px; margin-top: 32px; }
  h2   { font-size: 16pt; color: #1F5A84; margin-top: 24px; }
  h3   { font-size: 13pt; color: #1F2933; margin-top: 18px; }
  code { background: #F0F4F8; padding: 2px 5px; border-radius: 3px;
         font-family: Consolas, monospace; font-size: 10pt; }
  pre  { background: #F0F4F8; padding: 12px; border-radius: 4px; overflow-x: auto; }
  li   { margin: 3px 0; }
  hr   { border: none; border-top: 1px solid #CBD5E0; margin: 20px 0; }
  a    { color: #1F5A84; }
</style>
</head>
<body>
<p>${body}</p>
</body>
</html>`;
}

async function generatePdf(src, dest) {
  const md      = fs.readFileSync(src, 'utf8');
  const title   = path.basename(src, '.md');
  const html    = mdToHtml(md, title);
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'networkidle0' });
  await page.pdf({
    path:   dest,
    format: 'A4',
    margin: { top: '20mm', bottom: '20mm', left: '20mm', right: '20mm' },
    printBackground: true,
  });
  await browser.close();
  console.log('✓', path.relative(ROOT, dest));
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  console.log('Generating Rule 9 deliverables...\n');

  // README derivatives
  generateTxt(
    path.join(ROOT, 'README.md'),
    path.join(ROOT, 'README.txt')
  );
  await generateDocx(
    path.join(ROOT, 'README.md'),
    path.join(ROOT, 'README.docx')
  );
  await generatePdf(
    path.join(ROOT, 'README.md'),
    path.join(ROOT, 'README.pdf')
  );

  // USER-MANUAL derivatives
  await generateDocx(
    path.join(ROOT, 'USER-MANUAL.md'),
    path.join(ROOT, 'USER-MANUAL.docx')
  );
  await generatePdf(
    path.join(ROOT, 'USER-MANUAL.md'),
    path.join(ROOT, 'USER-MANUAL.pdf')
  );

  console.log('\nDone. Run gate dry-run to verify:');
  console.log('  node -e "const f=require(\'fs\');[\'README.txt\',\'README.docx\',\'README.pdf\',\'USER-MANUAL.docx\',\'USER-MANUAL.pdf\'].forEach(n=>console.log(n,f.existsSync(n)?\'OK\':\'MISSING\'))"');
}

main().catch(err => {
  console.error('\nFATAL:', err.message);
  process.exit(1);
});
