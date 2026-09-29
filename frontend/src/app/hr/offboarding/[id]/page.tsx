"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { OffboardingStatusBadge } from "@/components/OffboardingStatusBadge";
import { OffboardingTaskStatusBadge } from "@/components/OffboardingTaskStatusBadge";
import { api } from "@/lib/api";
import type { Employee } from "@/types/employees";
import {
  OFFBOARDING_REASON_LABELS,
  OFFBOARDING_TASK_CATEGORIES,
  OFFBOARDING_TASK_CATEGORY_LABELS,
  type OffboardingDetail,
  type OffboardingProgress,
  type OffboardingStatus,
  type OffboardingTask,
  type OffboardingTaskCategory,
} from "@/types/offboarding";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function OffboardingDetailPage() {
  const params = useParams<{ id: string }>();
  const caseId = Number(params.id);

  const [detail, setDetail] = useState<OffboardingDetail | null>(null);
  const [tasks, setTasks] = useState<OffboardingTask[]>([]);
  const [progress, setProgress] = useState<OffboardingProgress | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<OffboardingTaskCategory>("other");
  const [isRequired, setIsRequired] = useState(true);
  const [assigneeId, setAssigneeId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [caseData, taskData, progressData, employeeList] = await Promise.all([
        api.getOffboarding(caseId),
        api.listOffboardingTasks(caseId),
        api.getOffboardingProgress(caseId),
        api.listEmployees({ status: "active" }),
      ]);
      setDetail(caseData);
      setTasks(taskData);
      setProgress(progressData);
      setEmployees(employeeList.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load offboarding case");
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    if (!Number.isFinite(caseId)) {
      setError("Invalid offboarding id");
      setLoading(false);
      return;
    }
    load();
  }, [caseId, load]);

  const grouped = useMemo(() => {
    const map = new Map<OffboardingTaskCategory, OffboardingTask[]>();
    for (const task of tasks) {
      const list = map.get(task.category) ?? [];
      list.push(task);
      map.set(task.category, list);
    }
    return map;
  }, [tasks]);

  const caseMutable =
    detail?.status === "initiated" ||
    detail?.status === "in_progress" ||
    detail?.status === "pending_clearance";

  const runCaseAction = async (
    label: string,
    action: () => Promise<OffboardingDetail>,
    confirmMessage: string,
  ) => {
    if (!window.confirm(confirmMessage)) return;
    setActing(label);
    setError("");
    try {
      setDetail(await action());
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${label}`);
    } finally {
      setActing(null);
    }
  };

  const runTaskAction = async (
    key: string,
    action: () => Promise<unknown>,
  ) => {
    setActing(key);
    setError("");
    try {
      await action();
      const [taskData, progressData] = await Promise.all([
        api.listOffboardingTasks(caseId),
        api.getOffboardingProgress(caseId),
      ]);
      setTasks(taskData);
      setProgress(progressData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Task action failed");
    } finally {
      setActing(null);
    }
  };

  const onCreateTask = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    setCreating(true);
    setError("");
    try {
      await api.createOffboardingTask(caseId, {
        title: title.trim(),
        description: description.trim() || null,
        category,
        is_required: isRequired,
        assigned_to_employee_id: assigneeId ? Number(assigneeId) : null,
        due_date: dueDate || null,
      });
      setTitle("");
      setDescription("");
      setCategory("other");
      setIsRequired(true);
      setAssigneeId("");
      setDueDate("");
      const [taskData, progressData] = await Promise.all([
        api.listOffboardingTasks(caseId),
        api.getOffboardingProgress(caseId),
      ]);
      setTasks(taskData);
      setProgress(progressData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="max-w-4xl mx-auto">
        <Link href="/hr/offboarding" className="text-sm text-brand-700 hover:underline">
          ← Back to offboarding
        </Link>
        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}
      </div>
    );
  }

  const status: OffboardingStatus = detail.status;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <Link href="/hr/offboarding" className="text-sm text-brand-700 hover:underline">
          ← Back to offboarding
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">{detail.employee.full_name}</h1>
          <OffboardingStatusBadge status={status} />
        </div>
        <p className="mt-1 text-sm text-gray-600">
          {detail.employee.position} · {detail.employee.employee_number}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border shadow-sm p-5 space-y-3 text-sm">
        <Row label="Employee email" value={detail.employee.email} />
        <Row label="Reason" value={OFFBOARDING_REASON_LABELS[detail.reason]} />
        <Row label="Reason details" value={detail.reason_details || "—"} />
        <Row label="Last working day" value={formatDate(detail.last_working_day)} />
        <Row label="Initiated" value={formatDateTime(detail.initiated_at)} />
        <Row label="Completed" value={formatDateTime(detail.completed_at)} />
        <Row
          label="Created by"
          value={
            detail.created_by
              ? `${detail.created_by.full_name} (${detail.created_by.email})`
              : "—"
          }
        />
        <Row label="Updated" value={formatDateTime(detail.updated_at)} />
      </div>

      <section className="bg-white rounded-xl border shadow-sm p-5 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Offboarding checklist</h2>
            <p className="text-sm text-gray-600">
              {progress ? `${progress.percentage}% complete` : "—"}
              {progress?.overdue_tasks ? ` · ${progress.overdue_tasks} overdue` : ""}
              {progress?.required_complete ? " · Required tasks done" : ""}
            </p>
          </div>
          {progress && (
            <div className="text-xs text-gray-500">
              {progress.completed_tasks}/{progress.total_tasks} completed ·{" "}
              {progress.skipped_tasks} skipped
            </div>
          )}
        </div>

        {progress && (
          <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full bg-brand-600 transition-all"
              style={{ width: `${progress.percentage}%` }}
            />
          </div>
        )}

        <div className="space-y-5">
          {OFFBOARDING_TASK_CATEGORIES.map((cat) => {
            const items = grouped.get(cat);
            if (!items?.length) return null;
            return (
              <div key={cat}>
                <h3 className="text-sm font-semibold text-gray-800 mb-2">
                  {OFFBOARDING_TASK_CATEGORY_LABELS[cat]}
                </h3>
                <ul className="space-y-2">
                  {items.map((task) => (
                    <li
                      key={task.id}
                      className="border border-gray-100 rounded-lg px-3 py-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
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
                        {task.description && (
                          <p className="mt-1 text-xs text-gray-500">{task.description}</p>
                        )}
                        <p className="mt-1 text-xs text-gray-500">
                          Assignee: {task.assigned_to?.full_name ?? "Unassigned"} · Due:{" "}
                          {formatDate(task.due_date)}
                        </p>
                      </div>
                      {caseMutable &&
                        (task.status === "pending" || task.status === "in_progress") && (
                          <div className="flex flex-wrap gap-2 shrink-0">
                            {task.status === "pending" && (
                              <button
                                type="button"
                                disabled={acting !== null}
                                className="px-3 py-1.5 text-xs rounded-md border border-gray-300 hover:bg-gray-50 disabled:opacity-60"
                                onClick={() =>
                                  runTaskAction(`start-${task.id}`, () =>
                                    api.startOffboardingTask(caseId, task.id),
                                  )
                                }
                              >
                                Start
                              </button>
                            )}
                            {task.status === "in_progress" && (
                              <button
                                type="button"
                                disabled={acting !== null}
                                className="px-3 py-1.5 text-xs rounded-md border border-gray-300 hover:bg-gray-50 disabled:opacity-60"
                                onClick={() =>
                                  runTaskAction(`reopen-${task.id}`, () =>
                                    api.reopenOffboardingTask(caseId, task.id),
                                  )
                                }
                              >
                                Reopen
                              </button>
                            )}
                            <button
                              type="button"
                              disabled={acting !== null}
                              className="px-3 py-1.5 text-xs rounded-md bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-60"
                              onClick={() =>
                                runTaskAction(`complete-${task.id}`, () =>
                                  api.completeOffboardingTask(caseId, task.id),
                                )
                              }
                            >
                              Complete
                            </button>
                            <button
                              type="button"
                              disabled={acting !== null}
                              className="px-3 py-1.5 text-xs rounded-md border border-amber-300 text-amber-800 hover:bg-amber-50 disabled:opacity-60"
                              onClick={() =>
                                runTaskAction(`skip-${task.id}`, () =>
                                  api.skipOffboardingTask(caseId, task.id),
                                )
                              }
                            >
                              Skip
                            </button>
                          </div>
                        )}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>

        {caseMutable && (
          <form onSubmit={onCreateTask} className="border-t pt-4 grid gap-3 md:grid-cols-2">
            <h3 className="md:col-span-2 text-sm font-semibold text-gray-900">+ Add task</h3>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Title</label>
              <input
                className={inputClass}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Category</label>
              <select
                className={inputClass}
                value={category}
                onChange={(e) => setCategory(e.target.value as OffboardingTaskCategory)}
              >
                {OFFBOARDING_TASK_CATEGORIES.map((value) => (
                  <option key={value} value={value}>
                    {OFFBOARDING_TASK_CATEGORY_LABELS[value]}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
              <input
                className={inputClass}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Assignee</label>
              <select
                className={inputClass}
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
              >
                <option value="">Unassigned</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.first_name} {emp.last_name} — {emp.position}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Due date</label>
              <input
                type="date"
                className={inputClass}
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700 md:col-span-2">
              <input
                type="checkbox"
                checked={isRequired}
                onChange={(e) => setIsRequired(e.target.checked)}
              />
              Required
            </label>
            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2.5 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
              >
                {creating ? "Adding…" : "Add task"}
              </button>
            </div>
          </form>
        )}
      </section>

      <div className="flex flex-wrap gap-2">
        {status === "initiated" && (
          <ActionButton
            label="Start"
            disabled={acting !== null}
            busy={acting === "start"}
            onClick={() =>
              runCaseAction(
                "start",
                () => api.startOffboarding(detail.id),
                "Start this offboarding case?",
              )
            }
          />
        )}
        {status === "in_progress" && (
          <ActionButton
            label="Move to pending clearance"
            disabled={acting !== null}
            busy={acting === "pending"}
            onClick={() =>
              runCaseAction(
                "pending",
                () => api.moveOffboardingToPendingClearance(detail.id),
                "Move this case to pending clearance?",
              )
            }
          />
        )}
        {status === "pending_clearance" && (
          <>
            <ActionButton
              label="Back to in progress"
              disabled={acting !== null}
              busy={acting === "start"}
              onClick={() =>
                runCaseAction(
                  "start",
                  () => api.startOffboarding(detail.id),
                  "Move this case back to in progress?",
                )
              }
            />
            <ActionButton
              label="Complete"
              disabled={acting !== null}
              busy={acting === "complete"}
              onClick={() =>
                runCaseAction(
                  "complete",
                  () => api.completeOffboarding(detail.id),
                  "Complete this offboarding case? Checklist does not gate completion yet.",
                )
              }
            />
          </>
        )}
        {caseMutable && (
          <ActionButton
            label="Cancel"
            variant="danger"
            disabled={acting !== null}
            busy={acting === "cancel"}
            onClick={() =>
              runCaseAction(
                "cancel",
                () => api.cancelOffboarding(detail.id),
                "Cancel this offboarding case? Historical record will be kept.",
              )
            }
          />
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col sm:flex-row sm:gap-4">
      <dt className="sm:w-40 shrink-0 text-gray-500">{label}</dt>
      <dd className="text-gray-900">{value}</dd>
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
  busy,
  variant = "primary",
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "danger";
}) {
  const classes =
    variant === "danger"
      ? "bg-red-600 hover:bg-red-700 text-white"
      : "bg-brand-600 hover:bg-brand-700 text-white";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`px-4 py-2.5 rounded-lg text-sm font-medium disabled:opacity-60 ${classes}`}
    >
      {busy ? "Working…" : label}
    </button>
  );
}
