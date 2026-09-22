"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DOCUMENT_TYPE_LABELS, type DocumentType } from "@/types/documents";
import {
  ONBOARDING_TASK_TYPE_LABELS,
  type EmployeeDocumentType,
  type OnboardingTaskTemplate,
  type OnboardingTaskType,
} from "@/types/onboarding";
import type { Training } from "@/types/training";

const TASK_TYPES = Object.keys(ONBOARDING_TASK_TYPE_LABELS) as OnboardingTaskType[];
const DOCUMENT_TYPES = Object.keys(DOCUMENT_TYPE_LABELS) as DocumentType[];

export default function OnboardingTaskTemplatesPage() {
  const [templates, setTemplates] = useState<OnboardingTaskTemplate[]>([]);
  const [trainings, setTrainings] = useState<Training[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [taskType, setTaskType] = useState<OnboardingTaskType>("manual");
  const [documentType, setDocumentType] = useState<EmployeeDocumentType>("id_document");
  const [trainingId, setTrainingId] = useState("");
  const [isRequired, setIsRequired] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = async () => {
    setError("");
    setLoading(true);
    try {
      const [templateRows, trainingRows] = await Promise.all([
        api.listOnboardingTaskTemplates(),
        api.listTrainings(),
      ]);
      setTemplates(templateRows);
      setTrainings(trainingRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.createOnboardingTaskTemplate({
        title,
        description: description.trim() || null,
        task_type: taskType,
        is_required: isRequired,
        is_active: true,
        document_type: taskType === "document" ? documentType : null,
        training_id: taskType === "training" ? Number(trainingId) : null,
      });
      setTitle("");
      setDescription("");
      setTaskType("manual");
      setDocumentType("id_document");
      setTrainingId("");
      setIsRequired(true);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create template");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleActive = async (template: OnboardingTaskTemplate) => {
    setActingId(template.id);
    setError("");
    try {
      await api.updateOnboardingTaskTemplate(template.id, {
        is_active: !template.is_active,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update template");
    } finally {
      setActingId(null);
    }
  };

  const handleDelete = async (template: OnboardingTaskTemplate) => {
    setActingId(template.id);
    setError("");
    try {
      await api.deleteOnboardingTaskTemplate(template.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete template");
    } finally {
      setActingId(null);
    }
  };

  const trainingTitle = (id: number | null | undefined) =>
    trainings.find((item) => item.id === id)?.title || (id ? `#${id}` : "—");

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Task catalogue</h1>
        <p className="mt-1 text-sm text-gray-600">
          Reusable onboarding templates. Active templates are assigned automatically when a new
          employee is hired. Editing a template does not change existing employee tasks.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleCreate} className="bg-white rounded-xl border shadow-sm p-6 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Template title"
            className="px-4 py-2.5 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500"
          />
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value as OnboardingTaskType)}
            className="px-4 py-2.5 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500"
          >
            {TASK_TYPES.map((type) => (
              <option key={type} value={type}>
                {ONBOARDING_TASK_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>
        {taskType === "document" && (
          <select
            required
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value as EmployeeDocumentType)}
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500"
          >
            {DOCUMENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {DOCUMENT_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        )}
        {taskType === "training" && (
          <select
            required
            value={trainingId}
            onChange={(e) => setTrainingId(e.target.value)}
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Select training</option>
            {trainings.map((training) => (
              <option key={training.id} value={training.id}>
                {training.title}
              </option>
            ))}
          </select>
        )}
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          rows={2}
          className="w-full px-4 py-2.5 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500"
        />
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={isRequired}
            onChange={(e) => setIsRequired(e.target.checked)}
          />
          Required for onboarding completion
        </label>
        <button
          type="submit"
          disabled={submitting || (taskType === "training" && !trainingId)}
          className="bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Adding..." : "Add template"}
        </button>
      </form>

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : templates.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-500">No templates yet.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Title
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Config
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Required
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {templates.map((template) => (
                <tr key={template.id}>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    <p>{template.title}</p>
                    {template.description && (
                      <p className="text-xs text-gray-500 mt-0.5">{template.description}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {ONBOARDING_TASK_TYPE_LABELS[template.task_type]}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {template.task_type === "document"
                      ? template.document_type
                        ? DOCUMENT_TYPE_LABELS[template.document_type]
                        : "—"
                      : template.task_type === "training"
                        ? trainingTitle(template.training_id)
                        : "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {template.is_required ? "Yes" : "No"}
                  </td>
                  <td className="px-4 py-3 text-sm capitalize">
                    {template.is_active ? "Active" : "Inactive"}
                  </td>
                  <td className="px-4 py-3 text-right space-x-3">
                    <button
                      type="button"
                      disabled={actingId === template.id}
                      onClick={() => toggleActive(template)}
                      className="text-sm text-brand-700 disabled:opacity-50"
                    >
                      {template.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      type="button"
                      disabled={actingId === template.id}
                      onClick={() => handleDelete(template)}
                      className="text-sm text-red-700 disabled:opacity-50"
                    >
                      Delete
                    </button>
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
