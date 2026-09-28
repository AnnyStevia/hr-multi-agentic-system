"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  TrainingResourcePreview,
  TrainingResourcePreviewLive,
} from "@/components/TrainingResourcePreview";
import { api } from "@/lib/api";
import type { Training } from "@/types/training";

export default function HrTrainingCataloguePage() {
  const [trainings, setTrainings] = useState<Training[]>([]);
  const [query, setQuery] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [resourceUrl, setResourceUrl] = useState("");
  const [editUrls, setEditUrls] = useState<Record<number, string>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const rows = await api.listTrainings();
      setTrainings(rows);
      setEditUrls(Object.fromEntries(rows.map((item) => [item.id, item.resource_url ?? ""])));
    } catch (err) {
      setTrainings([]);
      setError(err instanceof Error ? err.message : "Failed to load trainings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const words = needle ? needle.split(/\s+/).filter(Boolean) : [];
    const matched = !words.length
      ? [...trainings]
      : trainings.filter((training) => {
          const haystack = [
            training.title,
            training.description ?? "",
            training.resource_url ?? "",
          ]
            .join(" ")
            .toLowerCase();
          return words.every((word) => haystack.includes(word));
        });

    return matched.sort((a, b) => {
      const aTime = Date.parse(a.created_at) || 0;
      const bTime = Date.parse(b.created_at) || 0;
      if (bTime !== aTime) return bTime - aTime;
      return b.id - a.id;
    });
  }, [trainings, query]);

  const resetCreateForm = () => {
    setTitle("");
    setDescription("");
    setResourceUrl("");
  };

  const closeCreate = () => {
    setShowCreate(false);
    resetCreateForm();
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await api.createTraining({
        title: title.trim(),
        description: description.trim() || null,
        resource_url: resourceUrl.trim() || null,
      });
      closeCreate();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create training");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveUrl = async (trainingId: number) => {
    setActingId(trainingId);
    setError("");
    try {
      const raw = (editUrls[trainingId] ?? "").trim();
      await api.updateTraining(trainingId, {
        resource_url: raw === "" ? null : raw,
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update resource URL");
    } finally {
      setActingId(null);
    }
  };

  const handleDelete = async (training: Training) => {
    if (
      !window.confirm(
        `Delete “${training.title}”? This also removes all onboarding assignments of this training.`,
      )
    ) {
      return;
    }
    setActingId(training.id);
    setError("");
    try {
      await api.deleteTraining(training.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete training");
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-brand-900">Training catalogue</h1>
          <p className="mt-1 text-sm text-brand-300">
            Browse learning resources and assign them from each employee&apos;s onboarding page.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="shrink-0 self-start rounded-xl bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Create training resource
        </button>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative block w-full max-w-md">
          <span className="sr-only">Search trainings</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by word…"
            className="w-full rounded-xl border border-brand-200 bg-white py-2.5 pl-10 pr-3 text-sm text-brand-900 placeholder:text-brand-300 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
          />
          <svg
            viewBox="0 0 24 24"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-300"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden
          >
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3-3" strokeLinecap="round" />
          </svg>
        </label>
        <p className="text-sm text-brand-300">
          {loading
            ? "Loading…"
            : query.trim()
              ? `${filtered.length} of ${trainings.length} shown`
              : `${trainings.length} training${trainings.length === 1 ? "" : "s"}`}
        </p>
      </div>

      {loading ? (
        <div className="py-20 flex justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
        </div>
      ) : trainings.length === 0 ? (
        <div className="rounded-2xl border border-brand-200 bg-white py-16 text-center space-y-3">
          <p className="text-sm text-brand-300">No trainings yet.</p>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="rounded-xl bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Create training resource
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-brand-200 bg-white py-16 text-center">
          <p className="text-sm text-brand-300">No trainings match “{query.trim()}”.</p>
        </div>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((training) => {
            const isEditing = editingId === training.id;
            return (
              <li
                key={training.id}
                className="flex flex-col overflow-hidden rounded-2xl border border-brand-200 bg-white shadow-sm"
              >
                <div className="border-b border-brand-100 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold text-brand-900 leading-snug">
                        {training.title}
                      </h3>
                      {training.description ? (
                        <p className="mt-1 text-sm text-brand-300 line-clamp-2">
                          {training.description}
                        </p>
                      ) : (
                        <p className="mt-1 text-xs text-brand-300 italic">No description</p>
                      )}
                    </div>
                    <button
                      type="button"
                      disabled={actingId === training.id}
                      onClick={() => handleDelete(training)}
                      className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                <div className="flex-1 p-4 space-y-3">
                  {training.resource_url ? (
                    <TrainingResourcePreview url={training.resource_url} title={training.title} />
                  ) : (
                    <div className="flex aspect-video items-center justify-center rounded-xl border border-dashed border-brand-200 bg-brand-50/50 px-4 text-center">
                      <p className="text-xs text-brand-300">No resource link yet</p>
                    </div>
                  )}

                  {isEditing ? (
                    <div className="space-y-2">
                      <label
                        className="block text-xs font-medium text-brand-300"
                        htmlFor={`edit-url-${training.id}`}
                      >
                        Resource URL
                      </label>
                      <input
                        id={`edit-url-${training.id}`}
                        type="url"
                        value={editUrls[training.id] ?? ""}
                        onChange={(e) =>
                          setEditUrls((prev) => ({ ...prev, [training.id]: e.target.value }))
                        }
                        placeholder="https://… (empty to clear)"
                        className="w-full border border-brand-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                      />
                      <TrainingResourcePreviewLive url={editUrls[training.id] ?? ""} />
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={actingId === training.id}
                          onClick={() => handleSaveUrl(training.id)}
                          className="rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                        >
                          {actingId === training.id ? "Saving..." : "Save"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditingId(null);
                            setEditUrls((prev) => ({
                              ...prev,
                              [training.id]: training.resource_url ?? "",
                            }));
                          }}
                          className="rounded-xl border border-brand-200 px-3 py-2 text-sm text-brand-900 hover:bg-brand-50"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setEditingId(training.id)}
                      className="w-full rounded-xl border border-brand-200 px-3 py-2 text-sm font-medium text-brand-900 hover:bg-brand-50"
                    >
                      {training.resource_url ? "Edit resource link" : "Add resource link"}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-brand-900/40"
            aria-label="Close create dialog"
            onClick={closeCreate}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-training-title"
            className="relative z-10 w-full max-w-lg rounded-2xl border border-brand-200 bg-white p-6 shadow-xl"
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h2 id="create-training-title" className="text-lg font-semibold text-brand-900">
                  Create training resource
                </h2>
                <p className="mt-0.5 text-xs text-brand-300">
                  Title is required. Resource URL is optional and must be http(s).
                </p>
              </div>
              <button
                type="button"
                onClick={closeCreate}
                className="rounded-lg px-2 py-1 text-sm text-brand-300 hover:bg-brand-50 hover:text-brand-900"
              >
                Close
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-brand-300 mb-1" htmlFor="training-title">
                  Title
                </label>
                <input
                  id="training-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full border border-brand-200 rounded-xl px-3 py-2.5 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                  placeholder="e.g. Security awareness"
                  required
                  autoFocus
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium text-brand-300 mb-1"
                  htmlFor="training-description"
                >
                  Description
                </label>
                <textarea
                  id="training-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  className="w-full border border-brand-200 rounded-xl px-3 py-2.5 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                  placeholder="What should the employee learn?"
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium text-brand-300 mb-1"
                  htmlFor="training-resource-url"
                >
                  Resource URL
                </label>
                <input
                  id="training-resource-url"
                  type="url"
                  value={resourceUrl}
                  onChange={(e) => setResourceUrl(e.target.value)}
                  placeholder="https://youtube.com/… or LMS link"
                  className="w-full border border-brand-200 rounded-xl px-3 py-2.5 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                />
              </div>
              {resourceUrl.trim() && (
                <div className="rounded-xl border border-dashed border-brand-200 bg-brand-50/50 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-brand-300">
                    Preview
                  </p>
                  <TrainingResourcePreviewLive url={resourceUrl} />
                </div>
              )}
              <div className="flex flex-wrap justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={closeCreate}
                  className="rounded-xl border border-brand-200 px-3.5 py-2 text-sm text-brand-900 hover:bg-brand-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !title.trim()}
                  className="rounded-xl bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {submitting ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
