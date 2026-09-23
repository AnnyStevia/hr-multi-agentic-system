"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { FileText, FolderLock, Library, Search } from "lucide-react";
import { api } from "@/lib/api";
import type {
  CompanyDocument,
  CompanyDocumentCategory,
  CompanyDocumentStatus,
  PrivateDocument,
} from "@/types/libraryDocuments";

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

type DocumentsWorkspaceProps = {
  canManageLibrary: boolean;
};

export function DocumentsWorkspace({ canManageLibrary }: DocumentsWorkspaceProps) {
  const [categories, setCategories] = useState<CompanyDocumentCategory[]>([]);
  const [companyDocs, setCompanyDocs] = useState<CompanyDocument[]>([]);
  const [privateDocs, setPrivateDocs] = useState<PrivateDocument[]>([]);
  const [loadingCompany, setLoadingCompany] = useState(true);
  const [loadingPrivate, setLoadingPrivate] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [statusFilter, setStatusFilter] = useState<CompanyDocumentStatus | "">("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const [showCompanyUpload, setShowCompanyUpload] = useState(false);
  const [showPrivateUpload, setShowPrivateUpload] = useState(false);
  const [editingCompany, setEditingCompany] = useState<CompanyDocument | null>(null);
  const [editingPrivate, setEditingPrivate] = useState<PrivateDocument | null>(null);

  const loadCategories = useCallback(async () => {
    setCategories(await api.listCompanyDocumentCategories());
  }, []);

  const loadCompany = useCallback(async () => {
    setLoadingCompany(true);
    try {
      setCompanyDocs(
        await api.listCompanyDocuments({
          q: search.trim() || undefined,
          category_id: categoryId === "" ? undefined : categoryId,
          status: canManageLibrary
            ? statusFilter || undefined
            : "active",
        }),
      );
    } finally {
      setLoadingCompany(false);
    }
  }, [search, categoryId, statusFilter, canManageLibrary]);

  const loadPrivate = useCallback(async () => {
    setLoadingPrivate(true);
    try {
      setPrivateDocs(await api.listMyPrivateDocuments());
    } catch (err) {
      // HR/admin without employee profile cannot use private docs
      setPrivateDocs([]);
      if (err instanceof Error && !err.message.toLowerCase().includes("employee profile")) {
        throw err;
      }
    } finally {
      setLoadingPrivate(false);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setError("");
    try {
      await loadCategories();
      await Promise.all([loadCompany(), loadPrivate()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    }
  }, [loadCategories, loadCompany, loadPrivate]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const categoryOptions = useMemo(
    () => [...categories].sort((a, b) => a.sort_order - b.sort_order),
    [categories],
  );

  const openCompany = async (doc: CompanyDocument, download: boolean) => {
    setBusyId(`c-${doc.id}`);
    setError("");
    try {
      const result = await api.getCompanyDocumentUrl(doc.id, download);
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open document");
    } finally {
      setBusyId(null);
    }
  };

  const openPrivate = async (doc: PrivateDocument, download: boolean) => {
    setBusyId(`p-${doc.id}`);
    setError("");
    try {
      const result = await api.getMyPrivateDocumentUrl(doc.id, download);
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open document");
    } finally {
      setBusyId(null);
    }
  };

  const archiveCompany = async (doc: CompanyDocument) => {
    setBusyId(`c-${doc.id}`);
    setError("");
    try {
      await api.updateCompanyDocument(doc.id, {
        status: doc.status === "archived" ? "active" : "archived",
      });
      await loadCompany();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update document");
    } finally {
      setBusyId(null);
    }
  };

  const deleteCompany = async (doc: CompanyDocument) => {
    if (!window.confirm(`Permanently delete “${doc.title}”?`)) return;
    setBusyId(`c-${doc.id}`);
    setError("");
    try {
      await api.deleteCompanyDocument(doc.id);
      await loadCompany();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document");
    } finally {
      setBusyId(null);
    }
  };

  const deletePrivate = async (doc: PrivateDocument) => {
    if (!window.confirm(`Delete private document “${doc.title}”?`)) return;
    setBusyId(`p-${doc.id}`);
    setError("");
    try {
      await api.deleteMyPrivateDocument(doc.id);
      await loadPrivate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-8">
      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <section className="bg-white rounded-xl border border-brand-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-brand-100 flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-lg bg-brand-50 p-2 text-brand-700">
              <Library className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-brand-900">Company Document Library</h2>
              <p className="mt-1 text-sm text-brand-300">
                Company-wide policies and resources.
                {canManageLibrary
                  ? " You can upload, edit, archive, and delete."
                  : " View and download only."}
              </p>
            </div>
          </div>
          {canManageLibrary ? (
            <button
              type="button"
              onClick={() => setShowCompanyUpload(true)}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 transition"
            >
              Upload Document
            </button>
          ) : null}
        </div>

        <div className="px-6 py-4 border-b border-brand-100 flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-brand-300" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents…"
              className="w-full rounded-lg border border-brand-200 pl-9 pr-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <select
            value={categoryId}
            onChange={(e) =>
              setCategoryId(e.target.value === "" ? "" : Number(e.target.value))
            }
            className="rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">All categories</option>
            {categoryOptions.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.label}
              </option>
            ))}
          </select>
          {canManageLibrary ? (
            <select
              value={statusFilter}
              onChange={(e) =>
                setStatusFilter((e.target.value || "") as CompanyDocumentStatus | "")
              }
              className="rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          ) : null}
        </div>

        <div className="p-6">
          {loadingCompany ? (
            <div className="py-10 flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
            </div>
          ) : companyDocs.length === 0 ? (
            <EmptyState
              icon={<FileText className="h-8 w-8 text-brand-300" />}
              title="No company documents yet"
              description={
                canManageLibrary
                  ? "Upload the first policy or handbook for everyone to browse."
                  : "HR has not published any company documents yet."
              }
            />
          ) : (
            <ul className="space-y-3">
              {companyDocs.map((doc) => (
                <li
                  key={doc.id}
                  className="rounded-xl border border-brand-100 bg-brand-50/40 px-4 py-3 flex flex-wrap items-center gap-3 justify-between"
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <FileText className="h-5 w-5 text-brand-600 shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium text-brand-900 truncate">{doc.title}</p>
                        <span className="inline-flex items-center rounded-full bg-white border border-brand-200 px-2 py-0.5 text-[11px] font-medium text-brand-700">
                          {doc.category_label}
                        </span>
                        {doc.status === "archived" ? (
                          <span className="inline-flex items-center rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                            Archived
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 text-xs text-brand-300">
                        {doc.original_filename} · {formatBytes(doc.size_bytes)} · v{doc.version}
                        {" · "}
                        {formatDate(doc.updated_at)}
                        {doc.uploaded_by_name ? ` · ${doc.uploaded_by_name}` : ""}
                      </p>
                      {doc.description ? (
                        <p className="mt-1 text-sm text-brand-700 line-clamp-2">{doc.description}</p>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <ActionButton
                      disabled={busyId === `c-${doc.id}`}
                      onClick={() => openCompany(doc, false)}
                    >
                      View
                    </ActionButton>
                    <ActionButton
                      disabled={busyId === `c-${doc.id}`}
                      onClick={() => openCompany(doc, true)}
                    >
                      Download
                    </ActionButton>
                    {canManageLibrary ? (
                      <>
                        <ActionButton
                          disabled={busyId === `c-${doc.id}`}
                          onClick={() => setEditingCompany(doc)}
                        >
                          Edit
                        </ActionButton>
                        <ActionButton
                          disabled={busyId === `c-${doc.id}`}
                          onClick={() => archiveCompany(doc)}
                        >
                          {doc.status === "archived" ? "Restore" : "Archive"}
                        </ActionButton>
                        <ActionButton
                          danger
                          disabled={busyId === `c-${doc.id}`}
                          onClick={() => deleteCompany(doc)}
                        >
                          Delete
                        </ActionButton>
                      </>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="bg-white rounded-xl border border-brand-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-brand-100 flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-lg bg-slate-100 p-2 text-slate-700">
              <FolderLock className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-brand-900">My Private Documents</h2>
              <p className="mt-1 text-sm text-brand-300">
                Only you can access these files. They are not visible to HR or Admin.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowPrivateUpload(true)}
            className="rounded-lg border border-brand-300 bg-white px-4 py-2 text-sm font-medium text-brand-800 hover:bg-brand-50 transition"
          >
            Upload Document
          </button>
        </div>

        <div className="p-6">
          {loadingPrivate ? (
            <div className="py-10 flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
            </div>
          ) : privateDocs.length === 0 ? (
            <EmptyState
              icon={<FolderLock className="h-8 w-8 text-brand-300" />}
              title="No private documents"
              description="Upload personal files that only you can view and download."
            />
          ) : (
            <ul className="space-y-3">
              {privateDocs.map((doc) => (
                <li
                  key={doc.id}
                  className="rounded-xl border border-brand-100 px-4 py-3 flex flex-wrap items-center gap-3 justify-between"
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <FolderLock className="h-5 w-5 text-slate-600 shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <p className="font-medium text-brand-900 truncate">{doc.title}</p>
                      <p className="mt-0.5 text-xs text-brand-300">
                        {doc.original_filename} · {formatBytes(doc.size_bytes)} ·{" "}
                        {formatDate(doc.updated_at)}
                      </p>
                      {doc.description ? (
                        <p className="mt-1 text-sm text-brand-700 line-clamp-2">{doc.description}</p>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <ActionButton
                      disabled={busyId === `p-${doc.id}`}
                      onClick={() => openPrivate(doc, false)}
                    >
                      View
                    </ActionButton>
                    <ActionButton
                      disabled={busyId === `p-${doc.id}`}
                      onClick={() => openPrivate(doc, true)}
                    >
                      Download
                    </ActionButton>
                    <ActionButton
                      disabled={busyId === `p-${doc.id}`}
                      onClick={() => setEditingPrivate(doc)}
                    >
                      Edit
                    </ActionButton>
                    <ActionButton
                      danger
                      disabled={busyId === `p-${doc.id}`}
                      onClick={() => deletePrivate(doc)}
                    >
                      Delete
                    </ActionButton>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {showCompanyUpload ? (
        <CompanyUploadDialog
          categories={categoryOptions}
          onClose={() => setShowCompanyUpload(false)}
          onSaved={async () => {
            setShowCompanyUpload(false);
            await loadCompany();
          }}
          onError={setError}
        />
      ) : null}

      {editingCompany ? (
        <CompanyEditDialog
          document={editingCompany}
          categories={categoryOptions}
          onClose={() => setEditingCompany(null)}
          onSaved={async () => {
            setEditingCompany(null);
            await loadCompany();
          }}
          onError={setError}
        />
      ) : null}

      {showPrivateUpload ? (
        <PrivateUploadDialog
          onClose={() => setShowPrivateUpload(false)}
          onSaved={async () => {
            setShowPrivateUpload(false);
            await loadPrivate();
          }}
          onError={setError}
        />
      ) : null}

      {editingPrivate ? (
        <PrivateEditDialog
          document={editingPrivate}
          onClose={() => setEditingPrivate(null)}
          onSaved={async () => {
            setEditingPrivate(null);
            await loadPrivate();
          }}
          onError={setError}
        />
      ) : null}
    </div>
  );
}

function EmptyState({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="py-12 text-center">
      <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-brand-50">
        {icon}
      </div>
      <p className="text-sm font-medium text-brand-900">{title}</p>
      <p className="mt-1 text-sm text-brand-300 max-w-md mx-auto">{description}</p>
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  danger,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${
        danger
          ? "border-red-200 text-red-700 hover:bg-red-50"
          : "border-brand-200 text-brand-800 hover:bg-white"
      }`}
    >
      {children}
    </button>
  );
}

function ModalShell({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl border border-brand-200">
        <div className="flex items-center justify-between border-b border-brand-100 px-5 py-4">
          <h3 className="text-base font-semibold text-brand-900">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-brand-300 hover:text-brand-700"
          >
            Close
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

function CompanyUploadDialog({
  categories,
  onClose,
  onSaved,
  onError,
}: {
  categories: CompanyDocumentCategory[];
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">(
    categories[0]?.id ?? "",
  );
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || categoryId === "") {
      onError("Category and file are required.");
      return;
    }
    setSubmitting(true);
    onError("");
    try {
      await api.uploadCompanyDocument({
        title,
        description: description || undefined,
        category_id: categoryId,
        file,
      });
      await onSaved();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title="Upload company document" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Title">
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </Field>
        <Field label="Category">
          <select
            required
            value={categoryId}
            onChange={(e) => setCategoryId(Number(e.target.value))}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </Field>
        <Field label="File">
          <input
            ref={fileRef}
            required
            type="file"
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm"
          />
          <p className="mt-1 text-xs text-brand-300">PDF, DOC, DOCX, JPG, or PNG up to 5 MB.</p>
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? "Uploading…" : "Upload"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function CompanyEditDialog({
  document,
  categories,
  onClose,
  onSaved,
  onError,
}: {
  document: CompanyDocument;
  categories: CompanyDocumentCategory[];
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [title, setTitle] = useState(document.title);
  const [description, setDescription] = useState(document.description ?? "");
  const [categoryId, setCategoryId] = useState(document.category_id);
  const [status, setStatus] = useState<CompanyDocumentStatus>(document.status);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    onError("");
    try {
      await api.updateCompanyDocument(document.id, {
        title,
        description,
        category_id: categoryId,
        status,
      });
      await onSaved();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title="Edit company document" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Title">
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </Field>
        <Field label="Category">
          <select
            required
            value={categoryId}
            onChange={(e) => setCategoryId(Number(e.target.value))}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Status">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as CompanyDocumentStatus)}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </Field>
        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function PrivateUploadDialog({
  onClose,
  onSaved,
  onError,
}: {
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) {
      onError("Choose a file to upload.");
      return;
    }
    setSubmitting(true);
    onError("");
    try {
      await api.uploadMyPrivateDocument({
        title,
        description: description || undefined,
        file,
      });
      await onSaved();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title="Upload private document" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Title">
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </Field>
        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </Field>
        <Field label="File">
          <input
            required
            type="file"
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm"
          />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? "Uploading…" : "Upload"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function PrivateEditDialog({
  document,
  onClose,
  onSaved,
  onError,
}: {
  document: PrivateDocument;
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [title, setTitle] = useState(document.title);
  const [description, setDescription] = useState(document.description ?? "");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    onError("");
    try {
      await api.updateMyPrivateDocument(document.id, {
        title,
        description,
      });
      await onSaved();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title="Edit private document" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Title">
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </Field>
        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-brand-800">{label}</span>
      {children}
    </label>
  );
}
