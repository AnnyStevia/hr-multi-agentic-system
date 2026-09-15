"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Job, JobStatus } from "@/types/jobs";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function statusClass(status: JobStatus): string {
  if (status === "published") return "bg-green-100 text-green-800";
  if (status === "closed") return "bg-gray-100 text-gray-700";
  return "bg-amber-100 text-amber-800";
}

export default function JobsListPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);

  const loadJobs = async () => {
    setError("");
    setLoading(true);
    try {
      setJobs(await api.listJobs());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handlePublish = async (id: number) => {
    setActingId(id);
    try {
      await api.publishJob(id);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish job");
    } finally {
      setActingId(null);
    }
  };

  const handleClose = async (id: number) => {
    setActingId(id);
    try {
      await api.closeJob(id);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to close job");
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Job Offers</h1>
          <p className="mt-1 text-sm text-gray-600">
            Draft, publish, and close recruitment offers.
          </p>
        </div>
        <Link
          href="/hr/jobs/create"
          className="inline-flex justify-center bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          Create Job Offer
        </Link>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-500">
            No job offers yet. Create the first one.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Title
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Created
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Published
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/hr/jobs/${job.id}`}
                        className="text-sm font-medium text-gray-900 hover:text-brand-700"
                      >
                        {job.title}
                      </Link>
                      <p className="text-xs text-gray-500">
                        {[job.department, job.location].filter(Boolean).join(" · ") || "—"}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${statusClass(job.status)}`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {formatDate(job.created_at)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {formatDate(job.published_at)}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <Link
                        href={`/hr/jobs/${job.id}`}
                        className="text-sm text-brand-700 hover:text-brand-800 mr-3"
                      >
                        View
                      </Link>
                      <Link
                        href={`/hr/jobs/${job.id}/applications`}
                        className="text-sm text-brand-700 hover:text-brand-800 mr-3"
                      >
                        Applications
                      </Link>
                      {job.status === "draft" && (
                        <button
                          onClick={() => handlePublish(job.id)}
                          disabled={actingId === job.id}
                          className="text-sm text-green-700 hover:text-green-800 disabled:opacity-50"
                        >
                          Publish
                        </button>
                      )}
                      {job.status === "published" && (
                        <button
                          onClick={() => handleClose(job.id)}
                          disabled={actingId === job.id}
                          className="text-sm text-gray-700 hover:text-gray-900 disabled:opacity-50"
                        >
                          Close
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
