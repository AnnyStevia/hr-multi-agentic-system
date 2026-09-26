"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { InterviewSummary } from "@/types/interviews";

export default function MyInterviewsPage() {
  const [items, setItems] = useState<InterviewSummary[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        setItems(await api.listMyInterviews());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load interviews");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My interview assignments</h1>
        <p className="mt-1 text-sm text-gray-600">Interviews where you are on the panel.</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      {items.length === 0 ? (
        <p className="text-sm text-gray-500">No interview assignments yet.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((interview) => (
            <li key={interview.id}>
              <Link
                href={`/employee/interviews/${interview.id}`}
                className="block rounded-xl border bg-white px-4 py-4 hover:border-brand-300 transition"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-gray-900">{interview.candidate_name}</p>
                    <p className="text-sm text-gray-600">{interview.job_title}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className="text-xs font-medium text-brand-700 bg-brand-50 px-2 py-1 rounded">
                      {interview.my_role === "primary" ? "Primary" : "Panel"}
                    </span>
                    {(interview.can_propose_slots ||
                      (interview.my_role === "primary" &&
                        interview.status === "proposed" &&
                        (interview.slot_count ?? 0) === 0)) && (
                      <span className="text-xs font-semibold text-amber-800 bg-amber-50 px-2 py-1 rounded">
                        Propose slots →
                      </span>
                    )}
                  </div>
                </div>
                <p className="mt-2 text-sm text-gray-700">{interview.status_label}</p>
                {(interview.can_propose_slots ||
                  (interview.my_role === "primary" &&
                    interview.status === "proposed" &&
                    (interview.slot_count ?? 0) === 0)) && (
                  <p className="mt-1 text-sm font-medium text-brand-700">
                    Open this assignment to submit available time slots.
                  </p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
