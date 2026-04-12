import { useState, useRef, useCallback } from "react";

interface FileUploadProps {
  token: string;
  onUploadComplete?: () => void;
}

export default function FileUpload({ token, onUploadComplete }: FileUploadProps) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const ACCEPTED = ".pdf,.docx,.xlsx,.csv,.txt,.html,.htm,.eml,.md,.json,.xml";

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
    setResult(null);
  }, []);

  const handleSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) setFile(selected);
    setResult(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const resp = await fetch("/api/datasources/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || "Upload failed");
      }

      await resp.json();
      setResult({ ok: true, message: `Queued for ingestion: ${file.name}` });
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      onUploadComplete?.();
    } catch (err: unknown) {
      setResult({ ok: false, message: err instanceof Error ? err.message : "Upload failed" });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          dragging
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-gray-400 bg-white"
        }`}
        role="button"
        aria-label="Drop a file here or click to browse"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          onChange={handleSelect}
          className="hidden"
          aria-hidden="true"
        />
        <div className="text-3xl mb-2">📄</div>
        {file ? (
          <p className="text-sm text-gray-900 font-medium">{file.name} ({(file.size / 1024).toFixed(1)} KB)</p>
        ) : (
          <>
            <p className="text-sm text-gray-600 font-medium">Drop a file here, or click to browse</p>
            <p className="text-xs text-gray-400 mt-1">PDF, DOCX, XLSX, CSV, TXT, HTML, EML</p>
          </>
        )}
      </div>

      {file && (
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="btn btn-primary w-full"
        >
          {uploading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="spinner" aria-hidden="true" /> Uploading...
            </span>
          ) : (
            `Upload ${file.name}`
          )}
        </button>
      )}

      {result && (
        <div
          className={`text-sm p-3 rounded-lg ${result.ok ? "bg-green-50 text-green-700 border border-green-200" : "error-banner"}`}
          role="alert"
        >
          {result.message}
        </div>
      )}
    </div>
  );
}
