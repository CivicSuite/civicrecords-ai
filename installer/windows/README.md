# CivicRecords AI — Windows Installer (T5E)

**This installer is UNSIGNED by design.** Scott locked T5E signing
posture = α (unsigned) on 2026-04-22. This file exists specifically so
operators know that truth before they double-click and so they have a
concrete path through the SmartScreen / "Windows protected your PC"
warning they **will** see on first run.

If you want a signed installer, wait for a future release — this one
does not pretend to offer it.

---

## What you will see on first run

When you double-click `CivicRecordsAI-<version>-Setup.exe`:

1. A blue **"Windows protected your PC"** dialog appears, sourced from
   Microsoft SmartScreen. The headline reads:

   > Microsoft Defender SmartScreen prevented an unrecognized app from
   > starting. Running this app might put your PC at risk.

2. Two buttons: **Run anyway** and **Don't run**. **Run anyway is not
   visible until you click the small "More info" link** in the top-left
   of the dialog.

This is expected. It is a consequence of the unsigned posture, not of a
defect in the installer or of a real risk. You are in control.

## How to get past SmartScreen — concrete steps

1. Click the **"More info"** link at the top of the SmartScreen dialog.
2. A second line appears naming the **Publisher** as **"Unknown
   publisher"** and the **App** as `CivicRecordsAI-<version>-Setup.exe`.
3. Click the **"Run anyway"** button that just appeared at the bottom.
4. The Windows User Account Control (UAC) elevation dialog appears next
   (the installer requires admin). Confirm it.

If you want a second check before clicking "Run anyway," use **the
published SHA-256 checksum** to verify you have the same binary the
release page advertises:

```powershell
Get-FileHash -Algorithm SHA256 .\CivicRecordsAI-<version>-Setup.exe
```

