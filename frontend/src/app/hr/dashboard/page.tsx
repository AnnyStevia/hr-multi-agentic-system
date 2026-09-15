"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import type { Job } from "@/types/jobs";

export default function HrDashboardPage() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeEmployees, setActiveEmployees] = useState<number | null>(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [jobData, employeeData] = await Promise.all([
          api.listJobs(),
          api.listEmployees({ status: "active" }),
        ]);
        setJobs(jobData);
        setActiveEmployees(employeeData.total);
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : "Could not load dashboard data");
      }
    };
    load();
  }, []);

  if (!user) return null;

  const draftCount = jobs.filter((job) => job.status === "draft").length;
  const publishedCount = jobs.filter((job) => job.status === "published").length;
  const closedCount = jobs.filter((job) => job.status === "closed").length;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Welcome, {user.first_name}</h1>
          <p className="mt-1 text-gray-600">
            Manage employees, departments, and job offers from this workspace.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/hr/employees/create"
            className="inline-flex justify-center border border-gray-300 text-gray-800 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            Add Employee
          </Link>
          <Link
            href="/hr/jobs/create"
            className="inline-flex justify-center bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 transition"
          >
            Create Job Offer
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Employees" value={activeEmployees ?? 0} />
        <StatCard label="Draft offers" value={draftCount} />
        <StatCard label="Published offers" value={publishedCount} />
        <StatCard label="Closed offers" value={closedCount} />
      </div>

      {loadError && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-lg text-sm">
          {loadError}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Profile</h2>
          <dl className="mt-4 space-y-3">
            <div>
              <dt className="text-xs text-gray-500">Name</dt>
              <dd className="text-sm font-medium text-gray-900">{user.full_name}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Email</dt>
              <dd className="text-sm font-medium text-gray-900">{user.email}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Roles</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {user.roles.map((role) => (
                  <span
                    key={role.id}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-100 text-brand-800"
                  >
                    {role.name}
                  </span>
                ))}
              </dd>
            </div>
          </dl>
        </section>

        <section className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
            Recruitment
          </h2>
          <p className="mt-3 text-sm text-gray-600">
            Create a job offer, keep it as a draft, then publish it when it is ready for candidates.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href="/hr/jobs"
              className="text-sm font-medium text-brand-700 border border-brand-200 px-3 py-2 rounded-lg hover:bg-brand-50"
            >
              View job offers
            </Link>
            <Link
              href="/hr/jobs/create"
              className="text-sm font-medium text-white bg-brand-600 px-3 py-2 rounded-lg hover:bg-brand-700"
            >
              Create Job Offer
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white rounded-xl border shadow-sm p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
