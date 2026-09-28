"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { TrainingResourcePreview } from "@/components/TrainingResourcePreview";
import { api } from "@/lib/api";
import type { MyTrainingResource } from "@/types/training";

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function EmployeeTrainingPage() {
  const [resources, setResources] = useState<MyTrainingResource[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      setResources(await api.listMyTrainings());
    } catch (err) {
      setResources([]);
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
      ? [...resources]
      : resources.filter((item) => {
          const haystack = [item.title, item.description ?? "", item.resource_url ?? ""]
            .join(" ")
            .toLowerCase();
          return words.every((word) => haystack.includes(word));
        });

    return matched.sort((a, b) => {
      if (a.status !== b.status) {
        return a.status === "pending" ? -1 : 1;
      }
      const aTime = Date.parse(a.created_at) || 0;
      const bTime = Date.parse(b.created_at) || 0;
      return bTime - aTime;
    });
  }, [resources, query]);

  const pendingCount = resources.filter((item) => item.status === "pending").length;

  const markCompleted = async (resource: MyTrainingResource) => {
    if (resource.status === "completed") return;
    try {
      const updated = await api.completeMyTraining(resource.training_id);
      setResources((prev) =>
        prev.map((item) => (item.training_id === updated.training_id ? updated : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark training completed");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brand-900">My training</h1>
          <p className="mt-1 text-sm text-brand-300">
            Browse all company training resources. Opening one marks it completed for you only.
          </p>
        </div>
        {!loading && (
          <p className="text-sm text-brand-300 shrink-0">
            {resources.length === 0
              ? "No resources yet"
              : pendingCount === 0
                ? "All caught up"
                : `${pendingCount} pending`}
          </p>
        )}
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

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

      {loading ? (
        <div className="py-20 flex justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
        </div>
      ) : resources.length === 0 ? (
        <div className="rounded-2xl border border-brand-200 bg-white py-16 text-center">
          <p className="text-sm text-brand-300">
            No training resources yet. HR will publish them in the Training catalogue.
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-brand-200 bg-white py-16 text-center">
          <p className="text-sm text-brand-300">No trainings match “{query.trim()}”.</p>
        </div>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((resource) => (
            <li
              key={resource.training_id}
              className={`flex flex-col overflow-hidden rounded-2xl border bg-white shadow-sm ${
                resource.status === "completed"
                  ? "border-green-100"
                  : "border-brand-200"
              }`}
            >
              <div className="flex items-start justify-between gap-3 border-b border-brand-100 p-4">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-brand-900">{resource.title}</h2>
                  {resource.description && (
                    <p className="mt-1 text-sm text-brand-300 line-clamp-2">
                      {resource.description}
                    </p>
                  )}
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-1 text-xs font-medium ${
                    resource.status === "completed"
                      ? "bg-green-100 text-green-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {resource.status === "completed" ? "Completed" : "Pending"}
                </span>
              </div>

              <div className="flex-1 space-y-3 p-4">
                {resource.resource_url ? (
                  <>
                    <TrainingResourcePreview
                      url={resource.resource_url}
                      title={resource.title}
                      onOpen={() => {
                        void markCompleted(resource);
                      }}
                    />
                    <p className="text-xs text-brand-300">
                      {resource.status === "completed"
                        ? `Completed ${formatDateTime(resource.completed_at)}`
                        : "Click the preview to open the resource and mark it completed for you."}
                    </p>
                  </>
                ) : (
                  <div className="space-y-3">
                    <div className="flex aspect-video items-center justify-center rounded-xl border border-dashed border-brand-200 bg-brand-50/50 px-4 text-center">
                      <p className="text-xs text-brand-300">
                        No resource link — mark completed when you finish offline.
                      </p>
                    </div>
                    {resource.status === "pending" && (
                      <button
                        type="button"
                        onClick={() => void markCompleted(resource)}
                        className="w-full rounded-xl bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
                      >
                        Mark as completed
                      </button>
                    )}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
