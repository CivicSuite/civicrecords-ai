; CivicRecords AI — Windows Installer (Tier 5 Blocker E)
; Built with Inno Setup 6.x
; https://jrsoftware.org/ishelp/
;
; T5E (Tier 5 Blocker E) — UNSIGNED BY DESIGN.
; Scott locked signing posture = α (unsigned) on 2026-04-22. This installer
; ships unsigned. Operators WILL see the Windows SmartScreen warning
; ("Windows protected your PC — unrecognized publisher") on first run.
; Remediation is documented in installer/windows/README.md and in the
; top-level README.md; the release page also publishes a SHA-256 checksum
; operators can use to verify the binary independently.
;
; Adapted from the PatentForgeLocal skeleton at
; patentforgelocal/installer/windows/patentforgelocal.iss. CivicRecords-
; specific adaptations:
;   - Does NOT bundle portable Python or portable Ollama (CivicRecords
;     runs on Docker / Compose, not native processes).
;   - DOES bundle the CivicRecords repo snapshot so a fresh machine can
;     reach a working install from a single double-click.
;   - Post-install runs installer/windows/launch-install.ps1, which
;     invokes the existing install.ps1 (T5C 4-model picker + T5B
;     auto-seed) after a prereq-check for Docker Desktop + WSL 2.
;   - Daily starts go through a separate installer/windows/launch-start.ps1
;     (wired to the "Start CivicRecords AI" Start Menu / Desktop shortcut)
;     which only runs "docker compose up -d" and opens the admin panel —
;     no prereq check, no install.ps1, no model re-pull, no re-seed.
;   - Version is supplied at build time via /DMyAppVersion=<semver>; no
;     hardcoded version lives in this file. The authoritative source is
;     backend/pyproject.toml, overridden by the git tag on tagged CI
;     builds. See installer/windows/build-installer.sh and
;     .github/workflows/release.yml.

#define MyAppName "CivicRecords AI"

; MyAppVersion is supplied by the build driver via the Inno Setup CLI flag
;   /DMyAppVersion=<semver>
; The authoritative source is backend/pyproject.toml on tagged releases it
; is overridden by the git tag (leading "v" stripped) via the CI workflow.
; If ISCC is invoked without /DMyAppVersion=..., we fail fast rather than
; ship a stale hardcoded value. See installer/windows/build-installer.sh
; and .github/workflows/release.yml.
#ifndef MyAppVersion
  #error "MyAppVersion must be supplied via /DMyAppVersion=<semver>. Use installer/windows/build-installer.sh or the Release workflow."
#endif

#define MyAppPublisher "CivicRecords AI contributors"
#define MyAppURL "https://scottconverse.github.io/civicrecords-ai/"

