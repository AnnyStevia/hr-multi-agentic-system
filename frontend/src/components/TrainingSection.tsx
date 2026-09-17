"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ApplicationSection } from "@/components/ApplicationSection";
import { api } from "@/lib/api";
import type { OnboardingTrainingAssignment, Training } from "@/types/training";

type TrainingSectionProps = {
  mode: "employee" | "hr";
  onboardingId?: number;
};

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function statusLabel(status: string): string {
  return status === "completed" ? "Completed" : "Pending";
}

export function TrainingSection({ mode, onboardingId }: TrainingSectionProps) {
  const [assignments, setAssignments] = useState<OnboardingTrainingAssignment[]>([]);
  const [catalog, setCatalog] = useState<Training[]>([]);
  const [selectedTrainingId, setSelectedTrainingId] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      if (mode === "employee") {
        setAssignments(await api.listMyOnboardingTrainings());
      } else {
        if (!onboardingId) {
          setAssignments([]);
          setCatalog([]);
          return;
        }
        const [assigned, trainings] = await Promise.all([
          api.listOnboardingTrainings(onboardingId),
          api.listTrainings(),
        ]);
        setAssignments(assigned);
        setCatalog(trainings);
      }
    } catch (err) {
      setAssignments([]);
      setCatalog([]);
      setError(err instanceof Error ? err.message : "Failed to load trainings");
    } finally {
      setLoading(false);
    }
  }, [mode, onboardingId]);

  useEffect(() => {
    load();
  }, [load]);

  const availableTrainings = useMemo(() => {
    const assignedIds = new Set(assignments.map((item) => item.training_id));
    return catalog.filter((item) => !assignedIds.has(item.id));
  }, [assignments, catalog]);

  const handleComplete = async (assignmentId: number) => {
    setBusyId(assignmentId);
    setError("");
    try {
      await api.completeMyOnboardingTraining(assignmentId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete training");
    } finally {
      setBusyId(null);
    }
  };

  const handleAssign = async (event: FormEvent) => {
    event.preventDefault();
    if (!onboardingId || !selectedTrainingId) return;
    setAssigning(true);
    setError("");
    try {
      await api.assignOnboardingTraining(onboardingId, Number(selectedTrainingId));
      setSelectedTrainingId("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign training");
    } finally {
      setAssigning(false);
    }
  };

  const handleCreateAndAssign = async (event: FormEvent) => {
    event.preventDefault();
    if (!onboardingId || !newTitle.trim()) return;
    setCreating(true);
    setError("");
    try {
      const created = await api.createTraining({
        title: newTitle.trim(),
        description: newDescription.trim() || null,
      });
      await api.assignOnboardingTraining(onboardingId, created.id);
      setNewTitle("");
      setNewDescription("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create training");
    } finally {
      setCreating(false);
    }
  };

  const handleRemove = async (assignmentId: number) => {
    if (!onboardingId) return;
    if (!window.confirm("Remove this training assignment?")) return;
    setBusyId(assignmentId);
    setError("");
    try {
      await api.removeOnboardingTraining(onboardingId, assignmentId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove assignment");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <ApplicationSection title="Training">
      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {mode === "hr" && onboardingId && (
        <div className="mb-6 space-y-4">
          <form onSubmit={handleAssign} className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
            <div className="sm:col-span-2">
              <label className="block text-xs text-gray-500 mb-1" htmlFor="assign-training">
                Assign existing training
              </label>
              <select
                id="assign-training"
                value={selectedTrainingId}
                onChange={(e) => setSelectedTrainingId(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">Select a training…</option>
                {availableTrainings.map((training) => (
                  <option key={training.id} value={training.id}>
                    {training.title}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={assigning || !selectedTrainingId}
              className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {assigning ? "Assigning..." : "Assign"}
            </button>
          </form>

          <form onSubmit={handleCreateAndAssign} className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
            <div>
              <label className="block text-xs text-gray-500 mb-1" htmlFor="new-training-title">
                New training title
              </label>
              <input
                id="new-training-title"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                placeholder="e.g. Security awareness"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1" htmlFor="new-training-desc">
                Description (optional)
              </label>
              <input
                id="new-training-desc"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={creating || !newTitle.trim()}
              className="border border-gray-300 px-3 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
            >
              {creating ? "Creating..." : "Create & assign"}
            </button>
          </form>
        </div>
      )}

      {loading ? (
        <div className="py-8 flex justify-center">
          <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-brand-600" />
        </div>
      ) : assignments.length === 0 ? (
        <p className="text-sm text-gray-500">No trainings assigned yet.</p>
      ) : (
        <ul className="space-y-3">
          {assignments.map((assignment) => (
            <li
              key={assignment.id}
              className={`border rounded-lg p-4 space-y-2 ${
                assignment.status === "completed"
                  ? "border-green-100 bg-green-50/40"
                  : "border-gray-200 bg-white"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{assignment.title}</p>
                  {assignment.description && (
                    <p className="mt-1 text-sm text-gray-600">{assignment.description}</p>
                  )}
                </div>
                <span
                  className={`text-xs font-medium px-2 py-1 rounded-full ${
                    assignment.status === "completed"
                      ? "bg-green-100 text-green-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {statusLabel(assignment.status)}
                </span>
              </div>
              {assignment.completed_at && (
                <p className="text-xs text-gray-500">
                  Completed {formatDateTime(assignment.completed_at)}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {mode === "employee" && assignment.status === "pending" && (
                  <button
                    type="button"
                    disabled={busyId === assignment.id}
                    onClick={() => handleComplete(assignment.id)}
                    className="bg-brand-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
                  >
                    {busyId === assignment.id ? "Completing..." : "Mark as completed"}
                  </button>
                )}
                {mode === "hr" && (
                  <button
                    type="button"
                    disabled={busyId === assignment.id}
                    onClick={() => handleRemove(assignment.id)}
                    className="border border-red-200 text-red-700 px-3 py-1.5 rounded-lg text-sm hover:bg-red-50 disabled:opacity-50"
                  >
                    Remove
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </ApplicationSection>
  );
}
