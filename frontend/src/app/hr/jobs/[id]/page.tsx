"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Job } from "@/types/jobs";

const EMPLOYMENT_LABELS: Record<string, string> = {
  full_time: "Full time",
  part_time: "Part time",
  contract: "Contract",
  internship: "Internship",
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);

  const jobId = Number(params.id);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        setJob(await api.getJob(jobId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load job");
      } finally {
        setLoading(false);
      }
    };
    if (!Number.isNaN(jobId)) {
      load();
    }
  }, [jobId]);

  const handlePublish = async () => {
    setActing(true);
    setError("");
    try {
      setJob(await api.publishJob(jobId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish job");
    } finally {
      setActing(false);
    }
  };

  const handleClose = async () => {
    setActing(true);
    setError("");
    try {
      setJob(await api.closeJob(jobId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to close job");
    } finally {
      setActing(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="max-w-3xl mx-auto">
        <p className="text-red-700">{error || "Job not found"}</p>
        <button onClick={() => router.push("/hr/jobs")} className="mt-4 text-sm text-brand-700">
          Back to job offers
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/hr/jobs" className="text-sm text-gray-500 hover:text-gray-800">
            Job Offers
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">{job.title}</h1>
          <p className="mt-1 text-sm text-gray-600">
            {[job.department, job.position, job.location].filter(Boolean).join(" · ") || "No location details"}
          </p>
        </div>
        <span className="capitalize text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-800">
          {job.status}
        </span>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border shadow-sm p-6 space-y-5">
        <Info label="Employment type" value={EMPLOYMENT_LABELS[job.employment_type] || job.employment_type} />
        <Info label="Created" value={formatDate(job.created_at)} />
        <Info label="Published" value={formatDate(job.published_at)} />
        <Info label="Closed" value={formatDate(job.closed_at)} />
        <div>
          <h2 className="text-sm font-medium text-gray-500">Description</h2>
          <p className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">{job.description}</p>
        </div>
        <div>
          <h2 className="text-sm font-medium text-gray-500">Requirements</h2>
          <p className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">
            {job.requirements || "—"}
          </p>
        </div>
        <div>
          <h2 className="text-sm font-medium text-gray-500">Application questions</h2>
          {job.questions?.length ? (
            <ul className="mt-2 space-y-2">
              {job.questions.map((question) => (
                <li key={question.id} className="text-sm text-gray-800">
                  {question.prompt}
                  <span className="ml-2 text-xs text-gray-500">
                    {question.question_type.replace("_", " ")}
                    {question.required ? " · required" : " · optional"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-gray-500">No questions defined.</p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Link
          href={`/hr/jobs/${job.id}/applications`}
          className="border border-gray-300 text-gray-800 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50"
        >
          View applications
        </Link>
        {job.status === "draft" && (
          <button
            onClick={handlePublish}
            disabled={acting}
            className="bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {acting ? "Publishing..." : "Publish"}
          </button>
        )}
        {job.status === "published" && (
          <button
            onClick={handleClose}
            disabled={acting}
            className="border border-gray-300 text-gray-800 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            {acting ? "Closing..." : "Close offer"}
          </button>
        )}
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <h2 className="text-sm font-medium text-gray-500">{label}</h2>
      <p className="mt-1 text-sm text-gray-900">{value}</p>
    </div>
  );
}
