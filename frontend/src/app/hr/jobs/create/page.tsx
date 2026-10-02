"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Briefcase,
  Building2,
  CircleHelp,
  FileText,
  ListChecks,
  MapPin,
  Sparkles,
} from "lucide-react";
import QuestionsEditor from "@/components/QuestionsEditor";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";
import type { EmploymentType, JobPayload, JobQuestionInput } from "@/types/jobs";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

const field =
  "h-10 w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

const area =
  "w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 py-2.5 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

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
    void load();
  }, []);

  const selectedDepartment = useMemo(
    () => departments.find((item) => item.id === departmentId) ?? null,
    [departments, departmentId]
  );

  const filledQuestions = questions.filter((question) => question.prompt.trim()).length;

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
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[920px] space-y-5">
        <Link
          href="/hr/jobs"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0f224a]/70 transition hover:text-[#0f224a]"
        >
          <ArrowLeft className="size-4" />
          Back to job offers
        </Link>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              Recruitment
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-brand-900">
              Create job offer
            </h1>
            <p className="mt-1 text-sm text-brand-300">
              Save as draft until ready, then publish to careers.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[12px] font-medium text-brand-700 shadow-sm ring-1 ring-brand-200/70">
              <Briefcase className="size-3.5 text-brand-600" />
              {EMPLOYMENT_TYPES.find((item) => item.value === employmentType)?.label}
            </span>
            {selectedDepartment ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[12px] font-medium text-brand-700 shadow-sm ring-1 ring-brand-200/70">
                <Building2 className="size-3.5 text-brand-600" />
                {selectedDepartment.name}
              </span>
            ) : null}
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <form className="space-y-5" onSubmit={(e) => e.preventDefault()}>
          <Section
            icon={<Sparkles className="size-4" />}
            title="Basics"
            subtitle="Title and where this role sits in the organization"
          >
            <Field label="Job title" id="title" required>
              <input
                id="title"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Community Manager"
                className={field}
              />
            </Field>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Department" id="department">
                <Select
                  id="department"
                  value={departmentId === "" ? "" : String(departmentId)}
                  onValueChange={(next) =>
                    setDepartmentId(next ? Number(next) : "")
                  }
                  triggerClassName={field}
                  options={[
                    { value: "", label: "No department" },
                    ...departments.map((department) => ({
                      value: String(department.id),
                      label: department.name,
                    })),
                  ]}
                />
              </Field>
              <Field label="Position label" id="position">
                <input
                  id="position"
                  value={position}
                  onChange={(e) => setPosition(e.target.value)}
                  placeholder="Optional display title"
                  className={field}
                />
              </Field>
            </div>
          </Section>

          <Section
            icon={<MapPin className="size-4" />}
            title="Role details"
            subtitle="Employment type, location, and internship duration"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Employment type" id="employmentType">
                <Select
                  id="employmentType"
                  value={employmentType}
                  onValueChange={(next) =>
                    setEmploymentType(next as EmploymentType)
                  }
                  triggerClassName={field}
                  options={EMPLOYMENT_TYPES.map((type) => ({
                    value: type.value,
                    label: type.label,
                  }))}
                />
              </Field>
              <Field label="Location" id="location">
                <input
                  id="location"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="e.g. Tangier, Morocco · Remote"
                  className={field}
                />
              </Field>
            </div>

            {employmentType === "internship" ? (
              <Field
                label="Internship duration (months)"
                id="internshipMonths"
                required
              >
                <input
                  id="internshipMonths"
                  type="number"
                  min={1}
                  max={24}
                  required
                  value={internshipMonths}
                  onChange={(e) => setInternshipMonths(e.target.value)}
                  className={field}
                />
              </Field>
            ) : null}
          </Section>

          <Section
            icon={<FileText className="size-4" />}
            title="Description & requirements"
            subtitle="What candidates will read on the careers page"
          >
            <Field label="Description" id="description" required>
              <textarea
                id="description"
                required
                rows={6}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Summarize the role, team, and impact…"
                className={area}
              />
            </Field>
            <Field label="Requirements" id="requirements">
              <textarea
                id="requirements"
                rows={5}
                value={requirements}
                onChange={(e) => setRequirements(e.target.value)}
                placeholder="One requirement per line works best…"
                className={area}
              />
            </Field>
          </Section>

          <Section
            icon={<CircleHelp className="size-4" />}
            title="Application questions"
            subtitle={
              filledQuestions > 0
                ? `${filledQuestions} question${filledQuestions === 1 ? "" : "s"} ready`
                : "Optional questions candidates answer when they apply"
            }
          >
            <QuestionsEditor questions={questions} onChange={setQuestions} />
          </Section>

          <section className={cn(card, "overflow-hidden")}>
            <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
                  <ListChecks className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-brand-900">Ready to save?</p>
                  <p className="mt-0.5 text-[13px] text-brand-300">
                    Drafts stay internal. Publish makes the offer visible on careers.
                  </p>
                </div>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <button
                  type="button"
                  disabled={!!submitting}
                  onClick={(e) => void handleSubmit(e, "draft")}
                  className="inline-flex h-10 items-center justify-center rounded-xl border border-brand-200 bg-white px-4 text-sm font-semibold text-brand-700 transition hover:bg-[#f3f6f5] disabled:opacity-50"
                >
                  {submitting === "draft" ? "Saving…" : "Save as draft"}
                </button>
                <button
                  type="button"
                  disabled={!!submitting}
                  onClick={(e) => void handleSubmit(e, "publish")}
                  className="inline-flex h-10 items-center justify-center rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-50"
                >
                  {submitting === "publish" ? "Publishing…" : "Publish offer"}
                </button>
              </div>
            </div>
          </section>
        </form>
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section className={cn(card, "overflow-visible")}>
      <div className="flex items-start gap-3 border-b border-brand-200/70 px-5 py-4">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-700">
          {icon}
        </span>
        <div>
          <h2 className="text-sm font-semibold text-brand-900">{title}</h2>
          <p className="mt-0.5 text-[12px] text-brand-300">{subtitle}</p>
        </div>
      </div>
      <div className="relative z-10 space-y-4 overflow-visible p-5">{children}</div>
    </section>
  );
}

function Field({
  label,
  id,
  required,
  children,
}: {
  label: string;
  id: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-[12px] font-semibold text-brand-700"
      >
        {label}
        {required ? <span className="text-rose-500"> *</span> : null}
      </label>
      {children}
    </div>
  );
}
