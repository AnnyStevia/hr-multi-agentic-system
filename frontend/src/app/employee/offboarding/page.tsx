"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { MeetingJoinBlock } from "@/components/MeetingJoinBlock";
import { OffboardingClearanceStatusBadge } from "@/components/OffboardingClearanceStatusBadge";
import { OffboardingStatusBadge } from "@/components/OffboardingStatusBadge";
import { OffboardingTaskStatusBadge } from "@/components/OffboardingTaskStatusBadge";
import { api } from "@/lib/api";
import { formatSlotRange } from "@/lib/interviews";
import {
  EXIT_INTERVIEW_STATUS_LABELS,
  OFFBOARDING_CLEARANCE_CATEGORY_LABELS,
  OFFBOARDING_REASON_LABELS,
  OFFBOARDING_TASK_CATEGORY_LABELS,
  type ExitInterviewEmployeeView,
  type OffboardingClearanceEmployeeView,
  type OffboardingEmployeeView,
  type OffboardingTaskEmployeeView,
} from "@/types/offboarding";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export default function EmployeeOffboardingPage() {
  const [cases, setCases] = useState<OffboardingEmployeeView[]>([]);
  const [tasks, setTasks] = useState<OffboardingTaskEmployeeView[]>([]);
  const [clearance, setClearance] = useState<OffboardingClearanceEmployeeView[]>([]);
  const [exitInterview, setExitInterview] = useState<ExitInterviewEmployeeView | null>(
    null,
  );
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [caseData, taskData, clearanceData, exitData] = await Promise.all([
        api.listMyOffboardings(),
        api.listMyOffboardingTasks(),
        api.listMyOffboardingClearance(),
        api.getMyOffboardingExitInterview(),
      ]);
      setCases(caseData);
      setTasks(taskData);
      setClearance(clearanceData);
      setExitInterview(exitData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load offboarding");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runTaskAction = async (key: string, action: () => Promise<unknown>) => {
    setActing(key);
    setError("");
    try {
      await action();
      setTasks(await api.listMyOffboardingTasks());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Task action failed");
    } finally {
      setActing(null);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My offboarding</h1>
          <p className="mt-1 text-sm text-gray-600">
            View your offboarding status, assigned tasks, and clearance progress.
          </p>
        </div>
        <Link
          href="/employee/offboarding/request"
          className="px-4 py-2 rounded-lg border border-brand-200 text-sm font-medium text-brand-800 hover:bg-brand-50"
        >
          Request to leave
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Cases</h2>
        {cases.length === 0 ? (
          <div className="bg-white rounded-xl border shadow-sm p-8 text-center text-sm text-gray-600">
            You have no offboarding cases.
          </div>
        ) : (
          cases.map((item) => (
            <div key={item.id} className="bg-white rounded-xl border shadow-sm p-5 space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <OffboardingStatusBadge status={item.status} />
                <span className="text-sm text-gray-700">
                  {OFFBOARDING_REASON_LABELS[item.reason]}
                </span>
              </div>
              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-gray-500">Last working day</dt>
                  <dd className="text-gray-900">{formatDate(item.last_working_day)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Initiated</dt>
                  <dd className="text-gray-900">{formatDate(item.initiated_at)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Completed</dt>
                  <dd className="text-gray-900">{formatDate(item.completed_at)}</dd>
                </div>
              </dl>
            </div>
          ))
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">My offboarding tasks</h2>
        {tasks.length === 0 ? (
          <div className="bg-white rounded-xl border shadow-sm p-8 text-center text-sm text-gray-600">
            No tasks are assigned to you.
          </div>
        ) : (
          <ul className="space-y-3">
            {tasks.map((task) => (
              <li key={task.id} className="bg-white rounded-xl border shadow-sm p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{task.title}</span>
                  <OffboardingTaskStatusBadge status={task.status} />
                  {task.is_required && (
                    <span className="text-[11px] uppercase tracking-wide text-red-600">
                      Required
                    </span>
                  )}
                  {task.is_overdue && (
                    <span className="text-[11px] uppercase tracking-wide text-orange-600">
                      Overdue
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {OFFBOARDING_TASK_CATEGORY_LABELS[task.category]} · Due{" "}
                  {formatDate(task.due_date)}
                </p>
                {task.description && (
                  <p className="mt-2 text-sm text-gray-600">{task.description}</p>
                )}
                {(task.status === "pending" || task.status === "in_progress") && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {task.status === "pending" && (
                      <button
                        type="button"
                        disabled={acting !== null}
                        className="px-3 py-1.5 text-xs rounded-md border border-gray-300 hover:bg-gray-50 disabled:opacity-60"
                        onClick={() =>
                          runTaskAction(`start-${task.id}`, () =>
                            api.startMyOffboardingTask(task.id),
                          )
                        }
                      >
                        Start
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={acting !== null}
                      className="px-3 py-1.5 text-xs rounded-md bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-60"
                      onClick={() =>
                        runTaskAction(`complete-${task.id}`, () =>
                          api.completeMyOffboardingTask(task.id),
                        )
                      }
                    >
                      Complete
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Clearance</h2>
        {clearance.length === 0 ? (
          <div className="bg-white rounded-xl border shadow-sm p-8 text-center text-sm text-gray-600">
            No clearance items for an active offboarding case.
          </div>
        ) : (
          <ul className="space-y-3">
            {clearance.map((item) => (
              <li key={item.id} className="bg-white rounded-xl border shadow-sm p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{item.item}</span>
                  <OffboardingClearanceStatusBadge status={item.status} />
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {OFFBOARDING_CLEARANCE_CATEGORY_LABELS[item.category]}
                </p>
                {item.notes && (
                  <p className="mt-2 text-sm text-gray-600">{item.notes}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Exit interview</h2>
        {!exitInterview ? (
          <div className="bg-white rounded-xl border shadow-sm p-8 text-center text-sm text-gray-600">
            No exit interview is scheduled for your active offboarding case.
          </div>
        ) : (
          <div className="bg-white rounded-xl border shadow-sm p-5 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-800">
                {EXIT_INTERVIEW_STATUS_LABELS[exitInterview.status]}
              </span>
              <span className="text-sm text-gray-700">
                {formatSlotRange(exitInterview.scheduled_at, exitInterview.ends_at)}
              </span>
            </div>
            <p className="text-sm text-gray-600">
              Interviewer: {exitInterview.interviewer?.full_name ?? "—"}
            </p>
            <MeetingJoinBlock
              status={exitInterview.status}
              meetingUrl={exitInterview.meeting_url}
              joinLabel="Join exit interview"
            />
          </div>
        )}
      </section>
    </div>
  );
}