Compare the output against the SHA-256 value printed alongside the
asset on the corresponding
[GitHub release page](https://github.com/CivicSuite/civicrecords-ai/releases).
If the values match, the binary is byte-identical to the one produced
by the public CI pipeline at the tagged commit. If they differ, **do
not run it** — download again from the release page directly.

## What the installer does on first run

1. Copies the CivicRecords AI source tree (backend, frontend, docs,
   scripts, `install.ps1`, `docker-compose.yml`, etc.) to
   `C:\Program Files\CivicRecords AI\`.
2. Creates Start Menu shortcuts and (optionally) a Desktop shortcut.
3. Runs the post-install bootstrap via `installer\windows\launch-install.ps1`,
   which in turn runs:
   - `prereq-check.ps1` — reports on **Docker Desktop**, **WSL 2 +
     Virtual Machine Platform**, **32 GB RAM floor** (Tier 5 target
     profile), and **host Ollama** (optional; preferred when present).
   - `install.ps1` — the existing bring-up script that owns:
     * `docker compose pull` and `docker compose up -d` for the full
       stack (api, worker, beat, frontend, postgres, redis, ollama).
     * An **automatic `ollama pull nomic-embed-text`** for the embedding
       model (required for search; not optional).
     * The **T5C 4-model Gemma 4 picker** (`gemma4:e4b` default), with
       an **automatic `ollama pull <selected-tag>` for the model you
       choose**. Expect several minutes on first run; the binary ranges
       from ~7 GB (`gemma4:e2b`) to ~20 GB (`gemma4:31b`).
     * T5B first-boot baseline seeding (175 exemption rules + 5
       compliance templates + 12 notification templates, idempotent on
       restart).
4. Opens the admin panel at `http://localhost:8080/` in your default
   browser when the stack is healthy.

## Two shortcuts, two flows — don't mix them up

The installer creates **two separate shortcuts** for two different
purposes. They do different things and run different scripts:

| Shortcut | Script | What it does |
|---|---|---|
| **Start CivicRecords AI** | `launch-start.ps1` | Daily start. Runs `docker compose up -d` (idempotent — no-ops if the stack is already running) and opens `http://localhost:8080/`. Does **not** run the prereq check. Does **not** invoke `install.ps1`. Does **not** pull any model. Does **not** re-seed data. |
| **Install or Repair CivicRecords AI** | `launch-install.ps1` | Full install/repair flow. Runs the prereq check, then `install.ps1` (which may show the Gemma 4 picker and may pull models). Use this after a fresh install (the installer fires it automatically for you the first time), after choosing a different LLM, or to repair a broken stack. |

The Desktop shortcut, if you opted into it, mirrors **Start CivicRecords
AI** — not the install/repair flow. Clicking it daily will not re-run
the installer or re-pull models.

## What the installer does NOT do

- **Does not install Docker Desktop for you.** You must install Docker
  Desktop separately; the prereq check will tell you if it's missing.
- **Does not enable WSL 2 or the Virtual Machine Platform feature
  silently.** These require elevated commands and typically a reboot;
  the prereq check prints the exact commands to run.
- **Does not sign the installer.** See the first paragraph.
- **Does not modify Windows Defender, firewall, or any system-wide
  setting** beyond the files it installs to `Program Files\CivicRecords AI\`
  and the Start Menu entries it creates.
- **Does not pull any model on daily starts.** Model pulls only happen
  inside `install.ps1`, which is only reached via the "Install or
  Repair CivicRecords AI" shortcut (or the post-install step of the
  installer wizard itself). The "Start CivicRecords AI" shortcut never
  runs `ollama pull`.

## Uninstall — what it removes, what it preserves

Use **Settings → Apps → Installed apps → CivicRecords AI → Uninstall**
or the shortcut **Uninstall CivicRecords AI** in the Start Menu.

The uninstaller asks two questions in sequence. Read them carefully —
the wording in the dialogs is the authoritative contract, and it tracks
this table:

| Step | Yes does | No does |
|---|---|---|
| **1. Stop the Compose stack?** | Runs `docker compose down` in the install dir. Stops the 7 containers. Releases host ports 8000 and 8080. **Does NOT remove Docker volumes** — `docker compose down` without `-v` never touches volumes. | Containers keep running. You can stop them later yourself with `docker compose down` (the Compose file stays on disk inside Docker Desktop's image cache even after uninstall, but you will not have the compose YAML on disk any more — so stop the stack first if you want a clean exit). |
| **2. Delete local app files under the install dir?** | `DelTree` removes `{app}\data`, `{app}\logs`, `{app}\config` from `Program Files\CivicRecords AI\`. These are local project-workspace files, app log files, and runtime config overrides. **These are NOT the database.** | These directories are preserved. They survive the uninstall untouched — `[Dirs] uninsneveruninstall` in the `.iss` file. |

**What is always preserved, regardless of your answers above:**

- **The Postgres database** (all requests, users, audit log entries,
  and the pgvector embedding store) lives in a **Docker-managed named
  volume**, not in `{app}\data`. `docker compose down` does not touch
  it, and `DelTree` on `{app}\data` does not touch it.
- **The Ollama models you pulled** live in a separate Docker-managed
  volume. Same story — nothing the uninstaller asks about removes them.

**For a FULL wipe that also removes the database and model volumes,**
run this **before** starting the uninstaller, while the compose file is
still on disk:

```powershell
cd "C:\Program Files\CivicRecords AI"
docker compose down -v
```

The `-v` flag deletes the named volumes. Only then start the
uninstaller. Once the app files are gone, you can still remove the
Docker volumes manually with `docker volume ls` + `docker volume rm`,
but the CivicRecords volume names are no longer conveniently discoverable.

## Verify the release before installing (optional)

Every CI-built release exposes the built installer + a SHA-256 checksum
on the release page. The build is produced by
`.github/workflows/release.yml` on a GitHub-hosted `windows-latest`
runner via `choco install innosetup -y` + the bash driver at
`installer/windows/build-installer.sh`. The build is reproducible from
any tagged commit.

## Version + provenance

- Installer source: `installer/windows/civicrecords-ai.iss`
- Build driver:     `installer/windows/build-installer.sh`
- Release pipeline: `.github/workflows/release.yml`
- Upstream baseline: the Inno Setup skeleton + release pattern are
  adapted from the PatentForgeLocal installer (same toolchain, same
  pipeline shape, same unsigned posture). CivicRecords-specific
  adaptations are documented inline in the `.iss` file.
