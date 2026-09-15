"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { ApplicationStatus } from "@/types/applications";
import type { Job } from "@/types/jobs";

const EMPLOYMENT_LABELS: Record<string, string> = {
  full_time: "Full time",
  part_time: "Part time",
  contract: "Contract",
  internship: "Internship",
};

export default function CareerJobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [statusByJobId, setStatusByJobId] = useState<Record<number, ApplicationStatus>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const published = await api.listCareerJobs();
        setJobs(published);
        try {
          const mine = await api.listMyApplications();
          const map: Record<number, ApplicationStatus> = {};
          for (const application of mine) {
            map[application.job_id] = application.status;
          }
          setStatusByJobId(map);
        } catch {
          setStatusByJobId({});
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load jobs");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Open positions</h1>
      <p className="mt-1 text-sm text-gray-600">Only published jobs are listed here.</p>

      {error && (
        <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="mt-6 bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-500">
            No published openings right now. Check back later.
          </div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {jobs.map((job) => {
              const status = statusByJobId[job.id];
              return (
                <li key={job.id}>
                  <Link
                    href={`/careers/jobs/${job.id}`}
                    className="block px-5 py-4 hover:bg-gray-50"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-gray-900">{job.title}</p>
                      {status ? <StatusBadge status={status} /> : null}
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      {[
                        job.department,
                        job.location,
                        EMPLOYMENT_LABELS[job.employment_type] || job.employment_type,
                      ]
                        .filter(Boolean)
                        .join(" · ") || "View details"}
                    </p>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
