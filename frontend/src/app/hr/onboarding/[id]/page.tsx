"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ApplicationSection } from "@/components/ApplicationSection";
import { DocumentsSection } from "@/components/DocumentsSection";
import { OnboardingProgressSection } from "@/components/OnboardingProgressSection";
import { TrainingSection } from "@/components/TrainingSection";
import { OnboardingStatusBadge } from "@/components/OnboardingStatusBadge";
import { OnboardingTaskStatusBadge } from "@/components/OnboardingTaskStatusBadge";
import { api } from "@/lib/api";
import type { Employee } from "@/types/employees";
import {
  ONBOARDING_TASK_TYPE_LABELS,
  type Onboarding,
  type OnboardingProgress,
  type OnboardingTask,
  type OnboardingTaskStatus,
} from "@/types/onboarding";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

type TaskEditForm = {
  title: string;
  description: string;
  due_date: string;
  status: OnboardingTaskStatus;
};

export default function OnboardingDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const onboardingId = Number(params.id);

  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [progress, setProgress] = useState<OnboardingProgress | null>(null);
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [tasks, setTasks] = useState<OnboardingTask[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [createTitle, setCreateTitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createDueDate, setCreateDueDate] = useState("");
  const [creating, setCreating] = useState(false);

  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<TaskEditForm>({
    title: "",
    description: "",
    due_date: "",
    status: "pending",
  });
  const [savingTaskId, setSavingTaskId] = useState<number | null>(null);
  const [deletingTaskId, setDeletingTaskId] = useState<number | null>(null);
  const [completingOnboarding, setCompletingOnboarding] = useState(false);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const onboardingData = await api.getOnboarding(onboardingId);
      const [employeeData, taskData, progressData] = await Promise.all([
        api.getEmployee(onboardingData.employee_id),
        api.listOnboardingTasks(onboardingId),
        api.getOnboardingProgress(onboardingId),
      ]);
      setOnboarding(onboardingData);
      setEmployee(employeeData);
      setTasks(taskData);
      setProgress(progressData);
    } catch (err) {
      setOnboarding(null);
      setEmployee(null);
      setTasks([]);
      setProgress(null);
      setError(err instanceof Error ? err.message : "Failed to load onboarding");
    } finally {
      setLoading(false);
    }
  }, [onboardingId]);

  useEffect(() => {
    if (!Number.isNaN(onboardingId)) {
      load();
    }
  }, [load, onboardingId]);

  const handleCreateTask = async (event: FormEvent) => {
    event.preventDefault();
    if (!createTitle.trim()) {
      setError("Task title is required.");
      return;
    }
    setCreating(true);
    setError("");
    try {
      await api.createOnboardingTask(onboardingId, {
        title: createTitle.trim(),
        description: createDescription.trim() || null,
        due_date: createDueDate || null,
      });
      setCreateTitle("");
      setCreateDescription("");
      setCreateDueDate("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (task: OnboardingTask) => {
    setEditingTaskId(task.id);
    setEditForm({
      title: task.title,
      description: task.description || "",
      due_date: task.due_date || "",
      status: task.status,
    });
  };

  const cancelEdit = () => {
    setEditingTaskId(null);
  };

  const handleSaveTask = async (taskId: number) => {
    if (!editForm.title.trim()) {
      setError("Task title is required.");
      return;
    }
    setSavingTaskId(taskId);
    setError("");
    try {
      const task = tasks.find((item) => item.id === taskId);
      const payload: Parameters<typeof api.updateOnboardingTask>[1] = {
        title: editForm.title.trim(),
        description: editForm.description.trim() || null,
        due_date: editForm.due_date || null,
      };
      if (task?.task_type === "manual") {
        payload.status = editForm.status;
      }
      await api.updateOnboardingTask(taskId, payload);
      setEditingTaskId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update task");
    } finally {
      setSavingTaskId(null);
    }
  };

  const handleCompleteManualTask = async (taskId: number) => {
    setSavingTaskId(taskId);
    setError("");
    try {
      await api.completeManualOnboardingTask(taskId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete task");
    } finally {
      setSavingTaskId(null);
    }
  };

  const handleDeleteTask = async (taskId: number) => {
    if (!window.confirm("Delete this task?")) return;
    setDeletingTaskId(taskId);
    setError("");
    try {
      await api.deleteOnboardingTask(taskId);
      if (editingTaskId === taskId) {
        setEditingTaskId(null);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete task");
    } finally {
      setDeletingTaskId(null);
    }
  };

  const handleCompleteOnboarding = async () => {
    if (!window.confirm("Mark this onboarding as completed?")) return;
    setCompletingOnboarding(true);
    setError("");
    try {
      await api.completeOnboarding(onboardingId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete onboarding");
    } finally {
      setCompletingOnboarding(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!onboarding || !employee) {
    return (
      <div className="max-w-4xl mx-auto">
        <p className="text-red-700">{error || "Onboarding not found"}</p>
        <button
          type="button"
          onClick={() => router.push("/hr/onboarding")}
          className="mt-4 text-sm text-brand-700"
        >
          Back to onboarding
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/hr/onboarding" className="text-sm text-gray-500 hover:text-gray-800">
            Onboarding
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{employee.full_name}</h1>
            <OnboardingStatusBadge status={onboarding.status} />
          </div>
          <p className="mt-1 text-sm text-gray-600">{employee.position}</p>
        </div>
        {onboarding.status === "in_progress" && (
          <div className="text-right space-y-1">
            <button
              type="button"
              disabled={completingOnboarding}
              onClick={handleCompleteOnboarding}
              className="border border-gray-300 bg-white text-gray-700 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
            >
              {completingOnboarding ? "Completing..." : "Mark onboarding complete"}
            </button>
            <p className="text-xs text-gray-500 max-w-xs">
              Override only — normally completes when the employee finishes all tasks.
            </p>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <ApplicationSection title="Employee information">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-500">Employee number</p>
            <p className="mt-0.5 text-gray-900">{employee.employee_number}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Email</p>
            <p className="mt-0.5 text-gray-900">{employee.email}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Department</p>
            <p className="mt-0.5 text-gray-900">{employee.department}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Position</p>
            <p className="mt-0.5 text-gray-900">{employee.position}</p>
          </div>
        </div>
      </ApplicationSection>

      <ApplicationSection title="Onboarding">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-500">Status</p>
            <div className="mt-1">
              <OnboardingStatusBadge status={onboarding.status} />
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500">Started</p>
            <p className="mt-0.5 text-gray-900">{formatDateTime(onboarding.started_at)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Completed</p>
            <p className="mt-0.5 text-gray-900">{formatDateTime(onboarding.completed_at)}</p>
          </div>
        </div>
      </ApplicationSection>

      <OnboardingProgressSection progress={progress} />

      <ApplicationSection title="Tasks">
        <form onSubmit={handleCreateTask} className="space-y-3 mb-6 pb-6 border-b border-gray-200">
          <h3 className="text-sm font-medium text-gray-900">Add task</h3>
          <div>
            <label htmlFor="task-title" className="block text-xs text-gray-500 mb-1">
              Title
            </label>
            <input
              id="task-title"
              required
              value={createTitle}
              onChange={(e) => setCreateTitle(e.target.value)}
              className={inputClass}
              placeholder="e.g. Sign employment contract"
            />
          </div>
          <div>
            <label htmlFor="task-description" className="block text-xs text-gray-500 mb-1">
              Description
            </label>
            <textarea
              id="task-description"
              rows={2}
              value={createDescription}
              onChange={(e) => setCreateDescription(e.target.value)}
              className={inputClass}
              placeholder="Optional details"
            />
          </div>
          <div>
            <label htmlFor="task-due-date" className="block text-xs text-gray-500 mb-1">
              Due date
            </label>
            <input
              id="task-due-date"
              type="date"
              value={createDueDate}
              onChange={(e) => setCreateDueDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <button
            type="submit"
            disabled={creating}
            className="bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create task"}
          </button>
        </form>

        {tasks.length === 0 ? (
          <p className="text-sm text-gray-500">No tasks yet. Add the first onboarding task above.</p>
        ) : (
          <div className="space-y-4">
            {tasks.map((task) => (
              <div key={task.id} className="border border-gray-200 rounded-lg p-4 space-y-3">
                {editingTaskId === task.id ? (
                  <>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Title</label>
                      <input
                        value={editForm.title}
                        onChange={(e) => setEditForm((current) => ({ ...current, title: e.target.value }))}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Description</label>
                      <textarea
                        rows={2}
                        value={editForm.description}
                        onChange={(e) =>
                          setEditForm((current) => ({ ...current, description: e.target.value }))
                        }
                        className={inputClass}
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Due date</label>
                        <input
                          type="date"
                          value={editForm.due_date}
                          onChange={(e) =>
                            setEditForm((current) => ({ ...current, due_date: e.target.value }))
                          }
                          className={inputClass}
                        />
                      </div>
                      {task.task_type === "manual" && (
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Status</label>
                          <select
                            value={editForm.status}
                            onChange={(e) =>
                              setEditForm((current) => ({
                                ...current,
                                status: e.target.value as OnboardingTaskStatus,
                              }))
                            }
                            className={inputClass}
                          >
                            <option value="pending">Pending</option>
                            <option value="completed">Completed</option>
                          </select>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={savingTaskId === task.id}
                        onClick={() => handleSaveTask(task.id)}
                        className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
                      >
                        {savingTaskId === task.id ? "Saving..." : "Save"}
                      </button>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        className="border border-gray-300 px-3 py-2 rounded-lg text-sm font-medium hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{task.title}</p>
                        <p className="mt-1 text-xs text-gray-500">
                          {task.is_required ? "Required" : "Optional"}
                          {" · "}
                          {ONBOARDING_TASK_TYPE_LABELS[task.task_type] || task.task_type}
                        </p>
                        {task.description && (
                          <p className="mt-1 text-sm text-gray-600">{task.description}</p>
                        )}
                      </div>
                      <OnboardingTaskStatusBadge status={task.status} />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-xs text-gray-500">Due date</p>
                        <p className="mt-0.5 text-gray-900">{formatDate(task.due_date)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Completed</p>
                        <p className="mt-0.5 text-gray-900">{formatDateTime(task.completed_at)}</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {task.task_type === "manual" && task.status === "pending" && (
                        <button
                          type="button"
                          disabled={savingTaskId === task.id}
                          onClick={() => handleCompleteManualTask(task.id)}
                          className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
                        >
                          {savingTaskId === task.id ? "Completing..." : "Mark completed"}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => startEdit(task)}
                        className="border border-gray-300 px-3 py-2 rounded-lg text-sm font-medium hover:bg-gray-50"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        disabled={deletingTaskId === task.id}
                        onClick={() => handleDeleteTask(task.id)}
                        className="border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm font-medium hover:bg-red-50 disabled:opacity-50"
                      >
                        {deletingTaskId === task.id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </ApplicationSection>

      <DocumentsSection mode="hr" employeeId={employee.id} allowDelete />
      <TrainingSection mode="hr" onboardingId={onboarding.id} />
    </div>
  );
}
