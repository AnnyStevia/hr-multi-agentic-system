"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { ApplicationListItem } from "@/types/applications";
import type { Job } from "@/types/jobs";
import { StatusBadge } from "@/components/StatusBadge";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function JobApplicationsPage() {
  const params = useParams<{ id: string }>();
  const jobId = Number(params.id);
  const [job, setJob] = useState<Job | null>(null);
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const [jobData, rows] = await Promise.all([
          api.getJob(jobId),
          api.listJobApplications(jobId),
        ]);
        setJob(jobData);
        setApplications(rows);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load applications");
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

  return (
    <div className="max-w-6xl mx-auto">
      <Link href={`/hr/jobs/${jobId}`} className="text-sm text-gray-500 hover:text-gray-800">
        {job?.title || "Job"}
      </Link>
      <h1 className="mt-2 text-2xl font-bold text-gray-900">Applications</h1>
      <p className="mt-1 text-sm text-gray-600 mb-6">Candidates who applied to this offer.</p>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {applications.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-500">No applications yet.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Candidate</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">CV</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cover letter</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {applications.map((application) => (
                <tr key={application.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-900">{application.candidate.full_name}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{application.candidate.email}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{formatDate(application.submitted_at)}</td>
                  <td className="px-4 py-3 text-sm">
                    <StatusBadge status={application.status} />
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {application.has_cv ? (
                      <Link href={`/hr/applications/${application.id}#documents`} className="text-brand-700">
                        View
                      </Link>
                    ) : (
                      "No"
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">{application.has_cover_letter ? "Yes" : "No"}</td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/hr/applications/${application.id}`} className="text-sm text-brand-700">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
