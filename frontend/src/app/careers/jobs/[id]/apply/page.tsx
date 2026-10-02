"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Briefcase,
  Building2,
  CheckCircle2,
  CircleHelp,
  FileText,
  GraduationCap,
  MapPin,
  Plus,
  Sparkles,
  Trash2,
  Upload,
  UserRound,
} from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { EMPLOYMENT_TYPE_LABELS } from "@/types/employees";
import type { ApplicationDetail, CvExtractionResult } from "@/types/applications";
import type { EducationEntry, ExperienceEntry } from "@/types/applications";
import type { Job, JobQuestion } from "@/types/jobs";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

const field =
  "h-10 w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

const area =
  "w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 py-2.5 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

const emptyEducation = (): EducationEntry => ({
  institution: "",
  degree: "",
  field_of_study: "",
});
const emptyExperience = (): ExperienceEntry => ({
  company: "",
  title: "",
  description: "",
});

function isBlankEducation(rows: EducationEntry[]): boolean {
  return rows.every(
    (row) =>
      !row.institution.trim() &&
      !(row.degree || "").trim() &&
      !(row.field_of_study || "").trim()
  );
}

function isBlankExperience(rows: ExperienceEntry[]): boolean {
  return rows.every(
    (row) =>
      !row.company.trim() &&
      !row.title.trim() &&
      !(row.description || "").trim()
  );
}

function mapExtractedEducation(extraction: CvExtractionResult): EducationEntry[] {
  return extraction.education
    .filter((item) => (item.institution || "").trim())
    .map((item) => ({
      institution: (item.institution || "").trim(),
      degree: item.degree?.trim() || "",
      field_of_study: item.field_of_study?.trim() || "",
      start_year: item.start_year,
      end_year: item.end_year,
    }));
}

function mapExtractedExperience(extraction: CvExtractionResult): ExperienceEntry[] {
  return extraction.experience
    .filter((item) => (item.company || "").trim() && (item.title || "").trim())
    .map((item) => ({
      company: (item.company || "").trim(),
      title: (item.title || "").trim(),
      description: item.description?.trim() || "",
      start_year: item.start_year,
      end_year: item.end_year,
    }));
}

