"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ApplicationSection } from "@/components/ApplicationSection";
import { api } from "@/lib/api";
import {
  DOCUMENT_TYPE_LABELS,
  type DocumentType,
  type EmployeeDocument,
} from "@/types/documents";

const DOCUMENT_TYPES = Object.keys(DOCUMENT_TYPE_LABELS) as DocumentType[];

type DocumentsSectionProps = {
  mode: "employee" | "hr";
  employeeId?: number;
  allowDelete?: boolean;
  preferredDocumentType?: DocumentType;
  onChanged?: () => void | Promise<void>;
};

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentsSection({
  mode,
  employeeId,
  allowDelete = false,
  preferredDocumentType = "id_document",
  onChanged,
}: DocumentsSectionProps) {
  const [documents, setDocuments] = useState<EmployeeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [documentType, setDocumentType] = useState<DocumentType>(preferredDocumentType);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDocumentType(preferredDocumentType);
  }, [preferredDocumentType]);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      if (mode === "employee") {
        setDocuments(await api.listMyDocuments());
      } else {
        if (!employeeId) {
          setDocuments([]);
          return;
        }
        setDocuments(await api.listEmployeeDocuments(employeeId));
      }
    } catch (err) {
      setDocuments([]);
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [mode, employeeId]);

  useEffect(() => {
    load();
  }, [load]);

  const openDocument = async (document: EmployeeDocument, download: boolean) => {
    setBusyId(document.id);
    setError("");
    try {
      const result =
        mode === "employee"
          ? await api.getMyDocumentUrl(document.id, download)
          : await api.getEmployeeDocumentUrl(employeeId as number, document.id, download);
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open document");
    } finally {
      setBusyId(null);
    }
  };

  const handleUpload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      if (mode === "employee") {
        await api.uploadMyDocument(documentType, file);
      } else {
        await api.uploadEmployeeDocument(employeeId as number, documentType, file);
      }
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      await load();
      await onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload document");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (document: EmployeeDocument) => {
    if (!allowDelete || mode !== "hr" || !employeeId) return;
    if (!window.confirm(`Delete ${document.original_filename}?`)) return;
    setBusyId(document.id);
    setError("");
    try {
      await api.deleteEmployeeDocument(employeeId, document.id);
      await load();
      await onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <ApplicationSection title="Documents">
      <p className="mb-4 text-sm text-gray-600">
        Upload PDF, DOC, DOCX, JPG, or PNG files up to 5 MB. Files are stored privately.
      </p>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleUpload} className="mb-6 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1" htmlFor="document-type">
            Document type
          </label>
          <select
            id="document-type"
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value as DocumentType)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            {DOCUMENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {DOCUMENT_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1" htmlFor="document-file">
            File
          </label>
          <input
            id="document-file"
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm"
          />
          {file && (
            <p className="mt-1 text-xs text-gray-600 truncate">{file.name}</p>
          )}
        </div>
        <button
          type="submit"
          disabled={uploading || !file}
          className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {uploading ? "Uploading..." : file ? "Upload" : "Choose a file first"}
        </button>
      </form>

      {loading ? (
        <div className="py-8 flex justify-center">
          <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-brand-600" />
        </div>
      ) : documents.length === 0 ? (
        <p className="text-sm text-gray-500">No documents uploaded yet.</p>
      ) : (
        <ul className="space-y-3">
          {documents.map((document) => (
            <li
              key={document.id}
              className="border border-gray-200 rounded-lg p-4 flex flex-wrap items-center justify-between gap-3"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">{document.original_filename}</p>
                <p className="mt-1 text-xs text-gray-500">
                  {DOCUMENT_TYPE_LABELS[document.document_type]} · {formatBytes(document.size_bytes)} ·{" "}
                  {formatDateTime(document.uploaded_at)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busyId === document.id}
                  onClick={() => openDocument(document, false)}
                  className="border border-gray-300 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
                >
                  View
                </button>
                <button
                  type="button"
                  disabled={busyId === document.id}
                  onClick={() => openDocument(document, true)}
                  className="border border-gray-300 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
                >
                  Download
                </button>
                {allowDelete && mode === "hr" && (
                  <button
                    type="button"
                    disabled={busyId === document.id}
                    onClick={() => handleDelete(document)}
                    className="border border-red-200 text-red-700 px-3 py-1.5 rounded-lg text-sm hover:bg-red-50 disabled:opacity-50"
                  >
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </ApplicationSection>
  );
}
