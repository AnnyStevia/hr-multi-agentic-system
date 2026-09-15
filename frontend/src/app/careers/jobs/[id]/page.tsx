"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { ApplicationDetail } from "@/types/applications";
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

export default function CareerJobDetailPage() {
  const params = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [existingApplication, setExistingApplication] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const jobId = Number(params.id);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        setJob(await api.getCareerJob(jobId));
        try {
          setExistingApplication(await api.getMyJobApplication(jobId));
        } catch {
          setExistingApplication(null);
        }
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

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!job) {
    return (
      <div>
        <p className="text-red-700">{error || "Job not found"}</p>
        <Link href="/careers/jobs" className="mt-4 inline-block text-sm text-brand-700">
          Back to openings
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/careers/jobs" className="text-sm text-gray-500 hover:text-gray-800">
          Open positions
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">{job.title}</h1>
        <p className="mt-1 text-sm text-gray-600">
          {[job.department, job.position, job.location].filter(Boolean).join(" · ") ||
            "No location details"}
        </p>
      </div>

      <div className="bg-white rounded-xl border shadow-sm p-6 space-y-5">
        <Info
          label="Employment type"
          value={EMPLOYMENT_LABELS[job.employment_type] || job.employment_type}
        />
        <Info label="Published" value={formatDate(job.published_at)} />
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
      </div>

      {existingApplication ? (
        <div className="inline-flex flex-col gap-2 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
          <p className="text-sm font-medium text-gray-900">You have already applied to this job</p>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>Application status:</span>
            <StatusBadge status={existingApplication.status} />
          </div>
        </div>
      ) : (
        <Link
          href={`/careers/jobs/${job.id}/apply`}
          className="inline-flex bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          Apply
        </Link>
      )}
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