export default function ApplyPage() {
  const params = useParams<{ id: string }>();
  const jobId = Number(params.id);
  const { user } = useAuth();
  const [job, setJob] = useState<Job | null>(null);
  const [existing, setExisting] = useState<ApplicationDetail | null>(null);
  const [submitted, setSubmitted] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [extractHint, setExtractHint] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [phone, setPhone] = useState("");
  const [education, setEducation] = useState<EducationEntry[]>([emptyEducation()]);
  const [experience, setExperience] = useState<ExperienceEntry[]>([emptyExperience()]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [cv, setCv] = useState<File | null>(null);
  const [coverLetter, setCoverLetter] = useState<File | null>(null);

  useEffect(() => {
    if (user?.phone) {
      setPhone(user.phone);
    }
  }, [user]);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const jobData = await api.getCareerJob(jobId);
        setJob(jobData);
        try {
          setExisting(await api.getMyJobApplication(jobId));
        } catch {
          setExisting(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load job");
      } finally {
        setLoading(false);
      }
    };
    if (!Number.isNaN(jobId)) {
      void load();
    }
  }, [jobId]);

  const handleCvSelected = async (file: File | null) => {
    setCv(file);
    setExtractHint("");
    if (!file) return;
    if (
      !file.name.toLowerCase().endsWith(".pdf") &&
      file.type !== "application/pdf"
    ) {
      setExtractHint(
        "Automatic pre-fill works with PDF CVs. You can still fill the form manually."
      );
      return;
    }
    setExtracting(true);
    try {
      const { extraction } = await api.extractCvFromUpload(file);
      if (extraction.phone?.trim()) {
        setPhone((current) =>
          current.trim() ? current : extraction.phone!.trim()
        );
      }
      const mappedEdu = mapExtractedEducation(extraction);
      if (mappedEdu.length > 0) {
        setEducation((current) =>
          isBlankEducation(current) ? mappedEdu : current
        );
      }
      const mappedExp = mapExtractedExperience(extraction);
      if (mappedExp.length > 0) {
        setExperience((current) =>
          isBlankExperience(current) ? mappedExp : current
        );
      }
      setExtractHint(
        "We pre-filled empty fields from your CV. Review before submitting."
      );
    } catch (err) {
      setExtractHint(
        err instanceof Error
          ? `${err.message} You can still fill the form manually.`
          : "Could not read the CV. You can still fill the form manually."
      );
    } finally {
      setExtracting(false);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setFieldError("");
    if (!cv) {
      setFieldError("A CV is required (PDF, DOC, or DOCX).");
      return;
    }
    if (phone.trim().replace(/\D/g, "").length < 8) {
      setFieldError("Enter a valid phone number.");
      return;
    }
    if (
      education.some((item) => !item.institution.trim()) ||
      experience.some((item) => !item.company.trim() || !item.title.trim())
    ) {
      setFieldError("Complete at least one education and one experience entry.");
      return;
    }
    const missing = (job?.questions || []).filter(
      (question) => question.required && !answers[question.id]?.trim()
    );
    if (missing.length) {
      setFieldError(`Answer required: ${missing[0].prompt}`);
      return;
    }

    const form = new FormData();
    form.append("phone", phone.trim());
    form.append("education", JSON.stringify(education));
    form.append("experience", JSON.stringify(experience));
    form.append(
      "answers",
      JSON.stringify(
        Object.entries(answers)
          .filter(([, value]) => value.trim())
          .map(([question_id, value]) => ({
            question_id: Number(question_id),
            value,
          }))
      )
    );
    form.append("cv", cv);
    if (coverLetter) {
      form.append("cover_letter", coverLetter);
    }

    setSubmitting(true);
    try {
      setSubmitted(await api.applyToJob(jobId, form));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to submit application"
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center bg-[#f3f6f5] p-6">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-full bg-[#f3f6f5] p-5 sm:p-6">
        <div className="mx-auto max-w-[920px]">
          <p className="text-sm text-red-700">{error || "Job not found"}</p>
          <Link
            href="/careers/jobs"
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700"
          >
            <ArrowLeft className="size-4" />
            Back to openings
          </Link>
        </div>
      </div>
    );
  }

  if (existing || submitted) {
    const application = submitted || existing;
    return (
      <div className="min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
        <div className="mx-auto max-w-[720px] space-y-5">
          <Link
            href={`/careers/jobs/${job.id}`}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0f224a]/70 transition hover:text-[#0f224a]"
          >
            <ArrowLeft className="size-4" />
            Back to job
          </Link>
          <section className={cn(card, "p-6 sm:p-8")}>
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
              <CheckCircle2 className="size-6" />
            </span>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight text-brand-900">
              {submitted ? "Application submitted" : "Already applied"}
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-brand-300">
              Your application for{" "}
              <span className="font-semibold text-brand-900">{job.title}</span>{" "}
              has been received.
            </p>
            {application ? (
              <div className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[#f7faf9] px-3 py-2 text-sm text-brand-700">
                <span className="text-brand-300">Status</span>
                <StatusBadge status={application.status} />
              </div>
            ) : null}
            <div className="mt-6 flex flex-wrap gap-2">
              <Link
                href={`/careers/jobs/${job.id}`}
                className="inline-flex h-10 items-center rounded-xl border border-brand-200 bg-white px-4 text-sm font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
              >
                View job
              </Link>
              <Link
                href="/careers/jobs"
                className="inline-flex h-10 items-center rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white transition hover:bg-brand-700"
              >
                Browse openings
              </Link>
            </div>
          </section>
        </div>
      </div>
    );
  }

  const employmentLabel =
    EMPLOYMENT_TYPE_LABELS[job.employment_type] || job.employment_type;

  return (
    <div className="min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[920px] space-y-5">
        <Link
          href={`/careers/jobs/${job.id}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0f224a]/70 transition hover:text-[#0f224a]"
        >
          <ArrowLeft className="size-4" />
          Back to {job.title}
        </Link>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              Application
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-brand-900">
              Apply for this role
            </h1>
            <p className="mt-1 text-sm text-brand-300">
              Upload your CV first to pre-fill the form. Cover letter is optional.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[12px] font-medium text-brand-700 shadow-sm ring-1 ring-brand-200/70">
              <Briefcase className="size-3.5 text-brand-600" />
              {employmentLabel}
            </span>
            {job.department ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[12px] font-medium text-brand-700 shadow-sm ring-1 ring-brand-200/70">
                <Building2 className="size-3.5 text-brand-600" />
                {job.department}
              </span>
            ) : null}
            {job.location ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[12px] font-medium text-brand-700 shadow-sm ring-1 ring-brand-200/70">
                <MapPin className="size-3.5 text-brand-600" />
                {job.location}
              </span>
            ) : null}
          </div>
        </div>

        <section className={cn(card, "px-5 py-4")}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
            Applying for
          </p>
          <p className="mt-1 text-base font-semibold text-brand-900">{job.title}</p>
        </section>

        {(error || fieldError) && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {fieldError || error}
          </div>
        )}
        {(extractHint || extracting) && !error && !fieldError ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            {extracting ? "Reading your CV…" : extractHint}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-5">
          <Section
            icon={<Upload className="size-4" />}
            title="Documents"
            subtitle="CV is required. PDF unlocks automatic pre-fill."
          >
            <FileField
              label="CV"
              required
              file={cv}
              onChange={(file) => void handleCvSelected(file)}
              hint="PDF, DOC, or DOCX. Max 5 MB."
            />
            <FileField
              label="Cover letter"
              file={coverLetter}
              onChange={setCoverLetter}
              hint="Optional"
            />
          </Section>

          <Section
            icon={<UserRound className="size-4" />}
            title="Contact"
            subtitle="We’ll use this to reach you about interviews"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Email" id="apply-email">
                <input
                  id="apply-email"
                  type="email"
                  value={user?.email || ""}
                  readOnly
                  className={cn(field, "bg-[#f7faf9] text-brand-700")}
                />
                <p className="mt-1.5 text-[12px] text-brand-300">
                  Email on your candidate account
                </p>
              </Field>
              <Field label="Phone number" id="apply-phone" required>
                <input
                  id="apply-phone"
                  type="tel"
                  required
                  minLength={8}
                  maxLength={30}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+212 648 050 664"
                  className={field}
                />
              </Field>
            </div>
          </Section>

          <Section
            icon={<GraduationCap className="size-4" />}
            title="Education / training"
            subtitle="At least one institution is required"
          >
            <div className="space-y-3">
              {education.map((item, index) => (
                <div
                  key={index}
                  className="space-y-3 rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                      Education {index + 1}
                    </p>
                    {education.length > 1 ? (
                      <button
                        type="button"
                        onClick={() =>
                          setEducation(education.filter((_, i) => i !== index))
                        }
                        className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 hover:text-rose-800"
                      >
                        <Trash2 className="size-3.5" />
                        Remove
                      </button>
                    ) : null}
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <input
                      required
                      placeholder="Institution"
                      value={item.institution}
                      onChange={(e) => {
                        const next = [...education];
                        next[index] = { ...item, institution: e.target.value };
                        setEducation(next);
                      }}
                      className={field}
                    />
                    <input
                      placeholder="Degree (optional)"
                      value={item.degree || ""}
                      onChange={(e) => {
                        const next = [...education];
                        next[index] = { ...item, degree: e.target.value };
                        setEducation(next);
                      }}
                      className={field}
                    />
                    <input
                      placeholder="Field of study (optional)"
                      value={item.field_of_study || ""}
                      onChange={(e) => {
                        const next = [...education];
                        next[index] = {
                          ...item,
                          field_of_study: e.target.value,
                        };
                        setEducation(next);
                      }}
                      className={cn(field, "sm:col-span-2")}
                    />
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setEducation([...education, emptyEducation()])}
                className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3 text-xs font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
              >
                <Plus className="size-3.5" />
                Add education
              </button>
            </div>
          </Section>

          <Section
            icon={<Briefcase className="size-4" />}
            title="Experience"
            subtitle="At least one role with company and title is required"
          >
            <div className="space-y-3">
              {experience.map((item, index) => (
                <div
                  key={index}
                  className="space-y-3 rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                      Experience {index + 1}
                    </p>
                    {experience.length > 1 ? (
                      <button
                        type="button"
                        onClick={() =>
                          setExperience(
                            experience.filter((_, i) => i !== index)
                          )
                        }
                        className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 hover:text-rose-800"
                      >
                        <Trash2 className="size-3.5" />
                        Remove
                      </button>
                    ) : null}
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <input
                      required
                      placeholder="Company"
                      value={item.company}
                      onChange={(e) => {
                        const next = [...experience];
                        next[index] = { ...item, company: e.target.value };
                        setExperience(next);
                      }}
                      className={field}
                    />
                    <input
                      required
                      placeholder="Title"
                      value={item.title}
                      onChange={(e) => {
                        const next = [...experience];
                        next[index] = { ...item, title: e.target.value };
                        setExperience(next);
                      }}
                      className={field}
                    />
                    <textarea
                      placeholder="Description (optional)"
                      value={item.description || ""}
                      onChange={(e) => {
                        const next = [...experience];
                        next[index] = { ...item, description: e.target.value };
                        setExperience(next);
                      }}
                      className={cn(area, "sm:col-span-2")}
                      rows={3}
                    />
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setExperience([...experience, emptyExperience()])
                }
                className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3 text-xs font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
              >
                <Plus className="size-3.5" />
                Add experience
              </button>
            </div>
          </Section>

          {(job.questions || []).length > 0 ? (
            <Section
              icon={<CircleHelp className="size-4" />}
              title="Questions for this job"
              subtitle={`${job.questions.length} question${
                job.questions.length === 1 ? "" : "s"
              }`}
            >
              <div className="space-y-4">
                {job.questions.map((question) => (
                  <QuestionField
                    key={question.id}
                    question={question}
                    value={answers[question.id] || ""}
                    onChange={(value) =>
                      setAnswers({ ...answers, [question.id]: value })
                    }
                  />
                ))}
              </div>
            </Section>
          ) : null}

          <section className={cn(card, "overflow-visible")}>
            <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
                  <Sparkles className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-brand-900">
                    Ready to submit?
                  </p>
                  <p className="mt-0.5 text-[13px] text-brand-300">
                    Review your details, then send your application.
                  </p>
                </div>
              </div>
              <button
                type="submit"
                disabled={submitting || extracting}
                className="inline-flex h-10 items-center justify-center rounded-xl bg-brand-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-50"
              >
                {submitting ? "Submitting…" : "Submit application"}
              </button>
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
      <div className="space-y-4 p-5">{children}</div>
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

function FileField({
  label,
  required,
  file,
  onChange,
  hint,
}: {
  label: string;
  required?: boolean;
  file: File | null;
  onChange: (file: File | null) => void;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-dashed border-brand-200 bg-[#f7faf9] p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-brand-900">
            {label}
            {required ? <span className="text-rose-500"> *</span> : null}
          </p>
          <p className="mt-0.5 truncate text-[12px] text-brand-300">
            {file ? file.name : hint || "Choose a file"}
          </p>
        </div>
        <label className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3 text-xs font-semibold text-brand-700 transition hover:bg-white">
          <FileText className="size-3.5" />
          {file ? "Change file" : "Choose file"}
          <input
            type="file"
            accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="sr-only"
            onChange={(e) => onChange(e.target.files?.[0] || null)}
          />
        </label>
      </div>
    </div>
  );
}

function QuestionField({
  question,
  value,
  onChange,
}: {
  question: JobQuestion;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4">
      <p className="text-sm font-semibold text-brand-900">
        {question.prompt}
        {question.required ? (
          <span className="text-rose-500"> *</span>
        ) : (
          <span className="ml-1 text-[12px] font-medium text-brand-300">
            (optional)
          </span>
        )}
      </p>
      {question.question_type === "long_text" ? (
        <textarea
          required={question.required}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(area, "mt-3")}
          rows={4}
        />
      ) : question.question_type === "yes_no" ? (
        <div className="mt-3 flex gap-4 text-sm font-medium text-brand-700">
          <label className="inline-flex items-center gap-2">
            <input
              type="radio"
              name={`q-${question.id}`}
              checked={value === "yes"}
              onChange={() => onChange("yes")}
              required={question.required}
              className="size-4 border-[#0f224a]/30 text-brand-600 focus:ring-[#0f224a]/20"
            />
            Yes
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="radio"
              name={`q-${question.id}`}
              checked={value === "no"}
              onChange={() => onChange("no")}
              className="size-4 border-[#0f224a]/30 text-brand-600 focus:ring-[#0f224a]/20"
            />
            No
          </label>
        </div>
      ) : (
        <input
          required={question.required}
          type={question.question_type === "number" ? "number" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(field, "mt-3")}
        />
      )}
    </div>
  );
}
