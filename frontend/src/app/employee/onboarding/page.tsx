"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  FileText,
  GraduationCap,
  ListChecks,
  UserRound,
} from "lucide-react";
import { DocumentsSection } from "@/components/DocumentsSection";
import { OnboardingStatusBadge } from "@/components/OnboardingStatusBadge";
import { OnboardingTaskStatusBadge } from "@/components/OnboardingTaskStatusBadge";
import { TrainingSection } from "@/components/TrainingSection";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import type {
  Onboarding,
  OnboardingProgress,
  OnboardingTask,
  OnboardingTaskType,
} from "@/types/onboarding";
import { ONBOARDING_TASK_TYPE_LABELS } from "@/types/onboarding";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    const fallback = new Date(value);
    if (Number.isNaN(fallback.getTime())) return value;
    return fallback.toLocaleDateString(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

const PROFILE_TYPES = new Set<OnboardingTaskType>([
  "profile_personal_info",
  "profile_picture",
  "education",
  "experience",
]);

function taskAction(
  task: OnboardingTask
): { href?: string; sectionId?: string; label: string } | null {
  if (task.status !== "pending") return null;
  if (PROFILE_TYPES.has(task.task_type)) {
    return { href: "/employee/profile", label: "Go to profile" };
  }
  if (task.task_type === "document") {
    return { sectionId: "documents", label: "Upload document" };
  }
  if (task.task_type === "training") {
    return { sectionId: "trainings", label: "Complete training" };
  }
  if (task.task_type === "acknowledgement") {
    return { label: "Acknowledge" };
  }
  if (task.task_type === "manual") {
    return null;
  }
  return null;
}

function taskIcon(taskType: OnboardingTaskType): ReactNode {
  if (PROFILE_TYPES.has(taskType)) return <UserRound className="size-4" />;
  if (taskType === "document") return <FileText className="size-4" />;
  if (taskType === "training") return <GraduationCap className="size-4" />;
  if (taskType === "acknowledgement") return <CheckCircle2 className="size-4" />;
  return <ClipboardList className="size-4" />;
}

function taskTone(taskType: OnboardingTaskType): string {
  if (PROFILE_TYPES.has(taskType)) return "bg-sky-50 text-sky-700";
  if (taskType === "document") return "bg-violet-50 text-violet-700";
  if (taskType === "training") return "bg-teal-50 text-teal-700";
  if (taskType === "acknowledgement") return "bg-emerald-50 text-emerald-700";
  return "bg-amber-50 text-amber-700";
}

export default function EmployeeOnboardingPage() {
  const { user, refreshUser } = useAuth();
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [progress, setProgress] = useState<OnboardingProgress | null>(null);
  const [tasks, setTasks] = useState<OnboardingTask[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = useCallback(
    async (opts?: { silent?: boolean }) => {
      const silent = opts?.silent ?? false;
      setError("");
      if (!silent) setLoading(true);
      try {
        const [onboardingData, progressData, taskData] = await Promise.all([
          api.getMyOnboarding(),
          api.getMyOnboardingProgress(),
          api.listMyOnboardingTasks(),
        ]);
        setOnboarding(onboardingData);
        setProgress(progressData);
        setTasks(taskData);
        if (onboardingData.status === "completed") {
          await refreshUser();
        }
      } catch (err) {
        if (!silent) {
          setOnboarding(null);
          setProgress(null);
          setTasks([]);
        }
        setError(
          err instanceof Error ? err.message : "Failed to load onboarding"
        );
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [refreshUser]
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        void load({ silent: true });
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [load]);

  const handleAcknowledge = async (taskId: number) => {
    setActingId(taskId);
    setError("");
    try {
      await api.acknowledgeMyOnboardingTask(taskId);
      await load({ silent: true });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to acknowledge task"
      );
    } finally {
      setActingId(null);
    }
  };

  const scrollToSection = (sectionId: string) => {
    document
      .getElementById(sectionId)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const pendingCount = useMemo(
    () => tasks.filter((task) => task.status === "pending").length,
    [tasks]
  );

  const preferredDocumentType =
    tasks.find(
      (task) =>
        task.task_type === "document" &&
        task.status === "pending" &&
        task.document_type
    )?.document_type ?? "id_document";

  if (loading) {
    return (
      <div className="-m-6 flex min-h-[50vh] items-center justify-center bg-[#f3f6f5] p-6">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      </div>
    );
  }

  if (!onboarding) {
    return (
      <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 sm:p-6">
        <div className="mx-auto flex max-w-[560px] justify-center py-16">
          <div className={cn(card, "w-full p-8 text-center")}>
            <h1 className="text-xl font-semibold text-brand-900">
              Onboarding unavailable
            </h1>
            <p className="mt-2 text-sm text-brand-300">
              {error ||
                "We could not find an onboarding record for your account."}
            </p>
            <button
              type="button"
              onClick={() => void load()}
              className="mt-5 inline-flex h-10 items-center rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white transition hover:bg-brand-700"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isComplete = onboarding.status === "completed";
  const percent = progress?.overall_percentage ?? 0;

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              Getting started
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-brand-900">
              Welcome{user?.first_name ? `, ${user.first_name}` : ""}
            </h1>
            <p className="mt-1 text-sm text-brand-300">
              {isComplete
                ? "Your onboarding is complete. You can review your tasks below."
                : "Complete the linked actions below. Required tasks unlock full employee access."}
            </p>
          </div>
          <OnboardingStatusBadge status={onboarding.status} />
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {isComplete ? (
          <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/80 px-5 py-4 text-sm text-emerald-900">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-semibold">Onboarding complete</p>
              <p className="mt-0.5 text-emerald-800/80">
                You now have full access to the employee portal.
              </p>
            </div>
          </div>
        ) : null}

        {/* Progress + status */}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <section className={cn(card, "p-5 xl:col-span-2")}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-brand-900">
                  Overall progress
                </h2>
                <p className="mt-0.5 text-[12px] text-brand-300">
                  Track required work, trainings, and documents
                </p>
              </div>
              <p className="text-3xl font-semibold tabular-nums tracking-tight text-brand-900">
                {percent}
                <span className="text-base font-semibold text-brand-300">%</span>
              </p>
            </div>
            <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-brand-100">
              <div
                className="h-full rounded-full bg-brand-600 transition-all"
                style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
              />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat
                label="Required"
                value={`${progress?.required_tasks?.completed ?? progress?.tasks.completed ?? 0}/${progress?.required_tasks?.total ?? progress?.tasks.total ?? 0}`}
              />
              <Stat
                label="Optional"
                value={`${progress?.optional_tasks?.completed ?? 0}/${progress?.optional_tasks?.total ?? 0}`}
              />
              <Stat
                label="Trainings"
                value={`${progress?.trainings.completed ?? 0}/${progress?.trainings.total ?? 0}`}
              />
              <Stat
                label="Documents"
                value={`${progress?.documents.total ?? 0}`}
              />
            </div>
          </section>

          <section className={cn(card, "p-5")}>
            <h2 className="text-sm font-semibold text-brand-900">
              Onboarding status
            </h2>
            <div className="mt-4 space-y-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                  Status
                </p>
                <div className="mt-1.5">
                  <OnboardingStatusBadge status={onboarding.status} />
                </div>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                  Started
                </p>
                <p className="mt-1 text-sm font-medium text-brand-900">
                  {formatDateTime(onboarding.started_at)}
                </p>
              </div>
              {onboarding.completed_at ? (
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                    Completed
                  </p>
                  <p className="mt-1 text-sm font-medium text-brand-900">
                    {formatDateTime(onboarding.completed_at)}
                  </p>
                </div>
              ) : null}
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                  Pending tasks
                </p>
                <p className="mt-1 text-sm font-medium text-brand-900">
                  {pendingCount}
                </p>
              </div>
            </div>
          </section>
        </div>

        {/* Tasks */}
        <section className={cn(card, "overflow-hidden")}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-brand-200/70 px-5 py-4">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-700">
                <ListChecks className="size-4" />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-brand-900">
                  Your tasks
                </h2>
                <p className="text-[12px] text-brand-300">
                  {!isComplete
                    ? pendingCount === 0
                      ? "All assigned tasks are done. Onboarding will complete automatically."
                      : `${pendingCount} pending task${pendingCount === 1 ? "" : "s"} remaining`
                    : "Review completed onboarding work"}
                </p>
              </div>
            </div>
          </div>

          <div className="p-4 sm:p-5">
            {tasks.length === 0 ? (
              <p className="py-8 text-center text-sm text-brand-300">
                No onboarding tasks have been assigned yet. Check back later or
                contact HR.
              </p>
            ) : (
              <ul className="space-y-3">
                {tasks.map((task) => {
                  const action = taskAction(task);
                  const done = task.status === "completed";
                  return (
                    <li
                      key={task.id}
                      className={cn(
                        "rounded-xl border p-4 transition",
                        done
                          ? "border-emerald-100 bg-emerald-50/40"
                          : "border-brand-200/70 bg-[#f7faf9]"
                      )}
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="flex min-w-0 gap-3">
                          <span
                            className={cn(
                              "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                              taskTone(task.task_type)
                            )}
                          >
                            {taskIcon(task.task_type)}
                          </span>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold text-brand-900">
                                {task.title}
                              </p>
                              <OnboardingTaskStatusBadge status={task.status} />
                            </div>
                            <p className="mt-1 text-[12px] text-brand-300">
                              {task.is_required ? "Required" : "Optional"}
                              {" · "}
                              {ONBOARDING_TASK_TYPE_LABELS[task.task_type] ||
                                task.task_type}
                            </p>
                            {task.description ? (
                              <p className="mt-2 text-sm text-brand-700/80">
                                {task.description}
                              </p>
                            ) : null}
                            {task.task_type === "manual" &&
                            task.status === "pending" ? (
                              <p className="mt-2 text-[12px] text-brand-300">
                                Waiting for HR to complete this task.
                              </p>
                            ) : null}
                            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-brand-300">
                              {task.due_date ? (
                                <span className="inline-flex items-center gap-1">
                                  <CalendarDays className="size-3.5" />
                                  Due {formatDate(task.due_date)}
                                </span>
                              ) : null}
                              {task.completed_at ? (
                                <span>
                                  Completed {formatDateTime(task.completed_at)}
                                </span>
                              ) : null}
                            </div>
                          </div>
                        </div>

                        {action ? (
                          <div className="shrink-0 sm:pt-1">
                            {action.href ? (
                              <Link
                                href={action.href}
                                className="inline-flex h-9 items-center rounded-xl bg-brand-600 px-3.5 text-xs font-semibold text-white transition hover:bg-brand-700"
                              >
                                {action.label}
                              </Link>
                            ) : null}
                            {action.sectionId ? (
                              <button
                                type="button"
                                onClick={() =>
                                  scrollToSection(action.sectionId!)
                                }
                                className="inline-flex h-9 items-center rounded-xl bg-brand-600 px-3.5 text-xs font-semibold text-white transition hover:bg-brand-700"
                              >
                                {action.label}
                              </button>
                            ) : null}
                            {!action.href &&
                            !action.sectionId &&
                            task.task_type === "acknowledgement" ? (
                              <button
                                type="button"
                                disabled={actingId === task.id}
                                onClick={() => void handleAcknowledge(task.id)}
                                className="inline-flex h-9 items-center rounded-xl bg-brand-600 px-3.5 text-xs font-semibold text-white transition hover:bg-brand-700 disabled:opacity-50"
                              >
                                {actingId === task.id
                                  ? "Saving…"
                                  : "Acknowledge"}
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        <div id="documents" className="scroll-mt-6">
          <DocumentsSection
            mode="employee"
            preferredDocumentType={preferredDocumentType}
            onChanged={() => load({ silent: true })}
          />
        </div>
        <div id="trainings" className="scroll-mt-6">
          <TrainingSection
            mode="employee"
            onChanged={() => load({ silent: true })}
          />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-[#f7faf9] px-3 py-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold tabular-nums text-brand-900">
        {value}
      </p>
    </div>
  );
}