[Setup]
AppId={{CIVICRECORDS-AI-B1C2D3E4-F5A6-7890-ABCD-EF0123456789}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\..\build
OutputBaseFilename=CivicRecordsAI-{#MyAppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\..\LICENSE
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
DisableProgramGroupPage=yes
; NOTE: SignTool is intentionally NOT configured. T5E ships unsigned by
; design per Scott's B3 lock (α) on 2026-04-22.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; ── Installer helper scripts (this directory) ─────────────────────────────
; Two separate launchers:
;   launch-install.ps1 → full bootstrap / repair (prereq check + install.ps1)
;   launch-start.ps1   → daily start (docker compose up -d + open browser)
Source: "launch-install.ps1"; DestDir: "{app}\installer\windows"; Flags: ignoreversion
Source: "launch-start.ps1"; DestDir: "{app}\installer\windows"; Flags: ignoreversion
Source: "prereq-check.ps1"; DestDir: "{app}\installer\windows"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}\installer\windows"; Flags: ignoreversion

; ── CivicRecords runtime (top of repo) ────────────────────────────────────
Source: "..\..\install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\install.sh"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\docker-compose.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\docker-compose.gpu.yml"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\docker-compose.host-ollama.yml"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion
Source: "..\..\Dockerfile.backend"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\Dockerfile.frontend"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\USER-MANUAL.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; ── Helper scripts ────────────────────────────────────────────────────────
Source: "..\..\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Backend source (for Docker build) ─────────────────────────────────────
Source: "..\..\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.pyc,__pycache__\*,.venv\*,node_modules\*,*.sqlite*,.pytest_cache\*"

; ── Frontend source (for Docker build) ────────────────────────────────────
Source: "..\..\frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "node_modules\*,dist\*,*.log"

; ── Docs (operator reference) ─────────────────────────────────────────────
Source: "..\..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "deprecated\*"

[Dirs]
; User data directories — survive uninstall unless the user explicitly
; opts in to delete them in the uninstall confirmation dialog below.
Name: "{app}\data"; Flags: uninsneveruninstall
Name: "{app}\logs"; Flags: uninsneveruninstall
Name: "{app}\config"; Flags: uninsneveruninstall

[Icons]
; Daily-start shortcut: brings up the Docker Compose stack and opens the
; admin panel. No install, no model pull, no data seed.
Name: "{group}\Start CivicRecords AI"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\installer\windows\launch-start.ps1"""; WorkingDir: "{app}"; Comment: "Bring up the Docker Compose stack and open the admin panel. No install/repair."

; Install-or-repair shortcut: runs the full bootstrap flow (prereq check +
; install.ps1 + Gemma 4 picker + model pull + baseline seeding). Use this
; for first runs, LLM changes, or stack repair.
Name: "{group}\Install or Repair CivicRecords AI"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\installer\windows\launch-install.ps1"""; WorkingDir: "{app}"; Comment: "Run the full install/repair flow: prereq check, Docker bring-up, Gemma 4 picker + model pull, baseline seed."

Name: "{group}\Stop CivicRecords AI"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command ""cd '{app}'; docker compose down"""; WorkingDir: "{app}"; Comment: "Stop the Docker Compose stack (containers only; volumes preserved)."
Name: "{group}\Open Admin Panel"; Filename: "http://localhost:8080/"
Name: "{group}\Installer Readme"; Filename: "{app}\installer\windows\README.md"
Name: "{group}\Uninstall CivicRecords AI"; Filename: "{uninstallexe}"

; Desktop shortcut mirrors the daily-start behavior, not install/repair.
Name: "{autodesktop}\Start CivicRecords AI"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\installer\windows\launch-start.ps1"""; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Bring up the Docker Compose stack and open the admin panel. No install/repair."

[Run]
; Post-install flow: complete first-run bootstrap. This runs the full
; install/repair path (prereq check, install.ps1, Gemma 4 picker + model
; pull, baseline seeding). It is NOT the same as the 'Start' shortcut —
; daily starts from then on should use 'Start CivicRecords AI'.
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\installer\windows\launch-install.ps1"""; Description: "Complete first-run install (prereq check, LLM picker + model pull, baseline seed)"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Application source files are removed automatically by the uninstaller.
; The persistent user-data dirs (data/, logs/, config/) are handled by the
; [Code] block below so the operator can opt in to data removal.

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RunningServices: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Step 1 prompt: stop the Compose stack (containers only). Volumes are
    // NOT removed by "docker compose down" (that requires the -v flag), so
    // saying Yes here only stops containers and releases ports.
    if MsgBox('Stop the CivicRecords AI Docker Compose stack now?' + #13#10 +
              '' + #13#10 +
              'REMOVES (on Yes):' + #13#10 +
              '  - Running containers (api, worker, beat, frontend,' + #13#10 +
              '    postgres, redis, ollama) — stopped via "docker' + #13#10 +
              '    compose down" in the install dir.' + #13#10 +
              '  - Host ports 8000 and 8080 are released.' + #13#10 +
              '' + #13#10 +
              'PRESERVES (always):' + #13#10 +
              '  - Docker-managed named volumes: the Postgres database' + #13#10 +
              '    (requests, users, audit log, vector store) AND the' + #13#10 +
              '    Ollama models you pulled. "docker compose down"' + #13#10 +
              '    (without -v) does not touch volumes.' + #13#10 +
              '' + #13#10 +
              'If you say No, containers keep running; stop them later' + #13#10 +
              'with "docker compose down" in the install dir.',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('powershell.exe',
           ExpandConstant('-ExecutionPolicy Bypass -NoProfile -Command "cd ''{app}''; docker compose down"'),
           '', SW_HIDE, ewWaitUntilTerminated, RunningServices);
    end;

    // Step 2 prompt: remove only the app-local file-system directories
    // that live under {app}. These are NOT the database. They are local
    // project workspace, logs, and config overrides written by the app
    // during operation. The Postgres database lives in a Docker-managed
    // volume and is never touched by this option.
    if MsgBox('Also delete local app files under the install directory?' + #13#10 +
              '' + #13#10 +
              'REMOVES (on Yes, CANNOT be undone):' + #13#10 +
              '  - {app}\data   (local project workspace files)' + #13#10 +
              '  - {app}\logs   (application log files)' + #13#10 +
              '  - {app}\config (runtime config overrides)' + #13#10 +
              '' + #13#10 +
              'PRESERVES (always — NOT removed by this option):' + #13#10 +
              '  - The Postgres database (in a Docker volume — NOT in' + #13#10 +
              '    {app}\data). All requests, users, audit entries,' + #13#10 +
              '    and the vector store survive this uninstall.' + #13#10 +
              '  - Ollama models you pulled (in a Docker volume).' + #13#10 +
              '' + #13#10 +
              'For a FULL wipe that also removes the database and model' + #13#10 +
              'volumes, run "docker compose down -v" from the install' + #13#10 +
              'dir BEFORE uninstalling (while the compose file is still' + #13#10 +
              'on disk).',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{app}\data'), True, True, True);
      DelTree(ExpandConstant('{app}\config'), True, True, True);
      DelTree(ExpandConstant('{app}\logs'), True, True, True);
    end;
  end;
end;
