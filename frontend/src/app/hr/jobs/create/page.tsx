"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";
import type { EmploymentType, JobPayload, JobQuestionInput } from "@/types/jobs";
import QuestionsEditor from "@/components/QuestionsEditor";

const EMPLOYMENT_TYPES: Array<{ value: EmploymentType; label: string }> = [
  { value: "full_time", label: "Full time" },
  { value: "part_time", label: "Part time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
];

export default function CreateJobPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [departmentId, setDepartmentId] = useState<number | "">("");
  const [departments, setDepartments] = useState<Department[]>([]);
  const [position, setPosition] = useState("");
  const [employmentType, setEmploymentType] = useState<EmploymentType>("full_time");
  const [internshipMonths, setInternshipMonths] = useState("6");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [requirements, setRequirements] = useState("");
  const [questions, setQuestions] = useState<JobQuestionInput[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState<"draft" | "publish" | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setDepartments(await api.listDepartments("active"));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load departments");
      }
    };
    load();
  }, []);

  const payload = (): JobPayload => ({
    title,
    description,
    department_id: departmentId === "" ? undefined : Number(departmentId),
    position: position || undefined,
    location: location || undefined,
    employment_type: employmentType,
    internship_duration_months:
      employmentType === "internship" ? Number(internshipMonths) : null,
    requirements: requirements || undefined,
    questions: questions.filter((question) => question.prompt.trim()),
  });

  const handleSubmit = async (e: FormEvent, action: "draft" | "publish") => {
    e.preventDefault();
    setError("");
    setSubmitting(action);
    try {
      const created = await api.createJob(payload());
      if (action === "publish") {
        await api.publishJob(created.id);
      }
      router.push(`/hr/jobs/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save job offer");
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900">Create Job Offer</h1>
      <p className="mt-1 text-sm text-gray-600 mb-6">
        Save as draft until the offer is ready, then publish it.
      </p>

      <form className="bg-white rounded-xl border shadow-sm p-6 space-y-5">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        <Field label="Title" id="title">
          <input
            id="title"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
          />
        </Field>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Department" id="department">
            <select
              id="department"
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : "")}
              className={inputClass}
            >
              <option value="">No department</option>
              {departments.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Position" id="position">
            <input
              id="position"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              className={inputClass}
            />
          </Field>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Employment type" id="employmentType">
            <select
              id="employmentType"
              value={employmentType}
              onChange={(e) => setEmploymentType(e.target.value as EmploymentType)}
              className={inputClass}
            >
              {EMPLOYMENT_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Location" id="location">
            <input
              id="location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className={inputClass}
            />
          </Field>
        </div>

        {employmentType === "internship" && (
          <Field label="Internship duration (months)" id="internshipMonths">
            <input
              id="internshipMonths"
              type="number"
              min={1}
              max={24}
              required
              value={internshipMonths}
              onChange={(e) => setInternshipMonths(e.target.value)}
              className={inputClass}
            />
          </Field>
        )}

        <Field label="Description" id="description">
          <textarea
            id="description"
            required
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Requirements" id="requirements">
          <textarea
            id="requirements"
            rows={4}
            value={requirements}
            onChange={(e) => setRequirements(e.target.value)}
            className={inputClass}
          />
        </Field>

        <QuestionsEditor questions={questions} onChange={setQuestions} />

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            type="button"
            disabled={!!submitting}
            onClick={(e) => handleSubmit(e, "draft")}
            className="flex-1 border border-gray-300 text-gray-800 py-2.5 rounded-lg font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            {submitting === "draft" ? "Saving..." : "Save as Draft"}
          </button>
          <button
            type="button"
            disabled={!!submitting}
            onClick={(e) => handleSubmit(e, "publish")}
            className="flex-1 bg-brand-600 text-white py-2.5 rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting === "publish" ? "Publishing..." : "Publish"}
          </button>
        </div>
      </form>
    </div>
  );
}

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

function Field({
  label,
  id,
  children,
}: {
  label: string;
  id: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}
